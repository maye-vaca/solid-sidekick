"""Shared placed-mesh packing; normalization precedes GPU float conversion."""

import base64
import hashlib
import json
from pathlib import Path
import re

import numpy as np


LIMITATIONS = "Mesh geometry, not STEP/B-rep. Not a structural or fabrication certification."


def display_color(name):
    palette = ("#8fc5e8", "#deb478", "#a9c588", "#c1a6dd", "#dba8b5", "#85c9bb")
    return palette[hashlib.sha256(name.encode("utf-8")).digest()[0] % len(palette)]


def packed_geometry(components):
    components = list(components)
    if not components:
        raise ValueError("Cannot view an empty assembly")
    ids = set()
    for name, mesh in components:
        if not isinstance(name, str) or not name or name in ids:
            raise ValueError("Mesh instance IDs must be unique nonempty strings")
        ids.add(name)
        if (mesh.is_empty or not len(mesh.faces) or not np.isfinite(mesh.vertices).all()
                or not np.isfinite(mesh.face_normals).all() or not np.any(mesh.area_faces > 0)):
            raise ValueError(f"Mesh has empty, nonfinite or unusable triangle geometry: {name}")
    bounds = np.array([
        np.min([mesh.bounds[0] for _, mesh in components], axis=0),
        np.max([mesh.bounds[1] for _, mesh in components], axis=0),
    ])
    extent = bounds[1]-bounds[0]
    scale = float(extent.max())
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("STL folder has no finite, nonzero model extent")
    origin = bounds[0]+extent/2
    records = []
    for name, mesh in components:
        triangles = (mesh.vertices[mesh.faces]-origin)/scale
        normals = np.broadcast_to(mesh.face_normals[:, None, :], triangles.shape)
        vertices = np.concatenate((triangles, normals), axis=2).astype("<f4")
        if not np.isfinite(vertices).all():
            raise ValueError(f"Coordinates cannot be represented for viewing: {name}")
        records.append({
            "name": name, "color": display_color(Path(name).stem),
            "bounds": ((mesh.bounds-origin)/scale).tolist(),
            "triangles": len(mesh.faces),
            "vertices": base64.b64encode(vertices.tobytes()).decode("ascii"),
        })
    return {"parts": records, "extent": extent.tolist(),
            "bounds": ((bounds-origin)/scale).tolist(),
            "bounds_mm": bounds.tolist(), "origin_mm": origin.tolist(), "scale_mm": scale}


def scene_data(components, *, title, coordinate_system, assumptions=(), metadata=None,
               instances=None, limitations=LIMITATIONS):
    """Scene v1: already placed geometry in mm; source transforms are metadata only."""
    for key, value in (("title", title), ("coordinate_system", coordinate_system), ("limitations", limitations)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Scene {key} must be a nonempty string")
    assumptions = list(assumptions)
    if not all(isinstance(item, str) for item in assumptions):
        raise ValueError("Scene assumptions must be strings")
    components = list(components)
    for name, mesh in components:
        if not np.all(mesh.area_faces > 0):
            raise ValueError(f"Embedded scenes require nondegenerate triangles: {name}")
    packed = packed_geometry(components)
    ids = {name for name, _ in components}
    for label, mapping in (("metadata", metadata), ("instances", instances)):
        if mapping is not None and set(mapping) != ids:
            raise ValueError(f"Scene {label} must match mesh instance IDs exactly")
    parts = []
    for record, (key, mesh) in zip(packed["parts"], components):
        info = ({"name": key, "color": record["color"], "material": "Unspecified", "notes": ""}
                if metadata is None else metadata[key])
        for field in ("name", "material", "notes"):
            if not isinstance(info.get(field), str) or (field != "notes" and not info[field].strip()):
                raise ValueError(f"Missing string {field}: {key}")
        if not isinstance(info.get("color"), str) or not re.fullmatch(r"#[a-fA-F0-9]{6}", info["color"]):
            raise ValueError(f"Invalid scene color: {key}")
        source = {"part_id": key, "transform_mm": np.eye(4).tolist()} if instances is None else instances[key]
        if not isinstance(source.get("part_id"), str) or not source["part_id"].strip():
            raise ValueError(f"Missing source part ID: {key}")
        transform = np.asarray(source.get("transform_mm"), dtype=np.float64)
        if (transform.shape != (4, 4) or not np.isfinite(transform).all()
                or not np.array_equal(transform[3], [0, 0, 0, 1])):
            raise ValueError(f"Invalid affine source transform: {key}")
        part = dict(record)
        part.update(id=key, part_id=source["part_id"], transform_mm=transform.tolist(),
                    bounds_mm=mesh.bounds.tolist(),
                    **{field: info[field] for field in ("name", "color", "material", "notes")})
        parts.append(part)
    result = {"schema_version": 1, "title": title, "units": "mm", "up": "Z",
              "origin_mm": packed["origin_mm"], "scale_mm": packed["scale_mm"],
              "bounds_mm": packed["bounds_mm"], "coordinate_system": coordinate_system,
              "assumptions": assumptions, "limitations": limitations, "parts": parts}
    json.dumps(result, allow_nan=False)
    return result


def script_json(data):
    return json.dumps(data, separators=(",", ":"), allow_nan=False).replace(
        "&", r"\u0026").replace("<", r"\u003c").replace(">", r"\u003e")
