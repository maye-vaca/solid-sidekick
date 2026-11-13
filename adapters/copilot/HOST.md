# Copilot host mapping

Requested execution: `{{EXECUTION_REQUEST}}`. This is a request to check, not
proof of capabilities, permission or a model-location declaration.
Follow the shared capability contract before filesystem mutation or execution.

Use the active workspace's actual tool definitions and normal approvals.
Copilot CLI, IDE and desktop app integrations differ. A standalone chat may
have no approved project checkout; do not assume its scratch directory is the
user's design workspace. Establish the approved target before executing CAD.

| Operation | Copilot mapping, only when actually available |
|---|---|
| Clarification | Host question UI; otherwise one visible chat question followed by waiting |
| Files and execution | Approved workspace read/edit and terminal tools |
| First display | Open the verified review page in an available browser panel, or give the reachable file/download |
| Revision staging | With approved page scripting, follow the shared checked packet protocol in the saved panel |
| Delivery | Real host attachments, or actual accessible artifact paths |

For app browser-panel staging, discover the browser canvas's supported actions
first. Retain the actual instance handle from the first open; use its documented
JavaScript-evaluation action only if supported. Serialize the verified handoff
as data from `verify --include-packet`, invoke `cadReview.loadHandoff(result)`,
and confirm `cadReview.getState()` matches the
pending revision while the displayed revision remains unchanged. Do not invoke
`apply()` or click Apply for the user. If page scripting is unavailable, the
user can use Load newer review in the existing page.
Do not attempt local `fetch`, start a server or weaken browser security.

Do not invent desktop canvas, attachment or session tools in the CLI/IDE.
The optional Copilot CLI runner is a controlled evaluation harness, not a
normal-approval policy and not a requirement for using the toolkit.
Denied operations stop without tool/transport/host bypasses.
