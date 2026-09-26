#!/usr/bin/env python3
"""Persistent READY arbitration. Actual network/budget/locks stay in a pinned adapter.

This module does not send requests, grant broker leases, or infer remote completion.
One coordinator consumes reservations immediately and supplies original receipts.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
import uuid


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def checked(ref):
    path = Path(ref["path"])
    if not path.is_absolute() or not path.is_file():
        raise ValueError("ABSOLUTE_ARTIFACT_REQUIRED")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise ValueError("ARTIFACT_CHANGED: " + str(path))
    return raw


def checked_json(ref):
    return json.loads(checked(ref))


def logical_key(entry):
    """Transport/executor aliases cannot turn the same query into a new query."""
    logical = entry["logical_identity"]
    fields = ("account_key", "notebook_id", "operation", "document_sha256", "round_id", "prompt_sha256")
    if any(not isinstance(logical.get(k), str) or not logical[k] for k in fields):
        raise ValueError("INCOMPLETE_LOGICAL_IDENTITY")
    if not isinstance(logical.get("source_ids"), list) or not logical["source_ids"]:
        raise ValueError("SOURCES_REQUIRED")
    if any(not isinstance(s, str) or not s for s in logical["source_ids"]):
        raise ValueError("INVALID_SOURCE_ID")
    if logical.get("conversation_id"):
        raise ValueError("FRESH_CONVERSATION_REQUIRED")
    value = {k: logical[k] for k in fields}
    value["source_ids"] = sorted(set(logical["source_ids"]))
    return digest(value)


class ReadyQueue:
    """A local scheduling journal, separate from the account's authoritative budget."""

    def __init__(self, database, policy):
        if policy.get("capacity") not in (1, 2) or type(policy["capacity"]) is not int:
            raise ValueError("ONLY_VALIDATED_CAPACITY_ONE_OR_TWO")
        if not policy.get("account_key") or not policy.get("coordinator_id"):
            raise ValueError("ACCOUNT_AND_COORDINATOR_REQUIRED")
        if type(policy.get("admission_seconds")) is not int or not 1 <= policy["admission_seconds"] <= 600:
            raise ValueError("BOUNDED_ADMISSION_REQUIRED")
        if policy["capacity"] == 2:
            capability = checked_json(policy["parallel_capability"])
            if capability.get("status") != "LIVE_TWO_QUERY_CAPABILITY" or capability.get("account_key") != policy["account_key"]:
                raise ValueError("MATCHING_LIVE_CAPABILITY_REQUIRED")
            if capability.get("validated_capacity") != 2 or not capability.get("evidence"):
                raise ValueError("TWO_QUERY_LIVE_EVIDENCE_REQUIRED")
            for ref in capability["evidence"]:
                checked(ref)
        self.policy = json.loads(canonical(policy))
        for ref in self.policy.get("protected_artifacts", []):
            checked(ref)
        path = Path(database)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY CHECK(id=1), policy TEXT NOT NULL, turn INTEGER NOT NULL DEFAULT 0, paused INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS items (seq INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT UNIQUE NOT NULL, logical_key TEXT UNIQUE NOT NULL, task_id TEXT NOT NULL, notebook_id TEXT NOT NULL, position INTEGER NOT NULL, entry TEXT NOT NULL, state TEXT NOT NULL, outcome TEXT, group_id TEXT);
            CREATE TABLE IF NOT EXISTS groups (id TEXT PRIMARY KEY, state TEXT NOT NULL, manifest TEXT NOT NULL, proof TEXT);
            CREATE UNIQUE INDEX IF NOT EXISTS one_unreturned_group ON groups((1)) WHERE state IN ('RESERVED','STARTED','QUARANTINED');
            CREATE TABLE IF NOT EXISTS turns (task_id TEXT PRIMARY KEY, last_turn INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL);
        """)
        with self.transaction():
            self.db.execute("INSERT OR IGNORE INTO config(id,policy) VALUES(1,?)", (canonical(policy),))
            if self.db.execute("SELECT policy FROM config WHERE id=1").fetchone()[0] != canonical(policy):
                raise ValueError("POLICY_CHANGED_USE_EXPLICIT_SUCCESSOR_QUEUE")

    @contextlib.contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def event(self, kind, payload):
        self.db.execute("INSERT INTO events(at,kind,payload) VALUES(?,?,?)", (time.time(), kind, canonical(payload)))

    def validate_entry(self, entry):
        if not re.fullmatch(r"[0-9a-f]{64}", entry.get("request_id", "")):
            raise ValueError("ORIGINAL_REQUEST_ID_REQUIRED")
        if not entry.get("task_id") or type(entry.get("position")) is not int or entry["position"] < 0:
            raise ValueError("TASK_AND_ORDER_REQUIRED")
        key = logical_key(entry)
        if entry["logical_identity"]["account_key"] != self.policy["account_key"]:
            raise ValueError("ACCOUNT_MISMATCH")
        if not entry.get("fixed_inputs") or not entry.get("owner_reservation"):
            raise ValueError("FROZEN_INPUTS_AND_OWNER_REQUIRED")
        checked(entry["owner_reservation"])
        for ref in entry["fixed_inputs"]:
            checked(ref)
        for prior in entry.get("dependencies", []):
            if not re.fullmatch(r"[0-9a-f]{64}", prior) or prior == entry["request_id"]:
                raise ValueError("INVALID_DEPENDENCY")
        if entry.get("retry_of"):
            retry = entry["retry_of"]
            prior = checked_json(retry["receipt"])
            if (prior.get("request_id") != retry.get("request_id") or prior.get("status") != "FAILED"
                    or prior.get("network_terminal") is not True or prior.get("mode") != "real"
                    or not retry.get("scope") or prior["request_id"] == entry["request_id"]):
                raise ValueError("EXPLICIT_TERMINAL_FAILED_RETRY_REQUIRED")
        return key

    def enqueue(self, entry):
        key = self.validate_entry(entry)
        value = canonical(entry)
        with self.transaction():
            prior = self.db.execute("SELECT * FROM items WHERE request_id=? OR logical_key=?", (entry["request_id"], key)).fetchone()
            if prior:
                if prior["entry"] == value:
                    return {"status": "ALREADY_REGISTERED", "request_id": prior["request_id"]}
                raise ValueError("ORIGINAL_OR_LOGICAL_QUERY_ALREADY_REGISTERED")
            self.db.execute("INSERT INTO items(request_id,logical_key,task_id,notebook_id,position,entry,state) VALUES(?,?,?,?,?,?,'READY')", (entry["request_id"], key, entry["task_id"], entry["logical_identity"]["notebook_id"], entry["position"], value))
            self.event("READY", {"request_id": entry["request_id"]})
        return {"status": "READY", "request_id": entry["request_id"]}

    def claim(self, *, minimum=1, now=None):
        """Call only when the coordinator/adapter is ready to consume immediately."""
        now = time.time() if now is None else now
        if minimum not in (1, 2) or minimum > self.policy["capacity"]:
            raise ValueError("UNSUPPORTED_BATCH_SIZE")
        for ref in self.policy.get("protected_artifacts", []):
            checked(ref)
        if self.policy["capacity"] == 2:
            capability = checked_json(self.policy["parallel_capability"])
            for ref in capability["evidence"]:
                checked(ref)
        with self.transaction():
            if self.db.execute("SELECT 1 FROM groups WHERE state IN ('RESERVED','STARTED','QUARANTINED')").fetchone():
                raise ValueError("UNRETURNED_GROUP_REQUIRES_RECONCILIATION")
            if self.db.execute("SELECT paused FROM config WHERE id=1").fetchone()[0]:
                raise ValueError("ACCOUNT_PAUSED")
            rows = self.db.execute("SELECT i.*,COALESCE(t.last_turn,-1) AS last_turn FROM items i LEFT JOIN turns t USING(task_id) WHERE state='READY' ORDER BY position,seq").fetchall()
            heads = {}
            for row in rows:
                heads.setdefault(row["task_id"], row)
            eligible = []
            for row in heads.values():
                entry = json.loads(row["entry"])
                if any(not self.db.execute("SELECT 1 FROM items WHERE request_id=? AND state='RETURNED'", (dep,)).fetchone() for dep in entry.get("dependencies", [])):
                    continue
                self.validate_entry(entry)
                eligible.append(row)
            eligible.sort(key=lambda row: (row["last_turn"], row["seq"]))
            chosen = []
            for row in eligible:
                entry = json.loads(row["entry"])
                if chosen and (entry["logical_identity"]["operation"] != "query" or chosen[0]["logical_identity"]["operation"] != "query" or entry["logical_identity"]["notebook_id"] == chosen[0]["logical_identity"]["notebook_id"]):
                    continue
                chosen.append(entry)
                if len(chosen) == self.policy["capacity"] or entry["logical_identity"]["operation"] != "query":
                    break
            if len(chosen) < minimum:
                return None
            group = {"group_id": uuid.uuid4().hex, "account_key": self.policy["account_key"], "coordinator_id": self.policy["coordinator_id"], "admitted_at": now, "expires_epoch": now + self.policy["admission_seconds"], "members": chosen, "network_authorized_by_scheduler": False}
            self.db.execute("INSERT INTO groups(id,state,manifest) VALUES(?,'RESERVED',?)", (group["group_id"], canonical(group)))
            self.db.execute("UPDATE config SET turn=turn+1 WHERE id=1")
            turn = self.db.execute("SELECT turn FROM config WHERE id=1").fetchone()[0]
            for entry in chosen:
                self.db.execute("UPDATE items SET state='RESERVED',group_id=? WHERE request_id=?", (group["group_id"], entry["request_id"]))
                self.db.execute("INSERT INTO turns(task_id,last_turn) VALUES(?,?) ON CONFLICT(task_id) DO UPDATE SET last_turn=excluded.last_turn", (entry["task_id"], turn))
            self.event("RESERVED", group)
            return group

    def mark_started(self, group_id, *, now=None):
        now = time.time() if now is None else now
        with self.transaction():
            row = self.db.execute("SELECT * FROM groups WHERE id=?", (group_id,)).fetchone()
            if not row or row["state"] != "RESERVED":
                raise ValueError("UNSTARTED_RESERVATION_REQUIRED")
            manifest = json.loads(row["manifest"])
            if not manifest["admitted_at"] <= now < manifest["expires_epoch"]:
                raise ValueError("EXPIRED_OR_FUTURE_ADMISSION_NO_NETWORK")
            self.db.execute("UPDATE groups SET state='STARTED' WHERE id=?", (group_id,))
            self.db.execute("UPDATE items SET state='STARTED' WHERE group_id=?", (group_id,))
            self.event("STARTED_ADAPTER", {"group_id": group_id, "at": now})

    def cancel_unstarted(self, group_id, reason):
        """Only a local reservation not yet handed to an adapter can be requeued."""
        with self.transaction():
            row = self.db.execute("SELECT state FROM groups WHERE id=?", (group_id,)).fetchone()
            if not row or row[0] != "RESERVED":
                raise ValueError("MAY_HAVE_SENT_REQUIRES_REAL_TERMINAL")
            self.db.execute("UPDATE groups SET state='CANCELLED_NO_ADAPTER' WHERE id=?", (group_id,))
            self.db.execute("UPDATE items SET state='READY',group_id=NULL WHERE group_id=?", (group_id,))
            self.event("CANCELLED_BEFORE_ADAPTER", {"group_id": group_id, "reason": reason})

    def quarantine(self, group_id, reason):
        with self.transaction():
            changed = self.db.execute("UPDATE groups SET state='QUARANTINED' WHERE id=? AND state IN ('STARTED','QUARANTINED')", (group_id,)).rowcount
            if not changed:
                raise ValueError("STARTED_GROUP_REQUIRED")
            self.event("QUARANTINED", {"group_id": group_id, "reason": reason})

    def finish(self, group_id, proof_ref):
        """Consume a coordinator's normalized pointer to actual broker/owner returns."""
        proof = checked_json(proof_ref)
        if proof.get("group_id") != group_id:
            raise ValueError("RETURN_GROUP_MISMATCH")
        returned = checked_json(proof["batch_return"])
        release = checked_json(returned["release"])
        terminal = checked_json(returned["terminal"])
        if (release.get("status") != "RELEASED" or terminal.get("remote_terminal") is not True
                or terminal.get("mode") != "real" or terminal.get("status") not in ("COMPLETE", "FAILED")
                or terminal.get("in_flight_requests") != []
                or release.get("resource") != "nlm-account:" + self.policy["account_key"]
                or terminal.get("process_group_empty") is not True
                or terminal.get("resource_lease", {}).get("id") != release.get("id")
                or release.get("release_proof", {}).get("external_locks_probed_and_released") is not True):
            raise ValueError("ACTUAL_RELEASE_NOT_PROVEN")
        row = self.db.execute("SELECT * FROM groups WHERE id=?", (group_id,)).fetchone()
        if not row or row["state"] not in ("STARTED", "QUARANTINED"):
            raise ValueError("UNRETURNED_STARTED_GROUP_REQUIRED")
        manifest = json.loads(row["manifest"])
        expected = {e["request_id"]: e for e in manifest["members"]}
        outcomes = returned["members"]
        ids = [o["origin_request_id"] for o in outcomes]
        if len(ids) != len(set(ids)) or set(ids) != set(expected):
            raise ValueError("RETURN_MEMBERS_MISMATCH")
        receipts = []
        for outcome in outcomes:
            receipt = checked_json(outcome["receipt"])
            key = outcome["origin_request_id"]
            identity = expected[key]["logical_identity"]
            if (outcome.get("network_terminal") is not True or receipt.get("network_terminal") is not True
                    or receipt.get("remote_terminal") is not True or receipt.get("process_group_empty") is not True
                    or receipt.get("request_id") != key or receipt.get("mode") != "real"
                    or receipt.get("resource_lease", {}).get("id") != release["id"]
                    or receipt.get("status") not in ("COMPLETE", "FAILED")
                    or outcome.get("status") != receipt["status"]):
                raise ValueError("ORIGINAL_NETWORK_TERMINAL_NOT_PROVEN")
            for field in ("account_key", "notebook_id", "document_sha256", "round_id"):
                if receipt.get(field) != identity[field]:
                    raise ValueError("RETURN_IDENTITY_MISMATCH: " + field)
            if sorted(receipt.get("source_ids", [])) != sorted(identity["source_ids"]):
                raise ValueError("RETURN_SOURCES_MISMATCH")
            original = checked_json(receipt["request"])
            if (original.get("operation") != identity["operation"]
                    or hashlib.sha256(original.get("prompt", "").encode()).hexdigest() != identity["prompt_sha256"]):
                raise ValueError("ORIGINAL_PROMPT_OR_OPERATION_MISMATCH")
            if receipt["status"] == "COMPLETE" and (receipt.get("fully_received") is not True or receipt.get("source_contract_valid") is not True):
                raise ValueError("COMPLETE_RESPONSE_CONTRACT_NOT_PROVEN")
            for name in ("native_fetch", "raw_response", "raw_answer", "cleanup", "envelope", "request"):
                if name in receipt:
                    checked(receipt[name])
            receipts.append(receipt)
        with self.transaction():
            state = self.db.execute("SELECT state FROM groups WHERE id=?", (group_id,)).fetchone()[0]
            if state not in ("STARTED", "QUARANTINED"):
                raise ValueError("RETURN_ALREADY_CONSUMED")
            self.db.execute("UPDATE groups SET state='RETURNED',proof=? WHERE id=?", (canonical(proof_ref), group_id))
            for receipt in receipts:
                self.db.execute("UPDATE items SET state='RETURNED',outcome=? WHERE request_id=?", (receipt["status"], receipt["request_id"]))
            if any(r.get("quota_limited") is True for r in receipts):
                self.db.execute("UPDATE config SET paused=1 WHERE id=1")
            self.event("NETWORK_RETURNED_NOT_PAPER_ACCEPTED", {"group_id": group_id, "proof": proof_ref, "review_credit": False})
        return {"status": "RETURNED", "review_credit": False, "outcomes": {r["request_id"]: r["status"] for r in receipts}}

    def status(self):
        return {"items": [dict(row) for row in self.db.execute("SELECT request_id,task_id,position,state,outcome,group_id FROM items ORDER BY seq")], "groups": [dict(row) for row in self.db.execute("SELECT id,state FROM groups")], "paused": bool(self.db.execute("SELECT paused FROM config WHERE id=1").fetchone()[0])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("operation", choices=("enqueue", "status"))
    parser.add_argument("--input")
    args = parser.parse_args()
    queue = ReadyQueue(args.database, json.loads(Path(args.policy).read_text()))
    try:
        result = queue.enqueue(json.loads(Path(args.input).read_text())) if args.operation == "enqueue" else queue.status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        queue.db.close()


if __name__ == "__main__":
    main()
