"""Optional browser checks: set CADKIT_BROWSER to an Edge/Chrome executable."""

import os
from pathlib import Path
import tempfile
import unittest

from example import build
from cadkit import Assembly, Instance, Part
from cadkit.geometry import box
from cadkit.validation import check_browser, rendered_pixels


@unittest.skipUnless(os.environ.get("CADKIT_BROWSER"), "Set CADKIT_BROWSER and install playwright for browser checks")
class BrowserTests(unittest.TestCase):
    def test_achromatic_and_colored_geometry_pass_but_blank_colored_background_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            for color in ("#000000", "#777777", "#ffffff", "#58b9c9"):
                with self.subTest(color=color):
                    assembly = Assembly("Raster regression", "+X right, +Y back, +Z up; mm")
                    assembly.add_part(Part("block", box(40, 30, 20), "Block", "Concept", color))
                    assembly.add_instance(Instance("block", "block"))
                    output = assembly.export(Path(directory) / color[1:])
                    report = check_browser(output, 1, os.environ["CADKIT_BROWSER"])
                    self.assertTrue(all(count > 1000 for count in report["pixels_by_view"].values()))
                    viewer = output / "viewer.html"
                    text = viewer.read_text(encoding="utf-8")
                    viewer.write_text(text.replace("gl.drawArrays(", "if(false)gl.drawArrays("),
                                      encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "no meaningful raster geometry"):
                        check_browser(output, 1, os.environ["CADKIT_BROWSER"])
                    viewer.write_text(
                        text.replace("gl.drawArrays(", "if(false)gl.drawArrays(")
                        .replace("gl.clearColor(.063,.098,.137,1)", "gl.clearColor(1,0,0,1)"),
                        encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "no meaningful raster geometry"):
                        check_browser(output, 1, os.environ["CADKIT_BROWSER"])

    def test_offline_render_and_controls(self):
        from playwright.sync_api import sync_playwright

        with tempfile.TemporaryDirectory() as directory:
            path = build().export(directory) / "viewer.html"
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    executable_path=os.environ["CADKIT_BROWSER"], headless=True,
                    args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
                )
                page = browser.new_page(viewport={"width": 1400, "height": 1000})
                errors, remote = [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda request: remote.append(request.url)
                        if request.url.startswith(("http://", "https://")) else None)
                page.goto(Path(path).as_uri(), wait_until="load")
                page.wait_for_function("document.getElementById('status').textContent.startsWith('6 / 6')")
                self.assertEqual(page.locator("#components .part").count(), 6)
                self.assertIn("Millimetres", page.locator("#conventions").inner_text())
                self.assertIn("no load rating", page.locator("#assumptions").text_content())
                self.assertTrue(page.locator("#error").is_hidden())
                for preset in ("top", "under", "front", "side", "iso"):
                    page.locator("#"+preset).click()
                    pixels = rendered_pixels(page)
                    self.assertGreater(pixels, 1000, preset)
                page.locator("#search").fill("standoff_2")
                self.assertEqual(page.locator("#components .part:visible").count(), 1)
                page.locator("#components .part:visible button").click()
                self.assertIn("Printed polymer", page.locator("#selected").inner_text())
                self.assertIn("Size (mm)", page.locator("#selected").inner_text())
                page.locator("#isolate").click()
                self.assertTrue(page.locator("#status").inner_text().startswith("1 / 6"))
                page.locator("#iso").click()
                page.locator("#search").fill("")
                self.assertTrue(page.locator("#status").inner_text().startswith("6 / 6"))
                page.locator("#hideAll").click()
                page.locator("#fit").click()
                self.assertTrue(page.evaluate("Number.isFinite(span)"))
                page.locator("#showAll").click()
                page.locator("#components input").first.uncheck()
                self.assertTrue(page.locator("#status").inner_text().startswith("5 / 6"))
                page.locator("#focus").click()
                self.assertTrue(page.evaluate("parts[selected].visible"))
                bounds = page.locator("#view").bounding_box()
                x, y = bounds["x"]+50, bounds["y"]+50
                before = page.evaluate("yaw")
                page.mouse.move(x, y)
                page.mouse.down()
                page.mouse.move(x+50, y+20)
                page.mouse.up()
                self.assertNotEqual(before, page.evaluate("yaw"))
                page.mouse.wheel(0, -100)
                page.wait_for_function("zoom>1")
                page.keyboard.down("Shift")
                page.mouse.down()
                page.mouse.move(x+80, y+50)
                page.mouse.up()
                page.keyboard.up("Shift")
                self.assertNotEqual(page.evaluate("pan"), [0, 0])
                self.assertEqual(page.evaluate("gl.getError()"), 0)
                self.assertFalse(errors, errors)
                self.assertFalse(remote, remote)
                browser.close()


if __name__ == "__main__":
    unittest.main()
