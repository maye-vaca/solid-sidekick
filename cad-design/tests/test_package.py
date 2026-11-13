import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import new_project


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PackageTests(unittest.TestCase):
    def run_cli(self, arguments, cwd):
        return subprocess.run(
            [sys.executable, *map(str, arguments)], cwd=cwd,
            text=True, capture_output=True, timeout=120,
        )

    def test_skill_metadata_links_and_portable_paths(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        frontmatter = text.split("---", 2)[1]
        self.assertRegex(frontmatter, r"(?m)^name: cad-design$")
        self.assertRegex(frontmatter, r"(?m)^description: .{40,}$")
        self.assertEqual(ROOT.name, "cad-design")
        self.assertLess(len(text.splitlines()), 180)
        for path in ROOT.rglob("*.md"):
            content = path.read_text(encoding="utf-8")
            for link in re.findall(r"\[[^]]+\]\(([^)]+)\)", content):
                if "://" not in link and not link.startswith("#"):
                    self.assertTrue((path.parent / link.split("#")[0]).is_file(), (path, link))
        for path in ROOT.rglob("*"):
            if path.suffix in (".py", ".md", ".json", ".txt") and "__pycache__" not in path.parts:
                content = path.read_text(encoding="utf-8")
                self.assertNotRegex(content, r"[A-Za-z]:[\\/]Users[\\/][^\\/\s]")
                self.assertNotIn(str(ROOT.parent), content, str(path))

    def test_unchanged_toolkit_files_match_foundation_when_available(self):
        original = ROOT.parent / "cad_foundation"
        if not original.is_dir():
            self.skipTest("Original milestone-1 source not present in portable package")
        bundled = ROOT / "scripts" / "foundation"
        for relative in (
            Path("cadkit") / "geometry.py",
            Path("requirements.txt"), Path("README.md"), Path("example.py"),
            Path("tests") / "test_foundation.py", Path("tests") / "test_browser.py",
        ):
            self.assertEqual(digest(original / relative), digest(bundled / relative), str(relative))

    def test_lightweight_viewer_preserves_original_model_data(self):
        original = ROOT.parent / "cad_foundation"
        if not original.is_dir():
            self.skipTest("Original milestone-1 source not present in portable package")
        sys.path.insert(0, str(ROOT / "scripts" / "foundation"))
        from example import build
        from cadkit.viewer import write_mesh_viewer

        legacy = runpy.run_path(str(original / "cadkit" / "viewer.py"))
        assembly = build()
        components = list(assembly.meshes()[1].items())
        metadata = {}
        for instance in assembly.instances:
            part = assembly.parts[instance.part_id]
            metadata[instance.id] = {"color": part.color, "material": part.material,
                                     "notes": f"{part.name}. {part.notes}".strip()}
        with tempfile.TemporaryDirectory() as directory:
            before, after = Path(directory) / "before.html", Path(directory) / "after.html"
            options = {"title": assembly.name, "units": "mm", "metadata": metadata,
                       "coordinate_system": assembly.coordinate_system, "assumptions": assembly.assumptions}
            legacy["write_mesh_viewer"](components, before, **options)
            write_mesh_viewer(components, after, **options)
            def model(path):
                payload = re.search(r'<script id="model" type="application/json">(.*?)</script>',
                                    path.read_text(encoding="utf-8"), re.S)[1]
                return json.loads(payload)
            self.assertEqual(model(before), model(after))

    @unittest.skipUnless(os.environ.get("CADKIT_BROWSER"), "Set CADKIT_BROWSER for viewer interaction checks")
    def test_long_assumptions_are_collapsed_accessible_and_do_not_hide_geometry(self):
        from playwright.sync_api import sync_playwright
        import trimesh
        sys.path.insert(0, str(ROOT / "scripts" / "foundation"))
        from cadkit.viewer import write_mesh_viewer

        notes = ["Long provenance and limitations " * 30,
                 "</p><script>throw Error('notes are text')</script>", "X" * 400]
        with tempfile.TemporaryDirectory() as directory, sync_playwright() as pw:
            path = write_mesh_viewer([("part", trimesh.creation.box())],
                                     Path(directory) / "viewer.html", assumptions=notes)
            empty = write_mesh_viewer([("part", trimesh.creation.box())],
                                      Path(directory) / "empty.html")
            browser = pw.chromium.launch(executable_path=os.environ["CADKIT_BROWSER"], headless=True,
                                        args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            try:
                for width in (1280, 375):
                    with self.subTest(width=width):
                        page = browser.new_page(viewport={"width": width, "height": 800})
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        page.goto(path.as_uri())
                        page.wait_for_function("document.getElementById('status').textContent.startsWith('1 / 1')")
                        self.assertFalse(page.locator("#assumptions-section").evaluate("e=>e.open"))
                        self.assertTrue(page.locator("#assumptions").is_hidden())
                        self.assertLess(page.locator("canvas").bounding_box()["y"], 400)
                        summary = page.locator("summary")
                        summary.focus()
                        page.keyboard.press("Enter")
                        self.assertTrue(page.locator("#assumptions").is_visible())
                        self.assertEqual(page.locator("#assumptions").text_content(), " | ".join(notes))
                        self.assertIn("Collapse", summary.inner_text())
                        self.assertTrue(page.evaluate(
                            "document.documentElement.scrollWidth<=innerWidth"))
                        page.keyboard.press("Space")
                        self.assertFalse(page.locator("#assumptions-section").evaluate("e=>e.open"))
                        self.assertLess(page.locator("canvas").bounding_box()["y"], 400)
                        page.goto(empty.as_uri())
                        page.wait_for_function("document.getElementById('status').textContent.startsWith('1 / 1')")
                        self.assertTrue(page.locator("#assumptions-section").is_hidden())
                        self.assertIn("physical fit", page.locator("header").inner_text())
                        self.assertFalse(errors, errors)
                        page.close()
            finally:
                browser.close()

    def test_existing_destinations_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("empty", "occupied"):
                destination = root / name
                destination.mkdir()
                if name == "occupied":
                    (destination / "model.py").write_text("user work", encoding="utf-8")
                before = {p.relative_to(destination): digest(p)
                          for p in destination.rglob("*") if p.is_file()}
                result = self.run_cli([ROOT / "scripts" / "new_project.py", destination], root)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("already exists", result.stderr)
                after = {p.relative_to(destination): digest(p)
                         for p in destination.rglob("*") if p.is_file()}
                self.assertEqual(before, after)
            file_target = root / "existing-file"
            file_target.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "already exists"):
                new_project.create_project(file_target)
            self.assertEqual(file_target.read_text(encoding="utf-8"), "keep")

    def test_missing_resources_fail_before_project_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "new project"
            with patch.object(new_project, "SKILL_ROOT", root):
                with self.assertRaisesRegex(FileNotFoundError, "incomplete"):
                    new_project.create_project(target)
            self.assertFalse(target.exists())

    def test_new_project_builds_and_checks_from_another_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "nested path" / "new project"
            result = self.run_cli([ROOT / "scripts" / "new_project.py", project], root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("No packages installed", result.stdout)
            self.assertFalse((project / "output").exists())
            expected = {
                "README.md", "requirements.txt", "model.py", "design_brief.json", "test_model.py",
                "cadkit/__init__.py", "cadkit/assembly.py", "cadkit/geometry.py", "cadkit/viewer.py",
                "cadkit/validation.py", "cadkit/preview.py", "checks.py", "validate.py",
                "cadkit/scene.py", "cadkit/embedded.py",
                "cadkit/revision.py", "cadkit/timing.py", "cadkit/review.py",
                "cadkit/regions.py", "cadkit/incremental.py",
                "cadkit/drawing.py", "cadkit/checkpoint.py", "drawing-settings.json",
                "cadkit/construction.py",
            }
            self.assertEqual(
                {p.relative_to(project).as_posix() for p in project.rglob("*") if p.is_file()},
                expected,
            )
            result = self.run_cli([project / "model.py"], root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((root / "output").exists())
            output = project / "output"
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["parts"]), 2)
            self.assertEqual(len(manifest["instances"]), 6)
            result = self.run_cli(["-m", "unittest", "-v"], project)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Ran 3 tests", result.stderr)
            result = self.run_cli([project / "validate.py"], root)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((output / "validation.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "passed" if os.environ.get("CADKIT_BROWSER") else
                             "geometry_passed_browser_not_run")
            self.assertEqual(report["exports"]["stls_reloaded"], 8)
            missing = root / "missing exports"
            failed = self.run_cli([project / "validate.py", "--output", missing], root)
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(json.loads((missing / "validation.json").read_text())["status"], "failed")
            result = self.run_cli(
                ["-m", "cadkit.viewer", output / "assembled", "--units", "mm", "--no-open"],
                project,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("RuntimeWarning", result.stderr)
            bad = root / "bad.json"
            bad.write_text('{"schema_version": 1}', encoding="utf-8")
            invalid_output = root / "invalid-output"
            result = self.run_cli(
                [project / "model.py", "--brief", bad, "--output", invalid_output], root,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Brief name", result.stderr)
            self.assertFalse(invalid_output.exists())

    @unittest.skipUnless(os.environ.get("CADKIT_BROWSER"),
                         "Set CADKIT_BROWSER and install playwright for browser checks")
    def test_generated_project_offline_viewer(self):
        from playwright.sync_api import sync_playwright

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = new_project.create_project(root / "viewer project")
            result = self.run_cli([project / "model.py"], root)
            self.assertEqual(result.returncode, 0, result.stderr)
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    executable_path=os.environ["CADKIT_BROWSER"], headless=True,
                    args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
                )
                page = browser.new_page(viewport={"width": 1400, "height": 1000})
                errors, remote = [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda request: remote.append(request.url)
                        if request.url.startswith(("http://", "https://")) else None)
                page.goto((project / "output" / "viewer.html").as_uri(), wait_until="load")
                page.wait_for_function(
                    "document.getElementById('status').textContent.startsWith('6 / 6')"
                )
                self.assertEqual(page.locator("#components .part").count(), 6)
                self.assertIn("gap: 32 mm (assumed;", page.locator("#assumptions").text_content())
                self.assertIn("+Z up", page.locator("#conventions").inner_text())
                self.assertTrue(page.locator("#error").is_hidden())
                pixels = page.evaluate("""()=>{
                    draw();
                    const bytes=new Uint8Array(canvas.width*canvas.height*4);
                    gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,bytes);
                    let colored=0;
                    for(let i=0;i<bytes.length;i+=4){
                        if(Math.max(bytes[i],bytes[i+1],bytes[i+2])-
                           Math.min(bytes[i],bytes[i+1],bytes[i+2])>45)colored++;
                    }
                    return colored;
                }""")
                self.assertGreater(pixels, 1000)
                page.locator("#search").fill("standoff_2")
                self.assertEqual(page.locator("#components .part:visible").count(), 1)
                page.locator("#components .part:visible button").click()
                self.assertIn("nominal bore", page.locator("#selected").inner_text())
                page.locator("#isolate").click()
                self.assertTrue(page.locator("#status").inner_text().startswith("1 / 6"))
                self.assertEqual(page.evaluate("gl.getError()"), 0)
                self.assertFalse(errors, errors)
                self.assertFalse(remote, remote)
                browser.close()


if __name__ == "__main__":
    unittest.main()
