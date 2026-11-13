"""Validated brief revisions and generated handoff evidence, not an approval authority."""

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re


IDENTIFIER = r"[A-Za-z0-9][A-Za-z0-9_.-]*"
STATUSES = ("measured", "confirmed", "assumed", "estimated")
REVISION_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "CAD brief revision metadata",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "schema_version": {"const": 1, "type": "integer"},
        "id": {"type": "string", "pattern": "^"+IDENTIFIER+"$"},
        "parent_id": {"type": ["string", "null"]},
        "ancestors": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        "delta": {"type": "string", "minLength": 1},
        "preserve": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        "dependencies": {"type": "object", "additionalProperties": {
            "type": "array", "items": {"type": "string"}, "uniqueItems": True}},
        "superseded_facts": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["name", "revision_id", "fact"],
            "properties": {"name": {"type": "string"}, "revision_id": {"type": "string"},
                           "fact": {"$ref": "#/$defs/fact"}}}},
        "open_decisions": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        "user_approval": {"anyOf": [{"type": "null"}, {
            "type": "object", "additionalProperties": False,
            "required": ["revision_id", "stage", "source"],
            "properties": {key: {"type": "string", "minLength": 1}
                           for key in ("revision_id", "stage", "source")}}]},
    },
    "$defs": {"fact": {
        "type": "object", "required": ["value", "unit", "status", "source"],
        "properties": {"value": {"type": "number"}, "unit": {"type": "string", "minLength": 1},
                       "status": {"enum": list(STATUSES)},
                       "source": {"type": "string", "minLength": 1}}}},
}
REVISION_SCHEMA["required"] = list(REVISION_SCHEMA["properties"])
REVISION_SCHEMA["properties"]["superseded_decisions"] = {
    "type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["name", "revision_id", "decision", "replaced_by", "source"],
        "properties": {
            "name": {"type": "string"}, "revision_id": {"type": "string"},
            "decision": {"type": "object"}, "replaced_by": {"type": "string"},
            "source": {"type": "string", "minLength": 1},
        },
    },
}


def canonical(data):
    try:
        return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError) as error:
        raise ValueError("Revision data must contain finite JSON-compatible values") from error


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")


def identifier(value, label):
    if not isinstance(value, str) or re.fullmatch(IDENTIFIER, value) is None:
        raise ValueError(f"{label} must be a revision identifier")


def strings(value, label):
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    for item in value:
        text(item, label)
    if len(set(value)) != len(value):
        raise ValueError(f"{label} must not contain duplicates")


def fact(value, label):
    if not isinstance(value, dict) or not {"value", "unit", "status", "source"} <= value.keys():
        raise ValueError(f"{label} requires value, unit, status and source")
    if type(value["value"]) not in (int, float) or not math.isfinite(value["value"]):
        raise ValueError(f"{label}.value must be a finite number, not a bool")
    text(value["unit"], f"{label}.unit")
    text(value["source"], f"{label}.source")
    if value["status"] not in STATUSES:
        raise ValueError(f"{label}.status must be one of {STATUSES}")


def validate_decisions(decisions):
    if not isinstance(decisions, dict):
        raise ValueError("Brief decisions must be an object")
    for name, decision in decisions.items():
        identifier(name, "Decision id")
        if not isinstance(decision, dict) or set(decision) != {
                "status", "blocks_modeling", "selected_option", "source"}:
            raise ValueError(f"Decision {name} requires status, blocks_modeling, selected_option and source")
        if decision["status"] not in ("awaiting_choice", "selected", "delegated"):
            raise ValueError(f"Decision {name} has an unsupported status")
        if type(decision["blocks_modeling"]) is not bool:
            raise ValueError(f"Decision {name}.blocks_modeling must be a bool")
        text(decision["source"], f"Decision {name}.source")
        if decision["status"] == "awaiting_choice":
            if decision["selected_option"] is not None:
                raise ValueError(f"Awaiting decision {name} cannot already select an option")
        else:
            text(decision["selected_option"], f"Decision {name}.selected_option")


def validate_deliverable(deliverable):
    if not isinstance(deliverable, dict) or set(deliverable) != {
            "status", "target", "outputs", "sequence", "source"}:
        raise ValueError("Deliverable requires status, target, outputs, sequence and source")
    if deliverable["status"] not in ("awaiting_choice", "selected", "delegated"):
        raise ValueError("Unsupported deliverable status")
    text(deliverable["source"], "Deliverable source")
    for name in ("outputs", "sequence"):
        strings(deliverable[name], f"Deliverable {name}")
    if deliverable["status"] == "awaiting_choice":
        if deliverable["target"] is not None:
            raise ValueError("Awaiting deliverable cannot already select a target")
    else:
        text(deliverable["target"], "Immediate deliverable target")
        if not deliverable["outputs"] or not deliverable["sequence"]:
            raise ValueError("Selected deliverable requires outputs and work sequence")


def require_modeling_ready(brief):
    """Block known unresolved geometry decisions, not ordinary nonblocking questions."""
    validate_brief(brief)
    if brief.get("deliverable", {}).get("status") == "awaiting_choice":
        raise ValueError("Unresolved immediate deliverable; ask one question and wait before modeling")
    blocked = [name for name, decision in brief.get("decisions", {}).items()
               if decision["blocks_modeling"] and decision["status"] == "awaiting_choice"]
    if blocked:
        raise ValueError("Unresolved modeling decisions: "+", ".join(blocked)+
                         "; show lightweight alternatives, ask one question and wait")


def validate_brief(brief):
    """Validate opt-in revision metadata; legacy briefs explicitly remain untracked."""
    if not isinstance(brief, dict):
        raise ValueError("Brief must be an object")
    validate_decisions(brief.get("decisions", {}))
    if "deliverable" in brief:
        validate_deliverable(brief["deliverable"])
    if "revision" not in brief:
        return None
    revision = brief["revision"]
    if (not isinstance(revision, dict)
            or not set(REVISION_SCHEMA["required"]) <= revision.keys()
            or not revision.keys() <= REVISION_SCHEMA["properties"].keys()):
        raise ValueError("Revision must contain exactly the versioned schema fields")
    if type(revision["schema_version"]) is not int or revision["schema_version"] != 1:
        raise ValueError("Revision schema_version must be integer1")
    identifier(revision["id"], "Revision id")
    strings(revision["ancestors"], "Revision ancestors")
    for ancestor in revision["ancestors"]:
        identifier(ancestor, "Ancestor")
    if revision["id"] in revision["ancestors"]:
        raise ValueError("Revision cannot be its own ancestor")
    expected_parent = revision["ancestors"][-1] if revision["ancestors"] else None
    if revision["parent_id"] != expected_parent:
        raise ValueError("Revision parent_id must be the last ancestor, or null for an initial revision")
    text(revision["delta"], "Revision delta")
    for key in ("preserve", "open_decisions"):
        strings(revision[key], f"Revision {key}")
    for key in ("name", "intent", "stage", "coordinate_system"):
        text(brief.get(key), f"Brief {key}")
    dimensions = brief.get("dimensions")
    if not isinstance(dimensions, dict) or not dimensions:
        raise ValueError("Tracked brief requires sourced dimensions")
    for name, value in dimensions.items():
        text(name, "Dimension name")
        fact(value, f"Dimension {name}")
    dependencies = revision["dependencies"]
    if not isinstance(dependencies, dict) or not dependencies.keys() <= dimensions.keys():
        raise ValueError("Revision dependencies must refer to current dimension names")
    for name, features in dependencies.items():
        strings(features, f"Dependencies of {name}")
    if not isinstance(revision["superseded_facts"], list):
        raise ValueError("superseded_facts must be a list")
    seen = set()
    for entry in revision["superseded_facts"]:
        if not isinstance(entry, dict) or set(entry) != {"name", "revision_id", "fact"}:
            raise ValueError("Superseded fact requires name, revision_id and fact")
        text(entry["name"], "Superseded fact name")
        if entry["revision_id"] not in revision["ancestors"]:
            raise ValueError("Superseded facts must reference an ancestor revision")
        key = (entry["name"], entry["revision_id"])
        if key in seen:
            raise ValueError("Duplicate superseded fact for a revision")
        seen.add(key)
        fact(entry["fact"], f"Superseded {entry['name']}")
    history = revision.get("superseded_decisions", [])
    if not isinstance(history, list):
        raise ValueError("superseded_decisions must be a list")
    seen, redirects = set(), {}
    for entry in history:
        if not isinstance(entry, dict) or set(entry) != {
                "name", "revision_id", "decision", "replaced_by", "source"}:
            raise ValueError("Superseded decision requires name, revision_id, decision, replaced_by and source")
        identifier(entry["name"], "Superseded decision name")
        identifier(entry["replaced_by"], "Replacement decision id")
        text(entry["source"], "Supersession source")
        validate_decisions({entry["name"]: entry["decision"]})
        if entry["revision_id"] not in revision["ancestors"]:
            raise ValueError("Superseded decisions must reference an ancestor revision")
        key = (entry["name"], entry["revision_id"])
        if key in seen:
            raise ValueError("Duplicate superseded decision for a revision")
        seen.add(key)
        redirects[entry["name"]] = entry["replaced_by"]
    for entry in history:
        target, visited = entry["replaced_by"], set()
        while target not in brief.get("decisions", {}):
            if target in visited or target not in redirects:
                raise ValueError("Superseded decision must resolve to a current replacement")
            visited.add(target)
            target = redirects[target]
    approval = revision["user_approval"]
    if approval is not None:
        if not isinstance(approval, dict) or set(approval) != {"revision_id", "stage", "source"}:
            raise ValueError("User approval requires revision_id, stage and source evidence")
        for key in approval:
            text(approval[key], f"User approval {key}")
        if approval["revision_id"] not in [*revision["ancestors"], revision["id"]]:
            raise ValueError("User approval must refer to the current revision or an ancestor")
        if approval["revision_id"] == revision["id"] and approval["stage"] != brief["stage"]:
            raise ValueError("Current user approval must identify the current design stage")
    canonical(brief)
    return revision


def make_snapshot(brief):
    revision = validate_brief(brief)
    if revision is None:
        return None
    payload = canonical(brief)
    identity = {"schema_version": 1, "id": revision["id"], "parent_id": revision["parent_id"],
                "brief_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest()}
    return {"schema_version": 1, "identity": identity, "brief": json.loads(payload)}


def validate_snapshot(snapshot):
    if (not isinstance(snapshot, dict) or set(snapshot) != {"schema_version", "identity", "brief"}
            or type(snapshot["schema_version"]) is not int or snapshot["schema_version"] != 1):
        raise ValueError("Invalid revision snapshot schema")
    expected = make_snapshot(snapshot["brief"])
    if expected is None or canonical(expected) != canonical(snapshot):
        raise ValueError("Revision snapshot identity/hash does not match its brief")
    return snapshot["identity"]


def advance_revision(brief, revision_id, delta, *, updates=None, preserve=(),
                     dependencies=None, open_decisions=None, brief_updates=None):
    previous = validate_brief(brief)
    if previous is None:
        raise ValueError("Adopt an initial revision explicitly before advancing a legacy brief")
    identifier(revision_id, "New revision id")
    if revision_id in [*previous["ancestors"], previous["id"]]:
        raise ValueError("New revision id must not reuse an existing revision")
    if updates is not None and not isinstance(updates, dict):
        raise ValueError("Dimension updates must be an object")
    if (not isinstance(preserve, (list, tuple))
            or open_decisions is not None and not isinstance(open_decisions, (list, tuple))):
        raise ValueError("Preserve and open_decisions must be lists or tuples")
    result = deepcopy(brief)
    revision = result["revision"]
    revision.update(id=revision_id, parent_id=previous["id"],
                    ancestors=[*previous["ancestors"], previous["id"]], delta=delta,
                    preserve=list(preserve))
    if open_decisions is not None:
        revision["open_decisions"] = list(open_decisions)
    if dependencies is not None:
        revision["dependencies"] = deepcopy(dependencies)
    if brief_updates is not None:
        if not isinstance(brief_updates, dict) or not brief_updates or not set(brief_updates) <= {
                "intent", "deliverable", "assumptions", "decisions", "retire_decisions", "open_decisions"}:
            raise ValueError("Brief updates allow only intent, deliverable, assumptions, decisions, retire_decisions and open_decisions")
        def archive_decision(name, replacement, source):
            revision.setdefault("superseded_decisions", []).append({
                "name": name, "revision_id": previous["id"],
                "decision": deepcopy(brief["decisions"][name]),
                "replaced_by": replacement, "source": source,
            })
        for name, value in brief_updates.items():
            if name in preserve:
                raise ValueError(f"Cannot change preserved brief field {name}")
            if name == "decisions":
                validate_decisions(value)
                decisions = result.setdefault("decisions", {})
                for decision_id, decision in sorted(value.items()):
                    if "decisions" in preserve or f"decisions.{decision_id}" in preserve:
                        raise ValueError(f"Cannot change preserved decision {decision_id}")
                    if decision_id in decisions and (
                            decisions[decision_id]["blocks_modeling"] and
                            not decision["blocks_modeling"]):
                        raise ValueError("Cannot clear a decision's modeling block; record selection or delegation")
                    if decision_id in decisions and decisions[decision_id] != decision:
                        archive_decision(decision_id, decision_id, decision["source"])
                    decisions[decision_id] = deepcopy(decision)
            elif name == "retire_decisions":
                continue
            elif name == "deliverable":
                validate_deliverable(value)
                result[name] = deepcopy(value)
            elif name == "open_decisions":
                if open_decisions is not None:
                    raise ValueError("Supply open_decisions only once")
                strings(value, "Updated open_decisions")
                revision["open_decisions"] = deepcopy(value)
            elif name == "assumptions":
                strings(value, "Updated assumptions")
                result[name] = deepcopy(value)
            else:
                text(value, "Updated intent")
                result[name] = value
        retired = brief_updates.get("retire_decisions", {})
        if not isinstance(retired, dict):
            raise ValueError("retire_decisions must be an object")
        for name, retirement in sorted(retired.items(), key=lambda item: str(item[0])):
            identifier(name, "Retired decision id")
            if "decisions" in preserve or f"decisions.{name}" in preserve:
                raise ValueError(f"Cannot retire preserved decision {name}")
            if name not in brief.get("decisions", {}) or name in brief_updates.get("decisions", {}):
                raise ValueError("Retire only an existing decision not also updated in this revision")
            if not isinstance(retirement, dict) or set(retirement) != {"replaced_by", "source"}:
                raise ValueError("Decision retirement requires replaced_by and source")
            target = retirement["replaced_by"]
            identifier(target, "Replacement decision id")
            text(retirement["source"], "Supersession source")
            if target == name or target in retired or target not in result.get("decisions", {}):
                raise ValueError("Retired decision requires a current, non-retired replacement")
            if (brief["decisions"][name]["blocks_modeling"]
                    and result["decisions"][target]["status"] == "awaiting_choice"):
                raise ValueError("Retiring a blocking decision requires selection or delegation")
            archive_decision(name, target, retirement["source"])
            del result["decisions"][name]
    for name, value in sorted((updates or {}).items(), key=lambda item: str(item[0])):
        fact(value, f"Updated {name}")
        current = brief["dimensions"].get(name)
        if current == value:
            continue
        if name in preserve or f"dimensions.{name}" in preserve or "dimensions" in preserve:
            raise ValueError(f"Cannot change preserved dimension {name}")
        if current is not None:
            revision["superseded_facts"].append(
                {"name": name, "revision_id": previous["id"], "fact": deepcopy(current)})
        result["dimensions"][name] = deepcopy(value)
    # Prior approval retains its original revision ID; advancing never approves the new revision.
    validate_brief(result)
    return result


def restore_snapshot(snapshot, destination):
    validate_snapshot(snapshot)
    destination = Path(destination)
    with destination.open("x", encoding="utf-8") as output:
        output.write(json.dumps(snapshot["brief"], indent=2, allow_nan=False)+"\n")
    return destination


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def retire_qualification(output, reason):
    """Keep exact prior evidence, but remove a qualification that is no longer current."""
    from .preview import write_json

    output = Path(output)
    state = output / "incremental-state.json"
    last = output / "incremental-last.json"
    if not state.exists() and (not last.exists() or
            json.loads(last.read_text(encoding="utf-8")).get("status") not in ("validated", "verified", "failed")):
        return
    evidence = []
    for path in (state, last, output / "manifest.json", output / "validation.json"):
        if not path.exists():
            continue
        content = path.read_bytes()
        archive = output / "qualification-history" / (
            hashlib.sha256(content).hexdigest()+"-"+path.name)
        archive.parent.mkdir(parents=True, exist_ok=True)
        if archive.exists():
            if archive.read_bytes() != content:
                raise ValueError(f"Qualification history conflicts with preserved evidence: {archive}")
        else:
            with archive.open("xb") as file:
                file.write(content)
        evidence.append(archive.relative_to(output).as_posix())
    write_json(last, {"event": "cadkit.revision_handoff", "status": "invalidated",
                      "reason": reason, "evidence": evidence})
    if state.exists():
        state.unlink()


def check_publication(snapshot, previous, current):
    """Prevent tracked-state downgrade, revision reuse and accidental backwards publication."""
    old = previous.get("revision")
    if old is None:
        return
    if snapshot is None:
        raise ValueError("Cannot overwrite a tracked export with an untracked source")
    identity = validate_snapshot(snapshot)
    if not isinstance(old, dict) or not {"id", "brief_sha256"} <= old.keys():
        raise ValueError("Prior tracked export has invalid revision identity")
    if old["id"] == identity["id"]:
        if old != identity:
            raise ValueError("Revision id reused for a different brief; advance the revision")
        previous_files = previous.get("files_sha256")
        if not isinstance(previous_files, dict):
            raise ValueError("Prior tracked export is missing file hashes")
        for name in set(previous_files) | set(current["files_sha256"]):
            if name.startswith(("parts/", "assembled/")) and previous_files.get(name) != current["files_sha256"].get(name):
                raise ValueError("Geometry changed without advancing the revision")
    elif old["id"] not in snapshot["brief"]["revision"]["ancestors"]:
        raise ValueError("Cannot overwrite a newer or unrelated tracked revision")


def verify_export(snapshot, output, *, require_validation=False):
    output = Path(output).resolve()
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if snapshot is None:
        if manifest.get("revision") is not None or require_validation:
            raise ValueError("Tracked revision required; source/export tracking is incompatible")
        return {"status": "untracked"}
    identity = validate_snapshot(snapshot)
    if manifest.get("revision") != identity:
        raise ValueError("Incompatible source/export revision identity or brief hash")
    saved = json.loads((output / "revision-state.json").read_text(encoding="utf-8"))
    if validate_snapshot(saved) != identity or canonical(saved) != canonical(snapshot):
        raise ValueError("Exported revision snapshot is stale")
    required = {"assembly.glb", "viewer.html", "revision-state.json"}
    if "review" in manifest:
        if manifest["review"] != {"schema_version": 1, "html": "review.html", "state": "review-state.json"}:
            raise ValueError("Unsupported review artifact metadata")
        required.update({"review.html", "review-state.json"})
    for folder, entries in (("parts", manifest["parts"]), ("assembled", manifest["instances"])):
        for entry in entries:
            identifier(entry["id"], "Export part/instance id")
            name = f"{folder}/{entry['id']}.stl"
            if entry["stl"] != name:
                raise ValueError("Unexpected revision export path")
            required.add(name)
    if manifest.get("viewer", {}).get("backend") == "embedded":
        from .embedded import ASSET_NAMES
        required.update({"viewer-scene.json", "viewer-assets/assets.json"})
        required.update("viewer-assets/"+name for name in ASSET_NAMES)
    hashes = manifest.get("files_sha256")
    if not isinstance(hashes, dict) or set(hashes) != required:
        raise ValueError("Tracked manifest must hash the complete generated file set")
    for name, expected in hashes.items():
        relative = PurePosixPath(name)
        target = (output / name).resolve()
        if relative.is_absolute() or ".." in relative.parts or not target.is_relative_to(output):
            raise ValueError("Revision export path escapes output")
        if not isinstance(expected, str) or sha256(target) != expected:
            raise ValueError(f"Revision export hash mismatch: {name}")
    if require_validation:
        report = json.loads((output / "validation.json").read_text(encoding="utf-8"))
        if (report.get("status") not in ("passed", "geometry_passed_browser_not_run")
                or report.get("revision") != identity
                or report.get("exports", {}).get("manifest_sha256") != sha256(manifest_path)):
            raise ValueError("Validation report is failed or stale for this revision/export")
    return {"status": "tracked", "identity": identity}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("schema")
    for name in ("check", "snapshot", "restore", "verify"):
        command = commands.add_parser(name)
        command.add_argument("source", type=Path)
        if name in ("snapshot", "restore", "verify"):
            command.add_argument("destination", type=Path)
        if name == "verify":
            command.add_argument("--validated", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "schema":
            result = REVISION_SCHEMA
        else:
            data = json.loads(args.source.read_text(encoding="utf-8"))
            if args.command == "restore":
                result = {"restored": str(restore_snapshot(data, args.destination))}
            else:
                snapshot = make_snapshot(data)
                if snapshot is None:
                    raise ValueError("Brief is untracked; adopt revision metadata explicitly")
                if args.command == "snapshot":
                    with args.destination.open("x", encoding="utf-8") as output:
                        json.dump(snapshot, output, indent=2, allow_nan=False)
                    result = snapshot["identity"]
                elif args.command == "verify":
                    result = verify_export(snapshot, args.destination, require_validation=args.validated)
                else:
                    result = {"identity": snapshot["identity"], "revision": data["revision"],
                              "dimensions": data["dimensions"], "coordinate_system": data["coordinate_system"]}
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Revision state failed: {error}\n")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
