from copy import deepcopy
import csv
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from test_revision import ROOT, brief
import new_project
from cadkit.checkpoint import render, write
from cadkit.drawing import format_length, generate, validate_settings, verify
from cadkit.revision import advance_revision, require_modeling_ready


def proposal():
    material = [[10, 10], [90, 10], [90, 60], [10, 60]]
    return {"schema_version": 1, "question": "Which profile is closer?", "view": "Front / X right, Z up",
            "bounds_mm": [[0, 0], [100, 80]], "fixed": ["80 mm overall width; lower endpoints unchanged"],
            "options": [
                {"id": "A", "title": "Straight band", "material": [material], "voids": [],
                 "labels": [{"at": [10, 70], "text": "80 mm width; fixed lower edge"}]},
                {"id": "B", "title": "Open band", "material": [material],
                 "voids": [[[20, 20], [80, 20], [80, 50], [20, 50]]],
                 "labels": [{"at": [10, 70], "text": "Same 80 mm width; central void"}]},
            ]}


class CheckpointTests(unittest.TestCase):
    def test_four_options_require_unique_ordered_labels_and_picture_every_choice(self):
        data = proposal()
        for identifier in ("C", "D"):
            option = deepcopy(data["options"][0])
            option.update(id=identifier, title=f"Distinct alternative {identifier}")
            data["options"].append(option)
        content = render(data)
        self.assertEqual(content.count("<section>"), 4)
        self.assertEqual(content.count('viewBox="0 -80 100 80"'), 4)
        self.assertIn("Fixed in all alternatives", content)
        self.assertIn("Choose A, B, C or D", content)
        for labels in (("A", "B", "A", "B"), ("A", "B", "D", "C")):
            bad = deepcopy(data)
            for option, identifier in zip(bad["options"], labels):
                option["id"] = identifier
            with self.assertRaisesRegex(ValueError, "labeled"):
                render(bad)
        data["options"].pop()
        with self.assertRaisesRegex(ValueError, "two or four"):
            render(data)

    @unittest.skipUnless(os.environ.get("CADKIT_BROWSER"), "Checkpoint layout requires actual Chromium/Edge")
    def test_long_headings_wrap_and_paired_drawings_align_at_desktop_and_mobile_widths(self):
        from playwright.sync_api import sync_playwright

        with tempfile.TemporaryDirectory() as directory, sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=os.environ["CADKIT_BROWSER"], headless=True)
            try:
                page = browser.new_page()
                for count in (2, 4):
                    data = proposal()
                    if count == 4:
                        for identifier in ("C", "D"):
                            option = deepcopy(data["options"][0])
                            option.update(id=identifier, title=f"Alternative {identifier}")
                            data["options"].append(option)
                    data["options"][0]["title"] = "Long descriptive mechanical interpretation with retained endpoints " * 8
                    data["options"][1]["title"] = "Short title"
                    path = Path(directory) / f"checkpoint-{count}.html"
                    path.write_text(render(data), encoding="utf-8")
                    for width in (1280, 375):
                        with self.subTest(count=count, width=width):
                            page.set_viewport_size({"width": width, "height": 900})
                            page.goto(path.as_uri())
                            boxes = page.locator("section").evaluate_all("""nodes=>nodes.map(node=>{
                                const heading=node.querySelector('h2'),svg=node.querySelector('svg');
                                const h=heading.getBoundingClientRect(),s=svg.getBoundingClientRect();
                                return {hBottom:h.bottom,sTop:s.top,sBottom:s.bottom,w:s.width,height:s.height,
                                        headingFits:heading.scrollHeight<=heading.clientHeight+1};
                            })""")
                            self.assertEqual(len(boxes), count)
                            for box in boxes:
                                self.assertTrue(box["headingFits"])
                                self.assertGreaterEqual(box["sTop"]+.1, box["hBottom"])
                                self.assertAlmostEqual(box["w"]/box["height"], 1.25, delta=.01)
                            if width == 1280:
                                for index in range(0, count, 2):
                                    self.assertAlmostEqual(boxes[index]["sTop"], boxes[index+1]["sTop"], delta=.1)
                                    self.assertAlmostEqual(boxes[index]["w"], boxes[index+1]["w"], delta=.1)
                            else:
                                for before, after in zip(boxes, boxes[1:]):
                                    self.assertGreater(after["sTop"], before["sBottom"])
                            self.assertTrue(page.evaluate("document.documentElement.scrollWidth<=innerWidth"))
            finally:
                browser.close()

    def test_deliverable_gate_selected_sequence_and_legacy_compatibility(self):
        source = brief()
        source.pop("deliverable", None)
        require_modeling_ready(source)
        source["deliverable"] = {"status": "awaiting_choice", "target": None, "outputs": [],
                                 "sequence": [], "source": "User has not chosen reference versus case"}
        with self.assertRaisesRegex(ValueError, "Unresolved immediate deliverable"):
            require_modeling_ready(source)
        selected = {"status": "selected", "target": "Storage case, not only the reference",
                    "outputs": ["Offline review", "STL/GLB"], "sequence": [
                        "Build estimated headphone reference as a dependency", "Deliver the case"],
                    "source": "Fictional user explicitly requests the case"}
        updated = advance_revision(source, "case-selected", "Select immediate deliverable",
                                   brief_updates={"deliverable": selected})
        require_modeling_ready(updated)
        self.assertEqual(updated["deliverable"], selected)
        self.assertIsNone(updated["revision"]["user_approval"])
        self.assertEqual(source["deliverable"]["status"], "awaiting_choice")
        with self.assertRaisesRegex(ValueError, "preserved"):
            advance_revision(source, "preserved", "Change preserved scope",
                             brief_updates={"deliverable": selected}, preserve=["deliverable"])

    def test_comparable_sketches_do_not_touch_accepted_source_and_escape_text(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")
            accepted = (project / "design_brief.json").read_bytes()
            path = project / "exploration" / "choice.json"
            path.parent.mkdir()
            data = proposal()
            data["options"][0]["title"] = "<script>alert(1)</script>"
            path.write_text(json.dumps(data), encoding="utf-8")
            page = write(project, path)
            content = page.read_text(encoding="utf-8")
            self.assertEqual(content.count('viewBox="0 -80 100 80"'), 2)
            self.assertIn("&lt;script&gt;", content)
            self.assertNotIn("<script>", content)
            self.assertIn("central void", content)
            self.assertEqual((project / "design_brief.json").read_bytes(), accepted)
            self.assertFalse((project / "output").exists())
            with self.assertRaises(FileExistsError):
                write(project, path)
            with self.assertRaisesRegex(ValueError, "exploration"):
                write(project, path, project / "output" / "review.html")
            bad = proposal()
            bad["options"][1]["material"][0][0] = [-10, 10]
            with self.assertRaisesRegex(ValueError, "common bounds"):
                render(bad)


class DrawingTests(unittest.TestCase):
    def cli(self, project, *args):
        env = dict(os.environ)
        env.pop("CADKIT_BROWSER", None)
        result = subprocess.run([sys.executable, "-m", "cadkit.incremental", *args],
                                cwd=project, env=env, text=True, capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        return result

    def test_portable_regeneration_sections_dimensions_schedule_and_stale_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = new_project.create_project(root / "original")
            self.cli(original, "qualify")
            settings_path = original / "drawing-settings.json"
            settings = json.loads(settings_path.read_bytes())
            settings.update(units="in", fraction_denominator=64, scale_denominator=4)
            settings_path.write_text(json.dumps(settings), encoding="utf-8")
            output = generate(original)
            report = json.loads((output / "drawing-state.json").read_bytes())
            self.assertEqual(report["sheet_mm"], [420, 297])
            self.assertEqual(report["settings"], settings)
            section = next(view for view in report["views"] if view["id"] == "section")
            self.assertEqual(section["extents_mm"], [120, 40])
            self.assertEqual(section["paper_extents_mm"], [30, 10])
            self.assertAlmostEqual(sum(section["areas_mm2"].values()), 960, places=4)
            self.assertIn("standoff_1", section["uncut_instances"])
            with (output / "schedule.csv").open(encoding="utf-8") as file:
                schedule = list(csv.DictReader(file))
            self.assertEqual({row["part_id"]: row["quantity"] for row in schedule},
                             {"plate": "2", "standoff": "4"})
            svg = (output / "sheet-01.svg").read_bytes()
            self.assertIn(b'4 23/32&quot;', svg)
            self.assertIn(b"Scale 1:4", svg)
            self.assertNotIn(str(original).encode(), svg)
            verify(original, output)
            with self.assertRaisesRegex(ValueError, "destination exists"):
                generate(original)
            copied = root / "relocated"
            shutil.copytree(original, copied)
            regenerated = generate(copied, output=copied / "regenerated")
            self.assertEqual((regenerated / "sheet-01.svg").read_bytes(), svg)
            self.assertEqual((regenerated / "schedule.csv").read_bytes(), (output / "schedule.csv").read_bytes())
            self.assertEqual(json.loads((regenerated / "drawing-state.json").read_bytes()), report)
            # Rendering reads checked exports, not a session-local builder or renderer.
            self.cli(copied, "verify")
            saved = settings_path.read_bytes()
            settings["scale_denominator"] = 8
            settings_path.write_text(json.dumps(settings), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "settings are stale"):
                verify(original, output)
            settings_path.write_bytes(saved)
            (output / "sheet-01.svg").write_bytes(svg+b" ")
            with self.assertRaisesRegex(ValueError, "artifacts"):
                verify(original, output)

    def test_bad_scale_empty_cut_and_changed_geometry_fail_without_publishing(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")
            self.cli(project, "qualify")
            path = project / "drawing-settings.json"
            settings = json.loads(path.read_bytes())
            settings.update(scale_denominator=1)
            settings["sheet"].update(size="A4", columns=4, rows=4)
            path.write_text(json.dumps(settings), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not fit"):
                generate(project, output=project / "bad-scale")
            self.assertFalse((project / "bad-scale").exists())
            settings = json.loads((ROOT / "templates" / "drawing-settings.json").read_bytes())
            settings["views"] = [{"id": "empty", "title": "Invalid cut", "kind": "section",
                                  "axis": "y", "offset_mm": 999}]
            path.write_text(json.dumps(settings), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no geometry"):
                generate(project, output=project / "empty")
            self.assertFalse((project / "empty").exists())
            stl = project / "output" / "assembled" / "base.stl"
            stl.write_bytes(stl.read_bytes()+b"\n")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                generate(project, output=project / "changed")
            self.assertFalse((project / "changed").exists())

    def test_fraction_labels_do_not_quantize_geometry_and_settings_reject_typos(self):
        settings = json.loads((ROOT / "templates" / "drawing-settings.json").read_bytes())
        settings["units"] = "in"
        self.assertEqual(format_length(241.3, settings), '9 1/2"')
        self.assertEqual(format_length(-25.4/128, settings), '-1/64"')
        self.assertEqual(format_length(25.4/128, settings), '1/64"')
        settings["units"] = "mm"
        self.assertEqual(format_length(25.4123, settings), "25.41 mm")
        for key, value in (("scale_denominator", 0), ("fraction_denominator", True),
                           ("decimal_places", -1), ("units", "cm"), ("unknown", 1)):
            bad = deepcopy(settings)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_settings(bad)

    @unittest.skipUnless(os.environ.get("CADKIT_BROWSER"), "PDF requires approved Chromium/Edge and Playwright")
    def test_pdf_preserves_physical_sheet_and_svg_scale(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")
            self.cli(project, "qualify")
            output = generate(project, browser=os.environ["CADKIT_BROWSER"])
            pdf = (output / "sheets.pdf").read_bytes()
            box = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", pdf)
            self.assertIsNotNone(box)
            self.assertAlmostEqual(float(box[1])*25.4/72, 420, delta=25.4/96)
            self.assertAlmostEqual(float(box[2])*25.4/72, 297, delta=25.4/96)
            self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", pdf)),
                             len(list(output.glob("sheet-*.svg"))))
            svg = ET.fromstring((output / "sheet-01.svg").read_bytes())
            self.assertEqual(svg.attrib["width"], "420mm")
            self.assertEqual(svg.attrib["height"], "297mm")
            verify(project, output)
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path=os.environ["CADKIT_BROWSER"], headless=True,
                                            args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
                try:
                    page = browser.new_page()
                    page.goto((project / "output" / "review.html").as_uri())
                    page.wait_for_function("cadReview.getState().revision")
                    target = json.loads((project / "design_brief.json").read_bytes())["deliverable"]["target"]
                    self.assertIn(target, page.locator("#deliverable").inner_text())
                    page.goto((output / "sheets.html").as_uri())
                    geometry = page.locator('svg').first.locator('path[data-instance="base"]').first
                    width = geometry.evaluate("""node=>{
                        const bounds=node.getBBox(),matrix=node.getScreenCTM();
                        return bounds.width*Math.hypot(matrix.a,matrix.b)*25.4/96;
                    }""")
                    self.assertAlmostEqual(width, 60, delta=.01)
                finally:
                    browser.close()

    @unittest.skipUnless(os.environ.get("CADKIT_BROWSER"), "Review refresh requires actual Chromium/Edge")
    def test_new_deliverable_stays_pending_until_user_apply_boundary(self):
        from playwright.sync_api import sync_playwright

        with tempfile.TemporaryDirectory() as directory, sync_playwright() as pw:
            project = new_project.create_project(Path(directory) / "project")
            self.cli(project, "qualify")
            browser = pw.chromium.launch(executable_path=os.environ["CADKIT_BROWSER"], headless=True,
                                        args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            try:
                page = browser.new_page()
                page.goto((project / "output" / "review.html").as_uri())
                page.wait_for_function("cadReview.getState().view")
                initial = page.locator("#deliverable").inner_text()
                patch = project / "selected-deliverable.json"
                patch.write_text(json.dumps({"deliverable": {
                    "status": "selected", "target": "Riser concept drawing package",
                    "outputs": ["Offline review", "SVG/HTML sheets"],
                    "sequence": ["Review geometry", "Produce concept sheets"],
                    "source": "Fictional explicit scope selection",
                }}), encoding="utf-8")
                self.cli(project, "revise", "--tier", "topology", "--revision", "drawing-scope",
                         "--delta", "Select requested drawing deliverable", "--brief-updates", patch,
                         "--browser", os.environ["CADKIT_BROWSER"])
                handoff = json.loads(self.cli(project, "verify", "--include-packet").stdout)
                page.evaluate("data=>cadReview.loadHandoff(data)", handoff)
                self.assertEqual(page.locator("#deliverable").inner_text(), initial)
                self.assertEqual(page.evaluate("cadReview.getState().revision.id"), "initial")
                page.locator("#apply").click()
                self.assertIn("Riser concept drawing package", page.locator("#deliverable").inner_text())
                self.assertEqual(page.evaluate("cadReview.getState().revision.id"), "drawing-scope")
                sketch = project / "exploration" / "choice.json"
                sketch.parent.mkdir()
                sketch.write_text(json.dumps(proposal()), encoding="utf-8")
                page.goto(write(project, sketch).as_uri())
                sizes = page.locator("svg").evaluate_all(
                    "nodes=>nodes.map(n=>({w:n.getBoundingClientRect().width,h:n.getBoundingClientRect().height}))")
                self.assertEqual(sizes[0], sizes[1])
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
