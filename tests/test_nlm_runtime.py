import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from nlm_runtime import Budget, AdmissionError, request_key
from workflow import ref


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.b = Budget(self.tmp.name)
        self.addCleanup(self.b.db.close)
        self.policy = {"regime": "legacy_daily_count", "source": "synthetic", "observed_at": 100,
                       "limit": 10, "observed_used": 7, "window_ends_at": time.time() + 3600,
                       "reserve_fraction": .2, "task_query_budget": 18}
        self.b.configure("a", self.policy)
        self.request = {"notebook_id": "n", "task_id": "t", "phase": "draft", "operation": "query", "prompt": "first", "document_sha256": "a", "source_id": "s", "round_id": "1"}

    def terminal(self, key, state="COMPLETE"):
        self.b.finish(key, state, {"test": True})

    def test_shared_reserve_inflight_and_final_budget(self):
        first = self.b.admit("a", self.request)
        with self.assertRaisesRegex(AdmissionError, "IN_FLIGHT"):
            self.b.admit("a", {**self.request, "task_id": "second"})
        self.terminal(first["id"])
        with self.assertRaisesRegex(AdmissionError, "RESERVE"):
            self.b.admit("a", {**self.request, "prompt": "second"})
        accepted = self.b.admit("a", {**self.request, "prompt": "final", "phase": "final"})
        self.assertFalse(accepted["duplicate"])

    def test_uncertain_request_quarantines_account_until_remote_reconciliation(self):
        first = self.b.admit("a", self.request)
        self.terminal(first["id"], "UNCERTAIN")
        with self.assertRaisesRegex(AdmissionError, "IN_FLIGHT"):
            self.b.admit("a", {**self.request, "prompt": "different", "phase": "final"})
        p = Path(self.tmp.name) / "terminal.json"
        p.write_text(json.dumps({"mode": "real", "request_id": first["id"], "remote_terminal": False}))
        with self.assertRaisesRegex(AdmissionError, "RECONCILIATION"):
            self.b.reconcile(first["id"], ref(p))
        p.write_text(json.dumps({"mode": "real", "request_id": first["id"], "remote_terminal": True,
                                 "transport_lock_free": True, "process_group_empty": True, "terminal_state": "FAILED"}))
        self.b.reconcile(first["id"], ref(p))
        self.assertFalse(self.b.admit("a", {**self.request, "prompt": "different", "phase": "final"})["duplicate"])

    def test_identity_and_source_reuse_across_rounds(self):
        base = {**self.request, "account_key": "a", "operation": "source_add", "file_sha256": "pdf"}
        self.assertNotEqual(request_key(base), request_key({**base, "notebook_id": "other"}))
        self.assertNotEqual(request_key(base), request_key({**base, "account_key": "other"}))
        self.assertEqual(request_key(base), request_key({**base, "round_id": "2"}))

    def test_quota_pause_allows_one_probe_at_observed_time(self):
        self.b.pause("a", resume_after=200)
        with self.assertRaisesRegex(AdmissionError, "PAUSED"):
            self.b.admit("a", {**self.request, "recovery_probe": True}, now=199)
        first = self.b.admit("a", {**self.request, "recovery_probe": True}, now=200)
        with self.assertRaises(AdmissionError):
            self.b.admit("a", {**self.request, "prompt": "second", "recovery_probe": True}, now=201)
        self.b.finish(first["id"], "FAILED", {}, quota_limited=True)
        with self.assertRaisesRegex(AdmissionError, "PAUSED"):
            self.b.admit("a", {**self.request, "prompt": "retry", "recovery_probe": True}, now=999999)

    def test_compute_unknown_never_claims_remaining_count(self):
        self.b.configure("a", {**self.policy, "regime": "compute_weekly"})
        first = self.b.admit("a", self.request)
        self.assertIsNone(self.b.db.execute("SELECT units FROM requests WHERE id=?", (first["id"],)).fetchone()[0])
        self.assertEqual(self.b.report("a")["server_compute_consumption"], "UNKNOWN")

    def test_daily_reset_is_observed_not_midnight_guessed(self):
        self.b.configure("a", {**self.policy, "window_ends_at": 200})
        with self.assertRaisesRegex(AdmissionError, "FRESH_OBSERVATION"):
            self.b.admit("a", self.request, now=201)


if __name__ == "__main__":
    unittest.main()
