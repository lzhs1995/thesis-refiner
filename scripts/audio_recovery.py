#!/usr/bin/env python3
"""Offline, request-specific checks for resuming an already created audio artifact.

No network, scheduler, accounting, application or input writes occur here. A caller
must still obtain current executor authority and a real resource lease. Pins are
integrity anchors supplied by that caller, not signatures or evidence of freshness.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
import uuid


ALLOWED = {"studio_status", "audio_download"}


class Rejected(ValueError):
    """A contract is incomplete, changed or outside the observation phase."""


def require(condition, code):
    if not condition:
        raise Rejected(code)


def integer(value, expected, code):
    require(type(value) is int and value == expected, code)


def text(value, code):
    require(isinstance(value, str) and bool(value.strip()), code)
    return value


def absolute(value):
    path = Path(text(value, "ABSOLUTE_PATH_REQUIRED"))
    require(path.is_absolute(), "ABSOLUTE_PATH_REQUIRED")
    return path.resolve()


def uuid_value(value):
    try:
        return str(uuid.UUID(text(value, "UUID_REQUIRED")))
    except (ValueError, AttributeError) as exc:
        raise Rejected("INVALID_UUID") from exc


def timestamp(value):
    try:
        result = datetime.fromisoformat(text(value, "RECEIPT_TIMESTAMP_REQUIRED"))
        require(result.tzinfo is not None, "TIMEZONE_REQUIRED")
        return result
    except ValueError as exc:
        raise Rejected("INVALID_RECEIPT_TIMESTAMP") from exc


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def json_bytes(data):
    value = json.loads(data, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(Rejected("NONFINITE_JSON")))
    require(isinstance(value, dict), "JSON_OBJECT_REQUIRED")
    return value


def read_pin(ref):
    require(isinstance(ref, dict) and set(ref) == {"path", "sha256"}, "EXACT_FILE_PIN_REQUIRED")
    digest = ref["sha256"]
    require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), "INVALID_SHA256")
    path = absolute(ref["path"])
    require(path.is_file(), "PIN_FILE_MISSING")
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == digest, "PIN_HASH_MISMATCH")
    return data


def document(ref):
    return json_bytes(read_pin(ref))


def same_pin(left, right):
    read_pin(left)
    read_pin(right)
    require(absolute(left["path"]) == absolute(right["path"])
            and left["sha256"] == right["sha256"], "PIN_IDENTITY_MISMATCH")


def request_identity(request, task, notebook, artifact):
    require(request.get("task_id") == task and request.get("notebook_id") == notebook,
            "REQUEST_SCOPE_CHANGED")
    require(request.get("operation") in ALLOWED, "OBSERVE_OR_DOWNLOAD_ONLY")
    require(request.get("artifact_id") == artifact, "ORIGINAL_ARTIFACT_REQUIRED")


def terminal(receipt_ref, release_ref, task, notebook):
    """Check the pinned terminal chain, not merely COMPLETE/RELEASED labels."""
    receipt, release = document(receipt_ref), document(release_ref)
    require(receipt.get("mode") == "real" and receipt.get("status") in {"COMPLETE", "FAILED"},
            "KNOWN_REAL_TERMINAL_REQUIRED")
    require(receipt.get("remote_terminal") is True
            and receipt.get("process_group_empty") is True
            and receipt.get("in_flight_requests") == [], "TERMINAL_RESOURCE_UNKNOWN")
    require(type(receipt.get("exit_code")) is int, "INTEGER_EXIT_CODE_REQUIRED")
    require((receipt["exit_code"] == 0) == (receipt["status"] == "COMPLETE"),
            "TERMINAL_EXIT_MISMATCH")
    require(receipt.get("notebook_id") == notebook, "RECEIPT_NOTEBOOK_CHANGED")
    lease = receipt.get("resource_lease", {})
    require(isinstance(lease, dict) and lease.get("task_id") == task, "LEASE_SCOPE_CHANGED")
    for key in ("id", "resource", "task_id", "surface_uuid", "workspace_uuid"):
        text(lease.get(key), "LEASE_IDENTITY_MISSING")
        require(release.get(key) == lease[key], "RELEASE_IDENTITY_CHANGED")
    require(release.get("status") == "RELEASED", "RESOURCE_NOT_RELEASED")
    integer(release.get("invocations"), 1, "ONE_ORIGINAL_INVOCATION_REQUIRED")
    proof = release.get("release_proof", {})
    require(isinstance(proof, dict) and proof.get("pending") is False
            and proof.get("own_processes_empty") is True
            and proof.get("in_flight_requests") == []
            and proof.get("external_locks_probed_and_released") is True,
            "RELEASE_PROOF_INCOMPLETE")
    same_pin(proof.get("terminal_receipt"), receipt_ref)
    transport = document(receipt.get("transport"))
    require(transport.get("remote_terminal") is True
            and transport.get("in_flight_requests") == []
            and transport.get("operation") == receipt.get("operation")
            and type(transport.get("exit_code")) is int
            and transport["exit_code"] == receipt["exit_code"], "TRANSPORT_TERMINAL_UNKNOWN")
    request = document(receipt.get("request"))
    require(request.get("task_id") == task and request.get("notebook_id") == notebook
            and request.get("operation") == receipt.get("operation"), "RECEIPT_REQUEST_CHANGED")
    result = None
    if receipt["status"] == "COMPLETE":
        same_pin(transport.get("result"), receipt.get("raw_answer"))
        result = document(receipt["raw_answer"])
    return receipt, request, transport, result


def validate(contract, request, operator_uuid, workspace_uuid):
    integer(contract.get("schema_version"), 1, "SCHEMA_VERSION_REQUIRED")
    required = {"schema_version", "plan", "intent", "created", "download_request",
                "succession", "binding", "operations", "preserve"}
    require(set(contract) == required, "EXACT_CONTRACT_FIELDS_REQUIRED")
    plan, intent, created = (document(contract[key]) for key in ("plan", "intent", "created"))
    task, notebook = text(plan.get("task_id"), "TASK_REQUIRED"), text(plan.get("notebook_id"), "NOTEBOOK_REQUIRED")
    integer(plan.get("audio_create_cap"), 1, "ONE_CREATE_SCOPE_REQUIRED")
    integer(intent.get("create_limit"), 1, "ONE_CREATE_INTENT_REQUIRED")
    require(intent.get("automatic_retries") is False, "NO_AUTOMATIC_CREATE_RETRY_REQUIRED")
    same_pin(intent.get("request"), created.get("request"))
    original = document(created["request"])
    require(original.get("task_id") == task and original.get("notebook_id") == notebook
            and original.get("operation") == "audio_create", "ORIGINAL_CREATE_SCOPE_CHANGED")
    same_pin(intent.get("source_selection"), original.get("selection"))
    selection = document(original["selection"])
    source_ids = original.get("source_ids")
    require(isinstance(source_ids, list) and bool(source_ids)
            and all(isinstance(item, str) and item.strip() for item in source_ids)
            and len(set(source_ids)) == len(source_ids), "UNIQUE_SOURCE_IDS_REQUIRED")
    require(selection.get("notebook_id") == notebook
            and isinstance(selection.get("sources"), list)
            and all(isinstance(item, dict) for item in selection["sources"])
            and [item.get("source_id") for item in selection["sources"]] == source_ids,
            "ORIGINAL_SOURCE_SELECTION_CHANGED")
    integer(selection.get("audio_source_count"), len(source_ids), "SOURCE_COUNT_CHANGED")
    for request_key, plan_key in (("format", "format"), ("length", "length"),
                                  ("language", "language"), ("prompt", "focus_prompt")):
        text(original.get(request_key), "ORIGINAL_PARAMETER_REQUIRED")
        require(original[request_key] == plan.get(plan_key), "ORIGINAL_PARAMETERS_CHANGED")
    receipt, bound, transport, raw = terminal(created.get("receipt"), created.get("release"), task, notebook)
    require(receipt["status"] == "COMPLETE" and receipt.get("operation") == "audio_create"
            and receipt.get("request_id") == text(intent.get("request_id"), "CREATE_REQUEST_ID_REQUIRED"),
            "CREATE_ACCEPTANCE_UNKNOWN")
    require(all(key in bound and bound[key] == value for key, value in original.items()), "BOUND_CREATE_CHANGED")
    require(receipt.get("account_key") == plan.get("account_key") == bound.get("account_key")
            and isinstance(plan.get("account_key"), str), "ACCOUNT_BINDING_CHANGED")
    integer(transport.get("automatic_create_retries"), 0, "CREATE_RETRY_EVIDENCE_CHANGED")
    http = transport.get("http")
    require(isinstance(http, list) and bool(http)
            and all(isinstance(item, dict) and item.get("fully_received") is True for item in http),
            "CREATE_RESPONSE_NOT_FULLY_RECEIVED")
    artifact = created.get("artifact")
    require(isinstance(artifact, dict) and artifact == raw and artifact.get("type") == "audio"
            and artifact.get("notebook_id") == notebook, "CREATE_ARTIFACT_NOT_PROVEN")
    artifact_id = text(artifact.get("artifact_id"), "CREATE_ARTIFACT_ID_MISSING")
    for key in ("format", "language", "length"):
        require(artifact.get(key) == original[key], "CREATED_PARAMETERS_CHANGED")

    succession, binding = document(contract["succession"]), document(contract["binding"])
    same_pin(succession.get("created"), contract["created"])
    require(succession.get("artifact_id") == artifact_id
            and binding.get("original_artifact_id") == artifact_id
            and binding.get("notebook_id") == notebook
            and binding.get("account_key") == plan["account_key"], "SUCCESSION_SCOPE_CHANGED")
    require(binding.get("observation_only") is True, "OBSERVATION_BINDING_REQUIRED")
    require(uuid_value(operator_uuid) == uuid_value(succession.get("executor_surface_uuid"))
            == uuid_value(binding.get("surface_uuid")), "EXECUTOR_UUID_CHANGED")
    require(uuid_value(workspace_uuid) == uuid_value(binding.get("workspace_uuid")), "WORKSPACE_UUID_CHANGED")
    require(succession.get("allowed_operations") == ["studio_status", "audio_download"],
            "SUCCESSION_OPERATION_SCOPE_CHANGED")
    for key in ("audio_create_cap", "source_add_cap", "query_cap"):
        integer(succession.get(key), 0, "SUCCESSION_ZERO_CAP_REQUIRED")
    text(succession.get("original_user_authorization"), "SUCCESSION_AUTHORIZATION_MISSING")
    require(succession.get("original_files_and_failures_preserved") is True, "HISTORY_PRESERVATION_REQUIRED")
    require(isinstance(contract["preserve"], list), "PRESERVATION_PINS_REQUIRED")
    for ref in contract["preserve"]:
        read_pin(ref)

    target = document(contract["download_request"])
    request_identity(target, task, notebook, artifact_id)
    require(target["operation"] == "audio_download", "ORIGINAL_DOWNLOAD_REQUEST_REQUIRED")
    output = absolute(target.get("output"))
    require(output.parent == absolute(plan.get("destination")), "ORIGINAL_DESTINATION_CHANGED")
    require(Path(target["output"]) == output and Path(plan["destination"]) == output.parent,
            "CANONICAL_DESTINATION_REQUIRED")
    request_identity(request, task, notebook, artifact_id)
    fields = {"task_id", "notebook_id", "operation", "artifact_id", "phase", "round_id", "label"}
    if request["operation"] == "audio_download":
        fields.add("output")
        require(absolute(request.get("output")) == output, "ORIGINAL_OUTPUT_ONLY")
    require(set(request) <= fields, "RECOVERY_REQUEST_PARAMETER_CHANGE")

    require(isinstance(contract["operations"], list), "ORIGINAL_OPERATIONS_REQUIRED")
    generation_state = artifact.get("status")
    previous_ids = {receipt["request_id"]}
    previous_at = timestamp(receipt.get("at"))
    for operation in contract["operations"]:
        require(isinstance(operation, dict) and set(operation) == {"receipt", "release"}, "OPERATION_PINS_REQUIRED")
        prior, prior_request, _, result = terminal(operation["receipt"], operation["release"], task, notebook)
        request_identity(prior_request, task, notebook, artifact_id)
        require(prior.get("account_key") == plan["account_key"]
                and prior_request.get("account_key") == plan["account_key"], "PRIOR_ACCOUNT_CHANGED")
        prior_id = text(prior.get("request_id"), "PRIOR_REQUEST_ID_REQUIRED")
        require(prior_id not in previous_ids, "DUPLICATE_OPERATION_RECEIPT")
        previous_ids.add(prior_id)
        prior_at = timestamp(prior.get("at"))
        require(prior_at >= previous_at, "OPERATION_ORDER_CHANGED")
        previous_at = prior_at
        if prior_request["operation"] == "audio_download":
            require(absolute(prior_request.get("output")) == output, "PRIOR_DOWNLOAD_DESTINATION_CHANGED")
        if prior["status"] != "COMPLETE":
            continue
        if prior_request["operation"] == "studio_status":
            require(result.get("notebook_id") == notebook and isinstance(result.get("artifacts"), list),
                    "STATUS_RESULT_SCOPE_CHANGED")
            found = [item for item in result["artifacts"] if isinstance(item, dict) and item.get("artifact_id") == artifact_id]
            require(len(found) == 1 and found[0].get("type") == "audio", "ORIGINAL_ARTIFACT_STATUS_MISSING")
            generation_state = found[0].get("status")
            if "source_ids" in found[0]:
                require(found[0]["source_ids"] == source_ids, "STATUS_SOURCE_DRIFT")
            if "custom_instructions" in found[0]:
                require(found[0]["custom_instructions"] == original["prompt"], "STATUS_PROMPT_DRIFT")
        else:
            require(result.get("artifact_id") == artifact_id, "DOWNLOADED_ARTIFACT_CHANGED")
            file_ref = result.get("file")
            require(isinstance(file_ref, dict), "DOWNLOADED_FILE_PIN_REQUIRED")
            require(absolute(file_ref.get("path")) == output, "DOWNLOADED_PATH_CHANGED")
            data = read_pin(file_ref)
            require(type(result.get("bytes")) is int and result["bytes"] == len(data) > 0,
                    "DOWNLOADED_BYTES_CHANGED")
    if request["operation"] == "audio_download":
        require(generation_state == "completed", "GENERATION_COMPLETION_NOT_PROVEN")
        require(not output.exists(), "DOWNLOAD_ALREADY_EXISTS_VERIFY_LOCALLY")
    return {"status": "OFFLINE_ELIGIBLE", "operation": request["operation"],
            "network_executed": False, "quota_verified": False,
            "current_authority_verified": False, "resource_admission_verified": False,
            "media_or_content_verified": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate"])
    parser.add_argument("--contract", required=True)
    parser.add_argument("--contract-sha256", required=True, help="Expected pin from the current authorized caller")
    parser.add_argument("--request", required=True)
    parser.add_argument("--operator-uuid", required=True)
    parser.add_argument("--workspace-uuid", required=True)
    args = parser.parse_args(argv)
    try:
        contract = document({"path": args.contract, "sha256": args.contract_sha256})
        request_data = absolute(args.request).read_bytes()
        report = validate(contract, json_bytes(request_data), args.operator_uuid, args.workspace_uuid)
        report.update(contract_sha256=args.contract_sha256,
                      request_sha256=hashlib.sha256(request_data).hexdigest())
        print(json.dumps(report, sort_keys=True))
        return 0
    except (Rejected, OSError, ValueError, TypeError, KeyError) as exc:
        # Error codes only: private request prompts, URLs and tokens are not printed.
        code = str(exc) if isinstance(exc, Rejected) else type(exc).__name__
        print(json.dumps({"status": "REJECTED", "reason": code, "network_executed": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
