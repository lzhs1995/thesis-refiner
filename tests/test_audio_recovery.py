"""Synthetic evidence only; exercise the installed-style CLI without network."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audio_recovery.py"
SPEC = importlib.util.spec_from_file_location("audio_recovery", SCRIPT)
RECOVERY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECOVERY)
OPERATOR = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "22222222-2222-4222-8222-222222222222"
PREDECESSOR = "33333333-3333-4333-8333-333333333333"


class Evidence:
    def __init__(self, root, **options):
        self.root, self.options = Path(root).resolve(), options
        self.output = self.root / "delivery" / "audio.m4a"
        self.output.parent.mkdir()
        self.task, self.notebook, self.artifact = "synthetic-audio-task", "synthetic-notebook", "synthetic-audio"
        self.params = {"format": "critique", "length": "default", "language": "zh-Hans", "prompt": "Explain the study.\nPreserve uncertainty."}
        selection = self.emit("selection", {"notebook_id": self.notebook,
                              "sources": [{"source_id": "source-a"}, {"source_id": "source-b"}],
                              "audio_source_count": options.get("source_count", 2)})
        plan = {"task_id": self.task, "notebook_id": self.notebook, "account_key": "synthetic-account",
                "audio_create_cap": options.get("create_cap", 1), "destination": str(self.output.parent),
                "focus_prompt": self.params["prompt"], **{key: self.params[key] for key in ("format", "length", "language")}}
        if options.get("plan_drift"):
            plan["language"] = "en"
        original = {"task_id": self.task, "notebook_id": self.notebook, "operation": "audio_create",
                    "selection": selection, "source_ids": ["source-a", "source-b"], **self.params}
        original_ref = self.emit("original", original)
        intent = self.emit("intent", {"request_id": "create-request", "request": original_ref,
                           "source_selection": selection, "create_limit": options.get("intent_cap", 1),
                           "automatic_retries": False})
        bound = {**original, "account_key": "synthetic-account", "transport_contract": "synthetic"}
        if options.get("bound_drift"):
            bound["source_ids"] = ["source-x", "source-b"]
        artifact = {"artifact_id": self.artifact, "notebook_id": self.notebook, "type": "audio",
                    "status": "unknown", **{key: self.params[key] for key in ("format", "length", "language")}}
        if options.get("no_artifact"):
            artifact.pop("artifact_id")
        receipt, release = self.terminal("create", bound, artifact, is_create=True)
        created = self.emit("created", {"artifact": artifact, "request": original_ref,
                            "receipt": receipt, "release": release, "generation_still_pending": True})
        succession = {"executor_surface_uuid": OPERATOR, "created": created, "artifact_id": self.artifact,
                      "allowed_operations": ["studio_status", "audio_download"], "audio_create_cap": 0,
                      "source_add_cap": 0, "query_cap": options.get("query_cap", 0),
                      "original_user_authorization": "Resume the same synthetic audio artifact.",
                      "original_files_and_failures_preserved": True}
        if options.get("succession_drift"):
            succession["artifact_id"] = "other-artifact"
        binding = {"surface_uuid": OPERATOR, "workspace_uuid": WORKSPACE,
                   "original_artifact_id": self.artifact, "notebook_id": self.notebook,
                   "account_key": "synthetic-account", "observation_only": True}
        download_request = {"task_id": self.task, "notebook_id": self.notebook, "operation": "audio_download",
                            "artifact_id": self.artifact, "output": str(self.output)}
        self.contract = {"schema_version": 1, "plan": self.emit("plan", plan), "intent": intent,
                         "created": created, "download_request": self.emit("download-original", download_request),
                         "succession": self.emit("succession", succession), "binding": self.emit("binding", binding),
                         "preserve": [self.emit("budget-snapshot", {"audio_attempts": 1, "remaining_quota": "unknown"})],
                         "operations": []}
        self.request = {"task_id": self.task, "notebook_id": self.notebook, "operation": "studio_status", "artifact_id": self.artifact}
        if options.get("completed"):
            status = {"notebook_id": self.notebook, "artifacts": [{"artifact_id": self.artifact,
                      "type": "audio", "status": "completed", "source_ids": original["source_ids"],
                      "custom_instructions": original["prompt"]}]}
            if options.get("status_drift"):
                status["artifacts"][0]["source_ids"] = ["source-x"]
            observation = self.terminal("status", self.request, status)
            self.contract["operations"] = [{"receipt": observation[0], "release": observation[1]}]
        if options.get("download"):
            self.request = download_request.copy()
        self.contract_ref = self.emit("contract", self.contract)
        self.request_ref = self.emit("request", self.request)

    def emit(self, name, value):
        path = self.root / (name + ".json")
        data = (json.dumps(value, sort_keys=True) + "\n").encode()
        path.write_bytes(data)
        return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest()}

    def terminal(self, name, request, result, is_create=False):
        opts = self.options
        request = {**request, "account_key": "synthetic-account"}
        if not is_create and opts.get("prior_account_drift"):
            request["account_key"] = "different-account"
        bound_ref = self.emit(name + "-bound", request)
        result_ref = self.emit(name + "-result", result)
        transport = {"remote_terminal": True, "in_flight_requests": [], "exit_code": 0,
                     "operation": request["operation"],
                     "result": result_ref, "http": [{"fully_received": True}], "automatic_create_retries": 0}
        if is_create and opts.get("incomplete_http"):
            transport["http"][0]["fully_received"] = False
        if is_create and opts.get("retry_bool"):
            transport["automatic_create_retries"] = False
        lease = {"id": name + "-lease", "task_id": self.task, "surface_uuid": PREDECESSOR,
                 "workspace_uuid": WORKSPACE, "resource": "synthetic-resource"}
        receipt = {"mode": "real", "request_id": name + "-request", "operation": request["operation"],
                   "status": "COMPLETE", "resource_lease": lease, "notebook_id": self.notebook,
                   "at": "2030-01-01T00:00:00+00:00" if is_create else "2030-01-01T00:00:01+00:00",
                   "account_key": "synthetic-account", "request": bound_ref, "remote_terminal": True,
                   "process_group_empty": True, "in_flight_requests": [], "exit_code": 0,
                   "raw_answer": result_ref, "transport": self.emit(name + "-transport", transport)}
        if is_create and opts.get("uncertain_create"):
            receipt["status"] = "UNCERTAIN"
        if is_create and opts.get("unknown_terminal"):
            receipt["in_flight_requests"] = "UNKNOWN"
        if is_create and opts.get("exit_bool"):
            receipt["exit_code"] = False
        if not is_create and opts.get("reordered"):
            receipt["at"] = "2029-01-01T00:00:00+00:00"
        receipt_ref = self.emit(name + "-receipt", receipt)
        proof = {"pending": False, "own_processes_empty": True, "in_flight_requests": [],
                 "terminal_receipt": receipt_ref, "external_locks_probed_and_released": True}
        if is_create and opts.get("unknown_release"):
            proof["pending"] = None
        release = {**lease, "status": "RELEASED", "invocations": opts.get("invocations", 1), "release_proof": proof}
        return receipt_ref, self.emit(name + "-release", release)

    def cli(self, operator=OPERATOR, workspace=WORKSPACE, digest=None):
        self.request_ref = self.emit("request", self.request)
        return subprocess.run([sys.executable, "-B", str(SCRIPT), "validate", "--contract", self.contract_ref["path"],
                               "--contract-sha256", digest or self.contract_ref["sha256"], "--request", self.request_ref["path"],
                               "--operator-uuid", operator, "--workspace-uuid", workspace], capture_output=True, text=True, timeout=10)


class AudioRecoveryTests(unittest.TestCase):
    def test_cli_observation_unknown_generation_is_allowed_without_completion_credit(self):
        with tempfile.TemporaryDirectory() as root:
            case = Evidence(root)
            before = {p.name: p.read_bytes() for p in Path(root).glob("*.json")}
            result = case.cli()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "OFFLINE_ELIGIBLE")
            for axis in ("network_executed", "quota_verified", "current_authority_verified",
                         "resource_admission_verified", "media_or_content_verified"):
                self.assertIs(report[axis], False)
            self.assertEqual(before, {p.name: p.read_bytes() for p in Path(root).glob("*.json")})

    def test_cli_download_requires_same_completed_artifact_and_absent_target(self):
        with tempfile.TemporaryDirectory() as root:
            case = Evidence(root, completed=True, download=True)
            result = case.cli()
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertFalse(case.output.exists())
            case.output.write_bytes(b"existing-artifact-needs-local-verification")
            again = case.cli()
            self.assertEqual(again.returncode, 2)
            self.assertEqual(json.loads(again.stdout)["reason"], "DOWNLOAD_ALREADY_EXISTS_VERIFY_LOCALLY")

    def test_cli_rejects_wrong_artifact_operator_workspace_and_create(self):
        for change, reason in (("artifact", "ORIGINAL_ARTIFACT_REQUIRED"), ("operator", "EXECUTOR_UUID_CHANGED"),
                               ("workspace", "WORKSPACE_UUID_CHANGED"), ("create", "OBSERVE_OR_DOWNLOAD_ONLY"),
                               ("source_add", "OBSERVE_OR_DOWNLOAD_ONLY"), ("query", "OBSERVE_OR_DOWNLOAD_ONLY"),
                               ("prompt", "RECOVERY_REQUEST_PARAMETER_CHANGE")):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as root:
                case = Evidence(root)
                if change == "artifact":
                    case.request["artifact_id"] = "wrong-artifact"
                elif change in {"create", "source_add", "query"}:
                    case.request["operation"] = "audio_create" if change == "create" else change
                elif change == "prompt":
                    case.request["prompt"] = "Changed prompt"
                result = case.cli(operator=PREDECESSOR if change == "operator" else OPERATOR,
                                  workspace=PREDECESSOR if change == "workspace" else WORKSPACE)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertEqual(json.loads(result.stdout)["reason"], reason)

    def test_cli_boolean_counts_and_zero_labels_are_rejected(self):
        for key, value in (("create_cap", True), ("intent_cap", True), ("source_count", True),
                           ("query_cap", False), ("invocations", True), ("retry_bool", True), ("exit_bool", True)):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as root:
                result = Evidence(root, **{key: value}).cli()
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertEqual(json.loads(result.stdout)["status"], "REJECTED")

    def test_cli_preserves_unknown_acceptance_terminal_and_release(self):
        for key in ("uncertain_create", "unknown_terminal", "unknown_release", "incomplete_http", "no_artifact"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as root:
                case = Evidence(root, **{key: True})
                result = case.cli()
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertFalse(case.output.exists())

    def test_cli_rejects_semantic_or_pinned_file_drift(self):
        for key in ("plan_drift", "bound_drift", "succession_drift", "status_drift", "hash_drift", "preserved_budget_drift", "reordered", "prior_account_drift"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as root:
                case = Evidence(root, completed=True, **{key: True})
                if key in {"hash_drift", "preserved_budget_drift"}:
                    name = "intent.json" if key == "hash_drift" else "budget-snapshot.json"
                    with (Path(root) / name).open("ab") as stream:
                        stream.write(b" ")
                result = case.cli()
                self.assertEqual(result.returncode, 2, result.stdout)

    def test_cli_download_pending_or_destination_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            case = Evidence(root, download=True)
            result = case.cli()
            self.assertEqual(json.loads(result.stdout)["reason"], "GENERATION_COMPLETION_NOT_PROVEN")
        with tempfile.TemporaryDirectory() as root:
            case = Evidence(root, completed=True, download=True)
            case.request["output"] = str(Path(root) / "other.m4a")
            result = case.cli()
            self.assertEqual(json.loads(result.stdout)["reason"], "ORIGINAL_OUTPUT_ONLY")

    def test_cli_contract_pin_and_existing_evidence_required(self):
        with tempfile.TemporaryDirectory() as root:
            case = Evidence(root)
            self.assertEqual(json.loads(case.cli(digest="0" * 64).stdout)["reason"], "PIN_HASH_MISMATCH")
            (Path(root) / "create-release.json").unlink()
            self.assertEqual(json.loads(case.cli().stdout)["reason"], "PIN_FILE_MISSING")

    def test_cli_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            case = Evidence(root)
            path = Path(case.contract_ref["path"])
            data = b'{"schema_version": 1, "schema_version": 1}'
            path.write_bytes(data)
            result = case.cli(digest=hashlib.sha256(data).hexdigest())
            self.assertEqual(json.loads(result.stdout)["reason"], "DUPLICATE_JSON_KEY")

    def test_cli_destination_symlink_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            case = Evidence(root, completed=True, download=True)
            case.output.symlink_to(Path(root) / "unexpected.m4a")
            result = case.cli()
            self.assertEqual(result.returncode, 2)
            self.assertIn(json.loads(result.stdout)["reason"],
                          {"ORIGINAL_DESTINATION_CHANGED", "CANONICAL_DESTINATION_REQUIRED"})


if __name__ == "__main__":
    unittest.main()
