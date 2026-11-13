# OpenAI host: check the actual environment

Requested execution: `{{EXECUTION_REQUEST}}`. Installation records a request,
not detected access, approval or a model-location declaration.
Use the [shared capability contract]({{SKILL_PATH}}/references/host-capabilities.md).

## Local workspace

For Codex CLI, IDE or a desktop environment with established approved local
tools, use the installed skill and normal filesystem/terminal approvals.
Confirm the workspace is on the user's machine or an explicitly approved local
connection; the product name alone is not proof. Execute the documented CAD
commands there. Open the generated page locally when supported; otherwise
give the actual accessible path for the user to open.

## Remote execution workspace

If execution is in a cloud/sandbox/remote workspace, state that location.
Proceed only when this remote boundary is established and approved, and not
when the user requested local-only execution. Dependencies/platform support
still need verification there. The Python process, exported files and validation
are remote; downloading them does not relocate the already performed computation.

Use actual download/attachment support to transfer the review page, checked
packet and requested exports. If downloads are unavailable, report the handoff
blocker. A remote `file:` URL does not open a file on the user's computer.
For updates, the user loads the downloaded checked packet in the existing
page and chooses Apply. Do not claim remote browser checks were local checks.

## Chat without suitable execution tools

Use manual mode: provide inspectable source/patches and commands, have the user
run them locally, and interpret the returned results with explicit attribution.
Do not call unrelated tools to simulate terminal access. File uploads and
skills do not grant access to the user's computer. Do not claim commands ran,
files were edited, validation passed or an HTML page was opened without evidence.

## Discovery and mismatches

With `discover`, establish which of the above applies from actual host context.
If unknown, ask one focused question before mutation/execution. A local request
with only remote tools is blocked pending a user decision, not authorization
to upload or run there. An explicit manual request forbids assistant-run CAD
even if execution tools happen to exist. Selecting a mode changes neither
host permissions nor data policies. Denials stop without alternate-tool,
transport or host bypasses.

The `.agents\skills` layout targets compatible Codex-style local discovery.
ChatGPT surface/account support varies. This ZIP does not register a ChatGPT
plugin or connector, and local CAD tools do not make a hosted model local.
