"""Measured CLI argv contracts and response normalization; never executes a CLI."""
from __future__ import annotations
from pathlib import Path


def cli_argv(provider, operation, *, notebook_id, file=None, prompt=None,
             source_ids=(), conversation_id=None):
    if provider not in {"nlm", "notebooklm"} or not notebook_id:
        raise ValueError("EXPLICIT_PROVIDER_AND_NOTEBOOK_REQUIRED")
    if operation == "source_add":
        p = Path(file or "").resolve(strict=True)
        if not p.is_file() or p.read_bytes()[:5] != b"%PDF-":
            raise ValueError("EXISTING_PDF_FILE_REQUIRED")
        return (["nlm", "source", "add", notebook_id, "--file", str(p), "--wait", "--json"]
                if provider == "nlm" else
                ["notebooklm", "source", "add", str(p), "-n", notebook_id, "--type", "file", "--json"])
    if operation == "source_fulltext" and provider == "notebooklm" and len(source_ids) == 1:
        return ["notebooklm", "source", "fulltext", source_ids[0], "-n", notebook_id, "--json"]
    if operation == "source_fulltext" and provider == "nlm" and len(source_ids) == 1:
        return ["nlm", "content", "source", source_ids[0], "--json"]
    if operation == "list":
        return ["nlm", "notebook", "list", "--json"] if provider == "nlm" else ["notebooklm", "list", "--json"]
    if operation == "query" and prompt and source_ids:
        if provider == "nlm":
            args = ["nlm", "notebook", "query", notebook_id, prompt, "--source-ids", ",".join(source_ids), "--json"]
            return args + (["--conversation-id", conversation_id] if conversation_id else ["--new-conversation"])
        # notebooklm-py 0.8.1 --new deletes the existing server conversation.
        # Its help contract does not provide a non-destructive fresh-round route.
        if not conversation_id:
            raise ValueError("NONDESTRUCTIVE_NEW_CONVERSATION_NOT_VERIFIED")
        args = ["notebooklm", "ask", prompt, "-n", notebook_id, "-c", conversation_id, "--json"]
        for source in source_ids:
            args += ["-s", source]
        return args
    raise ValueError("CLI_CAPABILITY_NOT_VERIFIED")


def reject_error(data):
    if data.get("success") is False or data.get("ok") is False or data.get("error") or str(data.get("status", "")).upper() in {"ERROR", "FAILED", "FAILURE"}:
        raise ValueError("REMOTE_ERROR_RESPONSE")


def unwrap(data):
    if not isinstance(data, dict):
        raise ValueError("RESPONSE_OBJECT_REQUIRED")
    reject_error(data)
    value = data.get("value", data)
    if not isinstance(value, dict):
        raise ValueError("RESPONSE_OBJECT_REQUIRED")
    reject_error(value)
    return value


def normalized_result(operation, data, *, source_id=None, notebook_id=None):
    # nlm 0.9.12 emits a bare array, including [] for an empty account.  Only
    # this operation permits an array; query/fulltext keep their object gate.
    if operation == "list":
        value = data
        if isinstance(value, dict):
            reject_error(value)
            value = value.get("value", value)
        if isinstance(value, dict):
            reject_error(value)
            value = value.get("notebooks")
        if not isinstance(value, list):
            raise ValueError("NOTEBOOK_LIST_MISSING")
        for notebook in value:
            if not isinstance(notebook, dict):
                raise ValueError("INVALID_NOTEBOOK_LIST_ENTRY")
            reject_error(notebook)
            if not isinstance(notebook.get("id", notebook.get("notebook_id")), str) or not notebook.get("id", notebook.get("notebook_id")):
                raise ValueError("NOTEBOOK_ID_MISSING")
        return {"notebooks": value}
    value = unwrap(data)
    if notebook_id and value.get("notebook_id") not in {None, notebook_id}:
        raise ValueError("RESPONSE_NOTEBOOK_MISMATCH")
    if operation == "source_add":
        source = value.get("source", value)
        if not isinstance(source, dict) or not (source.get("source_id") or source.get("id")):
            raise ValueError("UPLOAD_SOURCE_ID_MISSING")
        reject_error(source)
        if notebook_id and source.get("notebook_id") not in {None, notebook_id}:
            raise ValueError("RESPONSE_NOTEBOOK_MISMATCH")
        status = str(source.get("status", value.get("status", "UNKNOWN"))).upper()
        if status in {"ERROR", "FAILED", "FAILURE"}:
            raise ValueError("UPLOAD_FAILED")
        return {"source_id": source.get("source_id", source.get("id")), "status": status,
                "ready": status in {"READY", "PROCESSED"}, "raw": value}
    if operation == "source_fulltext":
        text = value.get("content", value.get("fulltext", value.get("text")))
        if not isinstance(text, str) or not text.strip():
            raise ValueError("FULLTEXT_CONTENT_MISSING")
        actual_id = value.get("source_id", value.get("id"))
        if not isinstance(actual_id, str) or not actual_id:
            raise ValueError("FULLTEXT_SOURCE_ID_MISSING")
        if source_id is not None and actual_id != source_id:
            raise ValueError("RESPONSE_SOURCE_MISMATCH")
        return {"content": text, "source_id": actual_id, "raw": value}
    if operation == "query":
        return value
    raise ValueError("UNSUPPORTED_RESPONSE_OPERATION")
