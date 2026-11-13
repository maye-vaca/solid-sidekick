import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import trimesh

from cadkit import Assembly, Instance, Part, Placement
from cadkit.geometry import box, plate_with_holes
from cadkit.viewer import load_components, viewer_data, write_mesh_viewer, write_viewer
from example import Dimensions, build


ROOT = Path(__file__).resolve().parents[1]


class FoundationTests(unittest.TestCase):
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
