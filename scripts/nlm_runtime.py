#!/usr/bin/env python3
"""Pinned existing-transport calls with shared account budgets and durable receipts."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

from workflow import checked_ref, ref, answer_payload
from nlm_contracts import normalized_result, unwrap


class AdmissionError(ValueError):
    pass


def broker_module(binding):
    path = checked_ref(binding["broker_module"])
    spec = importlib.util.spec_from_file_location("thesis_resource_broker", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request_key(request):
    fields = ("account_key", "notebook_id", "transport_contract", "task_id", "operation", "document_sha256", "round_id", "conversation_id", "source_id", "source_ids", "prompt", "file_sha256")
    if request.get("operation") == "source_add":
        fields = ("account_key", "notebook_id", "transport_contract", "operation", "file_sha256")
    values = {k: request.get(k) for k in fields}
    if values.get("source_ids"):
        values["source_ids"] = sorted(set(values["source_ids"]))
    if request.get("operation") in {"list", "source_fulltext"}:
        values["observation_id"] = request.get("observation_id")
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Budget:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get("NLM_ACCOUNT_STATE_ROOT", Path.home() / ".local/state/nlm-account-budget"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "budget.sqlite3", isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY, policy TEXT NOT NULL,
            paused INTEGER DEFAULT 0, resume_after REAL, probe_id TEXT);
          CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY, account TEXT NOT NULL,
            task_id TEXT NOT NULL, operation TEXT NOT NULL, started REAL NOT NULL,
            state TEXT NOT NULL, receipt TEXT, units REAL, phase TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS allocations(account TEXT NOT NULL,task_id TEXT NOT NULL,
            query_budget INTEGER NOT NULL, PRIMARY KEY(account,task_id));
        """)

    def configure(self, account, policy):
        if policy.get("regime") not in {"legacy_daily_count", "compute_weekly", "unknown"}:
            raise AdmissionError("QUOTA_REGIME_REQUIRED")
        observed = policy.get("observed_at")
        if type(observed) not in {int, float} or not math.isfinite(observed) or observed < 0 or not policy.get("source"):
            raise AdmissionError("QUOTA_SOURCE_AND_TIMESTAMP_REQUIRED")
        if not 0 <= policy.get("reserve_fraction", .2) < 1:
            raise AdmissionError("INVALID_RESERVE")
        if policy.get("regime") == "legacy_daily_count" and policy.get("limit") is not None:
            limit, used, ends = policy["limit"], policy.get("observed_used", 0), policy.get("window_ends_at")
            if (type(limit) is not int or limit < 1 or type(used) is not int or not 0 <= used <= limit
                    or type(ends) not in {int, float} or not math.isfinite(ends) or ends <= observed):
                raise AdmissionError("MEASURED_COUNT_WINDOW_REQUIRED")
        self.db.execute("INSERT INTO accounts(id,policy) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET policy=excluded.policy", (account, json.dumps(policy)))

    def pause(self, account, resume_after=None):
        if resume_after is not None and (type(resume_after) not in {int, float} or not math.isfinite(resume_after)):
            raise AdmissionError("FINITE_RESUME_TIMESTAMP_REQUIRED")
        self.db.execute("UPDATE accounts SET paused=1,resume_after=?,probe_id=NULL WHERE id=?", (resume_after, account))

    def allocate(self, account, task_id, query_budget):
        if not account or not task_id or type(query_budget) is not int or query_budget < 1:
            raise AdmissionError("EXPLICIT_POSITIVE_TASK_BUDGET_REQUIRED")
        self.db.execute("INSERT INTO allocations VALUES(?,?,?) ON CONFLICT(account,task_id) DO UPDATE SET query_budget=excluded.query_budget", (account, task_id, query_budget))

    def admit(self, account, request, now=None):
        now = time.time() if now is None else now
        request = {**request, "account_key": account}
        if not request.get("notebook_id"):
            raise AdmissionError("NOTEBOOK_REQUIRED_FOR_REQUEST_IDENTITY")
        key = request_key(request)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            prior = self.db.execute("SELECT * FROM requests WHERE id=?", (key,)).fetchone()
            if prior:
                self.db.execute("COMMIT")
                return {"duplicate": True, **dict(prior)}
            row = self.db.execute("SELECT * FROM accounts WHERE id=?", (account,)).fetchone()
            if not row:
                raise AdmissionError("ACCOUNT_POLICY_NOT_CONFIGURED")
            policy = json.loads(row["policy"])
            if request.get("recovery_probe") and request.get("operation") != "query":
                raise AdmissionError("RECOVERY_PROBE_MUST_BE_QUERY")
            if self.db.execute("SELECT id FROM requests WHERE account=? AND state IN ('STARTED','UNCERTAIN')", (account,)).fetchone():
                raise AdmissionError("ACCOUNT_REQUEST_IN_FLIGHT")
            if row["paused"]:
                if not request.get("recovery_probe") or row["probe_id"] or row["resume_after"] is None or now < row["resume_after"]:
                    raise AdmissionError("ACCOUNT_QUOTA_PAUSED")
            if not request.get("task_id") or request.get("phase") not in {"draft", "final", "recovery"}:
                raise AdmissionError("TASK_AND_BUDGET_PHASE_REQUIRED")
            query = request["operation"] == "query"
            task_count = self.db.execute("SELECT count(*) FROM requests WHERE account=? AND task_id=? AND operation='query'", (account, request["task_id"])).fetchone()[0]
            allocation = self.db.execute("SELECT query_budget FROM allocations WHERE account=? AND task_id=?", (account, request["task_id"])).fetchone()
            task_limit = allocation[0] if allocation else policy.get("task_query_budget")
            if query and type(task_limit) is not int:
                raise AdmissionError("TASK_PLANNING_BUDGET_REQUIRED")
            if query and task_count >= task_limit:
                raise AdmissionError("TASK_PLANNING_BUDGET_EXHAUSTED")
            # 旧次数制可算余额；计算量未知时不以次数伪装成服务端余量。
            units = 1 if query and policy["regime"] == "legacy_daily_count" else None
            if units is not None and policy.get("limit") is not None:
                if policy.get("window_ends_at") is None or now >= policy["window_ends_at"]:
                    raise AdmissionError("QUOTA_WINDOW_REQUIRES_FRESH_OBSERVATION")
                booked = self.db.execute("SELECT coalesce(sum(units),0) FROM requests WHERE account=? AND started>=?", (account, policy["observed_at"])).fetchone()[0]
                remaining = policy["limit"] - policy.get("observed_used", 0) - booked
                reserve = 0 if request["phase"] in {"final", "recovery"} else policy["limit"] * policy.get("reserve_fraction", .2)
                if remaining - units < reserve:
                    raise AdmissionError("FINAL_REVIEW_RESERVE_PROTECTED")
            self.db.execute("INSERT INTO requests(id,account,task_id,operation,started,state,units,phase) VALUES(?,?,?,?,?,'STARTED',?,?)", (key, account, request["task_id"], request["operation"], now, units, request["phase"]))
            if row["paused"]:
                self.db.execute("UPDATE accounts SET probe_id=? WHERE id=?", (key, account))
            self.db.execute("COMMIT")
            return {"id": key, "duplicate": False}
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def finish(self, key, state, receipt, *, quota_limited=False, resume_after=None):
        if state not in {"COMPLETE", "FAILED", "UNCERTAIN"}:
            raise AdmissionError("INVALID_REQUEST_TERMINAL_STATE")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT * FROM requests WHERE id=?", (key,)).fetchone()
            if not row or row["state"] != "STARTED":
                raise AdmissionError("REQUEST_ALREADY_FINAL_OR_UNKNOWN")
            self.db.execute("UPDATE requests SET state=?,receipt=? WHERE id=?", (state, json.dumps(receipt), key))
            if quota_limited:
                self.db.execute("UPDATE accounts SET paused=1,resume_after=?,probe_id=NULL WHERE id=?", (resume_after, row["account"]))
            else:
                self._complete_recovery_probe(row, state)
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def report(self, account):
        a = self.db.execute("SELECT * FROM accounts WHERE id=?", (account,)).fetchone()
        rows = [dict(r) for r in self.db.execute("SELECT * FROM requests WHERE account=? ORDER BY started", (account,))]
        return {"account": dict(a) if a else None, "requests": rows, "query_count": sum(r["operation"] == "query" for r in rows),
                "server_compute_consumption": "UNKNOWN", "counts_are_not_compute_units": True}

    def _complete_recovery_probe(self, row, state):
        # Metadata success cannot demonstrate that account chat quota recovered.
        # The exact admitted probe query must have a validated COMPLETE result.
        if state == "COMPLETE" and row["operation"] == "query":
            self.db.execute("UPDATE accounts SET paused=0,probe_id=NULL WHERE id=? AND probe_id=?",
                            (row["account"], row["id"]))

    def reconcile(self, key, terminal_evidence):
        evidence_path = checked_ref(terminal_evidence)
        proof = json.loads(evidence_path.read_text())
        if proof.get("mode") != "real" or proof.get("request_id") != key or any(proof.get(k) is not True for k in ("remote_terminal", "transport_lock_free", "process_group_empty")):
            raise AdmissionError("REMOTE_TERMINAL_RECONCILIATION_REQUIRED")
        if proof.get("terminal_state") not in {"COMPLETE", "FAILED"}:
            raise AdmissionError("TERMINAL_STATE_REQUIRED")
        if proof["terminal_state"] == "COMPLETE":
            result = json.loads(checked_ref(proof.get("result_receipt")).read_text())
            if result.get("request_id") != key or result.get("status") != "COMPLETE":
                raise AdmissionError("COMPLETE_RESULT_RECEIPT_REQUIRED")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT * FROM requests WHERE id=?", (key,)).fetchone()
            if not row or row["state"] not in {"UNCERTAIN", "STARTED"}:
                raise AdmissionError("REQUEST_NOT_UNCERTAIN")
            original = json.loads(row["receipt"]) if row["receipt"] else None
            record = proof["result_receipt"] if proof["terminal_state"] == "COMPLETE" else {"original_receipt": original, "reconciliation": terminal_evidence}
            history = self.root / "reconciliations"
            history.mkdir(exist_ok=True)
            (history / (key + "-" + str(time.time_ns()) + ".json")).write_text(json.dumps({"original_receipt": original, "reconciliation": terminal_evidence}))
            self.db.execute("UPDATE requests SET state=?,receipt=? WHERE id=?", (proof["terminal_state"], json.dumps(record), key))
            self._complete_recovery_probe(row, proof["terminal_state"])
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return record


def validate_response(request, raw):
    """Apply the same source/terminal contract to new, cached and recovered data."""
    payload = json.loads(Path(raw).read_text())
    if request["operation"] != "query":
        normalized_result(request["operation"], payload, source_id=request.get("source_id"),
                          notebook_id=request["notebook_id"])
        return None
    text, citations = answer_payload(raw)
    payload = unwrap(payload)
    conversation = payload.get("conversation_id")
    requested = set(request.get("source_ids") or [request.get("source_id")])
    if (not isinstance(text, str) or not text.strip() or not citations or not conversation
            or any(not isinstance(c, dict) or c.get("source_id") not in requested for c in citations)
            or not set(payload.get("sources_used") or []) <= requested):
        raise AdmissionError("EMPTY_CONTROL_FRAME_OR_INCOMPLETE_ANSWER")
    if request.get("conversation_id") and request["conversation_id"] != conversation:
        raise AdmissionError("RESPONSE_CONVERSATION_MISMATCH")
    if payload.get("notebook_id") not in {None, request["notebook_id"]}:
        raise AdmissionError("RESPONSE_NOTEBOOK_MISMATCH")
    return conversation


def run_bound(binding, request, budget=None):
    protected = {"target_id", "workspace_uuid", "surface_uuid", "account_key", "broker_module", "commands",
                 "transport_artifacts", "resource_root", "external_locks", "simulation", "lease_ttl",
                 "existing_target_only", "no_navigation", "no_login", "no_default_write", "no_browser_launch"}
    if protected.intersection(request):
        raise AdmissionError("REQUEST_CANNOT_OVERRIDE_BINDING: " + ",".join(sorted(protected.intersection(request))))
    for field in ("account_key", "notebook_id", "target_id", "workspace_uuid", "surface_uuid"):
        if not binding.get(field):
            raise AdmissionError("MISSING_BINDING: " + field)
    for flag in ("existing_target_only", "no_navigation", "no_login", "no_default_write", "no_browser_launch"):
        if binding.get(flag) is not True:
            raise AdmissionError("BOUND_TRANSPORT_POLICY_REQUIRED: " + flag)
    if request.get("notebook_id", binding["notebook_id"]) != binding["notebook_id"]:
        raise AdmissionError("NOTEBOOK_BINDING_MISMATCH")
    command_template = binding.get("commands", {}).get(request.get("operation"))
    if not isinstance(command_template, list) or not command_template:
        raise AdmissionError("OPERATION_NOT_ALLOWED_BY_BINDING")
    for artifact in binding.get("transport_artifacts", []):
        checked_ref(artifact)
    if not binding.get("transport_artifacts"):
        raise AdmissionError("TRANSPORT_HASH_REQUIRED")
    request = {**request, "account_key": binding["account_key"], "notebook_id": binding["notebook_id"],
               "transport_contract": hashlib.sha256(json.dumps({"artifacts": binding["transport_artifacts"],
                   "commands": binding["commands"], "target_id": binding["target_id"]}, sort_keys=True).encode()).hexdigest()}
    if request["operation"] in {"list", "source_fulltext"}:
        request.setdefault("observation_id", str(time.time_ns()))
    if request["operation"] == "query" and (not (request.get("source_id") or request.get("source_ids")) or not request.get("prompt", "").strip() or not request.get("round_id") or not request.get("document_sha256")):
        raise AdmissionError("SOURCE_VERSION_ROUND_AND_PROMPT_REQUIRED")
    if request["operation"] == "source_add":
        path = checked_ref({"path": request.get("file"), "sha256": request.get("file_sha256")})
        if path.read_bytes()[:5] != b"%PDF-":
            raise AdmissionError("PDF_UPLOAD_REQUIRED")
    if request["operation"] == "source_fulltext" and not request.get("source_id"):
        raise AdmissionError("FULLTEXT_SOURCE_REQUIRED")
    budget = budget or Budget()
    module = broker_module(binding)
    broker = module.Broker(binding.get("resource_root"))
    resource = "nlm-account:" + binding["account_key"]
    broker.configure(resource, binding.get("external_locks", []))
    ticket = broker.request(resource, request["task_id"], binding["workspace_uuid"], binding["surface_uuid"])
    lease = broker.grant(ticket["id"], ttl=binding.get("lease_ttl", 600))
    admitted = None
    proof = {"pending": None, "own_processes_empty": None, "in_flight_requests": "UNKNOWN"}
    release_safe = True
    try:
        admitted = budget.admit(binding["account_key"], request)
        if admitted["duplicate"]:
            if admitted["state"] != "COMPLETE":
                raise AdmissionError("EXISTING_REQUEST_REQUIRES_RECONCILIATION: " + admitted["id"])
            saved_ref = json.loads(admitted["receipt"])
            saved = json.loads(checked_ref(saved_ref).read_text())
            raw = checked_ref(saved.get("raw_answer"))
            if (saved.get("status") != "COMPLETE" or saved.get("request_id") != admitted["id"]
                    or saved.get("exit_code") != 0 or saved.get("answer_sha256") != ref(raw)["sha256"]):
                raise AdmissionError("CACHED_RECEIPT_INVALID")
            validate_response(request, raw)
            return {"cached": True, "receipt": saved_ref}
        key = admitted["id"]
        release_safe = False
        out = budget.root / "receipts" / key
        out.mkdir(parents=True, exist_ok=False)
        (out / "request.json").write_text(json.dumps(request, ensure_ascii=False, indent=2))
        (out / "lease.json").write_text(json.dumps(lease, indent=2))
        prompt = out / "prompt.txt"
        prompt.write_text(request.get("prompt", ""))
        fields = {**request, **binding, "request_id": key, "prompt_file": str(prompt), "output_dir": str(out),
                  "source_ids_csv": ",".join(request.get("source_ids") or [request.get("source_id", "")])}
        command = [str(arg).format_map(fields) for arg in command_template]
        started = time.time()
        result = broker.run(lease["id"], lease["token"], command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        raw = out / "raw.json"
        raw.write_text(result.get("stdout") or "")
        (out / "stderr.txt").write_text(result.get("stderr") or "")
        proof["own_processes_empty"] = result["process_group_empty"]
        valid = result["exit_code"] == 0
        reason = None
        conversation_id = None
        try:
            conversation_id = validate_response(request, raw)
        except (ValueError, AttributeError, TypeError) as exc:
            valid = False
            reason = "INVALID_RESPONSE: " + str(exc)
        text = ((result.get("stdout") or "") + (result.get("stderr") or "")).lower()
        quota = any(term in text for term in ("usage limit reached", "chat disabled until", "quota exceeded", '"status":429', '"status": 429'))
        receipt = {"mode": "simulation" if binding.get("simulation") else "real", "request_id": key,
                   "operation": request["operation"], "document_sha256": request.get("document_sha256"),
                   "account_key": binding["account_key"], "notebook_id": binding["notebook_id"], "request": ref(out / "request.json"),
                   "source_id": request.get("source_id"), "round_id": request.get("round_id"),
                   "source_ids": request.get("source_ids") or [request.get("source_id")],
                   "conversation_id": conversation_id, "resource_lease": lease,
                   "resource_root": str(broker.root), "remote_terminal": valid or quota,
                   "started_at": started, "ended_at": time.time(), "exit_code": result["exit_code"],
                   "answer_sha256": ref(raw)["sha256"], "raw_answer": ref(raw), "error": reason,
                   "process_group_empty": result["process_group_empty"], "quota_limited": quota,
                   "A5_credit": False, "target_id": binding["target_id"], "transport_artifacts": binding["transport_artifacts"]}
        status = "COMPLETE" if valid else "FAILED" if quota else "UNCERTAIN"
        receipt["status"] = status
        rp = out / "receipt.json"
        rp.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        budget.finish(key, status, ref(rp), quota_limited=quota, resume_after=None)
        release_safe = (valid or quota) and result["process_group_empty"]
        if release_safe:
            proof.update(pending=False, own_processes_empty=True, in_flight_requests=[], terminal_receipt=ref(rp))
        return {"cached": False, "receipt": ref(rp), "status": status}
    except BaseException as exc:
        if admitted and not admitted.get("duplicate"):
            row = budget.db.execute("SELECT state FROM requests WHERE id=?", (admitted["id"],)).fetchone()
            if row and row["state"] == "STARTED":
                out = budget.root / "receipts" / admitted["id"]
                out.mkdir(parents=True, exist_ok=True)
                rp = out / "interrupted.json"
                rp.write_text(json.dumps({"mode": "simulation" if binding.get("simulation") else "real",
                    "status": "UNCERTAIN", "request_id": admitted["id"], "resource_lease": lease,
                    "account_key": binding["account_key"], "notebook_id": binding["notebook_id"],
                    "reason": "INTERRUPTED_INSPECT_ORIGINAL_PROCESS_AND_RECEIPTS", "error": repr(exc)}, indent=2))
                budget.finish(admitted["id"], "UNCERTAIN", ref(rp))
        raise
    finally:
        # 网络结束立即归窗；本地裁决不占用账号租约。
        if release_safe:
            if admitted is None or admitted.get("duplicate"):
                proof.update(pending=False, own_processes_empty=True, in_flight_requests=[], no_request_submitted=True)
            broker.release(lease["id"], lease["token"], proof, reconcile=lease["expires"] <= time.time())


def reconcile_bound(binding, request_id, terminal_evidence, budget):
    """Resolve the retained request and exact resource lease; preserve the failure."""
    row = budget.db.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
    if not row or row["state"] not in {"STARTED", "UNCERTAIN"} or row["account"] != binding["account_key"]:
        raise AdmissionError("MATCHING_UNCERTAIN_REQUEST_REQUIRED")
    out = budget.root / "receipts" / request_id
    lease = json.loads((out / "lease.json").read_text())
    request = json.loads((out / "request.json").read_text())
    proof = json.loads(checked_ref(terminal_evidence).read_text())
    if (proof.get("mode") != "real" or proof.get("request_id") != request_id
            or proof.get("remote_terminal") is not True or proof.get("process_group_empty") is not True
            or proof.get("transport_lock_free") is not True or proof.get("terminal_state") not in {"COMPLETE", "FAILED"}):
        raise AdmissionError("REMOTE_TERMINAL_RECONCILIATION_REQUIRED")
    if proof["terminal_state"] == "COMPLETE":
        recovered = json.loads(checked_ref(proof.get("result_receipt")).read_text())
        if recovered.get("status") != "COMPLETE" or recovered.get("request_id") != request_id or recovered.get("exit_code") != 0:
            raise AdmissionError("COMPLETE_RESULT_RECEIPT_REQUIRED")
        if any(recovered.get(k) != request.get(k) for k in ("operation", "account_key", "notebook_id", "round_id", "document_sha256")):
            raise AdmissionError("RECOVERED_RESULT_BINDING_MISMATCH")
        raw = checked_ref(recovered.get("raw_answer"))
        if recovered.get("answer_sha256") != ref(raw)["sha256"]:
            raise AdmissionError("RECOVERED_ANSWER_HASH_MISMATCH")
        conversation = validate_response(request, raw)
        if request["operation"] == "query" and conversation != recovered.get("conversation_id"):
            raise AdmissionError("RECOVERED_QUERY_NOT_COMPLETE")
    module = broker_module(binding)
    broker = module.Broker(binding.get("resource_root"))
    current = broker.get(lease["id"])
    if current["resource"] != "nlm-account:" + binding["account_key"] or current["token"] != lease["token"]:
        raise AdmissionError("RECOVERY_LEASE_MISMATCH")
    terminal = out / ("terminal-" + str(time.time_ns()) + ".json")
    terminal.write_text(json.dumps({"request_id": request_id, "resource_lease": lease,
        "status": proof["terminal_state"], "remote_terminal": True, "process_group_empty": True,
        "evidence": terminal_evidence}, indent=2))
    release_proof = {"pending": False, "own_processes_empty": True, "in_flight_requests": [], "terminal_receipt": ref(terminal)}
    if current["status"] == "ACTIVE":
        released = broker.release(lease["id"], lease["token"], release_proof, reconcile=True)
        (out / "reconciled-release.json").write_text(json.dumps(released, indent=2))
    elif current["status"] != "RELEASED" or not (out / "reconciled-release.json").is_file():
        raise AdmissionError("RECOVERY_RELEASE_NOT_PROVEN")
    record = budget.reconcile(request_id, terminal_evidence)
    return {"status": proof["terminal_state"], "receipt": record,
            "release_receipt": ref(out / "reconciled-release.json")}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["configure", "pause", "report", "run", "allocate", "reconcile"])
    p.add_argument("--root")
    p.add_argument("--account")
    p.add_argument("--input")
    p.add_argument("--binding")
    p.add_argument("--resume-after", type=float)
    p.add_argument("--request-id")
    args = p.parse_args()
    budget = Budget(args.root)
    try:
        if args.command == "configure":
            budget.configure(args.account, json.loads(Path(args.input).read_text()))
            result = {"configured": args.account}
        elif args.command == "pause":
            budget.pause(args.account, args.resume_after)
            result = {"paused": args.account, "resume_after": args.resume_after}
        elif args.command == "report":
            result = budget.report(args.account)
        elif args.command == "allocate":
            value = json.loads(Path(args.input).read_text())
            budget.allocate(args.account, value["task_id"], value["query_budget"])
            result = {"allocated": value}
        elif args.command == "reconcile":
            result = reconcile_bound(json.loads(Path(args.binding).read_text()), args.request_id, ref(args.input), budget)
        else:
            result = run_bound(json.loads(Path(args.binding).read_text()), json.loads(Path(args.input).read_text()), budget)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") not in {"FAILED", "UNCERTAIN"} else 2
    except Exception as e:
        print(json.dumps({"status": "BLOCKED", "reason": str(e)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
