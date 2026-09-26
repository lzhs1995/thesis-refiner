#!/usr/bin/env python3
"""Backed-up maintained-file overlay. No global hooks, application or account changes."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def reject_symlinks(path):
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise ValueError("SYMLINKED_INSTALL_PATH: " + str(part))


@contextmanager
def mutation_locks(*roots, enabled=True):
    """Serialize cooperating installers/writers; persistent lock files are never removed."""
    if not enabled:
        yield
        return
    try:
        import fcntl
    except ImportError as exc:
        raise RuntimeError("INSTALL_LOCK_REQUIRES_POSIX") from exc
    handles = []
    try:
        for root in sorted({Path(p).absolute() for p in roots if p is not None}):
            reject_symlinks(root)
            root.parent.mkdir(parents=True, exist_ok=True)
            lock = root.parent / ("." + root.name + ".thesis-refiner.lock")
            reject_symlinks(lock)
            fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BaseException as exc:
                os.close(fd)
                if isinstance(exc, BlockingIOError):
                    raise RuntimeError("INSTALL_ROOT_BUSY: " + str(root)) from exc
                raise
            handles.append(fd)
        yield
    finally:
        for fd in reversed(handles):
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


def replace_bytes(target, content, *, expected, conflict):
    """Caller holds mutation_locks; also detect noncooperating writes during staging."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".thesis-install-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        reject_symlinks(target)
        current = target.read_bytes() if target.exists() else None
        if current != expected:
            raise ValueError(conflict + ": " + str(target))
        os.replace(temporary, target)
        if target.read_bytes() != content:
            raise ValueError(conflict + ": " + str(target))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def maintained_files(root):
    paths = [root / "SKILL.md", root / "README.md"]
    for directory in ("scripts", "references", "hooks", "adapters", "schemas", "agents"):
        paths.extend(p for p in (root / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    return sorted(paths)


def install(canonical, codex_adapter=None, *, apply=False):
    reject_symlinks(Path(canonical).expanduser().absolute())
    canonical = Path(canonical).expanduser().resolve()
    if canonical == ROOT or canonical.is_relative_to(ROOT) or ROOT.is_relative_to(canonical):
        raise ValueError("SOURCE_AND_DESTINATION_MUST_DIFFER")
    if codex_adapter:
        reject_symlinks(Path(codex_adapter).expanduser().absolute())
    adapter = Path(codex_adapter).expanduser().resolve() if codex_adapter else None
    if adapter and (adapter == ROOT or adapter.is_relative_to(ROOT) or ROOT.is_relative_to(adapter)):
        raise ValueError("ADAPTER_AND_SOURCE_MUST_BE_SEPARATE")
    if adapter and (adapter == canonical or adapter.is_relative_to(canonical) or canonical.is_relative_to(adapter)):
        raise ValueError("ADAPTER_AND_CANONICAL_MUST_BE_SEPARATE")
    with mutation_locks(canonical, adapter, enabled=apply):
        return _install(canonical, adapter, apply=apply)


def _install(canonical, adapter, *, apply):
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
        reject_symlinks(target)
        if target.is_symlink():
            raise ValueError("SYMLINKED_MAINTAINED_FILE_REQUIRES_EXPLICIT_MIGRATION: " + str(target))
        old = target.read_bytes() if target.exists() else None
        records.append({"path": str(target), "backup": str(backup_root / relative) if old is not None else None,
                        "before_sha256": sha(old) if old is not None else None,
                        "after_sha256": sha(content), "changed": old != content})
    plan = {"schema_version": 2, "applied": apply, "canonical": str(canonical),
            "codex_adapter": str(adapter) if adapter else None, "backup_root": str(backup_root),
            "source": str(ROOT), "files": records, "global_hooks_changed": False,
            "concurrency_contract": "cooperating_writers_use_mutation_locks; staging_and_postwrite_byte_checks",
            "applications_restarted": False, "live_acceptance": "NOT_CLAIMED"}
    if not apply:
        return plan
    backup_root.mkdir(parents=True, exist_ok=False)
    (backup_root / "PLAN.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    try:
        for (target, content, _), record in zip(writes, records):
            reject_symlinks(target)
            old = target.read_bytes() if target.exists() else None
            if (sha(old) if old is not None else None) != record["before_sha256"]:
                raise RuntimeError("CONCURRENT_INSTALL_CHANGE: " + str(target))
            if not record["changed"]:
                continue
            if old is not None:
                backup = Path(record["backup"])
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_bytes(old)
            replace_bytes(target, content, expected=old, conflict="CONCURRENT_INSTALL_CHANGE")
            if sha(target.read_bytes()) != record["after_sha256"]:
                raise RuntimeError("INSTALLED_HASH_MISMATCH")
        for record in records:
            if not Path(record["path"]).is_file() or sha(Path(record["path"]).read_bytes()) != record["after_sha256"]:
                raise RuntimeError("CONCURRENT_INSTALL_CHANGE: " + record["path"])
        manifest = backup_root / "INSTALLED.json"
        manifest.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
        plan["manifest"] = str(manifest)
        return plan
    except BaseException as exc:
        (backup_root / "INCOMPLETE.json").write_text(json.dumps({"error": repr(exc), "plan": plan}, indent=2))
        # Keep exact backups and the partial-install journal; do not overwrite
        # files changed concurrently by a live writer during automatic rollback.
        raise


def rollback(manifest_path, *, apply=False):
    """Restore only a completed installation; reject drift before any writes."""
    manifest_path = Path(manifest_path).expanduser().resolve()
    plan = json.loads(manifest_path.read_text())
    if type(plan.get("schema_version")) is not int or plan["schema_version"] != 2 or plan.get("applied") is not True or manifest_path.name != "INSTALLED.json":
        raise ValueError("COMPLETED_V2_INSTALL_RECEIPT_REQUIRED")
    canonical = Path(plan["canonical"])
    adapter = Path(plan["codex_adapter"]) if plan.get("codex_adapter") else None
    if not canonical.is_absolute() or (adapter and not adapter.is_absolute()):
        raise ValueError("ABSOLUTE_INSTALL_ROOTS_REQUIRED")
    backup_root = Path(plan["backup_root"])
    if backup_root != manifest_path.parent or not backup_root.is_absolute():
        raise ValueError("BACKUP_ROOT_MISMATCH")
    with mutation_locks(canonical, adapter, enabled=apply):
        return _rollback(manifest_path, plan, canonical, adapter, backup_root, apply=apply)


def _rollback(manifest_path, plan, canonical, adapter, backup_root, *, apply):
    changes = []
    seen = set()
    if not isinstance(plan.get("files"), list) or not plan["files"]:
        raise ValueError("INSTALL_FILE_RECORDS_REQUIRED")
    for record in plan["files"]:
        if not isinstance(record, dict) or type(record.get("changed")) is not bool:
            raise ValueError("BOOLEAN_CHANGE_FLAG_REQUIRED")
        for name in ("before_sha256", "after_sha256"):
            value = record.get(name)
            if value is None and name == "before_sha256":
                continue
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError("INVALID_INSTALL_FILE_HASH")
        target = Path(record["path"])
        if not target.is_absolute() or ".." in target.parts or target in seen:
            raise ValueError("INVALID_ROLLBACK_TARGET")
        seen.add(target)
        if not target.is_relative_to(canonical) and not (adapter and target == adapter / "SKILL.md"):
            raise ValueError("ROLLBACK_TARGET_OUTSIDE_INSTALL")
        reject_symlinks(target)
        if record["changed"] is not True:
            continue
        current = target.read_bytes() if target.exists() else None
        if current is None or sha(current) != record["after_sha256"]:
            raise ValueError("ROLLBACK_CONCURRENT_CHANGE: " + str(target))
        old = None
        if record["before_sha256"] is not None:
            backup = Path(record["backup"])
            if not backup.is_absolute() or ".." in backup.parts or not backup.is_relative_to(backup_root):
                raise ValueError("BACKUP_OUTSIDE_INSTALL")
            reject_symlinks(backup)
            old = backup.read_bytes()
            if sha(old) != record["before_sha256"]:
                raise ValueError("BACKUP_HASH_MISMATCH")
        changes.append((target, current, old))
    result = {"schema_version": 1, "applied": apply, "installation": str(manifest_path),
              "installation_sha256": sha(manifest_path.read_bytes()),
              "files": [str(p) for p, _, _ in changes], "global_hooks_changed": False}
    if apply:
        restored = []
        try:
            for target, current, old in changes:
                reject_symlinks(target)
                if not target.exists() or target.read_bytes() != current:
                    raise ValueError("ROLLBACK_CONCURRENT_CHANGE: " + str(target))
                if old is None:
                    target.unlink()
                else:
                    replace_bytes(target, old, expected=current, conflict="ROLLBACK_CONCURRENT_CHANGE")
                restored.append(str(target))
            for target, _, old in changes:
                now = target.read_bytes() if target.exists() else None
                if now != old:
                    raise ValueError("ROLLBACK_CONCURRENT_CHANGE: " + str(target))
            result["restored"] = restored
            (backup_root / "ROLLED-BACK.json").write_text(json.dumps(result, indent=2) + "\n")
        except BaseException as exc:
            (backup_root / "ROLLBACK-INCOMPLETE.json").write_text(json.dumps({"error": repr(exc), "restored": restored}, indent=2))
            raise
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--canonical")
    mode.add_argument("--rollback", help="completed INSTALLED.json receipt; defaults to dry run")
    parser.add_argument("--codex-adapter")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.rollback and args.codex_adapter:
        parser.error("rollback uses the adapter pinned in its installation receipt")
    result = rollback(args.rollback, apply=args.apply) if args.rollback else install(args.canonical, args.codex_adapter, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
