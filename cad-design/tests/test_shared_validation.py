import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "foundation"))
from cadkit import Assembly, Instance, Part, Placement
from cadkit.assembly import solid_mesh
from cadkit.geometry import box, cylinder
from cadkit.validation import Context, check_exports


def example():
    assembly = Assembly("Validation fixture", "+X right, +Y back, +Z up; mm",
                        assumptions=["Unrated fixture"], parameters={"width": 10})
    solid = box(10, 10, 2)-cylinder(1, 4).translate((3, 5, -1))
    assembly.add_part(Part("plate", solid, "Plate", "Illustrative", "#d9b079"))
    assembly.add_instance(Instance("base", "plate"))
    assembly.add_instance(Instance("top", "plate", Placement((0, 0, 12))))
    return assembly


class SharedValidationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
