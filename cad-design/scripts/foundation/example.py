"""A parameterized display riser: two plates and four reusable standoffs."""

import argparse
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
import webbrowser

from cadkit import Assembly, Instance, Part, Placement
from cadkit.geometry import cylinder, plate_with_holes, positive


@dataclass(frozen=True)
class Dimensions:
    width: float = 120
    depth: float = 80
    plate_thickness: float = 4
    gap: float = 32
    inset: float = 12
    standoff_radius: float = 5
    hole_diameter: float = 3.4

    def validate(self):
        for name, value in asdict(self).items():
            positive(value, name)
        if self.hole_diameter >= 2*self.standoff_radius:
            raise ValueError("Standoff hole must be smaller than its outside diameter")
        if not self.standoff_radius < self.inset < min(self.width, self.depth)/2:
            raise ValueError("Inset must fit standoffs inside the plate and keep them separate")
        if 2*self.standoff_radius >= min(self.width, self.depth)-2*self.inset:
            raise ValueError("Standoffs must not overlap each other")


def build(d=None):
    d = Dimensions() if d is None else d
    d.validate()
    holes = [(x, y, d.hole_diameter)
             for x in (d.inset, d.width-d.inset) for y in (d.inset, d.depth-d.inset)]
    assembly = Assembly(
        name="Display riser example",
        coordinate_system="Millimetres; origin at base lower-front-left corner. +X right, +Y back, +Z up.",
        assumptions=[
            "Demonstration geometry only; no load rating.",
            "Hole diameters are nominal design values, not verified fits.",
            "Fasteners and threads are omitted; materials are illustrative.",
        ], parameters=asdict(d))
    assembly.add_part(Part("plate", plate_with_holes(d.width, d.depth, d.plate_thickness, holes),
                           "Drilled plate", "Plywood (illustrative)", "#d9b079"))
    spacer = cylinder(d.standoff_radius, d.gap)-cylinder(
        d.hole_diameter/2, d.gap+2).translate((0, 0, -1))
    assembly.add_part(Part("standoff", spacer, "Tubular standoff", "Printed polymer (illustrative)",
                           "#58b9c9", notes="Local origin at the bottom of its central axis."))
    assembly.add_instance(Instance("base", "plate"))
    assembly.add_instance(Instance("top", "plate", Placement((0, 0, d.plate_thickness+d.gap))))
    for index, (x, y, _) in enumerate(holes, 1):
        assembly.add_instance(Instance(f"standoff_{index}", "standoff",
                                      Placement((x, y, d.plate_thickness))))
    return assembly


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "output")
    parser.add_argument("--gap", type=float, default=32, help="Space between plates, in mm")
    parser.add_argument("--open", action="store_true", help="Open the generated offline viewer")
    args = parser.parse_args()
    try:
        result = build(Dimensions(gap=args.gap)).export(args.output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Exported 2 unique parts and 6 instances to {result}")
    print("STL: mm; GLB: metres. Open viewer.html to inspect the assembly.")
    if args.open and not webbrowser.open((result / "viewer.html").as_uri()):
        print(f"Browser did not open. Open {result / 'viewer.html'} manually.", file=sys.stderr)


if __name__ == "__main__":
    main()
