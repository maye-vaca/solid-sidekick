# OpenCode host mapping

Requested execution: `{{EXECUTION_REQUEST}}`. Treat this as intent, not detected
access or a permission grant. Follow the
[shared capability contract]({{SKILL_PATH}}/references/host-capabilities.md).

Use the installed host's actual read/edit/shell tools under normal approvals.
Ask through an available question UI or one visible reply followed by waiting.
Do not invoke Copilot canvas, attachment or session APIs, or the Copilot CLI
harness. Those are not dependencies of this host.

Open the verified review page in an approved browser when possible. If there
is no page-scripting tool, provide a reachable local path or actual download;
the user uses Load newer review for checked packets and chooses Apply.
Do not substitute a remote workspace's file URL for a local downloadable file.

Ollama serves a model; OpenCode provides agent tools. A localhost endpoint in
a remote workspace is local to that workspace, not necessarily the user's
computer. Endpoint choice and enabled integrations determine model/data
processing boundaries. This adapter does not configure Ollama, cloud fallback,
web tools or telemetry. No local-only privacy claim follows from installation.
Denied operations stop without switching tools or endpoints.
