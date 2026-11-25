# Stage evidence and revision review

## Timing the actual path

The runner records CLI-probe and ownership overhead, prompt admission, observed
model/tool/compaction spans, cleanup, first readiness and first host-reported
opening separately. Event receipt is timestamped in the reader, not when a
backlogged event is consumed. Unsupported/missing telemetry is `not_observed`;
an interrupted span is incomplete, not a successful duration or zero.
Model activity is provider/stream elapsed time, not measured GPU compute.

The runner supplies a scoped `CADKIT_STAGE_FILE` and run nonce to its CAD
children. Outside the runner these are optional:

```powershell
$env:CADKIT_STAGE_FILE = "C:\approved-work\evidence\stages.jsonl"
$env:CADKIT_PREVIEW_RUN_ID = "explicit-local-run"
python model.py
python validate.py
```

`export_preview` measures the real builder and export calls. The shared validator
measures its total invocation, rebuild, host-gate wait, project checks, export
reload checks, interference checks, browser checks when requested, and report
write. Readiness markers include geometry/export durations; timing evidence is
not part of hashed geometry snapshots, preserving reproducible exports.
The same-process incremental command does not build the model twice:
`geometry` records its full build and `validation_context` records fresh context
construction using that exported assembly. Its nested `validation_source_guard`
checks source/environment and brief stability after the acknowledgement gate.
Standalone validation retains `validation_rebuild`. These names distinguish
removed duplicate construction from retained mesh/context and check costs;
they are not evidence of partial-kernel caching.
Local CAD spans use the high-resolution monotonic performance counter; the
runner's cross-process orchestration origin remains a separate monotonic clock.

Existing delivery orchestration can instrument its actual packaging operation:

```python
from cadkit.timing import stage
with stage("packaging"):
    # Execute the existing archive creation/verification here.
    create_and_verify_archive()
```

This is not a new packaging engine or an automatic performance optimization.
`run-summary.json` groups scoped stage evidence; malformed evidence is explicitly
invalid, and mismatched-run records are counted rather than adopted. Nested
validation stages overlap the validation total, and tool spans can include all
CAD stages. Do not sum these as disjoint time or infer end-to-end savings from
geometry alone.

`first_ready_orchestration_seconds` includes the CLI probe and owned launch.
`first_visible_preview` is only `host_reported_open` after a matching,
post-publication host acknowledgement; otherwise it is `not_observed`.
Its orchestration seconds measure receipt of that evidence, not the exact
first rasterized frame. First readiness/open observations survive republishing.
Old `first_preview_seconds` retains its cumulative-attempt clock for compatibility.

## One current revision-review panel

Tracked exports add `review.html` and `review-state.json`, both hashed by the
manifest. Preview notifications and starter `--open` use `review.html`.
Untracked legacy exports still use `viewer.html`. Its model metadata and
limitations start collapsed as well; existing exported files are not rewritten.
The read-only review shell reuses the established lightweight renderer for
both views, including when primary exports use the optional embedded backend;
it does not alter the private SDK's public API or require new runtime assets.

By default, reusing an output records the last tracked revision as a reference. For new
output folders, name an existing ancestor explicitly:

```powershell
python model.py --output .\revision-02 --previous-output .\revision-01 --open
```

Prior artifacts are verified before adoption and never modified. The comparison
keeps only current/prior geometry, not an ever-growing history. An unchanged-ID
re-export retains the same prior reference. Unrelated lineage, altered prior
files and incompatible coordinate conventions are rejected.

The page opens with one full-width isometric **Current model**. **Compare revisions**
reveals the prior reference and synchronized comparison presets; it is disabled
when no prior reference exists. Turning comparison on or off preserves the
camera, selection, visibility and pending update. The preference is stored
with that page's browser-session UI state. Narrow layouts stack the two views.
Revision IDs/hashes, captured prior validation status, the deliverable and
file-loading controls remain available under **Review details and updates**.
Staging an update opens that disclosure but does not apply the revision.
The short unchecked-snapshot and concept/fit/safety caveats remain visible.

Both views use one physical-mm orthographic frame, not independently
normalized fits. Camera, zoom, pan and component-ID visibility synchronize.
Presets deliberately reset the shared camera. Ordinary interaction does not.
Resizing or revealing a hidden frame does not broadcast unchanged camera state
back over a newer interaction. The embedded renderer avoids duplicating the
page title and caveat; standalone viewers retain both.

The focusable canvas supports arrow-key orbit, Shift + arrow pan, + / - zoom
and Home to fit visible geometry. **Move / zoom** also exposes click/tap
alternatives to dragging and scrolling. Components have named visibility
checkboxes, selection buttons with pressed states, dimensions and materials.
Model metadata and assumptions remain in keyboard-operable disclosures.
These controls and source/DOM checks are accessibility improvements, not a
claim of WCAG conformance or screen-reader/assistive-technology certification.

In the same panel use **Load newer review** with the newer `review-state.json`.
The packet and brief hashes are checked before staging an update. **Apply newer
revision** preserves world-space camera and matching visibility; it defers while
a pointer interaction is active. New component IDs default visible. Browser
session storage retains UI preferences, never old geometry. Reloading a file
older than the revision already shown in that panel blocks rendering instead
of silently restoring old geometry. Storage failures are surfaced.
The last-shown identity remains the recovery floor: after showing C and
reloading embedded A, intermediate B cannot unblock the page. A checked packet
for exactly C can recover the display, or a descendant can advance it. The
same revision ID with a different brief hash cannot recover it.

The default checked host recipe uses
`python -m cadkit.incremental verify --include-packet` for direct serialized
data transport to `cadReview.loadHandoff(result)` in the **existing** panel.
It verifies exact packet bytes and revision identity before staging; no `fetch`
of local files, server or browser-security change is needed. This
does not navigate/reload or automatically apply. Confirm the returned pending
identity with `cadReview.getState()` and leave **Apply newer revision** to the
user. See [the complete handoff recipe](regions-and-incremental.md) for first
opening, exact checked data and the manual file-chooser fallback. Never inject
custom reload banners or claim packet publication means visible application.
Older already-open pages without `loadHandoff` can still use their file
chooser with a compact verified packet; do not reload away the user's view
merely to gain the newer staging API.

Current geometry is explicitly **unchecked at export**. A prior validation label
is a captured report status tied to its old manifest, not live certification.
Run the shared validator and `revision verify --validated` separately. The
offline page cannot detect external disk edits while idle: refresh or explicitly
load newer data. Different file URLs/panels have separate UI state; no global
revision registry, live file watcher, user approval or fabrication certification
is claimed.
