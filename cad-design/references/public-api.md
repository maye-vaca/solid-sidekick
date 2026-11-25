# Public API: read this first

Use the existing project Python. Resolve the skill folder once. Scaffold only
into a new destination:

```powershell
python "<skill>\scripts\new_project.py" "<new project>"
python "<project>\model.py"
python "<project>\validate.py" --browser "<Edge or Chromium executable>"
```

An existing working environment needs no reinstall. `CAD_VALIDATION_PYTHON`
and `CADKIT_BROWSER`, when supplied by the host, identify those executables.
Install requirements only after an actual missing-dependency failure or an
intentional dependency change. Browser automation additionally uses Playwright.

## Modeling contract

For requested parts/assembly instructions, use the qualified construction
variant and [construction publication](construction-production.md):
`python -m cadkit.construction --plan .\construction-plan.json --output .\construction-01`.
It binds guide, quantities, storyboard/video and review to one checked revision;
bounded translational access checks are not physical/fabrication approval.

```python
from cadkit import Assembly, Part, Instance, Placement
from cadkit.geometry import box, cylinder, plate_with_holes

a = Assembly("Example", "+X right, +Y back, +Z up; mm",
             assumptions=["Nominal stock; fit unverified"], parameters={"stage": "concept"})
a.add_part(Part("panel", box(100, 60, 4), "Panel", "Plywood", "#d9b079"))
a.add_instance(Instance("lower", "panel"))
a.add_instance(Instance("upper", "panel", Placement((0, 0, 30))))
```

Callable forms:

- `box(width, depth, height)`: lower corner origin, +X/+Y/+Z extents, mm.
- `cylinder(radius, height, segments=96)`: +Z axis, base Z=0, XY centered.
- `plate_with_holes(width, depth, thickness, holes)`: each hole `(x, y, diameter)`.
- `internal_thread_tool(major_diameter, pitch, height, *, radial_clearance=0.0,
  steps_per_turn=144)`: simplified single-start right-hand 60-degree internal
  thread cutter in mm. Full threads cover Z=0 through `height`; the tool
  overruns both faces for subtraction. Requires positive dimensions, a nominal
  major greater than `1.08253 * pitch`, nonnegative finite clearance and integer
  requested resolution of at least 12 steps/turn. The request is a floor:
  the helix and bore core use enough facets to limit radial chord sag to
  2% of profile depth or 0.01 mm, whichever is smaller; helix steps round up
  to a multiple of four. This is a geometric approximation bound, not a
  thread-fit tolerance or class. See the thread recipe below.
- `Part(id, solid, name, material, color, units="mm", notes="", visual_regions=())`.
- `VisualRegion(id, name, color, triangles)`: disjoint final physical-mesh triangle
  indices, not extra solids. Import from `cadkit`; derive after final Booleans.
  See [physical finish regions](regions-and-incremental.md) for segmentation and export limits.
- `Placement(translation=(0,0,0), rotation=(0,0,0), units="mm")`: X/Y/Z Euler
  degrees locally, then translate. `matrix()` returns its 4x4 mm transform.
- `Instance(id, part_id, placement=Placement())`.
- `Assembly(name, coordinate_system, assumptions=[...], parameters={...})`;
  use fresh lists/dicts. `add_part`, `add_instance`, `meshes`, `export`.

Parts accept Manifold solids. `+` unions, `-` subtracts, `^` intersects;
`.translate((x,y,z))`, `.rotate((rx,ry,rz))`, `.scale((sx,sy,sz))` return solids.
Manifold's own cylinder order differs: `m.Manifold.cylinder(height, radius,
circular_segments=96)`. Use focused Manifold docs only for unfamiliar geometry.
Parts and placements normalize explicit `mm`/`in` once; never double-scale.
IDs start with a letter, contain letters/digits/underscore/hyphen, are
case-insensitively unique and must avoid platform device names.

### Threaded bores and fit trials

```python
from cadkit.geometry import cylinder, internal_thread_tool

# Illustrative assumed 3/8-16 pitch; 0.50 mm RADIAL clearance, not a fit guarantee.
cutter = internal_thread_tool(9.525, 25.4 / 16, 6, radial_clearance=0.50)
ring = cylinder(7, 6) - cutter
```

The cutter uses an internal major of `major_diameter + 2 * radial_clearance`
and minor of `major_diameter - 1.08253 * pitch + 2 * radial_clearance`.
Clearance is relative to that nominal profile, not automatically to a measured
bolt crest. It is not a class-fit implementation, calibrated gauge, external
bolt generator, multi-start or left-hand thread. Add required lead-in chamfers
and independently check the remaining wall, through-bore, thread engagement,
pitch repetition and default STL reload. Keep `Mesh64`/float64 through custom
mesh Booleans too; ASCII export cannot restore precision already discarded.
Do not judge a helix only at angular sample vertices: coarse chords on a
large-diameter/fine-pitch profile can fall inside the bore radius and interrupt
the cutting groove. Check intermediate angles and compare a finer reference
as well as through-bore, pitch and handedness. The helper increases resolution
instead of silently accepting that interrupted geometry.

Do not infer pitch or thread class from one caliper diameter. A reading in the
grooves is not a pitch/effective-diameter measurement. Keep nominal standard,
measured crest/minor, assumed pitch and trial clearance distinct in the brief.
Resolve consequential uncertainty or explicitly retain the user's chosen
assumption. For FDM trials, use the actual mating part, retain material/print
settings and label each clearance unambiguously. Printed coupons/gauges are
fit aids, not calibrated metrology; a visually plausible thread is not fit proof.
When increasing clearance, report both the diameter change and remaining
engagement with the measured mate. More clearance reduces binding but also
reduces engagement; material stiffness alone does not determine an optimum.
If pitch/profile is wrong, enlarging the hole does not establish a correct fit.

Keep comparison variants separate from accepted output. A variant using
`incremental qualify/revise` needs a complete project, including its own
`requirements.txt`, local runtime and source-bound checks, not just four wrapper
files pointing outside it. Scaffold/adapt a new project or use the existing
project's supported revision path; preserve approval and lineage.

Keep `build(brief_path=DEFAULT_BRIEF) -> Assembly` in `model.py`.
Keep editable dimensions, units, statuses and sources in `design_brief.json`;
derive relationships. Metadata belongs in `parameters`/`assumptions`, not just
chat. The starter's riser is only a smoke test unless it is the requested design.

New starters track revisions in that same brief. Preserve the template's
`revision=make_snapshot(brief)` binding when adapting `build()`. The default
correction path is `cadkit.incremental revise`, below; it uses
`cadkit.revision.advance_revision` to retain lineage, superseded facts and
approval provenance. Do not manually advance before running it. Tracked re-exports reject
same-ID brief/geometry changes. See [revision state](revision-state.md) for
the schema, migration, snapshot/restore and validated-handoff commands.

`a.export(output)` returns the resolved output Path: `parts` and `assembled`
ASCII STLs in mm, shared-instance `assembly.glb` in metres, offline `viewer.html`,
`manifest.json`. Z-up is preserved. These are meshes, not STEP/B-rep.
STL has no units; import as mm. Use new output after part removals/renames.

The lightweight viewer remains the default. For an explicitly requested embedded
component plus matching HTML, see [viewer backends](viewer-backends.md).
`a.viewer_scene()` returns the shared scene. `a.export(output,
viewer_backend="embedded", viewer_assets=trusted_prebuilt_assets_folder)` uses
optional prebuilt assets; it never downloads or silently falls back.

Tracked exports also create hashed `review.html`/`review-state.json`.
`export(..., previous_output=ancestor_folder)` compares a verified ancestor;
otherwise an existing output supplies the prior revision. The preview wrapper
accepts that same keyword and selects the review panel for tracked source.
See [timing and review](timing-and-review.md) for shared framing, UI-state
retention, staged updates and the difference between readiness and visible review.

For the first requested-geometry preview, preserve the starter's wrapper:

```python
from cadkit.preview import export_preview
assembly, result = export_preview(lambda: build(args.brief), args.output, brief_path=args.brief)
```

The `brief_path` preflight checks known blocking decisions before touching
readiness or calling the builder. Keep `require_modeling_ready(brief)` in
`load_brief()` before creating solids. Without `brief_path`, the wrapper can
only inspect the assembly snapshot after construction; direct tracked export
also rejects blocking snapshots before publication. These are workflow
guards, not a filesystem sandbox or a detector of unrecorded ambiguity.
For admitted builds, it invalidates readiness **before** building and emits a fresh, hashed
`preview-ready.json` only after viewer/manifest publication. It is explicitly
unvalidated. A supervising host can open the viewer immediately; ordinary local
use needs no host. Do not expose an unrelated starter as the requested design.
The same wrapper accepts the optional `viewer_backend` and `viewer_assets`
keyword arguments; preserve it rather than bypassing preview readiness.

## Shape decisions and brief updates

Establish the immediate result and dependency sequence using optional sourced
`deliverable` before detailed modeling. An explicitly awaiting deliverable
blocks modeling; selected/delegated contracts require target, outputs and
sequence. The review page shows the active contract, not a pending replacement.
See [collaboration and drawing tools](drawing-production.md) for its exact
shape, lightweight A/B proposals and portable sheet regeneration.

When geometry intent is unselected, show two cheap A/B sections, ask one visible
question and END THE TURN. Do not build/export/qualify a provisional model.
This overrides preview-first advice. A resolved dimension or incidental
presentation choice needs no detour. Explicit user delegation may proceed,
but is not whole-model or fabrication approval.

The brief optionally contains `decisions`, keyed by stable IDs:

```json
{"decisions":{"profile":{"status":"awaiting_choice","blocks_modeling":true,"selected_option":null,"source":"User has not selected a profile"}}}
```

Status is `awaiting_choice`, `selected` or `delegated`. Resolved/delegated
records require a nonempty selected option and source; awaiting records require
null selection. Only awaiting records with `blocks_modeling: true` block.
Absent/empty decisions retain older-project behavior; free-text
`revision.open_decisions` remain notes, not automatically blocking.

Before the first published model, record the user's selection in the initial
brief, adapt model/checks, then `qualify` once. For an existing accepted project,
keep its source/brief/exports intact while exploring; use a separate draft
under `exploration`. After selection, write `choice.json`, for example:

```json
{"decisions":{"profile":{"status":"selected","blocks_modeling":true,"selected_option":"circular","source":"User explicitly selected the circular section"}},"open_decisions":[]}
```

Then use `python -m cadkit.incremental revise --tier topology --revision shape-02
--delta "Selected circular profile" --brief-updates .\choice.json --browser "C:\path\to\msedge.exe"`
as one command. Adapt related model/check source first, but not the accepted brief.
Decisions merge by ID without deleting unrelated decisions; an existing blocking
flag cannot be cleared to bypass selection. `--brief-updates` accepts only
`decisions`, `retire_decisions`, `deliverable`, `intent`, `assumptions` and `open_decisions`; identity, dimensions,
stage, approval and arbitrary project fields are forbidden. Decision changes/retirement, deliverable and intent
require topology/final tier; scalar updates may also synchronize descriptive
assumptions/open notes. Do not duplicate derived radii/positions as fixed
descriptions: derive display text from current parameters in the builder.
If required changes cannot be represented, report the limitation, not a manual
`advance_revision`/`qualify` workaround.

Updating a decision archives its old sourced record in optional generated
`revision.superseded_decisions`; unchanged decisions are not duplicated.
When a differently named choice replaces an earlier one, retire the earlier ID
explicitly in the same topology/final patch:

```json
{"decisions":{"closure":{"status":"selected","blocks_modeling":true,"selected_option":"Circular screw-on lid","source":"User explicitly replaces the lift-off lid"}},"retire_decisions":{"case_style":{"replaced_by":"closure","source":"Screw closure replaces the earlier lift-off choice"}}}
```

Only existing decisions may retire, with a different current replacement and
nonempty source. Do not update and retire the same ID, retire its replacement
in the same patch or use an unresolved replacement for a blocking decision.
Unrelated decisions remain current. Preserve `decisions` or `decisions.ID` to
reject changes/removal. Later replacement chains retain their history.
Audit affected IDs: the runtime does not infer textual contradictions.

## Checks, not new infrastructure

From the project root, `python -m cadkit.incremental qualify`, then
`python -m cadkit.incremental revise --revision ID --delta "Correction" --updates .\correction.json`
advance/check a scoped correction without reinstalling or packaging.
`python -m cadkit.incremental verify` rejects stale source, exports or reports.
`verify --include-packet` additionally returns the exact checked `review_packet_json`
and `review_page` for the host to stage in the same panel using
`cadReview.loadHandoff(result)`, not local fetching, reload or automatic apply.
The older parsed `review_packet_data` field is retained for existing clients.

For requested drawings, run `python -m cadkit.drawing` from a qualified project.
Its copied runtime and `drawing-settings.json` produce physical-size SVG/HTML,
plans/sections/axonometric outlines and a CSV material schedule without a
session-local generator. `--output` chooses a new destination; `--verify`
checks existing sheets; `--browser` optionally adds PDF through approved
installed Chromium/Edge and Playwright. Unsupported fit at a saved scale
fails rather than shrinking. These are concept views, not fabrication drawings.
For code/topology work,
edit model/check source but retain the old brief/exports, then use
`revise --tier topology --revision ID --delta "Change" --browser "C:\path\to\msedge.exe"`.
Pass sourced facts with `--updates`; full tiers accept a complete replacement
map via `--dependencies`. Recorded failures have an explicit `--recover`
full-tier path with fresh lineage, not silent rollback.
Changed direct exports or rerun validation retire qualification and archive
exact prior records; byte-identical publication retains it.
This is a conservative full rebuild with scope guards, not partial kernel
caching. See [incremental handoff](regions-and-incremental.md) for full tiers,
failure state, qualified-environment limits and staging the existing panel.

Adapt only `checks.check(context)` for design-specific requirements; return a
small JSON-compatible dictionary of measurements. Context exposes:

```python
context.assembly                  # actual Assembly
context.local                    # part-id -> local Trimesh, mm
context.placed                   # instance-id -> placed Trimesh, mm
context.solids                   # instance-id -> placed Manifold
context.require(condition, "failure reason")
context.expect_bounds("instance", [[xmin,ymin,zmin], [xmax,ymax,zmax]])
context.expect_gap("first", "second", expected_mm)  # real native distance
```

`validate.py` handles STL solid comparisons, manifest/GLB checks, static
interferences and real offline raster/controls checks. It saves full
`output\validation.json` and prints a concise summary; open full diagnostics
only on failure. Browser checks preflight the executable and Playwright before
qualification retirement or revision advancement; missing prerequisites leave
the current handoff intact. Browser evidence is published only after all checks
pass. No browser means **geometry_passed_browser_not_run**.
`test_model.py` is an optional thin regression wrapper; do not duplicate
the validator in project code. For intentional overlaps or delivery nuances,
consult [validation and delivery](validation-and-delivery.md).

Do not read `cadkit` implementation, renderer, bundled example, or deep
references routinely. Consult them only for a missing API fact or actual
failure. Read only the relevant functions of a large supplied reference; do
not load an entire unrelated assembly. Preserve all requirements and caveats.
