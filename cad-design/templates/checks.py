"""Requirements for the illustrative riser; replace only these for a new design."""

import math
import json
from pathlib import Path
import manifold3d as m


def check(context):
    source = json.loads(Path(__file__).with_name("design_brief.json").read_text(encoding="utf-8"))
    dimensions = {}
    for name, fact in source["dimensions"].items():
        context.require(fact["unit"] in ("mm", "in"), f"Unsupported requirement unit: {name}")
        dimensions[name] = fact["value"]*(25.4 if fact["unit"] == "in" else 1)
    w, d, t, gap = (dimensions[k] for k in ("width", "depth", "plate_thickness", "gap"))
    inset, radius, bore = (dimensions[k] for k in ("inset", "standoff_radius", "hole_diameter"))
    top = t+gap
    context.require(len(context.local) == 2 and len(context.placed) == 6, "Expected 2 parts / 6 instances")
    context.expect_bounds("base", [[0, 0, 0], [w, d, t]])
    context.expect_bounds("top", [[0, 0, top], [w, d, top+t]])
    centers = ((inset, inset), (inset, d-inset), (w-inset, inset), (w-inset, d-inset))
    for index, (x, y) in enumerate(centers, 1):
        context.expect_bounds(f"standoff_{index}", [[x-radius, y-radius, t], [x+radius, y+radius, top]])
        for name, bottom, height in (("base", 0, t), ("top", top, t), (f"standoff_{index}", t, gap)):
            probe = m.Manifold.cylinder(height, bore/4, circular_segments=16).translate((x, y, bottom))
            context.require((context.solids[name] ^ probe).volume() < 1e-6, f"{name}: blocked through-hole")
    area = 96*math.sin(2*math.pi/96)/2
    context.require(abs(context.local["plate"].volume-(w*d-4*area*(bore/2)**2)*t) < 1e-5,
                    "Plate/hole dimensions changed")
    context.require(abs(context.local["standoff"].volume-area*(radius**2-(bore/2)**2)*gap) < 1e-5,
                    "Standoff bore/diameter changed")
    context.expect_gap("base", "top", gap)
    x_gap, y_gap = w-2*inset-2*radius, d-2*inset-2*radius
    for first, second, expected in (("standoff_1", "standoff_2", y_gap), ("standoff_1", "standoff_3", x_gap),
                                    ("standoff_2", "standoff_4", x_gap), ("standoff_3", "standoff_4", y_gap)):
        context.expect_gap(first, second, expected)
    return {"requirements": "Illustrative riser dimensions, through-holes, bores, contacts and gaps",
            "hole_diameter_mm": bore, "plate_gap_mm": gap}
