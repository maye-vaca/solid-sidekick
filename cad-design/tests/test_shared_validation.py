import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "foundation"))
from cadkit import Assembly, Instance, Part, Placement, VisualRegion
from cadkit.assembly import solid_mesh
from cadkit.geometry import box, cylinder
from cadkit.validation import (
    Context, capture_evidence, check_exports, preflight_browser, publish_evidence,
)


def example():
    assembly = Assembly("Validation fixture", "+X right, +Y back, +Z up; mm",
                        assumptions=["Unrated fixture"], parameters={"width": 10})
    solid = box(10, 10, 2)-cylinder(1, 4).translate((3, 5, -1))
    assembly.add_part(Part("plate", solid, "Plate", "Illustrative", "#d9b079"))
    assembly.add_instance(Instance("base", "plate"))
    assembly.add_instance(Instance("top", "plate", Placement((0, 0, 12))))
    return assembly


class SharedValidationTests(unittest.TestCase):
    def test_glb_precision_failure_is_caught_before_serialization_or_output_replacement(self):
        shapes = (
            (box(125, 10, 10) - cylinder(1, 12).translate((60, 5, -1))).translate((125000000, 0, 0)),
            box(.00001, 10, 10).translate((1000, 0, 0)),
            (box(125, 125, 1) - box(124.96, 124.96, 3).translate((.02, .02, -1))
             ).translate((1000000, 1000000, 0)),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = example().export(root / "accepted")
            before = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
            for solid in shapes:
                for regions in ((), (VisualRegion("finish", "Finish", "#ffffff", (0,)),)):
                    assembly = Assembly("GLB precision probe", "+Z up; mm")
                    assembly.add_part(Part("part", solid, "Part", "Concept", "#70c7d7",
                                           visual_regions=regions))
                    assembly.add_instance(Instance("part", "part"))
                    for target in (output, root / "new"):
                        with self.subTest(regions=bool(regions), bounds=solid.bounding_box(), target=target):
                            with patch("trimesh.Scene.export") as serialize:
                                with self.assertRaisesRegex(ValueError, "GLB.*precision.*before serialization"):
                                    assembly.export(target)
                                serialize.assert_not_called()
                            self.assertFalse((root / "new").exists())
                            self.assertEqual(before, {p.relative_to(output): p.read_bytes()
                                                      for p in output.rglob("*") if p.is_file()})

    def test_glb_same_bounds_and_volume_cannot_hide_a_moved_hole(self):
        assembly = example()
        with tempfile.TemporaryDirectory() as directory:
            output = assembly.export(directory)
            scene = trimesh.load(output / "assembly.glb", force="scene")
            altered = solid_mesh(box(10, 10, 2) - cylinder(1, 4).translate((7, 5, -1)))
            altered.visual.vertex_colors = trimesh.visual.color.hex_to_rgba(assembly.parts["plate"].color)
            altered.apply_scale(.001)
            scene.geometry["plate"] = altered
            (output / "assembly.glb").write_bytes(scene.export(file_type="glb"))
            with self.assertRaisesRegex(ValueError, "GLB.*geometry"):
                check_exports(Context(assembly), output)

    def test_glb_serialized_geometry_is_checked_before_publication(self):
        assembly = example()
        original_export = trimesh.Scene.export

        def damaged_export(scene, *args, **kwargs):
            damaged = scene.copy()
            mesh = damaged.geometry["plate"]
            mesh.vertices[:, 2] = 0
            return original_export(damaged, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            output = assembly.export(directory)
            before = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
            with patch("trimesh.Scene.export", damaged_export):
                with self.assertRaisesRegex(ValueError, "GLB.*geometry"):
                    assembly.export(output)
            self.assertEqual(before, {p.relative_to(output): p.read_bytes()
                                      for p in output.rglob("*") if p.is_file()})

    def test_local_detail_with_large_placements_stays_reusable_and_valid(self):
        assembly = Assembly("Local precision", "+Z up; mm")
        solid = box(125, 125, 1) - box(124.96, 124.96, 3).translate((.02, .02, -1))
        assembly.add_part(Part("frame", solid, "Frame", "Concept", "#70c7d7"))
        for name, placement in (("near", Placement()), ("far", Placement((1000000, 1000000, 0),
                                                                       (0, 0, 35)))):
            assembly.add_instance(Instance(name, "frame", placement))
        with tempfile.TemporaryDirectory() as directory:
            output = assembly.export(directory)
            check_exports(Context(assembly), output)
            scene = trimesh.load(output / "assembly.glb", force="scene")
            self.assertEqual(len(scene.geometry), 1)
            mesh = scene.geometry["frame"]
            self.assertTrue(mesh.is_volume)
            self.assertGreater(mesh.volume, 0)
            self.assertTrue(np.allclose(scene.graph["far"][0][:3, 3], [1000, 1000, 0]))

    def test_roundtrip_gap_and_interference(self):
        assembly = example()
        context = Context(assembly)
        context.expect_bounds("base", [[0, 0, 0], [10, 10, 2]])
        self.assertAlmostEqual(context.expect_gap("base", "top", 10), 10)
        with self.assertRaisesRegex(ValueError, "gap"):
            context.expect_gap("base", "top", 9)
        self.assertEqual(context.check_interferences()["pairs"], 1)
        with tempfile.TemporaryDirectory() as directory:
            output = assembly.export(directory)
            report = check_exports(context, output)
            self.assertEqual(report["stls_reloaded"], 3)
            self.assertEqual(report["max_solid_difference_mm3"], 0)

    def test_same_bounds_and_volume_do_not_hide_wrong_hole(self):
        assembly = example()
        with tempfile.TemporaryDirectory() as directory:
            output = assembly.export(directory)
            altered = box(10, 10, 2)-cylinder(1, 4).translate((7, 5, -1))
            solid_mesh(altered).export(output / "parts" / "plate.stl", file_type="stl_ascii")
            with self.assertRaisesRegex(ValueError, "exported solid changed"):
                check_exports(Context(assembly), output)

    def test_invalid_stl_reports_reload_facts_without_relaxing_checks(self):
        assembly = example()
        with tempfile.TemporaryDirectory() as directory:
            output = assembly.export(directory)
            mesh = solid_mesh(assembly.parts["plate"].solid)
            mesh.update_faces(list(range(len(mesh.faces) - 1)))
            mesh.export(output / "parts" / "plate.stl", file_type="stl_ascii")
            with self.assertRaisesRegex(ValueError, r"invalid reloaded STL .*watertight=False"):
                check_exports(Context(assembly), output)

    def test_stale_metadata_and_paths_fail(self):
        assembly = example()
        with tempfile.TemporaryDirectory() as directory:
            output = assembly.export(directory)
            manifest_path = output / "manifest.json"
            original = manifest_path.read_text(encoding="utf-8")
            for key, value in (("parameters", {}), ("assumptions", []),
                               ("coordinate_system", "different")):
                data = json.loads(original)
                data[key] = value
                manifest_path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(ValueError):
                    check_exports(Context(assembly), output)
            data = json.loads(original)
            data["parts"][0]["stl"] = "../outside.stl"
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unexpected manifest STL path"):
                check_exports(Context(assembly), output)

    def test_overlap_requires_explicit_allowance(self):
        assembly = example()
        assembly.add_instance(Instance("overlap", "plate"))
        context = Context(assembly)
        with self.assertRaisesRegex(ValueError, "Unexpected interference"):
            context.check_interferences()
        result = context.check_interferences([("base", "overlap")])
        self.assertEqual(len(result["documented_overlaps"]), 1)

    def test_browser_preflight_rejects_missing_executable(self):
        with self.assertRaisesRegex(ValueError, "Browser executable not found"):
            preflight_browser(Path("definitely-not-a-browser-executable"))

    def test_browser_preflight_requires_playwright(self):
        with patch("cadkit.validation.importlib.util.find_spec", return_value=None):
            with self.assertRaisesRegex(ValueError, "Playwright is not installed"):
                preflight_browser(sys.executable)

    def test_browser_preflight_returns_resolved_executable(self):
        with patch("cadkit.validation.importlib.util.find_spec", return_value=object()):
            self.assertEqual(preflight_browser(sys.executable), Path(sys.executable).resolve())

    def test_browser_evidence_is_staged_before_publication(self):
        class Page:
            def screenshot(self, path):
                Path(path).write_bytes(b"png")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            temporary = capture_evidence(Page(), output)
            self.assertTrue(temporary.exists())
            self.assertFalse((output / "evidence" / "validated-preview.png").exists())
            publish_evidence(output, temporary)
            self.assertFalse(temporary.exists())
            self.assertEqual((output / "evidence" / "validated-preview.png").read_bytes(), b"png")

    def test_failed_browser_capture_removes_temporary_evidence(self):
        class Page:
            def screenshot(self, path):
                Path(path).write_bytes(b"partial")
                raise RuntimeError("render failed")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "render failed"):
                capture_evidence(Page(), output)
            self.assertFalse((output / "evidence" / "validated-preview.png").exists())
            self.assertEqual(list(output.glob(".validated-preview-*")), [])


if __name__ == "__main__":
    unittest.main()
