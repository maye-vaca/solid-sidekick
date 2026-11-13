from datetime import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "foundation"))
from cadkit import Assembly, Instance, Part
from cadkit.geometry import box
from cadkit.preview import export_preview, sha256, utc_now, wait_for_ack, write_json


def build():
    assembly = Assembly("Preview fixture", "+Z up; mm")
    assembly.add_part(Part("block", box(10, 10, 10), "Block", "Illustrative", "#58b9c9"))
    assembly.add_instance(Instance("block", "block"))
    return assembly


class PreviewTests(unittest.TestCase):
    def test_published_only_after_complete_export_and_invalidated_before_next_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, notification = root / "output", root / "host" / "preview-ready.json"
            environment = {"CADKIT_PREVIEW_FILE": str(notification), "CADKIT_PREVIEW_RUN_ID": "fresh"}
            with patch.dict(os.environ, environment):
                export_preview(build, output)
                marker = output / "preview-ready.json"
                data = json.loads(marker.read_text())
                self.assertEqual(data["stage"], "preview_unvalidated")
                self.assertEqual(data["viewer_sha256"], sha256(output / "viewer.html"))
                self.assertEqual(data["manifest_sha256"], sha256(output / "manifest.json"))
                self.assertEqual(data, json.loads(notification.read_text()))
                first_id = data["build_id"]
                export_preview(build, output)
                self.assertNotEqual(json.loads(marker.read_text())["build_id"], first_id)

                def invalid():
                    self.assertFalse(marker.exists())
                    self.assertFalse(notification.exists())
                    raise ValueError("Invalid design input")

                with self.assertRaisesRegex(ValueError, "Invalid design"):
                    export_preview(invalid, output)
                self.assertFalse(marker.exists())
                self.assertFalse(notification.exists())

    def test_failed_export_has_no_false_ready_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            with self.assertRaises(ValueError):
                export_preview(lambda: Assembly("Empty", "+Z up"), output)
            self.assertFalse((output / "preview-ready.json").exists())

    def test_host_gate_rejects_stale_ack_and_checks_order_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, ack = root / "output", root / "preview-opened.json"
            environment = {
                "CADKIT_PREVIEW_RUN_ID": "fresh", "CADKIT_PREVIEW_ACK_FILE": str(ack),
                "CADKIT_PREVIEW_TIMEOUT": ".1", "CADKIT_PREVIEW_FILE": str(root / "preview-ready.json"),
            }
            with patch.dict(os.environ, environment):
                export_preview(build, output)
                data = json.loads((output / "preview-ready.json").read_text())
                write_json(ack, {"run_id": "old", "build_id": data["build_id"], "opened_at": utc_now()})
                with self.assertRaisesRegex(ValueError, "did not acknowledge"):
                    wait_for_ack(output)
                opened = utc_now()
                write_json(ack, {"run_id": "fresh", "build_id": data["build_id"], "opened_at": opened})
                result = wait_for_ack(output)
                self.assertEqual(result["status"], "opened_unvalidated")
                self.assertLessEqual(datetime.fromisoformat(data["published_at"]), datetime.fromisoformat(opened))
                (output / "viewer.html").write_text("changed")
                with self.assertRaisesRegex(ValueError, "changed before"):
                    wait_for_ack(output)

    def test_plain_local_use_does_not_require_host(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(wait_for_ack(Path("unused"))["status"], "host_open_not_requested")

    def test_portable_copy_does_not_replace_main_preview_or_inherit_host_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, notification = root / "main", root / "host" / "preview-ready.json"
            environment = {
                "CADKIT_PREVIEW_OUTPUT": str(output), "CADKIT_PREVIEW_FILE": str(notification),
                "CADKIT_PREVIEW_ACK_FILE": str(root / "not-opened.json"),
            }
            with patch.dict(os.environ, environment):
                export_preview(build, output)
                original = notification.read_bytes()
                portable = root / "portable" / "output"
                export_preview(build, portable)
                self.assertEqual(notification.read_bytes(), original)
                self.assertTrue((portable / "preview-ready.json").is_file())
                self.assertEqual(wait_for_ack(portable)["status"], "host_open_not_requested")


if __name__ == "__main__":
    unittest.main()
