# CAD design skill

A portable skill for helping a technical person turn a physical idea into a
parameterized model without first learning a traditional CAD interface.
It packages the code-first workflow developed during the minigolf project,
without requiring that conversation, its files or its geometry.

**This is a skill package, not an installed agent or CAD application.**
It includes instructions, a tested toolkit and a new-project helper.
It has not been installed globally.

## Operating contract

**AI assistance with CAD execution in the user's approved environment,
supervised through normal host approvals.**
The model and CAD tools may run in different locations. The offline viewer
does not imply on-device AI or guarantee that design data stays on the machine.
Local, remote and manual execution requests require separate capability checks.
See [host capabilities](references/host-capabilities.md).
See [the operating model](references/operating-model.md).

## What is inside

- [SKILL.md](SKILL.md): triggers, workflow, modeling/review gates and handoff rules.
- [Design workflow](references/design-workflow.md): intake, evidence and revision stages.
- [Physical-language examples](references/physical-language-examples.md): translate "flush", "higher" and similar corrections into geometric relationships.
- [Mechanical idioms](references/mechanical-idioms.md): feature admission,
  fit/motion/manufacturing checks and explicit unsupported-generator boundaries.
- [Toolkit guide](references/toolkit-guide.md): environment setup and API/commands.
- [Public API](references/public-api.md): compact modeling/checking contract; read first.
- Threaded bores: `cadkit.geometry.internal_thread_tool` supplies a 64-bit,
  simplified right-hand 60-degree cutter; see the public API for fit limits.
- [Validation and delivery](references/validation-and-delivery.md): checks, output contract and limits.
- [CLI runner](references/cli-runner.md): standalone discovery, owned-process cleanup, writer exclusion, deadlines and one verified bounded resume.
- [Revision evaluation](references/revision-evaluation.md): real multi-turn scenarios, findings and limits.
- [Improvement actions](references/improvement-actions.md): Nuvi lessons, implemented guidance/runner changes, prioritized engineering actions and fresh behavioural acceptance cases.
- [Revision state](references/revision-state.md): validated brief revisions, correction history, explicit approval provenance and stale-export/handoff guards.
- [Timing and review](references/timing-and-review.md): current-model-first review, opt-in comparison, keyboard/click camera controls, pending updates and stale-page protection.
- [Regions and incremental handoff](references/regions-and-incremental.md): finish colours within physical parts and checked scalar/topology/final revision commands without routine packaging.
- [Operating model](references/operating-model.md): model/execution location and approval boundaries.
- [Host capabilities](references/host-capabilities.md): shared operation mappings and local/remote/manual execution.
- [Viewer backends](references/viewer-backends.md): optional embeddable component and matching offline HTML.
- `scripts\foundation`: bundled milestone-1 Manifold3D/NumPy/Trimesh toolkit.
- `scripts\new_project.py`: creates a self-contained project in a new folder.
- `scripts\run_session.py`: supervised CLI execution without global configuration changes.
- `templates`: a runnable, explicitly illustrative riser and a dimension brief.
- `tests`: package/starter checks; foundation tests are bundled separately.

The workflow tracks measured, confirmed, assumed and estimated inputs; makes
units, axes and viewing direction explicit; shows a rough layout early; separates
parts from assembly placement; checks revisions; and delivers reproducible
source plus the requested exports. It does not claim that a plausible render
is a fabrication-ready engineering design.

## Use as a repository skill

For a GitHub Copilot client that supports repository skills, copy this complete
`cad-design` folder under your repository's `.github\skills`:

```text
your-repository\
  .github\
    skills\
      cad-design\
        SKILL.md
        references\
        scripts\
        templates\
        ...
```

Keep the supporting files with `SKILL.md`. Skill discovery/reload and approval
of scripts vary by client; follow that client's settings if it does not discover
the skill automatically. Copying these files is not installing Python packages.
This bundle does not change any global Copilot configuration.

Example request after discovery:

> Help me design a small mounting bracket using the cad-design workflow.
> I have measured the mounting surface but am not sure what other dimensions matter.

The skill should ask about critical unknowns, establish coordinates and show a
simple layout before refining details. The included riser is only a smoke test,
not the answer to that bracket request.

## Try the helper without installing the skill

From the folder containing `cad-design`, in PowerShell:

```powershell
python .\cad-design\scripts\new_project.py .\my-cad-project
Set-Location .\my-cad-project
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe model.py --open
.\.venv\Scripts\python.exe -m unittest -v
```

Use Python 3.10+ and compatible dependency builds. An appropriate existing
environment also works. The destination must not exist; the helper will not
overwrite even an empty folder. It makes no network requests and executes no
model code. If copying fails after the destination is created, it reports an
error and may leave a partial folder for inspection; it does not clean up user
work. Do not retry by deleting an unfamiliar folder.

Edit `design_brief.json` for the starter's dimensions and evidence. The model
converts explicit mm/in inputs to mm once, derives dependent placements, and
carries unresolved assumptions into the viewer and manifest.
Adapt `model.py`, the brief and checks to the actual design.
New projects share deterministic STL/GLB/manifest/interference/browser validation.
Write only design-specific requirements in `checks.py`, then run `validate.py`.
Full diagnostics stay in `output\validation.json`; browser omissions are explicit.
For repeated failures, use the validation reference's bounded diagnosis recipe
and preserve observations separately from hypotheses across compaction.
See the public API rather than loading toolkit/renderer internals routinely.
The starter also emits a fresh unvalidated-preview marker before deep checks.
The optional supervised CLI gate lets the host open that viewer immediately
and records actual opening before validation starts; it does not require a
server or a host for ordinary local model use.

After adapting the requested model, qualify once with
`python -m cadkit.incremental qualify`. Use `revise --updates` for sourced
scalar corrections instead of manual brief/lineage scripts. For source/topology
changes, edit model/related checks while keeping the old brief/exports, then
use `revise --tier topology` with a real browser. The
[checked revision recipe](references/regions-and-incremental.md) covers
dependency-map updates, explicit failure recovery and
`verify --include-packet` for staging a pending update in the same
`review.html` panel. Changed alternate exports or rerun validation retire
qualification and preserve exact diagnostic records; no live watcher,
automatic apply, partial-kernel caching or speedup is implied.

## Outputs and limits

Projects now include an explicit illustrative deliverable contract to replace
with the actual request, a lightweight A/B checkpoint tool, and portable
`cadkit.drawing` production with saved `drawing-settings.json`.
See [collaboration/drawing production](references/drawing-production.md)
for declarations, supported view/sheet settings, physical scale, verification
and optional browser PDF. Concept drawings do not imply fabrication readiness.

Each project exports local-part STLs, placed-instance STLs, a colored named GLB,
a self-contained offline HTML viewer and a JSON manifest.
**STL coordinates are mm; GLB coordinates are metres.**
STL has no unit metadata. Mesh files are not exact STEP/B-rep CAD.

The bundled backend is Manifold3D, not CadQuery/OpenCascade. Compatibility must
be verified by building/exporting on the actual Python/OS architecture, not by
assuming every dependency version or ARM platform has working wheels.
No animation/video dependencies are required.

The lightweight viewer remains the default, with no npm or optional runtime
dependency. A separately supplied `cad-viewer` prebuilt runtime enables explicit
`--viewer-backend embedded --viewer-assets "<runtime folder>"` exports from
generated projects. These also include a shared scene JSON and hosted component
assets. No downloads or automatic backend fallback occur during export.
See the viewer-backends reference for portable use and validation.

## Check this package

With the runtime requirements installed, from `cad-design`:

```powershell
python -m unittest discover -s tests -v
Set-Location .\scripts\foundation
python -m unittest discover -s tests -v
```

The first suite checks package links/metadata, source parity, no-overwrite
behavior, project creation, independent build/export, generated-project tests
and CLI failures. The foundation suite covers geometry, formats and viewer data.
Both suites have optional browser checks: set `CADKIT_BROWSER` to a Chromium/Edge executable
and provide Playwright in the test environment. These are development checks,
not extra runtime dependencies for a user project.

Milestone 3 exercises real CLI conversations for a bracket, enclosure and
simplified minigolf layout. The separate evaluation archive contains requests,
replies, immutable model stages, independent geometry comparisons and an offline
before/after gallery. It preserves failed attempts and identifies targeted
replays rather than claiming statistical reliability.

The optional milestone-4 `cad-designer` custom-agent profile is distributed
with this skill in the repository-ready `cad-design-agent` bundle. Select it
with `copilot --agent cad-designer` in a supporting client. The skill remains
independently usable; copying it alone does not install or register the agent.
