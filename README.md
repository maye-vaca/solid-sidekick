# Mechanical Design Toolkit

Construction-workflow alpha 0.1.0-alpha.9: one CAD skill/runtime with project-local host
adapters. This is not a CAD application, bundled LLM or universal chat plugin.
This repair release keeps generated files inheriting the project folder's ACL,
preflights browser executable/Playwright before qualification or revision
retirement, publishes browser evidence only after every check passes, writes
`validation.json` atomically, and adds a loopback `serve_review.py` fallback
for `file://`/DLP blocks. No account name is hardcoded and DLP tags are not
stripped. New projects include `cadkit.construction`: bounded assembly-access checks
before publishing revision-bound guides, quantities, storyboards and optional
WebM videos. It checks declared straight translations with conservative convex
swept envelopes and static interference, not arbitrary motion or safe fabrication.
Stationary placement is explicitly not an insertion check. See
[construction production](cad-design/references/construction-production.md).
Review now starts with one full-width isometric current model; **Compare
revisions** reveals the prior view and synchronized comparison presets.
Verbose provenance and updates live under a disclosure, and model metadata and
limitations start collapsed. All notes remain available; short unchecked-snapshot
and concept/fit/safety caveats stay visible. Keyboard and click/tap controls
provide orbit/pan/zoom alternatives. Focused source/browser contrast, keyboard
and reflow checks are not a WCAG or assistive-technology certification.
Existing trial runtimes and exported HTML are not changed.
This release retains the shared repairs found in architecture trials:
deterministic multi-fact/decision history for saved-JSON replay, two/four-choice
checkpoints with unique labels, and responsive title wrapping/drawing alignment.
New history is sorted; old snapshots/history are not rewritten.
Mechanical alpha.5 deliverable, drawing and reliability capabilities remain.
Apply remains a user action and retains camera/component visibility. Shared instructions use
a host-neutral capability contract; installed guides map it to each host.
Native qualification of the revised instructions remains separate work.

The printed-nut follow-up adds a reusable 64-bit internal-thread cutter,
clearance/pitch export regressions, actionable STL failure facts and bounded
diagnosis/resume guidance. Earlier OpenCode trial repairs are retained.
Thread sampling now adapts to profile depth, preventing the reproduced
between-sample groove loss from an admitted coarse request. Export predicts
GLB float32 precision loss before writing, then independently checks the
serialized GLB while staged; existing files remain untouched on GLB failure.
Valid nested/depth-staggered tangent cuts remain allowed; geometry is assessed
in 3D, not rejected by a blanket sketch-tangency rule.
See [trial findings](cad-design/references/improvement-actions.md#printed-nut-opencode-follow-up)
for observed failures, source/copy boundaries and unverified behavior.

Existing designs and installations are not changed by this archive. The
`portable-review` and `supported-revision` examples retain their runtime and historical evidence,
including the earlier portable-review user report; they are not newly
generated alpha.9 examples. New scaffolded projects use the updated runtime.
The new [mechanical-idiom test pieces](examples/mechanical-idioms/README.md)
provide 14 checked specimens/sets (23 local-part STLs), individual offline
viewers and a gallery. Their source uses the canonical runtime; physical fit,
loads, fatigue, sealing and manufacturing suitability remain unverified.
Already-open older review pages without `loadHandoff` retain the supported
file-chooser path; do not reload their view just to gain the new API.

For requested drawings, new projects include `drawing-settings.json` and
`python -m cadkit.drawing`: mesh-derived plans, sections, axonometric outlines,
physical-size SVG/HTML sheets and CSV schedules. Optional approved
Chromium/Edge plus Playwright adds PDF. Copied projects regenerate without a
session-folder dependency. Drawings remain concept-only: no hidden-line removal,
native Revit authoring, exact CAD or fabrication certification.
`shared-repair-integration.json` records the architecture source release and
hash parity of the two repaired modules. No architecture-specific PDF/SVG
runtime or review UI was imported. Focused unfamiliar mechanical acceptance
trials remain separate unfinished work; architecture trials do not replace them.

## Contents

All host entry points require the shared
[prototype and assembly evidence policy](cad-design/references/operating-model.md#prototype-and-assembly-evidence-policy):
check what software can establish, disclose uncertainty and use useful physical
trials rather than demanding guaranteed first-print fit. Known defects and
contradictions are not waived by calling a design a prototype. This is portable
guidance, not guaranteed model compliance; existing installations are unchanged.

- `cad-design`: the one canonical skill, Python toolkit, templates and offline viewer generator.
- `adapters`: thin Copilot/OpenCode profiles and OpenAI/manual startup and capability guides.
- `install.py`: standard-library, no-network project-local installer.
- `toolkit.json`, `VERSION`, `LICENSE`, `THIRD_PARTY_NOTICES`: release metadata and legal boundaries.
- `examples`: historical supported-revision/portable-review examples and the new mechanical-idiom test-piece catalog.
- `tests`: installer/packaging regressions; skill development tests remain with the skill.
- `qualification.json`: historical qualification plus bounded repair/thread follow-ups, not native multi-host acceptance.
- `file-hashes.json`: per-file integrity inventory, not a publisher signature.

## Choose a host and inspect an installation

Use Python 3.10+ and an approved working folder. Run from this extracted folder
in PowerShell (replace `python` with your chosen Python executable if needed):

```powershell
python .\install.py --host copilot --destination "..\my-design-workspace" --dry-run
python .\install.py --host copilot --destination "..\my-design-workspace"
```

Replace `copilot` with `opencode`, `openai` or `manual` as appropriate.
The destination is a project/workspace folder, NOT the host's global config
directory. It may already exist; unrelated files are preserved. Installation
refuses any existing target skill folder, profile, receipt or link/reparse path,
including an identical installation. The package folder itself must contain
only files listed in `file-hashes.json`; the installer also refuses unlisted
files in its own folder, including `.git`, notes and editor files. Copy a git
checkout to a clean folder before running it. There is deliberately no force/overwrite
option. For an update, install into a new workspace and review/migrate your work.
Do not delete existing customizations to silence a conflict.

Dry run verifies the complete package inventory and checks conflicts without
creating the destination. A real install copies the full skill and notices,
renders the selected thin wrapper/host guide and records installed-file hashes in
`.mechanical-design-toolkit\<host>.json`. It installs no Python dependencies,
models or host applications and changes no host/provider/global settings.
If an I/O failure occurs during installation, it exits nonzero and explicitly
reports that a partial installation may remain. Inspect it before retrying;
the installer is not a filesystem sandbox or a concurrent-writer lock.

## OpenCode + Ollama setup

OpenCode supplies the agent runtime and tools; Ollama supplies the model. The
installer connects them to neither; you do that separately.

1. Install the adapter into your project folder (not OpenCode's config folder):

   ```powershell
   python .\install.py --host opencode --destination "..\my-design-workspace"
   ```

   This creates `.opencode\agents\cad-designer.md`,
   `.opencode\skills\cad-design\` (including `SKILL.md`) and
   `.opencode\cad-design-host.md`, plus the receipt
   `.mechanical-design-toolkit\opencode.json`.

2. Point OpenCode at Ollama. OpenCode speaks the OpenAI-compatible API, so add
   an `ollama` provider block to your OpenCode config (project
   `opencode.json`, user `~/.config/opencode/opencode.json`, or the `OPENCODE_CONFIG`
   environment variable). `OLLAMA_API_KEY` is accepted by Ollama but unused;
   any non-empty value is fine:

   ```json
   {
     "$schema": "https://opencode.ai/config.json",
     "provider": {
       "ollama": {
         "npm": "@ai-sdk/openai-compatible",
         "name": "Ollama",
         "options": { "baseURL": "http://127.0.0.1:11434/v1" },
         "models": {
           "qwen3.8:27b": {
             "name": "Qwen 3.8 27B",
             "limit": { "context": 262144, "output": 32768 }
           }
         }
       }
     }
   }
   ```

   Pick a model large enough for agentic tool use (a 27B-class or larger local
   model is a sensible floor). List it in `models` so it shows in the model
   picker.

3. Launch OpenCode from the project folder so it discovers the installed
   agent: `opencode` in that directory, then pick the `cad-designer` agent
   and your Ollama model. OpenCode loads its config once at startup: after
   editing the config or installing the adapter, quit and restart OpenCode.
   Verify with `opencode agent` (or the agent list) that `cad-designer`
   appears, and with `opencode models` that your Ollama model is listed.

   Example first request:

   > Use cad-design to help me design a small mounting bracket. Ask about
   > consequential unknowns before modeling.

Runtime notes:

- The installer copies no Python dependencies. The skill's
  `scripts/foundation/requirements.txt` lists Manifold3D, NumPy and Trimesh;
  install them into an approved virtual environment before the agent runs
  geometry commands.
- The agent needs shell and file tools for execution. In the OpenCode TUI
  (interactive sessions) these are on by default; only headless/CI invocations
  require `--permission edit=allow --permission bash=allow`. Do not run the
  toolkit with `--auto`; the skill's workflow is permission-driven and expects
  interactive approval.
- `execution_capabilities_verified` in the receipt is always `false`; the
  installer never probes your environment. Treat "discover" as intent until
  you have actually run a command successfully.
- When the host has no in-app canvas, the agent opens review pages in your
  default browser. If `file://` navigation is denied (for example a managed
  device blocks browser reads of DLP-tagged files), the agent serves the output
  over `http://127.0.0.1:<port>` instead; that URL is local to your machine.
  New projects include `serve_review.py` for this; the same helper is
  `python -m cadkit.review_server`. Do not strip DLP tags.
- OpenCode's own docs for providers, agents and skills:
  https://opencode.ai/docs/ , https://opencode.ai/docs/agents/ ,
  https://opencode.ai/docs/skills/ , and
  https://docs.ollama.com/integrations/opencode

## Choose the execution boundary independently of the model

```powershell
python .\install.py --host openai --execution local --destination "..\codex-workspace" --dry-run
python .\install.py --host openai --execution remote --destination "..\remote-workspace"
python .\install.py --host openai --execution manual --destination "..\chat-handoff"
```

These are alternative examples, not a sequence. Run the installer in the actual
target environment; pointing it at a folder named "remote-workspace" does not
create a remote environment or upload anything.

`--execution` records intended CAD execution: `discover` (default), `local`,
`remote` or `manual`. The `manual` host defaults to and permits manual only.
Every installation includes a host guide and receipt recording the request
with `execution_capabilities_verified: false`. These are instructions, not
permission enforcement or capability detection. The assistant must establish
the actual boundary before execution. Mode selection does not configure model
inference; local CAD plus a hosted model is not local-only processing.

For OpenAI, the installed guide explicitly distinguishes an approved local
Codex-style workspace, approved remote execution with real downloads, and chat
without suitable tools. A requested local workspace cannot silently fall back
to remote execution. Manual mode requires user-run commands/results, even when
the assistant has some execution tools. Unknown or conflicting capabilities
require clarification, not guessed access. No mode bypasses an approval denial.

## Host paths and launch

| Host selection | Skill destination | Entry point |
|---|---|---|
| `copilot` | `.github\skills\cad-design` | `.github\agents\cad-designer.agent.md`; compatible CLI: `copilot --agent cad-designer` |
| `opencode` | `.opencode\skills\cad-design` | `.opencode\agents\cad-designer.md`; select CAD designer in the installed host |
| `openai` | `.agents\skills\cad-design` | Explicitly read `.agents\cad-designer.md`; compatible Codex clients discover the skill |
| `manual` | `cad-design` | Explicitly read `CAD_DESIGN_START.md` |

Ollama is a model server, not an agent host. Configure OpenCode's endpoint and
local model separately; this installer does not do that. For Copilot desktop,
use a workspace that actually exposes the installed repository customization;
copying files does not register an agent in an unrelated standalone chat.
ChatGPT environments vary: this ZIP does not install a ChatGPT plugin, grant
local filesystem access or guarantee Python/browser support. Without approved
execution tools, use manual mode and run the commands locally yourself.

Each wrapper links its installed host guide; that guide maps the shared
capability contract to actual tools and fallbacks. Copilot browser-canvas
operations are confined to its guide, not mandatory shared instructions.

Host documentation (configuration/discovery can change):
- https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-custom-agents
- https://opencode.ai/docs/agents/
- https://opencode.ai/docs/skills/
- https://developers.openai.com/codex/skills/
- https://docs.ollama.com/integrations/opencode

## First local project

After installation, start the chosen host from the destination and request:

> Use cad-design to help me design a small mounting bracket. Ask about
> consequential unknowns before modeling; use the approved local environment.

The shared skill includes a scaffold helper; read its README and public API
for the commands. Runtime requirements are Manifold3D, NumPy and Trimesh.
Reuse a compatible environment or install the generated requirements into an
approved virtual environment. Dependencies and a working OS/architecture build
are not supplied by this ZIP. No additional renderer download is needed for
the default viewer.

`examples\supported-revision` includes an existing illustrative riser, not your
design. Use its generated README for rebuild commands. Its qualification and
timings are historical evidence, not fresh execution on your machine.

## Try review without an assistant or Python

Extract the entire ZIP, then open
`examples\portable-review\START_HERE.html` in an ordinary browser.
No installer, Python, assistant, server or internet connection is needed for
this viewing exercise. The page explains how to open revision A, load the B
packet in the same page, and choose Apply yourself. It uses the existing
viewer, not another renderer. To send just this exercise to a reviewer, share
the complete `portable-review` folder, preserving its relative paths.

Both revisions were generated with supported checked commands. The extracted,
relocated exercise passed offline Edge checks using the actual file input,
including camera/visibility preservation and invalid/stale-packet rejection.
One user separately reported that B waited for their Apply click and retained
their view in the requested ordinary-Edge flow. Exact user browser version and
OS were not collected. This is not a clean-machine or multi-browser claim.

`examples\portable-review\acceptance.json` separates that user report from
automated evidence. Original `expected-state.json` still says human Apply was
not observed at creation time; the later result does not rewrite that record.
Applying a display update is not design/fabrication approval. The page still
labels exported snapshots unchecked; production validation is separate.

## Support and limits

Installer target layouts, conflict handling and installed-source parity are
tested separately from native agent conversations. This packaging alpha makes
no new behavioral or model-quality claim for OpenCode, OpenAI or manual hosts.
The prior Copilot trial remains partial: the clear-input control needed
interactive permission and native pure-scalar fast-tier adoption was unobserved.
Only Windows ARM64 execution has been exercised here; other OSes are untested.
The Copilot CLI runner remains an explicitly optional Copilot evaluation tool,
not the executor for other hosts. The shared skill owns design/revision rules;
host guides own UI/tool mapping. Unavailable integrations must not be fabricated.

Python computes geometry and the browser renders locally. Model processing
may be remote. Local-only use depends on the selected endpoint and every
enabled integration; no privacy guarantee follows from installing this bundle.
Retain normal approvals. A denial must not be bypassed via another tool.

STL units are mm; GLB uses metres. Mesh output is not exact STEP/B-rep CAD.
Checks and a plausible render do not certify strength, fit or fabrication safety.
The optional embedded viewer runtime, model weights and dependency binaries
are not included. Toolkit-authored code is MIT; see LICENSE and
THIRD_PARTY_NOTICES. Include both when redistributing copied cadkit source.

## Package checks

```powershell
python -m unittest discover -s tests -v
```

These are installer/packaging checks, not native-agent or physical-fit tests.
With runtime dependencies, use `cad-design\README.md` for CAD suites.
