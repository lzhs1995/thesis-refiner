"""Schemas describe syntax; workflow gates separately check live evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

import test_workflow


@unittest.skipUnless(importlib.util.find_spec("jsonschema"), "optional jsonschema dependency")
class SchemaTests(unittest.TestCase):
    def test_checkpoint_fixture_and_invalid_types(self):
        import jsonschema
        root = Path(__file__).resolve().parents[1]
        for path in (root / "schemas").glob("*.schema.json"):
            jsonschema.Draft202012Validator.check_schema(json.loads(path.read_text()))
        fixture = test_workflow.WorkflowTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        schema = json.loads((root / "schemas/checkpoint.schema.json").read_text())
        jsonschema.validate(fixture.state, schema)
        bad = copy.deepcopy(fixture.state)
        bad["documents"]["main"]["page_count"] = True
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)


if __name__ == "__main__":
    unittest.main()
