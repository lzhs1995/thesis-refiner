"""Public JS -> runtime -> actual broker, with a local synthetic transport.

No browser, account or network calls. Set COLLABORATION_BROKER to test an
installed broker; a sibling collaboration checkout is used in the workspace.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from nlm_runtime import Budget, AdmissionError, run_bound, reconcile_bound, broker_module
from workflow import ref

BROKER = Path(os.environ.get("COLLABORATION_BROKER", ROOT.parent / "multi-agent-collaboration/scripts/resource_broker.py"))


@unittest.skipUnless(BROKER.is_file(), "set COLLABORATION_BROKER for cross-repository integration")
class BoundRuntime(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.reply = self.root / "reply.json"
        self.counter = self.root / "calls.txt"
        self.transport = self.root / "synthetic_transport.py"
        self.transport.write_text("from pathlib import Path\nimport sys\np=Path(sys.argv[2]);p.write_text(str(int(p.read_text())+1) if p.exists() else '1')\nprint(Path(sys.argv[1]).read_text())\n")
        self.b = Budget(self.root / "budget")
        self.addCleanup(self.b.db.close)
        self.b.configure("synthetic-account", {"regime": "unknown", "source": "offline-fixture", "observed_at": time.time(), "task_query_budget": 18})
        self.binding = {"simulation": True, "account_key": "synthetic-account", "notebook_id": "notebook", "target_id": "pinned-synthetic-target",
                        "workspace_uuid": str(uuid.uuid4()), "surface_uuid": str(uuid.uuid4()),
                        "broker_module": ref(BROKER), "transport_artifacts": [ref(self.transport)],
                        "resource_root": str(self.root / "resources"), "external_locks": []}
        self.binding.update({name: True for name in ("existing_target_only", "no_navigation", "no_login", "no_default_write", "no_browser_launch")})
        self.binding["commands"] = {op: [sys.executable, str(self.transport), str(self.reply), str(self.counter), "{target_id}"]
                                    for op in ("list", "source_fulltext", "source_add", "query")}
        self.binding_path = self.root / "binding.json"
        self.binding_path.write_text(json.dumps(self.binding))
        self.context = {"task_id": "synthetic-task", "phase": "final"}
        self.driver = self.root / "driver.js"
        self.driver.write_text("""const Client=require(process.argv[2]);
const c=new Client({bindingPath:process.argv[3],stateRoot:process.argv[4],context:JSON.parse(process.argv[5]),python:process.argv[6]});
(async()=>{const method=process.argv[7]; const args=JSON.parse(process.argv[8]);
try {console.log(JSON.stringify(await c[method](...args)));} catch(e){console.log(JSON.stringify({error:String(e)}));process.exitCode=2;}})();
""")

    def response(self, value):
        self.reply.write_text(json.dumps(value))

    def js(self, method, args=(), context=None):
        proc = subprocess.run(["node", str(self.driver), str(ROOT / "adapters/codex/nlm-unified-client.js"),
                               str(self.binding_path), str(self.b.root), json.dumps(context or self.context),
                               sys.executable, method, json.dumps(args)], capture_output=True, text=True)
        return proc, json.loads(proc.stdout)

    def query(self):
        return {**self.context, "operation": "query", "source_ids": ["source"], "prompt": "Review the synthetic paper",
                "round_id": "round-1", "document_sha256": "a" * 64}

    def answer(self):
        return {"answer": "Synthetic evidence [1]", "conversation_id": "conversation-1", "citations": {"1": "source"},
                "references": [{"source_id": "source", "citation_number": 1, "cited_text": "Synthetic evidence"}]}

    def proof(self, request_id, response):
        out = self.b.root / "receipts" / request_id
        request = json.loads((out / "request.json").read_text())
        raw = self.root / "recovered-answer.json"
        raw.write_text(json.dumps(response))
        record = {**request, "mode": "real", "status": "COMPLETE", "request_id": request_id, "exit_code": 0,
                  "raw_answer": ref(raw), "answer_sha256": ref(raw)["sha256"], "conversation_id": response.get("conversation_id")}
        rp = self.root / "recovered-receipt.json"
        rp.write_text(json.dumps(record))
        proof = self.root / "terminal.json"
        proof.write_text(json.dumps({"mode": "real", "request_id": request_id, "terminal_state": "COMPLETE",
                                     "remote_terminal": True, "transport_lock_free": True, "process_group_empty": True,
                                     "result_receipt": ref(rp)}))
        return ref(proof)

    def test_public_list_arrays_are_fresh_and_release_resource(self):
        for value in ([], [{"id": "n", "title": "newly observed"}]):
            self.response(value)
            proc, result = self.js("notebookList")
            self.assertEqual(proc.returncode, 0, result)
            self.assertEqual(result["data"], value)
            self.assertFalse(result["cached"])
            receipt = json.loads(Path(result["receipt"]["path"]).read_text())
            broker = broker_module(self.binding).Broker(self.binding["resource_root"])
            self.assertEqual(broker.get(receipt["resource_lease"]["id"])["status"], "RELEASED")
        self.assertEqual(self.counter.read_text(), "2")

    def test_public_wrong_fulltext_quarantines_and_recovery_cannot_bypass(self):
        self.response({"source_id": "wrong", "content": "wrong source"})
        proc, result = self.js("sourceGetFulltext", ["notebook", "source"])
        self.assertEqual(proc.returncode, 2, result)
        row = self.b.report("synthetic-account")["requests"][0]
        self.assertEqual(row["state"], "UNCERTAIN")
        with self.assertRaisesRegex(ValueError, "RESPONSE_SOURCE_MISMATCH"):
            reconcile_bound(self.binding, row["id"], self.proof(row["id"], {"source_id": "wrong", "content": "wrong source"}), self.b)
        with self.assertRaisesRegex(AdmissionError, "IN_FLIGHT"):
            self.b.admit("synthetic-account", {**self.query(), "notebook_id": "notebook"})
        result = reconcile_bound(self.binding, row["id"], self.proof(row["id"], {"source_id": "source", "content": "correct source"}), self.b)
        self.assertEqual(result["status"], "COMPLETE")

    def test_public_target_override_never_reaches_transport(self):
        self.response([])
        proc, result = self.js("notebookList", context={**self.context, "target_id": "wrong-target"})
        self.assertEqual(proc.returncode, 2, result)
        self.assertFalse(self.counter.exists())

    def test_public_upload_checks_terminal_and_cache_bytes(self):
        pdf = self.root / "synthetic.pdf"
        pdf.write_bytes(b"%PDF-1.7\nsynthetic fixture")
        self.response({"id": "source", "status": "READY"})
        proc, result = self.js("sourceAdd", ["notebook", str(pdf)])
        self.assertEqual(proc.returncode, 0, result)
        proc, cached = self.js("sourceAdd", ["notebook", str(pdf)])
        self.assertEqual(proc.returncode, 0, cached)
        self.assertTrue(cached["cached"])
        receipt = json.loads(Path(result["receipt"]["path"]).read_text())
        Path(receipt["raw_answer"]["path"]).write_text('{"id":"tampered","status":"READY"}')
        proc, result = self.js("sourceAdd", ["notebook", str(pdf)])
        self.assertEqual(proc.returncode, 2, result)
        self.assertEqual(self.counter.read_text(), "1")

    def test_public_upload_json_error_is_not_complete(self):
        pdf = self.root / "synthetic.pdf"
        pdf.write_bytes(b"%PDF-1.7\nfixture")
        self.response({"id": "source", "status": "ERROR"})
        proc, result = self.js("sourceAdd", ["notebook", str(pdf)])
        self.assertEqual(proc.returncode, 2, result)

    def test_public_query_preserves_native_conversation_and_quotes(self):
        self.response(self.answer())
        proc, result = self.js("notebookQuery", ["notebook", "Review", {"sourceIds": ["source"], "roundId": "r1", "documentSha256": "a" * 64}])
        self.assertEqual(proc.returncode, 0, result)
        self.assertEqual(result["data"]["references"][0]["cited_text"], "Synthetic evidence")
        self.assertEqual(json.loads(Path(result["receipt"]["path"]).read_text())["conversation_id"], "conversation-1")

    def test_only_successful_current_query_probe_restores_paused_account(self):
        self.b.pause("synthetic-account", time.time() - 1)
        with self.assertRaisesRegex(AdmissionError, "PROBE_MUST_BE_QUERY"):
            self.b.admit("synthetic-account", {**self.context, "notebook_id": "notebook", "operation": "list", "recovery_probe": True})
        self.assertEqual(self.b.report("synthetic-account")["account"]["paused"], 1)
        self.response({"status": 200})
        result = run_bound(self.binding, {**self.query(), "recovery_probe": True}, self.b)
        self.assertEqual(result["status"], "UNCERTAIN")
        key = self.b.report("synthetic-account")["requests"][0]["id"]
        self.assertEqual(self.b.report("synthetic-account")["account"]["probe_id"], key)
        recovered = reconcile_bound(self.binding, key, self.proof(key, self.answer()), self.b)
        self.assertEqual(recovered["status"], "COMPLETE")
        account = self.b.report("synthetic-account")["account"]
        self.assertEqual(account["paused"], 0)
        self.assertIsNone(account["probe_id"])


if __name__ == "__main__":
    unittest.main()
