# Validated revision state

The existing `design_brief.json` remains the editable dimensional source.
New starters opt into the versioned `revision` block. Older projects without
that block continue as explicitly **untracked**; an invalid block is an error,
not a fallback to legacy mode. Adoption is explicit and should use a new output.

| Field | Contract |
|---|---|
| `schema_version` | Integer 1 |
| `id`, `parent_id`, `ancestors` | Safe current ID, immediate parent (null initially), ordered unique ancestor IDs; current ID cannot be an ancestor |
| `delta` | What this revision requests |
| `preserve` | Facts/features to retain; `advance_revision` enforces preserved dimension names or `dimensions.name` paths |
| `dependencies` | Current dimension names mapped to named dependent features |
| `superseded_facts` | Prior sourced dimension entries, with fact name and the ancestor revision where they were observed |
| `superseded_decisions` | Optional generated history: old name/decision, ancestor revision, replacement ID and supersession source; older version-1 briefs may omit it |
| `open_decisions` | Outstanding decisions, not silently resolved assumptions |
| `user_approval` | Null, or explicit revision ID, design stage and source evidence; prior approval never becomes approval of a new revision |

Current facts are the brief's existing `dimensions`, not another copy in the
revision block. Each requires finite numeric `value`, nonempty `unit`/`source`,
and `measured`, `confirmed`, `assumed` or `estimated` status. Geometry builders
still impose their own positive-size, unit-conversion and fit constraints.
The brief retains intent, stage, coordinates and any project-specific metadata.

## API

Routine published edits use `cadkit.incremental revise`, not the lower-level
helper below. `--brief-updates` accepts checked intent, assumptions, decision
merges and open-decision notes without granting access to revision identity,
stage or approval. See [public API](public-api.md) for runnable examples.

Optional top-level `decisions` records have exactly `status`, `blocks_modeling`,
`selected_option` and `source`. Status is awaiting_choice/selected/delegated;
only awaiting, blocking choices prevent modeling. The starter preflights them
before solids; qualify/revise, preview and tracked publication also guard
their respective boundaries. Nonblocking unknown material does not freeze
a visual concept. These records are hashed with the brief, not proof of
human identity. Older briefs without them remain compatible.
Optional `deliverable` records immediate target, outputs, work sequence and
selection/delegation source. An awaiting contract blocks modeling; the active
review displays it. Topology/final brief updates accept this field and
`preserve=["deliverable"]` protects it. See [the exact contract](drawing-production.md).
Changed same-ID decisions automatically archive their previous record.
For differently named replacements, include
`"retire_decisions":{"old_id":{"replaced_by":"new_id","source":"User's explicit replacement choice"}}`
alongside the new selected/delegated decision. The old ID leaves the current
decision set; unrelated records and previous approval remain unchanged.
Replacements must remain current, and blocking decisions cannot retire into
unresolved choices. `preserve=["decisions"]` or `decisions.old_id` prevents
changing or retiring those decisions. History is generated, not an accepted
brief-update input. Later replacements retain earlier history chains.

```python
from cadkit.revision import advance_revision, make_snapshot

updated = advance_revision(
    brief, "gap-02", "Change gap only",
    updates={"gap": {**brief["dimensions"]["gap"], "value": 45,
                     "status": "estimated", "source": "Explicit example estimate; not a measurement"}},
    preserve=["dimensions.width", "dimensions.depth"],
)
# Low-level API illustration, not the ordinary published-revision workflow.
assembly = Assembly(..., revision=make_snapshot(updated))
```

`advance_revision` returns a new brief, archives changed facts with their
provenance, records parent/lineage, rejects ID reuse and does not mutate the
input. It does not create user approval. An existing approval retains its old
revision ID. Open decisions and dependency mappings persist unless explicitly
replaced; a scalar correction does not silently resolve them.
New fact, decision-update and decision-retirement history entries are appended
in deterministic key order, so replay from canonical saved JSON produces the
same snapshot even when the input object order differs. Existing history is
never resorted or rewritten; prior snapshots keep their original identity.
Feature dependencies are recorded intent, not a constraint solver:
actual dependent geometry and preserved features still need project checks.

`make_snapshot` returns an isolated generated snapshot with a canonical brief
hash. `validate_snapshot` verifies its schema/content identity. Canonicalization
normalizes JSON object order; builders must not depend on dimension-dictionary
ordering. Lists such as placements retain their meaningful order.

## Source, export and handoff

Tracked exports add `revision-state.json`, manifest revision identity and a
hash map of all current generated files. The snapshot is generated evidence,
not a second editable brief. Preview markers carry the same revision identity.
The shared validator rejects mismatched IDs/hashes, stale snapshots and changed
artifacts. A same-ID re-export cannot alter brief content or STL geometry;
forward publication must descend from the existing tracked output. Downgrading
a tracked output to untracked source or publishing backwards is rejected.

Successful validation reports bind the revision and the exact manifest hash.
Use `verify --validated` before relying on such a report; simply reading an old
`status` field is insufficient. Report status still distinguishes omitted
browser checks. File publication is not transactional: interruption may leave
mixed files, but hash verification must reject that output.

From the generated project folder:

```powershell
python -m cadkit.revision schema
python -m cadkit.revision check .\design_brief.json
python -m cadkit.revision snapshot .\design_brief.json .\handoff-state.json
python -m cadkit.revision restore .\output\revision-state.json .\handoff-brief.json
python -m cadkit.revision verify .\design_brief.json .\output --validated
```

Snapshot/restore commands refuse existing destination files. A fresh context
uses the restored brief alongside the existing project source and toolkit;
the snapshot does not contain or recreate model source. Existing source and
the qualified environment must be supplied separately. A regression rebuilds
the starter in fresh processes and compares all generated geometry, viewer,
snapshot and provenance bytes across the handoff.

Hashes establish consistency, not authenticity. A recorded approval/source
claim is not a permission grant, proof of human identity or manufacturing
certification. Never synthesize approval from successful export or validation.
