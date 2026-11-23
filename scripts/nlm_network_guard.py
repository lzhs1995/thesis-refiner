#!/usr/bin/env python3
"""PreToolUse guard: only an administrator-pinned NLM entry may use the network.

The hook does no network I/O. The admitted entry repeats its live route gate
before preparation, admission and send. This is a tool boundary, not an OS
firewall or a proof about arbitrary opaque programs already running elsewhere.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import sys

MAX_BYTES = 2 * 1024 * 1024
NLM = re.compile(r'notebook[._-]?lm|notebook(?:lm)?\.google\.com|gemini.notebook|'
                 r'(?<![a-z0-9])nlm(?:[^a-z0-9]|$)', re.I)
EXECUTION = re.compile(r'bash|shell|exec|run_command|terminal|python|javascript|browser|navigate', re.I)
READ_TOOLS = {'read', 'read_file', 'read_text_file', 'view_image', 'glob', 'grep', 'search',
              'apply_patch', 'write', 'edit', 'write_file', 'edit_file', 'multi_edit', 'multiedit', 'tool_search'}


class Denied(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise Denied('NLM_NETWORK_GUARD_' + reason)


def file_ref(path):
    path = Path(path).resolve(strict=True)
    require(path.is_file() and path.stat().st_size <= MAX_BYTES, 'BOUNDED_REGULAR_FILE_REQUIRED')
    body = path.read_bytes()
    return dict(path=str(path), bytes=len(body), sha256=hashlib.sha256(body).hexdigest()), body


def pinned(value):
    actual, body = file_ref(value['path'])
    require(actual == value, 'PIN_CHANGED')
    return body


def load_policy(path, sha256):
    ref, body = file_ref(path)
    require(ref['sha256'] == sha256, 'REGISTERED_POLICY_CHANGED')
    policy = json.loads(body)
    require(policy['schema'] == 'nlm-network-policy-v1'
            and policy['policy_role'] == 'mandatory-domain-route'
            and bool(policy['required_route_label']), 'POLICY_SCHEMA')
    # Labels explain the machine rule; the exact route object supplies authority.
    pinned(policy['route_binding'])
    for item in [policy['entry'], policy['python'], *policy['code_pins']]:
        pinned(item)
    scripts = Path(policy['entry']['path']).parent
    require({v['path'] for v in policy['code_pins']}
            == {str(p.resolve()) for p in scripts.glob('*.py')}, 'COMPLETE_ENTRY_CODE_PINS_REQUIRED')
    return ref, policy


def strip_wrappers(argv):
    argv = list(argv)
    if len(argv) >= 2 and Path(argv[0]).name == 'rtk' and argv[1] == 'proxy':
        argv = argv[2:]
    # Environment overrides can replace a policy, import root, proxy or actor.
    # Do not guess which ones a caller intended to be harmless.
    return argv


def read_only(argv):
    if not argv:
        return True
    cmd = Path(argv[0]).name
    if cmd in {'cat', 'head', 'tail', 'wc', 'ls', 'stat', 'shasum', 'sha256sum'}:
        return not any('$' in v or '`' in v for v in argv)
    if cmd == 'rg':
        return not any(v.startswith(('--pre', '--hostname-bin')) for v in argv)
    if cmd == 'sed':
        # Only the common, non-executing line-range read used for code review.
        return len(argv) >= 4 and argv[1] == '-n' and bool(re.fullmatch(r'\d+(?:,\d+)?p', argv[2]))
    if cmd == 'git':
        # Disable external diff/textconv and do not accept -c/alias indirection.
        return (len(argv) >= 2 and argv[1] in {'status', 'log', 'rev-parse'}
                and not any(v.startswith(('--exec-path', '--config-env', '--ext-diff')) for v in argv))
    return False


def executable_mentions(argv, cwd, depth=0, seen=None):
    """Inspect bounded local wrapper sources without importing/executing them."""
    seen = set() if seen is None else seen
    if depth > 5:
        return True  # A nested executable chain that cannot be resolved is unproved.
    for token in argv:
        if NLM.search(token):
            return True
        path = Path(token)
        if not path.is_absolute():
            path = Path(cwd) / path
        candidate = (path.suffix.lower() in {'.py', '.sh', '.js', '.mjs', '.cjs', '.ts'}
                     or token == argv[0] or (argv and re.match(r'python[\d.]*$', Path(argv[0]).name)))
        if not candidate or not path.is_file():
            continue
        path = path.resolve()
        if path in seen:
            continue
        seen.add(path)
        if path.stat().st_size > MAX_BYTES:
            continue  # Not an assertion that arbitrary opaque code is safe.
        text = path.read_text(errors='replace')
        if NLM.search(text):
            return True
        # Follow literal wrapper source paths, including subprocess/runpy scripts.
        literals = re.findall(r'''["']([^"'\n]+\.(?:py|sh|js|mjs|cjs|ts))["']''', text)
        if executable_mentions(literals, path.parent, depth + 1, seen):
            return True
    return False


def approved_entry(argv, policy_ref, policy, cwd):
    require(len(argv) >= 7, 'EXACT_ENTRY_COMMAND_REQUIRED')
    require(str(Path(argv[0]).resolve()) == policy['python']['path'] and argv[1] == '-BE'
            and str(Path(argv[2]).resolve()) == policy['entry']['path'], 'PINNED_ENTRY_REQUIRED')
    mode = argv[3]
    require(mode in {'prepare', 'run'}, 'DIRECT_TRANSPORT_OR_UNKNOWN_MODE_FORBIDDEN')
    flags = {'--config', '--output-dir'} if mode == 'prepare' else {'--config', '--request'}
    require(len(argv) == 8 and set(argv[4::2]) == flags and len(set(argv[4::2])) == 2,
            'EXACT_ENTRY_ARGUMENTS_REQUIRED')
    args = dict(zip(argv[4::2], argv[5::2]))
    require(all(Path(v).is_absolute() and '$' not in v and '`' not in v for v in args.values()),
            'LITERAL_ABSOLUTE_ARGUMENTS_REQUIRED')
    _, body = file_ref(args['--config'])
    cfg = json.loads(body)
    require(cfg.get('route_policy') == policy_ref, 'TASK_NOT_BOUND_TO_REGISTERED_POLICY')
    require(cfg.get('route_binding') == policy['route_binding'] and cfg.get('python') == policy['python'],
            'TASK_ROUTE_OR_PYTHON_NOT_APPROVED')
    route = json.loads(pinned(policy['route_binding']))
    require(cfg.get('proxy') == route['proxy'], 'TASK_PROXY_NOT_APPROVED')
    if mode == 'run':
        require(cfg.get('code_pins') == policy['code_pins']
                and cfg.get('scripts') == str(Path(policy['entry']['path']).parent), 'PREPARED_ENTRY_CHANGED')
    # The entry checks actor/account/source/queue, and obtains fresh live route
    # evidence. The hook must not spend query budget or use historic TLS as PASS.


def shell_command(command, policy_loader, cwd, depth=0):
    require(depth <= 6, 'SHELL_NESTING_UNRESOLVED')
    lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|()<>\n')
    lexer.whitespace_split = True
    lexer.whitespace = ' \t\r'
    # Keep comment text in the conservative token view; shlex otherwise consumes
    # its terminating newline and could hide a following command behind `cat`.
    lexer.commenters = ''
    try:
        tokens = list(lexer)
    except ValueError:
        require(not NLM.search(command), 'NLM_SHELL_SYNTAX_UNRESOLVED')
        return
    chunks, current = [], []
    for token in tokens:
        if token and set(token) <= set(';&|()\n'):
            if current:
                chunks.append(current); current = []
        else:
            current.append(token)
    if current:
        chunks.append(current)
    # A command substitution/redirect can mutate input between verification and
    # execution. Never approve an NLM entry in compound or expanded shell text.
    for chunk in chunks:
        argv = strip_wrappers(chunk)
        if not argv:
            continue
        if Path(argv[0]).name in {'sh', 'bash', 'zsh'} and len(argv) == 3 and argv[1] in {'-c', '-lc'}:
            require(not executable_mentions(argv, cwd) or (len(chunks) == 1
                    and '$' not in command and '`' not in command), 'NLM_SHELL_COMPOSITION_FORBIDDEN')
            shell_command(argv[2], policy_loader, cwd, depth + 1)
            continue
        if Path(argv[0]).name in {'env', 'sudo', 'command', 'nohup', 'timeout'}:
            require(not executable_mentions(argv, cwd), 'UNAPPROVED_NLM_WRAPPER')
        if read_only(argv) and not any(v in {'>', '>>', '<', '<<'} or '$' in v or '`' in v for v in argv):
            continue
        if not executable_mentions(argv, cwd):
            continue
        require(len(chunks) == 1 and '\n' not in command.strip() and '$' not in command and '`' not in command
                and not any(v in {'>', '>>', '<', '<<'} for v in argv), 'NLM_SHELL_COMPOSITION_FORBIDDEN')
        policy_ref, policy = policy_loader()
        offline = [item for item in policy.get('offline_commands', []) if item.get('argv') == argv]
        if offline:
            require(len(offline) == 1 and offline[0].get('network') == 'none'
                    and bool(offline[0].get('files')), 'REVIEWED_OFFLINE_COMMAND_REQUIRED')
            for item in offline[0]['files']:
                pinned(item)
            return
        approved_entry(argv, policy_ref, policy, cwd)


def event_check(payload, policy_loader):
    require(isinstance(payload, dict), 'EVENT_OBJECT_REQUIRED')
    name = next((payload[k] for k in ('tool_name', 'toolName', 'tool', 'name') if payload.get(k)), '')
    require(isinstance(name, str) and bool(name), 'TOOL_NAME_REQUIRED')
    data = next((payload[k] for k in ('tool_input', 'toolInput', 'input', 'arguments') if k in payload), {})
    short = re.split(r'[.:/]', name.lower())[-1]
    if short in READ_TOOLS:
        return
    if NLM.search(name):
        raise Denied('NLM_NETWORK_GUARD_DIRECT_MCP_OR_UNBOUND_TOOL_FORBIDDEN')
    if not EXECUTION.search(name):
        # Explicit target URLs also cover browser/fetch tools with generic names.
        require(not re.search(r'https?://notebook(?:lm)?\.google\.com', json.dumps(data), re.I),
                'UNBOUND_NLM_DESTINATION')
        return
    cwd = payload.get('cwd') or os.getcwd()
    if isinstance(data, dict):
        cwd = data.get('workdir') or data.get('cwd') or cwd
        command = data.get('cmd') or data.get('command')
        code = data.get('code') or data.get('source')
        if isinstance(command, str):
            shell_command(command, policy_loader, cwd)
            return
    else:
        code = data if isinstance(data, str) else None
    if not isinstance(code, str):
        require(not NLM.search(json.dumps(data)), 'EXECUTION_PAYLOAD_UNRESOLVED')
        return
    # functions.exec carries JS orchestration, including literal nested cmd
    # strings. Extract only strings; never eval the surrounding program.
    pattern = r'''(?:["']?(?:cmd|command)["']?)\s*:\s*("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')'''
    matches = list(re.finditer(pattern, code))
    rest = code
    for match in reversed(matches):
        literal = match.group(1)
        try:
            command = json.loads(literal) if literal.startswith('"') else ast.literal_eval(literal)
        except (ValueError, SyntaxError):
            raise Denied('NLM_NETWORK_GUARD_EXEC_STRING_UNRESOLVED')
        # Capture a literal workdir/cwd in the same simple exec argument object.
        # Unknown computed directories are never authority for relative entries.
        start = code.rfind('{', 0, match.start())
        end = code.find('}', match.end())
        obj = code[start:end] if start >= 0 and end >= 0 else ''
        workdir = re.search(r'''["']?(?:workdir|cwd)["']?\s*:\s*("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')''', obj)
        command_cwd = cwd
        if workdir:
            value=workdir.group(1)
            command_cwd=json.loads(value) if value.startswith('"') else ast.literal_eval(value)
        shell_command(command, policy_loader, command_cwd)
        rest = rest[:match.start()] + 'cmd: "checked"' + rest[match.end():]
    require(not NLM.search(rest), 'NLM_DYNAMIC_EXEC_OR_DIRECT_SDK_FORBIDDEN')
    literals = re.findall(r'''["']([^"'\n]+\.(?:py|sh|js|mjs|cjs|ts))["']''', rest)
    require(not executable_mentions(literals, cwd), 'NLM_DYNAMIC_WRAPPER_FORBIDDEN')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', required=True)
    parser.add_argument('--policy-sha256', required=True)
    args = parser.parse_args()
    def deadline(*_):
        raise Denied('NLM_NETWORK_GUARD_LOCAL_DEADLINE')
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, 4)
    try:
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        require(len(raw) <= MAX_BYTES, 'EVENT_TOO_LARGE')
        payload = json.loads(raw)
        event_check(payload, lambda: load_policy(args.policy, args.policy_sha256))
        print('{}')
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        # No raw payloads, source text, route credentials or arbitrary exception
        # messages are copied to the user-facing decision.
        reason = str(exc) if isinstance(exc, Denied) else 'NLM_NETWORK_GUARD_INVALID_OR_UNREADABLE_BINDING'
        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny', 'permissionDecisionReason': reason}}))
        print(reason, file=sys.stderr)
        return 2
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__':
    raise SystemExit(main())
