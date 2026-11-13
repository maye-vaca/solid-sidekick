"""Build an offline, interactive browser viewer from a folder of STL files.

Install: python -m pip install trimesh numpy
Run: python -m cadkit.viewer "C:\\path\\to\\stls" --units mm
Optional: --output "C:\\path\\viewer.html" --no-open

Reads .stl files directly inside the folder, including uppercase extensions.
Preserves all coordinates: parts exported in assembled positions appear as an
assembly; independently centered parts will overlap. No unit conversion is made.
The output HTML embeds every mesh and needs no server, internet or source files.
STL has no colors; standalone imports use a deterministic palette. Assemblies
created by cadkit use explicit component colors and metadata instead.
"""

import argparse
import json
from pathlib import Path
import sys
import webbrowser

import numpy as np
import trimesh

from .scene import display_color, packed_geometry


def load_components(folder):
    folder = Path(folder).expanduser().resolve()
    if not folder.is_dir():
        raise ValueError(f"STL folder does not exist or is not a directory: {folder}")
    paths = sorted(
        (path for path in folder.iterdir() if path.is_file() and path.suffix.lower() == ".stl"),
        key=lambda path: path.name.casefold(),
    )
    if not paths:
        raise ValueError(f"No STL files found directly inside: {folder}")
    components = []
    for path in paths:
        try:
            mesh = trimesh.load_mesh(path, file_type="stl", process=True)
        except (OSError, ValueError, TypeError, IndexError) as error:
            raise ValueError(f"Could not read STL '{path.name}': {error}") from error
        if not isinstance(mesh, trimesh.Trimesh) or mesh.is_empty or not len(mesh.faces):
            raise ValueError(f"STL contains no triangles: {path.name}")
        if not np.isfinite(mesh.vertices).all():
            raise ValueError(f"STL contains non-finite coordinates: {path.name}")
        if not np.isfinite(mesh.face_normals).all() or not np.any(mesh.area_faces > 0):
            raise ValueError(f"STL contains no usable triangle surfaces: {path.name}")
        components.append((path.name, mesh))
    return components


def viewer_data(components):
    packed = packed_geometry(components)
    return {key: packed[key] for key in ("parts", "extent", "bounds")}


HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>STL component viewer</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#101923;color:#edf3f7;font:14px system-ui}
header{padding:16px 20px}h1{font-size:22px;margin:0 0 6px}p{margin:6px 0;color:#b9c9d3}
button,input{font:inherit}button{background:#263e50;color:#edf3f7;border:1px solid #58758b;
border-radius:5px;padding:7px 10px;cursor:pointer}button:hover{background:#36536a}
button:focus-visible,input:focus-visible{outline:2px solid #70d7e9;outline-offset:2px}
.toolbar{display:flex;flex-wrap:wrap;gap:7px;padding:0 20px 12px}
main{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:12px;padding:0 20px 20px}
.viewport{height:74vh;min-height:450px;background:#101923;border:1px solid #354b5b;
border-radius:8px;overflow:hidden}canvas{width:100%;height:100%;display:block;touch-action:none}
aside{display:flex;flex-direction:column;min-height:0;height:74vh;min-width:0;background:#172634;
border:1px solid #354b5b;border-radius:8px;padding:12px}aside h2{font-size:16px;margin:0 0 8px}
#search{background:#101923;color:#edf3f7;border:1px solid #58758b;border-radius:4px;
padding:8px;width:100%}.actions{display:flex;flex-wrap:wrap;gap:6px;margin:9px 0}
.actions button{padding:6px;font-size:12px}#components{overflow:auto;flex:1}
.part{display:flex;align-items:center;gap:7px;border-radius:4px;padding:3px}
.part[hidden]{display:none}.part.selected{background:#305467}.part input{flex:none}.part button{border:0;background:none;
padding:6px 2px;text-align:left;overflow-wrap:anywhere;min-width:0;flex:1}
.swatch{width:10px;height:10px;border:1px solid #c9d1d7;flex:none}
#selected,#status,#filterStatus{font-size:12px;overflow-wrap:anywhere}#selected{margin:10px 0 0}
#error{background:#5e2027;color:#fff;padding:14px 20px;white-space:pre-wrap}
@media(max-width:850px){main{grid-template-columns:minmax(0,1fr);padding:0 10px 10px}
.viewport{height:60vh;min-height:350px}aside{height:320px}.toolbar{padding:0 10px 10px}}
</style></head><body>
<header><h1>STL component viewer</h1>
<p id="summary">Loading meshes...</p>
<p>Drag to orbit; scroll to zoom; Shift-drag or right-drag to pan.
<span id="conventions"></span></p><p id="assumptions"></p></header>
<div id="error" role="alert" hidden></div>
<div class="toolbar">
<button id="iso">Assembly / isometric</button><button id="top">Top</button>
<button id="front">Front</button><button id="side">Side</button>
<button id="under">Underside</button><button id="fit">Fit visible</button>
</div>
<main><div class="viewport"><canvas id="view" aria-label="Interactive STL assembly"></canvas></div>
<aside><h2>Components</h2><input id="search" type="search" placeholder="Filter filenames"
aria-label="Filter component filenames">
<div class="actions"><button id="showAll">Show all</button><button id="hideAll">Hide all</button>
<button id="isolate">Isolate selected</button><button id="focus">Fit selected</button></div>
<p id="filterStatus"></p><div id="components"></div>
<p id="selected">Select a filename to highlight a component.</p>
<p id="status" role="status"></p></aside></main>
<script id="model" type="application/json">__MODEL__</script>
<script>
"use strict";
const el=id=>document.getElementById(id);
function showError(message){el("error").hidden=false;el("error").textContent=message;}
window.addEventListener("error",event=>showError(event.message));
const model=JSON.parse(el("model").textContent);
const parts=model.parts.map(part=>({...part,visible:true}));
const canvas=el("view"),gl=canvas.getContext("webgl",{antialias:true});
if(!gl){showError("WebGL is unavailable. Open this HTML in Edge or Chrome with hardware graphics enabled.");
throw Error("WebGL unavailable");}
canvas.addEventListener("webglcontextlost",event=>{
event.preventDefault();showError("The graphics context was lost. Reload this page to restore the viewer.");});
function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);
if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;}
const program=gl.createProgram();
gl.attachShader(program,shader(gl.VERTEX_SHADER,`
attribute vec3 position;attribute vec3 normal;
uniform vec3 center;uniform vec4 rotation;uniform vec2 scale;uniform vec2 pan;
uniform float depthRange;varying float light;
void main(){vec3 q=position-center;float along=q.x*rotation.y+q.y*rotation.x;
float u=q.x*rotation.x-q.y*rotation.y;
float up=q.z*rotation.z-along*rotation.w;
float depth=along*rotation.z+q.z*rotation.w;
gl_Position=vec4(u*scale.x+pan.x,up*scale.y+pan.y,-depth/depthRange,1.);
float na=normal.x*rotation.y+normal.y*rotation.x;
vec3 n=vec3(normal.x*rotation.x-normal.y*rotation.y,
normal.z*rotation.z-na*rotation.w,na*rotation.z+normal.z*rotation.w);
light=.48+.52*abs(dot(n,normalize(vec3(.3,.5,.81))));}`));
gl.attachShader(program,shader(gl.FRAGMENT_SHADER,`
precision mediump float;uniform vec3 color;varying float light;
void main(){gl_FragColor=vec4(color*light,1.);}`));
gl.linkProgram(program);
if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));
gl.useProgram(program);gl.enable(gl.DEPTH_TEST);
const uniforms=Object.fromEntries(["center","rotation","scale","pan","depthRange","color"]
.map(name=>[name,gl.getUniformLocation(program,name)]));
for(const part of parts){
const decoded=atob(part.vertices),bytes=new Uint8Array(decoded.length);
for(let i=0;i<decoded.length;i++)bytes[i]=decoded.charCodeAt(i);
part.buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,part.buffer);
gl.bufferData(gl.ARRAY_BUFFER,bytes,gl.STATIC_DRAW);
part.count=bytes.byteLength/24;delete part.vertices;
if(gl.getError()!==gl.NO_ERROR)throw Error("Could not upload mesh: "+part.name);}
const attributes=[["position",0],["normal",12]].map(([name,offset])=>({
location:gl.getAttribLocation(program,name),offset}));
for(const attribute of attributes)gl.enableVertexAttribArray(attribute.location);
let yaw=Math.PI-.5,pitch=.85,center=[0,0,0],span=1,zoom=1,pan=[0,0],selected=-1,drag=null;
function boundsFor(indices){const low=[Infinity,Infinity,Infinity],high=[-Infinity,-Infinity,-Infinity];
for(const index of indices)for(let axis=0;axis<3;axis++){
low[axis]=Math.min(low[axis],parts[index].bounds[0][axis]);
high[axis]=Math.max(high[axis],parts[index].bounds[1][axis]);}return[low,high];}
function fit(indices){
if(!indices.length){draw();return;}
const [low,high]=boundsFor(indices);center=low.map((v,i)=>(v+high[i])/2);
span=Math.max(1e-7,Math.hypot(...high.map((v,i)=>v-low[i]))*1.12);
zoom=1;pan=[0,0];draw();}
function visibleIndices(){return parts.flatMap((p,i)=>p.visible?[i]:[]);}
function draw(){
const width=canvas.clientWidth,height=canvas.clientHeight;if(!width||!height)return;
const ratio=Math.min(devicePixelRatio||1,2);
const targetWidth=Math.round(width*ratio),targetHeight=Math.round(height*ratio);
if(canvas.width!==targetWidth||canvas.height!==targetHeight){
canvas.width=targetWidth;canvas.height=targetHeight;}
gl.viewport(0,0,canvas.width,canvas.height);gl.clearColor(.063,.098,.137,1);
gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
const scale=Math.min(width,height)/span*zoom;
gl.uniform3fv(uniforms.center,center);
gl.uniform4f(uniforms.rotation,Math.cos(yaw),Math.sin(yaw),Math.cos(pitch),Math.sin(pitch));
gl.uniform2f(uniforms.scale,2*scale/width,2*scale/height);
gl.uniform2f(uniforms.pan,2*pan[0]/width,-2*pan[1]/height);
gl.uniform1f(uniforms.depthRange,4+Math.hypot(...center));
for(let index=0;index<parts.length;index++){
const part=parts[index];if(!part.visible)continue;
gl.bindBuffer(gl.ARRAY_BUFFER,part.buffer);
for(const attribute of attributes)gl.vertexAttribPointer(attribute.location,3,gl.FLOAT,false,24,attribute.offset);
let color=part.color.match(/[a-f0-9]{2}/gi).map(v=>parseInt(v,16)/255);
if(index===selected)color=color.map(v=>.6*v+.4);
gl.uniform3fv(uniforms.color,color);gl.drawArrays(gl.TRIANGLES,0,part.count);}
const count=visibleIndices().length;
el("status").textContent=count+" / "+parts.length+" components visible"+
(count?"":". Use Show all to restore the assembly.")+".";}
function select(index){
selected=index;for(let i=0;i<parts.length;i++)parts[i].row.classList.toggle("selected",i===index);
const part=parts[index],size=part.bounds[1].map((v,i)=>(v-part.bounds[0][i])*model.extent.reduce((a,b)=>Math.max(a,b)));
el("selected").textContent=part.name+" | Size ("+(model.units||"unspecified units")+"): "+
size.map(v=>v.toPrecision(6)).join(" x ")+(part.material?" | Material: "+part.material:"")+
(part.notes?" | "+part.notes:"");
draw();}
for(let index=0;index<parts.length;index++){
const part=parts[index],row=document.createElement("div");row.className="part";
const checkbox=document.createElement("input");checkbox.type="checkbox";checkbox.checked=true;
checkbox.setAttribute("aria-label","Show "+part.name);
checkbox.onchange=()=>{part.visible=checkbox.checked;draw();};
const swatch=document.createElement("span");swatch.className="swatch";swatch.style.background=part.color;
const button=document.createElement("button");button.textContent=part.name;button.title=part.name;
button.onclick=()=>select(index);row.append(checkbox,swatch,button);el("components").append(row);
part.row=row;part.checkbox=checkbox;}
function setVisibility(test){for(let i=0;i<parts.length;i++){
parts[i].visible=test(i);parts[i].checkbox.checked=parts[i].visible;}draw();}
el("showAll").onclick=()=>{setVisibility(()=>true);fit(visibleIndices());};
el("hideAll").onclick=()=>setVisibility(()=>false);
el("isolate").onclick=()=>{if(selected<0){el("selected").textContent="Select a filename first.";return;}
setVisibility(i=>i===selected);fit([selected]);};
el("focus").onclick=()=>{if(selected<0){el("selected").textContent="Select a filename first.";return;}
parts[selected].visible=true;parts[selected].checkbox.checked=true;fit([selected]);};
el("fit").onclick=()=>fit(visibleIndices());
for(const [id,a,b] of [["iso",Math.PI-.5,.85],["top",Math.PI,Math.PI/2],
["front",Math.PI,0],["side",Math.PI/2,0],["under",Math.PI,-Math.PI/2]]){
el(id).onclick=()=>{if(id==="iso")setVisibility(()=>true);yaw=a;pitch=b;fit(visibleIndices());};}
el("search").oninput=()=>{
const query=el("search").value.toLocaleLowerCase();let count=0;
for(const part of parts){const match=part.name.toLocaleLowerCase().includes(query);
part.row.hidden=!match;if(match)count++;}
el("filterStatus").textContent=count+" filenames listed. Filtering does not hide geometry.";};
canvas.oncontextmenu=event=>event.preventDefault();
canvas.onpointerdown=event=>{
if(event.button!==0&&event.button!==2)return;event.preventDefault();
drag={x:event.clientX,y:event.clientY,pan:event.shiftKey||event.button===2};
canvas.setPointerCapture(event.pointerId);};
canvas.onpointermove=event=>{
if(!drag)return;const dx=event.clientX-drag.x,dy=event.clientY-drag.y;
if(drag.pan){pan[0]+=dx;pan[1]+=dy;}else{yaw+=dx*.008;
pitch=Math.max(-Math.PI/2,Math.min(Math.PI/2,pitch+dy*.008));}
drag.x=event.clientX;drag.y=event.clientY;draw();};
for(const event of ["pointerup","pointercancel","lostpointercapture"])
canvas.addEventListener(event,()=>{drag=null;});
canvas.addEventListener("wheel",event=>{event.preventDefault();
zoom=Math.max(.02,Math.min(500,zoom*Math.exp(-event.deltaY*.001)));draw();},{passive:false});
el("summary").textContent=(model.title||"STL component viewer")+" / "+parts.length+" components / "+
parts.reduce((sum,p)=>sum+p.triangles,0).toLocaleString()+" triangles. "+
(model.explicitMetadata?"Colors and materials supplied by the assembly.":"Display colors are assigned; STL does not store colors.");
document.title=model.title||"STL component viewer";
el("conventions").textContent=model.coordinateSystem||"Original coordinates preserved; no unit conversion applied.";
el("assumptions").textContent=(model.assumptions||[]).length?
"Assumptions / limitations: "+model.assumptions.join(" | "):"";
el("search").dispatchEvent(new Event("input"));
new ResizeObserver(draw).observe(canvas);fit(visibleIndices());
</script></body></html>'''


def write_mesh_viewer(components, output, *, title="STL component viewer", units="unspecified",
                      metadata=None, coordinate_system="", assumptions=()):
    if units not in ("mm", "in", "unspecified"):
        raise ValueError("Viewer units must be mm, in, or unspecified")
    data = viewer_data(components)
    if metadata is not None:
        for record in data["parts"]:
            info = metadata[record["name"]]
            record.update(color=info["color"], material=info["material"], notes=info["notes"])
            record.update({key: info[key] for key in ("physical_instance_id", "part_id", "region_id") if key in info})
    data.update(title=title, units=units, explicitMetadata=metadata is not None,
                coordinateSystem=coordinate_system, assumptions=list(assumptions))
    target = Path(output).expanduser().resolve()
    if target.suffix.lower() not in (".html", ".htm"):
        raise ValueError("Viewer output must have an .html or .htm extension")
    payload = json.dumps(data, separators=(",", ":"), allow_nan=False)
    payload = payload.replace("&", r"\u0026").replace("<", r"\u003c").replace(">", r"\u003e")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(HTML.replace("__MODEL__", payload), encoding="utf-8")
    return target


def write_viewer(folder, output=None, *, units="unspecified"):
    folder = Path(folder).expanduser().resolve()
    components = load_components(folder)
    target = (folder.parent / f"{folder.name}_viewer.html" if output is None
              else Path(output).expanduser().resolve())
    target = write_mesh_viewer(components, target, units=units)
    return target, len(components)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path, help="Folder containing STL files (not recursive)")
    parser.add_argument("--output", type=Path, help="Output HTML path; default: beside the STL folder")
    parser.add_argument("--no-open", action="store_true", help="Write the viewer without opening a browser")
    parser.add_argument("--units", choices=("mm", "in", "unspecified"), default="unspecified",
                        help="Label the STL coordinates; no scaling is performed")
    args = parser.parse_args()
    try:
        path, count = write_viewer(args.folder, args.output, units=args.units)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Created viewer for {count} STL files: {path}")
    if not args.no_open and not webbrowser.open(path.as_uri()):
        print(f"Browser did not open. Open this file manually: {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
