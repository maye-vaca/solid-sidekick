# Toolkit guide

For normal modeling, start with [the compact public API](public-api.md).
This longer guide is for environment/setup details, not mandatory extra context.

All paths below are relative to the installed `cad-design` skill folder unless
an explicit project path is shown. Resolve them before invoking a shell.
PowerShell examples assume Windows; on other systems use that shell's quoting
and virtual-environment executable path, not literal Windows paths.

## New project

The helper only uses Python's standard library. It does not install dependencies
or execute generated model code.

```powershell
python "<skill folder>\scripts\new_project.py" "<new project folder>"
```

The destination must not exist. If the requested project already exists, work
with it directly; do not delete it to make this helper succeed.

The helper copies `cadkit`, requirements, a demonstration `model.py`,
`design_brief.json`, project checks and run instructions into the new folder.
The model is deliberately labeled as an illustrative riser. It is an environment
smoke test and a pattern to adapt, not a ready answer to a new user's idea.

From the created project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe model.py
.\.venv\Scripts\python.exe -m unittest -v
```

Use an existing project environment instead if it is already appropriate.
Before installing, inspect dependency compatibility with the actual Python/OS
architecture. If an install fails, report the exact package/platform blocker.
Do not assume native ARM works because another ARM operating system has wheels.
Do not silently change Python architecture, backend or output requirements.

Once the brief matches the user's project, adapt the geometry and tests, then:

```powershell
.\.venv\Scripts\python.exe model.py --open
```

The core model exports to `output` beside `model.py`. `--output` chooses another
directory; `--brief` selects a project brief. Relative `--brief` and `--output`
paths resolve from the shell's working directory.

## Geometry API

```python
from cadkit import Assembly, Instance, Part, Placement
from cadkit.geometry import box

assembly = Assembly("Example", "+X right, +Y back, +Z up; millimetres")
assembly.add_part(Part(
    "panel", box(100, 60, 4), "Panel", "Plywood", "#d9b079"
))
assembly.add_instance(Instance("lower", "panel"))
assembly.add_instance(Instance("upper", "panel", Placement((0, 0, 30))))
assembly.export("output")
```

`Part` accepts a Manifold solid in `mm` or `in` and normalizes it to mm.
`Placement` accepts translation in `mm` or `in`; rotation is local X/Y/Z Euler
degrees followed by translation. Define the required relations in code; the
toolkit does not solve general constraints.

Part and instance IDs start with a letter, contain letters/digits/underscores/
hyphens, and must be unique ignoring case. Use ordinary descriptive IDs rather
than platform-reserved device filenames.

`Assembly.parameters` accepts JSON-compatible dimension/provenance information.
`Assembly.assumptions` is a list of strings shown in the viewer and manifest.
Use explicit material/color metadata; do not encode design facts solely in names.

`Assembly.interference_volume(first_id, second_id)` returns mm³ of overlap.
Zero is not a clearance measurement and says nothing about swept motion or loads.

## Existing STL folder

```powershell
.\.venv\Scripts\python.exe -m cadkit.viewer "<STL folder>" --units mm
```

The standalone folder viewer only reads direct STL children and does not
assemble locally centered parts. Unit selection labels coordinates without
scaling them. It uses generic display colors because STL lacks metadata.
For assembly metadata, generate the viewer using `Assembly.export`.

## Bundled foundation

`scripts/foundation` contains the milestone-1 toolkit, requirements, runnable
example and its original README. New projects get local copies, so they do not
depend on the installed skill path after creation.
Read its README for export precision and coordinate conventions when needed.
The toolkit is mesh-based, not an exact-surface CAD kernel.
