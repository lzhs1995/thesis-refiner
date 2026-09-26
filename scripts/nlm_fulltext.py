"""Normalize an observed nlm fulltext response without inventing source identity.

The nlm 0.9.12 formatter omits the source ID returned by hizoJc.  A pinned
transport may use this offline function after verifying a fully received fetch
receipt and its response hash.  The caller owns transport/request provenance;
this function verifies the server ID and exact text against the CLI output.
It neither sends requests nor changes runtime, quota or lease state.
"""
from __future__ import annotations

import hashlib
import json

from nlm_contracts import normalized_result, unwrap


def _text_strings(value):
    """Match the measured client's extraction of nested nonempty strings."""
    for item in value:
        if isinstance(item, str) and item:
            yield item
        elif isinstance(item, list):
            yield from _text_strings(item)


def normalize_rpc_fulltext(cli_data, response_bytes, *, response_sha256,
                           expected_source_id):
    """Return an enriched copy; expected_source_id is a check, never the result.

    response_sha256 must come from the caller's verified terminal fetch receipt.
    The hash alone is not authentication or proof that a network call completed.
    No notebook ID is synthesized: hizoJc here does not echo notebook membership.
    """
    if not isinstance(response_bytes, bytes) or hashlib.sha256(response_bytes).hexdigest() != response_sha256:
        raise ValueError("FULLTEXT_RESPONSE_HASH_MISMATCH")
    if not isinstance(expected_source_id, str) or not expected_source_id:
        raise ValueError("EXPECTED_SOURCE_ID_REQUIRED")
    value = unwrap(cli_data)
    payloads = []
    for line in response_bytes.decode("utf-8").splitlines():
        try:
            frames = json.loads(line)
        except ValueError:
            continue  # XSSI prefix and byte-length framing are not RPC payloads.
        if not isinstance(frames, list):
            continue
        for frame in frames:
            if isinstance(frame, list) and frame[:2] == ["wrb.fr", "hizoJc"]:
                if len(frame) < 3 or not isinstance(frame[2], str):
                    raise ValueError("FULLTEXT_RPC_PAYLOAD_INVALID")
                payloads.append(json.loads(frame[2]))
    if len(payloads) != 1:
        raise ValueError("ONE_FULLTEXT_RPC_RESPONSE_REQUIRED")
    payload = payloads[0]
    if (not isinstance(payload, list) or len(payload) < 4
            or not isinstance(payload[0], list) or len(payload[0]) < 2
            or not isinstance(payload[0][0], list) or len(payload[0][0]) != 1
            or not isinstance(payload[0][0][0], str) or not payload[0][0][0]):
        raise ValueError("FULLTEXT_SERVER_SOURCE_ID_MISSING")
    actual_id = payload[0][0][0]
    if actual_id != expected_source_id:
        raise ValueError("RESPONSE_SOURCE_MISMATCH")
    if any(value[k] != actual_id for k in ("source_id", "id") if k in value):
        raise ValueError("CLI_AND_SERVER_SOURCE_MISMATCH")
    if not isinstance(payload[0][1], str) or value.get("title") != payload[0][1]:
        raise ValueError("FULLTEXT_TITLE_MISMATCH")
    if (not isinstance(payload[3], list) or len(payload[3]) != 1
            or not isinstance(payload[3][0], list)):
        raise ValueError("FULLTEXT_BLOCKS_MISSING")
    parts = []
    for block in payload[3][0]:
        if not isinstance(block, list):
            raise ValueError("FULLTEXT_BLOCK_INVALID")
        parts.extend(_text_strings(block))
    content = "\n\n".join(parts)
    if not content.strip() or value.get("content") != content:
        raise ValueError("CLI_AND_SERVER_FULLTEXT_MISMATCH")
    if type(value.get("char_count")) is not int or value["char_count"] != len(content):
        raise ValueError("FULLTEXT_CHARACTER_COUNT_MISMATCH")
    result = {**value, "source_id": actual_id,
              "identity_provenance": {"kind": "server_rpc", "rpc_id": "hizoJc",
                  "response_sha256": response_sha256, "source_id_location": "[0][0][0]",
                  "cli_source_id_present": "source_id" in value,
                  "notebook_identity": "request_binding_only"}}
    normalized_result("source_fulltext", result, source_id=expected_source_id)
    return result
