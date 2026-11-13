# Host capabilities and execution modes

The design rules, brief and checked commands are shared across hosts.
An adapter maps them to actual tools; a model name or application brand is not
proof that a capability exists. Use supplied context and discovered tool
definitions first. Do not repeat environment intake when already established.

## Establish the execution boundary before CAD work

Keep a compact capability summary in the current conversation, separate from
the dimensional brief. Establish:

- Execution location: approved local workspace, approved remote workspace,
  manual-only, or unknown. A Python/platform report alone cannot prove the
  machine is the user's computer.
- Actual filesystem read/write and Python command capabilities, including their
  approved workspace. A file upload is not local filesystem access.
- Browser capabilities separately: user-opened file/download, automated browser
  inspection, page scripting and embedded display are different capabilities.
- Question and delivery mechanisms: a question tool or a visible reply followed
  by waiting; real attachments/downloads or a path reachable by the user.
- Model processing: local, hosted or unknown, based on the configured endpoint
  and evidence, not the toolkit name. Do not claim verified local-only operation
  from an offline viewer or an installer setting.

Use the installed host guide if present; never invent missing tools. If a
consequential execution boundary remains unknown, ask one focused question and
wait before filesystem mutation or execution. Do not install dependencies or
run a smoke project just to discover tool availability.

## Requested modes are intent, not permission or capability detection

The installer may record `discover`, `local`, `remote` or `manual`. These are
guidance for the assistant, not a sandbox, an authenticated host claim or an
override of approvals. Recheck actual capabilities in the active session.

| Request | Required behavior |
|---|---|
| `discover` | Establish the boundary from available host context; ask if still unknown. No assumption of local execution. |
| `local` | Use only an established, user-approved local execution environment. Missing access is a blocker; do not silently substitute cloud execution. |
| `remote` | Use only an established, approved remote workspace. Explain that files and CAD computation are there; local download/viewing is a separate step. |
| `manual` | Do not execute CAD scripts, edit project files or install dependencies on the user's behalf. Provide inspectable changes/commands and wait for actual user-run results. |

If requested and available modes conflict, explain the mismatch and ask one
focused question. Do not claim completion or silently change the request.
Unknown/remote model processing is not made local by selecting local CAD.
If the user requires local-only model/data processing, establish that separately
before supplying design data to tools or services outside the approved boundary.

## Map the operation, not a vendor's tool name

| Shared operation | Supported mapping |
|---|---|
| Clarify a shape | Use the actual question UI, or ask one visible question and end the turn. No modeling while a blocking choice is pending. |
| Read/edit files | Use approved workspace tools; otherwise provide a patch/file for the user. Do not assume chat upload grants write access. |
| Build/check/revise | Run the same documented Python commands in the established environment, or supply them for manual execution. |
| Show geometry | Open the generated page if supported; otherwise provide a reachable local path or downloadable artifact. A remote `file:` URL is not reachable on the user's machine. |
| Stage a revision | Use approved page scripting only if actually supported; otherwise the user selects the checked packet with Load newer review in the existing page. |
| Apply a staged revision | The user chooses Apply. Do not click it, call `apply()` or equate staging with application. |
| Deliver | Attach actual files/downloads or identify a reachable output path. Never invent a download URL or an attachment tool. |

Use [the checked handoff protocol](regions-and-incremental.md) for packet hashes
and identity. Same-page review remains the goal; when the host cannot transport
new data into the old page, report the limitation instead of claiming it updated.
User-opened viewing is not automated inspection or browser qualification.
Manual results must be attributed to the user; unrun commands stay unrun.

If a capability is unavailable, choose an allowed fallback before attempting
the operation. If permission is denied, stop that operation; do not switch
tools, endpoints, machines or transport to evade the denial. Preserve accepted
artifacts and explain what is blocked. Do not weaken approvals or browser security.
