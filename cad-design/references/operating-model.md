# Operating model and supervision

The product contract is **AI-assisted design with CAD execution in the user's
approved environment**, supervised through the host's normal approvals.
The model may be local or hosted; CAD execution may be local, remote or
user-run. Establish these independently using
[host capabilities](host-capabilities.md).

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
