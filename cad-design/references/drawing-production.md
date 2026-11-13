# Collaboration checkpoints and portable concept drawings

## Establish the next deliverable

Separate the requested result from prerequisites. A headphone reference is a
dependency of a case, not a completed case. Reuse the user's stated purpose and
outputs; do not ask a redundant intake questionnaire. State the immediate
deliverable and sequence before starting detailed work. Ask one focused scope
question only when it is genuinely unclear, then wait.

The brief accepts an optional sourced contract:

```json
{"deliverable":{"status":"selected","target":"Storage case, not only the headphone reference","outputs":["Offline review","STL/GLB"],"sequence":["Estimate the headphone reference as a dependency","Build and review the case"],"source":"User explicitly requests a storage case"}}
```

`selected` and `delegated` require a nonempty target, outputs and sequence.
`awaiting_choice` requires null target and blocks modeling/publication, even
when geometry choices are otherwise resolved. Older briefs without this field
remain compatible; missing metadata does not grant permission to infer scope.
The review page shows the active snapshot's target, outputs and sequence.
Pending revisions do not change that display until human Apply.

Before first publication, record the actual contract in the unpublished brief;
replace the scaffold's explicitly illustrative contract. For a published
project, update `deliverable` through topology/final `--brief-updates`, not a
same-ID manual edit. Preserve it with `--preserve deliverable`. The contract
records scope, not identity authentication or fabrication approval.

Briefly explain a meaningful dependency or delay before the next preview.
Do not present an intermediate reference as the promised accessory, introduce
unrelated workspace names, or narrate every shell command.

## Comparable lightweight alternatives

For consequential shape/topology/mounting ambiguity, show two comparable
silhouettes or sections (four when needed), ask one question and END THE TURN. A drawing is not
a selection. Do not build/export/qualify a detailed "provisional" model.
Keep accepted source, exports and qualification unchanged while waiting.
Resolved edits and incidental presentation need no new checkpoint.

Use `cadkit.checkpoint` with a small declarative JSON proposal stored under
project `exploration`. No model builder, renderer, browser or geometry kernel
is executed by this tool. All options share 2D mm bounds, orientation and
display scale. Blue means material; white means void. Label the fixed features,
endpoints and dimensions in ordinary physical language.
Use ordered unique IDs A/B for two alternatives or A/B/C/D for four; three
options and repeated/reordered labels are rejected. Picture every offered
visual choice, inspect its label and full title before asking, and keep each
question about one decision. Titles wrap without a fixed-height crop; drawings
align by paired row on wide displays and stack on narrow displays.

```json
{
  "schema_version": 1,
  "question": "Which looks closer?",
  "view": "Front / X right, Z up",
  "bounds_mm": [[0,0],[100,80]],
  "fixed": ["80 mm width; lower endpoints unchanged"],
  "options": [
    {"id":"A","title":"Straight band","material":[[[10,10],[90,10],[90,60],[10,60]]],"voids":[],"labels":[{"at":[10,70],"text":"80 mm width"}]},
    {"id":"B","title":"Open band","material":[[[10,10],[90,10],[90,60],[10,60]]],"voids":[[[20,20],[80,20],[80,50],[20,50]]],"labels":[{"at":[10,70],"text":"Same width; central void"}]}
  ]
}
```

From the project root:

```powershell
python -m cadkit.checkpoint --input .\exploration\shape-choice.json
```

The tool refuses input/output outside `exploration` and existing output files.
For a subsequent proposal, choose a new `--output` path there. Open its actual
HTML page using an approved host surface or provide its real path. Do not
claim it was displayed merely because the file exists. The page cannot select,
approve, publish geometry or Apply a revision; capture the user's answer with
the host question UI, record the selected/delegated decision, then resume the
normal checked revision path.

## Regenerate drawing sheets from a copied project

New projects include `cadkit.drawing` and `drawing-settings.json`. Everything
needed to generate sheets is project-local. The command reads checked exported
meshes, not a session-local bespoke generator or the model builder.

After adapting and qualifying the actual project:

```powershell
python -m cadkit.drawing
python -m cadkit.drawing --output .\drawings-regenerated
python -m cadkit.drawing --verify .\drawings-regenerated
```

These are generation, explicit regeneration into a new folder, and verification
examples. Default output is `output\drawings\<revision>-<settings-hash>`.
Existing destinations are refused, not overwritten. Copy the entire project,
use its existing compatible Python environment, and run the same command in
the copied folder with a new destination. No original session/skill path,
server or network access is required.

The optional PDF command uses an approved installed Chromium/Edge and Playwright:

```powershell
python -m cadkit.drawing --output .\drawings-with-pdf --browser "C:\path\to\msedge.exe"
```

Without that optional capability, SVG/HTML/CSV generation still works and PDF
is not promised. No dependencies or browsers are downloaded. SVG sheets
declare exact physical mm size; PDF page edges may be quantized by Chromium
within one CSS pixel (about 0.265 mm). Geometry uses the requested scale with
PDF scale=1. Print actual size, not fit-to-page; screen zoom is not print scale.

## Saved settings and evidence

`drawing-settings.json` persists title, units (`mm` or `in`), decimal precision,
fraction denominator, numeric 1:N scale, sheet size/orientation/margins/grid,
lineweight, text size, hatch spacing, selected views and schedule inclusion.
Fractional inches support 1/2 through 1/128; null denominator selects decimal
inches. Labels round only presentation, never geometry or fit dimensions.
Scale 1:4 is equivalent to 3 inches on paper per foot of model length.

Projection directions are `top` (X/Y), `front` (X/Z) and `right` (Y/Z).
Sections specify `axis` and absolute `offset_mm` in the project's coordinate
frame. Axonometric outlines look from +X/-Y/+Z and omit dimension labels:
projected lengths are not true feature lengths. Optional `instances` selects
physical instance IDs per view; absent selection means the full assembly.
Projection/section dimension labels are overall projected extents, not
feature, hole, clearance or fabrication dimensions.

Views fill the saved sheet grid in order, adding sheets when needed.
A view too large at the specified scale is an error: choose a larger sheet,
fewer panels or another explicit scale. It is never silently shrunk.
The physical-part schedule lists quantities, recorded materials and local
bounds; CSV retains complete recorded notes. Schedule sheets are NTS.

`drawing-state.json` binds revision, current manifest/validation, exact settings
bytes, raw projected/cut extents and areas, paper extents, schedule and generated
file hashes. Verification rejects changed settings, stale geometry or altered
drawings. The source validation status is retained, including omitted browser
checks. Generation neither approves a design nor modifies CAD geometry,
the existing review panel or its Apply boundary.

These are **mesh-derived concept projections and sections**, not exact
B-rep drawings, hidden-line removal, photorealistic renders, native Revit
families, structural certification or fabrication-ready documentation.
Preserve fit/manufacturer/material uncertainties separately; drawing quality
does not resolve them. Architectural detailing remains a separate specialization.
