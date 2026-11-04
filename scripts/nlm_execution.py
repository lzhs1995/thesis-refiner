"""Explicit new-task adoption of the existing MAC prelaunch execution gate.

No queue, lock, identity provider or remote cancellation is implemented here.
The facade keeps nlm_runtime's original budget and receipt state machine.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import types


class ExecutionBindingError(ValueError):
    pass


def need(condition, reason):
    if not condition:
        raise ExecutionBindingError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def full_ref(path):
    path = Path(path)
    need(path.is_absolute() and not path.is_symlink() and path.resolve(strict=True) == path,
         "CANONICAL_EXECUTION_PATH_REQUIRED")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode), "REGULAR_EXECUTION_FILE_REQUIRED")
        hasher, total = hashlib.sha256(), 0
        while True:
            block = os.read(fd, 1024**2)
            if not block:
                break
            total += len(block)
            need(total <= before.st_size, "EXECUTION_PIN_GREW")
            hasher.update(block)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        need(total == before.st_size
             and identity(before) == identity(os.fstat(fd)) == identity(path.stat()), "EXECUTION_PIN_CHANGED")
        return {"path": str(path), "bytes": total, "sha256": hasher.hexdigest()}
    finally:
        os.close(fd)


def pinned_bytes(value, *, body=True):
    need(isinstance(value, dict) and set(value) == {"path", "bytes", "sha256"}, "FULL_EXECUTION_REF_REQUIRED")
    need(isinstance(value["path"], str) and type(value["bytes"]) is int and value["bytes"] >= 0
         and isinstance(value["sha256"], str) and re.fullmatch("[0-9a-f]{64}", value["sha256"]),
         "INVALID_EXECUTION_REF")
    path = Path(value["path"])
    need(path.is_absolute() and not path.is_symlink() and str(path.resolve(strict=True)) == str(path),
         "CANONICAL_EXECUTION_PATH_REQUIRED")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_size == value["bytes"], "EXECUTION_PIN_CHANGED")
        need(not body or before.st_size <= 8 * 1024**2, "EXECUTION_PIN_BODY_TOO_LARGE")
        hasher, chunks, total = hashlib.sha256(), [], 0
        while True:
            block = os.read(fd, 1024**2)
            if not block:
                break
            total += len(block)
            need(total <= value["bytes"], "EXECUTION_PIN_GREW")
            hasher.update(block)
            if body:
                chunks.append(block)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        need(identity(before) == identity(os.fstat(fd)) == identity(path.stat()),
             "EXECUTION_PIN_CHANGED")
        need(total == value["bytes"] and hasher.hexdigest() == value["sha256"], "EXECUTION_PIN_CHANGED")
        return b"".join(chunks) if body else None
    finally:
        os.close(fd)


def adoption(binding):
    value = binding.get("execution_contract")
    need(isinstance(value, dict) and set(value) == {
        "schema", "new_tasks_only", "actor", "controller", "cwd", "environment", "inputs"},
        "EXACT_NLM_EXECUTION_ADOPTION_REQUIRED")
    need(value["schema"] == "nlm-execution-adoption-v1" and value["new_tasks_only"] is True,
         "NEW_TASK_EXECUTION_ADOPTION_REQUIRED")
    need(isinstance(value["actor"], dict)
         and all(value["actor"].get(k) == binding.get(k) for k in ("workspace_uuid", "surface_uuid")),
         "NLM_EXECUTION_ACTOR_BINDING_MISMATCH")
    return value


def reject_overrides(request):
    reserved = {"actor", "actor_id", "owner_role", "session_id", "pane_uuid", "resource",
                "resource_lease", "generation", "request_revision", "attempt_id", "argv", "cwd",
                "environment", "inputs", "token", "contract_sha256", "lease", "binding"}
    forbidden = [key for key in request if key in reserved
                 or str(key).lower().startswith(("execution", "native", "controller"))]
    need(not forbidden, "REQUEST_CANNOT_OVERRIDE_EXECUTION: " + ",".join(sorted(forbidden)))


def load_broker(binding):
    """Validate the complete controller before compiling any of its modules.

    Do not put a controller directory on sys.path or consume an unchecked pyc.
    MAC performs its own pinned native dependency loading and authentication.
    """
    controller = adoption(binding)["controller"]
    need(isinstance(controller, dict) and set(controller) == {"source", "files"}, "CONTROLLER_REQUIRED")
    source = Path(controller["source"])
    need(source.is_absolute() and not source.is_symlink() and source.is_dir()
         and str(source.resolve()) == str(source), "CANONICAL_CONTROLLER_SOURCE_REQUIRED")
    need(isinstance(controller["files"], list), "COMPLETE_CONTROLLER_REQUIRED")
    refs = {}
    for item in controller["files"]:
        need(isinstance(item, dict) and set(item) == {"relative", "bytes", "sha256"}, "CONTROLLER_FILE_REQUIRED")
        name = item["relative"]
        need(isinstance(name, str) and re.fullmatch(r"scripts/[A-Za-z0-9_]+\.py", name)
             and name not in refs, "INVALID_CONTROLLER_MEMBER")
        refs[name] = {"path": str(source / name), "bytes": item["bytes"], "sha256": item["sha256"]}
    expected = {str(p.relative_to(source)) for p in (source / "scripts").glob("*.py")}
    need(set(refs) == expected and {"scripts/resource_broker.py", "scripts/resource_execution.py",
         "scripts/cmux_workspace_guard.py"} <= expected, "COMPLETE_CONTROLLER_REQUIRED")
    bodies = {name: pinned_bytes(value) for name, value in refs.items()}
    need(binding.get("broker_module") == refs["scripts/resource_broker.py"], "BROKER_CONTROLLER_PIN_MISMATCH")
    # The broker uses this exact module name. Refuse a previous/foreign loader
    # instead of silently replacing native state or accepting a stale module.
    for name, relative in (("resource_execution", "scripts/resource_execution.py"),
                           ("thesis_enforced_resource_broker", "scripts/resource_broker.py")):
        value = refs[relative]
        module = sys.modules.get(name)
        if module is not None:
            need(getattr(module, "__file__", None) == value["path"]
                 and getattr(module, "__execution_pin__", None) == value["sha256"],
                 "FOREIGN_OR_UNPINNED_EXECUTION_MODULE")
        else:
            module = types.ModuleType(name)
            module.__file__ = value["path"]
            module.__execution_pin__ = value["sha256"]
            sys.modules[name] = module
            try:
                exec(compile(bodies[relative], value["path"], "exec", dont_inherit=True), module.__dict__)
            except BaseException:
                sys.modules.pop(name, None)
                raise
    module = sys.modules["thesis_enforced_resource_broker"]
    for method in ("validate_execution_contract", "request_enforced", "grant_enforced",
                   "run_enforced", "release_enforced", "requeue_unsubmitted_enforced"):
        need(callable(getattr(module.Broker, method, None)), "ENFORCED_BROKER_API_REQUIRED: " + method)
    return module


def _freeze(path, data):
    need(len(data) <= 8 * 1024**2, "PREPARATION_TOO_LARGE")
    value = {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        try:
            pinned_bytes(value)
        except (ValueError, OSError) as exc:
            raise ExecutionBindingError("ORIGINAL_PREPARATION_CHANGED") from exc
    pinned_bytes(value)
    return value


def prepare(binding, request, root, key, module):
    """Prepare original bytes and authenticate before creating either database."""
    adopted = adoption(binding)
    inputs = adopted["inputs"]
    need(isinstance(inputs, list) and inputs, "BOUND_INPUTS_REQUIRED")
    for value in inputs:
        pinned_bytes(value, body=False)
    if request["operation"] == "query":
        need(any(value["sha256"] == request["document_sha256"] for value in inputs),
             "QUERY_DOCUMENT_NOT_BOUND_INPUT")
    if request["operation"] == "source_add":
        need(any(value["path"] == request["file"] and value["sha256"] == request["file_sha256"]
                 for value in inputs), "UPLOAD_NOT_BOUND_INPUT")
    root = Path(root).resolve()
    directory = root / "enforced-preparations" / key
    directory.mkdir(parents=True, exist_ok=True)
    need(directory.resolve() == directory, "CANONICAL_PREPARATION_REQUIRED")
    request_ref = _freeze(directory / "request.json", (canonical(request) + "\n").encode())
    prompt_ref = _freeze(directory / "prompt.txt", request.get("prompt", "").encode())
    out = root / "receipts" / key
    fields = {**request, **binding, "request_id": key, "prompt_file": prompt_ref["path"],
              "output_dir": str(out), "source_ids_csv": ",".join(request.get("source_ids") or [request.get("source_id", "")])}
    argv = [str(arg).format_map(fields) for arg in binding["commands"][request["operation"]]]
    contract = {"schema": "resource-execution-v1", "task_id": request["task_id"],
                "resource": "nlm-account:" + binding["account_key"], "actor": adopted["actor"],
                "controller": adopted["controller"], "operation": request["operation"],
                "request_revision": request_ref["sha256"], "attempt_id": "nlm:" + key,
                "argv": argv, "cwd": adopted["cwd"], "environment": adopted["environment"],
                "transport_artifacts": binding["transport_artifacts"], "inputs": [*inputs, request_ref, prompt_ref]}
    contract = module.Broker.validate_execution_contract(contract)
    _freeze(directory / "contract.json", (canonical(contract) + "\n").encode())
    return contract, Path(prompt_ref["path"])


class EnforcedBroker:
    """Adapt only request/grant/run/release; keep original NLM receipts intact."""
    def __init__(self, module, binding, contract):
        self.raw = module.Broker(binding.get("resource_root"))
        self.root = self.raw.root
        self.contract = contract
        self.lease = None
        self.result_execution = None

    def configure(self, *args, **kwargs):
        return self.raw.configure(*args, **kwargs)

    def request(self, resource, task_id, workspace_uuid, surface_uuid):
        need((resource, task_id, workspace_uuid, surface_uuid) == (
            self.contract["resource"], self.contract["task_id"], self.contract["actor"]["workspace_uuid"],
            self.contract["actor"]["surface_uuid"]), "EXECUTION_REQUEST_BINDING_MISMATCH")
        return self.raw.request_enforced(self.contract)

    def grant(self, ticket, ttl):
        self.lease = self.raw.grant_enforced(ticket, ttl=ttl)
        return self.lease

    def requeue_unsubmitted(self, ticket):
        execution = self.verify_lease(ticket)
        return self.raw.requeue_unsubmitted_enforced(
            ticket["id"], ticket["token"], generation=execution["generation"])

    def verify_lease(self, lease):
        execution = lease.get("execution") or {}
        need(execution.get("contract_sha256") == digest(self.contract)
             and all(execution.get(k) == self.contract[k] for k in ("operation", "request_revision", "attempt_id")),
             "ORIGINAL_EXECUTION_BINDING_REQUIRED")
        need(type(execution.get("generation")) is int and execution["generation"] > 0,
             "ORIGINAL_EXECUTION_GENERATION_REQUIRED")
        return execution

    def run(self, ticket, token, command, **kwargs):
        need(command == self.contract["argv"], "ACTUAL_ARGV_DIFFERS_FROM_EXECUTION_CONTRACT")
        need(self.lease is not None and (ticket, token) == (self.lease["id"], self.lease["token"]),
             "ORIGINAL_EXECUTION_LEASE_REQUIRED")
        execution = self.verify_lease(self.lease)
        result = self.raw.run_enforced(ticket, token, **{k: execution[k] for k in (
            "generation", "operation", "request_revision", "attempt_id")}, **kwargs)
        self.result_execution = result["execution"]
        return result

    def release(self, ticket, token, proof, reconcile=False):
        execution = self.verify_lease(self.lease)
        proof = dict(proof, execution=self.result_execution or execution)
        if proof.get("terminal_receipt"):
            old = proof["terminal_receipt"]
            value = full_ref(old["path"])
            need(value["sha256"] == old["sha256"], "TERMINAL_RECEIPT_CHANGED")
            proof["terminal_receipt"] = value
        return self.raw.release_enforced(ticket, token, proof,
                                         generation=execution["generation"], reconcile=reconcile)

    def verify_cached(self, saved):
        lease = saved.get("resource_lease") or {}
        self.verify_lease(lease)
        current = self.raw.get(lease["id"])
        need(current["status"] == "RELEASED" and current["token"] == lease["token"],
             "ORIGINAL_EXECUTION_RELEASE_REQUIRED")

    def close(self):
        self.raw.db.close()
