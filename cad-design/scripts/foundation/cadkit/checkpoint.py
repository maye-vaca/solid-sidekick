"""Render two or four comparable 2D interpretations without changing CAD geometry."""

import argparse
import html
import json
import math
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def point(value):
    require(isinstance(value, list) and len(value) == 2
            and all(type(v) in (int, float) and math.isfinite(v) for v in value),
            "Sketch points must contain two finite numbers in mm")
    return value


def text(value):
    require(isinstance(value, str) and value.strip(), "Sketch labels must be nonempty text")
    return html.escape(value)


def render(proposal):
    require(isinstance(proposal, dict) and set(proposal) == {
        "schema_version", "question", "view", "bounds_mm", "fixed", "options"}, "Invalid checkpoint fields")
    require(type(proposal["schema_version"]) is int and proposal["schema_version"] == 1,
            "Unsupported checkpoint version")
    question, view = text(proposal["question"]), text(proposal["view"])
    bounds = proposal["bounds_mm"]
    require(isinstance(bounds, list) and len(bounds) == 2, "Sketch requires shared 2D bounds")
    low, high = point(bounds[0]), point(bounds[1])
    require(all(a < b for a, b in zip(low, high)), "Sketch bounds must have positive extent")
    span = max(b-a for a, b in zip(low, high))
    require(isinstance(proposal["fixed"], list) and proposal["fixed"], "Label the fixed features")
    fixed = "".join("<li>" + text(item) + "</li>" for item in proposal["fixed"])
    options = proposal["options"]
    require(isinstance(options, list) and len(options) in (2, 4), "Provide two or four lightweight alternatives")
    panels = []
    for option, expected in zip(options, ("A", "B", "C", "D")):
        require(isinstance(option, dict) and set(option) == {
            "id", "title", "material", "voids", "labels"} and option["id"] == expected,
            "Alternatives must be labeled A/B or A/B/C/D in order, with title, material, voids and labels")
        svg = ""
        for name, fill in (("material", "#cbd9e5"), ("voids", "white")):
            polygons = option[name]
            require(isinstance(polygons, list) and (polygons or name == "voids"),
                    "Show material polygons and an explicit void list")
            for polygon in polygons:
                require(isinstance(polygon, list) and len(polygon) >= 3, "A polygon needs at least three points")
                points = [point(p) for p in polygon]
                require(all(all(a <= v <= b for a, v, b in zip(low, p, high)) for p in points),
                        "Sketch geometry must fit the common bounds")
                coordinates = " ".join(f"{x},{-y}" for x, y in points)
                svg += f'<polygon points="{coordinates}" fill="{fill}" stroke="#222" stroke-width="{span/400}"/>'
        require(isinstance(option["labels"], list) and option["labels"], "Label endpoints/dimensions")
        for annotation in option["labels"]:
            require(isinstance(annotation, dict) and set(annotation) == {"at", "text"}, "Invalid sketch annotation")
            x, y = point(annotation["at"])
            require(all(a <= v <= b for a, v, b in zip(low, (x, y), high)), "Label lies outside shared bounds")
            svg += f'<text x="{x}" y="{-y}" font-size="{span/45}">{text(annotation["text"])}</text>'
        panels.append(f'<section><h2>{expected}: {text(option["title"])}</h2>'
                      f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{low[0]} {-high[1]} '
                      f'{high[0]-low[0]} {high[1]-low[1]}">{svg}</svg></section>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Interpretation checkpoint</title>'
            '<style>body{font-family:Arial,sans-serif;margin:24px}main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}'
            'section{min-width:0;display:grid;grid-template-rows:subgrid;grid-row:span 2}h2{margin:0;overflow-wrap:anywhere}svg{display:block;box-sizing:border-box;width:100%;height:auto;background:#fafafa;border:1px solid #ccc}'
            'text{font-family:Arial,sans-serif}@media(max-width:650px){main{grid-template-columns:1fr}}</style><body>'
            f'<h1>{question}</h1><p>Alternatives only / {view} / same mm frame and scale.</p>'
            '<p>Blue = material; white = void. No detailed CAD model built or selected.</p>'
            f'<main>{"".join(panels)}</main><h2>Fixed in all alternatives</h2><ul>{fixed}</ul>'
            f'<p>Choose {"A or B" if len(options) == 2 else "A, B, C or D"} in the host conversation. The agent must wait; this page cannot approve or revise a model.</p>'
            '</body></html>')


def write(project, proposal_path, output=None):
    project = Path(project).resolve()
    exploration = project / "exploration"
    proposal_path = Path(proposal_path).resolve()
    output = Path(output).resolve() if output else exploration / "interpretation-choice.html"
    require(proposal_path.is_relative_to(exploration) and output.is_relative_to(exploration),
            "Checkpoint input/output must stay under project exploration, separate from accepted files")
    content = render(json.loads(proposal_path.read_bytes()))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as file:
        file.write(content)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        output = write(args.project, args.input, args.output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({"event": "cadkit.interpretation_checkpoint", "status": "awaiting_selection",
                      "page": str(output), "model_changed": False}))


if __name__ == "__main__":
    main()
