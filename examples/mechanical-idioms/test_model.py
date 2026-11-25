import copy
import tempfile
import unittest

from model import build, check_coupon, export
from cadkit import Part
from cadkit.geometry import box


class CouponTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = build()

    def test_all_fourteen_families_pass_independent_geometry_checks(self):
        self.assertEqual(len(self.cases), 14)
        for key, assembly in self.cases.items():
            with self.subTest(coupon=key):
                result = check_coupon(key, assembly)
                self.assertEqual(result["status"], "geometry_checks_passed")
                self.assertEqual(result["physical_acceptance"], "not_performed")

    def test_solid_filled_holes_and_missing_hook_do_not_pass_semantic_checks(self):
        for key, part, replacement in (
                ("02_holes", "hole_card", box(80, 22, 8)),
                ("07_snap_fit", "snap_envelope", box(6, 12, 5)),
                ("14_pattern", "vent_card", box(50, 30, 3))):
            with self.subTest(coupon=key):
                assembly = copy.copy(self.cases[key])
                assembly.parts = dict(assembly.parts)
                assembly.parts[part] = Part(part, replacement, "Broken specimen", "Concept", "#70c7d7")
                with self.assertRaises(ValueError):
                    check_coupon(key, assembly)

    def test_exported_parts_survive_default_reload_and_have_an_offline_catalog(self):
        from pathlib import Path
        import json

        with tempfile.TemporaryDirectory() as directory:
            result = export(directory)
            output = Path(directory)
            self.assertTrue((output / "gallery.html").is_file())
            self.assertIn('href="01_threads/viewer.html"', (output / "index.html").read_text())
            self.assertEqual(len(json.loads((output / "checks.json").read_text())["coupons"]), 14)
            for report in result["coupons"].values():
                self.assertGreater(report["exports"]["stls_reloaded"], 0)
                self.assertEqual(report["browser"]["status"], "not_run")


if __name__ == "__main__":
    unittest.main()
