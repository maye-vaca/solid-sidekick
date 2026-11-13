"""Advance, rebuild and validate a tracked project without installing or packaging."""

import argparse
from contextlib import contextmanager
import hashlib
import importlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import uuid

from .preview import export_preview, write_json
from .revision import (
    advance_revision, canonical, make_snapshot, require_modeling_ready,
    retire_qualification, sha256, verify_export,
)
from .timing import stage
from .validation import require


def source_binding(root):
    paths = set(root.glob("*.py")) | set((root / "cadkit").rglob("*.py"))
    paths.add(root / "requirements.txt")
    return {"files": {p.relative_to(root).as_posix(): sha256(p) for p in sorted(paths)},
            "python": str(Path(sys.executable).resolve()), "python_version": sys.version,
            "packages": {name: version(name) for name in ("manifold3d", "numpy", "trimesh")}}


@contextmanager
def writer(root):
    path = root / ".cadkit-revision-owner.json"
    token = uuid.uuid4().hex
    with path.open("x", encoding="utf-8") as lock:
        lock.write(token)
    primary = None
    try:
        yield
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            require(path.read_text(encoding="utf-8") == token,
                    "Revision writer token changed; refusing to remove another owner's lock")
            path.unlink()
        except (OSError, ValueError) as error:
            if primary is not None:
                primary.add_note(f"Revision writer cleanup also failed: {error}")
            else:
                raise


def affected_scope(brief, updates, manifest):
    parts, transforms = set(), set()
    known_parts = {p["id"] for p in manifest["parts"]}
    known_instances = {p["id"] for p in manifest["instances"]}
    for name in updates:
        require(name in brief["dimensions"], "Scalar tier cannot introduce dimensions")
        targets = brief["revision"]["dependencies"].get(name)
        require(bool(targets), f"Scalar correction {name} has no declared dependency scope")
        for target in targets:
            path = target.split(".")
            require(len(path) >= 2, f"Unsupported dependency target: {target}")
            if path[0] == "parts" and path[1] in known_parts:
                parts.add(path[1])
            elif path[0] == "instances" and path[1] in known_instances:
                transforms.add(path[1])
            else:
                raise ValueError(f"Unknown dependency target: {target}")
    return {"parts": sorted(parts), "transforms": sorted(transforms),
            "instances": sorted(transforms | {i["id"] for i in manifest["instances"] if i["part_id"] in parts})}


def check_scalar_scope(assembly, manifest, baseline, scope):
    local, _ = assembly.meshes()
    require(set(local) == {p["id"] for p in manifest["parts"]} and
            {i.id for i in assembly.instances} == {i["id"] for i in manifest["instances"]},
            "Scalar tier cannot change physical part or instance IDs; use topology tier")
    for old in manifest["parts"]:
        if old["id"] not in scope["parts"]:
            part = assembly.parts[old["id"]]
            data = local[part.id].export(file_type="stl_ascii").encode("utf-8")
            require(hashlib.sha256(data).hexdigest() == sha256(baseline / old["stl"]),
                    f"Unlisted physical geometry changed: {part.id}")
            require(all(old[k] == getattr(part, k) for k in ("name", "color", "material", "notes")) and
                    old.get("visual_regions", []) == [r.record() for r in part.visual_regions],
                    f"Unlisted finish or metadata changed: {part.id}")
    by_id = {i.id: i for i in assembly.instances}
    for old in manifest["instances"]:
        item = by_id[old["id"]]
        require(item.part_id == old["part_id"], "Scalar tier cannot reassign instance part IDs")
        if item.id not in scope["transforms"]:
            require(canonical(item.placement.matrix().tolist()) == canonical(old["transform_mm"]),
                    f"Unlisted placement changed: {item.id}")


def validate(output, browser, assembly_provider):
    from .validation import main as validate_main
    original = sys.argv
    try:
        sys.argv = ["validate.py", "--output", str(output)]
        if browser:
            sys.argv += ["--browser", str(browser)]
        try:
            validate_main(_assembly_provider=assembly_provider)
        except SystemExit as error:
            report = json.loads((output / "validation.json").read_text(encoding="utf-8"))
            raise ValueError(f"Shared validation failed: {report.get('error', str(error))}") from error
    finally:
        sys.argv = original


def qualified_baseline(snapshot, output, binding, *, require_same_source):
    verify_export(snapshot, output, require_validation=True)
    qualified = json.loads((output / "incremental-state.json").read_text(encoding="utf-8"))
    require(type(qualified.get("schema_version")) is int and qualified["schema_version"] == 1 and
            qualified["revision"] == snapshot["identity"] and
            qualified["manifest_sha256"] == sha256(output / "manifest.json") and
            qualified["validation_sha256"] == sha256(output / "validation.json"),
            "Qualified baseline is stale; qualify the current source and exports first")
    if require_same_source:
        require(qualified["source_binding"] == binding,
                "Model/checks/toolkit/environment changed; use topology tier and full checks")


def execute(args):
    root = Path.cwd().resolve()
    for name in ("model.py", "checks.py", "design_brief.json"):
        require((root / name).is_file(), "Run this command from the CAD project root")
    output = args.output.resolve()
    baseline = (getattr(args, "previous_output", None) or args.output).resolve()
    state_path = output / "incremental-state.json"
    brief_path = root / "design_brief.json"
    with writer(root):
        source_bytes = brief_path.read_bytes()
        brief = json.loads(source_bytes)
        snapshot = make_snapshot(brief)
        require(snapshot is not None, "Incremental work requires an explicitly tracked brief")
        binding = source_binding(root)
        if args.command == "verify":
            qualified_baseline(snapshot, output, binding, require_same_source=True)
            result = {"event": "cadkit.revision_handoff", "status": "verified",
                      "revision": snapshot["identity"], "packaged": False,
                      "validation_status": json.loads((output / "validation.json").read_text())["status"],
                      "review_page": (output / "review.html").as_uri(),
                      "review_packet": str(output / "review-state.json"),
                      "review_packet_sha256": sha256(output / "review-state.json"),
                      "panel_action": "verification only; no panel update performed"}
            if args.include_packet:
                packet_bytes = (output / "review-state.json").read_bytes()
                require(hashlib.sha256(packet_bytes).hexdigest() == result["review_packet_sha256"],
                        "Review packet changed during handoff")
                result["review_packet_data"] = json.loads(packet_bytes)
                qualified_baseline(snapshot, output, source_binding(root), require_same_source=True)
                require(make_snapshot(json.loads(brief_path.read_text(encoding="utf-8"))) == snapshot,
                        "Brief changed during handoff")
                result["panel_action"] = "load review_packet_data into the current panel; stage pending, do not auto-apply"
            return result
        scope, updates, prior_manifest = None, {}, None
        if args.command == "revise":
            if args.recover:
                require(args.tier != "scalar", "Recovery requires topology/final tier and full browser checks")
                failed = json.loads((output / "incremental-last.json").read_text(encoding="utf-8"))
                require(failed.get("status") == "failed" and failed.get("revision") == snapshot["identity"],
                        "Recovery requires failure evidence for the current brief")
                prior = json.loads((baseline / "revision-state.json").read_text(encoding="utf-8"))
                verify_export(prior, baseline)
                require(prior["identity"] == snapshot["identity"] or
                        prior["identity"]["id"] in brief["revision"]["ancestors"],
                        "Recovery baseline must be the current failed revision or an intact ancestor")
            else:
                qualified_baseline(snapshot, baseline, binding, require_same_source=args.tier == "scalar")
            prior_manifest = json.loads((baseline / "manifest.json").read_text(encoding="utf-8"))
            if args.tier != "scalar":
                require(bool(args.browser), "Topology/final tiers require an explicit browser check")
            updates = json.loads(args.updates.read_text(encoding="utf-8")) if args.updates else {}
            require(isinstance(updates, dict), "Updates must be a dimension-to-sourced-fact object")
            dependencies = json.loads(args.dependencies.read_text(encoding="utf-8")) if args.dependencies else None
            require(not args.dependencies or isinstance(dependencies, dict),
                    "Dependencies must be a complete dimension-to-feature-map object")
            brief_path_updates = getattr(args, "brief_updates", None)
            brief_updates = json.loads(brief_path_updates.read_text(encoding="utf-8")) if brief_path_updates else None
            require(brief_updates is None or isinstance(brief_updates, dict),
                    "Brief updates must be an object")
            if args.tier == "scalar":
                require(dependencies is None, "Dependency-map changes require topology/final tier")
                require(not brief_updates or not {"decisions", "intent"} & brief_updates.keys(),
                        "Decision/intent changes require topology/final tier")
                require(bool(updates), "Scalar revision requires an explicit sourced correction")
                scope = affected_scope(brief, updates, prior_manifest)
            revised = advance_revision(brief, args.revision, args.delta,
                                       updates=updates, preserve=args.preserve, dependencies=dependencies,
                                       brief_updates=brief_updates)
        else:
            revised = brief
        # Admission failures must not retire or overwrite the accepted handoff.
        require_modeling_ready(revised)
        expected = make_snapshot(revised)
        try:
            retire_qualification(output, "Rebuilding qualification; no checked handoff exists until checks finish")
            require(brief_path.read_bytes() == source_bytes, "Brief changed before revision admission")
            if args.command == "revise":
                write_json(brief_path, revised)
            model = importlib.import_module("model")

            def build():
                assembly = model.build()
                require(assembly.revision == expected, "Model did not bind the current brief snapshot")
                if scope is not None:
                    check_scalar_scope(assembly, prior_manifest, baseline, scope)
                if prior_manifest is not None and output == baseline:
                    require({p["id"] for p in prior_manifest["parts"]} <= set(assembly.parts) and
                            {i["id"] for i in prior_manifest["instances"]} <= {i.id for i in assembly.instances},
                            "Part/instance removal needs a new --output and --previous-output baseline")
                return assembly

            manifest = prior_manifest or (
                json.loads((output / "manifest.json").read_text(encoding="utf-8"))
                if (output / "manifest.json").is_file() else {})
            backend = manifest.get("viewer", {}).get("backend", "lightweight")
            assets = baseline / "viewer-assets" if backend == "embedded" else None
            assembly, _ = export_preview(build, output, viewer_backend=backend, viewer_assets=assets,
                                         previous_output=baseline if prior_manifest is not None else None,
                                         brief_path=brief_path)

            def checked_assembly():
                # The acknowledgement wait can admit external writes after export.
                with stage("validation_source_guard"):
                    require(make_snapshot(json.loads(brief_path.read_text(encoding="utf-8"))) == expected,
                            "Brief changed before revision validation")
                    require(source_binding(root) == binding,
                            "Source or environment changed before revision validation")
                    require(assembly.revision == expected, "Exported assembly snapshot changed")
                return assembly

            validate(output, args.browser, checked_assembly)
            require(make_snapshot(json.loads(brief_path.read_text(encoding="utf-8"))) == expected,
                    "Brief changed during revision checks")
            require(source_binding(root) == binding, "Source or environment changed during revision checks")
            verify_export(expected, output, require_validation=True)
            state = {"schema_version": 1, "revision": expected["identity"], "source_binding": binding,
                     "manifest_sha256": sha256(output / "manifest.json"),
                     "validation_sha256": sha256(output / "validation.json")}
            write_json(state_path, state)
            result = {"event": "cadkit.revision_handoff", "status": "validated",
                      "validation_status": json.loads((output / "validation.json").read_text())["status"],
                      "revision": expected["identity"], "tier": getattr(args, "tier", "qualification"),
                      "recovery": bool(getattr(args, "recover", False)),
                      "affected": scope, "execution": "full conservative rebuild and all geometry/export/project checks",
                      "review_packet": str(output / "review-state.json"),
                      "review_packet_sha256": sha256(output / "review-state.json"),
                      "review_page": (output / "review.html").as_uri(),
                      "panel_action": "load packet into the current review panel; stage pending, do not auto-apply",
                      "packaged": False}
            write_json(output / "incremental-last.json", result)
            return result
        except BaseException as error:
            try:
                if state_path.exists():
                    retire_qualification(output, "Revision checks or handoff failed")
                write_json(output / "validation.json", {"status": "failed", "error": str(error)})
                write_json(output / "incremental-last.json",
                           {"status": "failed", "error": str(error), "revision": expected["identity"],
                            "note": "The advanced brief is retained for diagnosis; no qualified handoff exists."})
            except (OSError, ValueError) as evidence_error:
                error.add_note(f"Failure evidence also could not be written: {evidence_error}")
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("qualify", "revise", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--output", type=Path, default=Path("output"))
        if name != "verify":
            command.add_argument("--browser", type=Path, default=os.environ.get("CADKIT_BROWSER"))
        else:
            command.add_argument("--include-packet", action="store_true",
                                 help="Include the checked review packet for the host to stage; does not update a panel")
        if name == "revise":
            command.add_argument("--previous-output", type=Path)
            command.add_argument("--recover", action="store_true",
                                 help="Advance a recorded failed revision; topology/final and intact exports required")
            command.add_argument("--revision", required=True)
            command.add_argument("--delta", required=True)
            command.add_argument("--updates", type=Path)
            command.add_argument("--brief-updates", type=Path,
                                 help="Checked intent/assumptions/decision/open-decision updates; no identity or approval fields")
            command.add_argument("--dependencies", type=Path,
                                 help="Complete replacement dependency map; topology/final tiers only")
            command.add_argument("--preserve", action="append", default=[])
            command.add_argument("--tier", choices=("scalar", "topology", "final"), default="scalar")
    args = parser.parse_args()
    try:
        with stage("incremental"):
            result = execute(args)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, json.dumps({"status": "failed", "error": str(error)})+"\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
