# Your code-first CAD project

This is an **illustrative display-riser starter**, not your finished design.
It has two reusable part definitions and six placed instances. Adapt the
geometry and tests to your actual project; do not just rename the example.

## Run on Windows / PowerShell

Requires Python 3.10+ and compatible dependency builds for your platform.
From this project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe model.py --open
.\.venv\Scripts\python.exe validate.py
```

An existing Python environment with the requirements can be used instead.
Other operating systems use their own virtual-environment executable path.
Nothing is fetched by the model or the generated viewer.
The first export is labeled **preview/unvalidated**. `preview-ready.json`
is published only after the viewer and manifest are complete; failed rebuilds
clear old readiness before attempting geometry. It is not validation approval.

The helper that created this folder did not install dependencies or execute code.
All runtime source is local; no installed-skill/session folder is needed.

## Edit and rebuild

`design_brief.json` contains the starter's dimensions, units, evidence statuses,
sources and assumptions. `model.py` reads these values; there is no separate
editable numeric parameter block to keep in sync.

Use the checked revision command below for a dimension correction; do not
hand-edit the brief and then re-export under its old ID. The gap, standoffs and
top plate placement update together. Input units are `mm` or `in`; geometry is
normalized to mm once. The "gap" is between the facing plate surfaces.

The default brief and output paths are beside `model.py`, even when run from a
different working directory. Alternate paths are relative to the shell's cwd:

```powershell
.\.venv\Scripts\python.exe model.py --brief .\design_brief.json --output .\revision-02 --open
```

`checks.py` derives independent requirements from the authoritative brief.
Adapt it for actual new features; do not remove a failed requirement just to
get a passing run or duplicate scalar values already supplied by the brief.
Keep the shared export/viewer machinery in `cadkit` unchanged. The optional
`python -m unittest -v` command runs the thin project regression wrapper.
This starter does not automatically advance beyond the `concept` stage.

## Unresolved shape choices

Before first publication, use the brief's optional `decisions` map for explicit
blocking choices. Each record has `status` (awaiting_choice/selected/delegated),
boolean `blocks_modeling`, `selected_option` (null while awaiting), and nonempty
`source`. Resolved/delegated records require a selected option. The starter
checks readiness before solids; preview, qualification and tracked export also
guard publication. Unknown nonblocking presentation/material does not freeze
a visual concept. Guards cannot detect unrecorded ambiguity or authenticate
claimed user approval.

While a shape is unselected, show lightweight A/B sections, ask one question
and end the turn; do not build a provisional detailed model. After selection,
finish the unpublished initial brief/source and qualify once.
For an already published model, retain accepted files while exploring, then
submit selected decisions with `revise --tier topology --brief-updates .\choice.json`.
That checked object permits only `decisions` (merged by ID), `intent`,
`assumptions`, and `open_decisions`. Never hand-advance identity or approval.
Scalar corrections can update descriptive assumptions/open notes alongside
`--updates`, but decisions/intent require a full tier. Derive changing
dimensions/radii/display descriptions from current facts rather than storing
duplicate fixed numbers. If an edit cannot be represented, report the blocker.

## Revision identity and handoff

The brief's `revision` block records ID, parent/ancestors, requested delta,
preserved/dependent features, superseded facts, open decisions and explicit
approval evidence. Current dimensions remain in `dimensions`. Initial user
approval is null; building or validating does not approve a revision.

From the project root and existing environment, qualify once after adapting the
model. Then supply a sourced correction without first editing the brief/code:

```powershell
python -m cadkit.incremental qualify
Set-Content -Path .\correction.json -Encoding ascii -Value '{"gap":{"value":40,"unit":"mm","status":"estimated","source":"Illustrative estimate, not a user measurement"}}'
python -m cadkit.incremental revise --revision gap-02 --delta "Change gap only" --updates .\correction.json --preserve dimensions.width --preserve dimensions.depth
python -m cadkit.incremental verify --include-packet
```

`revise` advances lineage, supersedes facts, builds, exports and validates.
Do not run separate `model.py`/`validate.py` calls around each correction or
requalify the unchanged baseline. Scalar admission requires unchanged source
and declared dependencies; it checks unlisted geometry/finishes/placements.
All geometry is conservatively rebuilt/checked, not partially cached.

For code/topology changes, edit `model.py` and directly related independent
checks first; retain the old brief/exports. Then use:

```powershell
python -m cadkit.incremental revise --tier topology --revision shape-03 --delta "Describe the authorized shape change" --browser "C:\path\to\msedge.exe"
python -m cadkit.incremental verify --include-packet
```

Use the actual existing browser executable or `CADKIT_BROWSER`. Sourced fact
changes use `--updates`; topology/final tiers also accept `--dependencies` with
a complete replacement dimension-to-feature map. Adapt the builder/checks for
new dimensions, but let the command advance the brief. Source edits correctly
make `verify` fail until the full-tier revision succeeds. Do not requalify
changed geometry under its old ID. `--preserve` records feature intent and
protects fact updates; geometry inside a changed owner needs project checks.

If checks fail, no qualified handoff remains; an advanced brief stays advanced.
Fix the cause, not the requirement. `qualify` can renew the current revision
when publication guards permit. If repairing already-exported geometry needs
a new ID, use the same command with `--recover --tier topology`, a fresh
`--revision`, `--delta` and real `--browser`. Recovery requires failure evidence
matching the current brief and intact current/ancestor exports; it preserves
failed lineage and diagnostics. Supply `--previous-output` for an intact
ancestor if needed; unreadable manifests/no intact baseline require restoring
an intact project snapshot, not bypassing guards.

For lower-level schema/restore inspection, rather than the routine edit loop:

```powershell
python -m cadkit.revision check .\design_brief.json
python -m cadkit.revision restore .\output\revision-state.json .\handoff-brief.json
python -m cadkit.revision verify .\design_brief.json .\output --validated
```

The generated snapshot is evidence, not another editable source. Restore
refuses an existing file. Pass a restored brief with `model.py --brief`, or
use it as the current brief in a fresh context with the same project source.
Verification rejects changed files and a stale/failed validation report.
Hashes prove consistency, not the authenticity of approval claims.

## Validation

`validate.py` runs the project-specific assertions plus shared STL/GLB/manifest
reload checks and all-pair static interference checks. It writes full diagnostics
to `output\validation.json` and prints only a concise summary.
No browser supplied means `geometry_passed_browser_not_run`, not a viewer pass.
When a supervising host requests the preview-open gate, deep validation starts
only after that host opens the fresh viewer; ordinary local use does not wait.
For actual raster/control/offline checks, install Playwright in the validation
environment if missing and supply a Chromium/Edge executable:

```powershell
python validate.py --browser "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
```

`CADKIT_BROWSER` also supplies that path. Browser automation is optional, not
a geometry dependency. Neither a static interference pass nor visual plausibility
establishes functional motion, physical fits or load capacity.

## Outputs

- `output\parts`: local-coordinate STLs, useful for individual parts.
- `output\assembled`: placed-instance STLs, aligned for assembly import.
- `output\assembly.glb`: colored, named assembly; coordinates in metres.
- `output\viewer.html`: self-contained offline interactive viewer.
- `output\manifest.json`: current file list, parameters, units and placements.
- `output\revision-state.json`: generated brief snapshot and revision identity, not editable input.
- `output\review.html`: offline current/prior review, labeled unchecked at export.
- `output\review-state.json`: hash-bound review packet for explicitly loading a newer revision in the same panel.
- `output\preview-ready.json`: fresh unvalidated build identity and export hashes.
- `output\validation.json`: actual completed checks, status, times and limitations.
- `output\incremental-state.json`: current source-bound qualification; absent when invalidated.
- `output\incremental-last.json`: explicit checked, invalidated or failed handoff status.
- `output\qualification-history`: exact retired qualification, handoff, manifest and report evidence, not a full rollback snapshot.

STL coordinates are **mm**, but STL has no unit metadata. Choose millimetres
when importing. Local-coordinate parts are not automatically oriented for
printing. GLB preserves the stated Z-up frame. These are meshes, not exact
STEP/B-rep CAD.

Unresolved dimension assumptions appear in the viewer and manifest. Mesh
validity does not establish strength, printability, fits or fabrication approval.
Hardware and materials in this demonstration are illustrative.

After renaming/removing components, export to a new output directory to avoid
confusing stale STLs with current parts. Unrelated files are not cleaned up by
the exporter. Export publication is not transactional if a write fails.

To view existing STLs separately, with the same environment:

```powershell
.\.venv\Scripts\python.exe -m cadkit.viewer ".\my-stls" --units mm
```

The viewer reads direct STL children, labels rather than converts units, and
preserves each mesh's existing positions.

For comparison in a new output folder, pass
`python model.py --output .\revision-02 --previous-output .\revision-01 --open`.
Prior source must be a verified ancestor with compatible coordinates.
The review panel synchronizes physical-mm framing, camera and component-ID
visibility. Load a newer `review-state.json` and apply it explicitly; active
pointer interactions defer application. Reloading a known older snapshot is
blocked. These are offline snapshots, not a live file watcher or validation UI.
The existing `viewer.html` remains available for single-revision review.

Compact `verify` emits the checked review URL and packet file hash. A host that
can fetch local files can read `review-state.json` relative to `review_page`,
check its exact bytes against `review_packet_sha256`, and pass the decoded JSON
to `cadReview.load(...)` in the same page. Alternatively
`verify --include-packet` emits `review_packet_data` for direct data transport;
packets contain geometry and can be large, so do not dump them into chat.
Open `review_page` once and retain the actual host panel handle.
Confirm `cadReview.getState().pending` matches `result.revision`; do not
reload/navigate, inject custom buttons, or call `apply()` for the user.
Without host JavaScript access, verify and use **Load newer review** with the
emitted `review_packet` path. Report pending separately from applied; neither
means user approval. Python writes/verifies packets but cannot control app
canvases. These commands do not package or claim a speedup.

Direct exports also retire qualification before publishing changed artifacts;
byte-identical publication retains it. Rerunning `validate.py` retires the
qualification bound to its old report. Exact records survive in
`qualification-history`; use `qualify` to renew current consistency, never edit
generated qualification records. Idle disk edits are not watched: verify
before handoff.

Optional `Part.visual_regions` uses `VisualRegion` triangle assignments on the
final mm mesh. This preserves finishes without extra physical parts/STLs or
coincident overlay solids. Viewer surface rows are not manufactured-part counts.

The runner automatically collects optional stage evidence through
`CADKIT_STAGE_FILE` and a run nonce. Geometry/export, validation components and
host acknowledgement are measured separately; skipped/unobserved work is not
zero time. Timing records are not design approval or hashed geometry input.

## Optional embedded component

The default above remains the lightweight WebGL1 HTML viewer. With a trusted
prebuilt `cad-viewer` runtime copied beside this project as `viewer-runtime`:

```powershell
python model.py --viewer-backend embedded --viewer-assets .\viewer-runtime --output .\embedded-output
python validate.py --output .\embedded-output --browser "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
```

This writes matching single-file offline `viewer.html`, `viewer-scene.json` and
hosted `viewer-assets`, in addition to the unchanged CAD exports. Browser
validation selects the backend from the current manifest. Readiness also hashes
the embedded companion files. Missing or mismatched runtime assets fail
explicitly; model execution never invokes npm or downloads a renderer.

The component requires WebGL2 and adds runtime size. It does not add B-rep or
fabrication certification. Serve the exported module/engine for web embedding;
use the single HTML file, not module imports, for offline `file://` review.
