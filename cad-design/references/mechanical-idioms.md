# Mechanical idioms: choose the contract before the geometry

Use this reference when a request introduces a mating, moving, flexible or
manufacturing-dependent feature. Do not repeat intake for facts already in the
brief. A familiar name such as "screw", "hinge" or "snap" is not a complete
geometric specification, and looking right is not a functional check.

Apply the [prototype and assembly evidence policy](operating-model.md#prototype-and-assembly-evidence-policy):
normal fit uncertainty permits a labeled physical trial, not an exhaustive
proof requirement or silent waiver of known geometry/software failures.

## Admission and evidence levels

1. Establish whether the feature is cosmetic, a fit prototype or intended to
   function. Keep that distinction in the existing deliverable and assumptions;
   never silently substitute a decorative envelope for a functional mechanism.
2. Identify the mating part, process/material, motion or retention intent and
   consequential unknowns from the table. Reuse measured/selected facts. Ask
   only the highest-impact missing question and stop when it blocks modeling.
3. Use a tested helper where one exists. Otherwise prove one small feature or
   interface before building a detailed assembly, array or pattern. A scratch
   prototype is not an accepted revision; label it and keep it separate.
4. Define independent geometric checks before implementation: feature count,
   actual section/profile, minimum material, clearance and assembly path as
   relevant. Include default export/reload, not just a plausible render.
5. Promote selected geometry through the existing revision workflow, preserving
   fixed dimensions and recording unresolved physical tests. Do not introduce
   another feature-state file or an unaudited parallel dimensional source.

Use the existing typed decision gate for a consequential unselected approach,
for example this illustrative fragment:

```json
{"decisions":{"retention":{"status":"awaiting_choice","blocks_modeling":true,"selected_option":null,"source":"Retention method has not been selected"}}}
```

Three levels must stay distinct: **tested reusable geometry** (the stated helper
contract), **project-specific geometry checks** (the checks actually executed)
and **physical/engineering acceptance** (not supplied by this toolkit). The
table is guidance, not a catalog of implemented generators or certified parts.

## Feature value and viability

Small volume relative to the whole part does not establish that a feature is
unnecessary. A tiny hole, relief or locating detail may be essential. Check its
stated purpose, mating interface and independent geometric evidence before
judging its value; an aggregate export-error tolerance is not that evidence.

If a requested feature appears redundant or has negligible effect on its
intended purpose, bring it to the user: explain what it does, why it appears
unnecessary and any consequence of keeping or removing it. State uncertainty
when its purpose is unknown. Ask whether to retain or omit it; do not silently
drop it, resize it or reinterpret the requirement.

If a functional requirement cannot be met under the current constraints,
explain the specific blocker and supporting evidence. Distinguish geometric
impossibility from an unavailable toolkit capability, export/process resolution
limit or unverified physical behavior; a failed attempt alone proves none of
these universally. Ask: "Would you like me to look for viable alternatives?"
Preserve the accepted design and wait for permission before pursuing a changed
approach. State the constraint each alternative would change; do not silently
substitute cosmetic geometry, another material, process, backend or format.
Record a blocking choice in the existing brief's typed `decisions`, and update
the requirement and its checks together only after the user selects a change.

## Interface and mechanism catalog

| Idiom | Consequential facts to establish | Construction guardrail and independent checks |
|---|---|---|
| Threads, nuts, screw closures | Nominal system/major, pitch, handedness/starts, engagement, mating evidence, process and radial versus diametral clearance | Use `internal_thread_tool` only for its simplified right-hand single-start internal profile. Check through-bore, pitch/handedness, retained wall, lead-in and default reload. A male screw needs its own external profile; do not relabel an internal cutter as a qualified bolt. No automatic thread-class or fit claim. |
| Clearance holes, countersinks, counterbores, slots | Fastener/head envelope, hole purpose, depth, datum/axis, edge distance and whether dimensions are radius/diameter | Use explicit subtraction from stock. Check the actual stepped/conical section, head seating and remaining bottom/side wall. Do not confuse drill clearance, tap drill and finished thread minor, or pick a countersink angle solely by appearance. |
| Sliding, press and locating fits | Which component moves, insertion direction/depth, process/material, measured mate and allowed play/retention | Separate nominal dimensions, design clearance and machine compensation. Check positive clearance where required and bottom-out separately. A press fit cannot be certified from static interference volume; use a labeled fit trial when appropriate. |
| Blind sockets, pins, bosses and ribs | Insertion depth, bottom clearance, wall/base thickness, required part count and assembly access | Derive cavity depth independently of pin length. Probe the actual void and bottom. Fuse ribs/bosses with finite overlap, not just coplanar contact; verify connected solids and retained wall. Grouped meshes are not a joint. |
| Bearings, bushings, shafts and shoulders | Actual component envelope, rotating/fixed interfaces, axial retention and removal/tool access | Treat purchased parts as measured or sourced envelopes, not invented internals. Check shoulder/seat position, shaft and housing interfaces, axial stack and removal path. A zero-overlap assembly does not establish a running fit or bearing life. |
| Hinges, sliders and pinned joints | Axis, travel/stops, clearances, retention and whether assembled or print-in-place | Model physical parts separately, preserve the axis and check defined poses plus an appropriate sweep. Static endpoint checks miss intermediate collisions. The construction tool's straight-translation access check does not validate rotation or articulated insertion. |
| Snap-fits, detents and living hinges | Material/process, deflection, allowable force/cycles, assembly/release direction and service environment | Geometric flexure/envelope prototypes only unless a separate justified mechanical analysis is supplied. Check interference through insertion/release and local thickness; do not invent force, fatigue or safe-strain limits. Unsupported material behavior stays unresolved. |
| Gears, racks, cams, lead screws and timing pulleys | Mating standard/profile, pitch/module, pressure angle where relevant, tooth counts, center distance, backlash and travel | No dedicated qualified generator is bundled. A ring of decorative teeth is not a gear. Prove matching profiles/contact and motion in an isolated pair before replication; use a suitable generator/backend when a functional profile cannot be justified here. Threads do not automatically qualify a lead-screw drive. |
| Springs and compliant mechanisms | Material, boundary conditions, load/travel, clearance and cycle intent | No force/deflection or fatigue solver is bundled. Helical appearance or a thin beam is only geometry. Separate a shape prototype from a functional spring specification and do not infer performance from positive volume. |
| Enclosure shells, lids, lips and gaskets | Wall process, opening/assembly direction, engagement, retained clearance and closure/seal intent | Construct outer and inner geometry explicitly; do not assume subtracting a uniformly scaled shape yields uniform wall thickness. Check sections, narrow walls, seams, screw access and removal. A gasket groove alone does not establish sealing/compression performance. |
| Fillets, chamfers, blends and draft | Which edges/faces, radius versus bevel, fixed outer envelope and manufacturing intent | There is no general exact B-rep fillet or draft/offset solver in this toolkit. Use a bounded profile construction only when it represents the requested shape; inspect sections and tangency/retained material. Do not turn a bevel into a claimed fillet or let cosmetics change a mating datum. |
| Sheet-metal bends, laser parts and folded tabs | Actual thickness, bend radius, tooling/process, allowance/K-factor evidence, relief and kerf | No qualified sheet-metal unfolding/allowance solver is bundled. A folded display mesh is not a flat pattern. Do not promise bend-correct DXF/STEP from an STL; resolve the production backend before detailed fabrication work. |
| Inserts, captive nuts and purchased hardware | Actual standard/vendor dimensions, insertion/tool envelope, retention process and installation access | Do not silently substitute printed threads for an insert, or a hex pocket for verified nut retention. Check seating, anti-rotation, pull-through material and access; heat-set retention remains a physical/process question. |
| Repeated holes, knurls, vents and lattices | Required count/pitch, orientation, retained ligament, surface purpose and geometry budget | Prove one feature, then a short pattern before the full array. Reuse part instances where parts really repeat. Check exact count, bounds, disconnected islands and minimum retained material; do not spend a long Boolean run on an unreviewed dense pattern. |

## Stop conditions and prototype ladder

Stop and clarify a contradictory fit, unknown mechanism type or unavailable
required exact format; preserve the valid design. If only a cosmetic envelope
is requested, record its simplification and avoid unnecessary detail.

For admitted functional geometry, progress from a section/sketch to one feature,
then a mating coupon/pair, and only then to the full assembly when that extra
prototype is warranted. Do not print or generate every ladder step by default.
Set a bounded first experiment: one part/pair, its required measurements and
export checks. If it fails, follow [bounded diagnosis](validation-and-delivery.md#bounded-mesh-failure-diagnosis)
instead of constructing a custom kernel, renderer or speculative repair chain.

Coupons validate only the sampled part/process/setting combination. Record
material, orientation, scale and observed fit; retain the actual mating object
as the fit authority. Do not extrapolate strength, lifetime, sealing or standard
conformance from one successful print.

For coplanar features, prefer one consistent planar profile when that expresses
the intended shape. Mixing a quantized polygon/extrusion edge with a separately
computed decimal box edge can leave tiny Boolean slivers that collapse under
normal STL welding. Prove the default roundtrip; finite overlap and valid
in-memory topology alone do not rule this out. Do not mask it with relaxed
welding or `process=False`.

When checking a rotating feature's section, isolate that feature before
rotating the section. A hexagonal nut exterior, for example, is not invariant
under a quarter-turn even when its internal helix is correct.

Do not prohibit tangent circles solely from their 2D arrangement. Same-depth
contained cuts may be redundant; different-depth cuts can form valid stepped
holes even when their circular profiles are internally tangent. Evaluate the
resulting 3D material, feature depths and normal export/reload instead.
Externally tangent through-holes can leave zero-width material that fails a
normal mesh reload; that is a property of that resulting solid, not a general
ban on adjacent or overlapping holes. Do not silently change a fit to avoid it.

Faceting must resolve the feature depth, not just its nominal diameter. A
coarse helical chord can fall below the thread's bore radius between samples.
The internal-thread helper adapts helix/core resolution; include intermediate
angular probes when checking a different/custom helical construction.

For fit tuning, quantify what each change buys and costs: radial versus
diametral enlargement, retained engagement, wall and bottom clearance. Do not
choose a universal clearance from material stiffness alone or disguise a
pitch/profile mismatch by making the mating feature progressively looser.

## Where to reuse existing support

The full source package includes `examples\mechanical-idioms`: 14 generated
test-piece sets, local-part STLs/GLBs, individual offline viewers, a gallery,
independent section/gap/connectivity checks and strict export/reload evidence.
These are examples, not additional qualified generators. The cam, compliant
frame and bent bracket deliberately do not claim a functional gear profile,
spring law or sheet-metal flat pattern. None has physical acceptance.
The source-package examples are not copied into an installed skill directory.

- [Public API](public-api.md#threaded-bores-and-fit-trials): thread cutter,
  primitive geometry and bounded feature contract.
- [Physical-language examples](physical-language-examples.md): translate fit,
  pin, placement and part-count intent without asking for CAD terminology.
- [Validation](validation-and-delivery.md): probes, clearances, export checks
  and evidence-first failure diagnosis.
- [Construction production](construction-production.md): the supported
  straight-translation access boundary, not a general motion solver.
- [Revision workflow](regions-and-incremental.md): preserve accepted source,
  isolate exploration and publish only a checked selected revision.
