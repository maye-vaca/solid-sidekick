"""Publish fresh unvalidated exports; optionally wait for the host to open them."""

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time
import uuid

from .timing import stage


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def export_preview(builder, output, *, viewer_backend="lightweight", viewer_assets=None,
                   previous_output=None, brief_path=None):
    """Invalidate readiness before building; return (Assembly, resolved output Path)."""
    from .revision import make_snapshot, require_modeling_ready, validate_snapshot
    expected = None
    if brief_path is not None:
        brief = json.loads(Path(brief_path).read_text(encoding="utf-8"))
        require_modeling_ready(brief)
        expected = make_snapshot(brief)
    output = Path(output).expanduser().resolve()
    marker = output / "preview-ready.json"
    expected_output = os.environ.get("CADKIT_PREVIEW_OUTPUT")
    notify_host = not expected_output or output == Path(expected_output).resolve()
    notification = Path(os.environ.get("CADKIT_PREVIEW_FILE", marker)) if notify_host else marker
    for path in {marker, notification}:
        if path.exists():
            path.unlink()
    with stage("geometry") as geometry:
        assembly = builder()
        if brief_path is not None and assembly.revision != expected:
            raise ValueError("Preview model did not bind the checked brief")
        if assembly.revision is not None:
            validate_snapshot(assembly.revision)
            require_modeling_ready(assembly.revision["brief"])
    with stage("export") as export:
        result = assembly.export(output, viewer_backend=viewer_backend, viewer_assets=viewer_assets,
                                 previous_output=previous_output)
    data = {
        "schema_version": 1, "stage": "preview_unvalidated",
        "run_id": os.environ.get("CADKIT_PREVIEW_RUN_ID", uuid.uuid4().hex),
        "build_id": uuid.uuid4().hex, "published_at": utc_now(),
        "viewer": str(result / ("review.html" if assembly.revision is not None else "viewer.html")),
        "manifest": str(result / "manifest.json"),
        "viewer_sha256": sha256(result / ("review.html" if assembly.revision is not None else "viewer.html")),
        "manifest_sha256": sha256(result / "manifest.json"),
        "parts": len(assembly.parts), "instances": len(assembly.instances),
        "timings": {"geometry_seconds": geometry["elapsed_seconds"], "export_seconds": export["elapsed_seconds"]},
    }
    if assembly.revision is not None:
        from .revision import validate_snapshot
        data["revision"] = validate_snapshot(assembly.revision)
    if viewer_backend == "embedded":
        paths = [result / "viewer-scene.json"] + sorted((result / "viewer-assets").iterdir())
        data["viewer_files_sha256"] = {path.relative_to(result).as_posix(): sha256(path) for path in paths}
    write_json(marker, data)
    if notification != marker:
        write_json(notification, data)
    print(json.dumps({"event": "cadkit.preview_ready", "stage": data["stage"],
                      "viewer": data["viewer"], "build_id": data["build_id"]}), flush=True)
    return assembly, result


def wait_for_ack(output):
    ack_file = os.environ.get("CADKIT_PREVIEW_ACK_FILE")
    expected_output = os.environ.get("CADKIT_PREVIEW_OUTPUT")
    if not ack_file or (expected_output and Path(output).resolve() != Path(expected_output).resolve()):
        return {"status": "host_open_not_requested"}
    marker = json.loads((Path(output) / "preview-ready.json").read_text(encoding="utf-8"))
    if marker.get("run_id") != os.environ.get("CADKIT_PREVIEW_RUN_ID"):
        raise ValueError("Preview marker belongs to a different run")
    limit = float(os.environ.get("CADKIT_PREVIEW_TIMEOUT", "60"))
    if not math.isfinite(limit) or limit <= 0:
        raise ValueError("Preview acknowledgement timeout must be finite and positive")
    deadline = time.monotonic()+limit
    while time.monotonic() < deadline:
        if Path(ack_file).is_file():
            ack = json.loads(Path(ack_file).read_text(encoding="utf-8"))
            if (ack.get("run_id"), ack.get("build_id")) == (marker["run_id"], marker["build_id"]):
                opened = datetime.fromisoformat(ack["opened_at"])
                if opened < datetime.fromisoformat(marker["published_at"]):
                    raise ValueError("Host opening predates this preview")
                if (sha256(marker["viewer"]), sha256(marker["manifest"])) != (
                    marker["viewer_sha256"], marker["manifest_sha256"]
                ):
                    raise ValueError("Preview changed before host acknowledgement")
                for relative, expected in marker.get("viewer_files_sha256", {}).items():
                    if sha256(Path(output) / relative) != expected:
                        raise ValueError(f"Preview companion changed before host acknowledgement: {relative}")
                return {"status": "opened_unvalidated", "build_id": marker["build_id"],
                        "published_at": marker["published_at"], "host_opened_at": ack["opened_at"]}
        time.sleep(.05)
    raise ValueError("Preview exported but host did not acknowledge opening it before validation")
