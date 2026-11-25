import base64
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import manifold3d as m
import trimesh

from cadkit import Assembly, Instance, Part, Placement
from cadkit.geometry import box, cylinder, internal_thread_tool, plate_with_holes
from cadkit.validation import Context, check_exports
from cadkit.viewer import load_components, viewer_data, write_mesh_viewer, write_viewer
from example import Dimensions, build


ROOT = Path(__file__).resolve().parents[1]


class FoundationTests(unittest.TestCase):
    def test_internal_thread_coarse_request_keeps_grooves_between_angular_samples(self):
        for major, pitch, clearance in ((20, .5, 0), (100, .25, 0), (9.525, 1.5875, .5)):
            with self.subTest(major=major, pitch=pitch, clearance=clearance):
                tool = internal_thread_tool(major, pitch, 1, radial_clearance=clearance,
                                            steps_per_turn=12)
                fine = internal_thread_tool(major, pitch, 1, radial_clearance=clearance,
                                            steps_per_turn=360)
                crest = (major - 1.08253 * pitch) / 2 + clearance
                depth = .541265 * pitch
                width = min(.001, pitch / 100)
                expected_volumes = []
                actual_volumes = []
                for angle in (0, 3.75, 7.5, 15, 22.5, 29.5):
                    probe = box(depth / 2, width, pitch).translate(
                        (crest + depth / 4, -width / 2, 0)).rotate((0, 0, angle))
                    actual_volumes.append((tool ^ probe).volume())
                    expected_volumes.append((fine ^ probe).volume())
                self.assertTrue(np.allclose(actual_volumes, expected_volumes, rtol=.08, atol=1e-10),
                                (actual_volumes, expected_volumes))
                bore = cylinder(crest - min(.02, depth / 10), 3).translate((0, 0, -1))
                ring = cylinder(major / 2 + clearance + 2, 1) - tool
                self.assertAlmostEqual((ring ^ bore).volume(), 0, delta=1e-6)
                assembly = Assembly("Adaptive thread", "+Z up; mm")
                assembly.add_part(Part("ring", ring, "Ring", "Concept", "#70c7d7"))
                assembly.add_instance(Instance("ring", "ring"))
                with tempfile.TemporaryDirectory() as directory:
                    check_exports(Context(assembly), assembly.export(directory))

    def test_nested_and_depth_staggered_tangent_cuts_remain_valid(self):
        large = cylinder(3, 10).translate((7, 7, -1))
        # A smaller same-depth circle inside the larger one is redundant, not invalid.
        small = cylinder(1, 10).translate((9, 7, -1))
        stock = box(14, 14, 8)
        shapes = (stock - large - small,
                  stock - cylinder(3, 4).translate((7, 7, 5))
                  - cylinder(1, 10).translate((9, 7, -1)))
        reference = stock - large
        self.assertAlmostEqual((shapes[0] - reference).volume() + (reference - shapes[0]).volume(),
                               0, delta=1e-6)
        for solid in shapes:
            with self.subTest(volume=solid.volume()), tempfile.TemporaryDirectory() as directory:
                assembly = Assembly("Tangent cut sections", "+Z up; mm")
                assembly.add_part(Part("block", solid, "Block", "Concept", "#70c7d7"))
                assembly.add_instance(Instance("block", "block"))
                check_exports(Context(assembly), assembly.export(directory))

    def test_internal_thread_clearance_variants_survive_default_export_reload(self):
        pitch, height, major = 25.4 / 16.0, 6.0, 9.525
        body = m.Manifold.cylinder(height, 12.0 / math.sqrt(3.0),
                                   circular_segments=6).rotate((0, 0, 30))
        previous_volume = None
        for clearance in (0.25, 0.35, 0.50, 0.55):
            with self.subTest(clearance=clearance), tempfile.TemporaryDirectory() as directory:
                tool = internal_thread_tool(major, pitch, height, radial_clearance=clearance)
                root = major / 2.0 + clearance
                chamfer = 0.3
                bottom = m.Manifold.cylinder(chamfer, root + chamfer, root, circular_segments=96)
                top = m.Manifold.cylinder(chamfer, root, root + chamfer, circular_segments=96)
                nut = body - tool - bottom - top.translate((0, 0, height - chamfer))
                self.assertEqual(nut.genus(), 1)
                self.assertEqual(len(nut.decompose()), 1)
                self.assertTrue(np.allclose(np.array(nut.bounding_box()).reshape(2, 3),
                                           [[-6, -12 / math.sqrt(3), 0],
                                            [6, 12 / math.sqrt(3), height]]))
                if previous_volume is not None:
                    self.assertLess(nut.volume(), previous_volume)
                previous_volume = nut.volume()
                assembly = Assembly("Thread fixture", "+Z thread axis; mm")
                assembly.add_part(Part("nut", nut, "Nut", "PLA", "#5a9e3a"))
                assembly.add_instance(Instance("nut", "nut"))
                output = assembly.export(directory)
                check_exports(Context(assembly), output)

    def test_internal_thread_pitch_and_through_bore(self):
        for pitch in (25.4 / 16.0, 25.4 / 18.0, 25.4 / 20.0):
            with self.subTest(pitch=pitch):
                tool = internal_thread_tool(9.525, pitch, 6, radial_clearance=0.25)
                nut = m.Manifold.cylinder(6, 7, circular_segments=96) - tool
                # Same angular section repeats at one pitch, not half a pitch.
                section = nut.slice(2.0)
                self.assertAlmostEqual((section - nut.slice(2.0 + pitch)).area(), 0, delta=1e-5)
                self.assertAlmostEqual((section.rotate(90) - nut.slice(2.0 + pitch / 4)).area(),
                                       0, delta=1e-5)
                self.assertGreater((section - nut.slice(2.0 + pitch / 2)).area(), 0.1)
                crest = (9.525 - 1.08253 * pitch) / 2 + 0.25
                probe = m.Manifold.cylinder(8, crest - 0.1, circular_segments=96).translate((0, 0, -1))
                self.assertAlmostEqual((nut ^ probe).volume(), 0, delta=1e-6)
                bolt = m.Manifold.cylinder(8, 9.25 / 2, circular_segments=96).translate((0, 0, -1))
                self.assertGreater((nut ^ bolt).volume(), 1)

    def test_internal_thread_rejects_invalid_inputs(self):
        cases = (
            {"major_diameter": 0}, {"pitch": -1}, {"height": float("inf")},
            {"major_diameter": 1, "pitch": 2}, {"radial_clearance": -0.1},
            {"radial_clearance": float("nan")}, {"radial_clearance": True},
            {"steps_per_turn": True}, {"steps_per_turn": 0}, {"steps_per_turn": 12.5},
        )
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                internal_thread_tool(**({"major_diameter": 9.525, "pitch": 1.5875,
                                         "height": 6} | changes))

    def test_example_has_reusable_local_geometry(self):
        assembly = build()
        local, placed = assembly.meshes()
        self.assertEqual(len(local), 2)
        self.assertEqual(len(placed), 6)
        self.assertTrue(np.allclose(placed["top"].bounds, [[0, 0, 36], [120, 80, 40]]))
        self.assertTrue(np.allclose(local["plate"].bounds, [[0, 0, 0], [120, 80, 4]]))
        expected = 120*80*4-4*np.pi*1.7**2*4
        self.assertAlmostEqual(local["plate"].volume, expected, delta=.2)
        self.assertAlmostEqual(assembly.interference_volume("base", "standoff_1"), 0)
        self.assertAlmostEqual(assembly.interference_volume("top", "standoff_1"), 0)

    def test_parameter_change_updates_every_surface(self):
        old, revised = build().meshes()[1], build(Dimensions(gap=50)).meshes()[1]
        self.assertTrue(np.allclose(revised["base"].bounds, old["base"].bounds))
        self.assertAlmostEqual(revised["top"].bounds[0, 2], 54)
        for index in range(1, 5):
            self.assertAlmostEqual(revised[f"standoff_{index}"].bounds[1, 2], 54)
            self.assertAlmostEqual(revised[f"standoff_{index}"].bounds[0, 2], 4)

    def test_units_and_euler_placement(self):
        part = Part("block", box(1, 2, 3), "Block", "Example", "#123456", units="in")
        assembly = Assembly("Units", "+X right, +Y back, +Z up")
        assembly.add_part(part)
        placement = Placement((1, 2, 3), (21, -37, 58), units="in")
        assembly.add_instance(Instance("world", "block", placement))
        local, placed = assembly.meshes()
        self.assertTrue(np.allclose(local["block"].extents, [25.4, 50.8, 76.2]))
        self.assertTrue(np.allclose(placement.translation, [25.4, 50.8, 76.2]))
        direct = part.solid.rotate(placement.rotation).translate(placement.translation)
        bounds = np.array(direct.bounding_box()).reshape(2, 3)
        self.assertTrue(np.allclose(placed["world"].bounds, bounds))
        self.assertEqual(part.units, "mm")
        assembly.add_instance(Instance("same", "block", placement))
        self.assertAlmostEqual(assembly.interference_volume("world", "same"),
                               part.solid.volume(), delta=.001)

    def test_rejects_bad_geometry_metadata_and_placements(self):
        for units in ("metres", "", None):
            with self.assertRaises(ValueError):
                Placement(units=units)
        with self.assertRaises(ValueError):
            Placement((float("nan"), 0, 0))
        with self.assertRaises(ValueError):
            Placement((1, 2))
        for ident, color in (("../escape", "#123456"), ("okay", "green")):
            with self.assertRaises(ValueError):
                Part(ident, box(1, 1, 1), "Part", "Material", color)
        with self.assertRaises(ValueError):
            Part("empty", box(1, 1, 1)-box(1, 1, 1), "Part", "Material", "#123456")
        with self.assertRaises(ValueError):
            box(-1, 2, 3)
        with self.assertRaises(ValueError):
            plate_with_holes(10, 10, 1, [(0, 5, 2)])
        with self.assertRaises(ValueError):
            build(Dimensions(gap=-1))
        with self.assertRaises(ValueError):
            build(Dimensions(inset=38))
        assembly = build()
        with self.assertRaises(ValueError):
            assembly.add_part(Part("PLATE", box(1, 1, 1), "x", "x", "#123456"))
        with self.assertRaises(ValueError):
            assembly.add_instance(Instance("BASE", "plate"))
        with self.assertRaises(ValueError):
            assembly.add_instance(Instance("unknown", "missing"))
        assembly.parameters["bad"] = float("nan")
        with self.assertRaises(ValueError):
            assembly.validate()

    def test_export_roundtrip_all_formats_and_metadata(self):
        assembly = build()
        local, placed = assembly.meshes()
        with tempfile.TemporaryDirectory() as directory:
            output = assembly.export(Path(directory) / "build")
            data = json.loads((output / "manifest.json").read_text())
            self.assertEqual((data["geometry_units"], data["stl_units"], data["glb_units"]),
                             ("mm", "mm", "m"))
            self.assertEqual(len(data["parts"]), 2)
            self.assertEqual(len(data["instances"]), 6)
            for entry in data["parts"]+data["instances"]:
                mesh = trimesh.load_mesh(output / entry["stl"])
                self.assertTrue(mesh.is_watertight)
                self.assertTrue(mesh.is_volume)
                self.assertTrue(np.allclose(mesh.bounds, entry["bounds_mm"]))
            scene = trimesh.load(output / "assembly.glb", force="scene")
            self.assertEqual(set(scene.graph.nodes_geometry), set(placed))
            self.assertEqual(len(scene.geometry), 2)
            for key, expected in placed.items():
                transform, geom = scene.graph[key]
                actual = scene.geometry[geom].copy()
                actual.apply_transform(transform)
                self.assertTrue(np.allclose(actual.bounds, expected.bounds*.001, atol=1e-8))
                part = assembly.parts[next(i.part_id for i in assembly.instances if i.id == key)]
                self.assertTrue(np.all(actual.visual.vertex_colors[:, :3] ==
                                       trimesh.visual.color.hex_to_rgba(part.color)[:3]))
            html = (output / "viewer.html").read_text()
            payload = html.split('<script id="model" type="application/json">')[1].split("</script>")[0]
            viewer = json.loads(payload)
            self.assertTrue(viewer["explicitMetadata"])
            self.assertEqual(viewer["units"], "mm")
            self.assertEqual(viewer["coordinateSystem"], assembly.coordinate_system)
            self.assertEqual(viewer["assumptions"], assembly.assumptions)
            top = next(item for item in viewer["parts"] if item["name"] == "top")
            self.assertEqual(top["material"], assembly.parts["plate"].material)
            self.assertEqual(top["color"], assembly.parts["plate"].color)
            self.assertNotIn("<script src=", html)
            self.assertNotIn("fetch(", html)
            keep = output / "user-file.txt"
            keep.write_text("Keep")
            build(Dimensions(gap=45)).export(output)
            self.assertEqual(keep.read_text(), "Keep")
            self.assertAlmostEqual(trimesh.load_mesh(output / "assembled" / "top.stl").bounds[0, 2], 49)

    def test_stl_folder_import_and_untrusted_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            with self.assertRaisesRegex(ValueError, "No STL"):
                load_components(folder)
            with self.assertRaises(ValueError):
                load_components(folder / "missing")
            mesh = trimesh.creation.box(extents=(2, 4, 6))
            mesh.export(folder / "one.STL", file_type="stl")
            mesh.export(folder / "two.stl", file_type="stl_ascii")
            paths = load_components(folder)
            self.assertEqual(len(paths), 2)
            path, count = write_viewer(folder, folder / "test.html", units="in")
            self.assertEqual(count, 2)
            self.assertIn('"units":"in"', path.read_text())
            evil = "</script><script>alert(1)</script>"
            path = write_mesh_viewer([(evil, mesh)], folder / "safe.html", title=evil)
            self.assertNotIn(evil, path.read_text())
            vertices = np.frombuffer(base64.b64decode(viewer_data(paths)["parts"][0]["vertices"]),
                                     dtype="<f4").reshape(-1, 6)
            self.assertTrue(np.isfinite(vertices).all())
            with self.assertRaises(ValueError):
                write_viewer(folder, folder / "bad.stl")
            with self.assertRaises(ValueError):
                write_viewer(folder, folder / "bad.html", units="invalid")
            with self.assertRaises(ValueError):
                viewer_data([])
            (folder / "broken.stl").write_text("not a mesh")
            with self.assertRaisesRegex(ValueError, "broken.stl"):
                load_components(folder)

    def test_cli_and_invalid_input(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(ROOT / "example.py"),
                                     "--gap", "42", "--output", directory],
                                    cwd=directory, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads((Path(directory) / "manifest.json").read_text())
            self.assertEqual(data["parameters"]["gap"], 42)
            bad = subprocess.run([sys.executable, str(ROOT / "example.py"), "--gap", "-2"],
                                 cwd=directory, text=True, capture_output=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("gap", bad.stderr)


if __name__ == "__main__":
    unittest.main()
