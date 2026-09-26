#!/usr/bin/env python3
"""Backed-up maintained-file overlay. No global hooks, application or account changes."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def maintained_files(root):
    paths = [root / "SKILL.md", root / "README.md"]
    for directory in ("scripts", "references", "hooks", "adapters", "schemas", "agents"):
        paths.extend(p for p in (root / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    return sorted(paths)


def install(canonical, codex_adapter=None, *, apply=False):
    canonical = Path(canonical).expanduser().resolve()
    if canonical == ROOT:
        raise ValueError("SOURCE_AND_DESTINATION_MUST_DIFFER")
    adapter = Path(codex_adapter).expanduser().resolve() if codex_adapter else None
    if adapter and (adapter == canonical or adapter.is_relative_to(canonical) or canonical.is_relative_to(adapter)):
        raise ValueError("ADAPTER_AND_CANONICAL_MUST_BE_SEPARATE")
    writes = []
    for source in maintained_files(ROOT):
        relative = source.relative_to(ROOT)
        writes.append((canonical / relative, source.read_bytes(), str(relative)))
    if adapter:
        content = ("---\nname: thesis-refiner\ndescription: Use for 论文精炼助手 or empirical thesis refinement; route to the shared canonical skill.\n---\n\n"
                   "Read [the canonical skill](" + str(canonical / "SKILL.md") + ") before working.\n"
                   "All workflow scripts, NLM contracts and references live there. This adapter adds no separate completion rules.\n")
        writes.append((adapter / "SKILL.md", content.encode(), "codex-adapter/SKILL.md"))
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_root = canonical.parent / (canonical.name + ".backup-" + stamp)
    records = []
    for target, content, relative in writes:
        if target.is_symlink():
            raise ValueError("SYMLINKED_MAINTAINED_FILE_REQUIRES_EXPLICIT_MIGRATION: " + str(target))
        old = target.read_bytes() if target.exists() else None
        records.append({"path": str(target), "backup": str(backup_root / relative) if old is not None else None,
                        "before_sha256": sha(old) if old is not None else None,
                        "after_sha256": sha(content), "changed": old != content})
    plan = {"schema_version": 1, "applied": apply, "canonical": str(canonical),
            "source": str(ROOT), "files": records, "global_hooks_changed": False,
            "applications_restarted": False, "live_acceptance": "NOT_CLAIMED"}
    if not apply:
        return plan
    backup_root.mkdir(parents=True, exist_ok=False)
    (backup_root / "PLAN.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    try:
        for (target, content, _), record in zip(writes, records):
            old = target.read_bytes() if target.exists() else None
            if (sha(old) if old is not None else None) != record["before_sha256"]:
                raise RuntimeError("CONCURRENT_INSTALL_CHANGE: " + str(target))
            if not record["changed"]:
                continue
            if old is not None:
                backup = Path(record["backup"])
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_bytes(old)
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=".thesis-install-", dir=target.parent)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                current = target.read_bytes() if target.exists() else None
                if current != old:
                    raise RuntimeError("CONCURRENT_INSTALL_CHANGE: " + str(target))
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            if sha(target.read_bytes()) != record["after_sha256"]:
                raise RuntimeError("INSTALLED_HASH_MISMATCH")
        manifest = backup_root / "INSTALLED.json"
        manifest.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
        plan["manifest"] = str(manifest)
        return plan
    except BaseException as exc:
        (backup_root / "INCOMPLETE.json").write_text(json.dumps({"error": repr(exc), "plan": plan}, indent=2))
        # Keep exact backups and the partial-install journal; do not overwrite
        # files changed concurrently by a live writer during automatic rollback.
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", required=True)
    parser.add_argument("--codex-adapter")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(install(args.canonical, args.codex_adapter, apply=args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
