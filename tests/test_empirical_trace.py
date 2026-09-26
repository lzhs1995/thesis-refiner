import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from empirical_trace import audit_contract, compare_csv, TraceError


class EmpiricalTraceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.file("data.csv", "id,b,n,label\na,0.1,2,Group A\nb,0.2,2,Group B\n")
        self.expected = self.file("reference.csv", "id,b,n,label\nb,0.2,2,Group B\na,0.1,2,Group A\n")
        self.contract = {"schema_version": 1, "task_id": "synthetic", "script": self.file("analysis.R", "# synthetic source\n"),
            "inputs": [self.data], "outputs": [self.expected], "full_reproduction": False,
            "runtime": {k: "recorded-synthetic" for k in ("session_id", "job_id", "transport", "source_revision", "installed_version", "loaded_version")},
            "samples": [{"artifact": self.data, "keys": ["id"], "expected_n": 2, "same_members_as": self.expected}],
            "tables": [{"artifact": self.data, "row_key": "id", "required_columns": ["label", "n"], "expected_rows": ["a", "b"],
                        "expected_cells": {"a": {"n": 2, "label": "Group A"}, "b": {"n": 2, "label": "Group B"}}}],
            "comparisons": [{"actual": self.data, "expected": self.expected, "keys": ["id"], "numeric_columns": ["b"],
                "storage_precision": "binary64", "display_rounding": 3, "ci_method": "not_applicable",
                "draws_requested": None, "draws_saved": None, "absolute_tolerance": "1e-12", "relative_tolerance": "0"}]}

    def file(self, name, text):
        path = self.root / name
        path.write_text(text)
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_order_independence_is_not_full_reproduction(self):
        result = audit_contract(self.contract)
        self.assertTrue(result["pass"], result)
        self.assertFalse(result["full_reproduction"])
        self.assertFalse(result["execution_performed_by_checker"])

    def test_same_n_with_different_people_rejected(self):
        self.contract["samples"][0]["same_members_as"] = self.file("other.csv", "id,b\na,0.1\nc,0.2\n")
        self.assertIn("SAMPLE_MEMBERSHIP_MISMATCH", str(audit_contract(self.contract)))

    def test_denominator_labels_and_missing_rows_are_explicit(self):
        self.contract["tables"][0]["expected_cells"]["a"]["n"] = 3
        self.assertIn("DENOMINATOR_LABEL", str(audit_contract(self.contract)))

    def test_binary32_label_does_not_relax_numeric_tolerance(self):
        spec = self.contract["comparisons"][0]
        spec["storage_precision"] = "binary32"
        spec["actual"] = self.file("rounded.csv", "id,b\na,0.10000000149011612\nb,0.2\n")
        with self.assertRaisesRegex(TraceError, "NUMERICAL_MISMATCH"):
            compare_csv(spec)

    def test_model_health_partial_remains_partial(self):
        model = {"id": "m", "evidence": self.file("model.log", "not all draws converged"),
                 "normal_termination": True, "standard_errors_valid": False, "draws_requested": 1000,
                 "draws_saved": 850, "replicate_convergence": "unknown"}
        self.contract["models"] = [model]
        self.assertFalse(audit_contract(self.contract)["pass"])
        model.update(accepted_partial=True, limitation="SE and replicate convergence unresolved; descriptive claim only")
        result = audit_contract(self.contract)
        self.assertTrue(result["pass"], result)
        self.assertEqual(result["status"], "CLOSED_WITH_DOCUMENTED_PARTIALS")
        self.contract["full_reproduction"] = True
        self.assertFalse(audit_contract(self.contract)["pass"])

    def test_missing_or_changed_file_is_not_evidence(self):
        Path(self.data["path"]).write_text("changed")
        self.assertIn("FILE_MISSING_OR_CHANGED", str(audit_contract(self.contract)))


if __name__ == "__main__":
    unittest.main()
