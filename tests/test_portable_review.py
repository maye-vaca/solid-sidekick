import base64
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = Path(os.environ.get("CADKIT_REVIEW_EXAMPLE", ROOT / "examples" / "portable-review"))


def packet_data(packet):
    if hashlib.sha256(packet["payload"].encode("utf-8")).hexdigest() != packet["sha256"]:
        raise ValueError("Example packet hash mismatch")
    return json.loads(packet["payload"])


def initial_packet():
    html = (EXAMPLE / "review.html").read_text(encoding="utf-8")
    embedded = re.search(r'<script id="review-data" type="application/json">(.*?)</script>', html, re.S)
    if embedded is None:
        raise ValueError("Initial review has no embedded packet")
    return json.loads(embedded[1])


def physical_bounds(scene, name):
    part = next(part for part in scene["parts"] if part["name"] == name)
    points = struct.iter_unpack("<6f", base64.b64decode(part["vertices"], validate=True))
    vertices = [[point[axis] * scene["scale_mm"] + scene["origin_mm"][axis]
                 for axis in range(3)] for point in points]
    return [[min(point[axis] for point in vertices) for axis in range(3)],
            [max(point[axis] for point in vertices) for axis in range(3)]]


class PortableReviewTests(unittest.TestCase):
    def test_browser_only_inventory_contains_real_distinct_geometry_and_no_original_paths(self):
        inventory = json.loads((EXAMPLE / "file-hashes.json").read_bytes())
        self.assertEqual(set(inventory) | {"file-hashes.json"},
                         {path.relative_to(EXAMPLE).as_posix() for path in EXAMPLE.rglob("*") if path.is_file()})
        for name, expected in inventory.items():
            path = EXAMPLE / name
            data = path.read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected, name)
            self.assertNotIn(path.suffix, (".py", ".js", ".wasm", ".exe"))
            self.assertNotIn(b"C:\\Users\\", data)
            self.assertNotIn(b"C:/Users/", data)
        html = (EXAMPLE / "review.html").read_text(encoding="utf-8")
        self.assertNotRegex(html, r"<script[^>]+\bsrc\s*=")
        self.assertNotRegex(html, r"<link[^>]+\bhref\s*=")
        self.assertIn('href="review.html"', (EXAMPLE / "START_HERE.html").read_text())
        a = packet_data(initial_packet())
        b = packet_data(json.loads((EXAMPLE / "updates" / "revision-b.json").read_bytes()))
        expected = json.loads((EXAMPLE / "expected-state.json").read_bytes())
        self.assertEqual(b["previous"]["snapshot"]["identity"], a["current"]["snapshot"]["identity"])
        self.assertIn(a["current"]["snapshot"]["identity"]["id"],
                      b["current"]["snapshot"]["brief"]["revision"]["ancestors"])
        for key, data in (("a", a), ("b", b)):
            scene = data["current"]["scene"]
            self.assertEqual(data["current"]["snapshot"]["identity"], expected[key]["revision"])
            self.assertEqual(len(scene["parts"]), expected["fixed"]["physical_instances"])
            base, top = physical_bounds(scene, "base"), physical_bounds(scene, "top")
            self.assertAlmostEqual(base[1][0] - base[0][0], expected["fixed"]["width_mm"], places=4)
            self.assertAlmostEqual(base[1][1] - base[0][1], expected["fixed"]["depth_mm"], places=4)
            self.assertAlmostEqual(base[1][2] - base[0][2], expected["fixed"]["plate_thickness_mm"], places=4)
            self.assertAlmostEqual(top[0][2] - base[1][2], expected[key]["gap_mm"], places=4)
            self.assertAlmostEqual(top[1][2], expected[key]["assembly_height_mm"], places=4)

    @unittest.skipUnless(os.environ.get("CADKIT_BROWSER"), "Set CADKIT_BROWSER for actual offline review UI checks")
    def test_relocated_offline_file_picker_pending_apply_and_failure_preservation(self):
        from playwright.sync_api import sync_playwright

        with tempfile.TemporaryDirectory() as temporary, sync_playwright() as pw:
            root = Path(temporary)
            evidence = Path(os.environ.get("CADKIT_REVIEW_EVIDENCE", root / "evidence"))
            evidence.mkdir(parents=True, exist_ok=True)
            expected = json.loads((EXAMPLE / "expected-state.json").read_bytes())
            browser = pw.chromium.launch(
                executable_path=os.environ["CADKIT_BROWSER"], headless=True,
                args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
            )
            try:
                context = browser.new_context(offline=True, viewport={"width": 1600, "height": 1100})
                context.route("http://**/*", lambda route: route.abort())
                context.route("https://**/*", lambda route: route.abort())
                page = context.new_page()
                errors, remote = [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda request: remote.append(request.url)
                        if request.url.startswith(("http:", "https:", "ws:", "wss:")) else None)
                url = (EXAMPLE / "review.html").resolve().as_uri()
                page.goto(url, wait_until="load")
                page.wait_for_function("cadReview.getState().view && !cadReview.getState().blocked")
                current = page.frame(name="current")
                current.wait_for_function("typeof initialized!=='undefined' && initialized")

                def raster(frame):
                    return frame.evaluate("""()=>{
                        draw(); const b=new Uint8Array(canvas.width*canvas.height*4);
                        gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,b);
                        let n=0; for(let i=0;i<b.length;i+=4)
                        if(Math.max(b[i],b[i+1],b[i+2])-Math.min(b[i],b[i+1],b[i+2])>45)n++;
                        return n;
                    }""")

                a_pixels = raster(current)
                self.assertGreater(a_pixels, 1000)
                self.assertEqual(page.evaluate("cadReview.getState().revision"), expected["a"]["revision"])
                self.assertTrue(page.locator("#apply").is_disabled())
                page.locator("#iso").click()
                current.locator('#components input[aria-label="Show standoff_1"]').uncheck()
                canvas = current.locator("#view")
                box = canvas.bounding_box()
                x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                page.mouse.move(x, y)
                page.mouse.down()
                page.mouse.move(x + 40, y + 20, steps=4)
                page.mouse.up()
                page.wait_for_function("cadReview.getState().interacting.length===0")
                before = page.evaluate("cadReview.getState().view")
                self.assertFalse(before["visibility"]["standoff_1"])
                page.screenshot(path=str(evidence / "a-before-update.png"))

                page.locator("#load").set_input_files(EXAMPLE / "updates" / "revision-b.json")
                page.wait_for_function("!!cadReview.getState().pending")
                pending = page.evaluate("cadReview.getState()")
                self.assertEqual(pending["revision"], expected["a"]["revision"])
                self.assertEqual(pending["pending"], expected["b"]["revision"])
                self.assertEqual(pending["view"]["camera"], before["camera"])
                self.assertEqual(page.url, url)
                page.screenshot(path=str(evidence / "b-pending-not-applied.png"))

                # This is an isolated automated fixture, not the user's review page.
                page.locator("#apply").click()
                page.wait_for_function("(id)=>cadReview.getState().revision.id===id",
                                       arg=expected["b"]["revision"]["id"])
                current = page.frame(name="current")
                previous = page.frame(name="previous")
                for frame in (current, previous):
                    frame.wait_for_function("typeof initialized!=='undefined' && initialized")
                page.wait_for_function("cadReview.getState().view.visibility.standoff_1===false")
                applied = page.evaluate("cadReview.getState()")
                self.assertEqual(applied["view"]["camera"], before["camera"])
                self.assertIsNone(applied["pending"])
                self.assertEqual(page.url, url)
                self.assertEqual(len(context.pages), 1)
                b_pixels, prior_pixels = raster(current), raster(previous)
                self.assertGreater(b_pixels, 1000)
                self.assertGreater(prior_pixels, 1000)
                page.screenshot(path=str(evidence / "b-applied-by-test-harness.png"))

                corrupt = json.loads((EXAMPLE / "updates" / "revision-b.json").read_bytes())
                corrupt["sha256"] = "0" * 64
                bad = root / "corrupt.json"
                bad.write_text(json.dumps(corrupt), encoding="utf-8")
                malformed = root / "malformed.json"
                malformed.write_text("{", encoding="utf-8")
                stale = root / "stale-a.json"
                stale.write_text(json.dumps(initial_packet()), encoding="utf-8")
                for path, message in ((bad, "hash mismatch"), (malformed, "Review load failed"),
                                      (stale, "not a newer descendant")):
                    page.locator("#load").set_input_files(path)
                    page.wait_for_function("(s)=>document.getElementById('message').textContent.includes(s)", arg=message)
                    state = page.evaluate("cadReview.getState()")
                    self.assertEqual(state["revision"], expected["b"]["revision"])
                    self.assertEqual(state["view"]["camera"], before["camera"])
                    self.assertIsNone(state["pending"])
                    self.assertTrue(page.locator("#apply").is_disabled())
                page.reload()
                page.wait_for_function("cadReview.getState().blocked")
                self.assertEqual(page.frame(name="current").locator("canvas").count(), 0)
                page.locator("#load").set_input_files(EXAMPLE / "updates" / "revision-b.json")
                page.wait_for_function("!!cadReview.getState().pending")
                page.locator("#apply").click()
                page.wait_for_function("!cadReview.getState().blocked")
                self.assertEqual(page.evaluate("cadReview.getState().revision"), expected["b"]["revision"])
                self.assertFalse(errors, errors)
                self.assertFalse(remote, remote)
                report = {
                    "status": "passed", "browser": browser.version,
                    "os": os.name, "context_offline": True, "remote_page_requests": remote,
                    "page_errors": errors, "used_server": False, "used_copilot_tools": False,
                    "transport": "Actual file-input File API, no cadReview.load injection",
                    "apply": "Automated UI click in isolated test fixture; not human acceptance",
                    "a_pixels": a_pixels, "b_pixels": b_pixels, "prior_pixels": prior_pixels,
                    "pending_before_apply": True, "same_page": True,
                    "camera_and_visibility_preserved": True,
                    "corruption_malformed_stale_rejected": True,
                    "stale_reload_blocked_and_last_seen_recovered": True,
                    "human_apply": "not_observed",
                }
                (evidence / "browser-checks.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
