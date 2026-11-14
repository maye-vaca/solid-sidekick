# OpenCode host mapping

Requested execution: `{{EXECUTION_REQUEST}}`. Treat this as intent, not detected
access or a permission grant. Follow the
[shared capability contract]({{SKILL_PATH}}/references/host-capabilities.md).

Use the installed host's actual read/edit/shell tools under normal approvals.
Ask through an available question UI or one visible reply followed by waiting.
Do not invoke Copilot canvas, attachment or session APIs, or the Copilot CLI
harness. Those are not dependencies of this host.

Open the verified review page automatically in the user's default browser when
the host has no in-app canvas or file viewer. OpenCode has no canvas (GitHub
Copilot does); do not wait to be asked to launch a review page. Opening a fresh
page for the first review is fine; the user still uses Load newer review for
checked packets and chooses Apply. Do not substitute a remote workspace's file
URL for a local downloadable file.

If a direct `file://` navigation is denied, serve the output over a loopback
HTTP server and open that URL instead:
- start `python -m http.server <port> --bind 127.0.0.1` in the output folder as
  a background process;
- open `http://127.0.0.1:<port>/review.html` (or `viewer.html`) in the default
  browser;
- confirm the server responds before telling the user it is ready, then stop
  the server after the user has the page.
Loopback only: never bind the server to another interface. This also works when
a managed device blocks browser reads of DLP-tagged files, because the browser
fetches over loopback instead of reading the file directly.

Ollama serves a model; OpenCode provides agent tools. A localhost endpoint in
a remote workspace is local to that workspace, not necessarily the user's
computer. Endpoint choice and enabled integrations determine model/data
processing boundaries. This adapter does not configure Ollama, cloud fallback,
web tools or telemetry. No local-only privacy claim follows from installation.
Denied operations stop without switching tools or endpoints.

Setup notes for a fresh OpenCode + Ollama project:
1. Install this adapter into the project (the installer refuses package
   folders containing unlisted files; copy a git checkout to a clean folder
   first).
2. Add an Ollama provider to your opencode.json (for example
   `ollama` with `npm: "@ai-sdk/openai-compatible/chat"`, a
   `http://localhost:11434/v1` baseURL, and the model IDs you want);
   OpenCode does not discover Ollama automatically.
3. Quit and restart OpenCode so the `cad-designer` agent and `cad-design`
   skill are loaded.
4. Install the Python runtime dependencies listed in
   `{{SKILL_PATH}}/scripts/foundation/requirements.txt` for the project
   interpreter you use.
