# Mechanical idiom test pieces

One actual geometry specimen or mating set for each of the 14 families in
`cad-design/references/mechanical-idioms.md`. This is a geometric regression and
fit-trial catalog, **not** a library of qualified functional mechanisms.

| Family | Actual test piece | Main independent checks / boundary |
|---|---|---|
| 01 Threads | 16 mm AF, 6 mm thick nut; nominal 10 mm major, 1.5 mm pitch, 0.25 mm radial clearance | Through-bore, pitch, right-hand progression, retained wall, STL reload. Simplified internal thread, not a qualified male screw or thread class. |
| 02 Holes | Clearance hole, stepped counterbore, 90-degree countersink and capsule slot | Four through features, recessed versus retained sections, slot ends and bridge. No selected fastener standard. |
| 03 Fits | 6 mm plug and 6.2 / 6.4 / 6.6 mm through-hole ladder | Actual sampled 0.10 / 0.20 / 0.30 mm radial gaps. Not a press-fit specification. |
| 04 Sockets | Blind socket, finite-overlap boss/rib and 6 mm shaft pin | Retained bottom, rib connectivity and cavity/shaft sections. Nominal 1 mm bottom clearance. |
| 05 Bushings | Housing shoulder, sleeve and shouldered shaft | Seat, shaft gap and axial stack. Idealized envelopes, not invented purchased-bearing internals. |
| 06 Hinges | Two Z-axis leaves and exploded pin | Coaxial bores, radial/axial gaps, full pin span and five sampled poses. No continuous sweep or pin-retention claim. |
| 07 Snap fits | 1.6 mm cantilever hook envelope | Beam section and finite root/hook connectivity. No latch mate, insertion-force or strain qualification. |
| 08 Motion profiles | 2 mm eccentric circular cam | Pivot bore and eccentric bounds. Not decorative teeth presented as a gear, or a qualified follower pair. |
| 09 Compliance | Parallel-leaf frame with two 1.6 mm beams | Beam sections, flexure window and fixture holes. No stiffness, travel or fatigue result. |
| 10 Enclosures | 2 mm shell and lipped lid | Floor/wall sections, 0.30 mm per-side lip envelope and closed pose. No seal or closure-force claim. |
| 11 Edge treatment | Faceted R4 planar corner beside a 3 mm bevel | Different section areas with fixed envelopes. Not a general B-rep fillet/draft solver. |
| 12 Sheet shapes | 2 mm bent bracket with R6 inner bend | Inner/outer bend probes, section volume and envelope. **Not a flat pattern or bend allowance.** |
| 13 Hardware | Captive hex pocket and ideal 8 mm AF gauge | Pocket section, seating, through-hole and shoulder. Gauge is not a functional nut or vendor-qualified hardware. |
| 14 Patterns | 18-hole vent card on 8 x 9 mm pitch | Exact positioned holes, retained ligaments and card envelope. No airflow or lattice-strength claim. |

## Regenerate and check

Use the source package's existing foundation dependencies. From this folder:

```powershell
python .\model.py
python -m unittest discover -s . -p test_model.py -q
python .\model.py --browser "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
```

The optional browser argument uses existing Playwright/Edge support; it does
not download a browser. Each sample uses the shared ASCII-STL/default reload,
GLB/metadata and offline-viewer checks. The catalog is generated from this
source, not handcrafted meshes. Imports resolve to the canonical runtime
relative to this folder; the full source package is needed to regenerate it.

Print **local part** STLs at 100% in mm, not `assembled` files, the gallery grid
or a scaled screenshot. Choose material, orientation, supports and process
compensation deliberately. The exploded layouts are for inspection, not a
ready-to-slice plate. Names identify files/components; numbers are not embossed
on the solids. Record material, orientation, settings and observations against
the specimen ID. None has been physically printed or accepted.

Existing historical examples and installed project runtimes are unchanged.
