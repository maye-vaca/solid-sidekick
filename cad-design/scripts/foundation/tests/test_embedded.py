import base64
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import shutil

import numpy as np
import trimesh

from cadkit.embedded import read_assets
from cadkit.preview import export_preview, sha256, utc_now, wait_for_ack, write_json
from cadkit.scene import scene_data
from cadkit.validation import Context, check_browser, check_exports
from cadkit.viewer import viewer_data
from example import build


ASSETS = os.environ.get("CADKIT_VIEWER_ASSETS")


class SceneTests(unittest.TestCase):
    def test_lightweight_retains_raw_mesh_degenerate_face_tolerance(self):
        box = trimesh.creation.box()
        mesh = trimesh.Trimesh(vertices=box.vertices, faces=np.vstack([box.faces, [0, 0, 0]]), process=False)
        components = [("raw", mesh)]
        self.assertEqual(viewer_data(components)["parts"][0]["triangles"], 13)
        with self.assertRaisesRegex(ValueError, "nondegenerate"):
            scene_data(components, title="Raw import", coordinate_system="mm; +Z up")

    def test_shared_bytes_and_large_offset_precision(self):
        mesh = trimesh.creation.box(extents=[.125, .0625, .03125])
        mesh.apply_translation([1e9, -2e9, 3e9])
        components = [("box", mesh)]
        scene = scene_data(components, title="Precision", coordinate_system="mm; +Z up")
        self.assertEqual(scene["parts"][0]["vertices"], viewer_data(components)["parts"][0]["vertices"])
        floats = np.frombuffer(base64.b64decode(scene["parts"][0]["vertices"]), dtype="<f4").reshape(-1, 6)
        world = floats[:, :3].astype(np.float64)*scene["scale_mm"]+scene["origin_mm"]
        np.testing.assert_array_equal(world, mesh.triangles.reshape(-1, 3))
        self.assertTrue(np.all(np.ptp(mesh.vertices.astype(np.float32), axis=0) == 0))

    def test_scene_identity_and_placement_are_not_applied_twice(self):
        assembly = build()
        scene = assembly.viewer_scene()
        self.assertEqual(scene["units"], "mm")
        self.assertEqual(scene["up"], "Z")
        self.assertEqual(len(scene["parts"]), 6)
        top = next(part for part in scene["parts"] if part["id"] == "top")
        self.assertEqual(top["part_id"], "plate")
        self.assertEqual(top["transform_mm"][2][3], 36)
        self.assertEqual(top["bounds_mm"], [[0., 0., 36.], [120., 80., 40.]])

    def test_invalid_export_choice_or_missing_assets_preserves_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            assembly = build()
            assembly.export(output)
            before = {p.relative_to(output): sha256(p) for p in output.rglob("*") if p.is_file()}
            for arguments in ({"viewer_backend": "unknown"}, {"viewer_backend": "embedded"},
                              {"viewer_assets": directory}):
                with self.assertRaises(ValueError):
                    assembly.export(output, **arguments)
            self.assertEqual(before, {p.relative_to(output): sha256(p) for p in output.rglob("*") if p.is_file()})
            with self.assertRaises(ValueError):
                export_preview(lambda: assembly, output, viewer_backend="embedded")
            self.assertFalse((output / "preview-ready.json").exists())


@unittest.skipUnless(ASSETS, "Optional prebuilt runtime: set CADKIT_VIEWER_ASSETS")
class EmbeddedTests(unittest.TestCase):
    def test_malformed_asset_metadata_rejected_before_output_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime"
            shutil.copytree(ASSETS, runtime)
            marker = runtime / "assets.json"
            original = json.loads(marker.read_text())
            output = build().export(root / "output")
            before = {p.relative_to(output): sha256(p) for p in output.rglob("*") if p.is_file()}
            for value in ([], {**original, "version": None}, {**original, "renderer": {}},
                          {**original, "files": {**original["files"], "engine.js": None}}):
                marker.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    build().export(output, viewer_backend="embedded", viewer_assets=runtime)
                self.assertEqual(before, {p.relative_to(output): sha256(p) for p in output.rglob("*") if p.is_file()})

    def test_bundle_roundtrip_assets_integrity_and_preview_hashes(self):
        assembly = build()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, ack = root / "output", root / "ack.json"
            with patch.dict(os.environ, {"CADKIT_PREVIEW_ACK_FILE": str(ack),
                                       "CADKIT_PREVIEW_RUN_ID": "embedded-case"}):
                export_preview(lambda: assembly, output, viewer_backend="embedded", viewer_assets=ASSETS)
                self.assertEqual(check_exports(Context(assembly), output)["viewer_backend"], "embedded")
                marker = json.loads((output / "preview-ready.json").read_text())
                self.assertEqual(len(marker["viewer_files_sha256"]), 10)
                write_json(ack, {"run_id": "embedded-case", "build_id": marker["build_id"], "opened_at": utc_now()})
                self.assertEqual(wait_for_ack(output)["status"], "opened_unvalidated")
                (output / "viewer-scene.json").write_text("{}")
                with self.assertRaisesRegex(ValueError, "companion changed"):
                    wait_for_ack(output)
            runtime = output / "viewer-assets"
            read_assets(runtime)
            (runtime / "engine.css").write_text("corrupt")
            with self.assertRaisesRegex(ValueError, "integrity mismatch"):
                read_assets(runtime)
            before = sha256(output / "viewer.html")
            with self.assertRaises(ValueError):
                assembly.export(output, viewer_backend="embedded", viewer_assets=runtime)
            self.assertEqual(sha256(output / "viewer.html"), before)

    @unittest.skipUnless(os.environ.get("CADKIT_BROWSER"), "Set CADKIT_BROWSER for real browser checks")
    def test_embedded_browser_controls_offline_and_disposal(self):
        with tempfile.TemporaryDirectory() as directory:
            output = build().export(directory, viewer_backend="embedded", viewer_assets=ASSETS)
            self.assertEqual(check_browser(output, 6, os.environ["CADKIT_BROWSER"])["status"], "passed")


if __name__ == "__main__":
    unittest.main()
