"""Opt-in prebuilt viewer assets; no npm, downloads or fallback during CAD export."""

import hashlib
from html import escape
import json
from pathlib import Path

from .scene import script_json


ASSET_NAMES = ("cad-viewer.mjs", "cad-viewer.js", "engine.html", "engine.js", "engine.css",
               "scene.schema.json", "index.d.ts", "THIRD-PARTY-NOTICES.txt")


def read_assets(folder):
    if folder is None:
        raise ValueError("The embedded viewer requires viewer_assets pointing to prebuilt cad-viewer/dist")
    folder = Path(folder).expanduser().resolve()
    marker = folder / "assets.json"
    if not marker.is_file():
        raise ValueError(f"Missing prebuilt viewer assets: {marker}; build/provide the optional cad-viewer package")
    manifest = json.loads(marker.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("Prebuilt viewer assets manifest must be an object")
    if (manifest.get("schema_version"), manifest.get("api_version"), manifest.get("scene_schema_version"),
        manifest.get("package")) != (1, 1, 1, "cad-assembly-viewer"):
        raise ValueError("Unsupported embedded viewer assets/API/scene schema")
    renderer = manifest.get("renderer")
    if (not isinstance(manifest.get("version"), str) or not manifest["version"].strip()
            or not isinstance(renderer, dict) or renderer.get("name") != "three-cad-viewer"
            or not isinstance(renderer.get("version"), str) or not renderer["version"].strip()):
        raise ValueError("Prebuilt viewer assets require runtime and renderer version metadata")
    if not isinstance(manifest.get("files"), dict) or set(manifest["files"]) != set(ASSET_NAMES):
        raise ValueError("Prebuilt viewer assets have an unexpected file set")
    files = {"assets.json": marker.read_bytes()}
    for name in ASSET_NAMES:
        path = folder / name
        data = path.read_bytes()
        expected = manifest["files"][name]
        if (not isinstance(expected, dict) or
                (len(data), hashlib.sha256(data).hexdigest()) != (expected.get("bytes"), expected.get("sha256"))):
            raise ValueError(f"Prebuilt viewer asset integrity mismatch: {name}")
        files[name] = data
    return manifest, files


def write_scene_bundle(scene, output, assets):
    """Write viewer.html plus scene JSON and a self-contained hosted module bundle."""
    manifest, files = assets
    output = Path(output)
    runtime = files["cad-viewer.js"].decode("utf-8").replace("</script", r"<\/script").replace(
        "</SCRIPT", r"<\/SCRIPT")
    payload = script_json(scene)
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(scene["title"])}</title>
<style>html,body,#viewer{{margin:0;width:100%;height:100%;background:#151d28;color:white;font:14px system-ui}}</style>
</head><body><div id="viewer"></div><script id="scene" type="application/json">{payload}</script>
<script>{runtime}
window.cadScene=JSON.parse(document.getElementById("scene").textContent);
window.cadViewer=new CadEmbed.CadViewer(document.getElementById("viewer"));
window.cadReady=window.cadViewer.load(window.cadScene).then(async()=>{{
 await window.cadViewer.flush();return true;
}});
window.cadReady.catch(error=>{{document.body.dataset.error=error.message;}});
</script></body></html>'''
    (output / "viewer.html").write_text(html, encoding="utf-8")
    (output / "viewer-scene.json").write_text(payload, encoding="utf-8")
    asset_folder = output / "viewer-assets"
    asset_folder.mkdir()
    for name, data in files.items():
        (asset_folder / name).write_bytes(data)
    return {"backend": "embedded", "scene_schema_version": 1, "scene": "viewer-scene.json",
            "assets": "viewer-assets", "api_version": manifest["api_version"],
            "runtime_version": manifest["version"], "renderer": manifest["renderer"]}
