"""Create a self-contained CAD starter in a new directory without overwriting files."""

import argparse
from pathlib import Path
import shutil
import tempfile


SKILL_ROOT = Path(__file__).resolve().parents[1]


def create_project(destination):
    destination = Path(destination).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"Destination already exists; choose a new folder: {destination}")
    foundation = SKILL_ROOT / "scripts" / "foundation"
    templates = SKILL_ROOT / "templates"
    required = [
        foundation / "cadkit" / name
        for name in ("__init__.py", "assembly.py", "geometry.py", "viewer.py", "scene.py",
                     "embedded.py", "validation.py", "preview.py", "revision.py", "timing.py", "review.py",
                     "regions.py", "incremental.py", "drawing.py", "checkpoint.py", "construction.py")
    ] + [foundation / "requirements.txt"] + [
        templates / name for name in ("model.py", "design_brief.json", "test_model.py",
                                     "checks.py", "validate.py", "README.md", "drawing-settings.json")
    ]
    for source in required:
        if not source.is_file():
            raise FileNotFoundError(f"Skill bundle is incomplete: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cad-starter-", dir=destination.parent) as directory:
        staged = Path(directory) / "project"
        staged.mkdir()
        for source in required:
            relative = Path("cadkit") / source.name if source.parent.name == "cadkit" else Path(source.name)
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        # A competing creator must not turn this into an overwrite on POSIX.
        destination.mkdir()
        for source in staged.iterdir():
            shutil.move(str(source), str(destination / source.name))
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="New project folder; must not already exist")
    args = parser.parse_args()
    try:
        destination = create_project(args.destination)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Created CAD starter: {destination}")
    print("This is an illustrative riser, not your design. Read README.md before adapting it.")
    print("No packages installed and no model code executed.")


if __name__ == "__main__":
    main()
