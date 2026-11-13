# Translating physical language into geometry

These are patterns, not canned design decisions.

## "I don't know the term; make that transition gentler"

Treat this as a visual choice, not a request for the user to learn a CAD term.
Offer two small sections in the same orientation: for example, A has a long
gradual rise, while B retains an upright face with only its corner softened.
Mark the same starting/ending points, unchanged height and surrounding fixed
features; shade material so a raised surface cannot be mistaken for a recess.
Use a simple SVG/HTML or text sketch rather than building two complete models.
Label unknown curvature as illustrative, and ask which picture is closer.
End the turn there: do not also build a provisional detailed model. If the
user explicitly says to choose, record that delegation before proceeding.

Store these alternatives separately from the accepted brief/exports. Once the
user chooses, record the intent and use the standard checked revision path.
If neither fits, refine the sketch without treating that iteration as failure.
Do not introduce a new exact radius, tangent join or manufacturing requirement
unless it has supporting evidence. Resolved scalar corrections need no sketch.

## "The 1-inch side is flush with the left edge"

Confirm whether "1-inch" is nominal stock and whether the part is upright.
For nominal 1x2 lumber, actual dimensions may be 3/4 x 1-1/2 inches; verify the
stock rather than applying that assumption universally.

With +X right from the user's fixed viewpoint and the platform's left edge at
X=0, an upright rail whose outside face is flush has width spanning X=0..w.
Its centerline is X=w/2, not X=0. If +X instead points left, derive the opposite
edge from that convention. A camera change does not change the result.

Test rail bottom = finished platform top, rail outside face = platform edge,
rail height = upright dimension, and end positions = required platform extent.

## "Use the factory edge to reduce waste"

Separate finished-part geometry from stock nesting. The part should not change
size just because it is placed against a sheet edge.
Align the specified straight part edge to the stock boundary; retain a factory
side rather than drawing a saw cut there. Check containment, non-overlap, actual
edge coincidence, and any required kerf/tool clearance.
Only create a nesting deliverable when requested; do not infer a production
cutting plan from a visual layout.

## "Move the upper platform higher"

Use a platform-top or support-height parameter. Derive all support lengths,
platform placement and attached-part elevations from it. Check those dependent
surfaces, not just the apparent camera position. Do not change hole pitch or
unrelated exterior dimensions.

## "Make it fit this shaft"

Ask for shaft diameter and intended fit/process if missing. A nominally equal
hole does not guarantee a sliding or interference fit.
Do not silently invent a clearance or manufacturing tolerance. After process
and fit intent are resolved, a provisional prototype clearance may be proposed
explicitly, with source/status and a physical fit test still required. Record
an assumed visual hole if the user requests an early concept; flag it as
unresolved. Nominal size, chosen clearance and actual printer compensation
are different quantities.

## "It is rounder, but has a flat band around it"

Compare a sphere, a rounded drum with an axially straight circumferential band,
and isolated planar patches. These are different surface constructions, not
interchangeable levels of rounding. Ask which interpretation applies or show
simple front/side sections before detailed geometry. Do not equate "flat" with
a planar surface without considering the stated direction.

## "Those eye edges should line up with the shoulder"

Identify the exact eye edge, shoulder feature and front viewing direction.
If retained dimensions conflict with that alignment, state which constraints
cannot simultaneously hold. Do not invent a new mounting arrangement or
quietly change the eyes to make the numbers agree.

## "The pin is 3/16 inch, not 3/8 inch"

Record which quantity is corrected: diameter, radius or length. Supersede only
that input and derive existing mating features from it. Keep shoulder diameter
and pin length unchanged even if they previously shared a numeric value.
If the user deferred sockets, retain that deferral until explicitly lifted.

## "Make it three parts that assemble"

Resolve which features belong to the head/body/pin or other named groups;
separate those physical groups from visual finish regions. Confirm joint fit
and fabrication process before designing clearances. Fuse intended fixed
features, verify one connected solid per requested part, add the authorized
interfaces and check assembly/removal without interference. A collection of
touching STL shells is not necessarily a single printable part.

## "Here's a photo of what I built"

Preserve the planning model unless the user asks to replace it. Create an
as-built interpretation with provenance. Perspective correction of the base
plane does not remove parallax from raised objects.
Use confirmed measurements to correct the interpretation and retain estimates
for what the photo cannot establish.

## "Give me CAD files"

Clarify the required format if it affects the backend choice.
Explain STL = triangle geometry/no units/colors; GLB = named colored assembly;
STEP = exact CAD solids not supplied by this mesh backend.
Generating Python objects is not an export. Build files, reload them, and state
which deliverables are ready.
