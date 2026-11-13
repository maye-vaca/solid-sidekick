from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_revision import ROOT
import new_project
from cadkit.construction import check_steps, generate, validate_plan, verify
from cadkit.geometry import box, cylinder


def step(name, moving, start=(0, 0, 0), end=(0, 0, 0)):
    return dict(id=name, title=name, instruction="Synthetic test step", source="Synthetic fixture",
                moving=moving, from_mm=list(start), to_mm=list(end))


class ConstructionTests(unittest.TestCase):
    def test_long_spindle_requires_loose_bridge_before_mounting(self):
        solids = {"base": box(20, 20, 2),
                  "bridge": (box(10, 10, 2)-cylinder(1.5, 4).translate((5, 5, -1))).translate((0, 0, 20)),
                  "spindle": cylinder(1, 30).translate((5, 5, 10))}
        bad = {"steps": [step("base", ["base"]), step("mount", ["bridge"]),
                         step("insert", ["spindle"], (0, 0, -30))]}
        with self.assertRaisesRegex(ValueError, "blocked assembly access spindle/base"):
            check_steps(bad, solids)
        good = {"steps": [step("base", ["base"]),
                          step("loose", ["bridge"], (0, 0, 100), (0, 0, 100)),
                          step("insert", ["spindle"], (0, 0, 70), (0, 0, 100)),
                          step("mount", ["bridge", "spindle"], (0, 0, 100))]}
        self.assertEqual(len(check_steps(good, solids)), 4)

    def test_original_wider_bridges_fail_before_guide_publication(self):
        for station in (85, 92):
            solids = {"bridge_y": box(73.5, 25, 10).translate((1.3, station-12.5, 0)),
                      "bridge_x": box(25, 73.5, 10).translate((station-12.5, 1.3, 0))}
            plan = {"steps": [step("place", list(solids))]}
            if station == 85:
                with self.assertRaisesRegex(ValueError, "assembly pose interference"):
                    check_steps(plan, solids)
            else:
                self.assertEqual(check_steps(plan, solids)[0]["status"], "passed")

    def test_sequence_cannot_teleport_previously_placed_parts_or_omit_final_members(self):
        solids = {"one": box(1, 1, 1), "two": box(1, 1, 1).translate((3, 0, 0))}
        with self.assertRaisesRegex(ValueError, "preceding pose"):
            check_steps({"steps": [step("first", ["one"]),
                                   step("teleport", ["one"], (0, 0, 10))]}, solids)
        with self.assertRaisesRegex(ValueError, "every instance"):
            check_steps({"steps": [step("only", ["one"])]}, solids)

    @unittest.skipUnless(os.environ.get("CADKIT_BROWSER"), "Set CADKIT_BROWSER for publication checks")
    def test_bundle_revision_inventory_recording_and_tamper_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            project = new_project.create_project(Path(directory) / "project")
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            environment.pop("PYTHONPATH", None)
            command = subprocess.run(
                [sys.executable, "-m", "cadkit.incremental", "qualify",
                 "--browser", os.environ["CADKIT_BROWSER"]],
                cwd=project, env=environment, text=True, capture_output=True, timeout=120)
            self.assertEqual(command.returncode, 0, command.stderr)
            identity = json.loads((project / "output" / "revision-state.json").read_text())["identity"]
            manifest = json.loads((project / "output" / "manifest.json").read_text())
            members = [item["id"] for item in manifest["instances"]]
            plan = dict(schema_version=1, revision=identity, title="Synthetic prototype",
                        source="Synthetic lab, not user acceptance", context_instances=[],
                        items=[dict(id="components", description="Illustrative component",
                                    units=[[name] for name in members], source="Qualified instance inventory", notes="")],
                        steps=[step("base-spacers", [name for name in members if name != "top"]),
                               step("lower-top", ["top"], (0, 0, 20))],
                        limitations=["Static spacers: insertion not checked; no physical acceptance"])
            for mutation in ("stale", "duplicate", "missing", "dimension"):
                bad = deepcopy(plan)
                if mutation == "stale":
                    bad["revision"]["brief_sha256"] = "0"*64
                elif mutation == "duplicate":
                    bad["items"][0]["units"].append([members[0]])
                elif mutation == "missing":
                    bad["items"][0]["units"].pop()
                else:
                    bad["items"][0]["dimension_keys"] = ["absent"]
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    validate_plan(bad, identity, set(members))
            plan_path = project / "construction-plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            output = generate(project, plan_path, project / "construction",
                              browser=Path(os.environ["CADKIT_BROWSER"]))
            self.assertEqual(verify(project, plan_path, output)["revision"], identity)
            self.assertGreater((output / "assembly.webm").stat().st_size, 1000)
            self.assertNotIn(b"\r\r\n", (output / "parts.csv").read_bytes())
            self.assertIn(identity["brief_sha256"], (output / "guide.html").read_text())
            self.assertIn(",6,", (output / "parts.csv").read_text())
            with self.assertRaisesRegex(ValueError, "new construction destination"):
                generate(project, plan_path, output)
            original = (output / "guide.html").read_bytes()
            (output / "guide.html").write_bytes(original+b"changed")
            with self.assertRaisesRegex(ValueError, "deliverables changed"):
                verify(project, plan_path, output)
            (output / "guide.html").write_bytes(original)
            video = (output / "assembly.webm").read_bytes()
            (output / "assembly.webm").write_bytes(video+b"changed")
            with self.assertRaisesRegex(ValueError, "deliverables changed"):
                verify(project, plan_path, output)
            (output / "assembly.webm").write_bytes(video)
            plan["steps"][0]["instruction"] = "Changed assembly order"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "receipt is stale"):
                verify(project, plan_path, output)


if __name__ == "__main__":
    unittest.main()
