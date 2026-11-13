from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "foundation"))
import new_project
from cadkit import Assembly, Instance, Part
from cadkit.geometry import box
from cadkit.preview import export_preview
from cadkit.revision import (
    advance_revision, make_snapshot, restore_snapshot, sha256,
    require_modeling_ready, validate_brief, validate_snapshot, verify_export,
)
from cadkit.validation import Context, check_exports


def brief():
    return json.loads((ROOT / "templates" / "design_brief.json").read_text(encoding="utf-8"))


def fixture(source):
    dimensions = source["dimensions"]
    assembly = Assembly(source["name"], source["coordinate_system"],
                        parameters={"dimensions": deepcopy(dimensions)}, revision=make_snapshot(source))
    assembly.add_part(Part("plate", box(dimensions["width"]["value"], 10, 2),
                           "Plate", "Illustrative", "#58b9c9"))
    assembly.add_instance(Instance("plate", "plate"))
    return assembly


class RevisionTests(unittest.TestCase):
    def test_new_history_is_order_independent_without_rewriting_existing_history(self):
        source = brief()
        choice = {"status": "selected", "blocks_modeling": True,
                  "selected_option": "Initial concept", "source": "Fictional initial choice"}
        source["decisions"] = {name: deepcopy(choice) for name in ("z_shape", "a_shape", "z_old", "a_old")}
        source = advance_revision(source, "prior", "Prior sourced corrections",
                                  updates={"width": dict(source["dimensions"]["width"], value=122)})
        # Older valid history need not have been sorted; it must retain its identity.
        source["revision"]["superseded_facts"].insert(0, {
            "name": "z_legacy", "revision_id": "initial",
            "fact": dict(source["dimensions"]["depth"], source="Historical preserved fact")})
        original = deepcopy(source)
        updates = {name: dict(source["dimensions"][name], value=value)
                   for name, value in (("width", 124), ("gap", 40), ("depth", 84))}
        patch = {
            "decisions": {name: dict(choice, selected_option="Revised concept")
                          for name in ("z_shape", "a_shape")},
            "retire_decisions": {
                "z_old": {"replaced_by": "z_shape", "source": "Explicit replacement"},
                "a_old": {"replaced_by": "a_shape", "source": "Explicit replacement"},
            },
        }
        revised = advance_revision(source, "multiple", "Multiple sourced changes", updates=updates, brief_updates=patch)
        normalized = json.loads(json.dumps({"updates": updates, "patch": patch}, sort_keys=True))
        replay = advance_revision(json.loads(json.dumps(source, sort_keys=True)), "multiple",
                                  "Multiple sourced changes", updates=normalized["updates"],
                                  brief_updates=normalized["patch"])
        self.assertEqual(make_snapshot(revised), make_snapshot(replay))
        self.assertEqual(revised["revision"]["superseded_facts"][:2], source["revision"]["superseded_facts"])
        self.assertEqual([entry["name"] for entry in revised["revision"]["superseded_facts"][2:]],
                         ["depth", "gap", "width"])
        self.assertEqual([entry["name"] for entry in revised["revision"]["superseded_decisions"]],
                         ["a_shape", "z_shape", "a_old", "z_old"])
        validate_snapshot(make_snapshot(revised))
        self.assertEqual(source, original)

    def test_decision_replacement_and_retirement_leave_only_current_choices_and_sourced_history(self):
        source = brief()
        selected = {"status": "selected", "blocks_modeling": True,
                    "selected_option": "Lift-off lid", "source": "Fictional initial choice"}
        source["decisions"] = {"case_style": selected, "material": dict(selected, selected_option="Birch")}
        updated = advance_revision(source, "screw-02", "Select screw closure", brief_updates={
            "decisions": {"closure": dict(selected, selected_option="Circular screw-on lid",
                                         source="Fictional user selects threaded closure")},
            "retire_decisions": {"case_style": {
                "replaced_by": "closure", "source": "Threaded closure replaces lift-off design"}},
        })
        self.assertNotIn("case_style", updated["decisions"])
        self.assertEqual(updated["decisions"]["material"], source["decisions"]["material"])
        self.assertEqual(updated["revision"]["superseded_decisions"], [{
            "name": "case_style", "revision_id": "initial", "decision": selected,
            "replaced_by": "closure", "source": "Threaded closure replaces lift-off design",
        }])
        next_choice = dict(updated["decisions"]["closure"], selected_option="Coarse circular screw")
        latest = advance_revision(updated, "screw-03", "Refine closure", brief_updates={
            "decisions": {"closure": next_choice}})
        self.assertEqual(latest["revision"]["superseded_decisions"][-1]["decision"],
                         updated["decisions"]["closure"])
        self.assertEqual(latest["decisions"]["closure"], next_choice)
        validate_snapshot(make_snapshot(latest))
        require_modeling_ready(latest)
        chained = advance_revision(latest, "closure-04", "Replace closure ID", brief_updates={
            "decisions": {"final_closure": next_choice},
            "retire_decisions": {"closure": {"replaced_by": "final_closure", "source": "Explicit replacement"}},
        })
        validate_snapshot(make_snapshot(chained))
        self.assertNotIn("closure", chained["decisions"])
        self.assertEqual(len(chained["revision"]["superseded_decisions"]), 3)
        self.assertIn("case_style", source["decisions"])
        self.assertNotIn("superseded_decisions", source["revision"])
        self.assertIsNone(latest["revision"]["user_approval"])
        unchanged = advance_revision(latest, "same-04", "No decision change", brief_updates={
            "decisions": {"closure": next_choice}})
        self.assertEqual(unchanged["revision"]["superseded_decisions"],
                         latest["revision"]["superseded_decisions"])

    def test_retirement_rejects_missing_unresolved_or_preserved_replacements_without_mutation(self):
        source = brief()
        source["decisions"] = {
            "shape": {"status": "awaiting_choice", "blocks_modeling": True,
                      "selected_option": None, "source": "Fictional unresolved shape"},
            "other": {"status": "awaiting_choice", "blocks_modeling": False,
                      "selected_option": None, "source": "Fictional unknown material"},
        }
        original = deepcopy(source)
        for retirement in (
            {"shape": {"replaced_by": "missing", "source": "Explicit change"}},
            {"shape": {"replaced_by": "shape", "source": "Explicit change"}},
            {"shape": {"replaced_by": "other", "source": "Explicit change"}},
            {"missing": {"replaced_by": "other", "source": "Explicit change"}},
            {"shape": {"replaced_by": "other", "source": ""}},
        ):
            with self.subTest(retirement=retirement), self.assertRaises(ValueError):
                advance_revision(source, "bad", "Invalid retirement",
                                 brief_updates={"retire_decisions": retirement})
        patch = {"decisions": {"other": dict(source["decisions"]["other"], status="selected",
                                            selected_option="Chosen replacement")},
                 "retire_decisions": {"shape": {"replaced_by": "other", "source": "Explicit choice"}}}
        for preserve in (["decisions"], ["decisions.shape"]):
            with self.assertRaisesRegex(ValueError, "preserved"):
                advance_revision(source, "bad", "Preserved decision", brief_updates=patch, preserve=preserve)
        revised = advance_revision(source, "resolved", "Explicit replacement", brief_updates=patch)
        require_modeling_ready(revised)
        for defect in ("ancestor", "duplicate", "replacement", "cycle"):
            invalid = deepcopy(revised)
            entry = invalid["revision"]["superseded_decisions"][-1]
            if defect == "ancestor":
                entry["revision_id"] = "missing"
            elif defect == "duplicate":
                invalid["revision"]["superseded_decisions"].append(deepcopy(entry))
            elif defect == "replacement":
                entry["replaced_by"] = "missing"
            else:
                entry["replaced_by"] = "shape"
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                validate_brief(invalid)
        self.assertEqual(source, original)

    def test_decision_states_and_checked_brief_updates_preserve_approval_and_other_decisions(self):
        source = brief()
        source["decisions"] = {
            "shape": {"status": "selected", "blocks_modeling": True,
                      "selected_option": "flat", "source": "Fictional user selects flat"},
            "material": {"status": "awaiting_choice", "blocks_modeling": False,
                         "selected_option": None, "source": "Material unspecified; concept only"}}
        source["revision"]["user_approval"] = {
            "revision_id": "initial", "stage": "concept", "source": "Fictional old approval"}
        original = deepcopy(source)
        patch = {"decisions": {"shape": dict(source["decisions"]["shape"],
                                            status="delegated", selected_option="rounded",
                                            source="Fictional user: choose a rounded concept")},
                 "assumptions": ["Concept only"], "open_decisions": []}
        revised = advance_revision(source, "shape-02", "Record delegated selection", brief_updates=patch)
        require_modeling_ready(revised)
        self.assertEqual(source, original)
        self.assertEqual(revised["decisions"]["material"], source["decisions"]["material"])
        self.assertEqual(revised["revision"]["user_approval"], source["revision"]["user_approval"])
        self.assertEqual(revised["dimensions"], source["dimensions"])
        self.assertEqual(revised["revision"]["open_decisions"], [])
        for invalid in (
            {"revision": {"id": "forged"}}, {"stage": "fabrication-approved"},
            {"dimensions": {}}, {"user_approval": {}}, {"decisions": []},
            {"decisions": {"shape": dict(source["decisions"]["shape"], blocks_modeling=False)}},
            {"decisions": {"shape": dict(source["decisions"]["shape"], status="unknown")}},
            {"decisions": {"shape": dict(source["decisions"]["shape"], source="")}},
            {"decisions": {"shape": dict(source["decisions"]["shape"], blocks_modeling=1)}},
            {"decisions": {"shape": dict(source["decisions"]["shape"], selected_option=None)}},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                advance_revision(source, "bad", "Rejected semantic patch", brief_updates=invalid)
        with self.assertRaisesRegex(ValueError, "preserved decision"):
            advance_revision(source, "bad", "Preserved decision", brief_updates=patch,
                             preserve=["decisions.shape"])

    def test_blocking_decisions_prevent_preview_build_and_direct_publication(self):
        source = brief()
        source["decisions"] = {"shape": {
            "status": "awaiting_choice", "blocks_modeling": True,
            "selected_option": None, "source": "Fictional user has not selected a shape"}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output"
            fixture(brief()).export(output)
            old = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
            path = root / "design_brief.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            def must_not_build():
                self.fail("A known blocking decision reached the geometry builder")
            with self.assertRaisesRegex(ValueError, "Unresolved modeling"):
                export_preview(must_not_build, output, brief_path=path)
            with self.assertRaisesRegex(ValueError, "Unresolved modeling"):
                fixture(source).export(output)
            self.assertEqual(old, {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()})
            source["decisions"]["shape"]["blocks_modeling"] = False
            require_modeling_ready(source)
            source["decisions"]["shape"]["selected_option"] = "Already chosen"
            with self.assertRaisesRegex(ValueError, "cannot already select"):
                validate_brief(source)

    def test_corrected_fact_supersedes_only_that_input_and_does_not_inherit_approval(self):
        source = brief()
        source["revision"]["user_approval"] = {
            "revision_id": "initial", "stage": "concept", "source": "Explicit fictional fixture approval"}
        original = deepcopy(source)
        corrected = dict(source["dimensions"]["gap"], value=36, status="confirmed",
                         source="Fictional user correction")
        revised = advance_revision(source, "gap-correction", "Correct gap only",
                                   updates={"gap": corrected}, preserve=["dimensions.width"])
        self.assertEqual(source, original)
        self.assertEqual(revised["dimensions"]["gap"], corrected)
        for name in set(source["dimensions"])-{"gap"}:
            self.assertEqual(revised["dimensions"][name], source["dimensions"][name])
        self.assertEqual(revised["revision"]["superseded_facts"], [{
            "name": "gap", "revision_id": "initial", "fact": source["dimensions"]["gap"]}])
        self.assertEqual(revised["revision"]["user_approval"]["revision_id"], "initial")
        self.assertNotEqual(revised["revision"]["id"],
                            revised["revision"]["user_approval"]["revision_id"])
        self.assertEqual(revised["revision"]["dependencies"], source["revision"]["dependencies"])
        self.assertEqual(revised["revision"]["open_decisions"], source["revision"]["open_decisions"])
        resolved = advance_revision(revised, "decision-resolved", "Explicitly resolve fixture decision",
                                    open_decisions=[])
        self.assertEqual(resolved["revision"]["open_decisions"], [])
        self.assertEqual(revised["revision"]["open_decisions"], source["revision"]["open_decisions"])
        self.assertIsNone(advance_revision(brief(), "next", "Unapproved change")["revision"]["user_approval"])

    def test_preserved_facts_and_reused_ids_fail_without_mutating_the_brief(self):
        source = brief()
        original = deepcopy(source)
        with self.assertRaisesRegex(ValueError, "preserved"):
            advance_revision(source, "next", "Contradiction",
                             updates={"width": dict(source["dimensions"]["width"], value=140)},
                             preserve=["dimensions.width"])
        with self.assertRaisesRegex(ValueError, "reuse"):
            advance_revision(source, "initial", "Reuse initial")
        self.assertEqual(source, original)

    def test_invalid_lineage_fact_provenance_and_approval_fail_explicitly(self):
        cases = []
        source = brief()
        source["revision"]["parent_id"] = "missing"
        cases.append(source)
        source = brief()
        source["dimensions"]["width"]["value"] = True
        cases.append(source)
        source = brief()
        source["dimensions"]["width"]["value"] = float("nan")
        cases.append(source)
        source = brief()
        source["dimensions"]["width"].pop("source")
        cases.append(source)
        source = brief()
        source["revision"]["dependencies"]["missing_fact"] = ["parts.plate"]
        cases.append(source)
        source = brief()
        source["revision"]["user_approval"] = {
            "revision_id": "initial", "stage": "fabrication-approved", "source": "A build succeeded"}
        cases.append(source)
        for invalid in cases:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_brief(invalid)

    def test_snapshot_is_generated_isolated_tamper_evident_and_non_overwriting(self):
        source = brief()
        snapshot = make_snapshot(source)
        source["dimensions"]["width"]["value"] = 999
        self.assertEqual(snapshot["brief"]["dimensions"]["width"]["value"], 120)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "restored.json"
            restore_snapshot(snapshot, destination)
            self.assertEqual(make_snapshot(json.loads(destination.read_text())), snapshot)
            original = destination.read_bytes()
            with self.assertRaises(FileExistsError):
                restore_snapshot(snapshot, destination)
            self.assertEqual(destination.read_bytes(), original)
            snapshot["brief"]["dimensions"]["width"]["value"] = 888
            with self.assertRaisesRegex(ValueError, "identity/hash"):
                validate_snapshot(snapshot)

    def test_tracked_export_rejects_source_revision_mismatch_and_changed_artifact(self):
        source = brief()
        assembly = fixture(source)
        with tempfile.TemporaryDirectory() as directory:
            output = assembly.export(directory)
            report = check_exports(Context(assembly), output)
            self.assertEqual(report["revision"]["status"], "tracked")
            revised = advance_revision(source, "next", "New decision record")
            with self.assertRaisesRegex(ValueError, "Incompatible"):
                verify_export(make_snapshot(revised), output)
            stl = output / "parts" / "plate.stl"
            stl.write_bytes(stl.read_bytes()+b"\n")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                verify_export(assembly.revision, output)

    def test_same_id_cannot_publish_changed_brief_geometry_or_untracked_downgrade(self):
        source = brief()
        with tempfile.TemporaryDirectory() as directory:
            output = fixture(source).export(directory)
            original = (output / "manifest.json").read_bytes()
            revised = deepcopy(source)
            revised["dimensions"]["width"]["value"] = 140
            with self.assertRaisesRegex(ValueError, "id reused"):
                fixture(revised).export(output)
            changed_geometry = fixture(source)
            changed_geometry.parts["plate"] = Part(
                "plate", box(121, 10, 2), "Plate", "Illustrative", "#58b9c9")
            with self.assertRaisesRegex(ValueError, "Geometry changed"):
                changed_geometry.export(output)
            untracked = fixture(source)
            untracked.revision = None
            with self.assertRaisesRegex(ValueError, "untracked"):
                untracked.export(output)
            self.assertEqual((output / "manifest.json").read_bytes(), original)
            verify_export(make_snapshot(source), output)

    def test_forward_publication_invalidates_old_report_and_blocks_backwards_revision(self):
        source = brief()
        with tempfile.TemporaryDirectory() as directory:
            output = fixture(source).export(directory)
            validation = {"status": "geometry_passed_browser_not_run",
                          "revision": make_snapshot(source)["identity"],
                          "exports": {"manifest_sha256": sha256(output / "manifest.json")}}
            (output / "validation.json").write_text(json.dumps(validation))
            verify_export(make_snapshot(source), output, require_validation=True)
            revised = advance_revision(source, "next", "Correct width",
                                       updates={"width": dict(source["dimensions"]["width"], value=140)})
            fixture(revised).export(output)
            with self.assertRaisesRegex(ValueError, "failed or stale"):
                verify_export(make_snapshot(revised), output, require_validation=True)
            with self.assertRaisesRegex(ValueError, "newer or unrelated"):
                fixture(source).export(output)

    def test_untracked_legacy_brief_is_explicit_and_never_approved_implicitly(self):
        source = brief()
        source.pop("revision")
        self.assertIsNone(make_snapshot(source))
        with self.assertRaisesRegex(ValueError, "Adopt an initial"):
            advance_revision(source, "next", "Missing initial revision")
        with tempfile.TemporaryDirectory() as directory:
            assembly = fixture(source)
            output = assembly.export(directory)
            self.assertEqual(verify_export(None, output), {"status": "untracked"})
            with self.assertRaisesRegex(ValueError, "Tracked revision required"):
                verify_export(None, output, require_validation=True)

    @unittest.skipUnless(os.environ.get("CADKIT_VIEWER_ASSETS"), "Supply the optional trusted viewer runtime")
    def test_embedded_preview_binds_revision_and_hashes_all_companions(self):
        assembly = fixture(brief())
        with tempfile.TemporaryDirectory() as directory:
            _, output = export_preview(lambda: assembly, directory, viewer_backend="embedded",
                                       viewer_assets=os.environ["CADKIT_VIEWER_ASSETS"])
            marker = json.loads((output / "preview-ready.json").read_text())
            self.assertEqual(marker["revision"], assembly.revision["identity"])
            report = check_exports(Context(assembly), output)
            self.assertEqual(report["revision"]["status"], "tracked")
            self.assertEqual(report["viewer_backend"], "embedded")
            (output / "viewer-assets" / "engine.css").write_text("changed")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                verify_export(assembly.revision, output)

    def test_fresh_process_handoff_rebuilds_identical_geometry_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")

            def run(*arguments):
                result = subprocess.run([sys.executable, *map(str, arguments)], cwd=project,
                                        text=True, capture_output=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("RuntimeWarning", result.stderr)
                return result

            run("model.py", "--output", "before")
            run("-m", "cadkit.revision", "restore", Path("before") / "revision-state.json", "handoff.json")
            run("model.py", "--brief", "handoff.json", "--output", "after")
            before = json.loads((project / "before" / "manifest.json").read_text())
            after = json.loads((project / "after" / "manifest.json").read_text())
            self.assertEqual(before, after)
            for name in before["files_sha256"]:
                self.assertEqual((project / "before" / name).read_bytes(),
                                 (project / "after" / name).read_bytes(), name)
            run("validate.py", "--output", "after")
            run("-m", "cadkit.revision", "verify", "handoff.json", "after", "--validated")
            report = json.loads((project / "after" / "validation.json").read_text())
            self.assertEqual(report["revision"], after["revision"])
            self.assertIsNone(json.loads((project / "handoff.json").read_text())["revision"]["user_approval"])


if __name__ == "__main__":
    unittest.main()
