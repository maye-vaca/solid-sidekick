# Design workflow

## A. Establish the brief

Collect only what is needed for the next design decision:

| Topic | Establish |
|---|---|
| Purpose | What does the object do, and how will the user interact with it? |
| Interfaces | What existing surfaces, parts, shafts or openings must it fit? |
| Geometry | Size limits, critical dimensions, clearances and movement |
| Materials/process | Stock available; printing, cutting, drilling or other fabrication |
| Evidence | Measured values, manufacturer drawings, calibrated photos, user confirmations |
| Output | Visual concept, fit-check prototype, STL/GLB or a need for exact CAD |
| Immediate deliverable | What the user will receive next; which reference/dependency comes first and which accessory/drawing follows |

Example question: "What diameter is the shaft this needs to fit?"
Avoid bundling unrelated questions or asking for an entire drawing package.
Explain why a critical measurement matters.
State the agreed next output before detailed work and record the sourced
`deliverable` contract. If the request clearly specifies it, reuse that
selection instead of asking again. Otherwise ask one scope question and wait.
Explain meaningful dependency work before the next preview, not every tool call.

If measurements are not yet available, offer a reversible visual envelope and
identify the values that must be checked before an interface can be finalized.
Do not invent mating-hole patterns, material strength or fit allowances.

## B. Provenance and coordinates

The starter brief has numeric `dimensions` entries containing `value`, `unit`,
`status` and `source`. It is an example, not a universal design schema.
Adapt it to the project rather than forcing everything into riser dimensions.

Statuses:

- `measured`: a stated measurement, with method/source if known.
- `confirmed`: the user explicitly supplied/approved this value or relationship.
- `assumed`: a chosen placeholder, awaiting confirmation.
- `estimated`: inferred from approximate evidence, such as a calibrated photograph.

Sources are not optional for model-driving dimensions. Retain uncertainty as a
range or a note when applicable. Noncritical confirmation is not permission to
change the project scope.

Record a physical coordinate convention, for example:
"Origin at the lower-front-left corner, +X to the right as viewed from the
operator position, +Y toward the back, +Z up; millimetres."

Use that same convention in geometry, descriptions and checks. A camera may
rotate without redefining left/right. For "flush", identify the two faces or
edges; do not guess whether the user means a centerline.

## Interpretation checkpoint

Shape language is a hypothesis, not a feature specification. "More ball-like"
does not necessarily mean a sphere; a "flat band" may be an axially straight
surface curving around the body, not separate planar patches. When alternatives
change topology, mounting or proportions, first show a quick reference-aligned
silhouette/section or ask one question distinguishing those alternatives.
Ask one visible question and end the turn. Do not build, export or qualify a
detailed model while that choice is pending, even if labeled provisional.
This checkpoint takes precedence over preview-first and reversible-assumption
advice. The user may explicitly delegate a choice; record that delegation,
not inferred whole-model approval. Ordinary resolved edits need no checkpoint.

Prefer two lightweight A/B silhouettes or sections (A/B/C/D when four are needed) when the difference is
visual. Keep the same orientation/scale, show the material versus empty space,
and label the endpoints, dimensions and features that stay fixed. Describe
each in ordinary physical language and ask which is closer; do not require
the user to choose a fillet, spline or surface-continuity term. A small SVG/HTML
or text diagram is sufficient; avoid a full kernel build for this question.
Use [the bundled checkpoint tool](drawing-production.md) for portable,
comparable A/B SVG/HTML without modifying accepted geometry.
Put these explorations in a separate location, not the accepted brief or
generated output folder, and label them as alternatives, not validated models.
Open an actual visual through the host when available; otherwise provide its
real path and do not claim it was displayed.
Picture every offered visual alternative, verify unique matching labels and
unclipped titles, then ask one question. Do not silently omit C/D or reuse A/B
labels for a four-option question.

For a new project, record typed blocking `decisions` in its unpublished brief.
After selection, finish the initial source/brief and qualify once. For an
already accepted project, keep its brief/code/exports unchanged while waiting;
store pending sketches/proposals under `exploration`, not as accepted facts.
Then submit selected decisions through `revise --tier topology --brief-updates`.
Runtime can reject recorded blocks; it cannot detect an unrecorded user request
or authenticate a claimed selection. See [the API](public-api.md).

After selection, record the chosen intent and any still-estimated curvature,
then use the normal revision/check/pending-review path. Do not silently turn a
qualitative choice into an exact measured radius or tangent-blend promise.
Keep this proportional: a resolved dimension change needs no A/B detour.
Exploratory iterations can be successful collaboration; distinguish new intent
from preventable misunderstanding, lost decisions and unnecessary rebuilds.

Use orthographic front/side/top views with fixed axis labels when judging
proportions. An isometric render alone can hide a depth or alignment error.
Keep the user's current camera separate from the model's coordinate convention.
Do not repeatedly reset a camera or visibility the user is actively inspecting.

## C. Envelope review

Create the simplest shapes that show scale, layout and working space. Do not
model threads or decorative features before the major arrangement is reviewed.
Show the model from the user's reference viewpoint and an informative alternate
view. Label guessed features in the viewer/assumptions, not just chat text.

At this stage ask about consequential arrangement choices; reuse previously
provided decisions rather than asking the same question again.

## D. Interfaces and components

Create each part in useful local coordinates. Place repeated parts via
instances. Store important parameters once, and derive placements from mating
surfaces. Add focused checks for those relationships.

Maintain three distinct concepts: visual regions (face/eyes/finishes), physical
parts (connected manufactured pieces), and interfaces (contacts, sockets,
clearance and insertion direction). A coloured region need not be another
printed part. Do not fuse away a requested movable joint or count touching STL
shells as one connected part. A physical-part preview may be single-material;
explain that limitation rather than implying the approved finish was removed.

Before adding fitted interfaces, resolve intended fit and fabrication process,
one decision at a time. If machine compensation is unknown, explicitly propose
provisional clearance and a fit test; never describe that estimate as a measured
tolerance or a guaranteed fit. Check blind-hole bottom clearance as well as
diameter, and whether the parts can actually assemble/disassemble.

Distinguish a visual hardware envelope from an actual component definition.
If flange pitch, bearing geometry or fastener length is unknown, record it as
illustrative. Do not present an illustrative model as a drilling template.

Geometry stays independent of the renderer. The viewer reads exported geometry
and metadata. Do not embed camera/time code in the part-building functions.

## E. Revision loop

For "move this rail on top, flush with the left edge":

1. Resolve the part and the user's viewing frame.
2. Decide whether the part stands on its narrow or wide face; ask if ambiguous.
3. Derive its bottom elevation from the finished platform top.
4. Derive its outside face position from the platform edge.
5. Update the brief and relevant geometry/placement.
6. Check actual bounds, contact and remaining clearance.
7. Regenerate and show the affected view.

Use concise summaries of what changed, not a narration of tool calls.

For "move the holes outward a little", first ask which hole set is affected,
for example "Do you mean the foot holes, upright holes, or both?" Stop there;
ask the amount only after scope is known, unless the answer supplies it too.
One reply containing two questions still bundles two decisions.
Keep the last valid dimensions, geometry and exports while clarification is
pending. If a revision contradicts retained dimensions, explain the conflict;
do not apply part of it or silently relax another constraint.

### Compact revision contract

Before editing, identify the requested delta, fixed features and dependent
features. A pin-diameter correction changes the pin and existing mating bores,
not shoulder diameter merely because both once shared the same number.
If bores were explicitly deferred, do not add them during the correction.

Keep the current contract with the project's existing brief/state, not in an
ever-growing prompt. New starters use the validated
[revision-state schema](revision-state.md); keep that metadata contract while
adapting project-specific dimensions and intent. Its fields include:
revision ID/parent, delta, preserve, dependencies, current facts, superseded
facts, open decisions and explicit user-approved stage. Keep units, axes and
source/status with the facts. Generate export metadata from those current
inputs; do not independently hand-edit generated manifests or duplicate values
into unrelated offsets.

Advance corrected inputs with `cadkit.incremental revise` so superseded sources,
open decisions and prior approval attribution persist; it calls the revision
helper internally. Do not separately advance the brief before admission. Preserve the generated
snapshot binding in `build()`; a same-ID brief/geometry change is not a new
valid revision. Older untracked projects require explicit adoption.

One user correction supersedes the earlier input, not the whole design.
Retain superseded values for history without leaving both active. If an eye
inset implies a surprising shoulder change, explain the conflicting retained
relationships and ask; do not invent front-mounted shoulders.

### Match the work to the revision

| Change tier | Required work |
|---|---|
| Resolved parameter correction | Update the parameter/derived features; build/export; check changed dimensions, dependencies and affected exports; refresh the current preview |
| Shape or arrangement ambiguity | Resolve with a sketch/section or one focused question before detailed work; then inspect the affected orthographic views |
| Interface, topology or physical-part change | Full relevant geometry/export/interference checks; connected-solid counts, clearances and assembly/removal path |
| Final handoff or requested checkpoint | Full applicable validator, current source/export consistency and requested packaging; state physical-fit and browser limitations |

Use the existing project validator when no narrower qualified checker exists.
Do not trade correctness for speed or suppress a failure to fit the fast tier.
Avoid regenerating a smoke project, requalifying an unchanged renderer or
building a full source ZIP for every small edit. Prefer one current review view
when the host can refresh it; preserve prior outputs without accumulating tabs.
If the host lacks revision comparison/state retention, say so rather than
claiming a version-selector or overlay feature exists.

For tracked projects, [the checked revision commands](regions-and-incremental.md)
are the default: qualify once, provide sourced scalar updates to `revise`,
then `verify --include-packet` and stage the packet in the existing
`review.html` panel. For code/topology work, edit model/related checks first
but retain the old brief/exports until `revise --tier topology` advances and
checks them. Full tiers require a real browser; failed revisions have an
explicit `--recover` path. Do not replace these with bespoke lineage scripts,
repeated qualification, single-viewer reload buttons or extra preview tabs.

Resume from the current brief, files and evidence, not just remembered chat.
A new agent context must receive the compact current contract, approved scope,
existing output paths and unfinished checks. Do not start a second writer while
the previous process may still own the design.

## F. Handoff stage

Use concrete labels: "concept", "fit-check prototype", or a more specific,
evidence-backed description. Do not equate render quality with engineering
completeness. Export only the requested surfaces of the work.
For requested drawing sheets, use [portable drawing production](drawing-production.md)
with saved units, fractions, physical scale, view selection and sheet conventions.
Do not strand the generator in an originating session folder.

The starter's `stage` does not automatically advance after a successful build.
Changing it requires the corresponding design evidence/review, not an export.
