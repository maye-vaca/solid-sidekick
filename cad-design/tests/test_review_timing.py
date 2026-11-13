from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from test_revision import ROOT, brief, fixture
import new_project
import run_session as runner
import test_runner as runner_tests
from cadkit.preview import export_preview
from cadkit.review import read_packet
from cadkit.revision import advance_revision, verify_export
from cadkit.timing import stage
from cadkit.validation import Context, check_exports


class TimingTests(unittest.TestCase):
    def test_runner_collects_real_cad_tool_stages_and_does_not_invent_visible_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            new_project.create_project(root / "design")
            fake = root / "fake_cli.py"
            fake.write_text(runner_tests.FAKE_CLI)
            options = runner_tests.RunnerTests().options(root, "pipeline")
            environment = dict(os.environ)
            environment.pop("CADKIT_BROWSER", None)
            with patch.dict(os.environ, environment, clear=True), patch.object(
                    runner, "find_cli", return_value=[sys.executable, str(fake)]):
                result = runner.execute(options)
            pipeline = result["timings"]["pipeline"]
            self.assertEqual(pipeline["stages"]["geometry"][0]["status"], "passed")
            self.assertEqual(pipeline["stages"]["export_checks"][0]["status"], "passed")
            self.assertEqual(result["first_visible_preview"]["status"], "not_observed")
            self.assertGreater(result["first_ready_orchestration_seconds"], result["timings"]["cli_probe_seconds"])

    def test_first_host_open_is_separate_from_ready_and_survives_republishing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "fake_cli.py"
            fake.write_text(runner_tests.FAKE_CLI)
            options = runner_tests.RunnerTests().options(root, "previews-open")
            options.await_preview = True
            with patch.object(runner, "find_cli", return_value=[sys.executable, str(fake)]):
                result = runner.execute(options)
            self.assertEqual(result["first_visible_preview"]["build_id"], "first")
            self.assertEqual(result["attempts"][0]["latest_preview"]["build_id"], "second")
            self.assertGreaterEqual(result["first_visible_preview"]["orchestration_seconds"],
                                    result["first_ready_orchestration_seconds"])

    def test_activity_spans_preserve_overlaps_and_incomplete_observations(self):
        state = runner.Progress(10)
        state.accept({"type": "model.call_start"}, 11)
        state.accept({"type": "tool.execution_start", "data": {"toolCallId": "a"}}, 12)
        state.accept({"type": "tool.execution_complete", "data": {"toolCallId": "a"}}, 14)
        state.accept({"type": "model.call_finished"}, 15)
        state.accept({"type": "tool.execution_start", "data": {"toolCallId": "b"}}, 16)
        timings = state.timings()
        self.assertEqual(timings["model_activity"]["spans"][0]["elapsed_seconds"], 4)
        self.assertEqual(timings["tool_execution"]["spans"][0]["elapsed_seconds"], 2)
        self.assertEqual(timings["tool_execution"]["spans"][1]["status"], "incomplete")
        self.assertNotIn("elapsed_seconds", timings["tool_execution"]["spans"][1])
        self.assertEqual(timings["compaction"]["status"], "not_observed")

    def test_stage_failures_and_packaging_are_measured_without_changing_primary_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stages.jsonl"
            with patch.dict(os.environ, {"CADKIT_STAGE_FILE": str(path), "CADKIT_PREVIEW_RUN_ID": "timed"}):
                with self.assertRaisesRegex(ValueError, "geometry failure"):
                    with stage("geometry"):
                        raise ValueError("geometry failure")
                with stage("packaging"):
                    with zipfile.ZipFile(Path(directory) / "package.zip", "w") as archive:
                        archive.writestr("fact.json", '{"value":1}')
            evidence = runner.pipeline_timings(path, "timed")
            self.assertEqual(evidence["stages"]["geometry"][0]["status"], "failed")
            self.assertEqual(evidence["stages"]["packaging"][0]["status"], "passed")
            self.assertGreaterEqual(evidence["stages"]["packaging"][0]["elapsed_seconds"], 0)
            path.write_text('{"run_id":"timed","event":"cadkit.stage"}\n')
            self.assertEqual(runner.pipeline_timings(path, "timed")["status"], "invalid_evidence")

    def test_actual_scaffold_pipeline_records_geometry_export_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")
            path = project / "stages.jsonl"
            env = {**os.environ, "CADKIT_STAGE_FILE": str(path), "CADKIT_PREVIEW_RUN_ID": "pipeline"}
            env.pop("CADKIT_BROWSER", None)
            for command in (["model.py"], ["validate.py"]):
                result = subprocess.run([sys.executable, *command], cwd=project, env=env,
                                        capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
            evidence = runner.pipeline_timings(path, "pipeline")
            for name in ("geometry", "export", "validation", "validation_rebuild", "project_checks", "export_checks",
                         "interference_checks", "validation_report"):
                self.assertEqual(evidence["stages"][name][0]["status"], "passed", name)
            self.assertEqual(evidence["stages"]["browser_checks"], [])
            marker = json.loads((project / "output" / "preview-ready.json").read_text())
            self.assertEqual(Path(marker["viewer"]).name, "review.html")
            self.assertIn("export_seconds", marker["timings"])


class ReviewTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("CADKIT_BROWSER"), "Set CADKIT_BROWSER for review interaction checks")
    def test_review_notes_collapse_without_changing_pending_revision_or_camera(self):
        from playwright.sync_api import sync_playwright

        with tempfile.TemporaryDirectory() as directory, sync_playwright() as pw:
            root = Path(directory)
            source = brief()
            first = fixture(source)
            first.assumptions = ["Baseline provenance " * 100]
            before = first.export(root / "before")
            revised = advance_revision(source, "next", "Next concept")
            second = fixture(revised)
            second.assumptions = ["Current limitations " * 100]
            after = second.export(root / "after", previous_output=before)
            packet = json.loads((after / "review-state.json").read_text())
            browser = pw.chromium.launch(executable_path=os.environ["CADKIT_BROWSER"], headless=True,
                                        args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            try:
                page = browser.new_page(viewport={"width": 375, "height": 800})
                page.goto((before / "review.html").as_uri())
                page.wait_for_function("cadReview.getState().view")
                current = page.frame(name="current")
                current.wait_for_function("initialized")
                self.assertFalse(current.locator("#assumptions-section").evaluate("e=>e.open"))
                page.evaluate("p=>cadReview.load(p)", packet)
                state = page.evaluate("cadReview.getState()")
                current.locator("summary").click()
                current.wait_for_function("document.getElementById('assumptions-section').open")
                self.assertEqual(current.locator("#assumptions").inner_text(), first.assumptions[0].strip())
                self.assertEqual(page.evaluate("cadReview.getState()"), state)
                current.locator("summary").click()
                current.wait_for_function("!document.getElementById('assumptions-section').open")
                page.locator("#apply").click()
                current.wait_for_function("initialized && model.assumptions[0].startsWith('Current')")
                self.assertFalse(current.locator("#assumptions-section").evaluate("e=>e.open"))
                self.assertEqual(page.evaluate("cadReview.getState().revision.id"), "next")
                self.assertIsNone(page.evaluate("cadReview.getState().pending"))
                self.assertEqual(page.evaluate("cadReview.getState().view"), state["view"])
                current.locator("summary").click()
                current.wait_for_function("document.getElementById('assumptions-section').open")
                self.assertEqual(current.locator("#assumptions").inner_text(), second.assumptions[0].strip())
            finally:
                browser.close()

    def test_user_text_cannot_replace_review_template_tokens_or_close_script_payload(self):
        source = brief()
        source["name"] = "__RENDERER__ __BRIDGE__ </script><script>throw Error('not code')</script>"
        with tempfile.TemporaryDirectory() as directory:
            output = fixture(source).export(directory)
            html = (output / "review.html").read_text()
            payload = re.search(r'<script id="review-data" type="application/json">(.*?)</script>', html, re.S)[1]
            self.assertEqual(json.loads(payload), json.loads((output / "review-state.json").read_text()))
            self.assertNotIn("</script><script>throw Error('not code')</script>", payload)
    def revisions(self, root):
        source = brief()
        first = fixture(source)
        before = first.export(root / "before")
        revised = advance_revision(source, "wider", "Correct width",
                                   updates={"width": dict(source["dimensions"]["width"], value=144)})
        after = fixture(revised).export(root / "after", previous_output=before)
        newest = advance_revision(revised, "widest", "Second width correction",
                                  updates={"width": dict(revised["dimensions"]["width"], value=168)})
        last = fixture(newest).export(root / "last", previous_output=after)
        return source, revised, newest, before, after, last

    def test_history_is_source_bound_self_contained_and_same_revision_reexport_is_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            source, revised, _, before, after, _ = self.revisions(Path(directory))
            state = read_packet(after / "review-state.json")
            self.assertEqual(state["previous"]["snapshot"], fixture(source).revision)
            self.assertEqual(state["current"]["snapshot"], fixture(revised).revision)
            self.assertEqual(state["frame"]["bounds_mm"], [[0., 0., 0.], [144., 10., 2.]])
            original = (after / "review.html").read_bytes()
            fixture(revised).export(after)
            self.assertEqual(original, (after / "review.html").read_bytes())
            check_exports(Context(fixture(revised)), after)
            (after / "review-state.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                verify_export(fixture(revised).revision, after)
            self.assertTrue((before / "review.html").is_file())

    def test_incompatible_history_or_mutated_prior_artifact_is_not_silently_adopted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = brief()
            before = fixture(source).export(root / "before")
            unrelated = deepcopy(source)
            unrelated["revision"]["id"] = "unrelated"
            with self.assertRaisesRegex(ValueError, "newer or unrelated"):
                fixture(unrelated).export(root / "bad", previous_output=before)
            revised = advance_revision(source, "next", "Next")
            (before / "review.html").write_text("changed")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                fixture(revised).export(root / "bad", previous_output=before)
            self.assertFalse((root / "bad" / "manifest.json").exists())

    @unittest.skipUnless(os.environ.get("CADKIT_BROWSER"), "Set CADKIT_BROWSER for review raster/interaction checks")
    def test_blocked_reload_rejects_intermediate_packet_and_recovers_to_last_seen_or_newer(self):
        from playwright.sync_api import Error, sync_playwright

        with tempfile.TemporaryDirectory() as directory, sync_playwright() as pw:
            root = Path(directory)
            _, revised, newest, before, after, last = self.revisions(root)
            next_brief = advance_revision(newest, "fourth", "Next review")
            fourth = fixture(next_brief).export(root / "fourth", previous_output=last)
            conflict = deepcopy(newest)
            conflict["dimensions"]["width"]["value"] += 1
            conflicting = fixture(conflict).export(root / "conflicting", previous_output=after)
            branch = fixture(advance_revision(revised, "other-branch", "Divergent branch")).export(
                root / "branch", previous_output=after)
            packets = {name: json.loads((output / "review-state.json").read_text())
                       for name, output in (("B", after), ("C", last), ("D", fourth),
                                            ("conflict", conflicting), ("branch", branch))}
            browser = pw.chromium.launch(executable_path=os.environ["CADKIT_BROWSER"], headless=True,
                                        args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            try:
                page = browser.new_page()
                page.goto((before / "review.html").as_uri())
                page.wait_for_function("cadReview.getState().view && !cadReview.getState().blocked")
                page.evaluate("p=>cadReview.load(p)", packets["C"])
                self.assertEqual(page.evaluate("cadReview.apply()")["status"], "applied")
                page.reload()
                page.wait_for_function("cadReview.getState().blocked")
                for rejected in ("B", "conflict", "branch"):
                    with self.subTest(rejected=rejected), self.assertRaises(Error):
                        page.evaluate("p=>cadReview.load(p)", packets[rejected])
                self.assertTrue(page.evaluate("cadReview.getState().blocked"))
                self.assertIsNone(page.evaluate("cadReview.getState().pending"))
                self.assertEqual(page.frame(name="current").locator("canvas").count(), 0)
                self.assertEqual(page.evaluate("p=>cadReview.load(p)", packets["C"])["status"], "pending")
                self.assertEqual(page.evaluate("cadReview.apply()")["status"], "applied")
                self.assertEqual(page.evaluate("cadReview.getState().revision.id"), "widest")
                page.reload()
                page.wait_for_function("cadReview.getState().blocked")
                page.evaluate("p=>cadReview.load(p)", packets["D"])
                self.assertEqual(page.evaluate("cadReview.apply()")["status"], "applied")
                self.assertEqual(page.evaluate("cadReview.getState().revision.id"), "fourth")
            finally:
                browser.close()

    @unittest.skipUnless(os.environ.get("CADKIT_BROWSER"), "Set CADKIT_BROWSER for review raster/interaction checks")
    def test_offline_review_fixed_frame_user_state_pending_updates_and_stale_reload(self):
        from playwright.sync_api import Error, sync_playwright

        with tempfile.TemporaryDirectory() as directory, sync_playwright() as pw:
            _, _, _, _, after, last = self.revisions(Path(directory))
            packet = json.loads((last / "review-state.json").read_text())
            browser = pw.chromium.launch(executable_path=os.environ["CADKIT_BROWSER"], headless=True,
                                        args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            try:
                page = browser.new_page(viewport={"width": 1600, "height": 1000})
                errors, remote = [], []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on("request", lambda r: remote.append(r.url) if r.url.startswith(("http:", "https:")) else None)
                page.goto((after / "review.html").as_uri())
                page.wait_for_function("cadReview.getState().view && !cadReview.getState().blocked")
                current, previous = page.frame(name="current"), page.frame(name="previous")
                for frame in (current, previous):
                    frame.wait_for_function("typeof initialized!=='undefined' && initialized")
                    pixels = frame.evaluate("""()=>{
                        draw();const b=new Uint8Array(canvas.width*canvas.height*4);
                        gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,b);
                        let count=0;for(let i=0;i<b.length;i+=4)if(Math.max(b[i],b[i+1],b[i+2])-Math.min(b[i],b[i+1],b[i+2])>45)count++;
                        return count;}""")
                    self.assertGreater(pixels, 100)
                self.assertEqual(current.evaluate("center"), previous.evaluate("center"))
                self.assertEqual(current.evaluate("span"), previous.evaluate("span"))
                self.assertEqual(current.evaluate("parts[0].bounds[0][0]"), previous.evaluate("parts[0].bounds[0][0]"))
                for defect in ("frame", "lineage"):
                    data = json.loads(packet["payload"])
                    if defect == "frame":
                        data["frame"]["origin_mm"][0] += 20
                    else:
                        data["previous"] = data["current"]
                    payload = json.dumps(data)
                    inconsistent = dict(packet, payload=payload,
                                        sha256=hashlib.sha256(payload.encode()).hexdigest())
                    with self.assertRaises(Error):
                        page.evaluate("p=>cadReview.load(p)", inconsistent)
                    self.assertIn("wider", page.locator("#identity").inner_text())
                current.locator("#components input").first.uncheck()
                previous.wait_for_function("parts[0].visible===false")
                current.evaluate("yaw+=.2;zoom=1.3;pan=[14,8];draw()")
                page.wait_for_function("cadReview.getState().view.camera.zoom===1.3")
                before = page.evaluate("cadReview.getState().view")
                current.evaluate("drag={x:0,y:0,pan:false};draw()")
                page.wait_for_function("cadReview.getState().interacting.length>0")
                self.assertEqual(page.evaluate("p=>cadReview.load(p)", packet)["status"], "pending")
                self.assertEqual(page.evaluate("cadReview.apply()")["status"], "interaction_active")
                self.assertIn("wider", page.locator("#identity").inner_text())
                current.evaluate("drag=null;draw()")
                page.wait_for_function("cadReview.getState().interacting.length===0")
                self.assertEqual(page.evaluate("cadReview.apply()")["status"], "applied")
                current.wait_for_function("typeof initialized!=='undefined' && initialized && model.reviewIdentity===JSON.parse(document.getElementById('model').textContent).reviewIdentity")
                page.wait_for_function("cadReview.getState().revision.id==='widest'")
                self.assertEqual(page.evaluate("cadReview.getState().view.camera"), before["camera"])
                self.assertFalse(page.evaluate("cadReview.getState().view.visibility.plate"))
                bad = dict(packet, sha256="0"*64)
                with self.assertRaises(Error):
                    page.evaluate("p=>cadReview.load(p)", bad)
                self.assertIn("rejected", page.locator("#message").inner_text())
                page.reload()
                page.wait_for_function("cadReview.getState().blocked")
                self.assertIn("Blocked stale", page.locator("#identity").inner_text())
                page.locator("#front").click()
                page.reload()
                page.wait_for_function("cadReview.getState().blocked")
                self.assertEqual(page.frame(name="current").locator("canvas").count(), 0)
                self.assertFalse(errors, errors)
                self.assertFalse(remote, remote)
            finally:
                browser.close()
