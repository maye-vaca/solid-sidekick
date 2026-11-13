"""Disjoint finish assignments on final physical-part triangles, never extra solids."""

from dataclasses import dataclass
from numbers import Integral
import re

import numpy as np
import trimesh


@dataclass(frozen=True)
class VisualRegion:
    id: str
    name: str
    color: str
    triangles: tuple[int, ...]

    def __post_init__(self):
        from .assembly import identifier
        identifier(self.id, "Visual region ID")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Visual region name must not be empty")
        if not isinstance(self.color, str) or not re.fullmatch(r"#[a-fA-F0-9]{6}", self.color):
            raise ValueError("Visual region color must be #RRGGBB")
        indices = tuple(self.triangles)
        if (not indices or any(isinstance(i, bool) or not isinstance(i, Integral) or i < 0 for i in indices)
                or len(set(indices)) != len(indices)):
            raise ValueError("Visual region needs unique nonnegative integer triangle indices")
        object.__setattr__(self, "triangles", tuple(int(i) for i in indices))

    def record(self):
        return {"id": self.id, "name": self.name, "color": self.color, "triangles": list(self.triangles)}


def validate_regions(part, mesh):
    seen, ids = set(), set()
    if part.visual_regions and len(part.solid.decompose()) != 1:
        raise ValueError("A region-bearing physical part must be one connected solid")
    for region in part.visual_regions:
        if not isinstance(region, VisualRegion):
            raise ValueError("Part visual_regions must contain VisualRegion records")
        if region.id.casefold() in ids:
            raise ValueError("Duplicate visual region ID")
        ids.add(region.id.casefold())
        if max(region.triangles) >= len(mesh.faces) or seen.intersection(region.triangles):
            raise ValueError("Visual regions must be disjoint and refer to existing triangles")
        seen.update(region.triangles)


def colored_mesh(part, mesh):
    colored = mesh.copy()
    if not part.visual_regions:
        colored.visual.vertex_colors = trimesh.visual.color.hex_to_rgba(part.color)
        return colored
    colors = np.tile(trimesh.visual.color.hex_to_rgba(part.color), (len(mesh.faces), 1))
    for region in part.visual_regions:
        colors[list(region.triangles)] = trimesh.visual.color.hex_to_rgba(region.color)
    colored.unmerge_vertices()
    colored.visual.vertex_colors = np.repeat(colors, 3, axis=0)
    return colored


def render_surfaces(components, manifest):
    """Partition triangles once; stable surface IDs carry physical parent metadata."""
    definitions = {p["id"]: p for p in manifest["parts"]}
    instances = {p["id"]: p for p in manifest["instances"]}
    meshes, metadata, sources = [], {}, {}
    for instance_id, mesh in components:
        instance = instances[instance_id]
        part = definitions[instance["part_id"]]
        regions = part.get("visual_regions", [])
        groups = []
        if regions:
            used = set()
            for region in regions:
                indices = region["triangles"]
                if (not indices or any(type(i) is not int or i < 0 or i >= len(mesh.faces) for i in indices)
                        or len(set(indices)) != len(indices) or used.intersection(indices)):
                    raise ValueError("Invalid exported visual region triangle partition")
                used.update(indices)
                groups.append((f"{instance_id}::region::{region['id']}", region, indices))
            remainder = sorted(set(range(len(mesh.faces)))-used)
            if remainder:
                groups.append((f"{instance_id}::base", None, remainder))
        else:
            groups.append((instance_id, None, None))
        for key, region, indices in groups:
            label = part.get("name", instance_id)
            if regions:
                label += " / "+(region["name"] if region else "base finish")
            meshes.append((key, mesh if indices is None else mesh.submesh([indices], append=True, repair=False)))
            metadata[key] = {"name": label, "color": region["color"] if region else part["color"],
                             "material": part["material"],
                             "notes": f"{label}. {part['notes']}".strip() if not regions else
                                      f"Finish surface of physical instance {instance_id}; not a separate part. {part['notes']}"}
            sources[key] = {"part_id": instance["part_id"], "transform_mm": instance["transform_mm"],
                            "physical_instance_id": instance_id, "region_id": region["id"] if region else None}
            metadata[key].update({k: sources[key][k] for k in ("physical_instance_id", "part_id", "region_id")})
    return meshes, metadata, sources
