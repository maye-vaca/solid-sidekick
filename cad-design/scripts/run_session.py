"""Run Copilot CLI with scoped isolation, progress deadlines and one safe resume."""

import argparse
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid

from owned_process import OwnedProcess


DISABLED_SERVERS = ("workiq", "ado", "mail", "computer-use")
PROBE_TIMEOUT = 15
MODEL_PROGRESS = {
    "model.call_start", "model.call_finished", "model.call_failure",
    "assistant.message_delta", "assistant.reasoning_delta", "assistant.tool_call_delta",
    "assistant.message", "assistant.turn_start", "assistant.turn_end", "assistant.turn_retry",
}


@dataclass
class Options:
    workspace: Path
    prompt_file: Path
    evidence: Path
    python: Path
    browser: Path | None = None
    cli: Path | None = None
    name: str = "CAD design"
    startup_timeout: float = 60
    model_timeout: float = 120
    retries: int = 1
    await_preview: bool = False
    preview_instances: int | None = None
    preview_output: Path | None = None
    resume_session: str | None = None
    no_ask_user: bool = False
    agent: str | None = None


def read_preview(path, workspace, run_id, seen_build=None, expected_instances=None, expected_output=None):
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("run_id") != run_id or data.get("build_id") == seen_build:
        return None
    if expected_instances is not None and data.get("instances") != expected_instances:
        return None
    if expected_output is not None and Path(data["viewer"]).resolve().parent != expected_output:
        return None
    if data.get("stage") != "preview_unvalidated" or not data.get("build_id"):
        raise ValueError("Invalid preview readiness marker")
    import hashlib
    for key in ("viewer", "manifest"):
        target = Path(data[key]).resolve(strict=True)
        if not target.is_relative_to(workspace):
            raise ValueError("Preview path escapes the approved workspace")
        if hashlib.sha256(target.read_bytes()).hexdigest() != data[key+"_sha256"]:
            raise ValueError("Preview hash does not match the published export")
    manifest = json.loads(Path(data["manifest"]).read_text(encoding="utf-8"))
    if data.get("revision") != manifest.get("revision"):
        raise ValueError("Preview/source export revision identities do not match")
    return data


def find_cli(explicit=None):
    if explicit is not None:
        candidates = [Path(explicit)]
    else:
        candidates = []
        if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
            candidates.append(Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "WinGet" / "Links" / "copilot.exe")
        found = shutil.which("copilot")
        if found:
            candidates.append(Path(found))
    for candidate in candidates:
        if candidate.is_file():
            return [str(candidate.resolve())]
    raise FileNotFoundError("Standalone Copilot CLI not found; supply --cli with its executable path")


def error_record(error):
    return {"type": type(error).__name__, "message": str(error)}


def persist_result(path, data, primary=None):
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as error:
        if primary is not None:
            primary.add_note(f"Could not persist failure evidence: {error}")
            raise primary from error
        raise


class WriterLease:
    def __init__(self, options):
        self.path = options.workspace / ".cad-runner-owner.json"
        self.evidence = options.evidence
        self.token = uuid.uuid4().hex
        self.safe = True

    def __enter__(self):
        try:
            with self.path.open("x", encoding="utf-8") as output:
                json.dump({"token": self.token, "runner_pid": os.getpid(),
                           "started_at_unix": time.time(), "evidence": str(self.evidence),
                           "state": "running_or_unverified"}, output, indent=2)
        except FileExistsError as error:
            message = f"Workspace writer ownership is unresolved; inspect {self.path}. No CLI was started."
            (self.evidence / "run-summary.json").write_text(json.dumps({
                "status": "blocked", "failure_stage": "writer_ownership",
                "error": {"type": "WriterBlocked", "message": message},
                "writer_blocked": True, "attempts": [],
            }, indent=2), encoding="utf-8")
            raise RuntimeError(message) from error
        return self

    def __exit__(self, kind, error, traceback):
        if self.safe:
            try:
                if json.loads(self.path.read_text(encoding="utf-8")).get("token") != self.token:
                    raise RuntimeError("Workspace writer ownership changed; lock was not removed")
                self.path.unlink()
            except (OSError, ValueError, RuntimeError) as release_error:
                self.safe = False
                try:
                    summary_path = self.evidence / "run-summary.json"
                    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
                    summary.update(status="blocked", failure_stage="writer_ownership_release",
                                   writer_blocked=True, ownership_release_error=error_record(release_error))
                    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
                except (OSError, ValueError) as report_error:
                    release_error.add_note(f"Could not persist ownership-release failure: {report_error}")
                if error is None:
                    raise
                error.add_note(f"Writer ownership release also failed: {release_error}")


def finish_owner(owner, lease):
    """Keep cleanup failures separate; release ownership only after verification."""
    failure = None
    try:
        cleanup = owner.stop()
    except BaseException as error:
        failure = error
        cleanup = {"status": "blocked", **owner.identity(), "error": error_record(error)}
    try:
        owner.close()
    except BaseException as error:
        cleanup["status"] = "blocked"
        cleanup["close_error"] = error_record(error)
        if failure is None:
            failure = error
    lease.safe = cleanup["status"] == "verified"
    return cleanup, failure


def probe_cli(prefix, options, environment, lease):
    owner = OwnedProcess()
    primary = None
    try:
        with (options.evidence / "probe-stdout.txt").open("xb") as output, (
                options.evidence / "probe-stderr.txt").open("xb") as error:
            lease.safe = False
            process = owner.start([*prefix, "--no-auto-update", "--version"], env=environment,
                                  stdout=output, stderr=error, cwd=options.workspace)
            (options.evidence / "process-probe.json").write_text(
                json.dumps(owner.identity(), indent=2), encoding="utf-8")
            process.wait(timeout=PROBE_TIMEOUT)
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, process.args)
    except BaseException as error:
        primary = error
    finally:
        cleanup, cleanup_error = finish_owner(owner, lease)
    if primary is None and cleanup.get("active_before"):
        primary = RuntimeError("CLI version probe left active descendants")
    persist_result(options.evidence / "probe-result.json", {
        "primary_failure": error_record(primary) if primary else None, "cleanup": cleanup,
    }, primary or cleanup_error)
    if primary is not None:
        raise primary
    if cleanup_error is not None:
        raise cleanup_error
    text = (options.evidence / "probe-stdout.txt").read_text(encoding="utf-8")
    if not text.strip():
        raise RuntimeError("CLI version probe returned no version")
    return text.strip().splitlines()[0]


class Progress:
    def __init__(self, now, session_id=None):
        self.started = self.last_model = now
        self.prompt_ready = None
        self.session_id = session_id
        self.active_tools = set()
        self.activity = []
        self.open_activity = {}

    def accept(self, event, now):
        kind, data = event.get("type"), event.get("data", {})
        if not isinstance(data, dict):
            return
        categories = {
            "model.call_start": ("model_activity", True), "model.call_finished": ("model_activity", False),
            "model.call_failure": ("model_activity", False),
            "tool.execution_start": ("tool_execution", True), "tool.execution_complete": ("tool_execution", False),
            "session.compaction_start": ("compaction", True), "session.compaction_complete": ("compaction", False),
        }
        if kind in categories:
            category, opening = categories[kind]
            identity = data.get("toolCallId") if category == "tool_execution" else (
                data.get("modelCallId") or data.get("requestId") or category)
            key = (category, identity)
            if opening:
                if key in self.open_activity:
                    self.activity.append({"stage": category, "status": "incomplete",
                                          "started_seconds": self.open_activity[key]-self.started})
                self.open_activity[key] = now
            elif key in self.open_activity:
                start = self.open_activity.pop(key)
                self.activity.append({"stage": category, "status": "observed",
                                      "started_seconds": max(0, start-self.started),
                                      "elapsed_seconds": max(0, now-start)})
        if kind == "session.start":
            self.session_id = data.get("sessionId")
        if kind in ("user.message", "assistant.turn_start") and self.prompt_ready is None:
            self.prompt_ready = now
            self.last_model = now
        if kind in MODEL_PROGRESS or kind == "tool.execution_complete":
            self.last_model = now
        if kind == "tool.execution_start":
            self.active_tools.add(data.get("toolCallId"))
        elif kind == "tool.execution_complete":
            self.active_tools.discard(data.get("toolCallId"))

    def stalled(self, now, options):
        if self.prompt_ready is None and now-self.started > options.startup_timeout:
            return "startup_timeout"
        if self.prompt_ready is not None and not self.active_tools and now-self.last_model > options.model_timeout:
            return "model_silence_timeout"
        return None

    def timings(self):
        spans = self.activity+[{"stage": category, "status": "incomplete",
                                "started_seconds": max(0, start-self.started)}
                               for (category, _), start in self.open_activity.items()]
        return {name: {"status": "observed" if any(s["stage"] == name for s in spans) else "not_observed",
                       "spans": [s for s in spans if s["stage"] == name]}
                for name in ("model_activity", "tool_execution", "compaction")}


def pipeline_timings(path, run_id):
    names = ("geometry", "export", "preview_ack", "validation_rebuild", "project_checks",
             "export_checks", "interference_checks", "browser_checks", "validation", "validation_report", "packaging",
             "incremental")
    pending, finished, ignored = {}, [], 0
    try:
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                item = json.loads(line)
                if not isinstance(item, dict):
                    raise ValueError("Stage evidence must be JSON objects")
                if item.get("run_id") != run_id:
                    ignored += 1
                    continue
                if item.get("event") != "cadkit.stage" or item.get("stage") not in names:
                    raise ValueError("Unknown stage evidence")
                if item["status"] == "started":
                    pending[item["span_id"]] = item
                elif item["status"] in ("passed", "failed"):
                    if (item["span_id"] not in pending or type(item.get("elapsed_seconds")) not in (int, float)
                            or not math.isfinite(item["elapsed_seconds"]) or item["elapsed_seconds"] < 0):
                        raise ValueError("Unpaired or invalid completed stage")
                    pending.pop(item["span_id"])
                    finished.append(item)
                else:
                    raise ValueError("Invalid stage outcome")
    except (OSError, ValueError, KeyError) as error:
        return {"status": "invalid_evidence", "error": error_record(error)}
    return {"status": "observed" if finished or pending else "not_observed", "ignored_other_run_records": ignored,
            "stages": {name: [s for s in finished if s["stage"] == name] for name in names},
            "incomplete": list(pending.values()),
            "limit": "Overlapping/nested spans are not additive; missing instrumentation is not zero time."}


def run_attempt(command, options, environment, number, resume_identity=None, *, lease):
    started = time.monotonic()
    progress = Progress(started, resume_identity or options.resume_session)
    events = queue.Queue()
    preview = None
    first_preview = None
    first_open = None
    primary = None
    reader = None
    reader_errors = []
    reason = None
    owner = OwnedProcess()
    output_path = options.evidence / f"attempt-{number}.jsonl"
    with output_path.open("xb") as output, (
        options.evidence / f"attempt-{number}-stderr.txt"
    ).open("xb") as error:
        def read_output():
            try:
                for line in process.stdout:
                    output.write(line)
                    output.flush()
                    try:
                        events.put((json.loads(line), time.monotonic()))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # Preserve non-protocol output in the raw log; it is not progress.
                        continue
            except (OSError, ValueError) as error:
                reader_errors.append(error)
            finally:
                process.stdout.close()

        try:
            lease.safe = False
            process = owner.start(command, cwd=options.workspace, env=environment,
                                  stdout=subprocess.PIPE, stderr=error)
            progress = Progress(time.monotonic(), resume_identity or options.resume_session)
            reader = threading.Thread(target=read_output, daemon=True)
            reader.start()
            with (options.evidence / f"process-{number}.json").open("x", encoding="utf-8") as info:
                json.dump({**owner.identity(), "attempt": number,
                           "started_at_unix": time.time(),
                           "resume_session": resume_identity or options.resume_session}, info, indent=2)
            while process.poll() is None:
                if reader_errors:
                    raise reader_errors[0]
                try:
                    event, observed_at = events.get(timeout=.1)
                    if isinstance(event, dict):
                        progress.accept(event, observed_at)
                except queue.Empty:
                    pass
                fresh = read_preview(
                    Path(environment["CADKIT_PREVIEW_FILE"]), options.workspace,
                    environment["CADKIT_PREVIEW_RUN_ID"],
                    preview["build_id"] if preview else None, options.preview_instances, options.preview_output,
                )
                if fresh:
                    preview = {**fresh, "attempt": number, "noticed_seconds": time.monotonic()-started,
                               "orchestration_seconds": time.monotonic()-float(
                                   environment.get("CADKIT_TIMING_ORIGIN", started))}
                    if first_preview is None:
                        first_preview = preview
                    (options.evidence / "accepted-preview.json").write_text(
                        json.dumps(preview, indent=2), encoding="utf-8")
                    print(json.dumps({"event": "preview_ready", "stage": preview["stage"],
                                      "viewer": preview["viewer"]}), flush=True)
                ack_path = environment.get("CADKIT_PREVIEW_ACK_FILE")
                if first_open is None and preview and ack_path and Path(ack_path).is_file():
                    ack = json.loads(Path(ack_path).read_text(encoding="utf-8"))
                    if (ack.get("run_id"), ack.get("build_id")) == (
                            environment["CADKIT_PREVIEW_RUN_ID"], preview["build_id"]):
                        from datetime import datetime
                        if datetime.fromisoformat(ack["opened_at"]) < datetime.fromisoformat(preview["published_at"]):
                            raise ValueError("Host opening predates preview publication")
                        first_open = {"status": "host_reported_open", "build_id": ack["build_id"],
                                      "opened_at": ack["opened_at"], "noticed_seconds": time.monotonic()-started,
                                      "orchestration_seconds": time.monotonic()-float(
                                          environment.get("CADKIT_TIMING_ORIGIN", started))}
                reason = progress.stalled(time.monotonic(), options)
                if reason:
                    break
        except BaseException as error:
            primary = error
        finally:
            cleanup, cleanup_error = finish_owner(owner, lease)
            if reader is not None:
                try:
                    reader.join(timeout=5)
                except BaseException as error:
                    lease.safe = False
                    cleanup["status"] = "blocked"
                    cleanup["reader_error"] = error_record(error)
                    if primary is None:
                        primary = error
        if reader is not None and reader.is_alive():
            lease.safe = False
            cleanup["status"] = "blocked"
            cleanup["reader_error"] = {"type": "RuntimeError", "message": "Owned output reader did not stop"}
            if primary is None:
                primary = RuntimeError("CLI output reader remained active after cleanup")
        elif reader_errors and primary is None:
            primary = reader_errors[0]
        while not events.empty():
            event, observed_at = events.get_nowait()
            if isinstance(event, dict):
                progress.accept(event, observed_at)
    process = owner.process
    unexpected = primary is None and reason is None and bool(cleanup.get("active_before"))
    failure = error_record(primary) if primary else (
        {"type": "WatchdogTimeout", "message": reason} if reason else (
            {"type": "LingeringDescendants", "message": "CLI exited with active owned descendants"}
            if unexpected else (
                {"type": "CLIExit", "message": f"CLI exit code {process.returncode}"}
                if process is not None and process.returncode else None)))
    result = {
        "attempt": number, "exit_code": process.returncode if process else None, "watchdog": reason,
        "primary_failure": failure, "cleanup": cleanup, "unexpected_descendants": unexpected,
        "session_id": progress.session_id,
        "elapsed_seconds": time.monotonic()-started,
        "startup_seconds": None if progress.prompt_ready is None else progress.prompt_ready-progress.started,
        "usage_file": f"usage-{number}.json",
        "preview": first_preview, "latest_preview": preview,
        "first_visible_preview": first_open or {"status": "not_observed"},
        "timings": {**progress.timings(), "ownership_setup_seconds": max(0, progress.started-started),
                    "cleanup": cleanup},
    }
    persist_result(options.evidence / f"attempt-{number}-result.json", result, primary or cleanup_error)
    if primary is not None:
        raise primary
    if cleanup_error is not None:
        raise cleanup_error
    return result


def execute(options):
    if (not all(math.isfinite(value) and value > 0
                for value in (options.startup_timeout, options.model_timeout)) or options.retries not in (0, 1)):
        raise ValueError("Deadlines must be positive; retries must be zero or one")
    if options.agent is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", options.agent):
        raise ValueError("Agent must be a custom-agent file identifier, such as cad-designer")
    options.workspace = options.workspace.resolve(strict=True)
    if options.resume_session is not None:
        options.resume_session = str(uuid.UUID(options.resume_session))
    options.prompt_file = options.prompt_file.resolve(strict=True)
    options.python = options.python.resolve(strict=True)
    options.evidence = options.evidence.absolute()
    options.evidence.mkdir(parents=True, exist_ok=False)
    if options.preview_output is not None:
        options.preview_output = (options.workspace / options.preview_output).resolve()
        if not options.preview_output.is_relative_to(options.workspace):
            raise ValueError("Requested preview output must be inside the approved workspace")
    with WriterLease(options) as lease:
        return execute_owned(options, lease)


def execute_owned(options, lease):
    environment = os.environ.copy()
    environment.update(
        COPILOT_PLUGIN_DIR_ONLY="true", COPILOT_AUTO_UPDATE="false",
        CAD_VALIDATION_PYTHON=str(options.python),
        CADKIT_PREVIEW_FILE=str(options.evidence / "preview-ready.json"),
        CADKIT_PREVIEW_RUN_ID=uuid.uuid4().hex,
        CADKIT_STAGE_FILE=str(options.evidence / "stages.jsonl"),
    )
    environment.pop("CADKIT_PREVIEW_ACK_FILE", None)
    environment.pop("CADKIT_PREVIEW_OUTPUT", None)
    if options.preview_output is not None:
        environment["CADKIT_PREVIEW_OUTPUT"] = str(options.preview_output)
    if options.await_preview:
        environment["CADKIT_PREVIEW_ACK_FILE"] = str(options.evidence / "preview-opened.json")
    if options.browser:
        environment["CADKIT_BROWSER"] = str(options.browser.resolve(strict=True))
    started = time.monotonic()
    orchestration_started = started
    environment["CADKIT_TIMING_ORIGIN"] = str(orchestration_started)
    probe_seconds = None
    version = None
    attempts, resume_id = [], options.resume_session

    def timings():
        return {"overall_seconds": time.monotonic()-orchestration_started,
                "cli_probe_seconds": probe_seconds,
                "pipeline": pipeline_timings(options.evidence / "stages.jsonl", environment["CADKIT_PREVIEW_RUN_ID"])}

    def record_failure(stage, error, number=None):
        context = error.__context__
        summary = {
            "status": "failed", "failure_stage": stage, "failed_attempt": number,
            "error": error_record(error), "writer_blocked": not lease.safe,
            "cli_version": version, "elapsed_seconds": time.monotonic()-started,
            "attempts": attempts, "resumed_session": options.resume_session, "agent": options.agent,
            "accepted_preview_file": "accepted-preview.json"
            if (options.evidence / "accepted-preview.json").is_file() else None,
            "owned_process_file": f"process-{number}.json"
            if number is not None and (options.evidence / f"process-{number}.json").is_file() else None,
            "limits": "Cleanup evidence is separate from CLI completion and artifact validity. Blocked ownership prohibits another writer; no automatic retry after exceptions.",
            "timings": timings(),
            "first_ready_orchestration_seconds": next((
                item["preview"]["orchestration_seconds"] for item in attempts if item["preview"]), None),
        }
        result_path = options.evidence / (f"attempt-{number}-result.json" if number else "probe-result.json")
        if result_path.is_file():
            detail = json.loads(result_path.read_text(encoding="utf-8"))
            summary["primary_failure"] = detail.get("primary_failure") or error_record(error)
            summary["cleanup"] = detail["cleanup"]
            if number is not None:
                summary["attempts"] = [*attempts, detail]
        summary["first_ready_orchestration_seconds"] = next((
            item["preview"]["orchestration_seconds"] for item in summary["attempts"]
            if item.get("preview")), None)
        if context is not None:
            summary["error"]["context"] = {"type": type(context).__name__, "message": str(context)}
        persist_result(options.evidence / "run-summary.json", summary, error)

    try:
        prefix = find_cli(options.cli)
        version = probe_cli(prefix, options, environment, lease)
        probe_seconds = time.monotonic()-started
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        record_failure("cli_probe", error)
        raise
    recovering = False
    started = time.monotonic()
    for number in range(1, options.retries+2):
        prompt = options.prompt_file.read_text(encoding="utf-8") if not recovering else (
            "The previous model stream stalled. Continue the same CAD task. First inspect "
            "completed files and validation state; reuse them. Do not recreate an existing "
            "project, overwrite user edits, rerun completed checks unnecessarily or expand scope."
        )
        command = [
            *prefix, "-C", str(options.workspace), "-p", prompt,
            "--add-dir", str(options.python.parent.parent),
            "--allow-tool=write", "--allow-tool=shell", "--deny-tool=task",
            "--disable-builtin-mcps", "--no-auto-update",
            "--output-format=json", "--stream=on", "--no-color",
            "--usage-output-file", str(options.evidence / f"usage-{number}.json"),
            "--log-dir", str(options.evidence / "cli-logs"),
        ]
        command += [f"--disable-mcp-server={name}" for name in DISABLED_SERVERS]
        if options.no_ask_user:
            command.append("--no-ask-user")
        if options.agent:
            command += ["--agent", options.agent]
        command += ["--resume", resume_id] if resume_id else ["--trust-folder", "--name", options.name]
        try:
            result = run_attempt(command, options, environment, number, resume_id, lease=lease)
            if options.resume_session and result["session_id"] != options.resume_session:
                raise RuntimeError("CLI continuation returned a different session identity")
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, KeyboardInterrupt) as error:
            record_failure("attempt", error, number)
            raise
        attempts.append(result)
        summary = {
            "status": "passed" if result["exit_code"] == 0 and not result["primary_failure"]
            and result["cleanup"]["status"] == "verified" else "failed",
            "cli_version": version, "elapsed_seconds": time.monotonic()-started,
            "attempts": attempts,
            "resumed_session": options.resume_session,
            "agent": options.agent,
            "timings": timings(),
            "first_visible_preview": next(({
                **item["first_visible_preview"],
                "noticed_seconds": sum(p["elapsed_seconds"] for p in attempts[:index])+
                item["first_visible_preview"]["noticed_seconds"]}
                for index, item in enumerate(attempts)
                if item["first_visible_preview"]["status"] == "host_reported_open"), {"status": "not_observed"}),
            "first_ready_orchestration_seconds": next((
                item["preview"]["orchestration_seconds"] for item in attempts if item["preview"]), None),
            "first_preview_seconds": next((
                sum(previous["elapsed_seconds"] for previous in attempts[:index])+item["preview"]["noticed_seconds"]
                for index, item in enumerate(attempts) if item["preview"]), None),
        }
        (options.evidence / "run-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        if summary["status"] == "passed":
            return summary
        if not result["watchdog"]:
            break
        if result["startup_seconds"] is not None and not result["session_id"]:
            break
        recovering = result["startup_seconds"] is not None
        resume_id = result["session_id"] if recovering else options.resume_session
    raise RuntimeError(f"CLI evaluation failed; inspect {options.evidence / 'run-summary.json'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("workspace", "prompt-file", "evidence", "python"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--cli", type=Path)
    parser.add_argument("--browser", type=Path)
    parser.add_argument("--name", default="CAD design")
    parser.add_argument("--startup-timeout", type=float, default=60)
    parser.add_argument("--model-timeout", type=float, default=120)
    parser.add_argument("--retries", type=int, choices=(0, 1), default=1)
    parser.add_argument("--await-preview", action="store_true", help="Require a host-open acknowledgement before deep validation")
    parser.add_argument("--preview-instances", type=int, help="Expose only the expected requested-assembly instance count")
    parser.add_argument("--preview-output", type=Path, help="Scope host notifications/gate to this workspace-relative output")
    parser.add_argument("--resume-session", help="Continue this exact session UUID with the supplied new prompt")
    parser.add_argument("--no-ask-user", action="store_true", help="Use reply-based clarification in noninteractive evaluation")
    parser.add_argument("--agent", help="Select a repository custom-agent file identifier; otherwise use the host default")
    args = parser.parse_args()
    try:
        result = execute(Options(**vars(args)))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"CAD CLI runner failed: {error}\n")
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
