#!/usr/bin/env python3
"""Verify an existing delivery manifest/ZIP and generate exact local chat links.

Read-only for all delivery files. Writes only explicitly named new reports;
does not rebuild a package or certify scientific, visual or listening review.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

from delivery_audit import checked_ref, integer, json_file, need, sha, string


def member_name(value):
    string(value, "MEMBER")
    part = PurePosixPath(value)
    need(not part.is_absolute() and part.as_posix() == value and bool(part.parts)
         and not any(p in (".", "..") for p in part.parts)
         and not any(c in value for c in "\\:\r\n\x00"), "MEMBER:UNSAFE_OR_NONCANONICAL")
    return value


def local_link(label, path):
    label = string(label, "LINK_LABEL")
    need(not any(c in label for c in "\r\n\x00"), "LINK_LABEL:CONTROL_CHARACTER")
    for char in "\\[]*_`":
        label = label.replace(char, "\\" + char)
    target = str(path)
    need(not any(c in target for c in "\r\n\x00"), "LINK_PATH:CONTROL_CHARACTER")
    for before, after in (("%", "%25"), ("<", "%3C"), (">", "%3E"), ("#", "%23"), ("?", "%3F")):
        target = target.replace(before, after)
    return f"[{label}](<{target}>)"


def verify_archive(spec, expected):
    path = checked_ref(spec["file"])
    prefix = spec.get("prefix", "")
    need(isinstance(prefix, str), "ZIP:PREFIX_REQUIRED")
    if prefix:
        need(prefix.endswith("/"), "ZIP:PREFIX_REQUIRES_TRAILING_SLASH")
        member_name(prefix[:-1])
    wanted = {prefix + key: value for key, value in expected.items()}
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [info.filename for info in entries]
        need(len(names) == len(set(names)), "ZIP:DUPLICATE_MEMBER")
        files = {}
        for info in entries:
            member_name(info.filename.rstrip("/") if info.is_dir() else info.filename)
            need(not info.flag_bits & 1 and not stat.S_ISLNK(info.external_attr >> 16), "ZIP:ENCRYPTED_OR_SYMLINK_MEMBER")
            if info.is_dir():
                need(any(name.startswith(info.filename) for name in wanted), "ZIP:UNDECLARED_DIRECTORY")
            else:
                files[info.filename] = info
        need(set(files) == set(wanted), "ZIP:MEMBER_SET_OR_PREFIX_MISMATCH")
        for name, ref in wanted.items():
            info = files[name]
            need(info.file_size == ref["bytes"], "ZIP:SIZE_MISMATCH:" + name)
            digest = hashlib.sha256()
            with archive.open(info) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)  # ZipExtFile also verifies CRC on full read.
            need(digest.hexdigest() == ref["sha256"], "ZIP:HASH_MISMATCH:" + name)
    return {"file": str(path), "sha256": sha(path), "members": len(wanted), "crc_checked": True}


def audit(contract):
    need(isinstance(contract, dict), "CONTRACT:OBJECT_REQUIRED")
    need(contract.get("schema") == "delivery-manifest-v1", "CONTRACT:SCHEMA_REQUIRED")
    need("require_sources" not in contract or type(contract["require_sources"]) is bool,
         "CONTRACT:REQUIRE_SOURCES_BOOLEAN")
    root = Path(string(contract.get("package_root"), "PACKAGE_ROOT"))
    need(root.is_absolute() and root.is_dir(), "PACKAGE_ROOT:ABSOLUTE_DIRECTORY_REQUIRED")
    manifest_path = checked_ref(contract["manifest"])
    manifest = json_file(manifest_path)
    need(isinstance(manifest, dict), "MANIFEST:OBJECT_REQUIRED")
    rows = manifest.get("files")
    need(isinstance(rows, list) and bool(rows), "MANIFEST:FILES_REQUIRED")
    field = contract.get("member_field", "package_path")
    need(field in ("package_path", "name", "path"), "MANIFEST:MEMBER_FIELD_UNSUPPORTED")
    expected, sources = {}, 0
    for row in rows:
        need(isinstance(row, dict), "MANIFEST:FILE_OBJECT_REQUIRED")
        name = member_name(row.get(field))
        need(name not in expected, "MANIFEST:DUPLICATE_MEMBER")
        path = root.joinpath(*PurePosixPath(name).parts)
        need(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), "MANIFEST:FILE_ESCAPES_PACKAGE")
        size = integer(row.get("bytes"), "MANIFEST_BYTES")
        pin = {"path": str(path), "sha256": row.get("sha256"), "bytes": size}
        checked_ref(pin)
        if "source" in row:
            checked_ref(row["source"])
            need(row["source"]["sha256"] == pin["sha256"], "MANIFEST:SOURCE_COPY_MISMATCH")
            sources += 1
        elif contract.get("require_sources") is True:
            raise ValueError("MANIFEST:SOURCE_REQUIRED")
        expected[name] = pin
    # Most final manifests exclude themselves. Include the exact manifest bytes
    # in directory/ZIP set comparison when it lives inside the delivery root.
    if manifest_path.resolve().is_relative_to(root.resolve()):
        name = manifest_path.resolve().relative_to(root.resolve()).as_posix()
        need(name not in expected, "MANIFEST:SELF_REFERENCE_NOT_SUPPORTED")
        expected[name] = {"path": str(manifest_path), "sha256": contract["manifest"]["sha256"],
                          "bytes": manifest_path.stat().st_size}
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() or p.is_symlink()}
    need(actual == set(expected), "PACKAGE:MEMBER_SET_MISMATCH")
    roles = contract.get("roles")
    need(isinstance(roles, list) and bool(roles), "ROLES:NONEMPTY_LIST_REQUIRED")
    links, seen = [], set()
    for role in roles:
        need(isinstance(role, dict), "ROLE:OBJECT_REQUIRED")
        identity = string(role.get("id"), "ROLE_ID")
        name = member_name(role.get("member"))
        need(identity not in seen and name in expected, "ROLE:DUPLICATE_OR_MISSING_MEMBER")
        seen.add(identity)
        suffixes = role.get("suffixes")
        need(isinstance(suffixes, list) and bool(suffixes) and all(
            isinstance(s, str) and s.startswith(".") and len(s) > 1 and not any(c in s for c in "/\\\r\n")
            for s in suffixes), "ROLE:EXPLICIT_SUFFIXES_REQUIRED")
        need(any(name.lower().endswith(s.lower()) for s in suffixes), "ROLE:WRONG_SUFFIX")
        pin = expected[name]
        links.append({"role": identity, **pin, "markdown": local_link(role.get("label"), pin["path"])})
    archive = verify_archive(contract["zip"], expected) if "zip" in contract else None
    return {"status": "PASS", "schema": "delivery-manifest-v1", "manifest": contract["manifest"],
            "files": len(rows), "source_mappings": sources, "zip": archive, "links": links,
            "markdown": "\n\n".join(row["markdown"] for row in links) + "\n",
            "semantic_visual_listening_review": "NOT_PERFORMED", "delivery_files_modified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--output")
    parser.add_argument("--markdown-output")
    args = parser.parse_args()
    try:
        contract = json_file(args.contract)
        result = audit(contract)
        destinations = [Path(x) for x in (args.output, args.markdown_output) if x]
        need(len({p.absolute() for p in destinations}) == len(destinations), "REPORT:DESTINATIONS_MUST_DIFFER")
        for dest in destinations:
            need(dest.is_absolute() and not dest.exists() and not dest.is_symlink()
                 and not dest.resolve().is_relative_to(Path(contract["package_root"]).resolve()),
                 "REPORT:NEW_ABSOLUTE_PATH_OUTSIDE_PACKAGE_REQUIRED")
        for path, value in ((args.output, json.dumps(result, ensure_ascii=False, indent=2) + "\n"),
                            (args.markdown_output, result["markdown"])):
            if path:
                with Path(path).open("x", encoding="utf-8") as stream:
                    stream.write(value)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc), "links": []}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
