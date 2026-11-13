import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("toolkit_installer", ROOT / "install.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def test_all_hosts_install_complete_identical_skill_and_resolve_profile_links(self):
        manifest, content = installer.verified_package(ROOT)
        for host, config in manifest["hosts"].items():
            with self.subTest(host=host), tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / "workspace with spaces"
                destination.mkdir()
                unrelated = destination / "customer.txt"
                unrelated.write_bytes(b"untouched")
                result = installer.install(ROOT, destination, host)
                self.assertEqual(result["status"], "installed")
                self.assertEqual(unrelated.read_bytes(), b"untouched")
                skill = destination / config["skill"]
                for name, data in content.items():
                    if name.startswith("cad-design/"):
                        self.assertEqual((skill / name[len("cad-design/"):]).read_bytes(), data)
                for name in (config["profile"], config["guide"]):
                    source = destination / name
                    text = source.read_text(encoding="utf-8")
                    self.assertNotIn("{{", text)
                    for link in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
                        if "://" not in link:
                            self.assertTrue((source.parent / link).is_file(), link)
                receipt = json.loads((destination / ".mechanical-design-toolkit" / f"{host}.json").read_bytes())
                for name, expected in receipt["files"].items():
                    self.assertEqual(hashlib.sha256((destination / name).read_bytes()).hexdigest(), expected)
                self.assertEqual((skill / "LICENSE").read_bytes(), content["LICENSE"])
                self.assertFalse((destination / "opencode.json").exists())
                self.assertFalse((destination / ".venv").exists())

    def test_dry_run_does_not_create_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "new workspace"
            result = installer.install(ROOT, destination, "opencode", dry_run=True)
            self.assertEqual(result["status"], "dry_run")
            self.assertFalse(destination.exists())

    def test_conflicts_refused_before_any_file_is_written(self):
        manifest, _ = installer.verified_package(ROOT)
        for host, config in manifest["hosts"].items():
            for conflict in (config["skill"], config["profile"], config["guide"],
                             f".mechanical-design-toolkit/{host}.json"):
                with self.subTest(host=host, conflict=conflict), tempfile.TemporaryDirectory() as directory:
                    destination = Path(directory)
                    target = destination / conflict
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(b"existing customization")
                    before = {p.relative_to(destination): p.read_bytes()
                              for p in destination.rglob("*") if p.is_file()}
                    with self.assertRaises(FileExistsError):
                        installer.install(ROOT, destination, host)
                    self.assertEqual(before, {p.relative_to(destination): p.read_bytes()
                                             for p in destination.rglob("*") if p.is_file()})
            with self.subTest(host=host, conflict="empty skill"), tempfile.TemporaryDirectory() as directory:
                destination = Path(directory)
                (destination / config["skill"]).mkdir(parents=True)
                with self.assertRaises(FileExistsError):
                    installer.install(ROOT, destination, host, dry_run=True)

    def test_reinstallation_refused_even_when_bytes_match(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            installer.install(ROOT, destination, "copilot")
            with self.assertRaises(FileExistsError):
                installer.install(ROOT, destination, "copilot")

    def test_tampered_or_incomplete_inventory_refused_before_writing(self):
        for mode in ("modified", "missing", "missing_guide", "extra", "traversal"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                package = root / "package"
                shutil.copytree(ROOT, package, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                if mode == "modified":
                    (package / "cad-design" / "SKILL.md").write_bytes(b"tampered")
                elif mode == "missing":
                    (package / "adapters" / "manual" / "CAD_DESIGN_START.md").unlink()
                elif mode == "missing_guide":
                    (package / "adapters" / "openai" / "HOST.md").unlink()
                elif mode == "extra":
                    (package / "unexpected.py").write_bytes(b"print('unlisted')")
                else:
                    inventory = json.loads((package / "file-hashes.json").read_bytes())
                    inventory["../escape"] = "0" * 64
                    (package / "file-hashes.json").write_text(json.dumps(inventory), encoding="utf-8")
                with self.assertRaises((ValueError, OSError)):
                    installer.install(package, root / "target", "manual")
                self.assertFalse((root / "target").exists())

    def test_existing_file_parent_and_linked_parent_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".github").write_bytes(b"keep")
            with self.assertRaises(ValueError):
                installer.install(ROOT, root, "copilot")
            self.assertEqual((root / ".github").read_bytes(), b"keep")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / "real"
            real.mkdir()
            link = root / "link"
            if os.name == "nt":
                import subprocess
                result = subprocess.run(
                    [os.environ["ComSpec"], "/c", "mklink", "/J", str(link), str(real)],
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            else:
                link.symlink_to(real, target_is_directory=True)
            try:
                with self.assertRaisesRegex(ValueError, "Links and reparse"):
                    installer.install(ROOT, link / "nested", "copilot", dry_run=True)
                self.assertEqual(list(real.iterdir()), [])
            finally:
                if os.name == "nt":
                    link.rmdir()
                else:
                    link.unlink()

    def test_partial_write_failure_is_explicit_and_never_reported_installed(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path.open

            def failing_open(path, mode="r", *args, **kwargs):
                if mode == "xb" and path.name == "SKILL.md":
                    raise PermissionError("test denial")
                return original(path, mode, *args, **kwargs)

            with patch.object(Path, "open", failing_open):
                with self.assertRaisesRegex(OSError, "partial installation may remain"):
                    installer.install(ROOT, Path(directory) / "workspace", "manual")

    def test_host_metadata_has_no_permission_or_model_overrides(self):
        _, content = installer.verified_package(ROOT)
        for name in ("adapters/copilot/cad-designer.agent.md", "adapters/opencode/cad-designer.md"):
            frontmatter = content[name].decode("utf-8").split("---", 2)[1]
            self.assertNotRegex(frontmatter, r"(?m)^(model|permissions|tools|mcp-servers):")
        for value in ("../escape", "/absolute", "C:/drive", "folder\\file", "folder//file", "./file"):
            with self.assertRaises(ValueError):
                installer.relative_path(value)

    def test_execution_requests_render_guides_and_never_claim_detected_capabilities(self):
        manifest, _ = installer.verified_package(ROOT)
        for host in ("copilot", "opencode", "openai"):
            for requested in ("discover", "local", "remote", "manual"):
                with self.subTest(host=host, requested=requested), tempfile.TemporaryDirectory() as directory:
                    destination = Path(directory)
                    result = installer.install(ROOT, destination, host, execution_mode=requested)
                    receipt = json.loads((destination / ".mechanical-design-toolkit" / f"{host}.json").read_bytes())
                    self.assertEqual(result["requested_execution"], requested)
                    self.assertFalse(result["execution_capabilities_verified"])
                    self.assertEqual(receipt["requested_execution"], requested)
                    self.assertFalse(receipt["execution_capabilities_verified"])
                    guide = (destination / manifest["hosts"][host]["guide"]).read_text()
                    self.assertIn(f"Requested execution: `{requested}`", guide)
                    self.assertFalse((destination / "opencode.json").exists())
        with tempfile.TemporaryDirectory() as directory:
            installer.install(ROOT, Path(directory), "manual")
            receipt = json.loads((Path(directory) / ".mechanical-design-toolkit" / "manual.json").read_bytes())
            self.assertEqual(receipt["requested_execution"], "manual")

    def test_invalid_manual_execution_requests_fail_without_writes(self):
        for requested in ("discover", "local", "remote", "unrecognized"):
            with self.subTest(requested=requested), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "new"
                with self.assertRaisesRegex(ValueError, "does not support execution request"):
                    installer.install(ROOT, target, "manual", execution_mode=requested)
                self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
