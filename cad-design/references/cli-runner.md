# Optional Copilot CLI evaluation harness

This reference applies only to the supplied Copilot CLI harness, not normal
OpenCode, OpenAI or manual-mode use. It is not a requirement for using the
CAD toolkit. Other hosts use their approved execution tools as described in
[host capabilities](host-capabilities.md); do not launch this runner as a
substitute or bypass when a host capability is unavailable or denied.

`scripts/run_session.py` and its sibling `owned_process.py` use standard-library
Python. Keep both together. The runner does not install
anything or change global CLI configuration. It prefers the standalone Windows
WinGet CLI over an app launcher shim, or accepts an explicit `--cli` path.
On other systems it uses `copilot` from PATH.

```powershell
python "<skill folder>\scripts\run_session.py" --workspace "<approved work folder>" --prompt-file "<request.txt>" --evidence "<new evidence folder>" --python "<project Python executable>" --browser "<Edge or Chromium executable>"
```

The workspace and prompt must exist. The evidence folder must not exist.
The model/provider is not overridden. Plugin auto-discovery and updates are
disabled only in the child process; unrelated known MCPs are disabled.
Repository-local skills remain available. File writes and shell tools are
approved for the controlled run; this is not a security sandbox.
These are harness settings, not the deployed agent's normal permission policy.
Do not label this controlled mode as an interactive approval test or use its
disabled tool catalogue as evidence of how inherited tools behave.

Default behavior:

- CLI version probe: 15 seconds.
- Prompt startup: 60 seconds until the prompt/assistant turn is admitted.
  The clock starts after owned launch/resumption, not while native containment
  is being established. End-to-end elapsed time still includes that setup.
- Silent model/between-turn wait: 120 seconds without meaningful progress.
  Streaming model output refreshes this clock; background-status noise does not.
- An active tool call is not a model stall. This watchdog deliberately does not
  impose a time limit on a legitimate build/test tool. Supervise long tools
  separately if the project needs such a limit.
- At most one retry. A stalled admitted session is resumed by its actual ID,
  with instructions to inspect existing work before continuing. A startup that
  never admitted the prompt may be retried fresh. Ordinary CLI errors are
  reported, not automatically retried. Any retry also requires verified cleanup.

`--startup-timeout`, `--model-timeout`, and `--retries` can change these limits.
Cleanup has a separate bounded 10-second budget, followed by at most 5 seconds
to join the output reader. An uncertain cleanup never authorizes another writer.

Evidence includes per-attempt JSONL streams, usage files and `run-summary.json`.
Each spawned attempt also records `process-N.json` with its exact owned PID,
native containment, Windows creation FILETIME, attempt, start timestamp and
requested resume identity. `attempt-N-result.json` retains the primary failure,
cleanup outcome and timing even when the attempt raises. The version probe
also has `process-probe.json`, stdout/stderr and `probe-result.json`.
A recorded PID is
historical evidence, not proof that the current process with that PID is still
owned; inspect live identity before manual cleanup.

CLI discovery/version-probe exceptions and attempt exceptions (including
cleanup timeout or interrupted execution) write an explicit failed summary
when the evidence folder is writable. Primary execution/cancellation and
cleanup failures are separate records; a cleanup timeout must not replace the
original exception. Raw evidence and accepted-preview references are retained.
Such exceptions propagate without automatic retry.

## Owned processes and writer exclusion

On Windows the runner creates a kernel job with kill-on-close and no breakaway.
The CLI starts suspended, joins that job, and only then resumes its verified
initial thread. If assignment/resumption fails, execution fails closed instead
of falling back to an uncontained CLI. Descendants inherit the job, including
virtual-environment launcher children. Cleanup terminates that owned job and
checks its active-process count reaches zero, even when the original parent
has already exited. A zero-exit CLI leaving active descendants is reported as
failed, not silently successful. Closing the job handle is a termination
backup, not a substitute for recorded verification.

No PowerShell process enumeration, image-name kills, approval changes or
CLI-session lock deletion are involved. Native job/process handles avoid
selecting a different process after PID reuse. This is ownership/lifecycle
control, not a security sandbox or a guarantee about external broker services.
POSIX retains a separately created process group; deliberate group escape is
not contained, and the Windows ARM64 qualification does not certify POSIX.

Each approved workspace has one exclusive `.cad-runner-owner.json` owned by
this runner, separate from the CLI's own locks. Its random token and evidence
path identify the run. Verified cleanup releases only that token's lock.
Unknown cleanup or interrupted ownership release keeps the lock; even a new
evidence folder cannot start another CLI there. An abruptly killed runner
also leaves this fail-closed record.

For a blocked workspace, read that owner record and its `run-summary.json`,
`process-N.json` and cleanup result. Independently establish that prior owned
work has stopped before explicitly reviewing/removing that exact runner-owned
record. Do not clear it merely because its PID is absent or its timestamp is
old, delete CLI locks, or substitute a new workspace to bypass the block.
The guard coordinates this runner's callers, not unrelated/manual writers or
overlapping workspaces that use different roots.

### Negative-timeout investigation

The installed CPython 3.12 Windows pipe-communication path calculates an
internal remaining deadline before `wait()`. That budget can become negative;
`TimeoutExpired` can display it even though the configured timeout was positive.
A deterministic regression reproduces this after pipe EOF. This identifies a
mechanism, not definitive proof of the historical incident's exact timing.
The old PowerShell/`subprocess.run` cleanup path has been removed. New cleanup
uses native job queries with a clamped monotonic remaining budget; its timeout
failure reports the positive cleanup limit. Provider DNS/transport failures
and other CLI/SDK internals are not thereby fixed.

Raw diagnostics may contain local paths/provider metadata; inspect and sanitize
them before sharing. A successful runner exit means the CLI completed, not
that a design is correct; geometric/project validation remains required.

## Early host preview

The runner accepts a marker only for its fresh run nonce, workspace-contained
paths and matching viewer/manifest hashes. `--preview-instances N` optionally
filters out an unrelated starter. Tracked preview/manifest revision identities
must agree; hash consistency is not user approval. It saves
`accepted-preview.json` and prints
a `preview_ready` event while CLI work continues.
Use `--preview-output "<project>\output"` (relative to the workspace) to scope
both notification and the host gate to the requested export. Portability copies
or incidental smoke exports then cannot replace it or wait for another host
acknowledgement. First-preview timing is retained even after later exports.

With `--await-preview`, the shared validator waits up to 60 seconds for the
host to open that actual viewer, clearly titled **unvalidated preview**, then
write `preview-opened.json` inside the evidence folder:

```json
{"run_id":"copy from accepted marker","build_id":"copy from accepted marker","opened_at":"UTC ISO timestamp after actual opening"}
```

Do not acknowledge before opening. The shared validator rejects stale IDs or
changed exports and records publication, host opening and validation-start
times. No acknowledgement fails explicitly; it is not a silent fallback.
The host must watch the accepted marker concurrently rather than waiting for
CLI exit. Ordinary non-supervised projects have no gate or background service.
The evaluation harness includes `host_preview.py` for waiting/acknowledging.

## Successive design revisions

Use `--resume-session "<exact session UUID>"` with a new prompt file and a new
evidence folder for each turn. The runner sends the actual revision request,
not the watchdog recovery message, and verifies that the session identity stays
the same. Preserve a verified project snapshot between turns.
Folder trust is supplied only when creating a fresh session: CLI 1.0.109
rejects `--trust-folder` combined with `--resume`. This applies to explicit
revisions and watchdog recovery alike.

Long-history compaction counts toward the startup deadline. Raising that
deadline only changes waiting; it is not a context-management solution.
For a future fresh-context handoff, first ensure the prior writer is stopped,
then supply the compact current brief, revision scope, approved decisions,
artifact paths and unfinished checks. Do not silently substitute a new session
for an explicitly requested continuation.

`--no-ask-user` selects the CLI's supported noninteractive, reply-based
clarification mode. It is intended for scripted conversations whose next turn
supplies the answer; it does not authorize an evaluator to invent a real user's
design decision. Leave it off for normal host question forms.

## Optional custom agent

`--agent cad-designer` selects the companion repository profile when the complete
agent bundle is present under `.github\agents` and `.github\skills`.
The runner forwards selection on fresh and resumed turns without pinning a model.
Omit it to preserve the normal host-default agent behavior. This flag selects
an existing profile; it does not install one or change global configuration.
