"""Build an illustrative riser from a provenance-bearing brief and export review files."""

import argparse
from dataclasses import asdict, dataclass, fields
import json
from pathlib import Path
import sys
import webbrowser

from cadkit import Assembly, Instance, Part, Placement
from cadkit.geometry import cylinder, plate_with_holes, positive
from cadkit.preview import export_preview
from cadkit.revision import make_snapshot, require_modeling_ready, validate_brief as validate_revision


ROOT = Path(__file__).resolve().parent
DEFAULT_BRIEF = ROOT / "design_brief.json"
STATUSES = {"measured", "confirmed", "assumed", "estimated"}


@dataclass(frozen=True)
class Dimensions:
    width: float
    depth: float
    plate_thickness: float
    gap: float
    inset: float
    standoff_radius: float
    hole_diameter: float

    def validate(self):
        for name, value in asdict(self).items():
            positive(value, name)
        if self.hole_diameter >= 2*self.standoff_radius:
            raise ValueError("Standoff hole must be smaller than its outside diameter")
        if not self.standoff_radius < self.inset < min(self.width, self.depth)/2:
            raise ValueError("Inset must fit standoffs inside the plate and keep them separate")
        if 2*self.standoff_radius >= min(self.width, self.depth)-2*self.inset:
            raise ValueError("Standoffs must not overlap each other")


def load_brief(path=DEFAULT_BRIEF):
    brief = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(brief, dict):
        raise ValueError("Brief must be a JSON object")
    if type(brief.get("schema_version")) is not int or brief["schema_version"] != 1:
        raise ValueError("Brief schema_version must be 1")
    require_modeling_ready(brief)
    for key in ("name", "intent", "stage", "coordinate_system"):
        if not isinstance(brief.get(key), str) or not brief[key].strip():
            raise ValueError(f"Brief {key} must be a nonempty string")
    assumptions = brief.get("assumptions")
    if not isinstance(assumptions, list) or not all(
        isinstance(item, str) and item.strip() for item in assumptions
    ):
        raise ValueError("Brief assumptions must be a list of nonempty strings")
    entries = brief.get("dimensions")
    names = {field.name for field in fields(Dimensions)}
    if not isinstance(entries, dict) or set(entries) != names:
        raise ValueError(f"Brief dimensions must contain exactly: {', '.join(sorted(names))}")
    values = {}
    for name, entry in entries.items():
        if not isinstance(entry, dict):
            raise ValueError(f"Dimension {name} must be an object")
        value = entry.get("value")
        if type(value) not in (int, float):
            raise ValueError(f"Dimension {name} value must be a number, not a bool/string")
        positive(value, name)
        if entry.get("unit") not in ("mm", "in"):
            raise ValueError(f"Dimension {name} unit must be mm or in")
        if not isinstance(entry.get("status"), str) or entry["status"] not in STATUSES:
            raise ValueError(f"Dimension {name} status must be one of {', '.join(sorted(STATUSES))}")
        if not isinstance(entry.get("source"), str) or not entry["source"].strip():
            raise ValueError(f"Dimension {name} needs a nonempty source")
        values[name] = value * (25.4 if entry["unit"] == "in" else 1)
    dimensions = Dimensions(**values)
    dimensions.validate()
    validate_revision(brief)
    return brief, dimensions


def build(brief_path=DEFAULT_BRIEF):
    brief, d = load_brief(brief_path)
    assumptions = list(brief["assumptions"])
    for name, entry in sorted(brief["dimensions"].items()):
        if entry["status"] in ("assumed", "estimated"):
            assumptions.append(
                f"{name}: {entry['value']} {entry['unit']} ({entry['status']}; {entry['source']})."
            )
    assembly = Assembly(
        brief["name"], brief["coordinate_system"], assumptions=assumptions,
        parameters={"stage": brief["stage"], "intent": brief["intent"],
                    "dimensions": brief["dimensions"], "dimensions_mm": asdict(d)},
        revision=make_snapshot(brief),
    )
    holes = [(x, y, d.hole_diameter)
             for x in (d.inset, d.width-d.inset) for y in (d.inset, d.depth-d.inset)]
    assembly.add_part(Part(
        "plate", plate_with_holes(d.width, d.depth, d.plate_thickness, holes),
        "Drilled plate", "Plywood (illustrative)", "#d9b079",
    ))
    spacer = cylinder(d.standoff_radius, d.gap)-cylinder(
        d.hole_diameter/2, d.gap+2).translate((0, 0, -1))
    assembly.add_part(Part(
        "standoff", spacer, "Tubular standoff", "Printed polymer (illustrative)",
        "#58b9c9", notes="Local origin at bottom of central axis; nominal bore, no fit certification.",
    ))
    assembly.add_instance(Instance("base", "plate"))
    assembly.add_instance(Instance("top", "plate", Placement((0, 0, d.plate_thickness+d.gap))))
    for index, (x, y, _) in enumerate(holes, 1):
        assembly.add_instance(Instance(
            f"standoff_{index}", "standoff", Placement((x, y, d.plate_thickness)),
        ))
    return assembly


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", type=Path, default=DEFAULT_BRIEF)
    parser.add_argument("--output", type=Path, default=ROOT / "output")
    parser.add_argument("--open", action="store_true", help="Open the exported offline viewer")
    parser.add_argument("--viewer-backend", choices=("lightweight", "embedded"), default="lightweight",
                        help="Default lightweight HTML, or optional sandboxed component/offline bundle")
    parser.add_argument("--viewer-assets", type=Path, help="Prebuilt cad-viewer/dist folder for embedded backend")
    parser.add_argument("--previous-output", type=Path, help="Tracked ancestor output to compare without modifying it")
    args = parser.parse_args()
    try:
        assembly, result = export_preview(lambda: build(args.brief), args.output,
                                          viewer_backend=args.viewer_backend, viewer_assets=args.viewer_assets,
                                          previous_output=args.previous_output, brief_path=args.brief)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Exported {len(assembly.parts)} unique parts and {len(assembly.instances)} instances to {result}")
    print("STL coordinates: mm (choose mm on import). GLB: metres. Tracked preview: review.html; single revision: viewer.html.")
    print("Unresolved assumptions are in the viewer and manifest; this starter is not fabrication approval.")
    review = result / ("review.html" if assembly.revision is not None else "viewer.html")
    if args.open and not webbrowser.open(review.as_uri()):
        print(f"Browser did not open. Open {review} manually.", file=sys.stderr)


if __name__ == "__main__":
    main()
