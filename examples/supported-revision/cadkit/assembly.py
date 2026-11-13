"""Reusable components, placement and exports; canonical geometry uses millimetres."""

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import re
import tempfile

import manifold3d as m
import numpy as np
import trimesh
from .regions import VisualRegion

def identifier(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", value):
        raise ValueError(f"{label} must start with a letter and contain only letters, digits, _ or -")
    return value


def unit_scale(units):
    if units not in ("mm", "in"):
        raise ValueError("Units must be 'mm' or 'in'")
    return 1.0 if units == "mm" else 25.4


def solid_mesh(solid):
    if solid.status() != m.Error.NoError or not math.isfinite(solid.volume()) or solid.volume() <= 0:
        raise ValueError(f"Invalid or empty Manifold solid: {solid.status()}")
    raw = solid.to_mesh64()
    mesh = trimesh.Trimesh(vertices=raw.vert_properties[:, :3], faces=raw.tri_verts, process=False)
    if not np.isfinite(mesh.vertices).all() or not mesh.is_watertight or not mesh.is_volume:
        raise ValueError("Component must have finite, watertight, consistently oriented geometry")
    return mesh


@dataclass(frozen=True)
class Part:
    """A reusable local-coordinate shape; input units are normalized to mm once."""

    id: str
    solid: m.Manifold
    name: str
    material: str
    color: str
    units: str = "mm"
    notes: str = ""
    visual_regions: tuple[VisualRegion, ...] = ()

    def __post_init__(self):
        identifier(self.id, "Part ID")
        if not self.name.strip() or not self.material.strip():
            raise ValueError("Part name and material must not be empty")
        if not re.fullmatch(r"#[a-fA-F0-9]{6}", self.color):
            raise ValueError("Part color must be a #RRGGBB hex color")
        scale = unit_scale(self.units)
        object.__setattr__(self, "solid", self.solid.scale((scale,)*3))
        object.__setattr__(self, "units", "mm")
        object.__setattr__(self, "visual_regions", tuple(self.visual_regions))
        from .regions import validate_regions
        validate_regions(self, solid_mesh(self.solid))


@dataclass(frozen=True)
class Placement:
    """Rotate locally by Euler X/Y/Z degrees, then translate in explicit units."""

    translation: tuple[float, float, float] = (0, 0, 0)
    rotation: tuple[float, float, float] = (0, 0, 0)
    units: str = "mm"

    def __post_init__(self):
        scale = unit_scale(self.units)
        for values in (self.translation, self.rotation):
            if len(values) != 3 or not all(math.isfinite(v) for v in values):
                raise ValueError("Placement requires three finite translation and rotation values")
        object.__setattr__(self, "translation", tuple(v*scale for v in self.translation))
        object.__setattr__(self, "rotation", tuple(self.rotation))
        object.__setattr__(self, "units", "mm")

    def matrix(self):
        transform = trimesh.transformations.euler_matrix(
            *map(math.radians, self.rotation), axes="sxyz")
        transform[:3, 3] = self.translation
        return transform


@dataclass(frozen=True)
class Instance:
    id: str
    part_id: str
    placement: Placement = field(default_factory=Placement)

    def __post_init__(self):
        identifier(self.id, "Instance ID")
        identifier(self.part_id, "Part reference")


@dataclass
class Assembly:
    name: str
    coordinate_system: str
    assumptions: list[str] = field(default_factory=list)
    parameters: dict = field(default_factory=dict)
    parts: dict[str, Part] = field(default_factory=dict)
    instances: list[Instance] = field(default_factory=list)
    revision: dict | None = None

    def add_part(self, part):
        if part.id.casefold() in {key.casefold() for key in self.parts}:
            raise ValueError(f"Duplicate part ID: {part.id}")
        self.parts[part.id] = part
        return part.id

    def add_instance(self, instance):
        if instance.part_id not in self.parts:
            raise ValueError(f"Unknown part: {instance.part_id}")
        if instance.id.casefold() in {item.id.casefold() for item in self.instances}:
            raise ValueError(f"Duplicate instance ID: {instance.id}")
        self.instances.append(instance)

    def validate(self):
        if not self.name.strip() or not self.coordinate_system.strip():
            raise ValueError("Assembly name and coordinate system are required")
        if not self.parts or not self.instances:
            raise ValueError("Assembly requires parts and instances")
        if any(key != part.id for key, part in self.parts.items()):
            raise ValueError("Part dictionary keys must match part IDs")
        if len({key.casefold() for key in self.parts}) != len(self.parts):
            raise ValueError("Part IDs must be unique, ignoring case")
        if len({item.id.casefold() for item in self.instances}) != len(self.instances):
            raise ValueError("Instance IDs must be unique, ignoring case")
        for part in self.parts.values():
            from .regions import validate_regions
            validate_regions(part, solid_mesh(part.solid))
        for instance in self.instances:
            if instance.part_id not in self.parts:
                raise ValueError(f"Unknown part: {instance.part_id}")
        json.dumps(self.parameters, allow_nan=False)
        if not all(isinstance(item, str) for item in self.assumptions):
            raise ValueError("Assumptions must be strings")
        if self.revision is not None:
            from .revision import validate_snapshot
            validate_snapshot(self.revision)

    def meshes(self):
        self.validate()
        local = {key: solid_mesh(part.solid) for key, part in self.parts.items()}
        placed = {}
        for instance in self.instances:
            mesh = local[instance.part_id].copy()
            mesh.apply_transform(instance.placement.matrix())
            placed[instance.id] = mesh
        return local, placed

    def interference_volume(self, first_id, second_id):
        """Positive-volume overlap in mm^3, not strength or functional validation."""
        self.validate()
        by_id = {item.id: item for item in self.instances}
        solids = []
        for key in (first_id, second_id):
            instance = by_id[key]
            solid = self.parts[instance.part_id].solid
            solids.append(solid.transform(instance.placement.matrix()[:3].tolist()))
        return (solids[0] ^ solids[1]).volume()

    def viewer_scene(self):
        """Return a versioned mm/Z-up scene with placed geometry and source identity."""
        _, placed = self.meshes()
        return self._viewer_scene(placed)

    def _viewer_scene(self, placed):
        from .scene import scene_data
        if any(part.visual_regions for part in self.parts.values()):
            from .regions import render_surfaces
            components, metadata, sources = render_surfaces(list(placed.items()), self._surface_manifest())
            scene = scene_data(components, title=self.name, coordinate_system=self.coordinate_system,
                               assumptions=self.assumptions, metadata=metadata, instances=sources)
            scene["physical_instances"] = [item.id for item in self.instances]
            for record in scene["parts"]:
                record.update({key: sources[record["id"]][key] for key in ("physical_instance_id", "region_id")})
            return scene

        metadata, instances = {}, {}
        for item in self.instances:
            part = self.parts[item.part_id]
            metadata[item.id] = {key: getattr(part, key) for key in ("name", "color", "material", "notes")}
            instances[item.id] = {"part_id": item.part_id, "transform_mm": item.placement.matrix().tolist()}
        return scene_data(list(placed.items()), title=self.name, coordinate_system=self.coordinate_system,
                          assumptions=self.assumptions, metadata=metadata, instances=instances)

    def _surface_manifest(self):
        return {"parts": [
            {"id": part.id, "name": part.name, "color": part.color, "material": part.material,
             "notes": part.notes, **({"visual_regions": [r.record() for r in part.visual_regions]}
                                    if part.visual_regions else {})}
            for part in self.parts.values()],
            "instances": [{"id": item.id, "part_id": item.part_id,
                           "transform_mm": item.placement.matrix().tolist()} for item in self.instances]}

    def export(self, output, *, viewer_backend="lightweight", viewer_assets=None, previous_output=None):
        """Local and assembled ASCII STLs in mm, GLB in metres, HTML and manifest."""
        from .viewer import write_mesh_viewer
        if self.revision is not None:
            from .revision import require_modeling_ready, validate_snapshot
            validate_snapshot(self.revision)
            require_modeling_ready(self.revision["brief"])

        if viewer_backend not in ("lightweight", "embedded"):
            raise ValueError("viewer_backend must be lightweight or embedded")
        if viewer_backend == "lightweight" and viewer_assets is not None:
            raise ValueError("viewer_assets is only valid with viewer_backend='embedded'")
        assets = None
        if viewer_backend == "embedded":
            from .embedded import read_assets
            assets = read_assets(viewer_assets)
        local, placed = self.meshes()
        output = Path(output).expanduser().resolve()
        if previous_output is not None and self.revision is None:
            raise ValueError("Revision comparison requires tracked source")
        # Stage a complete build before replacing generated files. No directory deletion.
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="cadkit-", dir=output.parent) as temp:
            stage = Path(temp)
            for subdir in ("parts", "assembled"):
                (stage / subdir).mkdir()
            for key, mesh in local.items():
                mesh.export(stage / "parts" / f"{key}.stl", file_type="stl_ascii")
            for key, mesh in placed.items():
                mesh.export(stage / "assembled" / f"{key}.stl", file_type="stl_ascii")
            scene = trimesh.Scene(base_frame="__cadkit_world__", metadata={"units": "m", "name": self.name})
            for key, mesh in local.items():
                from .regions import colored_mesh
                colored = colored_mesh(self.parts[key], mesh)
                colored.apply_scale(.001)
                scene.geometry[key] = colored
            for instance in self.instances:
                transform = instance.placement.matrix()
                transform[:3, 3] *= .001
                scene.graph.update(frame_to=instance.id, frame_from=scene.graph.base_frame,
                                   matrix=transform, geometry=instance.part_id)
            (stage / "assembly.glb").write_bytes(scene.export(file_type="glb"))
            info = {}
            for instance in self.instances:
                part = self.parts[instance.part_id]
                info[instance.id] = {"color": part.color, "material": part.material,
                                     "notes": f"{part.name}. {part.notes}".strip()}
            if viewer_backend == "lightweight":
                components = list(placed.items())
                title = self.name
                if any(part.visual_regions for part in self.parts.values()):
                    from .regions import render_surfaces
                    components, info, _ = render_surfaces(components, self._surface_manifest())
                    title += f" / {len(self.instances)} physical instances; finish surfaces are not parts"
                write_mesh_viewer(components, stage / "viewer.html", title=title,
                                  units="mm", metadata=info, coordinate_system=self.coordinate_system,
                                  assumptions=self.assumptions)
            else:
                from .embedded import write_scene_bundle
                viewer = write_scene_bundle(self._viewer_scene(placed), stage, assets)
            manifest = {
                "schema_version": 1, "name": self.name, "geometry_units": "mm",
                "stl_units": "mm", "glb_units": "m", "coordinate_system": self.coordinate_system,
                "parameters": self.parameters, "assumptions": self.assumptions,
                "limitations": "Mesh geometry, not STEP/B-rep. Not a structural or fabrication certification.",
                "parts": [{
                    "id": part.id, "name": part.name, "material": part.material, "color": part.color,
                    "notes": part.notes, "stl": f"parts/{part.id}.stl",
                    "bounds_mm": local[part.id].bounds.tolist(),
                    "volume_mm3": float(local[part.id].volume),
                } for part in self.parts.values()],
                "instances": [{
                    "id": item.id, "part_id": item.part_id,
                    "transform_mm": item.placement.matrix().tolist(),
                    "stl": f"assembled/{item.id}.stl",
                    "bounds_mm": placed[item.id].bounds.tolist(),
                } for item in self.instances],
            }
            for entry, part in zip(manifest["parts"], self.parts.values()):
                if part.visual_regions:
                    entry["visual_regions"] = [region.record() for region in part.visual_regions]
            if viewer_backend == "embedded":
                manifest["viewer"] = viewer
            if self.revision is not None:
                from .revision import sha256, validate_snapshot
                from .review import write_review
                manifest["revision"] = validate_snapshot(self.revision)
                prior = Path(previous_output).resolve() if previous_output is not None else (
                    output if (output / "manifest.json").is_file() else None)
                manifest["review"] = write_review(self.revision, placed, manifest, stage, prior)
                (stage / "revision-state.json").write_text(
                    json.dumps(self.revision, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
                manifest["files_sha256"] = {
                    path.relative_to(stage).as_posix(): sha256(path)
                    for path in sorted(stage.rglob("*")) if path.is_file()
                }
            if (output / "manifest.json").is_file():
                from .revision import check_publication
                previous = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
                check_publication(self.revision, previous, manifest)
            (stage / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
            published = output / "manifest.json"
            if not published.is_file() or published.read_bytes() != (stage / "manifest.json").read_bytes():
                from .revision import retire_qualification
                retire_qualification(output, "Changed exports are being published; qualify the current source and exports")
            # Generated-name replacements only; unrelated files are preserved.
            for source in sorted(stage.rglob("*")):
                if source.is_file():
                    target = output / source.relative_to(stage)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source.replace(target)
        return output
