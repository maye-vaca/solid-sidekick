# Validation and delivery

## Checks are evidence, not labels

Require only the checks relevant to the task, but actually execute them.
Distinguish "source builds", "geometry validated", "export reloaded", "viewer
inspected", and "user-approved arrangement". None implies the others.

| Surface | Relevant check |
|---|---|
| Solid | Manifold status, finite coordinates, positive volume |
| Mesh | Watertightness, winding/positive volume, finite vertices |
| Requested dimension | Bounds or direct geometric measurement against the requirement |
| Mating interface | Hole/shaft dimensions, axes, insertion direction and measured clearance |
| Relative placement | Contact faces, edge alignment, support height, orientation |
| Repeated parts | One definition, correct instance count and transforms |
| Interference | Relevant pairs checked; acceptable/intentional intersections documented |
| Motion | Geometry at relevant positions or a justified swept check, not just the final pose |
| STL | Reload and measure bounds/scale in mm, including a small detailed part |
| GLB | Preflight float32 precision; reload physical solids, triangle geometry, finishes and named placements in metres |
| Viewer | Visible geometry, useful camera, selection/visibility controls and no rendering error |
| Portability | Build/export from a fresh project location without original-session paths |

Do not "fix" a failed test by removing the requirement. Do not repair a mesh in
a way that changes a fit without explaining and checking the resulting geometry.

For a user-requested physical part count, check connected positive-volume
solids, not only file count, mesh grouping or names. Distinguish visual colour
regions from manufactured pieces. Verify actual mating cavities, bottom-out
clearance and a feasible insertion/removal path where applicable.

Keep independent requirement oracles; derive dependent relationships without
copying implementation errors into tests. A finite probe crossing a cut plane
may contain partial material: do not classify the entire probe by its centre.
Distinguish a real geometry failure, an incorrect test expectation and a bounded
numerical residual. For Boolean slivers, quantify any excluded residual and
verify that no meaningful material was discarded; do not broadly relax checks.

## Bounded mesh failure diagnosis

Start with the actual current `validation.json`, brief/revision, failing command
and file path. A transcript summary is a lead, not proof of current disk state.
Separate **observed**, **hypothesized**, **ruled out** and **next experiment**.
Do not promote "in-memory valid" into "the exporter/checker is wrong".

1. Reproduce the smallest failing part once. Compare in-memory, serialized and
   default-reloaded mesh counts, finite coordinates, bounds, watertightness and
   positive volume. The shared invalid-STL error reports reload facts.
2. For custom meshes, check precision at construction before changing export
   or validation. Use `m.Mesh64` with float64 vertices and uint64 indices before
   Booleans. A threaded ribbon built with float32 can produce tiny intersections
   that collapse under default STL vertex welding. A valid in-memory topology
   alone does not establish a robust printable export.
3. Change one cause and rerun the same default export/reload check. Keep its
   negative control and a regression covering the failing fit variants.
   Do not remove watertight/volume checks, globally tighten merge tolerance,
   or declare the failure a false positive without discriminating evidence.
   `process=False` on STL gives unstitched triangle soup, not proof of a solid.
4. Inspect the installed API before using unfamiliar methods. Prefer
   `importlib.metadata.version("manifold3d")` to assuming `__version__`; inspect
   the particular method's help rather than enumerating the entire kernel.
   Do not add SciPy solely to investigate a problem already exposed by basic
   mesh counts and the existing Manifold operations. On Windows, use ASCII
   diagnostic text or `python -X utf8`; an encoding error is not geometry evidence.
5. Each additional diagnostic must resolve a different open hypothesis. After
   two experiments that add no evidence, reassess and report the precise blocker
   instead of repeating analysis, rereading the same files or rewriting another
   nearly identical `_diag` script. Keep scratch scripts outside the project:
   root-level Python files participate in qualified source binding.
6. Across compaction or handoff, retain paths, revision, observed results, ruled-out
   experiments, unresolved hypotheses and the next executable check. Resume
   that check after verifying current files; do not restart the entire trace.
   State success only after the actual command, not while writing its script.

Track units through numerical diagnosis. For example, `6e-9 mm` is `0.006 nm`,
not `6 nm`; neither magnitude by itself excuses a failed export.
After a geometry repair, retain the prior exports/brief and use the supported
topology revision or recorded-failure recovery path. Do not requalify changed
geometry under the old identity or hand-edit failure evidence.

## Use the shared checker

Generated projects include `validate.py`, `checks.py` and `cadkit.validation`.
After exporting, run:

```powershell
python validate.py --browser "<Edge or Chromium executable>"
```

`CADKIT_BROWSER` is the default browser path when set. Browser checks additionally
need Playwright in the validation environment; geometry/export runtime does not.
The checker reloads every current local and placed STL, compares bounds and
symmetric solid differences, verifies manifest provenance/transforms and GLB
sharing/scale/colors, checks all static instance pairs with AABB pruning, and
exercises the real offline viewer. It uses native Manifold distance queries,
not optional SciPy proximity tracing.

GLB checks also compare the independently reloaded physical meshes to the
source, not just their outer bounds. Missing holes can preserve both bounds
and plausible rendering. Finish-color seams are welded only at exactly equal
positions for physical checks; no looser merge tolerance is used to hide lost
detail. The report's `exports.glb` records checked part count and maximum
solid difference in mm^3.

Write only project-specific assertions in `checks.check(context)`: actual
dimensions, holes, bores, placements and required gaps. Return concise measured
results as a JSON-compatible dictionary. `context` supplies `assembly`, `local`
and `placed` Trimesh dictionaries, placed Manifold `solids`, `require`,
`expect_bounds` and `expect_gap`. A deliberately intersecting design may declare
`ALLOWED_OVERLAPS = (("first_id", "second_id"), ...)` in `checks.py`; explain each
allowance. Unexpected overlaps greater than 0.01 mm^3 fail. The thin unit-test
wrapper must use the same allowances when the design requires them.

Full results go to `output\validation.json`; successful stdout is a compact
status/count/time summary. Read full diagnostics only when needed. Missing,
malformed or stale exports fail explicitly. Without a browser executable the
status is **geometry_passed_browser_not_run**, never an implied browser pass.
Model assertions and generic export agreement are complementary: an export
matching the wrong model does not establish that the user's design was met.
Keep an independent numeric/source oracle for reconstruction evaluations.

## Export contract

`Assembly.export` produces:

- `parts`: one ASCII STL per part definition in local coordinates.
- `assembled`: one ASCII STL per placed instance.
- `assembly.glb`: shared part meshes with named placement transforms.
- `viewer.html`: geometry and metadata embedded; no remote scripts/server.
- `manifest.json`: current file list, parameters, transforms, units and limits.

The lightweight viewer is the default. The explicitly selected
[embedded backend](viewer-backends.md) adds `viewer-scene.json`, `viewer-assets`
and a manifest `viewer` entry. The shared checker uses that entry to select
scene/runtime integrity and actual embedded-browser checks. Preview readiness
hashes the companion files too. Do not infer the active backend from leftover
files in a reused output directory.

STLs use mm coordinates but carry no unit field; instruct importers to use mm.
GLB uses metres for vertices and translation, preserving the documented Z-up
modeling convention rather than silently rotating the model.
ASCII STL avoids the float32 small-detail loss encountered in binary STL.
Test actual output: text encoding alone is not proof of correct geometry.

### GLB precision gates

Before creating export files, `Assembly.export` simulates the actual
mm-to-metres-to-float32 position conversion for each local part. It rejects
nonfinite/collapsed vertices, degenerate or non-volumetric physical geometry,
reversed triangles, triangle displacement beyond 0.0002 mm, and solid changes
beyond the shared Boolean-difference tolerance. This predicts serialization
loss; it is not merely a check of the original float64 mesh.

After serialization, the exporter reloads the staged GLB and applies the same
physical/geometry checks, plus exact finish assignment, shared-part references
and placed transforms/bounds. This catches serializer or format-path problems
the prediction cannot establish. Either GLB failure leaves the existing output
files and qualification untouched. `validate.py` repeats the actual GLB reload
checks later, so changed untracked GLBs do not evade geometry validation.

Keep detailed geometry near the part's local origin and express assembly
offsets with `Placement`. A large offset baked into vertex coordinates consumes
float32 precision; an ordinary-looking STL can therefore accompany a collapsed
GLB. The error identifies the part and suggests local-coordinate correction.
The exporter does not silently rebase coordinates, enlarge features, omit GLB
or substitute a different delivery format. If the geometry cannot be represented
within this contract, resolve the requested output explicitly.

These are GLB-specific gates, not full project qualification or a blanket
tangency rule. Independent dimensional/mating checks, normal STL reload and
browser checks remain separate. The exporter still permits an unchecked STL
preview to be published before the shared validator reports an STL failure.
Do not claim its entire multi-file publication is atomic.

Source inputs may be in inches but convert once at the model boundary. Do not
scale an already-normalized `Part` or `Placement` a second time.
Do not call STL "editable parametric CAD"; edit Python parameters and rebuild.

## Input provenance in generated outputs

Tracked projects bind the brief snapshot, preview, manifest and validation
report to one revision identity. Before handing off, run
`python -m cadkit.revision verify design_brief.json output --validated`.
It rejects changed generated files and stale reports; success still does not
mean a skipped browser check or physical fit was verified. See
[revision state](revision-state.md) for lineage, correction and restore limits.

Carry the brief's unresolved assumptions and dimension statuses into the
assembly parameters/assumptions. Visual estimates must remain distinguishable
from measured geometry in the delivered artifacts, not just the conversation.

If the user asks for only source/STL, do not add a film, BOM, shopping exercise,
cut list or drilling template. Explain exclusions that materially affect use.

## File handling and delivery

The exporter stages a build before replacing generated files, but publication
is not an atomic transaction. A file lock or permissions error must be reported.
The exporter preserves unrelated files and old renamed STLs; use a new output
directory for revisions that remove/rename components, or follow the manifest.
Never delete a whole user folder to "clean" an export.

Provide a short executable command, output path, units and remaining limits.
Include the project source, its local toolkit and requirements together so it
can run independently. A generated HTML viewer can be shared alone.
If the host can attach files, attach actual artifacts rather than merely
describing files that have not been generated.

Refresh a current review surface when supported instead of opening a new tab
for every scalar change. Preserve prior outputs for history; package source at
requested handoff or a meaningful checkpoint, not automatically on every edit.
Always validate the particular exports being delivered, including current
provenance; a previously passed report does not qualify a later modified build.

Keep separate outcomes for native agent execution, geometry/export validation,
host visual review, host-assisted recovery and user approval. Retain the failed
run when the host repairs or finishes artifacts, and identify the recovery as
such. Tests of package mechanics do not establish that new prompt guidance
improves agent behaviour; that requires fresh, bounded conversational trials.

## Evaluation scope

Helper and template checks verify the package mechanics. They do not prove an
LLM will consistently ask the right questions or interpret arbitrary designs.
The [revision evaluation](revision-evaluation.md) uses actual fresh conversations
for bracket, enclosure and simplified assembly revisions, including ambiguity,
adverse inputs and format limitations. Consult its per-turn evidence and trial
versions; one controlled conversation per case does not establish reliability
for arbitrary requests or fabrication suitability.
