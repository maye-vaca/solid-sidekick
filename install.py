"""Install one verified CAD skill and a thin host adapter without overwriting user work."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys


ROOT = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def relative_path(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError(f"Invalid package-relative path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in value.split("/")):
        raise ValueError(f"Invalid package-relative path: {value!r}")
    return Path(*path.parts)


def check_path(path):
    """Reject links/reparse points, including existing ancestors."""
    for candidate in (*reversed(path.parents), path):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            raise ValueError(f"Links and reparse points are not installation targets: {candidate}")
        if candidate != path and not stat.S_ISDIR(info.st_mode):
            raise ValueError(f"Installation parent is not a directory: {candidate}")


def verified_package(root):
    check_path(root)
    inventory_path = root / "file-hashes.json"
    check_path(inventory_path)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if not isinstance(inventory, dict) or not inventory:
        raise ValueError("Package hash inventory must be a nonempty object")
    content = {}
    for name, expected in inventory.items():
        path = root / relative_path(name)
        if name == "file-hashes.json":
            raise ValueError("Package inventory must not include itself")
        check_path(path)
        if not isinstance(expected, str) or len(expected) != 64:
            raise ValueError(f"Invalid package hash: {name}")
        data = path.read_bytes()
        if digest(data) != expected:
            raise ValueError(f"Package integrity check failed: {name}")
        content[name] = data
    for path in root.rglob("*"):
        check_path(path)
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            name = path.relative_to(root).as_posix()
            if name != "file-hashes.json" and name not in content:
                raise ValueError(f"Unlisted package file: {name}")
    manifest = json.loads(content["toolkit.json"])
    if manifest["version"] != content["VERSION"].decode("utf-8").strip():
        raise ValueError("VERSION and toolkit.json disagree")
    return manifest, content


def plan_install(root, destination, host, execution_mode=None):
    manifest, content = verified_package(root)
    destination = Path(destination).expanduser().absolute()
    check_path(destination)
    if destination.exists() and not destination.is_dir():
        raise ValueError(f"Workspace must be a directory: {destination}")
    config = manifest["hosts"][host]
    execution_mode = execution_mode or config.get(
        "default_execution_request", manifest["default_execution_request"]
    )
    allowed = config.get("execution_requests", manifest["execution_requests"])
    if execution_mode not in allowed:
        raise ValueError(f"{host} does not support execution request {execution_mode!r}; choose {allowed}")
    skill = relative_path(config["skill"])
    profile = relative_path(config["profile"])
    guide = relative_path(config["guide"])
    receipt = Path(".mechanical-design-toolkit") / f"{host}.json"
    canonical = relative_path(manifest["canonical_skill"]).as_posix() + "/"
    plan = {skill / relative_path(name[len(canonical):]): data
            for name, data in content.items() if name.startswith(canonical)}
    if skill / "SKILL.md" not in plan:
        raise ValueError("Package has no canonical SKILL.md")
    for name in ("LICENSE", "THIRD_PARTY_NOTICES"):
        plan[skill / name] = content[name]
    for target, template_name in ((profile, config["template"]), (guide, config["guide_template"])):
        text = content[relative_path(template_name).as_posix()].decode("utf-8")
        for token, value in {
            "{{SKILL_PATH}}": Path(os.path.relpath(skill, target.parent)).as_posix(),
            "{{HOST_GUIDE}}": Path(os.path.relpath(guide, target.parent)).as_posix(),
            "{{EXECUTION_REQUEST}}": execution_mode,
        }.items():
            text = text.replace(token, value)
        if "{{" in text:
            raise ValueError(f"Unresolved adapter placeholder: {template_name}")
        plan[target] = text.encode("utf-8")
    plan[receipt] = json_bytes({
        "schema_version": 1,
        "toolkit": manifest["name"],
        "version": manifest["version"],
        "host": host,
        "skill": skill.as_posix(),
        "profile": profile.as_posix(),
        "guide": guide.as_posix(),
        "requested_execution": execution_mode,
        "execution_capabilities_verified": False,
        "files": {name.as_posix(): digest(data) for name, data in plan.items()},
        "qualification": config["status"],
        "dependencies_installed": False,
        "host_configuration_changed": False,
    })
    for relative in (skill, *plan):
        target = destination / relative
        check_path(target)
        if target.exists():
            raise FileExistsError(f"Installation conflict; nothing overwritten: {target}")
    return destination, skill, plan, execution_mode


def install(root, destination, host, dry_run=False, execution_mode=None):
    destination, skill, plan, execution_mode = plan_install(root, destination, host, execution_mode)
    result = {
        "status": "dry_run",
        "host": host,
        "requested_execution": execution_mode,
        "execution_capabilities_verified": False,
        "destination": str(destination),
        "files": [name.as_posix() for name in sorted(plan)],
        "dependencies_installed": False,
        "host_configuration_changed": False,
    }
    if dry_run:
        return result
    try:
        check_path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        check_path(destination / skill)
        (destination / skill).parent.mkdir(parents=True, exist_ok=True)
        (destination / skill).mkdir()
        for name, data in plan.items():
            target = destination / name
            check_path(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(data)
            if digest(target.read_bytes()) != digest(data):
                raise OSError(f"Installed file verification failed: {target}")
    except (OSError, ValueError) as error:
        raise OSError(
            f"Installation failed; a partial installation may remain at {destination}. "
            f"Inspect it before retrying. Cause: {error}"
        ) from error
    result["status"] = "installed"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, choices=("copilot", "opencode", "openai", "manual"))
    parser.add_argument("--destination", required=True, type=Path, help="Approved project folder, not global config")
    parser.add_argument("--dry-run", action="store_true", help="Verify and plan without writing")
    parser.add_argument("--execution", choices=("discover", "local", "remote", "manual"),
                        help="Requested boundary, not permissions or detected access; default discover (manual for manual host)")
    args = parser.parse_args()
    try:
        result = install(ROOT, args.destination, args.host, args.dry_run, args.execution)
    except (OSError, ValueError, KeyError) as error:
        print(f"Installation refused: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
