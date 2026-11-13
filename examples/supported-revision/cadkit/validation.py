"""Reusable solid, export and offline-browser checks; no design-specific geometry."""

import argparse
import importlib
from itertools import combinations
import json
import os
from pathlib import Path
import sys
import time

import manifold3d as m
import numpy as np
import trimesh

from .preview import utc_now, wait_for_ack
from .timing import stage


def require(condition, message):
    if not condition:
        raise ValueError(message)


def mesh_solid(mesh):
    solid = m.Manifold(m.Mesh64(
        np.array(mesh.vertices, dtype=np.float64, order="C", copy=True),
        np.array(mesh.faces, dtype=np.uint64, order="C", copy=True),
    ))
    require(solid.status() == m.Error.NoError, f"Reloaded mesh is invalid: {solid.status()}")
    return solid


class Context:
    def __init__(self, assembly):
        self.assembly = assembly
        self.local, self.placed = assembly.meshes()
        self.solids = {
            item.id: assembly.parts[item.part_id].solid.transform(item.placement.matrix()[:3].tolist())
            for item in assembly.instances
        }

    @staticmethod
    def require(condition, message):
        require(condition, message)

    def expect_bounds(self, name, bounds, tolerance=.0002):
        require(np.allclose(self.placed[name].bounds, bounds, atol=tolerance, rtol=0),
                f"{name}: required bounds do not match")

    def expect_gap(self, first, second, expected, tolerance=.0002):
        require(expected >= 0 and tolerance > 0, "Gap and tolerance must be nonnegative/positive")
        # A cap above the expected gap distinguishes actual distance from a capped result.
        actual = self.solids[first].min_gap(self.solids[second], max(1, expected+1))
        require(abs(actual-expected) <= tolerance,
                f"{first}/{second}: gap {actual} mm, expected {expected} mm")
        return float(actual)

    def check_interferences(self, allowed=()):
        allowed = {frozenset(pair) for pair in allowed}
        pairs, intersections, overlaps = 0, 0, []
        for first, second in combinations(self.placed, 2):
            pairs += 1
            a, b = self.placed[first].bounds, self.placed[second].bounds
            if np.all(np.minimum(a[1], b[1])-np.maximum(a[0], b[0]) > 1e-7):
                intersections += 1
                volume = float((self.solids[first] ^ self.solids[second]).volume())
                if volume > .01:
                    overlaps.append({"first": first, "second": second, "volume_mm3": volume})
                    require(frozenset((first, second)) in allowed,
                            f"Unexpected interference: {first}/{second}: {volume} mm^3")
        return {"pairs": pairs, "boolean_checks": intersections, "documented_overlaps": overlaps,
                "note": "Zero overlap does not establish clearance or physical fit."}


def compare_solid(actual, expected, label):
    tolerance = max(.02, expected.volume()*1e-5)
    difference = (actual-expected).volume()+(expected-actual).volume()
    require(difference <= tolerance, f"{label}: exported solid changed by {difference} mm^3")
    return float(difference)


def check_exports(context, output):
    output = Path(output)
    assembly = context.assembly
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    from .revision import sha256, verify_export
    revision = verify_export(assembly.revision, output)
    if "review" in manifest:
        from .review import check_review
        check_review(assembly.revision, context.placed, manifest, output)
    require((manifest["geometry_units"], manifest["stl_units"], manifest["glb_units"]) == ("mm", "mm", "m"),
            "Manifest must specify mm geometry/STLs and metre GLB")
    require(manifest["parameters"] == json.loads(json.dumps(assembly.parameters)),
            "Exported parameter/provenance metadata is stale")
    require(manifest["assumptions"] == assembly.assumptions, "Exported assumptions are stale")
    require(manifest["coordinate_system"] == assembly.coordinate_system, "Exported coordinate frame is stale")
    require({item["id"] for item in manifest["parts"]} == set(assembly.parts), "Wrong manifest parts")
    require(len(manifest["parts"]) == len(assembly.parts), "Duplicate manifest parts")
    require({item["id"] for item in manifest["instances"]} == set(context.placed), "Wrong manifest instances")
    require(len(manifest["instances"]) == len(context.placed), "Duplicate manifest instances")
    for entry in manifest["parts"]:
        part = assembly.parts[entry["id"]]
        require(entry.get("visual_regions", []) == [r.record() for r in part.visual_regions],
                f"{part.id}: stale visual region mapping")
        require(all(entry[key] == getattr(part, key) for key in ("name", "color", "material", "notes")),
                f"{part.id}: stale physical part metadata")
    errors = []
    for entries, meshes, folder in ((manifest["parts"], context.local, "parts"),
                                     (manifest["instances"], context.placed, "assembled")):
        for entry in entries:
            require(entry["stl"] == f"{folder}/{entry['id']}.stl", "Unexpected manifest STL path")
            path = output / entry["stl"]
            require(path.read_bytes().startswith(b"solid "), f"{entry['id']}: expected ASCII STL")
            mesh = trimesh.load_mesh(path)
            require(mesh.is_volume and mesh.is_watertight and np.isfinite(mesh.vertices).all(),
                    f"{entry['id']}: invalid reloaded STL")
            require(np.allclose(mesh.bounds, meshes[entry["id"]].bounds, atol=.0002, rtol=0),
                    f"{entry['id']}: STL bounds mismatch")
            require(np.allclose(mesh.bounds, entry["bounds_mm"], atol=.0002, rtol=0),
                    f"{entry['id']}: stale manifest bounds")
            errors.append(compare_solid(mesh_solid(mesh), mesh_solid(meshes[entry["id"]]), entry["id"]))
            if folder == "parts" and assembly.parts[entry["id"]].visual_regions:
                require(np.allclose(mesh.triangles, meshes[entry["id"]].triangles, atol=.0002, rtol=0),
                        f"{entry['id']}: STL triangle order no longer binds visual regions")
    by_id = {item.id: item for item in assembly.instances}
    for entry in manifest["instances"]:
        item = by_id[entry["id"]]
        require(entry["part_id"] == item.part_id and
                np.allclose(entry["transform_mm"], item.placement.matrix(), atol=1e-8, rtol=0),
                f"{item.id}: wrong manifest part reference or transform")
    scene = trimesh.load(output / "assembly.glb", force="scene")
    require(set(scene.graph.nodes_geometry) == set(context.placed), "Wrong GLB instance nodes")
    require(len(scene.geometry) == len(context.local), "GLB did not reuse part definitions")
    for item in assembly.instances:
        transform, geometry = scene.graph[item.id]
        expected = item.placement.matrix()
        expected[:3, 3] *= .001
        require(np.allclose(transform, expected, atol=1e-8, rtol=0), f"{item.id}: wrong GLB transform")
        mesh = scene.geometry[geometry].copy()
        mesh.apply_transform(transform)
        require(np.allclose(mesh.bounds, context.placed[item.id].bounds*.001, atol=2e-7, rtol=0),
                f"{item.id}: wrong GLB bounds/scale")
        part = assembly.parts[item.part_id]
        actual = scene.geometry[geometry]
        if part.visual_regions:
            from .regions import colored_mesh
            expected_mesh = colored_mesh(part, context.local[item.part_id])
            require(np.allclose(actual.triangles, expected_mesh.triangles*.001, atol=2e-7, rtol=0),
                    f"{item.id}: GLB region geometry mapping changed")
            require(np.array_equal(actual.visual.vertex_colors[actual.faces],
                                   expected_mesh.visual.vertex_colors[expected_mesh.faces]),
                    f"{item.id}: wrong GLB region colors")
        else:
            color = trimesh.visual.color.hex_to_rgba(part.color)
            require(np.all(actual.visual.vertex_colors == color), f"{item.id}: wrong GLB color")
    html = (output / "viewer.html").read_text(encoding="utf-8")
    backend = manifest.get("viewer", {}).get("backend", "lightweight")
    require(backend in ("lightweight", "embedded"), "Unknown exported viewer backend")
    if backend == "embedded":
        from .embedded import read_assets
        from .scene import script_json

        require(manifest["viewer"]["scene"] == "viewer-scene.json" and
                manifest["viewer"]["assets"] == "viewer-assets", "Unexpected viewer companion paths")
        runtime, _ = read_assets(output / "viewer-assets")
        require(manifest["viewer"]["runtime_version"] == runtime["version"] and
                manifest["viewer"]["api_version"] == runtime["api_version"] and
                manifest["viewer"]["renderer"] == runtime["renderer"], "Stale viewer runtime metadata")
        expected = assembly._viewer_scene(context.placed)
        require((output / "viewer-scene.json").read_text(encoding="utf-8") == script_json(expected),
                "Viewer scene does not match model geometry/identity/metadata")
        marker = '<script id="scene" type="application/json">'
        require(marker in html, "Embedded viewer has no inline scene")
        payload = html.split(marker, 1)[1].split("</script>", 1)[0]
        require(payload == script_json(expected), "Standalone scene differs from module scene")
        return {"stls_reloaded": len(errors), "glb_instances": len(context.placed),
                "shared_geometries": len(context.local), "max_solid_difference_mm3": max(errors),
                "viewer_backend": backend, "scene_schema_version": 1,
                "revision": revision, "manifest_sha256": sha256(output / "manifest.json")}
    payload = html.split('<script id="model" type="application/json">')[1].split("</script>")[0]
    viewer = json.loads(payload)
    require(viewer["units"] == "mm" and viewer["coordinateSystem"] == assembly.coordinate_system,
            "Viewer units/axes mismatch")
    require(viewer["assumptions"] == assembly.assumptions, "Viewer dropped uncertainty")
    if any(part.visual_regions for part in assembly.parts.values()):
        from .regions import render_surfaces
        from .viewer import viewer_data
        components, metadata, sources = render_surfaces(list(context.placed.items()), manifest)
        expected = viewer_data(components)["parts"]
        require(len(viewer["parts"]) == len(expected), "Wrong finish surface count")
        for record, wanted in zip(viewer["parts"], expected):
            key = wanted["name"]
            require(all(record.get(k) == wanted[k] for k in ("name", "vertices", "triangles", "bounds")) and
                    all(record.get(k) == metadata[key][k] for k in ("color", "material", "notes")) and
                    all(record.get(k) == sources[key][k] for k in ("part_id", "physical_instance_id", "region_id")),
                    "Wrong viewer region geometry, finish or physical mapping")
    else:
        require({part["name"] for part in viewer["parts"]} == set(context.placed), "Wrong viewer components")
    return {"stls_reloaded": len(errors), "glb_instances": len(context.placed),
            "shared_geometries": len(context.local), "max_solid_difference_mm3": max(errors),
            "revision": revision, "manifest_sha256": sha256(output / "manifest.json")}


def check_browser(output, count, executable):
    output = Path(output).resolve()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    backend = manifest.get("viewer", {}).get("backend", "lightweight")
    require(backend in ("lightweight", "embedded"), "Unknown exported viewer backend")
    if any(p.get("visual_regions") for p in manifest["parts"]):
        require(count == len(manifest["instances"]), "Wrong physical instance count")
        if backend == "embedded":
            count = len(json.loads((output / "viewer-scene.json").read_text(encoding="utf-8"))["parts"])
        else:
            html = (output / "viewer.html").read_text(encoding="utf-8")
            count = len(json.loads(html.split('<script id="model" type="application/json">')[1].split("</script>")[0])["parts"])
    if backend == "embedded":
        return check_embedded_browser(output, count, executable)
    from playwright.sync_api import sync_playwright

    output = Path(output).resolve()
    errors, remote, pixels = [], [], {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=str(executable), headless=True,
            args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
        )
        try:
            page = browser.new_page(viewport={"width": 1500, "height": 1050})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.on("request", lambda request: remote.append(request.url)
                    if request.url.startswith(("http://", "https://")) else None)
            page.route("http://**/*", lambda route: route.abort())
            page.route("https://**/*", lambda route: route.abort())
            page.goto((output / "viewer.html").as_uri(), wait_until="load")
            page.wait_for_function(
                "(n)=>document.getElementById('status').textContent.startsWith(`${n} / ${n}`)", arg=count)
            require(page.locator("#components .part").count() == count, "Viewer component count mismatch")
            require(page.locator("#error").is_hidden(), "Viewer reports an error")
            for preset in ("top", "under", "front", "side", "iso"):
                page.locator("#"+preset).click()
                pixels[preset] = page.evaluate("""()=>{
                    draw();
                    const bytes=new Uint8Array(canvas.width*canvas.height*4);
                    gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,bytes);
                    let colored=0;
                    for(let i=0;i<bytes.length;i+=4)
                        if(Math.max(bytes[i],bytes[i+1],bytes[i+2])-Math.min(bytes[i],bytes[i+1],bytes[i+2])>45)colored++;
                    return colored;
                }""")
                require(pixels[preset] > 1000, f"{preset}: no meaningful raster geometry")
            (output / "evidence").mkdir(exist_ok=True)
            page.screenshot(path=str(output / "evidence" / "validated-preview.png"))
            name = page.locator("#components .part button").first.inner_text()
            page.locator("#search").fill(name)
            require(page.locator("#components .part:visible").count() >= 1, "Search failed")
            page.locator("#components .part:visible button").first.click()
            require(bool(page.locator("#selected").inner_text()), "Selection failed")
            page.locator("#isolate").click()
            require(page.locator("#status").inner_text().startswith(f"1 / {count}"), "Isolate failed")
            page.locator("#search").fill("")
            page.locator("#hideAll").click()
            page.locator("#fit").click()
            require(page.evaluate("Number.isFinite(span)"), "Empty-view fit failed")
            page.locator("#showAll").click()
            page.locator("#components input").first.uncheck()
            require(page.locator("#status").inner_text().startswith(f"{count-1} / {count}"), "Visibility failed")
            page.locator("#focus").click()
            require(page.evaluate("parts[selected].visible"), "Fit selected failed")
            bounds = page.locator("#view").bounding_box()
            x, y = bounds["x"]+50, bounds["y"]+50
            before = page.evaluate("yaw")
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x+50, y+20)
            page.mouse.up()
            require(page.evaluate("yaw") != before, "Orbit failed")
            page.mouse.wheel(0, -100)
            page.wait_for_function("zoom>1")
            page.keyboard.down("Shift")
            page.mouse.down()
            page.mouse.move(x+80, y+50)
            page.mouse.up()
            page.keyboard.up("Shift")
            require(page.evaluate("pan") != [0, 0], "Pan failed")
            require(page.evaluate("gl.getError()") == 0 and not errors, f"Rendering errors: {errors}")
            require(not remote, f"Offline viewer requested remote resources: {remote}")
        finally:
            browser.close()
    return {"status": "passed", "pixels_by_view": pixels, "errors": errors, "remote_requests": remote}


def check_embedded_browser(output, count, executable):
    from playwright.sync_api import sync_playwright

    errors, remote, pixels = [], [], {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=str(executable), headless=True,
                                    args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        try:
            page = browser.new_page(viewport={"width": 1500, "height": 1050})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.on("request", lambda request: remote.append(request.url)
                    if request.url.startswith(("http://", "https://")) else None)
            page.route("http://**/*", lambda route: route.abort())
            page.route("https://**/*", lambda route: route.abort())
            page.goto((output / "viewer.html").as_uri())
            require(page.evaluate("()=>window.cadReady") is True, "Embedded viewer did not become ready")
            state = page.evaluate("()=>cadViewer.getState()")
            require(len(state["parts"]) == count and len(state["visible"]) == count, "Embedded component count mismatch")
            frame = page.frame_locator("iframe")
            require(frame.locator(".parts button").count() == count, "Embedded list count mismatch")
            require(page.get_by_role("alert").is_hidden(), "Embedded viewer reports an error")
            for preset in ("iso", "top", "front", "right", "bottom"):
                page.evaluate("(name)=>cadViewer.preset(name)", preset)
                sample = page.evaluate("()=>cadViewer.pixels()")
                pixels[preset] = sample["colored"]
                require(sample["colored"] > 1000, f"{preset}: no meaningful embedded raster geometry")
            filtered = page.evaluate("()=>cadViewer.filter('no-such-instance-!@#')")
            require(filtered["matched"] == 0 and len(filtered["state"]["visible"]) == count,
                    "Embedded filter altered visibility")
            page.evaluate("()=>cadViewer.filter('')")
            frame.locator(".parts button").first.click()
            require(page.evaluate("()=>cadViewer.getState().then(s=>s.selected)") == state["parts"][0]["id"],
                    "Embedded list selection failed")
            frame.get_by_role("button", name="Isolate", exact=True).click()
            require(len(page.evaluate("()=>cadViewer.getState()")["visible"]) == 1, "Embedded isolate failed")
            frame.get_by_role("button", name="Hide all", exact=True).click()
            require(page.evaluate("()=>cadViewer.fit()")["fitted"] is False, "Empty embedded fit failed")
            require(page.evaluate("()=>cadViewer.pixels()")["colored"] == 0, "Hidden meshes still render")
            frame.get_by_role("button", name="Show all", exact=True).click()
            require(page.evaluate("()=>cadViewer.fit('selected')")["fitted"], "Embedded fit selected failed")
            page.evaluate("()=>cadViewer.fit()")
            page.evaluate("()=>cadViewer.preset('iso')")
            canvas = frame.locator("canvas").bounding_box()
            x, y = canvas["x"]+canvas["width"]*.35, canvas["y"]+canvas["height"]*.4
            before = page.evaluate("()=>cadViewer.getState().then(s=>s.camera)")
            page.mouse.move(x, y); page.mouse.down()
            page.mouse.move(x+60, y+30, steps=4); page.mouse.up()
            after = page.evaluate("()=>cadViewer.getState().then(s=>s.camera)")
            require(before != after, "Embedded pointer orbit failed")
            page.mouse.wheel(0, -180)
            page.wait_for_function("async(z)=>(await cadViewer.getState()).camera.zoom!==z", arg=after["zoom"])
            before = page.evaluate("()=>cadViewer.getState().then(s=>s.camera.target)")
            page.mouse.down(button="right")
            page.mouse.move(x+100, y+65, steps=4); page.mouse.up(button="right")
            require(page.evaluate("()=>cadViewer.getState().then(s=>s.camera.target)") != before,
                    "Embedded pointer pan failed")
            (output / "evidence").mkdir(exist_ok=True)
            page.screenshot(path=str(output / "evidence" / "validated-preview.png"))
            disposal = page.evaluate("()=>cadViewer.dispose()")
            require(disposal["after"]["total"] == 0 and disposal["remainingCanvas"] == 0,
                    "Embedded tracked GPU resources remained after disposal")
            require(page.locator("iframe").count() == 0, "Embedded frame remained after disposal")
            require(not errors and not remote, f"Embedded browser errors/network: {errors}/{remote}")
        finally:
            browser.close()
    return {"status": "passed", "backend": "embedded", "pixels_by_view": pixels,
            "errors": errors, "remote_requests": remote, "disposal": disposal}


@stage("validation")
def main(*, _assembly_provider=None):
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(sys.argv[0]).resolve().parent
    parser.add_argument("--output", type=Path, default=root / "output")
    parser.add_argument("--browser", type=Path, default=os.environ.get("CADKIT_BROWSER"))
    args = parser.parse_args()
    started = time.monotonic()
    report_path = args.output / "validation.json"
    brief_path = root / "design_brief.json"
    if brief_path.is_file():
        from .revision import require_modeling_ready
        try:
            require_modeling_ready(json.loads(brief_path.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError) as error:
            parser.exit(1, json.dumps({"status": "blocked", "error": str(error)})+"\n")
    try:
        from .revision import retire_qualification
        retire_qualification(args.output, "Validation is being rerun; qualify to renew the source-bound handoff")
        with stage("preview_ack"):
            preview = wait_for_ack(args.output)
        validation_started_at = utc_now()
        if _assembly_provider is None:
            with stage("validation_rebuild"):
                context = Context(importlib.import_module("model").build())
        else:
            # Private same-process handoff; standalone validation always rebuilds.
            with stage("validation_context"):
                context = Context(_assembly_provider())
        from .revision import validate_snapshot
        with stage("project_checks"):
            project = importlib.import_module("checks").check(context)
        allowed = getattr(importlib.import_module("checks"), "ALLOWED_OVERLAPS", ())
        with stage("export_checks"):
            exports = check_exports(context, args.output)
        with stage("interference_checks"):
            interference = context.check_interferences(allowed)
        if args.browser:
            with stage("browser_checks"):
                browser = check_browser(args.output, len(context.placed), args.browser)
        else:
            browser = {"status": "not_run", "reason": "No browser executable supplied"}
        report = {
            "status": "passed" if args.browser else "geometry_passed_browser_not_run",
            "revision": validate_snapshot(context.assembly.revision) if context.assembly.revision is not None else None,
            "project": project, "parts": len(context.local), "instances": len(context.placed),
            "preview": preview, "validation_started_at": validation_started_at,
            "exports": exports, "interference": interference, "browser": browser,
            "limits": "Mesh/static-pose checks, not manufacturing fit, strength or motion certification.",
        }
    except (OSError, ValueError, AssertionError, KeyError) as error:
        report = {"status": "failed", "error": str(error)}
        args.output.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        parser.exit(1, json.dumps(report)+"\n")
    report["elapsed_seconds"] = time.monotonic()-started
    report["completed_at"] = utc_now()
    with stage("validation_report"):
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("status", "parts", "instances", "elapsed_seconds")},
                     separators=(",", ":")))


if __name__ == "__main__":
    main()
