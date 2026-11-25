"""Build 14 bounded mechanical-idiom test pieces; no physical-performance claims."""

import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import sys

import manifold3d as m
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cad-design" / "scripts" / "foundation"))
from cadkit import Assembly, Instance, Part, Placement
from cadkit.geometry import box, cylinder, internal_thread_tool, plate_with_holes
from cadkit.validation import Context, check_browser, check_exports, preflight_browser, require
from cadkit.viewer import write_mesh_viewer


LIMIT = ("Geometry/fit-trial specimens only. Material, process compensation, physical fit, "
         "loads, fatigue, sealing and manufacturing suitability are unverified.")
COLORS = ("#70c7d7", "#e7b365", "#a9cd78")


def coupon(title, parts, note, **parameters):
    assembly = Assembly(title, "Millimetres; +Z up. Local part STLs are not an arranged print plate.",
                        [LIMIT, note], parameters)
    for index, (name, solid, translation) in enumerate(parts):
        assembly.add_part(Part(name, solid, name.replace("_", " "), "Unspecified prototype material",
                               COLORS[index % len(COLORS)], notes=note))
        assembly.add_instance(Instance(name, name, Placement(translation)))
    return assembly


def hexagon(across_flats, height):
    return cylinder(across_flats / math.sqrt(3), height, segments=6).rotate((0, 0, 30))


def profile(points, height):
    return m.CrossSection([points]).extrude(height)


def arc(center, radius, start, end):
    return [(center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle))
            for angle in np.linspace(math.radians(start), math.radians(end), 25)]


def build():
    cases = {}
    major, pitch, clearance, height = 10.0, 1.5, .25, 6.0
    root = major / 2 + clearance
    lead = m.Manifold.cylinder(.4, root + .4, root, circular_segments=96)
    top = m.Manifold.cylinder(.4, root, root + .4, circular_segments=96).translate((0, 0, 5.6))
    nut = hexagon(16, height) - internal_thread_tool(
        major, pitch, height, radial_clearance=clearance) - lead - top
    cases["01_threads"] = coupon(
        "01 Threads - internal-thread nut", [("nut", nut, (0, 0, 0))],
        "Simplified right-hand single-start internal thread, not a thread class or a qualified screw.",
        major_mm=major, pitch_mm=pitch, radial_clearance_mm=clearance, across_flats_mm=16, height_mm=height)

    holes = plate_with_holes(80, 22, 8, [(10, 11, 4.4), (30, 11, 4.4), (50, 11, 4.4)])
    holes -= cylinder(4.2, 4).translate((30, 11, 5))
    holes -= m.Manifold.cylinder(3.1, 2.2, 5.3, circular_segments=96).translate((50, 11, 5))
    slot = (cylinder(2.2, 10).translate((67, 11, -1)) +
            cylinder(2.2, 10).translate((73, 11, -1)) +
            box(6, 4.4, 10).translate((67, 8.8, -1)))
    cases["02_holes"] = coupon(
        "02 Holes - clearance, counterbore, countersink and slot", [("hole_card", holes - slot, (0, 0, 0))],
        "Compare actual stepped/conical sections. Nominal 90-degree countersink; no fastener standard selected.",
        through_diameter_mm=4.4, counterbore_diameter_mm=8.4, counterbore_depth_mm=3,
        countersink_top_diameter_mm=10.4, slot_center_spacing_mm=6)

    fit_block = plate_with_holes(36, 18, 8, [(7, 9, 6.2), (18, 9, 6.4), (29, 9, 6.6)])
    plug = cylinder(3, 12) + cylinder(4.5, 2)
    cases["03_fits"] = coupon(
        "03 Fits - radial-clearance ladder",
        [("fit_block", fit_block, (0, 0, 0)), ("plug", plug, (48, 9, 0))],
        "Left to right: 0.10, 0.20, 0.30 mm radial clearance around a 6 mm plug. Not a press-fit specification.",
        plug_diameter_mm=6, radial_clearances_mm=[.1, .2, .3], hole_centers_mm=[7, 18, 29])

    socket = (box(24, 24, 3) + cylinder(7, 10).translate((12, 12, 2.8)) +
              box(2, 12, 7).translate((11, 0, 2.8)))
    socket -= cylinder(4, 8).translate((12, 12, 5.8))
    pin = cylinder(3.8, 6) + cylinder(5, 2).translate((0, 0, 6))
    cases["04_sockets"] = coupon(
        "04 Sockets - blind boss, rib and pin",
        [("ribbed_socket", socket, (0, 0, 0)), ("pin", pin, (34, 12, 0))],
        "7 mm blind socket, 6 mm pin shaft: 1 mm nominal bottom clearance; 0.20 mm radial clearance.",
        socket_depth_mm=7, pin_insertion_mm=6, boss_floor_z_mm=5.8, radial_clearance_mm=.2)

    housing = box(22, 22, 10) - cylinder(3.4, 12).translate((11, 11, -1))
    housing -= cylinder(6.2, 9).translate((11, 11, 2))
    bushing = cylinder(6, 8) - cylinder(3.2, 10).translate((0, 0, -1))
    shaft = cylinder(3, 14) + cylinder(4.5, 2)
    cases["05_bushings"] = coupon(
        "05 Bushings - seat, sleeve and shouldered shaft",
        [("housing", housing, (0, 0, 0)), ("bushing", bushing, (32, 11, 0)), ("shaft", shaft, (46, 11, 0))],
        "Idealized sleeve, not purchased bearing internals. 0.20 mm radial seat and shaft clearances; 2 mm seat floor.",
        housing_height_mm=10, seat_floor_mm=2, bushing_height_mm=8, shaft_diameter_mm=6)

    knuckle = cylinder(5.5, 4)
    bore = cylinder(2.2, 6).translate((0, 0, -1))
    leaf_a = (knuckle + box(16, 10, 2).translate((-20, -5, 0))) - bore
    leaf_b = (knuckle + box(16, 10, 2).translate((4, -5, 0))) - bore
    hinge_pin = cylinder(2, 11) + cylinder(3.5, 1.5)
    cases["06_hinge"] = coupon(
        "06 Hinges - two leaves and pin",
        [("leaf_a", leaf_a, (0, 0, 0)), ("leaf_b", leaf_b, (0, 0, 4.6)),
         ("hinge_pin", hinge_pin, (34, 0, 0))],
        "Z-axis joint. Leaves shown on-axis; pin exploded. Sampled poses only, not a swept-motion or retention qualification.",
        pin_diameter_mm=4, bore_diameter_mm=4.4, knuckle_height_mm=4, axial_gap_mm=.6)

    beam_hook = profile([(5.8, 5.2), (36, 5.2), (33, 8.5), (31, 8.5),
                         (31, 6.8), (5.8, 6.8)], 3)
    snap = box(6, 12, 5) + beam_hook
    cases["07_snap_fit"] = coupon(
        "07 Snap fits - cantilever hook envelope", [("snap_envelope", snap, (0, 0, 0))],
        "Geometry-only 1.6 mm flexure with finite root overlap. No latch mate, insertion force, safe strain or cycle claim.",
        beam_thickness_mm=1.6, beam_height_mm=3)

    cam = cylinder(12, 4).translate((2, 0, 0)) - cylinder(2.2, 6).translate((0, 0, -1))
    cases["08_cam"] = coupon(
        "08 Motion profiles - eccentric cam", [("eccentric_cam", cam, (0, 0, 0))],
        "2 mm eccentric circular cam geometry. Not an involute gear, conjugate follower pair, lead screw or motion solver.",
        outer_radius_mm=12, eccentricity_mm=2, pivot_bore_diameter_mm=4.4)

    compliant = box(40, 20, 3) - box(30, 16.8, 5).translate((6, 1.6, -1))
    for y in (5, 15):
        compliant -= cylinder(1.2, 5).translate((3, y, -1))
    cases["09_compliance"] = coupon(
        "09 Compliance - parallel-leaf frame", [("flexure_frame", compliant, (0, 0, 0))],
        "Two 1.6 mm beams and a rigid-end envelope. Geometry only; stiffness, travel, creep and fatigue are unresolved.",
        beam_thickness_mm=1.6, thickness_z_mm=3, window_mm=[30, 16.8])

    body = box(36, 28, 12) - box(32, 24, 11).translate((2, 2, 2))
    lip = box(31.4, 23.4, 3) - box(27.4, 19.4, 5).translate((2, 2, -1))
    lid = box(36, 28, 2) + lip.translate((2.3, 2.3, 1.8))
    cases["10_enclosure"] = coupon(
        "10 Enclosures - open shell and lipped lid",
        [("shell", body, (0, 0, 0)), ("lid", lid, (0, 38, 0))],
        "2 mm walls/floor; 0.30 mm per-side lip clearance. Lid shown beside shell, lip up. No sealing/closure-force claim.",
        wall_mm=2, floor_mm=2, lip_clearance_per_side_mm=.3, effective_lip_depth_mm=2.8)

    rounded = profile([(0, 0), (24, 0), *arc((20, 14), 4, 0, 90), (0, 18)], 4)
    beveled = profile([(0, 0), (24, 0), (24, 15), (21, 18), (0, 18)], 4)
    cases["11_edge_profiles"] = coupon(
        "11 Edge treatment - rounded versus beveled profile",
        [("rounded_corner", rounded, (0, 0, 0)), ("beveled_corner", beveled, (34, 0, 0))],
        "Faceted R4 planar corner and 3 mm bevel, extruded 4 mm. Not a general B-rep fillet, blend or draft operation.",
        corner_radius_mm=4, bevel_legs_mm=3, thickness_mm=4)

    bend_outline = [(0, 26), *arc((8, 8), 8, 180, 270), (30, 0), (30, 2),
                    *arc((8, 8), 6, 270, 180), (2, 26)]
    bracket = profile(bend_outline, 20).rotate((90, 0, 0)).translate((0, 20, 0))
    cases["12_bent_sheet"] = coupon(
        "12 Sheet shapes - constant-thickness bent bracket", [("bent_bracket", bracket, (0, 0, 0))],
        "2 mm folded display geometry with R6 inner bend. NOT an unfolded blank, bend allowance, kerf or tooling specification.",
        thickness_mm=2, inner_bend_radius_mm=6, width_mm=20)

    pocket = hexagon(8.2, 4.4).translate((12, 11, 4.6))
    captive = box(24, 22, 8) - pocket - cylinder(2.3, 10).translate((12, 11, -1))
    gauge = hexagon(8, 3) - cylinder(2, 5).translate((0, 0, -1))
    cases["13_captive_nut"] = coupon(
        "13 Hardware - captive-hex-pocket gauge",
        [("pocket_block", captive, (0, 0, 0)), ("nut_envelope_gauge", gauge, (34, 11, 0))],
        "Ideal 8 mm AF gauge and 8.2 mm AF pocket. Gauge is NOT a functional nut or vendor-qualified hardware.",
        gauge_across_flats_mm=8, pocket_across_flats_mm=8.2, pocket_depth_mm=3.4, clearance_hole_mm=4.6)

    centers = [(x, y, 3) for y in (6, 15, 24) for x in (5, 13, 21, 29, 37, 45)]
    cases["14_pattern"] = coupon(
        "14 Patterns - vent and ligament card",
        [("vent_card", plate_with_holes(50, 30, 3, centers), (0, 0, 0))],
        "18 through-holes on 8 x 9 mm pitch; minimum nominal ligament 5 mm. No lattice strength/airflow claim.",
        count=18, hole_diameter_mm=3, pitch_mm=[8, 9], minimum_ligament_mm=5)
    return cases


def near(actual, expected, label, tolerance=.002):
    require(abs(actual - expected) <= tolerance, f"{label}: {actual}, expected {expected}")


def void(solid, probe, label):
    near((solid ^ probe).volume(), 0, label, 1e-6)


def material(solid, point, label):
    probe = box(.1, .1, .1).translate(tuple(value - .05 for value in point))
    near((solid ^ probe).volume(), probe.volume(), label, 1e-7)


def check_coupon(key, assembly):
    context = Context(assembly)
    solids = {name: part.solid for name, part in assembly.parts.items()}
    for name, solid in solids.items():
        require(len(solid.decompose()) == 1, f"{key}/{name}: disconnected physical part")
    interference = context.check_interferences()
    facts = []
    if key == "01_threads":
        nut = solids["nut"]
        crest = (10 - 1.08253 * 1.5) / 2 + .25
        void(nut, cylinder(crest - .02, 8).translate((0, 0, -1)), "Thread through-bore")
        require(nut.genus() == 1, "Nut must have one through-bore")
        # Isolate the thread: the hexagonal exterior is not invariant under 90-degree rotation.
        feature = nut ^ cylinder(6, 6)
        a, b = feature.slice(2), feature.slice(3.5)
        near((a - b).area() + (b - a).area(), 0, "One-pitch repetition", 1e-5)
        near((a.rotate(90) - feature.slice(2.375)).area(), 0, "Right-hand quarter-pitch", 1e-5)
        require((a - feature.slice(2.75)).area() > .1, "Thread must not be a cylindrical hole")
        material(nut, (6, 0, 3), "Retained thread wall")
        context.expect_bounds("nut", [[-8, -16 / math.sqrt(3), 0], [8, 16 / math.sqrt(3), 6]])
        facts = ["Through-bore", "Pitch 1.5 mm and right-hand progression", "Retained wall and 16 mm AF"]
    elif key == "02_holes":
        solid = solids["hole_card"]
        require(solid.genus() == 4, "Expected four distinct through features")
        for x in (10, 30, 50):
            void(solid, cylinder(2.19, 10).translate((x, 11, -1)), "Clearance through-hole")
        for point in ((33, 11, 4), (54, 11, 5.5), (70, 13.5, 4)):
            material(solid, point, "Step, cone and slot retained material")
        for x, z in ((33, 6), (54, 7.5), (65, 4), (70, 4), (75, 4)):
            void(solid, box(.1, .1, .1).translate((x, 11, z)), "Recess or slot void")
        facts = ["Four through features", "Stepped and conical seating sections", "Both slot ends and bridge"]
    elif key == "03_fits":
        block = solids["fit_block"]
        require(block.genus() == 3, "Clearance ladder needs three holes")
        for x, gap in ((7, .1), (18, .2), (29, .3)):
            shaft = cylinder(3, 8).translate((x, 9, 0))
            void(block, shaft, "Nominal plug passage")
            near(block.min_gap(shaft, 1), gap, "Actual sampled radial clearance")
        near(solids["plug"].slice(5).area(), math.pi * 9, "Plug diameter section", .03)
        facts = ["Actual 0.10/0.20/0.30 mm radial gaps", "6 mm plug section"]
    elif key == "04_sockets":
        solid = solids["ribbed_socket"]
        void(solid, cylinder(3.99, 6.98).translate((12, 12, 5.81)), "Blind socket void")
        material(solid, (12, 12, 5.5), "Blind socket bottom")
        material(solid, (12, 3, 5), "Finite rib/root material")
        floor_probe = cylinder(3.79, .001).translate((12, 12, 5.798))
        near((solid ^ floor_probe).volume(), floor_probe.volume(), "Socket floor position", 1e-6)
        near(solids["pin"].slice(3).area(), math.pi * 3.8 ** 2, "Pin shaft section", .04)
        near(solids["pin"].slice(5.999).area(), math.pi * 3.8 ** 2, "Shaft upper section", .04)
        near(solids["pin"].slice(6.001).area(), math.pi * 5 ** 2, "Pin shoulder section", .06)
        near(solid.bounding_box()[5] - 5.8 - 6, 1, "Nominal bottom clearance")
        void(solid, solids["pin"].translate((12, 12, 6.8)), "Seated pin/shoulder pose")
        facts = ["Connected rib and boss", "Blind bottom retained", "Socket and pin sections", "Seated shoulder pose"]
    elif key == "05_bushings":
        housing, bushing = solids["housing"], solids["bushing"]
        void(housing, cylinder(6.19, 7.98).translate((11, 11, 2.01)), "Sleeve seat")
        material(housing, (15.5, 11, 1), "Seat shoulder")
        void(bushing, cylinder(3.19, 10).translate((0, 0, -1)), "Bushing through-bore")
        near(bushing.min_gap(cylinder(3, 8), 1), .2, "Shaft running envelope gap")
        near(housing.min_gap(cylinder(6, 7.6).translate((11, 11, 2.2)), 1), .2,
             "Sleeve seat radial/axial probe gap")
        near(bushing.bounding_box()[5], 8, "Sleeve axial height")
        facts = ["Seat shoulder and sleeve bore", "0.20 mm shaft radial gap", "8 mm sleeve / 2 mm floor stack"]
    elif key == "06_hinge":
        for name in ("leaf_a", "leaf_b"):
            void(solids[name], cylinder(2.19, 6).translate((0, 0, -1)), "Coaxial hinge bore")
            near(solids[name].min_gap(cylinder(2, 4), 1), .2, "Pin radial gap")
        context.expect_gap("leaf_a", "leaf_b", .6)
        installed_pin = solids["hinge_pin"].translate((0, 0, -1.5))
        require(installed_pin.bounding_box()[5] > context.placed["leaf_b"].bounds[1, 2],
                "Hinge pin shaft must span both knuckles")
        void(context.solids["leaf_a"] + context.solids["leaf_b"], installed_pin, "Installed hinge pin")
        for angle in (0, 45, 90, 135, 180):
            void(solids["leaf_a"], solids["leaf_b"].rotate((0, 0, angle)).translate((0, 0, 4.6)),
                 "Sampled hinge pose")
        facts = ["Coaxial bores", "0.20 mm radial / 0.60 mm axial gaps", "Pin spans both knuckles",
                 "Five sampled poses; no sweep claim"]
    elif key == "07_snap_fit":
        solid = solids["snap_envelope"]
        near((solid ^ box(.1, 12, 5).translate((18, 0, 0))).volume(), .1 * 1.6 * 3,
             "Cantilever section thickness", 1e-6)
        material(solid, (32, 8, 1), "Retaining-hook envelope")
        facts = ["1.6 x 3 mm beam section", "Finite root and hook connectivity"]
    elif key == "08_cam":
        context.expect_bounds("eccentric_cam", [[-10, -12, 0], [14, 12, 4]])
        void(solids["eccentric_cam"], cylinder(2.19, 6).translate((0, 0, -1)), "Pivot bore")
        require(solids["eccentric_cam"].genus() == 1, "Cam requires one pivot bore")
        facts = ["Pivot bore", "Eccentric outer bounds: -10 to +14 mm from pivot"]
    elif key == "09_compliance":
        solid = solids["flexure_frame"]
        near((solid ^ box(.1, 20, 3).translate((20, 0, 0))).volume(), .1 * 2 * 1.6 * 3,
             "Two compliant beam sections", 1e-6)
        require(solid.genus() == 3, "Flexure window and two fixture holes required")
        facts = ["Two 1.6 x 3 mm beams", "Open flexure window and two fixture holes"]
    elif key == "10_enclosure":
        body, lid = solids["shell"], solids["lid"]
        near(body.slice(6).area(), 36 * 28 - 32 * 24, "2 mm shell wall section", 1e-5)
        near(body.slice(1).area(), 36 * 28, "Closed floor section", 1e-5)
        points = np.concatenate(lid.slice(3).to_polygons())
        require(np.allclose([points.min(axis=0), points.max(axis=0)], [[2.3, 2.3], [33.7, 25.7]]),
                "Lid lip clearance envelope changed")
        void(body, lid.rotate((180, 0, 0)).translate((0, 28, 14)), "Closed lid/shell pose")
        material(body, (18, 14, 1), "Retained shell floor")
        facts = ["2 mm wall/floor sections", "0.30 mm lip envelope clearance", "Noninterfering closed pose"]
    elif key == "11_edge_profiles":
        near(solids["rounded_corner"].slice(2).area(), 24 * 18 - 16 + 4 * math.pi,
             "R4 quarter-circle profile area", .02)
        near(solids["beveled_corner"].slice(2).area(), 24 * 18 - 3 * 3 / 2,
             "3 mm bevel profile area", 1e-5)
        facts = ["Distinct rounded and straight-bevel sections", "Preserved 24 x 18 mm outer envelopes"]
        for solid in solids.values():
            require(np.allclose(solid.bounding_box(), [0, 0, 0, 24, 18, 4]), "Edge profile bounds changed")
    elif key == "12_bent_sheet":
        solid = solids["bent_bracket"]
        context.expect_bounds("bent_bracket", [[0, 0, 0], [30, 20, 26]])
        near(solid.volume(), (22 * 2 + 18 * 2 + math.pi / 4 * (8 ** 2 - 6 ** 2)) * 20,
             "Constant-thickness bend volume", .4)
        material(solid, (8 - 7 / math.sqrt(2), 10, 8 - 7 / math.sqrt(2)), "Bend mid-thickness")
        for radius in (5.5, 8.5):
            point = 8 - radius / math.sqrt(2)
            void(solid, box(.1, .1, .1).translate((point, 10, point)), "Inner/outer bend clearance")
        facts = ["2 mm thickness and R6 inner/R8 outer bend", "Constant-thickness section volume", "No flat-pattern claim"]
    elif key == "13_captive_nut":
        block = solids["pocket_block"]
        void(block, solids["nut_envelope_gauge"].translate((12, 11, 4.6)), "Gauge seating envelope")
        void(block, cylinder(2.29, 10).translate((12, 11, -1)), "Fastener passage")
        material(block, (16, 11, 4), "Pull-through shoulder material")
        near(block.slice(6).area(), 24 * 22 - math.sqrt(3) / 2 * 8.2 ** 2,
             "Hexagonal pocket section", 1e-5)
        facts = ["Hex pocket section", "Gauge seating", "Through-hole and retained shoulder"]
    elif key == "14_pattern":
        solid = solids["vent_card"]
        require(solid.genus() == 18, "Expected exactly 18 through-holes")
        for y in (6, 15, 24):
            for x in (5, 13, 21, 29, 37, 45):
                void(solid, cylinder(1.49, 5).translate((x, y, -1)), "Pattern hole")
        for cutout in (box(50, 30, 3) - solid).decompose():
            bounds = np.array(cutout.bounding_box()).reshape(2, 3)
            require(np.allclose(bounds[1] - bounds[0], [3, 3, 3], atol=1e-5, rtol=0),
                    "Pattern hole diameter/depth changed; nominal ligament no longer established")
        for x in (9, 17, 25, 33, 41):
            material(solid, (x, 6, 1.5), "Retained horizontal ligament")
        context.expect_bounds("vent_card", [[0, 0, 0], [50, 30, 3]])
        facts = ["18 positioned through-holes", "3 mm actual hole diameter/depth envelopes",
                 "Retained ligaments", "Preserved card envelope"]
    else:
        raise ValueError(f"No independent checks for coupon: {key}")
    return {"status": "geometry_checks_passed", "checks": facts, "interference": interference,
            "physical_acceptance": "not_performed", "limits": LIMIT}


def export(output, browser=None):
    if browser:
        browser = preflight_browser(browser)
    output = Path(output).resolve()
    cases = build()
    reports, gallery, metadata, links = {}, [], {}, []
    for index, (key, assembly) in enumerate(cases.items()):
        report = check_coupon(key, assembly)
        folder = assembly.export(output / key)
        report["exports"] = check_exports(Context(assembly), folder)
        report["browser"] = (check_browser(folder, len(assembly.instances), browser) if browser
                             else {"status": "not_run"})
        (folder / "coupon-checks.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        reports[key] = report
        meshes = assembly.meshes()[1]
        low = np.min([mesh.bounds[0] for mesh in meshes.values()], axis=0)
        offset = np.array([index % 4 * 110 + 10, index // 4 * 110 + 10, 0]) - low
        for instance in assembly.instances:
            name = f"c{index + 1:02}_{instance.id}"
            mesh = meshes[instance.id]
            mesh.apply_translation(offset)
            gallery.append((name, mesh))
            part = assembly.parts[instance.part_id]
            metadata[name] = dict(color=part.color, material=part.material,
                                  notes=f"{assembly.name}. {part.notes}")
        downloads = " ".join(
            f'<a href="{key}/parts/{name}.stl">{html.escape(name)} STL</a>'
            for name in assembly.parts)
        links.append(f'<li><h2><a href="{key}/viewer.html">{html.escape(assembly.name)}</a></h2>'
                     f'<p>{html.escape(assembly.assumptions[1])}</p><p>{downloads} '
                     f'<a href="{key}/assembly.glb">GLB</a></p></li>')
    write_mesh_viewer(gallery, output / "gallery.html", title="Mechanical idiom test pieces - 14 geometry demonstrations",
                      units="mm", metadata=metadata, coordinate_system="mm; +Z up; exploded catalog grid",
                      assumptions=[LIMIT, "Gallery positions are for inspection, not assembly or print placement."])
    index = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Mechanical idiom test pieces</title>
<style>html{{color-scheme:dark}}body{{background:#101923;color:#edf3f7;font:16px/1.5 system-ui;
max-width:960px;margin:auto;padding:20px}}a{{color:#70d7e9;display:inline-block;padding:6px;overflow-wrap:anywhere}}
:focus-visible{{outline:3px solid #70d7e9;outline-offset:3px}}h2{{font-size:18px}}
li{{margin:20px 0}}p{{overflow-wrap:anywhere}}ol{{padding-left:24px}}</style></head>
<body><main><h1>Mechanical idiom test pieces</h1><p>{html.escape(LIMIT)}</p>
<p>Print local part STLs at 100% in mm, not the exploded gallery.
Select material, orientation and process settings before any physical trial.
The files are labeled; the solids do not have embossed labels.</p>
<p><a href="gallery.html">Inspect all 14 idioms together</a></p><ol>{"".join(links)}</ol></main></body></html>'''
    (output / "index.html").write_text(index, encoding="utf-8")
    report = {"scope": "One bounded example per mechanical-idiom family; not every listed mechanism.",
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "coupons": reports, "physical_acceptance": "not_performed", "limits": LIMIT}
    (output / "checks.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "output")
    parser.add_argument("--browser", type=Path, help="Optional installed Edge/Chrome for offline raster/control checks")
    args = parser.parse_args()
    report = export(args.output, args.browser)
    print(json.dumps({"coupons": len(report["coupons"]), "status": "geometry_and_exports_checked",
                      "index": str(args.output.resolve() / "index.html"), "physical_acceptance": "not_performed"}))


if __name__ == "__main__":
    main()
