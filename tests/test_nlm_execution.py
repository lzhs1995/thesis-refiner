"""Actual MAC broker + original NLM state machine + a named, offline transport.

Only native caller discovery is mocked. Never contacts an account or app.
COLLABORATION_BROKER must name the implementation being adopted.
"""
import copy
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import nlm_execution as execution
import nlm_runtime as runtime
from workflow import ref

BROKER = Path(os.environ.get("COLLABORATION_BROKER", ROOT.parent / "multi-agent-collaboration/scripts/resource_broker.py"))


@unittest.skipUnless(BROKER.is_file(), "set COLLABORATION_BROKER for actual cross-repository tests")
class NlmExecution(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.actor = {k: str(uuid.uuid4()) for k in ("workspace_uuid", "surface_uuid", "pane_uuid", "session_id")}
        self.current_actor = dict(self.actor)
        self.document = self.root / "frozen.pdf"
        self.document.write_bytes(b"%PDF-1.7\nfrozen offline manuscript")
        self.counter = self.root / "transport-calls.txt"
        self.answer = self.root / "answer.json"
        self.answer.write_text(json.dumps({"answer": "Offline answer [1]", "conversation_id": "conversation",
            "citations": {"1": "source"}, "references": [{"source_id": "source", "citation_number": 1,
                                                             "cited_text": "Offline evidence"}]}))
        self.transport = self.root / "named_offline_nlm_transport.py"
        self.transport.write_text("from pathlib import Path\nimport sys\np=Path(sys.argv[1])\n"
            "p.write_text(str(int(p.read_text())+1) if p.exists() else '1')\n"
            "assert Path(sys.argv[3]).read_text() == 'Review the frozen paper'\n"
            "assert Path(sys.argv[4]).is_dir()\nprint(Path(sys.argv[2]).read_text())\n")
        source = BROKER.resolve().parents[1]
        controller = {"source": str(source), "files": [
            {"relative": str(p.relative_to(source)), **{k: v for k, v in execution.full_ref(p).items() if k != "path"}}
            for p in sorted((source / "scripts").glob("*.py"))]}
        python = str(Path(sys.executable).resolve())
        self.binding = {"simulation": True, "account_key": "offline-account", "notebook_id": "notebook",
            "target_id": "offline-only-target", "workspace_uuid": self.actor["workspace_uuid"],
            "surface_uuid": self.actor["surface_uuid"], "broker_module": execution.full_ref(BROKER),
            "transport_artifacts": [execution.full_ref(p) for p in (python, self.transport, self.answer)],
            "resource_root": str(self.root / "resources"), "external_locks": [],
            "commands": {"query": [python, "-B", str(self.transport), str(self.counter), str(self.answer),
                                    "{prompt_file}", "{output_dir}"]},
            "execution_contract": {"schema": "nlm-execution-adoption-v1", "new_tasks_only": True,
                "actor": self.actor, "controller": controller, "cwd": str(self.root),
                "environment": {}, "inputs": [execution.full_ref(self.document)]}}
        self.binding.update({k: True for k in ("existing_target_only", "no_navigation", "no_login",
                                                "no_default_write", "no_browser_launch")})
        self.request = {"task_id": "chapter-2", "phase": "final", "operation": "query", "source_ids": ["source"],
            "prompt": "Review the frozen paper", "round_id": "r1", "document_sha256": execution.full_ref(self.document)["sha256"]}
        self.budget = runtime.Budget(self.root / "budget")
        self.addCleanup(self.budget.db.close)
        self.budget.configure("offline-account", {"regime": "unknown", "source": "offline-fixture",
                                                "observed_at": time.time(), "task_query_budget": 4})
        self.module = runtime.broker_module(self.binding)
        self.helper = self.module.Broker._execution_module()
        caller = patch.object(self.helper, "native_identity", side_effect=lambda contract: self.current_actor)
        caller.start()
        self.addCleanup(caller.stop)

    def run_bound(self):
        return runtime.run_bound(self.binding, self.request, self.budget)

    def query_rows(self):
        return [dict(row) for row in self.budget.db.execute("SELECT * FROM requests")]

    def resource_rows(self, table="tickets"):
        path = self.root / "resources/queue.sqlite3"
        if not path.exists():
            return []
        db = sqlite3.connect(path)
        try:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute("SELECT * FROM " + table)]
        finally:
            db.close()

    def assert_no_submission(self):
        self.assertFalse(self.counter.exists())
        self.assertEqual(self.query_rows(), [])
        self.assertEqual(self.resource_rows(), [])

    def test_normal_original_receipt_and_complete_cache(self):
        result = self.run_bound()
        self.assertEqual(result["status"], "COMPLETE")
        receipt = json.loads(Path(result["receipt"]["path"]).read_text())
        self.assertEqual(receipt["enforcement_scope"], "PRELAUNCH_ONLY")
        self.assertEqual(receipt["execution"]["state"], "TERMINAL")
        self.assertEqual(receipt["execution"]["generation"], receipt["resource_lease"]["execution"]["generation"])
        self.assertEqual(self.counter.read_text(), "1")
        before = self.resource_rows()
        with patch.object(self.module.Broker, "request_enforced", side_effect=AssertionError("cache queued")):
            cached = self.run_bound()
        self.assertTrue(cached["cached"])
        self.assertEqual(cached["receipt"], result["receipt"])
        self.assertEqual(self.resource_rows(), before)
        self.assertEqual(len(self.query_rows()), 1)
        self.assertEqual(before[0]["status"], "RELEASED")
        self.assertEqual(json.loads(before[0]["release_proof"])["execution"], receipt["execution"])
        self.assertEqual(self.counter.read_text(), "1")

    def test_wrong_native_session_refuses_before_databases(self):
        self.current_actor["session_id"] = str(uuid.uuid4())
        fresh = self.root / "unconstructed-budget"
        with self.assertRaisesRegex(ValueError, "NATIVE_EXECUTION_ACTOR_MISMATCH"):
            runtime.run_bound(self.binding, self.request, budget_root=fresh)
        self.assertFalse((fresh / "budget.sqlite3").exists())
        self.assertFalse((self.root / "resources").exists())
        self.assert_no_submission()

    def test_same_role_different_native_surface_refuses(self):
        self.current_actor["surface_uuid"] = str(uuid.uuid4())
        with self.assertRaisesRegex(ValueError, "NATIVE_EXECUTION_ACTOR_MISMATCH"):
            self.run_bound()
        self.assert_no_submission()

    def test_request_cannot_override_execution_or_controller(self):
        for field in ("execution_contract", "execution", "native_actor", "native_session", "controller",
                      "controller_source", "actor", "generation", "request_revision", "attempt_id", "cwd"):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "OVERRIDE_EXECUTION"):
                runtime.run_bound(self.binding, {**self.request, field: "override"}, self.budget)
        self.assert_no_submission()

    def test_changed_input_refuses_before_queue(self):
        self.document.write_bytes(b"%PDF-changed")
        with self.assertRaisesRegex(ValueError, "PIN_CHANGED"):
            self.run_bound()
        self.assert_no_submission()

    def test_changed_input_after_admit_refuses_before_transport(self):
        admit = self.budget.admit
        def change_after_admit(*args, **kwargs):
            value = admit(*args, **kwargs)
            self.document.write_bytes(b"changed after native preflight")
            return value
        with patch.object(self.budget, "admit", side_effect=change_after_admit):
            with self.assertRaisesRegex(ValueError, "PIN_.*CHANGED"):
                self.run_bound()
        self.assertFalse(self.counter.exists())
        self.assertEqual(self.query_rows()[0]["state"], "UNCERTAIN")
        self.assertEqual(self.resource_rows()[0]["status"], "ACTIVE")

    def test_stale_generation_refuses_at_actual_broker_run(self):
        run = self.module.Broker.run_enforced
        def stale(broker, ticket, token, **kwargs):
            kwargs["generation"] += 1
            return run(broker, ticket, token, **kwargs)
        with patch.object(self.module.Broker, "run_enforced", stale):
            with self.assertRaisesRegex(ValueError, "GENERATION_MISMATCH"):
                self.run_bound()
        self.assertFalse(self.counter.exists())
        self.assertEqual(self.query_rows()[0]["state"], "UNCERTAIN")

    def test_missing_api_never_falls_back_to_legacy_run(self):
        with patch.object(self.module.Broker, "run_enforced", None), patch.object(
                self.module.Broker, "run", side_effect=AssertionError("legacy fallback")):
            with self.assertRaisesRegex(ValueError, "ENFORCED_BROKER_API_REQUIRED"):
                self.run_bound()
        self.assert_no_submission()

    def test_uncertain_original_is_preserved_and_never_replayed(self):
        self.answer.write_text('{"answer":"missing citations"}')
        self.binding["transport_artifacts"][-1] = execution.full_ref(self.answer)
        result = self.run_bound()
        self.assertEqual(result["status"], "UNCERTAIN")
        rows, tickets = self.query_rows(), self.resource_rows()
        with self.assertRaisesRegex(ValueError, "EXISTING_REQUEST_REQUIRES_RECONCILIATION"):
            self.run_bound()
        self.assertEqual(self.query_rows(), rows)
        self.assertEqual(self.resource_rows(), tickets)
        self.assertEqual(self.counter.read_text(), "1")

    def test_changed_contract_cannot_replace_original_preparation(self):
        self.run_bound()
        rows, tickets = self.query_rows(), self.resource_rows()
        self.binding["execution_contract"]["environment"] = {"NLM_CHANGED": "yes"}
        with self.assertRaisesRegex(ValueError, "ORIGINAL_PREPARATION_CHANGED"):
            self.run_bound()
        self.assertEqual(self.query_rows(), rows)
        self.assertEqual(self.resource_rows(), tickets)
        self.assertEqual(self.counter.read_text(), "1")

    def test_legacy_ticket_cannot_be_upgraded(self):
        broker = self.module.Broker(self.binding["resource_root"])
        self.addCleanup(broker.db.close)
        resource = "nlm-account:offline-account"
        broker.configure(resource)
        broker.request(resource, self.request["task_id"], self.actor["workspace_uuid"], self.actor["surface_uuid"])
        before = self.resource_rows()
        with self.assertRaisesRegex(ValueError, "LEGACY_TICKET_CANNOT_BE_UPGRADED"):
            self.run_bound()
        self.assertEqual(self.resource_rows(), before)
        self.assertEqual(self.query_rows(), [])
        self.assertFalse(self.counter.exists())

    def test_budget_refusal_releases_exact_unsubmitted_execution(self):
        self.budget.pause("offline-account")
        with self.assertRaisesRegex(ValueError, "ACCOUNT_QUOTA_PAUSED"):
            self.run_bound()
        self.assertFalse(self.counter.exists())
        ticket = self.resource_rows()[0]
        self.assertEqual(ticket["status"], "RELEASED")
        proof = json.loads(ticket["release_proof"])
        self.assertTrue(proof["no_request_submitted"])
        self.assertEqual(proof["execution"]["operation"], "query")
        self.assertEqual(self.query_rows(), [])
        old_generation = proof["execution"]["generation"]
        # Simulate a measured budget restoration only in this temporary DB.
        self.budget.db.execute("UPDATE accounts SET paused=0 WHERE id='offline-account'")
        result = self.run_bound()
        receipt = json.loads(Path(result["receipt"]["path"]).read_text())
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(receipt["resource_lease"]["id"], ticket["id"])
        self.assertGreater(receipt["execution"]["generation"], old_generation)
        self.assertEqual(receipt["execution"]["attempt_id"], proof["execution"]["attempt_id"])
        history = self.resource_rows("resource_execution_unsubmitted_history")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["generation"], old_generation)
        self.assertEqual(json.loads(history[0]["lease"]), ticket)
        self.assertEqual(json.loads(history[0]["release_proof"]), proof)
        for name in ("lease", "binding", "release_proof"):
            self.assertEqual(history[0][name + "_sha256"], execution.digest(json.loads(history[0][name])))
        self.assertTrue(self.run_bound()["cached"])
        self.assertEqual(self.counter.read_text(), "1")

    def test_controller_pin_and_complete_closure_fail_before_import(self):
        bad = copy.deepcopy(self.binding)
        bad["execution_contract"]["controller"]["files"].pop()
        with self.assertRaisesRegex(ValueError, "COMPLETE_CONTROLLER_REQUIRED"):
            runtime.run_bound(bad, self.request, self.budget)
        bad = copy.deepcopy(self.binding)
        bad["broker_module"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "BROKER_CONTROLLER_PIN_MISMATCH"):
            runtime.run_bound(bad, self.request, self.budget)
        self.assert_no_submission()

    def test_operation_mismatch_is_rejected_by_actual_broker(self):
        run = self.module.Broker.run_enforced
        def wrong_operation(broker, ticket, token, **kwargs):
            kwargs["operation"] = "source_add"
            return run(broker, ticket, token, **kwargs)
        with patch.object(self.module.Broker, "run_enforced", wrong_operation):
            with self.assertRaisesRegex(ValueError, "OPERATION_BINDING_CHANGED"):
                self.run_bound()
        self.assertFalse(self.counter.exists())

    def test_actual_argv_cannot_change_between_preparation_and_launch(self):
        run = execution.EnforcedBroker.run
        def changed_argv(broker, ticket, token, command, **kwargs):
            return run(broker, ticket, token, [*command, "unbound"], **kwargs)
        with patch.object(execution.EnforcedBroker, "run", changed_argv):
            with self.assertRaisesRegex(ValueError, "ACTUAL_ARGV_DIFFERS"):
                self.run_bound()
        self.assertFalse(self.counter.exists())

    def test_legacy_complete_cache_is_not_upgraded(self):
        result = self.run_bound()
        path = Path(result["receipt"]["path"])
        saved = json.loads(path.read_text())
        saved["resource_lease"].pop("execution")
        path.write_text(json.dumps(saved))
        self.budget.db.execute("UPDATE requests SET receipt=?", (json.dumps(ref(path)),))
        tickets = self.resource_rows()
        with self.assertRaisesRegex(ValueError, "ORIGINAL_EXECUTION_BINDING_REQUIRED"):
            self.run_bound()
        self.assertEqual(self.resource_rows(), tickets)
        self.assertEqual(self.counter.read_text(), "1")

    def test_reconcile_preserves_original_execution_and_never_resubmits(self):
        good_answer = self.answer.read_text()
        self.answer.write_text('{"answer":"missing citations"}')
        self.binding["transport_artifacts"][-1] = execution.full_ref(self.answer)
        result = self.run_bound()
        original = json.loads(Path(result["receipt"]["path"]).read_text())
        key = original["request_id"]
        raw = self.root / "original-result-readback.json"
        raw.write_text(good_answer)
        recovered = dict(original, mode="real", status="COMPLETE", exit_code=0,
                         raw_answer=ref(raw), answer_sha256=ref(raw)["sha256"], conversation_id="conversation")
        receipt = self.root / "original-readback-receipt.json"
        receipt.write_text(json.dumps(recovered))
        terminal = self.root / "original-terminal-evidence.json"
        terminal.write_text(json.dumps({"mode": "real", "request_id": key, "remote_terminal": True,
            "process_group_empty": True, "transport_lock_free": True, "terminal_state": "COMPLETE",
            "result_receipt": ref(receipt)}))
        final = runtime.reconcile_bound(self.binding, key, ref(terminal), self.budget)
        self.assertEqual(final["status"], "COMPLETE")
        self.assertEqual(self.resource_rows()[0]["status"], "RELEASED")
        self.assertTrue(self.run_bound()["cached"])
        self.assertEqual(self.counter.read_text(), "1")

    def test_preparation_rejects_symlink_and_fifo_without_blocking(self):
        target = self.root / "target"
        target.write_bytes(b"same")
        link = self.root / "preparation-link"
        link.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "ORIGINAL_PREPARATION_CHANGED"):
            execution._freeze(link, b"same")
        fifo = self.root / "preparation-fifo"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, "ORIGINAL_PREPARATION_CHANGED"):
            execution._freeze(fifo, b"same")


if __name__ == "__main__":
    unittest.main()
