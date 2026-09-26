"""Offline file identity: exact declared path + SHA256; optional size is checked.

Extra descriptive metadata is retained by callers, not promoted into identity.
Byte-identical copies at other paths need an explicit copy/provenance contract.
"""
import hashlib
from pathlib import Path
import re


def checked_bytes(ref):
    if (not isinstance(ref, dict) or not isinstance(ref.get("path"), str)
            or not isinstance(ref.get("sha256"), str)
            or re.fullmatch(r"[a-f0-9]{64}", ref["sha256"]) is None):
        raise ValueError("HASHED_FILE_REFERENCE_REQUIRED")
    path = Path(ref["path"])
    if not path.is_absolute() or not path.is_file():
        raise ValueError("ABSOLUTE_EVIDENCE_REQUIRED")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise ValueError("EVIDENCE_HASH_MISMATCH: " + str(path))
    if "bytes" in ref and (type(ref["bytes"]) is not int or ref["bytes"] < 0
                           or len(raw) != ref["bytes"]):
        raise ValueError("EVIDENCE_SIZE_MISMATCH")
    return raw


def same_identity(actual, expected):
    """Verify both files before comparing; do not resolve away a changed root."""
    checked_bytes(actual)
    checked_bytes(expected)
    return (actual["path"], actual["sha256"]) == (expected["path"], expected["sha256"])
