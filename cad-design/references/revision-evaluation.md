# Real revision scenarios

The later [Nuvi improvement actions](improvement-actions.md) distinguish updated
guidance and runner fixes from engineering work and conversational re-evaluation
still pending. These older trials do not validate the new prompt wording.

The accompanying milestone-3 evaluation archive exercises three actual
project-local Copilot CLI conversations, not a parent agent editing examples
and calling that a conversational test. Each case starts without an existing
model and continues by its actual session UUID.

| Case | Revisions and adverse requests |
|---|---|
| Printed bracket | Extend one edge by half an inch without moving existing features; clarify unspecified hole movement; increase only the foot-hole spacing by a total quarter inch; reject holes too large to remain inside the retained faces |
| Enclosure | Reduce walls/floor while preserving the body cavity; derive the smaller outside and matching lid; add an under-lid ring with four nominal 0.3 mm gaps; reject conflicting wall/cavity/outside dimensions |
| Simplified minigolf | Correct a rail from alongside to on-top/flush-left; widen the platform and derive rotor/shaft centers; preserve shared component geometry and heights; explain the exact-STEP limitation |

The selected conversations cover 13 turns and nine geometric states, with
independently checked geometry and preserved valid designs on blocked turns. All inputs
are confirmed fictional design intent, not measurements of the original
minigolf assembly. The layout fixture is not the full approved rotor/hub.
Current/past prompts are supplied to each modeling session; future turns and
the independent expected solids are kept outside its workspace.

The independent checker compares full placed solids, local part geometry,
placements and measured relationships, not just model-authored checks or
matching bounds. It also rebuilds native source in a fresh process on
clarification/rejection turns, preventing stale valid exports from concealing
changed invalid source. Model-driving dimensions, coordinate frame, concept
stage, provenance and unrelated user files must survive.

## Findings carried into this version

- CLI 1.0.109 rejects `--trust-folder` combined with `--resume`. Trust is now
  added only to fresh sessions, for both ordinary revisions and stall recovery.
- A bracket reply bundled scope and distance questions. Clarification guidance
  now makes one decision per turn explicit, including reply-only mode, with a
  concrete affected-feature example. The affected conversation is replayed
  from scratch, not silently patched into a successful transcript.
- A valid STEP reply said "not possible", which the evaluator initially failed
  to recognize. Its phrase matcher was corrected and regression-tested; the
  preserved reply/source/geometry was reassessed without a new model run.

The evaluation archive retains these failures and identifies selected trials
and reassessments. It includes source, briefs, STLs/GLB, offline viewers, plain
assistant replies, independent checkers and rebuild instructions, without raw
provider diagnostics. Its `index.html` offers initial/revised comparisons.
The skill is supplied separately and remains portable; nothing is globally
installed and no dedicated agent wrapper is included.

This is bounded behavioral evidence, not a statistical benchmark, arbitrary
natural-language constraint solver, manufacturing qualification, physical fit
verification, strength analysis or safe-motion certification. Mesh output is
still not exact editable STEP/B-rep CAD.
