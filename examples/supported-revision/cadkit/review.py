"""Offline current/prior review, using the existing lightweight renderer."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import trimesh

from .revision import canonical, sha256, validate_snapshot, verify_export
from .scene import packed_geometry, script_json
from .viewer import HTML


BRIDGE = r'''
<script>
let quiet=false,initialized=false;
function reviewState(){const f=model.reviewFrame;return {
 camera:{yaw,pitch,center_mm:center.map((v,i)=>v*f.scale_mm+f.origin_mm[i]),
 span_mm:span*f.scale_mm,zoom,pan:[...pan]},
 visibility:Object.fromEntries(parts.map(p=>[p.name,p.visible])),
 selected:selected<0?null:parts[selected].name,interacting:!!drag};}
const originalDraw=draw;
draw=function(){originalDraw();if(initialized&&!quiet)parent.postMessage({
 kind:"cad-review-state",revision:model.reviewIdentity,state:reviewState()},"*");};
window.addEventListener("message",e=>{
 if(e.source!==parent||e.data?.kind!=="cad-review-apply"||e.data.revision!==model.reviewIdentity)return;
 const s=e.data.state,f=model.reviewFrame;quiet=true;
 try{if(s.camera){const c=s.camera;yaw=c.yaw;pitch=c.pitch;
 center=c.center_mm.map((v,i)=>(v-f.origin_mm[i])/f.scale_mm);
 span=c.span_mm/f.scale_mm;zoom=c.zoom;pan=[...c.pan];}
 for(let i=0;i<parts.length;i++){
 parts[i].visible=s.visibility?.[parts[i].name]??true;
 parts[i].checkbox.checked=parts[i].visible;
 parts[i].row.classList.toggle("selected",s.selected===parts[i].name);}
 selected=parts.findIndex(p=>p.name===s.selected);draw();initialized=true;
 }finally{quiet=false;}
});
for(const name of ["pointerdown","pointerup","pointercancel","lostpointercapture"])
 canvas.addEventListener(name,()=>{if(initialized)parent.postMessage({
 kind:"cad-review-state",revision:model.reviewIdentity,state:reviewState()},"*");});
parent.postMessage({kind:"cad-review-ready",revision:model.reviewIdentity},"*");
</script>
'''


PAGE = r'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CAD revision review</title>
<style>
body{margin:0;background:#101923;color:#edf3f7;font:14px system-ui}header{padding:14px}
button,input{font:inherit;margin:4px;padding:7px}#message{color:#ffd080;white-space:pre-wrap}
.views{display:grid;grid-template-columns:1fr 1fr}iframe{width:100%;height:800px;border:1px solid #58758b}
h2{font-size:16px;padding:8px;margin:0}p{margin:6px 0}
@media(max-width:900px){.views{grid-template-columns:1fr}}
</style><header><h1>CAD revision review</h1><p id="identity"></p>
<p>Snapshot review in mm, not live validation or fabrication approval.
Current is unchecked at export. Reload or load a newer review-state.json to refresh.</p>
<button id="front">Compare front</button><button id="top">Compare top</button>
<button id="side">Compare side</button><button id="iso">Compare isometric</button>
<label>Load newer review <input id="load" type="file" accept=".json"></label>
<button id="apply" disabled>Apply newer revision</button>
<p id="message" role="status"></p></header>
<div class="views"><section><h2 id="current-label"></h2>
<iframe id="current" name="current" sandbox="allow-scripts" title="Current revision"></iframe></section>
<section><h2 id="previous-label"></h2>
<iframe id="previous" name="previous" sandbox="allow-scripts" title="Prior revision"></iframe></section></div>
<script id="review-data" type="application/json">__PACKET__</script>
<script id="renderer" type="application/json">__RENDERER__</script>
<script id="bridge" type="application/json">__BRIDGE__</script>
<script>
"use strict";
const el=id=>document.getElementById(id),frames=["current","previous"];
let active=null,pending=null,view=null,interacting=new Set(),blocked=false,lastSeen=null;
const key="cad-review-ui:"+location.href.split("#")[0];
function notice(s){el("message").textContent=s;}
const safeJSON=x=>JSON.stringify(x).replaceAll("<","\\u003c").replaceAll(">","\\u003e").replaceAll("&","\\u0026");
async function decode(packet){
 if(packet.schema_version!==1||typeof packet.payload!=="string")throw Error("Invalid review packet");
 const bytes=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(packet.payload));
 const hash=Array.from(new Uint8Array(bytes),v=>v.toString(16).padStart(2,"0")).join("");
 if(hash!==packet.sha256)throw Error("Review payload hash mismatch");
 const data=JSON.parse(packet.payload);
 if(data.schema_version!==1||!data.current?.snapshot?.identity||!data.frame?.scale_mm)throw Error("Invalid review state");
 const vector=x=>Array.isArray(x)&&x.length===3&&x.every(Number.isFinite);
 const bounds=x=>Array.isArray(x)&&x.length===2&&x.every(vector);
 if(!vector(data.frame.origin_mm)||!bounds(data.frame.bounds_mm)||!Number.isFinite(data.frame.scale_mm)||data.frame.scale_mm<=0)throw Error("Invalid comparison frame");
 for(const d of [data.current,data.previous].filter(Boolean)){
 if(d.scene.coordinate_system!==data.current.scene.coordinate_system)throw Error("Incompatible coordinate frames");
 const identity=d.snapshot.identity,brief=d.snapshot.brief;
 const canonical=x=>Array.isArray(x)?x.map(canonical):x&&typeof x==="object"?
 Object.fromEntries(Object.keys(x).sort().map(k=>[k,canonical(x[k])])):x;
 if(identity.id!==brief.revision.id||!Array.isArray(brief.revision.ancestors))throw Error("Invalid revision identity");
 const briefBytes=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(d.brief_json));
 const briefHash=Array.from(new Uint8Array(briefBytes),v=>v.toString(16).padStart(2,"0")).join("");
 if(briefHash!==identity.brief_sha256||JSON.stringify(canonical(JSON.parse(d.brief_json)))!==JSON.stringify(canonical(brief)))throw Error("Brief identity hash mismatch");
 if(!Number.isFinite(d.scene.scale_mm)||d.scene.scale_mm<=0)throw Error("Invalid geometry scale");
 if(!vector(d.scene.origin_mm)||!bounds(d.scene.bounds_mm)||!Array.isArray(d.scene.parts)||!d.scene.parts.length)throw Error("Invalid scene bounds");
 const ids=new Set();
 for(const p of d.scene.parts){
 if(typeof p.vertices!=="string"||!p.name||ids.has(p.name))throw Error("Invalid review mesh");
 ids.add(p.name);const raw=atob(p.vertices);
 if(!Number.isInteger(p.triangles)||p.triangles<=0||raw.length!==p.triangles*72)throw Error("Invalid mesh byte count");
 const values=new Float32Array(Uint8Array.from(raw,c=>c.charCodeAt(0)).buffer);
 if(!values.every(Number.isFinite)||!p.bounds.flat().every(Number.isFinite))throw Error("Nonfinite review geometry");
 }
 }
 if(data.previous&&!data.current.snapshot.brief.revision.ancestors.includes(data.previous.snapshot.identity.id))throw Error("Review reference is not a prior ancestor");
 const scenes=[data.current,data.previous].filter(Boolean).map(d=>d.scene);
 const low=[0,1,2].map(a=>Math.min(...scenes.map(s=>s.bounds_mm[0][a])));
 const high=[0,1,2].map(a=>Math.max(...scenes.map(s=>s.bounds_mm[1][a])));
 if(low.some((x,a)=>x!==data.frame.bounds_mm[0][a]||(x+high[a])/2!==data.frame.origin_mm[a])||
 high.some((x,a)=>x!==data.frame.bounds_mm[1][a])||Math.max(...high.map((x,a)=>x-low[a]))!==data.frame.scale_mm)throw Error("Comparison frame does not match review geometry");
 return data;
}
function persist(){
 try{sessionStorage.setItem(key,JSON.stringify({view,identity:active.current.snapshot.identity,
 ancestors:active.current.snapshot.brief.revision.ancestors}));}
 catch(e){notice("UI state could not be saved: "+e.message);}
}
function send(id){if(view&&active[id])el(id).contentWindow.postMessage({
 kind:"cad-review-apply",revision:active[id].snapshot.identity.brief_sha256,state:view},"*");}
function modelFor(d,frame){
 const s=d.scene;
 const parts=s.parts.map(p=>{
 const raw=atob(p.vertices),bytes=Uint8Array.from(raw,c=>c.charCodeAt(0)),v=new Float32Array(bytes.buffer);
 for(let i=0;i<v.length;i+=6)for(let a=0;a<3;a++)v[i+a]=(v[i+a]*s.scale_mm+s.origin_mm[a]-frame.origin_mm[a])/frame.scale_mm;
 const out=new Uint8Array(v.buffer);let binary="";
 for(let i=0;i<out.length;i+=8192)binary+=String.fromCharCode(...out.subarray(i,i+8192));
 return {...p,vertices:btoa(binary),bounds:p.bounds.map(b=>b.map((x,a)=>(x*s.scale_mm+s.origin_mm[a]-frame.origin_mm[a])/frame.scale_mm))};
 });
 return {parts,extent:[frame.scale_mm,frame.scale_mm,frame.scale_mm],title:s.title,units:"mm",
 coordinateSystem:s.coordinate_system,assumptions:s.assumptions,explicitMetadata:true,reviewFrame:frame,
 reviewIdentity:d.snapshot.identity.brief_sha256};
}
function resetCamera(preset="front"){
 if(blocked){notice("Older snapshot remains blocked. Load a newer descendant review first.");return;}
 const [yaw,pitch]=({front:[Math.PI,0],top:[Math.PI,Math.PI/2],side:[Math.PI/2,0],iso:[Math.PI-.5,.85]})[preset];
 view={...(view||{}),camera:{yaw,pitch,center_mm:[...active.frame.origin_mm],
 span_mm:Math.hypot(...active.frame.bounds_mm[1].map((x,i)=>x-active.frame.bounds_mm[0][i]))*1.12,
 zoom:1,pan:[0,0]}};
 frames.forEach(send);persist();
}
function render(data){
 active=data;blocked=false;interacting.clear();
 const identity=data.current.snapshot.identity;
 lastSeen=identity;
 el("identity").textContent="Current revision: "+identity.id+" / "+identity.brief_sha256.slice(0,12)+" / unchecked at export";
 if(!view)resetCamera();
 const renderer=JSON.parse(el("renderer").textContent),bridge=JSON.parse(el("bridge").textContent);
 for(const id of frames){
 const d=data[id];
 el(id+"-label").textContent=d?(id==="current"?"Current: ":"Prior reference: ")+d.snapshot.identity.id+" / "+d.validation:"Prior reference unavailable";
 if(d)el(id).srcdoc=renderer.replace("__MODEL__",safeJSON(modelFor(d,data.frame))).replace("</body>",bridge+"</body>");
 else el(id).srcdoc="<p style='font:16px system-ui'>No prior tracked revision supplied.</p>";
 }
 persist();
}
window.addEventListener("message",e=>{
 const id=frames.find(id=>el(id).contentWindow===e.source);if(!id||!active||blocked)return;
 if(e.data?.revision!==active[id]?.snapshot.identity.brief_sha256)return;
 if(e.data?.kind==="cad-review-ready"){send(id);return;}
 if(e.data?.kind!=="cad-review-state")return;
 const state=e.data.state;
 if(state.interacting)interacting.add(id);else interacting.delete(id);
 view={...state,visibility:{...(view?.visibility||{}),...state.visibility}};
 frames.filter(other=>other!==id).forEach(send);persist();
});
function admit(data){
 const old=active.current.snapshot.identity,newId=data.current.snapshot.identity;
 const ancestors=data.current.snapshot.brief.revision.ancestors;
 if(data.current.scene.coordinate_system!==active.current.scene.coordinate_system)throw Error("Incoming coordinate frame changed; comparison refused");
 if(newId.id===old.id||!ancestors.includes(old.id))throw Error("Incoming review is not a newer descendant");
 const recovery=blocked&&newId.id===lastSeen?.id&&newId.brief_sha256===lastSeen.brief_sha256;
 if(lastSeen&&!recovery&&!ancestors.includes(lastSeen.id))throw Error("Incoming review is older than or incompatible with the last shown revision");
}
async function load(packet){
 try{const data=await decode(packet),newId=data.current.snapshot.identity;
 admit(data);
 pending=data;el("apply").disabled=false;notice("New revision "+newId.id+" is waiting. Apply when ready; the displayed snapshot has not changed.");
 return {status:"pending",revision:newId};
 }catch(e){notice("Incoming review rejected; displayed snapshot unchanged: "+e.message);throw e;}
}
function apply(){
 if(!pending)return {status:"no_pending_revision"};
 if(interacting.size){notice("Update deferred until pointer interaction ends.");return {status:"interaction_active"};}
 admit(pending);
 const data=pending;pending=null;render(data);el("apply").disabled=true;
 notice("Applied "+data.current.snapshot.identity.id+"; camera and matching component visibility retained.");
 return {status:"applied"};
}
window.cadReview={load,apply,preset:resetCamera,getState:()=>({revision:active?.current.snapshot.identity,
 view,pending:pending?.current.snapshot.identity,blocked,interacting:[...interacting]})};
el("apply").onclick=apply;
el("load").onchange=async()=>{
 try{await load(JSON.parse(await el("load").files[0].text()));}catch(e){notice("Review load failed: "+e.message);}
};
for(const id of ["front","top","side","iso"])el(id).onclick=()=>resetCamera(id);
(async()=>{
 try{
 const data=await decode(JSON.parse(el("review-data").textContent));active=data;
 let saved=null;try{saved=JSON.parse(sessionStorage.getItem(key));}catch(e){notice("Saved UI state unavailable: "+e.message);}
 if(saved){
 lastSeen=saved.identity;
 view=saved.view;
 if(saved.identity.brief_sha256!==data.current.snapshot.identity.brief_sha256){
 if(!data.current.snapshot.brief.revision.ancestors.includes(saved.identity.id)){
 blocked=true;el("identity").textContent="Blocked stale/unrelated snapshot "+data.current.snapshot.identity.id+"; last shown "+saved.identity.id;
 notice("An older or incompatible file was reloaded. Load a newer descendant review; old geometry was not restored.");return;}
 notice("New embedded revision loaded; camera and matching visibility retained.");}
 }
 render(data);
 }catch(e){blocked=true;notice("Review could not be opened: "+e.message);}
})();
</script></html>'''


def read_packet(path):
    packet = json.loads(Path(path).read_text(encoding="utf-8"))
    if (packet.get("schema_version") != 1 or not isinstance(packet.get("payload"), str)
            or hashlib.sha256(packet["payload"].encode("utf-8")).hexdigest() != packet.get("sha256")):
        raise ValueError("Review payload hash mismatch")
    data = json.loads(packet["payload"])
    if data["schema_version"] != 1:
        raise ValueError("Unsupported review state")
    for descriptor in (data["current"], data["previous"]):
        if descriptor is not None:
            validate_snapshot(descriptor["snapshot"])
    if (data["previous"] is not None and
            data["previous"]["snapshot"]["identity"]["id"] not in
            data["current"]["snapshot"]["brief"]["revision"]["ancestors"]):
        raise ValueError("Review reference is not a prior ancestor")
    return data


def descriptor(snapshot, components, manifest):
    if any(part.get("visual_regions") for part in manifest["parts"]):
        from .regions import render_surfaces
        components, metadata, sources = render_surfaces(components, manifest)
        scene = packed_geometry(components)
        scene.update(title=manifest["name"]+f" / {len(manifest['instances'])} physical instances; finish surfaces are not parts",
                     coordinate_system=manifest["coordinate_system"], assumptions=manifest["assumptions"])
        for record in scene["parts"]:
            key = record["name"]
            record.update({k: metadata[key][k] for k in ("color", "material", "notes")})
            record.update({k: sources[key][k] for k in ("part_id", "physical_instance_id", "region_id")})
        return {"snapshot": deepcopy(snapshot), "brief_json": canonical(snapshot["brief"]),
                "scene": scene, "validation": "unchecked at export"}
    scene = packed_geometry(components)
    scene.update(title=manifest["name"], coordinate_system=manifest["coordinate_system"],
                 assumptions=manifest["assumptions"])
    for part in scene["parts"]:
        instance = next(item for item in manifest["instances"] if item["id"] == part["name"])
        info = next(item for item in manifest["parts"] if item["id"] == instance["part_id"])
        part.update(color=info["color"], material=info["material"], notes=info["notes"])
    return {"snapshot": deepcopy(snapshot), "brief_json": canonical(snapshot["brief"]),
            "scene": scene, "validation": "unchecked at export"}


def review_frame(current, previous):
    scenes = [current["scene"]]+([previous["scene"]] if previous else [])
    bounds = np.array([[min(s["bounds_mm"][0][a] for s in scenes) for a in range(3)],
                       [max(s["bounds_mm"][1][a] for s in scenes) for a in range(3)]])
    return {"bounds_mm": bounds.tolist(), "origin_mm": bounds.mean(axis=0).tolist(),
            "scale_mm": float(np.max(bounds[1]-bounds[0]))}


def write_review(snapshot, placed, manifest, stage, previous_output):
    validate_snapshot(snapshot)
    current = descriptor(snapshot, list(placed.items()), manifest)
    previous = None
    if previous_output is not None:
        prior = Path(previous_output)
        old_manifest = json.loads((prior / "manifest.json").read_text(encoding="utf-8"))
        if old_manifest.get("revision") is not None:
            old_snapshot = json.loads((prior / "revision-state.json").read_text(encoding="utf-8"))
            verify_export(old_snapshot, prior)
            old_identity = old_snapshot["identity"]
            if old_manifest["coordinate_system"] != manifest["coordinate_system"]:
                raise ValueError("Cannot compare incompatible coordinate frames")
            if old_identity["id"] == snapshot["identity"]["id"] and old_identity != snapshot["identity"]:
                raise ValueError("Revision id reused for a different brief; advance the revision")
            if old_identity == snapshot["identity"]:
                if "review" in old_manifest:
                    previous = read_packet(prior / "review-state.json")["previous"]
            else:
                if old_identity["id"] not in snapshot["brief"]["revision"]["ancestors"]:
                    raise ValueError("Cannot compare a newer or unrelated revision; reference must be an ancestor")
                if "review" in old_manifest:
                    previous = read_packet(prior / "review-state.json")["current"]
                else:
                    meshes = [(item["id"], trimesh.load_mesh(prior / item["stl"]))
                              for item in old_manifest["instances"]]
                    previous = descriptor(old_snapshot, meshes, old_manifest)
                report_path = prior / "validation.json"
                if report_path.is_file():
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                    valid = (report.get("revision") == old_identity and
                             report.get("exports", {}).get("manifest_sha256") == sha256(prior / "manifest.json"))
                    previous["validation"] = ("recorded "+report["status"] if valid else
                                              "stale or incompatible validation report")
    frame = review_frame(current, previous)
    payload = canonical({"schema_version": 1, "current": current, "previous": previous, "frame": frame})
    packet = {"schema_version": 1, "payload": payload,
              "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest()}
    (stage / "review-state.json").write_text(json.dumps(packet, indent=2), encoding="utf-8")
    substitutions = {"PACKET": script_json(packet), "RENDERER": script_json(HTML), "BRIDGE": script_json(BRIDGE)}
    html = re.sub(r"__(PACKET|RENDERER|BRIDGE)__", lambda match: substitutions[match[1]], PAGE)
    (stage / "review.html").write_text(html, encoding="utf-8")
    return {"schema_version": 1, "html": "review.html", "state": "review-state.json"}


def check_review(snapshot, placed, manifest, output):
    data = read_packet(Path(output) / "review-state.json")
    if data["current"] != descriptor(snapshot, list(placed.items()), manifest):
        raise ValueError("Review geometry or source identity is stale")
    if data["frame"] != review_frame(data["current"], data["previous"]):
        raise ValueError("Review comparison frame is stale")
    return {"status": "passed", "current": snapshot["identity"],
            "previous": data["previous"]["snapshot"]["identity"] if data["previous"] else None}
