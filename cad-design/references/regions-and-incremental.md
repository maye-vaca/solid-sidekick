# Physical finish regions and checked incremental handoff

## Finish regions are surfaces, not manufactured solids

`Part(..., visual_regions=(VisualRegion(...), ...))` optionally assigns finishes
to disjoint triangles of the final, normalized-mm physical mesh:

```python
import numpy as np
from cadkit import Part, VisualRegion
from cadkit.assembly import solid_mesh

mesh = solid_mesh(final_fused_solid_mm)
front = np.flatnonzero(mesh.face_normals[:, 1] < -.999)
part = Part("head", final_fused_solid_mm, "Head", "Nominal polymer", "#00aabb",
            visual_regions=(VisualRegion("face", "Black face finish", "#111111",
                                         tuple(front)),))
```

Derive indices anew from the final post-Boolean mesh every build. If a desired
finish boundary crosses a triangle, the model must first provide that boundary;
this is not a texture-painting, UV or automatic curved-surface segmentation API.
Normalize inch geometry before deriving the final triangle assignments.
Overlaps, out-of-range/duplicate indices, invalid colours and disconnected
region-bearing physical solids are rejected. Unassigned triangles use the
physical part's base colour. Other part construction semantics stay unchanged.

The manifest retains its physical `parts` and `instances` and adds per-part
`visual_regions` with IDs, names, colours and triangle indices. Physical STL
counts do not increase; STL itself still cannot carry colour. GLB keeps one
shared geometry per physical part with per-face vertex colours, not coincident
extra solids.

Both existing viewer backends and tracked current/prior review display a
disjoint surface partition. Region rows are finish surfaces, not extra
manufactured components. Stable render IDs carry `part_id`,
`physical_instance_id` and `region_id`; the embedded scene also lists physical
instance IDs. The title/notes distinguish surface counts from physical counts.
Visibility is per surface row, not a new physical-parts tree. No duplicate
overlay geometry or hidden recolouring solid is introduced.

The validator binds the region table to the source part, checks STL triangle
order, reloads GLB geometry/colours and verifies viewer region geometry and
parent IDs. Existing no-region exports keep the legacy lightweight HTML bytes.

## One revision command, same qualified environment

Run from the existing project root using that project's working Python.
No install, CLI model conversation, archive build or source-model rewrite is
performed by these commands:

```powershell
python -m cadkit.incremental qualify
python -m cadkit.incremental revise --revision eye-inset-corrected --delta "Correct the sourced eye inset only" --updates .\correction.json --preserve dimensions.body_width
python -m cadkit.incremental verify
```

`correction.json` is a dimension-name-to-sourced-fact object, for example:

```json
{"eye_inset":{"value":6.35,"unit":"mm","status":"measured","source":"User correction: 1/4 inch inset"}}
```

The example assumes an adapted model with that dimension and dependency map;
it is not a command to modify the historical Nuvi project. In the starter,
`gap` is a runnable correction case. New starters declare all their dimension
dependencies and their independent checks read requirements from the brief,
not the model's derived metadata. Project-specific hard constraints still
apply: a correction conflicting with them must fail, not auto-rewrite checks.

For a complete runnable starter correction, qualify once, leave the brief/code
unchanged, and use the existing environment:

```powershell
Set-Content -Path .\correction.json -Encoding ascii -Value '{"gap":{"value":40,"unit":"mm","status":"confirmed","source":"Illustrative correction, not a user measurement"}}'
python -m cadkit.incremental revise --revision gap-02 --delta "Correct gap only" --updates .\correction.json --preserve dimensions.width
python -m cadkit.incremental verify --include-packet
```

The command itself advances the brief, supersedes the fact, builds, exports and
checks. Do not first hand-edit the brief, call `advance_revision`, run
`model.py`, or run a second `validate.py`. Those are lower-level operations,
not the default revision sequence. Do not repeatedly `qualify` an already
qualified baseline.

Selected shape/intent changes use `--brief-updates .\choice.json` in a full
topology/final revision. Allowed fields are decisions (merged by ID),
retire_decisions, deliverable, intent, assumptions and open_decisions; identity/stage/approval and dimensional facts
cannot be smuggled through this input. Scalar revisions may synchronize
assumptions/open notes alongside sourced dimension updates, but cannot change
decisions, retire decisions, change deliverable or intent. See [the exact schema/examples](public-api.md).
Updating an existing decision archives its old sourced record. When a new
decision ID replaces an old one, supply `retire_decisions` with the old ID and
its sourced replacement; do not leave contradictory choices current.
An unresolved blocking proposal is rejected before accepted brief, exports
or qualification are touched. Before first publication, author the selected
initial brief/model and qualify once; no published baseline yet exists to revise.

`qualify` rebuilds, exports and runs shared/project validation, then binds the
snapshot, exact manifest/report hashes, project-root Python source, toolkit
Python source, requirements, interpreter and installed dependency versions in
`incremental-state.json`. This is a local consistency record, not an
authentication, hermetic-build or complete external-asset attestation.

The scalar tier requires that binding to match, an existing sourced dimension,
and nonempty dependencies of the form `parts.ID[.feature]` or
`instances.ID[.feature]`. Feature suffixes conservatively authorize their owner
part/instance; they are not sub-feature execution selectors. It records
affected parts/instances, rejects renamed/reassigned IDs, and enforces exact
unchanged STL bytes/finishes for unlisted parts and transforms for unlisted
placements. A missing scope never means "change anything."

The command deliberately uses one full conservative model build and all
project, geometry/export and interference checks. Its same-process validator
receives that just-exported assembly after rechecking the brief, source and
environment following any preview-acknowledgement wait. It constructs a fresh
validation context and still reloads and compares exports, checks finishes,
project requirements and interferences, and runs the required browser tier.
The existing post-validation stability and handoff guards remain in force.
Standalone `validate.py` independently rebuilds from disk; there is no CLI
option to bypass that build. No assembly survives into a later command.
Arbitrary project builders
do not expose a safe partial-build graph. Incrementality here means scoped
revision admission, verified preservation, environment reuse, compact evidence
and no routine packaging, not selective kernel recomputation or a speedup
guarantee. Browser checking is explicit in the report; no browser is
`geometry_passed_browser_not_run`, never a browser pass.

Use `--tier topology` or `--tier final` when code/topology changes or for final
checks; these require `--browser` or `CADKIT_BROWSER` and run the actual shared
browser checks. They do not generate a delivery archive. For part removals,
use a new `--output` plus the qualified `--previous-output` ancestor rather
than leaving orphaned STL files in the current export directory.

For code/topology work, start from qualified old exports. Edit `model.py` and
the directly related independent project checks, **but leave the current brief
and generated exports unchanged** until admission:

```powershell
python -m cadkit.incremental revise --tier topology --revision shape-02 --delta "Describe the authorized shape change" --browser "C:\path\to\msedge.exe"
python -m cadkit.incremental verify --include-packet
```

`CADKIT_BROWSER` can supply the actual existing executable instead. A source
edit makes ordinary `verify` fail until the full-tier revision succeeds; that
is expected, not a reason to run `qualify` under the old ID. Geometry cannot
change under an already-published revision ID.
If the change needs new/corrected dimensions, pass `--updates .\correction.json`.
If dependencies change, pass `--dependencies .\dependencies.json`, containing
the **complete replacement** dimension-to-feature map, not a partial patch.
Scalar tier rejects dependency-map changes. New dimension names must be
supported by the adapted builder/checks. `--preserve` records the contract and
rejects conflicting fact updates; preservation inside changed owner parts
still requires independent project-specific checks.

Before validation and again before handoff, the command rechecks source/environment stability, snapshot
identity, current exports and the validation report. `verify` repeats those
bindings without building or changing the design. Failed checks invalidate
target qualification and write explicit failure evidence. If the authoritative
brief has already advanced, it remains advanced for diagnosis; there is no
silent rollback or transactional multi-file publication guarantee.

All assembly export paths, including direct `Assembly.export` and
`export_preview`, retire current qualification **before** replacing changed
exports. Byte-identical publication keeps it. Rerunning the shared validator
also retires qualification before replacing its bound report. Exact prior
qualification/handoff/manifest/report bytes are retained under content-addressed
`qualification-history`; `incremental-last.json` explicitly says `invalidated`
until a new checked command succeeds. This history is diagnostic evidence,
not a full geometry/source rollback snapshot. Idle files are not watched;
`verify` remains necessary after manual edits or external writes.

After failure, fix the model/check defect without weakening an actual
requirement. If the current source/geometry can requalify under publication
guards, use `qualify`. If repairing it changes already-exported geometry, use
the explicit full-check recovery path instead of editing lineage by hand:

```powershell
python -m cadkit.incremental revise --recover --tier topology --revision repaired-03 --delta "Repair the recorded construction failure" --browser "C:\path\to\msedge.exe"
python -m cadkit.incremental verify --include-packet
```

Recovery requires recorded failure evidence matching the current brief,
intact current or ancestor exports, a fresh revision ID and real browser
checks. It retains the failed revision in lineage and archives its diagnostic
records, rather than relabelling it successful. For damaged/partial target
exports, supply an intact `--previous-output` ancestor while retaining the
failed `--output` for admission. If no intact baseline exists, or the target's
publication manifest is unreadable, stop and restore an intact project
snapshot; recovery is not automatic rollback. Never delete ownership records
or overwrite history to force admission.

The revision writer lock excludes concurrent invocations of this command only.
It is not a filesystem sandbox or a lock for unrelated/manual/other-runner
writers; never auto-clear an existing ownership record. Existing host
preview-acknowledgement gates are still honored.

## Refresh the current panel without replacing the user's view

A successful command emits `cadkit.revision_handoff` and saves
`incremental-last.json` with the exact current revision, packet/hash, check
status and affected scope. The host can load that packet into the existing
panel through `cadReview.loadHandoff(result)`. This stages a pending update without
reloading the page, dropping camera/visibility or auto-applying mid-drag.
The user explicitly applies it; the interaction gate can defer application.
Without that host action, use the panel's **Load newer review** file chooser.
The Python command cannot control the host's display by itself and never claims it
has visibly refreshed a panel merely because it wrote a file.

For a host with browser-page JavaScript access:

1. Run `python -m cadkit.incremental verify --include-packet` immediately before staging.
   Its single JSON result includes `review_page`, `revision`,
   `validation_status` and `review_packet_sha256`. It checks current bindings
   without rebuilding, installing or packaging.
2. On the first display, open `review_page` once and retain the host's actual
   panel handle. On later revisions do not navigate/reopen/reload that panel.
3. Pass the JSON result to `await window.cadReview.loadHandoff(result)`.
   It checks the SHA256 of the exact `review_packet_json` bytes, decodes the
   packet and checks its revision identity before changing pending state.
   The installed host
   guide maps this operation to an actual approved browser tool, if available.
   Serialize values as JSON; never interpolate
   user text as code or fetch it through an unrelated service.
4. Read `cadReview.getState()` and confirm the pending identity matches the
   verified result while the displayed identity/camera remain unchanged.
   Stop there: the user chooses **Apply newer revision**.

Serialize the checked result into a host-owned
`result` value and run this small script in the existing page:

```javascript
await window.cadReview.loadHandoff(result);
const state = window.cadReview.getState();
if (!state.pending || ["schema_version", "id", "parent_id", "brief_sha256"]
    .some(key => state.pending[key] !== result.revision[key]))
    throw new Error("Pending identity differs from checked handoff");
```

Do not fetch a `file:` URL: browsers commonly prohibit it. The checked
serialized handoff and file chooser work without local fetching. If permission
is denied, stop the affected operation without switching transport to evade
the denial. Do not weaken browser security or start a server as a workaround.
No local server is required.

The packet is opt-in because it contains geometry and may exceed a megabyte.
`review_packet_data` remains available for lower-level `cadReview.load(packet)`
clients; use `loadHandoff` for the extra outer-file hash and identity checks.
Compact `verify` without `--include-packet` remains suitable for file-chooser
handoff and does not embed either packet representation;
do not dump it into the conversation for routine updates. If checks or packet loading fail, report the failure and leave the
display alone. A stale/reused packet may be rejected even if it is valid on
disk: the panel also protects its last-shown identity. For manual fallback,
verify first and select the emitted `review_packet` path using the file chooser.
Report a load result as **pending**, not **applied**, and do not infer user
approval from either state.

The current display remains labeled unchecked at export; a checked handoff is
not user approval, live validation, manufacturing fit or physical certification.
