import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_session as runner
from owned_process import OwnedProcess, WindowsJob, remaining


FAKE_CLI = r'''
import hashlib, json, os, pathlib, subprocess, sys, time
if "--version" in sys.argv:
    if pathlib.Path("scenario").is_file() and pathlib.Path("scenario").read_text()=="probe-stall":
        time.sleep(30)
    print("test-cli 1")
    raise SystemExit(0)
if "--resume" in sys.argv and "--trust-folder" in sys.argv:
    print("error: --trust-folder conflicts with --resume", file=sys.stderr)
    raise SystemExit(1)
def emit(kind, **data):
    print(json.dumps({"type":kind,"data":data}), flush=True)
workspace=pathlib.Path(sys.argv[sys.argv.index("-C")+1])
scenario=(workspace/"scenario").read_text()
if scenario=="startup":
    time.sleep(30)
emit("session.start",sessionId=sys.argv[sys.argv.index("--resume")+1] if "--resume" in sys.argv else "fake-session")
emit("user.message")
if scenario=="stall" and "--resume" not in sys.argv:
    emit("model.call_start")
    subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"])
    time.sleep(30)
if scenario=="tool":
    emit("tool.execution_start",toolCallId="long-tool")
    time.sleep(.6)
    emit("tool.execution_complete",toolCallId="long-tool")
if scenario=="error":
    raise SystemExit(7)
if scenario=="orphan":
    child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"],
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    (workspace/"child-pid").write_text(str(child.pid))
    raise SystemExit(0)
if scenario=="pipeline":
    emit("tool.execution_start",toolCallId="cad-pipeline")
    for script in ("model.py","validate.py"):
        subprocess.run([os.environ["CAD_VALIDATION_PYTHON"],script],cwd=workspace/"design",
                       stdout=subprocess.DEVNULL,check=True)
    emit("tool.execution_complete",toolCallId="cad-pipeline")
if scenario in ("previews","previews-open"):
    emit("tool.execution_start",toolCallId="exports")
    for build in ("first","second"):
        viewer,manifest=workspace/"viewer.html",workspace/"manifest.json"
        viewer.write_text(build);manifest.write_text("{}")
        from datetime import datetime, timezone
        marker={"run_id":os.environ["CADKIT_PREVIEW_RUN_ID"],"build_id":build,
                "stage":"preview_unvalidated","instances":6,"viewer":str(viewer),"manifest":str(manifest),
                "published_at":datetime.now(timezone.utc).isoformat(),
                "viewer_sha256":hashlib.sha256(viewer.read_bytes()).hexdigest(),
                "manifest_sha256":hashlib.sha256(manifest.read_bytes()).hexdigest()}
        pathlib.Path(os.environ["CADKIT_PREVIEW_FILE"]).write_text(json.dumps(marker))
        if scenario=="previews-open":
            time.sleep(.1)
            pathlib.Path(os.environ["CADKIT_PREVIEW_ACK_FILE"]).write_text(json.dumps({
                "run_id":marker["run_id"],"build_id":build,"opened_at":datetime.now(timezone.utc).isoformat()}))
        time.sleep(.25)
    emit("tool.execution_complete",toolCallId="exports")
usage=pathlib.Path(sys.argv[sys.argv.index("--usage-output-file")+1])
usage.write_text(json.dumps({"resumed":"--resume" in sys.argv,"prompt":sys.argv[sys.argv.index("-p")+1],
    "agent":sys.argv[sys.argv.index("--agent")+1] if "--agent" in sys.argv else None}))
emit("assistant.message",content="done")
'''


class RunnerTests(unittest.TestCase):
    def options(self, root, scenario):
        (root / "scenario").write_text(scenario)
        prompt = root / "request.txt"
        prompt.write_text("test")
        return runner.Options(root, prompt, root / "evidence", Path(sys.executable),
                              startup_timeout=.4, model_timeout=.2)

    def run_fake(self, root, scenario):
        fake = root / "fake_cli.py"
        fake.write_text(FAKE_CLI)
        options = self.options(root, scenario)
        with patch.object(runner, "find_cli", return_value=[sys.executable, str(fake)]):
            return runner.execute(options)

    def test_silent_model_is_resumed_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_fake(root, "stall")
            self.assertEqual(result["status"], "passed")
            self.assertEqual(len(result["attempts"]), 2)
            self.assertEqual(result["attempts"][0]["watchdog"], "model_silence_timeout")
            self.assertTrue(json.loads((root / "evidence" / "usage-2.json").read_text())["resumed"])

    def test_active_tool_is_not_mistaken_for_model_stall(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_fake(Path(directory), "tool")
            self.assertEqual(len(result["attempts"]), 1)
            self.assertIsNone(result["attempts"][0]["watchdog"])

    def test_startup_has_bounded_retry_and_explicit_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(RuntimeError):
                self.run_fake(root, "startup")
            report = json.loads((root / "evidence" / "run-summary.json").read_text())
            self.assertEqual(len(report["attempts"]), 2)
            self.assertTrue(all(item["watchdog"] == "startup_timeout" for item in report["attempts"]))

    def test_nonzero_cli_exit_is_not_retried_or_hidden(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(RuntimeError):
                self.run_fake(root, "error")
            report = json.loads((root / "evidence" / "run-summary.json").read_text())
            self.assertEqual(len(report["attempts"]), 1)
            self.assertEqual(report["attempts"][0]["exit_code"], 7)

    def test_version_probe_timeout_preserves_failure_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = self.options(root, "probe-stall")
            fake = root / "fake_cli.py"
            fake.write_text(FAKE_CLI)
            with patch.object(runner, "find_cli", return_value=[sys.executable, str(fake)]), patch.object(
                    runner, "PROBE_TIMEOUT", .05):
                with self.assertRaises(subprocess.TimeoutExpired):
                    runner.execute(options)
            report = json.loads((options.evidence / "run-summary.json").read_text())
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["failure_stage"], "cli_probe")
            self.assertEqual(report["error"]["type"], "TimeoutExpired")
            self.assertEqual(report["cleanup"]["status"], "verified")
            self.assertFalse(report["writer_blocked"])
            self.assertEqual(report["attempts"], [])

    def test_cleanup_error_is_recorded_once_and_never_resumed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "fake_cli.py"
            fake.write_text(FAKE_CLI)
            options = self.options(root, "startup")
            stop = OwnedProcess.stop

            def cleanup_error(owner, timeout=10):
                result = stop(owner, timeout)
                if "--version" in owner.process.args:
                    return result
                raise subprocess.TimeoutExpired("owned-process cleanup", -1)

            with patch.object(runner, "find_cli", return_value=[sys.executable, str(fake)]), patch.object(
                    OwnedProcess, "stop", autospec=True, side_effect=cleanup_error) as cleanup:
                with self.assertRaises(subprocess.TimeoutExpired):
                    runner.execute(options)
            self.assertEqual(cleanup.call_count, 2)  # One probe and one attempt, never repeated cleanup.
            report = json.loads((options.evidence / "run-summary.json").read_text())
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["failure_stage"], "attempt")
            self.assertEqual(report["failed_attempt"], 1)
            self.assertEqual(report["error"]["type"], "TimeoutExpired")
            self.assertEqual(report["primary_failure"]["type"], "WatchdogTimeout")
            self.assertEqual(report["cleanup"]["status"], "blocked")
            self.assertTrue(report["writer_blocked"])
            owned = json.loads((options.evidence / report["owned_process_file"]).read_text())
            self.assertGreater(owned["pid"], 0)
            self.assertEqual(owned["attempt"], 1)
            self.assertFalse((options.evidence / "attempt-2.jsonl").exists())
            blocked = self.options(root, "ok")
            blocked.evidence = root / "second-evidence"
            with patch.object(runner, "find_cli") as discovery, self.assertRaisesRegex(RuntimeError, "ownership"):
                runner.execute(blocked)
            discovery.assert_not_called()
            self.assertTrue((root / ".cad-runner-owner.json").is_file())

    def test_attempt_exception_retains_existing_preview_and_raw_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = self.options(root, "ok")
            preview = b'{"build_id":"useful-preview"}'
            raw = b'{"type":"model.call_failure"}\n'

            def fail_attempt(command, options, environment, number, resume_identity, *, lease):
                (options.evidence / "accepted-preview.json").write_bytes(preview)
                (options.evidence / "attempt-1.jsonl").write_bytes(raw)
                raise RuntimeError("Transport failed after preview")

            fake = root / "fake_cli.py"
            fake.write_text(FAKE_CLI)
            with patch.object(runner, "find_cli", return_value=[sys.executable, str(fake)]), patch.object(
                    runner, "run_attempt", side_effect=fail_attempt) as attempt:
                with self.assertRaisesRegex(RuntimeError, "Transport"):
                    runner.execute(options)
            self.assertEqual(attempt.call_count, 1)
            report = json.loads((options.evidence / "run-summary.json").read_text())
            self.assertEqual(report["accepted_preview_file"], "accepted-preview.json")
            self.assertEqual((options.evidence / "accepted-preview.json").read_bytes(), preview)
            self.assertEqual((options.evidence / "attempt-1.jsonl").read_bytes(), raw)

    def test_primary_error_survives_simultaneous_cleanup_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "fake_cli.py"
            fake.write_text(FAKE_CLI)
            options = self.options(root, "startup")
            stop = OwnedProcess.stop

            def cleanup_error(owner, timeout=10):
                result = stop(owner, timeout)
                if "--version" in owner.process.args:
                    return result
                raise subprocess.TimeoutExpired("injected cleanup", 10)

            with patch.object(runner, "find_cli", return_value=[sys.executable, str(fake)]), patch.object(
                    runner, "read_preview", side_effect=ValueError("Primary transport failure")), patch.object(
                    OwnedProcess, "stop", autospec=True, side_effect=cleanup_error):
                with self.assertRaisesRegex(ValueError, "Primary transport"):
                    runner.execute(options)
            report = json.loads((options.evidence / "run-summary.json").read_text())
            self.assertEqual(report["primary_failure"]["type"], "ValueError")
            self.assertEqual(report["cleanup"]["error"]["type"], "TimeoutExpired")
            self.assertEqual(len(report["attempts"]), 1)
            self.assertTrue(report["writer_blocked"])

    def test_keyboard_cancellation_verifies_cleanup_before_releasing_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "fake_cli.py"
            fake.write_text(FAKE_CLI)
            options = self.options(root, "startup")
            with patch.object(runner, "find_cli", return_value=[sys.executable, str(fake)]), patch.object(
                    runner, "read_preview", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    runner.execute(options)
            report = json.loads((options.evidence / "run-summary.json").read_text())
            self.assertEqual(report["primary_failure"]["type"], "KeyboardInterrupt")
            self.assertEqual(report["cleanup"]["status"], "verified")
            self.assertFalse(report["writer_blocked"])
            self.assertFalse((root / ".cad-runner-owner.json").exists())

    @unittest.skipUnless(os.name == "nt", "Windows job-object contract")
    def test_exited_parent_does_not_hide_an_active_descendant(self):
        sentinel = OwnedProcess()
        try:
            sentinel.start([sys._base_executable, "-c", "import time; time.sleep(30)"])
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with self.assertRaises(RuntimeError):
                    self.run_fake(root, "orphan")
                report = json.loads((root / "evidence" / "run-summary.json").read_text())
                attempt = report["attempts"][0]
                self.assertEqual(attempt["exit_code"], 0)
                self.assertEqual(attempt["primary_failure"]["type"], "LingeringDescendants")
                self.assertEqual(attempt["cleanup"]["containment"], "windows_job")
                self.assertGreaterEqual(attempt["cleanup"]["active_before"], 1)
                self.assertEqual(attempt["cleanup"]["active_after"], 0)
                self.assertEqual(len(report["attempts"]), 1)
                self.assertFalse((root / ".cad-runner-owner.json").exists())
                self.assertIsNone(sentinel.process.poll(), "Unrelated process must remain alive")
        finally:
            sentinel.stop()
            sentinel.close()

    @unittest.skipUnless(os.name == "nt", "Windows suspended launch")
    def test_job_assignment_failure_never_runs_an_uncontained_child(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "fake_cli.py"
            fake.write_text(FAKE_CLI)
            options = self.options(root, "ok")
            with patch.object(runner, "find_cli", return_value=[sys.executable, str(fake)]), patch.object(
                    WindowsJob, "attach", side_effect=OSError("Injected job assignment refusal")):
                with self.assertRaisesRegex(OSError, "assignment refusal"):
                    runner.execute(options)
            self.assertEqual((options.evidence / "probe-stdout.txt").read_bytes(), b"")
            report = json.loads((options.evidence / "run-summary.json").read_text())
            self.assertEqual(report["cleanup"]["status"], "verified")
            self.assertFalse((root / ".cad-runner-owner.json").exists())
            self.assertFalse((options.evidence / "attempt-1.jsonl").exists())

    @unittest.skipUnless(os.name == "nt", "Windows kill-on-close descendant containment")
    def test_closing_owner_handle_stops_descendants_without_parent_cooperation(self):
        import _winapi

        owner = OwnedProcess()
        child_handle = None
        try:
            with tempfile.TemporaryDirectory() as directory:
                marker = Path(directory) / "child"
                code = (
                    "import pathlib,subprocess,sys,time;"
                    "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(5)']);"
                    "target=pathlib.Path(sys.argv[1]);temp=target.with_suffix('.tmp');"
                    "temp.write_text(str(child.pid));temp.replace(target);time.sleep(5)"
                )
                owner.start([sys._base_executable, "-c", code, str(marker)])
                deadline = time.monotonic()+5
                while not marker.is_file() and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertTrue(marker.is_file(), "Owned fixture did not publish its child")
                child_handle = owner.job.check(owner.job.api.OpenProcess(
                    0x100000, False, int(marker.read_text())))
                owner.close()
                self.assertEqual(_winapi.WaitForSingleObject(child_handle, 1000), 0)
                owner.process.wait(timeout=5)
        finally:
            if owner.job.handle is not None:
                owner.stop()
                owner.close()
            if owner.process is not None:
                owner.process.wait(timeout=6)
            if child_handle is not None:
                _winapi.WaitForSingleObject(child_handle, 6000)
                owner.job.check(owner.job.api.CloseHandle(child_handle))

    @unittest.skipUnless(os.name == "nt", "Windows cleanup acknowledgement deadline")
    def test_unverified_native_job_exit_has_a_bounded_positive_timeout(self):
        owner = OwnedProcess()
        try:
            owner.start([sys._base_executable, "-c", "import time; time.sleep(5)"])
            with patch.object(owner.job, "active", return_value=1):
                with self.assertRaises(subprocess.TimeoutExpired) as failure:
                    owner.stop(timeout=.02)
            self.assertEqual(failure.exception.timeout, .02)
        finally:
            owner.stop()
            owner.close()

    @unittest.skipUnless(os.name == "nt", "Windows ownership setup timing")
    def test_native_ownership_setup_is_not_mistaken_for_cli_startup_stall(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "fake_cli.py"
            fake.write_text(FAKE_CLI)
            options = self.options(root, "ok")
            options.startup_timeout = 1
            resume = WindowsJob.resume

            def slow_resume(job, pid):
                time.sleep(1.1)
                resume(job, pid)

            with patch.object(runner, "find_cli", return_value=[sys.executable, str(fake)]), patch.object(
                    WindowsJob, "resume", autospec=True, side_effect=slow_resume):
                result = runner.execute(options)
            self.assertEqual(len(result["attempts"]), 1)
            self.assertIsNone(result["attempts"][0]["watchdog"])

    def test_changed_ownership_token_is_never_deleted_or_reported_as_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = self.options(root, "ok")
            options.evidence.mkdir()
            with self.assertRaisesRegex(RuntimeError, "ownership changed"):
                with runner.WriterLease(options):
                    (root / ".cad-runner-owner.json").write_text('{"token":"replaced"}')
                    (options.evidence / "run-summary.json").write_text('{"status":"passed"}')
            self.assertEqual(json.loads((root / ".cad-runner-owner.json").read_text())["token"], "replaced")
            report = json.loads((options.evidence / "run-summary.json").read_text())
            self.assertEqual(report["status"], "blocked")

    def test_workspace_ownership_blocks_even_a_new_evidence_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = self.options(root, "ok")
            owner = root / ".cad-runner-owner.json"
            original = b'{"token":"another-writer","state":"running_or_unverified"}'
            owner.write_bytes(original)
            with patch.object(runner, "find_cli") as discovery, self.assertRaisesRegex(RuntimeError, "ownership"):
                runner.execute(options)
            discovery.assert_not_called()
            self.assertEqual(owner.read_bytes(), original)
            report = json.loads((options.evidence / "run-summary.json").read_text())
            self.assertEqual(report["status"], "blocked")

    @unittest.skipUnless(os.name == "nt", "Installed CPython Windows timeout mechanism")
    def test_negative_displayed_timeout_can_be_an_expired_internal_wait_budget(self):
        owner = OwnedProcess()
        try:
            process = owner.start([sys._base_executable, "-c", "import os,time; os.close(1); os.close(2); time.sleep(5)"],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            with patch.object(process, "_remaining_time", side_effect=[1, 1, -.001]):
                with self.assertRaises(subprocess.TimeoutExpired) as failure:
                    process.communicate(timeout=1)
            self.assertEqual(failure.exception.timeout, -.001)
            self.assertEqual(owner.stop()["status"], "verified")
        finally:
            owner.stop()
            owner.close()

    def test_cleanup_remaining_budget_never_becomes_negative(self):
        self.assertEqual(remaining(0), 0)

    def test_progress_ignores_background_noise(self):
        options = runner.Options(Path("."), Path("."), Path("."), Path(sys.executable),
                                 startup_timeout=5, model_timeout=10)
        state = runner.Progress(0)
        state.accept({"type": "user.message", "data": {}}, 1)
        state.accept({"type": "session.background_tasks_changed", "data": {}}, 9)
        self.assertEqual(state.stalled(12, options), "model_silence_timeout")

    def test_existing_evidence_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = self.options(root, "tool")
            options.evidence.mkdir()
            with self.assertRaises(FileExistsError):
                runner.execute(options)

    def test_explicit_continuation_delivers_new_request_not_stall_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "fake_cli.py"
            fake.write_text(FAKE_CLI)
            options = self.options(root, "ok")
            options.resume_session = "00000000-0000-4000-8000-000000000001"
            options.no_ask_user = True
            with patch.object(runner, "find_cli", return_value=[sys.executable, str(fake)]):
                result = runner.execute(options)
            usage = json.loads((options.evidence / "usage-1.json").read_text())
            self.assertTrue(usage["resumed"])
            self.assertEqual(usage["prompt"], "test")
            self.assertEqual(result["resumed_session"], options.resume_session)
            self.assertEqual(result["attempts"][0]["session_id"], options.resume_session)

    def test_invalid_continuation_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = self.options(root, "ok")
            options.resume_session = "not-a-session-uuid"
            with self.assertRaises(ValueError):
                runner.execute(options)

    def test_custom_agent_selection_is_forwarded_on_fresh_and_resumed_turns(self):
        for resumed in (False, True):
            with self.subTest(resumed=resumed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fake = root / "fake_cli.py"
                fake.write_text(FAKE_CLI)
                options = self.options(root, "ok")
                options.agent = "cad-designer"
                if resumed:
                    options.resume_session = "00000000-0000-4000-8000-000000000001"
                with patch.object(runner, "find_cli", return_value=[sys.executable, str(fake)]):
                    result = runner.execute(options)
                usage = json.loads((options.evidence / "usage-1.json").read_text())
                self.assertEqual(usage["agent"], "cad-designer")
                self.assertEqual(result["agent"], "cad-designer")

    def test_invalid_agent_identifier_is_rejected_before_creating_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = self.options(root, "ok")
            options.agent = "--allow-all"
            with self.assertRaisesRegex(ValueError, "Agent"):
                runner.execute(options)
            self.assertFalse(options.evidence.exists())

    def test_later_preview_does_not_overwrite_first_preview_timing(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_fake(Path(directory), "previews")
            attempt = result["attempts"][0]
            self.assertEqual(attempt["preview"]["build_id"], "first")
            self.assertEqual(attempt["latest_preview"]["build_id"], "second")
            self.assertEqual(result["first_preview_seconds"], attempt["preview"]["noticed_seconds"])
            self.assertLess(result["first_preview_seconds"], attempt["latest_preview"]["noticed_seconds"])

    def test_preview_requires_fresh_nonce_scoped_paths_and_matching_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            viewer = root / "viewer.html"
            manifest = root / "manifest.json"
            viewer.write_text("viewer")
            manifest.write_text("{}")
            marker = root / "preview-ready.json"
            data = {
                "run_id": "current", "build_id": "build", "stage": "preview_unvalidated",
                "instances": 6, "viewer": str(viewer), "manifest": str(manifest),
                "viewer_sha256": hashlib.sha256(viewer.read_bytes()).hexdigest(),
                "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            }
            marker.write_text(json.dumps(data))
            self.assertIsNone(runner.read_preview(marker, root, "stale"))
            self.assertIsNone(runner.read_preview(marker, root, "current", expected_instances=17))
            self.assertIsNone(runner.read_preview(marker, root, "current", expected_output=root / "other"))
            self.assertEqual(runner.read_preview(marker, root, "current")["build_id"], "build")
            self.assertIsNone(runner.read_preview(marker, root, "current", seen_build="build"))
            with self.assertRaisesRegex(ValueError, "escapes"):
                runner.read_preview(marker, root / "approved-subfolder", "current")
            revision = {"id": "next", "brief_sha256": "source"}
            manifest.write_text(json.dumps({"revision": revision}))
            data["manifest_sha256"] = hashlib.sha256(manifest.read_bytes()).hexdigest()
            marker.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "revision"):
                runner.read_preview(marker, root, "current")
            data["revision"] = revision
            marker.write_text(json.dumps(data))
            self.assertEqual(runner.read_preview(marker, root, "current")["revision"], revision)
            viewer.write_text("changed")
            with self.assertRaisesRegex(ValueError, "hash"):
                runner.read_preview(marker, root, "current")


if __name__ == "__main__":
    unittest.main()
