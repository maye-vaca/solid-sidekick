"""Portable mesh-derived concept sheets, not fabrication drawings or exact CAD."""

import argparse
import csv
from fractions import Fraction
import hashlib
import html
import io
import json
import math
from pathlib import Path
import shutil
import tempfile
import textwrap

import numpy as np
import trimesh

from .incremental import qualified_baseline, source_binding, writer
from .revision import canonical, identifier, make_snapshot, sha256, text
from .validation import mesh_solid, require


SIZES = {"A3": (297, 420), "A4": (210, 297), "Letter": (215.9, 279.4)}
BASES = {
    "top": np.eye(3),
    "front": np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]]),
    "right": np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]]),
    "axonometric": np.array([[1, 1, 0], [-1, 1, 2], [1, -1, 1]]) /
                   np.array([[math.sqrt(2)], [math.sqrt(6)], [math.sqrt(3)]]),
}


def number(value, label, *, minimum=0, positive=False):
    require(type(value) in (int, float) and math.isfinite(value), f"{label} must be finite")
    require(value > minimum if positive else value >= minimum, f"{label} is out of range")
    return value


def fields(value, required, optional=()):
    require(isinstance(value, dict) and set(required) <= value.keys()
            and value.keys() <= set(required) | set(optional), f"Expected fields: {', '.join(required)}")


def validate_settings(settings):
    fields(settings, ("schema_version", "title", "units", "fraction_denominator", "decimal_places",
                      "scale_denominator", "sheet", "style", "views", "schedule"))
    require(type(settings["schema_version"]) is int and settings["schema_version"] == 1,
            "Unsupported drawing settings version")
    text(settings["title"], "Drawing title")
    require(settings["units"] in ("mm", "in"), "Drawing units must be mm or in")
    denominator = settings["fraction_denominator"]
    require(denominator is None or type(denominator) is int
            and denominator in (2, 4, 8, 16, 32, 64, 128), "Unsupported fraction denominator")
    require(type(settings["decimal_places"]) is int and 0 <= settings["decimal_places"] <= 6,
            "decimal_places must be an integer from 0 to 6")
    number(settings["scale_denominator"], "Scale denominator", minimum=1)
    sheet = settings["sheet"]
    fields(sheet, ("size", "orientation", "margin_mm", "columns", "rows"))
    require(isinstance(sheet["size"], str) and sheet["size"] in SIZES
            and sheet["orientation"] in ("portrait", "landscape"),
            "Unsupported sheet size/orientation")
    number(sheet["margin_mm"], "Sheet margin", minimum=5)
    for name in ("columns", "rows"):
        require(type(sheet[name]) is int and 1 <= sheet[name] <= 4, f"Invalid sheet {name}")
    fields(settings["style"], ("line_mm", "text_mm", "hatch_spacing_mm"))
    for name, value in settings["style"].items():
        number(value, name, positive=True)
    require(type(settings["schedule"]) is bool, "schedule must be a bool")
    require(isinstance(settings["views"], list) and settings["views"], "Select at least one view")
    seen = set()
    for view in settings["views"]:
        kind = view.get("kind") if isinstance(view, dict) else None
        required = ("id", "title", "kind")
        if kind == "projection":
            required += ("direction",)
        elif kind == "section":
            required += ("axis", "offset_mm")
        else:
            require(kind == "axonometric", "View kind must be projection, section or axonometric")
        fields(view, required, ("instances", "dimensions"))
        identifier(view["id"], "Drawing view id")
        text(view["title"], "View title")
        require(view["id"] not in seen, "Duplicate drawing view id")
        seen.add(view["id"])
        if kind == "projection":
            require(view["direction"] in ("top", "front", "right"), "Unsupported projection direction")
        elif kind == "section":
            require(view["axis"] in ("x", "y", "z"), "Section axis must be x, y or z")
            value = view["offset_mm"]
            require(type(value) in (int, float) and math.isfinite(value), "Section offset must be finite mm")
        require(type(view.get("dimensions", True)) is bool, "View dimensions must be a bool")
        if "instances" in view:
            require(isinstance(view["instances"], list) and view["instances"], "Select nonempty instances")
            for instance in view["instances"]:
                identifier(instance, "View instance")
            require(len(set(view["instances"])) == len(view["instances"]), "Duplicate view instance")
    return settings


def format_length(mm, settings):
    value = mm / 25.4 if settings["units"] == "in" else mm
    denominator = settings["fraction_denominator"] if settings["units"] == "in" else None
    if denominator:
        ticks = math.floor(abs(value) * denominator + .5)
        whole, numerator = divmod(ticks, denominator)
        sign = "-" if value < 0 and ticks else ""
        fraction = str(Fraction(numerator, denominator)) if numerator else ""
        label = f"{whole} {fraction}" if whole and numerator else str(whole) if not numerator else fraction
        return sign + label + '"'
    return f'{value:.{settings["decimal_places"]}f}' + ('"' if settings["units"] == "in" else " mm")


def label(x, y, value, size, anchor="start"):
    return (f'<text x="{x:.6f}" y="{y:.6f}" font-size="{size:.6f}" '
            f'text-anchor="{anchor}">{html.escape(str(value))}</text>')


def polygon_path(polygons):
    return " ".join("M " + " L ".join(f"{x:.6f},{-y:.6f}" for x, y in polygon) + " Z"
                    for polygon in polygons)


def project_view(view, solids):
    direction = ({"x": "right", "y": "front", "z": "top"}[view["axis"]]
                 if view["kind"] == "section" else view.get("direction", "axonometric"))
    basis = BASES[direction]
    selected = view.get("instances", list(solids))
    require(set(selected) <= solids.keys(), f"{view['id']}: unknown physical instance")
    contours, empty, areas = {}, [], {}
    for instance in selected:
        transformed = solids[instance].transform(np.column_stack((basis, np.zeros(3))).tolist())
        if view["kind"] == "section":
            offset = view["offset_mm"] * (-1 if view["axis"] == "y" else 1)
            section = transformed.slice(offset)
        else:
            section = transformed.project()
        polygons = [np.asarray(polygon) for polygon in section.to_polygons()]
        if polygons:
            contours[instance] = polygons
            areas[instance] = float(section.area())
        else:
            empty.append(instance)
    require(bool(contours), f"{view['id']}: selected view/section contains no geometry")
    points = np.vstack([polygon for polygons in contours.values() for polygon in polygons])
    bounds = np.array([points.min(axis=0), points.max(axis=0)])
    return contours, {"id": view["id"], "kind": view["kind"], "basis": basis.tolist(),
                      "bounds_mm": bounds.tolist(), "extents_mm": (bounds[1]-bounds[0]).tolist(),
                      "instances": selected, "uncut_instances": empty, "areas_mm2": areas}


def sheet_size(settings):
    width, height = SIZES[settings["sheet"]["size"]]
    return (height, width) if settings["sheet"]["orientation"] == "landscape" else (width, height)


def sheet_svg(content, settings, revision, page, *, scaled=True):
    width, height = sheet_size(settings)
    margin, size = settings["sheet"]["margin_mm"], settings["style"]["text_mm"]
    scale_label = f"1:{settings['scale_denominator']:g} at 100%" if scaled else "NTS"
    precision = (f"nearest 1/{settings['fraction_denominator']} inch"
                 if settings["units"] == "in" and settings["fraction_denominator"]
                 else f"{settings['decimal_places']} decimal places")
    caption = f"Revision {revision['id']} | Scale {scale_label} | Units {settings['units']} / {precision}"
    spacing = settings["style"]["hatch_spacing_mm"] * settings["scale_denominator"]
    hatch = (f'<defs><pattern id="cut" width="{spacing}" height="{spacing}" patternUnits="userSpaceOnUse">'
             f'<path d="M 0 {spacing} L {spacing} 0" stroke="#888" '
             f'stroke-width="{settings["style"]["line_mm"] * settings["scale_denominator"] / 2}"/>'
             '</pattern></defs>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" '
            f'viewBox="0 0 {width} {height}"><title>{html.escape(settings["title"])}</title>'
            '<style>text{font-family:Arial,sans-serif;fill:#222}path{stroke-linejoin:round}</style>'
            + hatch
            + label(margin, margin+size, settings["title"], size*1.3)
            + label(margin, margin+size*3, caption, size)
            + content
            + label(margin, height-margin-size*2,
                    "MESH-DERIVED CONCEPT / NOT FABRICATION APPROVAL. Print actual size; never fit to page.", size)
            + label(margin, height-margin,
                    f"Rounded labels are not tolerances. Projection outlines have no hidden-line removal. Sheet {page}.", size)
            + "</svg>")


def view_panel(view, contours, record, settings, index):
    sheet = settings["sheet"]
    width, height = sheet_size(settings)
    margin, size = sheet["margin_mm"], settings["style"]["text_mm"]
    cell_width = (width-2*margin) / sheet["columns"]
    cell_height = (height-2*margin-40) / sheet["rows"]
    require(cell_width > 35 and cell_height > 35, "Sheet layout leaves no usable drawing area")
    x = margin + index % sheet["columns"] * cell_width
    y = margin + 20 + index // sheet["columns"] * cell_height
    low, high = np.array(record["bounds_mm"])
    scale = 1 / settings["scale_denominator"]
    paper_size = (high-low) * scale
    require(np.all(paper_size <= [cell_width-30, cell_height-30]),
            f"{view['id']}: geometry does not fit at 1:{settings['scale_denominator']:g}; "
            "choose a larger sheet, fewer views per sheet or a larger scale denominator")
    center = (low+high)/2
    tx, ty = x+cell_width/2-center[0]*scale, y+cell_height/2+center[1]*scale
    result = label(x+3, y+size, view["title"], size)
    if view["kind"] == "section":
        result += label(x+3, y+size*2.3,
                        f"Cut {view['axis'].upper()}={format_length(view['offset_mm'], settings)}", size*.8)
    elif view["kind"] == "axonometric":
        result += label(x+3, y+size*2.3, "Axon +X/-Y/+Z; projected outlines, not hidden-line CAD", size*.8)
    else:
        axes = {"top": "X right / Y up", "front": "X right / Z up", "right": "Y right / Z up"}
        result += label(x+3, y+size*2.3, axes[view["direction"]], size*.8)
    stroke = settings["style"]["line_mm"] / scale
    for instance, polygons in contours.items():
        fill = "url(#cut)" if view["kind"] == "section" else "none"
        result += (f'<g transform="translate({tx:.6f} {ty:.6f}) scale({scale:.9f})">'
                   f'<path data-instance="{html.escape(instance, quote=True)}" d="{polygon_path(polygons)}" '
                   f'fill="{fill}" fill-rule="evenodd" stroke="#222" stroke-width="{stroke:.6f}"/></g>')
    if view.get("dimensions", True) and view["kind"] != "axonometric":
        left, right = tx+low[0]*scale, tx+high[0]*scale
        top, bottom = ty-high[1]*scale, ty-low[1]*scale
        result += (f'<path d="M {left:.6f} {bottom+4:.6f} H {right:.6f} '
                   f'M {right+4:.6f} {top:.6f} V {bottom:.6f}" fill="none" stroke="#555" '
                   f'stroke-width="{settings["style"]["line_mm"]:.6f}"/>')
        result += label((left+right)/2, bottom+4+size, format_length(high[0]-low[0], settings), size, "middle")
        result += (f'<g transform="translate({right+5:.6f} {(top+bottom)/2:.6f}) rotate(-90)">'
                   + label(0, 0, format_length(high[1]-low[1], settings), size, "middle") + "</g>")
    record.update(paper_extents_mm=paper_size.tolist(), model_to_paper=scale)
    return result


def schedule_rows(manifest, settings):
    rows = []
    for part in manifest["parts"]:
        instances = [item["id"] for item in manifest["instances"] if item["part_id"] == part["id"]]
        low, high = np.array(part["bounds_mm"])
        rows.append({"part_id": part["id"], "name": part["name"], "quantity": len(instances),
                     "material": part["material"], "notes": part["notes"],
                     "local_bounds": " x ".join(format_length(v, settings) for v in high-low)})
    return rows


def render_schedule(rows, settings, revision, start_page):
    width, height = sheet_size(settings)
    margin, size = settings["sheet"]["margin_mm"], settings["style"]["text_mm"]
    available = width-2*margin
    require(available > 80, "Sheet too narrow for the material schedule")
    positions = [margin, margin+available*.32, margin+available*.66, margin+available*.74]
    widths = [available*.30, available*.32, available*.07, available*.25]
    pages, content, y = [], "", margin+25
    for row in rows:
        cells = [row["name"], row["material"], str(row["quantity"]), row["local_bounds"]]
        lines = [textwrap.wrap(value, max(1, int(w/(size*.6)))) or [""]
                 for value, w in zip(cells, widths)]
        row_height = max(map(len, lines))*size*1.4+3
        require(row_height < height-2*margin-50, "Schedule row cannot fit on this sheet")
        if y+row_height > height-margin-20:
            pages.append(sheet_svg(content, settings, revision, start_page+len(pages), scaled=False))
            content, y = "", margin+25
        if not content:
            content = label(margin, margin+18, "PHYSICAL PART SCHEDULE / FULL ASSEMBLY / NTS", size)
            for position, title in zip(positions, ("Part", "Material (as recorded)", "Qty", "Local bounds")):
                content += label(position, y, title, size)
            y += size*2
        for position, values in zip(positions, lines):
            for line, value in enumerate(values):
                content += label(position, y+line*size*1.4, value, size)
        y += row_height
    if content:
        pages.append(sheet_svg(content, settings, revision, start_page+len(pages), scaled=False))
    return pages


def generate(project, *, settings_path=None, output=None, browser=None):
    project = Path(project).resolve()
    settings_path = Path(settings_path).resolve() if settings_path else project / "drawing-settings.json"
    raw = settings_path.read_bytes()
    settings = validate_settings(json.loads(raw))
    brief = json.loads((project / "design_brief.json").read_bytes())
    snapshot = make_snapshot(brief)
    require(snapshot is not None, "Drawings require a tracked, qualified project")
    geometry = project / "output"
    with writer(project):
        binding = source_binding(project)
        qualified_baseline(snapshot, geometry, binding, require_same_source=True)
        manifest = json.loads((geometry / "manifest.json").read_bytes())
        solids = {item["id"]: mesh_solid(trimesh.load_mesh(geometry / item["stl"]))
                  for item in manifest["instances"]}
        settings_hash = hashlib.sha256(raw).hexdigest()
        destination = (Path(output).resolve() if output else geometry / "drawings" /
                       f"{snapshot['identity']['id']}-{settings_hash[:12]}")
        require(not destination.exists(), "Drawing destination exists; choose a new --output folder to regenerate")
        require(not destination.is_relative_to(project / "cadkit"), "Drawing output cannot replace runtime source")
        pages, records = [], []
        count = settings["sheet"]["columns"] * settings["sheet"]["rows"]
        for start in range(0, len(settings["views"]), count):
            content = ""
            for index, view in enumerate(settings["views"][start:start+count]):
                contours, record = project_view(view, solids)
                content += view_panel(view, contours, record, settings, index)
                records.append(record)
            svg = sheet_svg(content, settings, snapshot["identity"], len(pages)+1)
            pages.append(svg)
        rows = schedule_rows(manifest, settings) if settings["schedule"] else []
        pages.extend(render_schedule(rows, settings, snapshot["identity"], len(pages)+1))
        width, height = sheet_size(settings)
        page_html = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>'
                     + html.escape(settings["title"]) + "</title><style>"
                     + f"@page{{size:{width}mm {height}mm;margin:0}}"
                     + "body{margin:0;background:#ddd}svg{display:block;background:white;break-after:page}"
                     + "svg:last-child{break-after:auto}</style><body>" + "".join(pages) + "</body></html>")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="cad-drawing-", dir=destination.parent) as directory:
            stage = Path(directory)
            for index, svg in enumerate(pages, 1):
                (stage / f"sheet-{index:02}.svg").write_text(svg, encoding="utf-8")
            (stage / "sheets.html").write_text(page_html, encoding="utf-8")
            stream = io.StringIO(newline="")
            csv_writer = csv.DictWriter(stream, fieldnames=(
                "part_id", "name", "quantity", "material", "notes", "local_bounds"))
            csv_writer.writeheader()
            csv_writer.writerows(rows)
            (stage / "schedule.csv").write_text(stream.getvalue(), encoding="utf-8")
            if browser:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as pw:
                    app = pw.chromium.launch(executable_path=str(browser), headless=True)
                    try:
                        page = app.new_page()
                        remote = []
                        page.on("request", lambda request: remote.append(request.url)
                                if request.url.startswith(("http:", "https:")) else None)
                        page.goto((stage / "sheets.html").as_uri())
                        require(not remote, "Drawing page attempted remote requests")
                        page.pdf(path=str(stage / "sheets.pdf"), prefer_css_page_size=True,
                                 print_background=True, scale=1)
                    finally:
                        app.close()
            qualified_baseline(snapshot, geometry, source_binding(project), require_same_source=True)
            require(settings_path.read_bytes() == raw, "Drawing settings changed during generation")
            require(canonical(json.loads((project / "design_brief.json").read_bytes())) == canonical(brief),
                    "Drawing source brief changed during generation")
            report = {"schema_version": 1, "revision": snapshot["identity"],
                      "manifest_sha256": sha256(geometry / "manifest.json"),
                      "validation_sha256": sha256(geometry / "validation.json"),
                      "settings_sha256": settings_hash, "settings": settings, "views": records,
                      "sheet_mm": [width, height], "schedule": rows,
                      "geometry_validation": json.loads((geometry / "validation.json").read_bytes())["status"],
                      "limits": "Concept projections/sections; no hidden-line removal, exact CAD or fabrication approval",
                      "files_sha256": {path.name: sha256(path) for path in sorted(stage.iterdir())}}
            (stage / "drawing-state.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            destination.mkdir()
            for path in stage.iterdir():
                shutil.move(str(path), str(destination / path.name))
    return destination


def verify(project, output, *, settings_path=None):
    project, output = Path(project).resolve(), Path(output).resolve()
    settings_path = Path(settings_path).resolve() if settings_path else project / "drawing-settings.json"
    report = json.loads((output / "drawing-state.json").read_bytes())
    snapshot = make_snapshot(json.loads((project / "design_brief.json").read_bytes()))
    require(snapshot is not None and report["revision"] == snapshot["identity"], "Drawing revision is stale")
    geometry = project / "output"
    qualified_baseline(snapshot, geometry, source_binding(project), require_same_source=True)
    require(report["manifest_sha256"] == sha256(geometry / "manifest.json") and
            report["validation_sha256"] == sha256(geometry / "validation.json"), "Drawing geometry binding is stale")
    require(report["settings_sha256"] == sha256(settings_path) and
            report["settings"] == validate_settings(json.loads(settings_path.read_bytes())),
            "Drawing settings are stale")
    files = {path.name: sha256(path) for path in output.iterdir()
             if path.is_file() and path.name != "drawing-state.json"}
    require(files == report["files_sha256"], "Drawing artifacts are missing, changed or unlisted")
    return {"status": "verified_concept", "revision": report["revision"], "output": str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--settings", type=Path)
    parser.add_argument("--output", type=Path, help="New destination; existing files are never overwritten")
    parser.add_argument("--browser", type=Path, help="Optional Chromium/Edge PDF export; requires Playwright")
    parser.add_argument("--verify", type=Path, help="Verify an existing drawing folder against current source/settings")
    args = parser.parse_args()
    try:
        if args.verify:
            require(args.output is None and args.browser is None, "--verify cannot generate or export PDF")
            print(json.dumps(verify(args.project, args.verify, settings_path=args.settings)))
            return
        output = generate(args.project, settings_path=args.settings, output=args.output, browser=args.browser)
    except (OSError, ValueError, ImportError) as error:
        parser.error(str(error))
    print(json.dumps({"event": "cadkit.drawings_ready", "stage": "concept_not_fabrication",
                      "output": str(output), "state": str(output / "drawing-state.json")}))


if __name__ == "__main__":
    main()
