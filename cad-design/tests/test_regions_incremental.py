from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from test_revision import ROOT, brief
import new_project
from cadkit import Assembly, Instance, Part, Placement, VisualRegion
from cadkit.assembly import solid_mesh
from cadkit.geometry import box, cylinder
from cadkit.revision import advance_revision, make_snapshot, verify_export
from cadkit.validation import Context, check_browser, check_exports


def three_parts():
    head = box(40, 20, 20)
    for x in (12, 28):
        head += cylinder(3, 4).rotate((90, 0, 0)).translate((x, 0, 12))
    mesh = solid_mesh(head)
    centers = mesh.triangles_center
    front = np.flatnonzero((np.abs(centers[:, 1]) < 1e-6) & (mesh.face_normals[:, 1] < -.9))
    eyes = np.flatnonzero(centers[:, 1] < -.001)
    assembly = Assembly("Illustrative three-part finish fixture, not Nuvi", "+X right, +Y back, +Z up; mm",
                        revision=make_snapshot(brief()))
    assembly.add_part(Part("head", head, "Head", "Nominal display polymer", "#00aabb",
                           visual_regions=(VisualRegion("face", "Black face finish", "#111111", tuple(front)),
                                           VisualRegion("eyes", "White eye finish", "#ffffff", tuple(eyes)))))
    assembly.add_part(Part("body", box(30, 20, 35), "Body", "Nominal display polymer", "#dd7744"))
    assembly.add_part(Part("pin", cylinder(2, 14), "Pin", "Nominal display polymer", "#889999"))
    for name, pos in (("head", (0, 0, 0)), ("body", (5, 0, -55)), ("pin", (20, 10, -18))):
        assembly.add_instance(Instance(name, name, Placement(pos)))
    return assembly


class RegionTests(unittest.TestCase):
    def test_three_connected_parts_retain_disjoint_finishes_in_stl_glb_and_review(self):
        assembly = three_parts()
        with tempfile.TemporaryDirectory() as directory:
            output = assembly.export(Path(directory) / "output")
            check_exports(Context(assembly), output)
            self.assertEqual(len(list((output / "parts").glob("*.stl"))), 3)
            self.assertEqual(len(list((output / "assembled").glob("*.stl"))), 3)
            self.assertTrue(all(len(p.solid.decompose()) == 1 for p in assembly.parts.values()))
            scene = assembly.viewer_scene()
            self.assertEqual(set(scene["physical_instances"]), {"head", "body", "pin"})
            self.assertEqual(len(scene["parts"]), 5)
            self.assertEqual(sum(p["triangles"] for p in scene["parts"]),
                             sum(len(m.faces) for m in assembly.meshes()[1].values()))
            colors = {p["region_id"]: p["color"] for p in scene["parts"] if p["region_id"]}
            self.assertEqual(colors, {"face": "#111111", "eyes": "#ffffff"})
            before = (output / "review.html").read_bytes()
            assembly.export(output)
            self.assertEqual(before, (output / "review.html").read_bytes())

    def test_bad_or_overlapping_regions_and_disconnected_physical_parts_are_rejected(self):
        for regions in (
            (VisualRegion("a", "A", "#ffffff", (0,)), VisualRegion("b", "B", "#111111", (0,))),
            (VisualRegion("a", "A", "#ffffff", (9999,)),),
            (VisualRegion("a", "A", "#ffffff", (0,)), VisualRegion("A", "A", "#ffffff", (1,))),
        ):
            with self.assertRaises(ValueError):
                Part("p", box(2, 2, 2), "P", "Nominal", "#ffffff", visual_regions=regions)
        with self.assertRaisesRegex(ValueError, "connected"):
            Part("p", box(2, 2, 2)+box(2, 2, 2).translate((5, 0, 0)), "P", "Nominal",
                 "#ffffff", visual_regions=(VisualRegion("a", "A", "#ffffff", (0,)),))
        with self.assertRaises(ValueError):
            VisualRegion("a", "A", "#ffffff", (True,))

    def test_untracked_export_cannot_hide_a_tampered_region_mapping(self):
        assembly = three_parts()
        assembly.revision = None
        with tempfile.TemporaryDirectory() as directory:
            output = assembly.export(directory)
            path = output / "manifest.json"
            manifest = json.loads(path.read_text())
            manifest["parts"][0]["visual_regions"][0]["triangles"] = [99999]
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "region mapping"):
                check_exports(Context(assembly), output)

    @unittest.skipUnless(os.environ.get("CADKIT_VIEWER_ASSETS"), "Supply trusted optional assets")
    def test_embedded_backend_preserves_surface_to_physical_mapping(self):
        assembly = three_parts()
        with tempfile.TemporaryDirectory() as directory:
            output = assembly.export(directory, viewer_backend="embedded",
                                     viewer_assets=os.environ["CADKIT_VIEWER_ASSETS"])
            check_exports(Context(assembly), output)
            if os.environ.get("CADKIT_BROWSER"):
                check_browser(output, 3, os.environ["CADKIT_BROWSER"])

    @unittest.skipUnless(os.environ.get("CADKIT_BROWSER"), "Supply browser for real finish raster")
    def test_lightweight_real_browser_renders_regions_without_extra_physical_parts(self):
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory() as directory:
            output = three_parts().export(directory)
            check_browser(output, 3, os.environ["CADKIT_BROWSER"])
            with sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path=os.environ["CADKIT_BROWSER"], headless=True,
                                            args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
                try:
                    page = browser.new_page(viewport={"width": 1500, "height": 1050})
                    page.goto((output / "viewer.html").as_uri())
                    page.locator("#front").click()
                    pixels = page.evaluate("""()=>{
                        draw();const b=new Uint8Array(canvas.width*canvas.height*4);
                        gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,b);
                        let white=0,black=0;for(let i=0;i<b.length;i+=4){
                        if(Math.min(b[i],b[i+1],b[i+2])>190)white++;
                        if(Math.max(b[i],b[i+1],b[i+2])<22)black++;}
                        return {white,black};}""")
                    self.assertGreater(pixels["white"], 100)
                    self.assertGreater(pixels["black"], 100)
                finally:
                    browser.close()


class IncrementalTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("CADKIT_BROWSER"), "Full-tier replay requires actual browser checks")
    def test_unsorted_multi_fact_and_decision_patch_survives_saved_snapshot_and_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")
            source_path = project / "design_brief.json"
            source = json.loads(source_path.read_bytes())
            choice = {"status": "selected", "blocks_modeling": True,
                      "selected_option": "Initial layout", "source": "Fictional initial choice"}
            source["decisions"] = {name: dict(choice) for name in ("z_layout", "a_layout", "z_old", "a_old")}
            source_path.write_text(json.dumps(source), encoding="utf-8")
            self.cli(project, "qualify")
            updates = {name: dict(source["dimensions"][name], value=value, source="Fictional correction")
                       for name, value in (("width", 124), ("gap", 40), ("depth", 84))}
            patch = {
                "decisions": {name: dict(choice, selected_option="Revised layout")
                              for name in ("z_layout", "a_layout")},
                "retire_decisions": {
                    "z_old": {"replaced_by": "z_layout", "source": "Explicit replacement"},
                    "a_old": {"replaced_by": "a_layout", "source": "Explicit replacement"},
                },
            }
            update_path, patch_path = project / "updates.json", project / "choices.json"
            update_path.write_text(json.dumps(updates), encoding="utf-8")
            patch_path.write_text(json.dumps(patch), encoding="utf-8")
            expected = make_snapshot(advance_revision(source, "multiple", "Multiple sourced corrections",
                                                      updates=updates, brief_updates=patch))
            self.cli(project, "revise", "--tier", "topology", "--revision", "multiple",
                     "--delta", "Multiple sourced corrections", "--updates", update_path,
                     "--brief-updates", patch_path, browser=True)
            handoff = json.loads(self.cli(project, "verify", "--include-packet").stdout)
            self.assertEqual(handoff["revision"], expected["identity"])
            self.assertEqual(json.loads((project / "output" / "revision-state.json").read_bytes()), expected)
            verify_export(expected, project / "output", require_validation=True)

    def cli(self, project, *args, success=True, browser=False):
        env = dict(os.environ)
        if not browser:
            env.pop("CADKIT_BROWSER", None)
        result = subprocess.run([sys.executable, "-m", "cadkit.incremental", *map(str, args)],
                                cwd=project, env=env, capture_output=True, text=True, timeout=120)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def correction(self, project, name="gap", value=40):
        source = json.loads((project / "design_brief.json").read_text())
        path = project / "correction.json"
        path.write_text(json.dumps({name: dict(source["dimensions"][name], value=value,
                                              source="Explicit qualification fixture correction")}), encoding="utf-8")
        return path

    def test_blocked_admission_and_forged_semantic_fields_leave_accepted_project_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")
            self.cli(project, "qualify")
            path = Path(directory) / "brief-updates.json"
            for patch in (
                {"decisions": {"shape": {"status": "awaiting_choice", "blocks_modeling": True,
                                        "selected_option": None, "source": "User has not chosen"}}},
                {"revision": {"id": "forged"}}, {"stage": "fabrication-approved"},
                {"deliverable": {"status": "awaiting_choice", "target": None, "outputs": [],
                                 "sequence": [], "source": "User has not chosen reference or case"}},
                {"decisions": {"shape": {"status": "selected", "blocks_modeling": True,
                                        "selected_option": "flat", "source": ""}}},
            ):
                path.write_text(json.dumps(patch), encoding="utf-8")
                before = {p.relative_to(project): p.read_bytes() for p in project.rglob("*")
                          if p.is_file() and "__pycache__" not in p.parts}
                result = self.cli(project, "revise", "--tier", "topology", "--browser", sys.executable,
                                  "--revision", "blocked", "--delta", "Must reject",
                                  "--brief-updates", path, success=False)
                self.assertIn("Unresolved immediate deliverable" if "deliverable" in patch else
                              "Unresolved modeling" if "decisions" in patch and
                              patch["decisions"]["shape"]["status"] == "awaiting_choice" else
                              ("Brief updates allow" if "decisions" not in patch else "source"),
                              result.stdout+result.stderr)
                self.assertEqual(before, {p.relative_to(project): p.read_bytes() for p in project.rglob("*")
                                          if p.is_file() and "__pycache__" not in p.parts})

    def test_blocking_initial_brief_stops_qualify_model_and_validation_before_artifact_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")
            path = project / "design_brief.json"
            source = json.loads(path.read_text())
            source["decisions"] = {"shape": {"status": "awaiting_choice", "blocks_modeling": True,
                                             "selected_option": None, "source": "User is unsure"}}
            path.write_text(json.dumps(source), encoding="utf-8")
            output = project / "output"
            output.mkdir()
            (output / "preview-ready.json").write_bytes(b"Retained prior diagnostic marker")
            before = {p.relative_to(project): p.read_bytes() for p in project.rglob("*")
                      if p.is_file() and "__pycache__" not in p.parts}
            self.cli(project, "qualify", success=False)
            for command in ("model.py", "validate.py"):
                result = subprocess.run([sys.executable, command], cwd=project, capture_output=True,
                                        text=True, timeout=30)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Unresolved modeling", result.stdout+result.stderr)
            self.assertEqual(before, {p.relative_to(project): p.read_bytes() for p in project.rglob("*")
                                      if p.is_file() and "__pycache__" not in p.parts})

    def test_scalar_correction_can_synchronize_descriptions_but_cannot_change_decisions(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")
            self.cli(project, "qualify")
            patch = Path(directory) / "descriptions.json"
            patch.write_text(json.dumps({"assumptions": ["Updated concept caveat; not approved"]}), encoding="utf-8")
            original_plate = (project / "output" / "parts" / "plate.stl").read_bytes()
            self.cli(project, "revise", "--revision", "gap-description", "--delta", "Correct gap and description",
                     "--updates", self.correction(project), "--brief-updates", patch,
                     "--preserve", "dimensions.width")
            self.cli(project, "verify")
            source = json.loads((project / "design_brief.json").read_text())
            self.assertEqual(source["assumptions"], ["Updated concept caveat; not approved"])
            self.assertEqual(source["dimensions"]["gap"]["value"], 40)
            self.assertEqual(original_plate, (project / "output" / "parts" / "plate.stl").read_bytes())
            before = (project / "design_brief.json").read_bytes()
            for semantic in (
                {"decisions": {"shape": {"status": "selected", "blocks_modeling": True,
                                        "selected_option": "flat", "source": "User selected flat"}}},
                {"retire_decisions": {"shape": {"replaced_by": "other", "source": "Explicit replacement"}}},
                {"deliverable": {"status": "selected", "target": "Riser plus concept sheets",
                                 "outputs": ["Review", "Drawings"], "sequence": ["Review geometry", "Draw sheets"],
                                 "source": "Explicit deliverable selection"}},
            ):
                patch.write_text(json.dumps(semantic), encoding="utf-8")
                rejected = self.cli(project, "revise", "--revision", "wrong-tier", "--delta", "Wrong scalar tier",
                                    "--updates", self.correction(project, value=42), "--brief-updates", patch, success=False)
                self.assertIn("Decision/intent changes require topology", rejected.stdout+rejected.stderr)
                self.assertEqual(before, (project / "design_brief.json").read_bytes())

    @unittest.skipUnless(os.environ.get("CADKIT_BROWSER"), "Decision changes require real full-tier checks")
    def test_supported_topology_decision_update_is_bound_checked_and_not_user_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")
            self.cli(project, "qualify")
            patch = Path(directory) / "selected.json"
            patch.write_text(json.dumps({
                "decisions": {"riser_layout": {"status": "selected", "blocks_modeling": True,
                                             "selected_option": "standard", "source": "Fictional user selects standard layout"}},
                "intent": "Record standard layout without fabrication approval",
                "open_decisions": []}), encoding="utf-8")
            handoff = json.loads(self.cli(project, "revise", "--tier", "topology", "--revision", "layout-selected",
                                          "--delta", "Record selected standard layout", "--brief-updates", patch,
                                          browser=True).stdout.splitlines()[-1])
            self.assertEqual(handoff["tier"], "topology")
            source = json.loads((project / "design_brief.json").read_text())
            self.assertEqual(source["decisions"]["riser_layout"]["selected_option"], "standard")
            self.assertIsNone(source["revision"]["user_approval"])
            self.assertEqual(source["revision"]["open_decisions"], [])
            self.assertEqual(json.loads((project / "output" / "revision-state.json").read_text())["brief"], source)
            self.cli(project, "verify")
            patch.write_text(json.dumps({
                "decisions": {"layout_v2": dict(source["decisions"]["riser_layout"],
                                               source="Fictional explicit replacement choice")},
                "retire_decisions": {"riser_layout": {
                    "replaced_by": "layout_v2", "source": "Fictional sourced layout supersession"}},
            }), encoding="utf-8")
            self.cli(project, "revise", "--tier", "topology", "--revision", "layout-retired",
                     "--delta", "Replace prior layout decision", "--brief-updates", patch, browser=True)
            source = json.loads((project / "design_brief.json").read_text())
            self.assertEqual(set(source["decisions"]), {"layout_v2"})
            history = source["revision"]["superseded_decisions"][-1]
            self.assertEqual(history["name"], "riser_layout")
            self.assertEqual(history["replaced_by"], "layout_v2")
            self.assertEqual(history["revision_id"], "layout-selected")
            self.assertIsNone(source["revision"]["user_approval"])
            self.cli(project, "verify", "--include-packet")

    def test_revision_builds_once_but_standalone_validation_rebuilds(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")
            with (project / "model.py").open("a", encoding="utf-8") as file:
                file.write('\n_original_build = build\n'
                           'def build(*args, **kwargs):\n'
                           '    with (ROOT / "build-calls.txt").open("a") as calls:\n'
                           '        calls.write("build\\n")\n'
                           '    return _original_build(*args, **kwargs)\n')
            self.cli(project, "qualify")
            self.assertEqual((project / "build-calls.txt").read_text().splitlines(), ["build"])
            self.cli(project, "revise", "--revision", "once-02", "--delta", "Gap correction",
                     "--updates", self.correction(project))
            self.assertEqual(len((project / "build-calls.txt").read_text().splitlines()), 2)
            env = dict(os.environ)
            env.pop("CADKIT_BROWSER", None)
            result = subprocess.run([sys.executable, "validate.py"], cwd=project, env=env,
                                    capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len((project / "build-calls.txt").read_text().splitlines()), 3)
            self.cli(project, "verify", success=False)  # Standalone checks retire qualification.

    def test_export_time_source_or_brief_drift_rejects_reuse_before_project_checks(self):
        for target in ("checks.py", "design_brief.json"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as directory:
                project = new_project.create_project(Path(directory) / "project")
                with (project / "model.py").open("a", encoding="utf-8") as file:
                    file.write('\n_original_build = build\n'
                               'def build(*args, **kwargs):\n'
                               '    assembly = _original_build(*args, **kwargs)\n'
                               '    original_export = assembly.export\n'
                               '    def drift(*a, **k):\n'
                               '        result = original_export(*a, **k)\n'
                               f'        path = ROOT / {target!r}\n'
                               '        text = path.read_text(encoding="utf-8")\n')
                    if target == "checks.py":
                        file.write('        path.write_text(text + "\\n# external write\\n", encoding="utf-8")\n')
                    else:
                        file.write('        source = json.loads(text)\n'
                                   '        source["dimensions"]["gap"]["value"] += 1\n'
                                   '        path.write_text(json.dumps(source), encoding="utf-8")\n')
                    file.write('        return result\n'
                               '    assembly.export = drift\n'
                               '    return assembly\n')
                with (project / "checks.py").open("a", encoding="utf-8") as file:
                    file.write('\ndef check(context):\n'
                               '    raise AssertionError("Project checks must not run after drift")\n')
                result = self.cli(project, "qualify", success=False)
                self.assertIn("before revision validation", result.stderr)
                self.assertNotIn("Project checks must not run after drift", result.stderr)
                self.assertFalse((project / "output" / "incremental-state.json").exists())
                last = json.loads((project / "output" / "incremental-last.json").read_text())
                self.assertEqual(last["status"], "failed")

    def test_source_drift_during_project_checks_still_retires_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")
            with (project / "checks.py").open("a", encoding="utf-8") as file:
                file.write('\n_original_check = check\n'
                           'def check(context):\n'
                           '    result = _original_check(context)\n'
                           '    with Path(__file__).open("a", encoding="utf-8") as source:\n'
                           '        source.write("\\n# external write during checks\\n")\n'
                           '    return result\n')
            result = self.cli(project, "qualify", success=False)
            self.assertIn("Source or environment changed during revision checks", result.stderr)
            self.assertFalse((project / "output" / "incremental-state.json").exists())

    def test_scalar_command_checks_dependencies_preserves_other_geometry_and_never_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")
            self.cli(project, "qualify")
            original_brief = (project / "design_brief.json").read_bytes()
            dependency_path = project / "dependencies.json"
            dependency_path.write_text(json.dumps(json.loads(original_brief)["revision"]["dependencies"]),
                                       encoding="utf-8")
            rejected = self.cli(project, "revise", "--revision", "wrong-tier", "--delta", "Wrong tier",
                                "--updates", self.correction(project), "--dependencies", dependency_path,
                                success=False)
            self.assertIn("Dependency-map changes require", rejected.stderr)
            self.assertEqual((project / "design_brief.json").read_bytes(), original_brief)
            old_plate = (project / "output" / "parts" / "plate.stl").read_bytes()
            self.cli(project, "revise", "--revision", "gap-corrected", "--delta", "Gap correction",
                     "--updates", self.correction(project), "--preserve", "dimensions.width")
            source = json.loads((project / "design_brief.json").read_text())
            self.assertEqual(source["dimensions"]["gap"]["value"], 40)
            self.assertEqual(source["revision"]["superseded_facts"][-1]["fact"]["value"], 32)
            self.assertEqual(old_plate, (project / "output" / "parts" / "plate.stl").read_bytes())
            result = json.loads((project / "output" / "incremental-last.json").read_text())
            self.assertEqual(result["affected"]["parts"], ["standoff"])
            self.assertEqual(result["affected"]["transforms"], ["top"])
            self.assertFalse(result["packaged"])
            self.assertEqual(result["validation_status"], "geometry_passed_browser_not_run")
            verify_export(make_snapshot(source), project / "output", require_validation=True)
            self.cli(project, "verify")
            handoff = json.loads(self.cli(project, "verify", "--include-packet").stdout)
            self.assertEqual(handoff["review_packet_data"],
                             json.loads((project / "output" / "review-state.json").read_text()))
            self.assertEqual(handoff["review_packet_json"],
                             (project / "output" / "review-state.json").read_bytes().decode("utf-8"))
            self.assertEqual(handoff["review_page"], (project / "output" / "review.html").as_uri())
            self.assertEqual(handoff["revision"]["id"], "gap-corrected")
            self.assertFalse(list(project.rglob("*.zip")))

    def test_changed_source_stale_exports_missing_scope_and_full_tier_without_browser_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")
            self.cli(project, "qualify")
            original = (project / "design_brief.json").read_bytes()
            patch = self.correction(project)
            for kind in ("source", "export", "full"):
                path = project / ("checks.py" if kind == "source" else "output/parts/plate.stl")
                prior = path.read_bytes()
                if kind != "full":
                    path.write_bytes(prior+b"\n")
                    self.cli(project, "verify", success=False)
                    self.cli(project, "verify", "--include-packet", success=False)
                args = ["revise", "--revision", "next", "--delta", "Correction", "--updates", patch]
                if kind == "full":
                    args += ["--tier", "topology"]
                self.cli(project, *args, success=False)
                self.assertEqual((project / "design_brief.json").read_bytes(), original)
                path.write_bytes(prior)
            source = json.loads(original)
            source["revision"]["dependencies"].pop("gap")
            (project / "design_brief.json").write_text(json.dumps(source), encoding="utf-8")
            self.cli(project, "qualify", success=False)

    def test_failed_checks_invalidate_handoff_and_retain_diagnostic_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")
            checks = project / "checks.py"
            with checks.open("a", encoding="utf-8") as file:
                file.write('\noriginal_check = check\n'
                           'def check(context):\n'
                           '    original_check(context)\n'
                           '    context.require(context.assembly.parameters["dimensions_mm"]["gap"] < 35, "fixture gap rejection")\n'
                           '    return {}\n')
            self.cli(project, "qualify")
            qualified = (project / "output" / "incremental-state.json").read_bytes()
            self.cli(project, "revise", "--revision", "rejected", "--delta", "Rejected correction",
                     "--updates", self.correction(project), success=False)
            self.assertFalse((project / "output" / "incremental-state.json").exists())
            report = json.loads((project / "output" / "validation.json").read_text())
            self.assertEqual(report["status"], "failed")
            source = json.loads((project / "design_brief.json").read_text())
            self.assertEqual(source["revision"]["id"], "rejected")
            self.assertIn(qualified, [p.read_bytes() for p in
                                     (project / "output" / "qualification-history").glob("*.json")])
            with self.assertRaises(ValueError):
                verify_export(make_snapshot(source), project / "output", require_validation=True)

    def test_alternate_exports_retire_current_qualification_and_preserve_its_exact_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            for mode in ("preview", "direct"):
                with self.subTest(mode=mode):
                    project = new_project.create_project(Path(directory) / mode)
                    self.cli(project, "qualify")
                    output = project / "output"
                    state = (output / "incremental-state.json").read_bytes()
                    handoff = (output / "incremental-last.json").read_bytes()
                    args = ["model.py"] if mode == "preview" else [
                        "-c", "import model; model.build().export('output')"]
                    result = subprocess.run([sys.executable, *args], cwd=project,
                                            capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual((output / "incremental-state.json").read_bytes(), state)
                    source_path = project / "design_brief.json"
                    source = json.loads(source_path.read_text())
                    revised = advance_revision(source, "alternate", "Alternate export",
                                               updates={"gap": dict(source["dimensions"]["gap"], value=40)})
                    source_path.write_text(json.dumps(revised), encoding="utf-8")
                    result = subprocess.run([sys.executable, *args], cwd=project,
                                            capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertFalse((output / "incremental-state.json").exists())
                    history = [p.read_bytes() for p in (output / "qualification-history").glob("*.json")]
                    self.assertIn(state, history)
                    self.assertIn(handoff, history)
                    self.assertEqual(json.loads((output / "incremental-last.json").read_text())["status"],
                                     "invalidated")
                    self.cli(project, "verify", success=False)
                    self.cli(project, "qualify")
                    self.cli(project, "verify")
                    self.assertIn(state, [p.read_bytes() for p in (output / "qualification-history").glob("*.json")])

    def test_standalone_validation_retires_qualification_without_erasing_prior_report(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")
            self.cli(project, "qualify")
            output = project / "output"
            original = {name: (output / name).read_bytes() for name in
                        ("incremental-state.json", "incremental-last.json", "manifest.json", "validation.json")}
            result = subprocess.run([sys.executable, "validate.py"], cwd=project, capture_output=True,
                                    text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((output / "incremental-state.json").exists())
            history = [p.read_bytes() for p in (output / "qualification-history").glob("*.json")]
            for content in original.values():
                self.assertIn(content, history)
            verify_export(make_snapshot(json.loads((project / "design_brief.json").read_text())),
                          output, require_validation=True)
            self.cli(project, "verify", "--include-packet", success=False)

    def test_missing_dependency_and_unlisted_geometry_are_rejected_by_scalar_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            for kind in ("missing", "unlisted"):
                project = new_project.create_project(Path(directory) / kind)
                if kind == "missing":
                    path = project / "design_brief.json"
                    source = json.loads(path.read_text())
                    source["revision"]["dependencies"].pop("gap")
                    path.write_text(json.dumps(source), encoding="utf-8")
                else:
                    path = project / "model.py"
                    text = path.read_text().replace(
                        "plate_with_holes(d.width, d.depth,", "plate_with_holes(d.width+d.gap-32, d.depth,")
                    path.write_text(text, encoding="utf-8")
                self.cli(project, "qualify")
                original_plate = (project / "output" / "parts" / "plate.stl").read_bytes()
                result = self.cli(project, "revise", "--revision", "bad", "--delta", "Scoped guard",
                                  "--updates", self.correction(project), success=False)
                self.assertIn("no declared dependency" if kind == "missing" else "Unlisted physical geometry",
                              result.stdout+result.stderr)
                self.assertEqual(original_plate, (project / "output" / "parts" / "plate.stl").read_bytes())

    @unittest.skipUnless(os.environ.get("CADKIT_BROWSER"), "Full tiers require actual browser checks")
    def test_topology_and_final_tiers_run_full_browser_checks_and_renew_qualification(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")
            self.cli(project, "qualify")
            model = project / "model.py"
            model.write_text(model.read_text().replace(
                "for x in (d.inset, d.width-d.inset) for y in (d.inset, d.depth-d.inset)]",
                "for x in (d.inset, d.width-d.inset) for y in (d.inset, d.depth-d.inset)]"
                " + [(d.width/2, d.depth/2, d.hole_diameter)]"), encoding="utf-8")
            checks = project / "checks.py"
            checks.write_text(checks.read_text().replace(
                'len(context.placed) == 6, "Expected 2 parts / 6 instances"',
                'len(context.placed) == 7, "Expected 2 parts / 7 instances"').replace(
                "centers = ((inset, inset), (inset, d-inset), (w-inset, inset), (w-inset, d-inset))",
                "centers = ((inset, inset), (inset, d-inset), (w-inset, inset), (w-inset, d-inset), (w/2, d/2))"
            ).replace("w*d-4*area", "w*d-5*area"), encoding="utf-8")
            original_brief = (project / "design_brief.json").read_bytes()
            self.cli(project, "verify", "--include-packet", success=False)
            dependencies = json.loads(original_brief)["revision"]["dependencies"]
            for targets in dependencies.values():
                if any(target.startswith("instances.standoff_") for target in targets):
                    targets.append("instances.standoff_5")
            dependency_path = project / "dependencies.json"
            dependency_path.write_text(json.dumps(dependencies), encoding="utf-8")
            self.cli(project, "revise", "--revision", "bad-scalar", "--delta", "Wrong tier",
                     "--updates", self.correction(project), "--dependencies", dependency_path, success=False)
            self.assertEqual(original_brief, (project / "design_brief.json").read_bytes())
            for tier in ("topology", "final"):
                self.cli(project, "revise", "--revision", tier, "--delta", "Full check fixture",
                         "--tier", tier, "--dependencies", dependency_path, browser=True)
                report = json.loads((project / "output" / "validation.json").read_text())
                self.assertEqual(report["status"], "passed")
                self.assertEqual(report["browser"]["status"], "passed")
                self.assertEqual(report["instances"], 7)
                self.assertEqual(json.loads((project / "design_brief.json").read_text())["revision"]["dependencies"],
                                 dependencies)
                self.cli(project, "verify", "--include-packet")
                self.assertFalse(json.loads((project / "output" / "incremental-last.json").read_text())["packaged"])

    @unittest.skipUnless(os.environ.get("CADKIT_BROWSER"), "Handoff requires an actual existing browser panel")
    def test_checked_packet_stages_scalar_revision_in_same_review_page(self):
        from playwright.sync_api import Error, sync_playwright

        with tempfile.TemporaryDirectory() as directory, sync_playwright() as pw:
            project = new_project.create_project(Path(directory) / "project")
            self.cli(project, "qualify")
            browser = pw.chromium.launch(executable_path=os.environ["CADKIT_BROWSER"], headless=True,
                                        args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            try:
                page = browser.new_page()
                requests = []
                page.on("request", lambda request: requests.append(request.url)
                        if request.url.startswith(("http:", "https:")) else None)
                page.goto((project / "output" / "review.html").as_uri())
                page.wait_for_function("cadReview.getState().view && !cadReview.getState().blocked")
                page.frame(name="current").wait_for_function("typeof initialized!=='undefined' && initialized")
                page.frame(name="current").evaluate(
                    "yaw+=.2;zoom=1.3;parts[0].visible=false;parts[0].checkbox.checked=false;draw()")
                page.wait_for_function("cadReview.getState().view.camera.zoom===1.3")
                camera = page.evaluate("cadReview.getState().view.camera")
                visibility = page.evaluate("cadReview.getState().view.visibility")
                self.cli(project, "revise", "--revision", "gap-corrected", "--delta", "Gap correction",
                         "--updates", self.correction(project))
                handoff = json.loads(self.cli(project, "verify", "--include-packet").stdout)
                page.evaluate("()=>{window.fetch=()=>{throw Error('Local-file fetching is forbidden in this test')}}")
                before = page.evaluate("cadReview.getState()")
                for defect in ("hash", "packet", "identity", "status", "malformed", "payload"):
                    bad = deepcopy(handoff)
                    if defect == "hash":
                        bad["review_packet_sha256"] = "0"*64
                    elif defect == "packet":
                        bad["review_packet_json"] += " "
                    elif defect == "identity":
                        bad["revision"]["id"] = "wrong"
                    elif defect == "status":
                        bad["status"] = "failed"
                    else:
                        bad["review_packet_json"] = ("{" if defect == "malformed"
                            else json.dumps(dict(bad["review_packet_data"], sha256="0"*64)))
                        bad["review_packet_sha256"] = hashlib.sha256(
                            bad["review_packet_json"].encode("utf-8")).hexdigest()
                    with self.subTest(defect=defect), self.assertRaises(Error):
                        page.evaluate("h=>cadReview.loadHandoff(h)", bad)
                    self.assertEqual(page.evaluate("cadReview.getState()"), before)
                self.assertEqual(page.evaluate("h=>cadReview.loadHandoff(h)", handoff)["status"],
                                 "pending")
                state = page.evaluate("cadReview.getState()")
                self.assertEqual(state["revision"]["id"], "initial")
                self.assertEqual(state["pending"], handoff["revision"])
                self.assertEqual(state["view"]["camera"], camera)
                self.assertEqual(state["view"]["visibility"], visibility)
                bad = deepcopy(handoff)
                bad["review_packet_sha256"] = "0"*64
                with self.assertRaises(Error):
                    page.evaluate("h=>cadReview.loadHandoff(h)", bad)
                self.assertEqual(page.evaluate("cadReview.getState()"), state)
                page.locator("#apply").click()
                self.assertEqual(page.evaluate("cadReview.getState().revision"), handoff["revision"])
                self.assertEqual(page.evaluate("cadReview.getState().view.camera"), camera)
                self.assertEqual(page.evaluate("cadReview.getState().view.visibility"), visibility)
                self.assertEqual(requests, [])
                self.assertEqual(page.url, (project / "output" / "review.html").as_uri())
            finally:
                browser.close()

    @unittest.skipUnless(os.environ.get("CADKIT_BROWSER"), "Recovery requires actual full browser checks")
    def test_explicit_recovery_advances_failed_export_without_manual_lineage_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")
            self.cli(project, "qualify")
            model = project / "model.py"
            correct = model.read_text()
            model.write_text(correct.replace("spacer = cylinder(d.standoff_radius, d.gap)",
                                             "spacer = cylinder(d.standoff_radius, d.gap+1)"), encoding="utf-8")
            self.cli(project, "revise", "--revision", "failed-shape", "--delta", "Gap correction",
                     "--updates", self.correction(project), "--tier", "topology", browser=True, success=False)
            output = project / "output"
            failed = (output / "incremental-last.json").read_bytes()
            failed_stl = (output / "parts" / "standoff.stl").read_bytes()
            self.assertEqual(json.loads(failed)["status"], "failed")
            model.write_text(correct, encoding="utf-8")
            original_brief = (project / "design_brief.json").read_bytes()
            for args in (["--tier", "topology"], ["--recover"]):
                self.cli(project, "revise", "--revision", "repaired", "--delta", "Repair model construction",
                         *args, browser=True, success=False)
                self.assertEqual((project / "design_brief.json").read_bytes(), original_brief)
            self.cli(project, "revise", "--revision", "repaired", "--delta", "Repair model construction",
                     "--recover", "--tier", "topology", browser=True)
            self.cli(project, "verify", "--include-packet")
            source = json.loads((project / "design_brief.json").read_text())
            self.assertEqual(source["revision"]["parent_id"], "failed-shape")
            self.assertEqual(source["dimensions"]["gap"]["value"], 40)
            self.assertNotEqual(failed_stl, (output / "parts" / "standoff.stl").read_bytes())
            self.assertIn(failed, [p.read_bytes() for p in (output / "qualification-history").glob("*.json")])
            self.assertTrue(json.loads((output / "incremental-last.json").read_text())["recovery"])
            self.cli(project, "revise", "--revision", "not-a-failure", "--delta", "Invalid recovery",
                     "--recover", "--tier", "topology", browser=True, success=False)
