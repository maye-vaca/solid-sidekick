"""Observed stage spans; timings are evidence, not validation or user approval."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import time
import uuid


@contextmanager
def stage(name):
    started = time.perf_counter()
    span = {"schema_version": 1, "event": "cadkit.stage", "stage": name,
            "span_id": uuid.uuid4().hex, "run_id": os.environ.get("CADKIT_PREVIEW_RUN_ID"),
            "started_at_unix": time.time()}

    def emit(status, **extra):
        destination = os.environ.get("CADKIT_STAGE_FILE")
        if destination:
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as output:
                output.write(json.dumps({**span, "status": status, **extra}, allow_nan=False)+"\n")

    emit("started")
    try:
        yield span
    except BaseException as error:
        span["elapsed_seconds"] = time.perf_counter()-started
        try:
            emit("failed", elapsed_seconds=span["elapsed_seconds"], error_type=type(error).__name__)
        except OSError as timing_error:
            error.add_note(f"Stage evidence also failed: {timing_error}")
        raise
    else:
        span["elapsed_seconds"] = time.perf_counter()-started
        emit("passed", elapsed_seconds=span["elapsed_seconds"])
