# Checked construction prototypes

Do not let a parts/assembly guide outrun its construction model. Qualify the
actual hardware-bearing variant first with real browser checks, preserving the
old revision. Generate the guide, instance-derived quantities and storyboard
from one declared plan. A raw prose proposal is not an alternative way to
publish unchecked dimensioned assembly instructions.

```powershell
python -m cadkit.construction --plan .\construction-plan.json --output .\construction-01
python -m cadkit.construction --plan .\construction-plan.json --output .\construction-video-01 --browser "C:\path\to\msedge.exe"
python -m cadkit.construction --plan .\construction-plan.json --verify .\construction-video-01
```

Run from the project with its existing Python. Default geometry is `output`;
`--geometry` selects a different qualified export. Existing destinations are
refused. No dependencies, host customizations or old outputs are installed or
changed. Optional recording uses existing Edge/Chromium and Playwright.

## Plan contract

`construction-plan.json` contains these exact fields:

- `schema_version`: 1.
- `revision`: the complete current `revision-state.json` identity, not just an ID.
- `title`, `source`: nonempty, sourced text.
- `context_instances`: explicit reference-only IDs excluded from purchase counts.
- `items`: `{id, description, units, source, notes}`. Each unit is a nonempty
  array of model instance IDs; quantity is the number of units, not a manually
  entered total. For a bought spindle/foot pair, one unit may contain both
  envelopes. Describe sets honestly; this does not infer real kit contents.
  Optional `dimension_keys` references current brief facts and prints their
  values/units/status automatically. Never duplicate cut sizes in free text.
- `steps`: `{id, title, instruction, source, moving, from_mm, to_mm}`. Offsets
  are three finite mm numbers relative to checked final coordinates. No rotations.
- `limitations`: nonempty list of unresolved physical/procedural uncertainties.

Every instance appears exactly once in the inventory or context exclusions;
every instance must also be introduced by the assembly sequence and finish at
zero offset. Previously introduced instances become obstacles automatically.
A repeated moving member must start at its preceding offset; it cannot teleport.
All members in one step share the same translation, as a rigid module.

Example step, AFTER introducing a base and supports:

```json
{
  "id": "lower-module",
  "title": "Mount the preassembled module",
  "instruction": "Lower the loose bridge and already-fitted spindle onto the supports.",
  "source": "Reviewed construction sequence; nominal envelope only",
  "moving": ["bridge", "spindle", "foot"],
  "from_mm": [0, 0, 100],
  "to_mm": [0, 0, 0]
}
```

An initially loose module can be introduced away from the base, then its
spindle inserted there, then the entire module moved into place. This is how
the jig trial's impossible mounted-bridge spindle insertion must be corrected.
Do not omit an already installed obstacle to get a passing result.

## What the gate actually checks

Publication requires current source/environment/brief/export qualification,
an actual browser pass, coherent plan identity/inventory and at least one
translation checked against previously introduced obstacles. Each moving
solid's convex swept envelope must not intersect those obstacles; every
declared assembled pose must also have no positive-volume interference.
This would reject the jig's intersecting wider bridges before a guide is emitted.

Convex envelopes are conservative for nonconvex parts: they can falsely block a
path through a hole/cavity. Stop, expose the blocked case, and refine the
bounded plan or arrange off-assembly preassembly. Never silently waive a clash.
Rotating, flexible, threaded or articulated insertion is unsupported.

Stationary introduction explicitly says **insertion not checked** in the guide
and storyboard. It is not evidence of tool access or assembly motion. One
passing translation does not certify the entire construction process.
Inspect instructions and captions against the actual declared steps; the
runtime cannot infer mechanical truth from natural-language instructions.
Retain physical fit, tolerances, fastening/tool access and force uncertainties.

## Outputs and human review

`guide.html`, `parts.csv`, `assembly.html`, `review.html`,
`review-state.json`, `review-handoff.json` and `construction-state.json` all
refer to the same revision. Recording adds `assembly.webm`, final-frame PNG
and decoded video metadata. The recording uses the shared lightweight renderer,
four seconds per step, no sound and no new geometry builder.
Open `assembly.html` and choose **Play assembly**. Its public
`cadConstructionPresentation.start()` also supports approved isolated recording.

The construction receipt binds exact plan/source/export/artifact bytes; it
is integrity evidence, not authentication or professional approval. Verification
recomputes the bounded plan checks and rejects stale or changed artifacts.
Changing hardware/geometry needs a supported revision and a new plan identity
and destination. Restored projects verify with matching relative files/environment.

Pass `review-handoff.json` to the existing review page's `cadReview.loadHandoff`
to stage the matching model; only the USER clicks Apply. Without page scripting,
use the packet file chooser. Offer the update instead of leaving an old viewer
and a new construction guide as if they were one revision. Preserve camera and
visibility through the existing review workflow.

All outputs remain prototype illustrations, not safe-to-build certification.
