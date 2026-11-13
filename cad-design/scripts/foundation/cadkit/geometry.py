"""Primitive helpers in millimetres, with explicit input checks."""

import math

import manifold3d as m


def positive(value, name):
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


def box(width, depth, height):
    """Local origin at the lower corner; X width, Y depth, Z height."""
    for name, value in (("width", width), ("depth", depth), ("height", height)):
        positive(value, name)
    return m.Manifold.cube((width, depth, height))


def cylinder(radius, height, segments=96):
    """Local Z-axis cylinder, centered in X/Y with its base at Z=0."""
    positive(radius, "radius")
    positive(height, "height")
    if type(segments) is not int or segments < 3:
        raise ValueError("segments must be an integer of at least 3")
    return m.Manifold.cylinder(height, radius, circular_segments=segments)


def plate_with_holes(width, depth, thickness, holes):
    """Each hole is (x, y, diameter), wholly within the rectangular plate."""
    solid = box(width, depth, thickness)
    for x, y, diameter in holes:
        positive(diameter, "hole diameter")
        radius = diameter/2
        if not (math.isfinite(x) and math.isfinite(y)
                and radius < x < width-radius and radius < y < depth-radius):
            raise ValueError("Hole must fit strictly inside the plate")
        solid -= cylinder(radius, thickness+2).translate((x, y, -1))
    return solid
