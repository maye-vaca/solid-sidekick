# CAD foundation

A local, code-first mesh-CAD toolkit extracted from the minigolf workflow.
This is milestone 1: a reusable foundation, not yet a skill or an agent.
No CAD application, Node.js, animation, server or internet-connected viewer is required.

## Run the example

Use Python 3.10 or later. Open PowerShell in this extracted folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe example.py --open
```

The example is a small display riser: two drilled plates and four tubular
standoffs. It has **two reusable part definitions and six placed instances**.
It is demonstration geometry, not a load-rated product.

```powershell
.\.venv\Scripts\python.exe example.py --gap 45 --output .\revised --open
```

Changing the gap changes all four standoff lengths and moves the upper plate.
Inspect with orbit, zoom, pan, view presets, component search, hide/isolate,
and fit-selected controls. Units, coordinate conventions, explicit colors,
materials and assumptions come from the assembly, not filename guesses.

Dependencies must have compatible builds for your OS/Python architecture.
Running the example is the geometry/export smoke test; installation alone
is not proof of compatibility. This project was exercised on Windows ARM64.
The version ranges in requirements.txt are compatibility bounds, not a
claim that every possible dependency combination has been tested.

## Generated files

By default, the script writes into `output` beside `example.py`:

| Output | Meaning |
|---|---|
| `parts\*.stl` | One STL per unique part, in its modeled local coordinates |
| `assembled\*.stl` | One STL per placed instance, at its assembly coordinates |
| `assembly.glb` | Colored assembly with shared geometries and named instance transforms |
| `viewer.html` | Self-contained offline viewer; open in Edge or Chrome |
| `manifest.json` | Units, coordinate conventions, dimensions, materials, colors, transforms, assumptions and file references |

**STL coordinates are millimetres. Import as mm; STL itself stores no units.**
ASCII STL is used to avoid binary float32 rounding of small details.
Local coordinates are not automatically laid out for printing.
**GLB coordinates are metres**, following glTF conventions; geometry and
translations are both converted. The Z-up modeling convention is preserved
and documented, not silently rotated.

Each export is built in a temporary directory before publishing generated files.
A write/permission failure during publication is reported, but publication is
not transactional. Rerunning replaces same-named generated files. Unrelated
files and STLs from formerly named components are not deleted: use a fresh output
folder after renaming/removing components, or follow manifest.json for the
current file set rather than scanning an old directory.

## Build your own assembly

`cadkit.geometry` creates Manifold3D solids in mm. You can also use Manifold3D
directly for profiles, extrusions, unions, differences and intersections.

```python
from cadkit import Assembly, Instance, Part, Placement
from cadkit.geometry import box

assembly = Assembly("My project", "+X right, +Y back, +Z up; dimensions in mm")
assembly.add_part(Part(
    "panel", box(100, 60, 4), "Panel", "Plywood", "#d9b079"
))
assembly.add_instance(Instance("lower", "panel"))
assembly.add_instance(Instance("upper", "panel", Placement((0, 0, 30))))
assembly.export("my_output")
```

Keep your geometry functions, named parameters and placement logic in your
project script. Definitions and instances are separate: changing one part
definition updates all its instances.

- A `Part` accepts input units `mm` or `in`; its solid is normalized to mm once.
- A `Placement` accepts translation units `mm` or `in`. Rotations are always
  degrees: local X, then Y, then Z; translation is applied afterward.
- Part and instance IDs must start with a letter and use only letters,
  digits, underscores or hyphens; IDs are unique ignoring case.
- `Assembly.interference_volume("lower", "upper")` reports positive-volume
  overlap in mm³. Touching faces are not positive-volume overlap.
- Parameters and assumptions are saved in the manifest; no general constraint
  solver, material strength solver or automatic fabrication planning is included.

The toolkit checks positive solid volume, finite coordinates, watertightness and
winding before export. It does not certify fit, strength, impact resistance,
safe mechanisms, tolerances or suitability for manufacture. Overlap checks
are explicit and pair-specific, not automatic whole-assembly validation.
It creates mesh models, **not exact STEP/B-rep CAD solids**.

## View an existing STL folder

```powershell
.\.venv\Scripts\python.exe -m cadkit.viewer ".\some_stls" --units mm
```

Only direct `.stl` children are read (case-insensitive). The viewer preserves
positions; it cannot assemble unrelated parts exported at their origins.
`--units` labels existing coordinates; it does not convert them. Imported STL
files have no materials/colors, so a deterministic generic palette is used.
The standalone folder viewer is for visual inspection; open/non-watertight
meshes are not automatically rejected or repaired.

Use `--no-open` to generate without opening a browser, or `--output path.html`
to choose a destination. Generated HTML embeds all data and can be copied
elsewhere without its STL source files.

## Check the foundation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests cover units, rotation/translation, part reuse, parameter changes, invalid
inputs, pairwise overlap, STL/GLB round trips, metadata, offline viewer packaging
and the command-line example. Browser controls are also exercised during
development; Playwright is not a runtime dependency. To run that optional test,
install Playwright and set `CADKIT_BROWSER` to a local Chrome/Edge executable
before running the same test command. Without that variable the browser test
is explicitly skipped.

## Files

- `cadkit\assembly.py`: parts, instances, placements, checks, export pipeline.
- `cadkit\geometry.py`: reusable checked primitive helpers.
- `cadkit\viewer.py`: offline WebGL viewer and optional STL-folder CLI.
- `example.py`: parameterized non-minigolf demonstration.
- `tests\test_foundation.py`: repeatable regression checks.

The bundle is independent of the original session, paths, minigolf geometry
and generated reports. Keep this folder together; no package installation step
is needed beyond installing its three dependencies.
