#!/usr/bin/env python3
"""Read hook registrations and probe this skill's entrypoint; never edit client config."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def commands(value):
    if isinstance(value, dict):
        if isinstance(value.get("command"), str):
            yield value["command"]
        for key, nested in value.items():
            if key != "command":
                yield from commands(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from commands(nested)


def inspect_config(path, *, active):
    """Only read the hooks subtree; never echo other config (tokens, env, etc.)."""
    path = Path(path).expanduser().resolve()
    report = {"path": str(path), "declared_active_config": active, "exists": path.is_file(), "registrations": []}
    if not path.is_file():
        return report
    raw = path.read_bytes()
    report["sha256"] = hashlib.sha256(raw).hexdigest()
    obj = json.loads(raw)
    for command in commands(obj.get("hooks", {})):
        if not any(x in command for x in ("thesis-refiner", "论文精炼助手", "a5-termination-auditor")):
            continue
        row = {"command": command, "resolved_hook": None, "exists": False}
        if "$env:" in command or "\\" in command:
            row["resolution"] = "WINDOWS_SYNTAX_UNRESOLVED_ON_POSIX" if os.name != "nt" else "REQUIRES_NATIVE_SHELL_RESOLUTION"
        else:
            try:
                tokens = shlex.split(command)
                candidates = [v for v in tokens if v.endswith("a5-termination-auditor.js")]
                if len(candidates) == 1:
                    target = Path(os.path.expandvars(candidates[0])).expanduser()
                    if target.is_absolute():
                        row.update(resolved_hook=str(target), exists=target.is_file(), resolution="ABSOLUTE_PATH")
                    else:
                        row["resolution"] = "CWD_DEPENDENT_PATH"
                else:
                    row["resolution"] = "OTHER_LEGACY_HOOK"
            except ValueError:
                row["resolution"] = "MALFORMED_COMMAND"
        report["registrations"].append(row)
    return report


def doctor(root=ROOT, configs=(), legacy_configs=()):
    root = Path(root).resolve()
    hook = root / "hooks/a5-termination-auditor.js"
    report = {"schema_version": 1, "skill_root": str(root), "installed": hook.is_file(),
              "client_invocation": "NOT_MEASURED", "client_reload": "NOT_MEASURED",
              "configs": [inspect_config(p, active=True) for p in configs] +
                         [inspect_config(p, active=False) for p in legacy_configs],
              "entrypoint_probes": [], "global_hooks_changed": False}
    env = os.environ.copy()
    for name in ("THESIS_REFINER_CHECKPOINT", "THESIS_REFINER_DELIVERY_CHECKPOINT", "THESIS_REFINER_ROOT"):
        env.pop(name, None)
    env["THESIS_PYTHON"] = sys.executable
    if hook.is_file():
        report["hook_sha256"] = hashlib.sha256(hook.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            cases = [("unbound_passthrough", {"task": "unrelated"}, 0),
                     ("missing_bound_checkpoint", {"workflow_checkpoint": str(Path(tmp) / "missing.json")}, 2)]
            for name, value, expected in cases:
                payload = json.dumps(value)
                try:
                    result = subprocess.run(["node", str(hook)], input=payload, text=True, capture_output=True, env=env, timeout=65)
                    passed = result.returncode == expected and (name != "unbound_passthrough" or result.stdout == payload)
                    report["entrypoint_probes"].append({"name": name, "exit_code": result.returncode, "pass": passed})
                except (OSError, subprocess.TimeoutExpired) as exc:
                    report["entrypoint_probes"].append({"name": name, "pass": False, "error": type(exc).__name__})
    active_rows = [r for c in report["configs"] if c["declared_active_config"] for r in c["registrations"]]
    report["canonical_registration_found"] = any(r["resolved_hook"] and Path(r["resolved_hook"]).resolve() == hook for r in active_rows)
    report["entrypoint_pass"] = len(report["entrypoint_probes"]) == 2 and all(r["pass"] for r in report["entrypoint_probes"])
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--config", action="append", default=[], help="actual client config, explicit; repeatable")
    p.add_argument("--legacy-config", action="append", default=[])
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    result = doctor(a.root, a.config, a.legacy_config)
    raw = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if a.output:
        if not a.output.is_absolute() or a.output.exists():
            p.error("output must be a new absolute path; existing configs/evidence are not overwritten")
        with a.output.open("x") as f:
            f.write(raw)
    print(raw, end="")
    return 0 if result["entrypoint_pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
