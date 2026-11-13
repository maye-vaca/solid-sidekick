# Optional embeddable viewer

The default remains the lightweight, self-contained WebGL1 HTML viewer.
Its Assumptions / limitations section starts collapsed; Read more expands all
notes and Collapse hides them again. The native disclosure supports keyboard
activation. A brief concept/fit/safety caveat stays visible. The same renderer
is used by current/prior offline review frames; opening notes does not Apply a
pending revision or change the camera. Existing exported HTML is unchanged;
new exports use the updated presentation.
Use it unless the user requests the embeddable component/matching HTML.
Do not install npm/Rust, fetch runtime files or silently change backend during
model generation.

The separate, optional `cad-viewer` package provides a prebuilt `dist` folder
and a framework-independent sandboxed component. It uses three-cad-viewer 5.1.3
and requires WebGL2; standalone output is larger and software rendering is slower
than the lightweight renderer in the reference evaluation.

## Export

```python
assembly.export(
    output,
    viewer_backend="embedded",
    viewer_assets=trusted_prebuilt_assets_folder,
)
```

The runtime folder must contain `assets.json` and its eight matching files.
Missing, incompatible or mismatched assets fail explicitly before replacing
existing exports. Runtime hashes check integrity, not trust/authenticity.
The model does not download assets or execute npm. The Python geometry
requirements are unchanged. The optional module/native source package and
prebuilt runtime are supplied separately, not copied into every skill project.

Preserve the preview wrapper for first previews:

```python
assembly, result = export_preview(
    lambda: build(args.brief), args.output,
    viewer_backend="embedded", viewer_assets=args.viewer_assets,
)
```

The starter CLI exposes matching `--viewer-backend embedded --viewer-assets`
options. For a portable project, copy the trusted runtime folder with that
project (for example `viewer-runtime`) and pass a relative path. Do not hardcode
the skill's source/session folder into the model. Default CLI use remains
`python model.py`, with no viewer runtime dependency.

Embedded export adds:

- `viewer.html`: one offline file containing the runtime, styles, notices and scene.
- `viewer-scene.json`: a versioned scene for the embedded component.
- `viewer-assets`: the prebuilt hosted module/engine, notices, types and schema.
- `manifest.json`'s `viewer` entry: backend, scene/assets paths, runtime/API version.

The usual STLs and GLB are unchanged. Explicit backend changes are not cleanup
operations; use a new output directory to avoid confusing old companion files
with the current manifest. Readiness hashes cover embedded companions as well
as viewer/manifest; invalid exports cannot retain a ready marker.

## Component and scene identity

`assembly.viewer_scene()` returns the shared scene without writing files or
requiring runtime assets. It uses mm/Z-up, stable instance IDs, reusable part
IDs, source transforms, original bounds, assumptions and metadata. GPU vertices
are **already placed** and normalized before float32 conversion. Source transforms
are metadata, not transforms to apply again. Reusable scene schema v1 is in the
optional package; the lightweight viewer shares its packing, not its public DOM.

The browser API is `CadViewer`: asynchronous `load`, `updateScene`, `select`,
`setVisibility`, `preset`, `fit`, `getState`, `dispose`. `updateScene` preserves
selection/hidden state by surviving IDs and retains the filter; new IDs are
visible and removed IDs are dropped. It resets the camera because normalization
may change. `load` defaults to resetting view state. View readiness is not CAD
validation.

## Validation

Use the existing `validate.py`. It chooses real browser checks from the current
manifest, checks standalone/JSON scene agreement and runtime digests, and
continues checking every STL/GLB/placement with the same geometry checks.
Do not claim embedded-browser success from a lightweight-viewer test or DOM
presence alone. Missing browser execution is still explicitly not run.

The component isolates upstream globals/listeners in sandboxed frames.
For strict host CSP, serve the optional package's external engine and use
`frameUrl`; do not weaken the host policy. Offline delivery is the single HTML
file, not ES module imports through `file://`.

Rust/WASM remains deferred. No backend adds STEP, accurate B-rep measurements,
material verification or fabrication approval.
