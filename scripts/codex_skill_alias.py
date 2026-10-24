#!/usr/bin/env python3
"""Preview or apply one exact-SHA Codex discovery alias; never copy a release."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("_thesis_alias_installer", ROOT / "scripts/install.py")
_installer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_installer)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def absolute(path):
    path = Path(path).expanduser()
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("ABSOLUTE_PATH_WITHOUT_TRAVERSAL_REQUIRED")
    return path


def snapshot(path):
    before = path.stat()
    content = path.read_bytes()
    after = path.stat()
    fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    if fields(before) != fields(after):
        raise ValueError("INPUT_CHANGED_DURING_READ")
    return dict(bytes=len(content), sha256=digest(content), device=before.st_dev,
                inode=before.st_ino, mtime_ns=before.st_mtime_ns)


def canonical_pin(path):
    logical = absolute(path)
    resolved = logical.resolve(strict=True)
    if logical.name != "SKILL.md" or not resolved.is_file():
        raise ValueError("CANONICAL_SKILL_FILE_REQUIRED")
    return dict(path=str(logical), resolved_path=str(resolved), **snapshot(resolved))


def content_for(canonical):
    return ("---\nname: thesis-refiner\ndescription: Use for 论文精炼助手 or empirical thesis refinement; route to the shared canonical skill.\n---\n\n"
            "Read [the canonical skill](" + str(canonical) + ") before working.\n"
            "All workflow scripts, NLM contracts and references live there. This adapter adds no separate completion rules.\n").encode()


def preview(canonical_skill, adapter_root, previous_sha256):
    canonical = canonical_pin(canonical_skill)
    adapter = absolute(adapter_root)
    _installer.reject_symlinks(adapter)
    target = adapter / "SKILL.md"
    resolved_source = Path(canonical["resolved_path"]).parent
    if (adapter == ROOT or adapter.is_relative_to(ROOT) or ROOT.is_relative_to(adapter)
            or adapter == resolved_source or adapter.is_relative_to(resolved_source)
            or resolved_source.is_relative_to(adapter)
            or target == Path(canonical["path"])):
        raise ValueError("ALIAS_MUST_BE_SEPARATE_FROM_SOURCE")
    before = snapshot(target) if target.exists() else None
    actual = before["sha256"] if before else "ABSENT"
    if actual != previous_sha256:
        raise ValueError("ALIAS_PREDECESSOR_SHA_MISMATCH")
    content = content_for(canonical["path"])
    return dict(schema="thesis-codex-alias-plan-v1", adapter_root=str(adapter),
                target=str(target), canonical=canonical, before=before,
                previous_sha256=previous_sha256, content_utf8=content.decode(),
                after_sha256=digest(content), after_bytes=len(content),
                changed=before is None or before["sha256"] != digest(content),
                release_files_copied=0, global_hooks_changed=False,
                applications_restarted=False, in_flight_tasks_migrated=False,
                complete_release_verification="Separate caller requirement",
                contract="New-task discovery alias only; settle tasks pinning this alias before apply")


def create_exact(path, content):
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def apply(plan_path, plan_sha256, journal_directory):
    plan_path = absolute(plan_path)
    raw = plan_path.read_bytes()
    if digest(raw) != plan_sha256:
        raise ValueError("PLAN_SHA_MISMATCH")
    plan = json.loads(raw)
    if plan.get("schema") != "thesis-codex-alias-plan-v1":
        raise ValueError("ALIAS_PLAN_REQUIRED")
    adapter = absolute(plan["adapter_root"])
    journal = absolute(journal_directory)
    _installer.reject_symlinks(journal)
    for source in (ROOT, Path(plan["canonical"]["resolved_path"]).parent, adapter):
        if journal == source or journal.is_relative_to(source) or source.is_relative_to(journal):
            raise ValueError("JOURNAL_MUST_BE_SEPARATE")
    with _installer.mutation_locks(adapter):
        fresh = preview(plan["canonical"]["path"], adapter, plan["previous_sha256"])
        if fresh != plan:
            raise ValueError("ALIAS_PLAN_INPUT_CHANGED")
        if not plan["changed"]:
            return dict(applied=False, changed=False, plan_sha256=plan_sha256,
                        target=plan["target"], after_sha256=plan["after_sha256"])
        target = Path(plan["target"])
        before = target.read_bytes() if target.exists() else None
        content = plan["content_utf8"].encode()
        journal.mkdir(parents=True, exist_ok=False)
        create_exact(journal / "PLAN.json", raw)
        if before is not None:
            create_exact(journal / "BEFORE.md", before)
        sync_directory(journal)
        try:
            # Both cooperating installer exclusion and byte CAS remain in effect.
            if canonical_pin(plan["canonical"]["path"]) != plan["canonical"]:
                raise ValueError("CANONICAL_CHANGED_BEFORE_COMMIT")
            _installer.replace_bytes(target, content, expected=before,
                                     conflict="ALIAS_CONCURRENT_CHANGE")
            sync_directory(target.parent)
            if canonical_pin(plan["canonical"]["path"]) != plan["canonical"]:
                raise ValueError("CANONICAL_CHANGED_AFTER_COMMIT")
            if target.read_bytes() != content:
                raise ValueError("ALIAS_CONCURRENT_CHANGE")
            result = dict(applied=True, changed=True, target=str(target),
                          plan_sha256=plan_sha256, after_sha256=digest(content),
                          backup=str(journal / "BEFORE.md") if before is not None else None,
                          outcome="COMMITTED", global_hooks_changed=False,
                          release_files_copied=0, applications_restarted=False,
                          in_flight_tasks_migrated=False, runtime_adoption="NOT_CLAIMED")
            create_exact(journal / "RESULT.json", (json.dumps(result, indent=2) + "\n").encode())
            sync_directory(journal)
            return result
        except BaseException as exc:
            current = target.read_bytes() if target.exists() else None
            outcome = ("COMMITTED_POSTCHECK_UNKNOWN" if current == content else
                       "NO_ALIAS_CHANGE" if current == before else "CONCURRENT_TARGET_CHANGE")
            diagnostic = dict(error=repr(exc), outcome=outcome, plan_sha256=plan_sha256,
                              current_sha256=digest(current) if current is not None else None,
                              automatic_rollback=False, automatic_retry=False)
            create_exact(journal / "INCOMPLETE.json", (json.dumps(diagnostic, indent=2) + "\n").encode())
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("preview")
    plan.add_argument("--canonical-skill", required=True)
    plan.add_argument("--adapter-root", required=True)
    plan.add_argument("--previous-sha256", required=True, help="exact current SHA256, or ABSENT for a fresh alias")
    install = commands.add_parser("apply")
    install.add_argument("--plan", required=True)
    install.add_argument("--plan-sha256", required=True)
    install.add_argument("--journal-directory", required=True)
    args = parser.parse_args()
    result = (preview(args.canonical_skill, args.adapter_root, args.previous_sha256)
              if args.command == "preview" else apply(args.plan, args.plan_sha256, args.journal_directory))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

