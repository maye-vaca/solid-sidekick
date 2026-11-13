"""Checked prototype instructions and translational assembly storyboards."""

import argparse
import csv
import hashlib
import html
import io
from itertools import combinations
import json
from pathlib import Path
import shutil
import tempfile

import manifold3d as m
import numpy as np
import trimesh

from .drawing import fields
from .incremental import qualified_baseline, source_binding, writer
from .revision import canonical, identifier, make_snapshot, sha256, text
from .review import read_packet
from .scene import script_json
from .validation import mesh_solid, require
from .viewer import HTML


LIMITS = ("Prototype only: conservative convex swept envelopes for straight translations; "
          "stationary placement steps do not verify insertion. No rotation paths, threads, "
          "tool access, deformation, forces, hardware tolerances or fabrication approval.")


def vector(value):
    require(isinstance(value, list) and len(value) == 3
            and all(type(v) in (int, float) and np.isfinite(v) for v in value),
            "Assembly offsets must contain three finite mm numbers")
    return value


def ids(value, known):
    require(isinstance(value, list) and value and all(isinstance(v, str) for v in value)
            and len(set(value)) == len(value) and set(value) <= known,
            "Assembly members must be unique known instance IDs")
    return value


def validate_plan(plan, identity, known, facts=()):
    fields(plan, ("schema_version", "revision", "title", "source", "items",
                  "context_instances", "steps", "limitations"))
    require(type(plan["schema_version"]) is int and plan["schema_version"] == 1,
            "Unsupported construction plan version")
    require(plan["revision"] == identity, "Construction plan revision is stale")
    for key in ("title", "source"):
        text(plan[key], key)
    require(isinstance(plan["limitations"], list) and plan["limitations"],
            "Declare construction uncertainties")
    for note in plan["limitations"]:
        text(note, "Construction limitation")
    context = plan["context_instances"]
    require(isinstance(context, list) and all(isinstance(v, str) for v in context)
            and len(set(context)) == len(context) and set(context) <= known,
            "Invalid context instances")
    covered, item_ids = set(context), set()
    require(isinstance(plan["items"], list) and plan["items"], "Declare the parts inventory")
    for item in plan["items"]:
        fields(item, ("id", "description", "units", "source", "notes"), ("dimension_keys",))
        identifier(item["id"], "Inventory id")
        require(item["id"] not in item_ids, "Duplicate inventory id")
        item_ids.add(item["id"])
        for key in ("description", "source"):
            text(item[key], key)
        require(isinstance(item["notes"], str), "Inventory notes must be text")
        keys = item.get("dimension_keys", [])
        require(isinstance(keys, list) and all(isinstance(k, str) for k in keys)
                and len(set(keys)) == len(keys) and set(keys) <= set(facts),
                "Inventory dimensions must reference current named facts")
        require(isinstance(item["units"], list) and item["units"], "Inventory units are required")
        for unit in item["units"]:
            members = ids(unit, known)
            require(not covered.intersection(members), "Inventory/context members overlap")
            covered.update(members)
    require(covered == known, "Every instance needs an inventory unit or explicit context exclusion")
    require(isinstance(plan["steps"], list) and plan["steps"], "Declare assembly steps")
    seen = set()
    for step in plan["steps"]:
        fields(step, ("id", "title", "instruction", "source", "moving", "from_mm", "to_mm"))
        identifier(step["id"], "Assembly step id")
        require(step["id"] not in seen, "Duplicate assembly step id")
        seen.add(step["id"])
        for key in ("title", "instruction", "source"):
            text(step[key], key)
        ids(step["moving"], known)
        vector(step["from_mm"])
        vector(step["to_mm"])
    require(any(step["from_mm"] != step["to_mm"] for step in plan["steps"]),
            "Publication requires a declared translational assembly-access step, not only static poses")
    return plan


def check_steps(plan, solids):
    poses, records = {}, []
    for step in plan["steps"]:
        moving, start, end = set(step["moving"]), step["from_mm"], step["to_mm"]
        sweep_pairs = 0
        for name in moving:
            require(name not in poses or poses[name] == start,
                    f"{step['id']}: {name} start does not match its preceding pose")
        # Hulls conservatively cover every point in a straight translation.
        sweeps = {name: solids[name].translate(start) if start == end else
                  m.Manifold.batch_hull([solids[name].translate(start), solids[name].translate(end)])
                  for name in sorted(moving)}
        for name, sweep in sweeps.items():
            for fixed, offset in sorted(poses.items()):
                if fixed not in moving:
                    if start != end:
                        sweep_pairs += 1
                    volume = float((sweep ^ solids[fixed].translate(offset)).volume())
                    require(volume <= .01,
                            f"{step['id']}: blocked assembly access {name}/{fixed}: {volume} mm^3")
        poses.update({name: end for name in moving})
        for first, second in combinations(sorted(poses), 2):
            volume = float((solids[first].translate(poses[first]) ^
                            solids[second].translate(poses[second])).volume())
            require(volume <= .01,
                    f"{step['id']}: assembly pose interference {first}/{second}: {volume} mm^3")
        records.append({"id": step["id"], "check": "static placement" if start == end else
                        "conservative straight-translation sweep", "sweep_pairs": sweep_pairs,
                        "status": "passed"})
    require(set(poses) == set(solids) and all(offset == [0, 0, 0] for offset in poses.values()),
            "Assembly sequence must introduce every instance and end at the checked final pose")
    return records


def checked_inputs(project, geometry, plan_path):
    for path in Path(__file__).parent.glob("*.py"):
        require(sha256(path) == sha256(project / "cadkit" / path.name),
                "Construction must execute the exact qualified project runtime")
    brief = json.loads((project / "design_brief.json").read_bytes())
    snapshot = make_snapshot(brief)
    require(snapshot is not None, "Construction requires a tracked design")
    qualified_baseline(snapshot, geometry, source_binding(project), require_same_source=True)
    validation = json.loads((geometry / "validation.json").read_bytes())
    require(validation["status"] == "passed", "Construction publication requires real browser qualification")
    manifest = json.loads((geometry / "manifest.json").read_bytes())
    packet = read_packet(geometry / "review-state.json")
    require(packet["current"]["snapshot"] == snapshot, "Construction review is stale")
    solids = {item["id"]: mesh_solid(trimesh.load_mesh(geometry / item["stl"]))
              for item in manifest["instances"]}
    plan = validate_plan(json.loads(plan_path.read_bytes()), snapshot["identity"], set(solids),
                         snapshot["brief"]["dimensions"])
    checks = check_steps(plan, solids)
    require(any(check["sweep_pairs"] > 0 for check in checks),
            "Assembly access must be checked against previously introduced obstacles")
    return snapshot, packet["current"]["scene"], plan, checks


PRESENTATION = r'''
<style>
header,.toolbar,aside{display:none}main{display:block;padding:0}
.viewport{height:100vh;min-height:0;border:0}
#construction-caption{position:fixed;bottom:0;left:0;right:0;background:#101923e8;
padding:12px 20px;pointer-events:none}
#construction-title{position:fixed;top:0;left:0;right:0;background:#101923e8;padding:12px 20px}
#construction-play{position:fixed;top:54px;left:20px}
</style>
<div id="construction-title"></div><div id="construction-caption"></div>
<button id="construction-play">Play assembly</button>
<script id="construction-plan" type="application/json">__PLAN__</script>
<script>
const assemblyPlan=JSON.parse(document.getElementById("construction-plan").textContent);
const originalVertices=parts.map(p=>{
 const raw=atob(model.parts.find(x=>x.name===p.name).vertices);
 return new Float32Array(Uint8Array.from(raw,c=>c.charCodeAt(0)).buffer);
});
document.getElementById("construction-title").textContent=assemblyPlan.title+
" | "+assemblyPlan.revision.id+" | Prototype; no physical approval";
let started=null,finished=false;
function animate(now){
 const elapsed=Math.max(0,(now-started)/1000),index=Math.min(Math.floor(elapsed/4),assemblyPlan.steps.length-1);
 const step=assemblyPlan.steps[index],progress=Math.min(1,(elapsed-index*4)/4),positions={};
 for(let i=0;i<index;i++)for(const name of assemblyPlan.steps[i].moving)
   positions[name]=assemblyPlan.steps[i].to_mm;
 for(const name of step.moving)positions[name]=step.from_mm.map((v,a)=>v+
   (step.to_mm[a]-v)*progress);
 for(let i=0;i<parts.length;i++){
   const p=parts[i],offset=positions[p.physical_instance_id||p.name];p.visible=!!offset;
   if(offset){const v=originalVertices[i].slice();
     for(let j=0;j<v.length;j+=6)for(let a=0;a<3;a++)v[j+a]+=offset[a]/model.scale_mm;
     gl.bindBuffer(gl.ARRAY_BUFFER,p.buffer);gl.bufferData(gl.ARRAY_BUFFER,v,gl.STATIC_DRAW);
   }
 }
 document.getElementById("construction-caption").textContent=step.title+": "+step.instruction+
 (step.from_mm.every((v,i)=>v===step.to_mm[i])?" [Static placement; insertion not checked]":"");
 draw();
 if(elapsed<assemblyPlan.steps.length*4)requestAnimationFrame(animate);else finished=true;
}
window.cadConstructionPresentation={start:()=>{
 if(started!==null)throw Error("Presentation already started");
 document.getElementById("construction-play").hidden=true;
 started=performance.now();requestAnimationFrame(animate);
},getState:()=>({started:started!==null,finished,revision:assemblyPlan.revision})};
document.getElementById("construction-play").onclick=()=>cadConstructionPresentation.start();
for(const p of parts)p.visible=false;
center=assemblyPlan.display_bounds_mm[0].map((v,a)=>
 ((v+assemblyPlan.display_bounds_mm[1][a])/2-assemblyPlan.origin_mm[a])/model.scale_mm);
span=Math.hypot(...assemblyPlan.display_bounds_mm[1].map((v,a)=>
 (v-assemblyPlan.display_bounds_mm[0][a])/model.scale_mm))*1.12;draw();
</script>
'''


def storyboard(scene, plan):
    model = dict(parts=scene["parts"], title=scene["title"], units="mm",
                 extent=np.subtract(*scene["bounds_mm"][::-1]).tolist(),
                 scale_mm=scene["scale_mm"], coordinateSystem=scene["coordinate_system"],
                 explicitMetadata=True, assumptions=scene["assumptions"])
    offsets = np.array([[0, 0, 0]] + [step[key] for step in plan["steps"]
                                    for key in ("from_mm", "to_mm")])
    display = dict(plan, origin_mm=scene["origin_mm"], display_bounds_mm=[
        (np.array(scene["bounds_mm"][0])+offsets.min(axis=0)).tolist(),
        (np.array(scene["bounds_mm"][1])+offsets.max(axis=0)).tolist()])
    extra = PRESENTATION.replace("__PLAN__", script_json(display))
    return HTML.replace("__MODEL__", script_json(model)).replace("</body>", extra + "</body>")


def item_dimensions(item, brief):
    return "; ".join(f"{key}: {brief['dimensions'][key]['value']} "
                     f"{brief['dimensions'][key]['unit']} ({brief['dimensions'][key]['status']})"
                     for key in item.get("dimension_keys", []))


def guide(plan, brief):
    identity = plan["revision"]
    escape = html.escape
    rows = "".join(f"<tr><td>{len(item['units'])}</td><td>{escape(item['description'])}</td>"
                   f"<td>{escape(item_dimensions(item, brief))}</td>"
                   f"<td>{escape(item['notes'])}</td></tr>" for item in plan["items"])
    steps = "".join(f"<li><strong>{escape(step['title'])}</strong>: {escape(step['instruction'])}"
                    f" <small>({'Static placement; insertion not checked' if step['from_mm'] == step['to_mm'] else 'Conservative translation check'})</small></li>"
                    for step in plan["steps"])
    return ("<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{escape(plan['title'])}</title><body><h1>{escape(plan['title'])}</h1>"
            f"<p>Construction revision {escape(identity['id'])} / {identity['brief_sha256']}</p>"
            f"<p>{LIMITS}</p><table><tr><th>Qty units/sets</th><th>Item</th>"
            f"<th>Current dimension facts</th><th>Notes</th></tr>{rows}</table>"
            f"<ol>{steps}</ol><h2>Uncertainties</h2><ul>" +
            "".join(f"<li>{escape(note)}</li>" for note in plan["limitations"]) +
            "</ul><p>Use review.html for this revision; review-handoff.json stages it in an "
            "existing compatible page. Only the user chooses Apply.</p></body></html>")


def generate(project, plan_path, output, *, geometry=None, browser=None):
    project, plan_path, output = map(lambda p: Path(p).resolve(), (project, plan_path, output))
    geometry = Path(geometry).resolve() if geometry else project / "output"
    require(not output.exists() and not output.is_symlink(), "Choose a new construction destination")
    with writer(project):
        raw = plan_path.read_bytes()
        binding = source_binding(project)
        snapshot, scene, plan, checks = checked_inputs(project, geometry, plan_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="cad-construction-", dir=output.parent) as directory:
            stage = Path(directory)
            (stage / "guide.html").write_text(guide(plan, snapshot["brief"]), encoding="utf-8")
            stream = io.StringIO(newline="")
            csv_writer = csv.writer(stream)
            csv_writer.writerow(("id", "description", "quantity_units", "dimension_facts", "source", "notes"))
            for item in plan["items"]:
                values = [item["id"], item["description"], len(item["units"]),
                          item_dimensions(item, snapshot["brief"]), item["source"], item["notes"]]
                csv_writer.writerow(["'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@"))
                                     else v for v in values])
            (stage / "parts.csv").write_bytes(stream.getvalue().encode("utf-8"))
            (stage / "assembly.html").write_text(storyboard(scene, plan), encoding="utf-8")
            for name in ("review.html", "review-state.json"):
                shutil.copyfile(geometry / name, stage / name)
            packet_json = (stage / "review-state.json").read_text(encoding="utf-8")
            handoff = {"event": "cadkit.revision_handoff", "status": "verified",
                       "validation_status": "passed", "revision": snapshot["identity"],
                       "review_packet_json": packet_json,
                       "review_packet_sha256": hashlib.sha256(packet_json.encode("utf-8")).hexdigest()}
            (stage / "review-handoff.json").write_text(json.dumps(handoff, indent=2), encoding="utf-8")
            if browser:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as pw:
                    app = pw.chromium.launch(executable_path=str(browser), headless=True,
                                            args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
                    errors, remote = [], []
                    try:
                        context = app.new_context(viewport={"width": 1280, "height": 720},
                                                  record_video_dir=str(stage / "recording"),
                                                  record_video_size={"width": 1280, "height": 720})
                        page = context.new_page()
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        page.on("request", lambda request: remote.append(request.url)
                                if request.url.startswith(("http:", "https:")) else None)
                        page.goto((stage / "assembly.html").as_uri())
                        page.evaluate("cadConstructionPresentation.start()")
                        page.wait_for_function("cadConstructionPresentation.getState().finished || "
                                               "!document.getElementById('error').hidden",
                                               timeout=len(plan["steps"])*4000+30000)
                        require(not errors and not remote, f"Assembly recording failed: {errors}, {remote}")
                        page.screenshot(path=str(stage / "assembly-final.png"))
                        context.close()
                        page.video.save_as(str(stage / "assembly.webm"))
                        shutil.rmtree(stage / "recording")
                        playback = app.new_page()
                        playback.goto((stage / "assembly.html").as_uri())
                        metadata = playback.evaluate("""()=>new Promise((resolve,reject)=>{
                          const v=document.createElement('video');v.src='assembly.webm';
                          v.onloadedmetadata=()=>resolve({width:v.videoWidth,height:v.videoHeight,duration:v.duration});
                          v.onerror=()=>reject(Error('Recorded video could not be decoded'));
                        })""")
                        require(metadata["width"] == 1280 and metadata["height"] == 720
                                and metadata["duration"] >= len(plan["steps"])*4,
                                "Recorded video metadata does not cover the assembly sequence")
                        (stage / "video-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
                    finally:
                        app.close()
            qualified_baseline(snapshot, geometry, source_binding(project), require_same_source=True)
            require(binding == source_binding(project) and raw == plan_path.read_bytes()
                    and make_snapshot(json.loads((project / "design_brief.json").read_bytes())) == snapshot,
                    "Construction source changed during publication")
            report = {"schema_version": 1, "revision": snapshot["identity"], "plan": plan,
                      "plan_sha256": hashlib.sha256(raw).hexdigest(), "source_binding": binding,
                      "geometry_sha256": {name: sha256(geometry / name) for name in
                                          ("manifest.json", "validation.json", "review.html", "review-state.json")},
                      "checks": checks, "limits": LIMITS,
                      "files_sha256": {p.name: sha256(p) for p in stage.iterdir() if p.is_file()}}
            (stage / "construction-state.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            output.mkdir()
            for path in stage.iterdir():
                shutil.move(str(path), str(output / path.name))
    return output


def verify(project, plan_path, output, *, geometry=None):
    project, plan_path, output = map(lambda p: Path(p).resolve(), (project, plan_path, output))
    geometry = Path(geometry).resolve() if geometry else project / "output"
    report = json.loads((output / "construction-state.json").read_bytes())
    snapshot, _, plan, checks = checked_inputs(project, geometry, plan_path)
    require(report["revision"] == snapshot["identity"] and report["plan"] == plan
            and report["plan_sha256"] == sha256(plan_path) and report["checks"] == checks
            and report["source_binding"] == source_binding(project), "Construction receipt is stale")
    require(report["geometry_sha256"] == {name: sha256(geometry / name) for name in
                                         ("manifest.json", "validation.json", "review.html", "review-state.json")},
            "Construction geometry binding changed")
    require({p.name: sha256(p) for p in output.iterdir() if p.is_file()
             and p.name != "construction-state.json"} == report["files_sha256"],
            "Construction deliverables changed, missing or unlisted")
    require(all(p.is_file() for p in output.iterdir()), "Unlisted construction subdirectory")
    return {"status": "verified_prototype", "revision": snapshot["identity"], "limits": LIMITS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--geometry", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--browser", type=Path, help="Record the generated storyboard as WebM")
    args = parser.parse_args()
    try:
        if args.verify:
            require(args.output is None and args.browser is None, "--verify does not publish/record")
            result = verify(args.project, args.plan, args.verify, geometry=args.geometry)
        else:
            require(args.output is not None, "Select a new --output destination")
            result = {"status": "published_prototype",
                      "output": str(generate(args.project, args.plan, args.output,
                                             geometry=args.geometry, browser=args.browser))}
        print(json.dumps(result))
    except (OSError, ValueError, ImportError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
