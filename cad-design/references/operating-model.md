# Operating model and supervision

The product contract is **AI-assisted design with CAD execution in the user's
approved environment**, supervised through the host's normal approvals.
The model may be local or hosted; CAD execution may be local, remote or
user-run. Establish these independently using
[host capabilities](host-capabilities.md).

## Prototype and assembly evidence policy

**Catch what the software can establish, disclose what remains uncertain, and
make the next physical experiment useful.** Apply this policy before modeling,
on resume/handoff and when changing hosts or models. It governs the shared
workflow; do not replace it with either "keep trying until everything passes"
or "prove all physical behavior before allowing a prototype."

| Situation | Required response |
|---|---|
| Known software defect, missing requested geometry or misleading viewer/animation | Fix the affected output before describing it as checked. If blocked, disclose the failure and preserve the last valid design; do not bypass checks, hide missing features or claim completion. |
| Demonstrable contradiction, such as a rigid part larger than its only insertion opening | Explain the evidence before recommending fabrication. Ask whether the user wants viable alternatives; do not silently change the fit, mechanism or manufacturing assumptions. |
| Uncertain printed fit, friction, shrinkage or material behavior | Continue the agreed concept/fit-prototype workflow when relevant software checks pass. Label the uncertainty and propose a bounded physical trial; do not demand guaranteed first-print fit or treat ordinary calibration as design failure. |
| Expensive, hazardous or irreversible assembly | Explain the consequences and require proportionately stronger evidence before recommending fabrication or use. A mesh check or successful prototype is not engineering/safety approval. |

Keep three claims separate: the geometry represents the requested dimensions;
the exported files and any supplied instructions faithfully represent that
geometry; and the physical parts actually fit and function. Evidence for one
does not establish the others. Static final placement does not prove an
insertion path, a video recording does not prove correct assembly instructions,
and matching a nominal thread profile does not guarantee printed fit.

For an ordinary fit prototype, use the supplied measurements, run relevant
geometry/export checks, state which interface or behavior remains uncertain,
and identify what the next trial should measure. Printing a measured nut,
observing a snug fit and adjusting clearance is a legitimate iteration, not
proof that the original modeling workflow failed. Avoid unnecessary coupons
or repeated intake when the requested prototype is already a useful trial.

Preserve declared functional features. Small relative volume is not evidence
that a feature is dispensable. Follow
[feature value and viability](mechanical-idioms.md#feature-value-and-viability)
before proposing removal or alternatives. Unverified behavior is not proven
impossibility; conversely, "prototype" is not permission to ignore a known
geometric contradiction or software defect.

Carry the agreed prototype purpose, relevant evidence, unresolved physical
questions and next trial forward in the existing brief's deliverable,
assumptions and revision record. Use typed blocking decisions only for actual
unselected consequential choices, not merely because physical fit is untested.
Resume from those facts instead of inventing stricter acceptance criteria,
silently relaxing requirements or retrying failed approaches indefinitely.
Software fixes and unchanged approved work need no new design-choice approval;
changes to the user's requirements do.

This is a portable agent instruction, not a guarantee of model compliance or
a new automatic assembly solver. Existing runtime checks enforce only their
documented contracts and recorded decisions. Installed copies must include
this policy to apply it; changing the source package does not update them.

## What runs where

- AI reasoning uses the host's configured model endpoint. This package neither
  ships a model nor selects a local or hosted provider.
- Python, Manifold3D and export/geometry checks execute in the approved working
  environment. Generated source, STL/GLB, manifests and viewers are files in
  that environment; remote workspace files are not on the user's computer
  until explicitly transferred.
- The exported HTML viewer is self-contained and works offline. That does not
  make the model conversation or the whole design workflow offline.
- Prompts, file content and tool output are processed where the selected model
  runs and may also reach enabled integrations. Follow the actual data policies;
  do not promise that design data never leaves the machine without evidence.
- In manual-only chat, the assistant proposes changes/commands; the user runs
  them. Uploaded source and a readable skill do not grant terminal or local access.

## Permissions are owned by the host

The agent inherits available tools and normal approval rules. An execution-mode
request is not an enforced local-only sandbox or a permission grant. Extra capabilities
may be used when relevant to the user's task and approved, not merely because
they are available. Do not add integrations, install globally, alter agent
configuration or delegate by default.

Show the requested operation and its scope through the host's permission UI
when approval is required. Do not suggest blanket access just to make the CAD
workflow proceed. If permission is denied, stop the affected operation and
preserve the last valid design. Explain the blocker; do not retry through
another tool or weaken permission settings to evade the decision.

## Evidence is configuration-specific

The original milestone-3/4 scripted evaluations preapproved local writes and
shell commands while disabling delegation and unrelated integrations. Those
results establish the tested geometry and workflow, not behavior under every
host permission configuration.

A normal-approval test must identify the actual client, tool availability and
approval decisions, including denials. Client support, visibility of previews
and available question tools vary. Do not report a simulated client as a tested
desktop/IDE UI or a single clean trial as a guarantee of tool-policy compliance.
