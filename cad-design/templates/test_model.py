"""Thin project checks; shared validation supplies the export/browser machinery."""

import json
from pathlib import Path
import tempfile
import unittest

from cadkit.validation import Context, check_exports
from checks import check
from model import DEFAULT_BRIEF, build


class ModelTests(unittest.TestCase):
    def test_requirements_and_static_interferences(self):
        context = Context(build())
        check(context)
        context.check_interferences()

    def test_export_roundtrip(self):
        assembly = build()
        with tempfile.TemporaryDirectory() as directory:
            output = assembly.export(directory)
            check_exports(Context(assembly), output)

    def test_rejects_bad_schema(self):
        brief = json.loads(DEFAULT_BRIEF.read_text(encoding="utf-8"))
        brief["schema_version"] = 999
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(brief), encoding="utf-8")
            with self.assertRaises(ValueError):
                build(path)


if __name__ == "__main__":
    unittest.main()
