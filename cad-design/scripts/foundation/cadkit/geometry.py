"""Primitive helpers in millimetres, with explicit input checks."""

import math

import manifold3d as m
import numpy as np


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


def internal_thread_tool(major_diameter, pitch, height, *, radial_clearance=0.0,
                         steps_per_turn=144):
    """Single-start right-hand 60-degree bore cutter; full threads over Z=0..height.

    Millimetres; simplified internal profile, not a certified thread class.
    The tool overruns both faces. Lead-ins and the surrounding wall are the
    caller's responsibility. Clearance is added to radii, not diameters.
    Requested steps are a floor; angular sampling adapts to thread depth.
    """
    for name, value in (("major_diameter", major_diameter), ("pitch", pitch), ("height", height)):
        positive(value, name)
    if (isinstance(radial_clearance, bool) or not math.isfinite(radial_clearance)
            or radial_clearance < 0):
        raise ValueError("radial_clearance must be finite and nonnegative")
    if type(steps_per_turn) is not int or steps_per_turn < 12:
        raise ValueError("steps_per_turn must be an integer of at least 12")
    if major_diameter <= 1.08253 * pitch:
        raise ValueError("major_diameter must exceed the internal thread profile depth")

    root = major_diameter / 2.0 + radial_clearance
    crest = (major_diameter - 1.08253 * pitch) / 2.0 + radial_clearance
    # Keep a facet's radial sag small relative to the thread depth, not just its diameter.
    chord_error = min(.01, (root - crest) * .02)
    if not math.isfinite(root) or chord_error <= 0:
        raise ValueError("Internal thread dimensions cannot resolve a finite thread depth")
    half_angle = math.asin(math.sqrt((chord_error / root) / 2))
    if half_angle == 0:
        raise ValueError("Internal thread dimensions cannot resolve angular sampling")
    required_steps = math.ceil(math.pi / (2 * half_angle))
    steps_per_turn = 4 * math.ceil(max(steps_per_turn, required_steps) / 4)
    core_segments = 4 * math.ceil(max(96, required_steps) / 4)
    inner = crest - min(0.25, crest / 2.0)
    crest_half_width = pitch / 16.0
    inner_half_width = crest_half_width + (root - inner) * math.tan(math.radians(30.0))
    profile = ((inner, -inner_half_width), (root, -crest_half_width),
               (root, crest_half_width), (inner, inner_half_width))
    turns = math.ceil((height + 2.0 * pitch) / pitch)
    steps = turns * steps_per_turn
    start = -pitch
    end = start + turns * pitch
    vertices, faces = [], []
    for step in range(steps + 1):
        angle = 2.0 * math.pi * step / steps_per_turn
        z = start + pitch * step / steps_per_turn
        cosine, sine = math.cos(angle), math.sin(angle)
        vertices.extend((radius * cosine, radius * sine, z + offset)
                        for radius, offset in profile)
    for step in range(steps):
        ring, following_ring = 4 * step, 4 * (step + 1)
        for index in range(4):
            following = (index + 1) % 4
            faces.extend(((ring + index, following_ring + index, following_ring + following),
                          (ring + index, following_ring + following, ring + following)))
    faces.extend(((0, 1, 2), (0, 2, 3)))
    last = 4 * steps
    faces.extend(((last, last + 2, last + 1), (last, last + 3, last + 2)))
    # Float32 rounding here can create intersections that collapse on STL reload.
    ribbon = m.Manifold(m.Mesh64(
        vert_properties=np.asarray(vertices, dtype=np.float64),
        tri_verts=np.asarray(faces, dtype=np.uint64),
    ))
    if ribbon.status() != m.Error.NoError:
        raise ValueError(f"Internal thread ribbon is invalid: {ribbon.status()}")
    core = m.Manifold.cylinder(end - start + 2.0 * pitch, crest, circular_segments=core_segments)
    tool = core.translate((0, 0, start - pitch)) + ribbon
    if tool.status() != m.Error.NoError:
        raise ValueError(f"Internal thread boolean failed: {tool.status()}")
    return tool
