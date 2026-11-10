#!/usr/bin/env python3
"""Exact offline preparation dispatch; all other events use the original NLM guard.

This file never starts the registered command and never performs network I/O.
The installation pins its registry. An offline registration grants no network
authority and cannot stand in for the SDK policy, route gate or budget admission.
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
import stat
import sys
import types

MAX_BYTES = 2 * 1024 * 1024
NETWORK_GUARD_SHA256 = {
    '19ddbe15e874c26375ba21558829d9239d582d87a5501acbc7ec2882ec6b981f',
    'cac540ae0d1b4e6ff6820f0b8855b41c1b7c4d30aae83c151252365f7fab568f',
}
EXECUTION = re.compile(r'bash|shell|exec|run_command|terminal|python|javascript|browser|navigate', re.I)


class Denied(ValueError):
    pass


def require(ok, reason):
    if not ok: raise Denied('NLM_NETWORK_GUARD_' + reason)


def file_ref(path):
    path = Path(path).resolve(strict=True)
    require(path.is_file() and path.stat().st_size <= MAX_BYTES, 'BOUNDED_REGULAR_FILE_REQUIRED')
    body = path.read_bytes()
    return {'path': str(path), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}, body


def pinned(ref):
    actual, body = file_ref(ref['path'])
    require(actual == ref, 'PIN_CHANGED')
    return body


def descriptor(value):
    require(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}
            and isinstance(value['path'], str) and Path(value['path']).is_absolute()
            and type(value['bytes']) is int and 0 <= value['bytes'] <= MAX_BYTES
            and isinstance(value['sha256'], str) and re.fullmatch('[a-f0-9]{64}', value['sha256']),
            'OFFLINE_EXACT_FILE_DESCRIPTOR_REQUIRED')


def validate_offline_preparation(item, *, check_files=True):
    """Installation and dispatch use the same bounded, offline-only validator."""
    fields = {'schema', 'id', 'action', 'argv', 'python', 'script', 'input', 'authorization',
              'input_schema', 'authorization_schema', 'root_session', 'dependencies', 'network'}
    require(type(item) is dict, 'OFFLINE_PREPARATION_OBJECT_REQUIRED')
    action = item.get('action')
    if action == 'maintenance-install': fields.add('plan_sha256')
    require(set(item) == fields and item['schema'] == 'nlm-offline-preparation-v1'
            and item['network'] == 'none' and action in {'static', 'prepare', 'maintenance-install'},
            'EXACT_OFFLINE_PREPARATION_SCHEMA_REQUIRED')
    require(isinstance(item['id'], str) and 0 < len(item['id']) <= 128, 'OFFLINE_ID_REQUIRED')
    require(all(isinstance(item[k], str) and bool(item[k]) for k in ('input_schema', 'authorization_schema', 'root_session')),
            'OFFLINE_EXACT_PRIVATE_SCHEMA_AND_ROOT_REQUIRED')
    for key in ('python', 'script', 'input', 'authorization'): descriptor(item[key])
    dependencies = item['dependencies']
    require(type(dependencies) is list and 1 <= len(dependencies) <= 4096, 'OFFLINE_PINNED_DEPENDENCIES_REQUIRED')
    for ref in dependencies: descriptor(ref)
    pins = [item[k] for k in ('python', 'script', 'input', 'authorization')] + dependencies
    known = {}
    for ref in pins:
        require(ref['path'] not in known or known[ref['path']] == ref, 'OFFLINE_CONFLICTING_DEPENDENCY_PIN')
        known[ref['path']] = ref
    argv = item['argv']
    require(type(argv) is list and all(type(x) is str and x for x in argv), 'OFFLINE_COMPLETE_ARGV_REQUIRED')
    require(all('$' not in x and '`' not in x and '\n' not in x and '\r' not in x for x in argv),
            'OFFLINE_LITERAL_ARGV_REQUIRED')
    prefix = [item['python']['path'], '-BE', item['script']['path']]
    if action in {'static', 'prepare'}:
        require(Path(item['script']['path']).name == 'root_prepare_once.py', 'OFFLINE_PREPARER_SCRIPT_REQUIRED')
        prefix += [action]
        accepted = [prefix, prefix + ['--input', item['input']['path']],
            prefix + ['--input', item['input']['path'], '--input-sha256', item['input']['sha256'],
                      '--self-sha256', item['script']['sha256'], '--apply']]
    else:
        require(Path(item['script']['path']).name == 'install_once.py'
                and isinstance(item['plan_sha256'], str) and re.fullmatch('[a-f0-9]{64}', item['plan_sha256']),
                'OFFLINE_EXACT_INSTALLER_PLAN_REQUIRED')
        accepted = [prefix + ['--input', item['input']['path']],
            prefix + ['--input', item['input']['path'], '--input-sha256', item['input']['sha256'],
                      '--self-sha256', item['script']['sha256'], '--plan-sha256', item['plan_sha256'], '--apply']]
    require(argv in accepted, 'OFFLINE_EXACT_ACTION_ARGUMENTS_REQUIRED')
    if not check_files: return
    bodies = {path: pinned(ref) for path, ref in known.items()}
    # Narrow known forbidden call sites supplement the pinned source review;
    # this is not a claim to prove arbitrary Python harmless by static analysis.
    tree = ast.parse(bodies[item['script']['path']], filename=item['script']['path'])
    prohibited = {'admit', 'run_bound', 'check_route', 'query', 'child_main', 'legacy_run'}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call): continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else None
        require(name not in prohibited, 'OFFLINE_NETWORK_OR_BUDGET_CALL_FORBIDDEN')
    supplied = json.loads(bodies[item['input']['path']])
    authority = json.loads(bodies[item['authorization']['path']])
    require(type(supplied) is dict and type(authority) is dict
            and supplied.get('schema') == item['input_schema']
            and authority.get('schema') == item['authorization_schema'],
            'OFFLINE_PINNED_INPUT_SCHEMAS_REQUIRED')
    require(supplied.get('authorization') == item['authorization'], 'OFFLINE_INPUT_AUTHORIZATION_CHANGED')
    if action in {'static', 'prepare'}:
        require(supplied.get('stage') == action and supplied.get('wrapper') == item['script'],
                'OFFLINE_PREPARATION_INPUT_CHANGED')
        require(authority.get('status') == 'AUTHORIZED_OFFLINE_PREPARATION'
                and authority.get('supervisor_session') == item['root_session']
                and authority.get('stage') == action and authority.get('wrapper') == item['script']
                and authority.get('network_calls_authorized') == 0
                and authority.get('budget_admission_authorized') is False
                and authority.get('runtime_execution_authorized') is False,
                'OFFLINE_PREPARATION_SCOPE_REQUIRED')
    else:
        require(supplied.get('wrapper') == item['script']
                and authority.get('status') == 'AUTHORIZED_ONE_LOCAL_INSTALL'
                and authority.get('root_session') == item['root_session']
                and authority.get('network_queries_authorized') == 0
                and authority.get('runtime_execution_authorized') is False
                and authority.get('approved_input') == {k: v for k, v in supplied.items() if k != 'authorization'},
                'OFFLINE_INSTALL_APPROVED_INPUT_REQUIRED')


def load_registry(path, sha256):
    ref, body = file_ref(path)
    require(ref['sha256'] == sha256, 'REGISTERED_DISPATCH_REGISTRY_CHANGED')
    registry = json.loads(body)
    require(type(registry) is dict and set(registry) == {'schema', 'network_guard', 'network_authority', 'offline_preparations'}
            and registry['schema'] == 'nlm-offline-preparation-dispatch-registry-v1', 'DISPATCH_REGISTRY_SCHEMA')
    descriptor(registry['network_guard'])
    require(registry['network_guard']['sha256'] in NETWORK_GUARD_SHA256, 'REVIEWED_NETWORK_GUARD_REQUIRED')
    authority = registry['network_authority']
    require(type(authority) is dict and set(authority) == {'kind', 'file'}
            and authority['kind'] in ('policy', 'registry'), 'EXACT_NETWORK_AUTHORITY_KIND_REQUIRED')
    descriptor(authority['file'])
    offline = registry.get('offline_preparations', [])
    require(type(offline) is list and len(offline) <= 32, 'BOUNDED_OFFLINE_REGISTRATIONS_REQUIRED')
    ids, commands = set(), set()
    for item in offline:
        validate_offline_preparation(item, check_files=False)
        command = tuple(item['argv'])
        require(item['id'] not in ids and command not in commands, 'OFFLINE_REGISTRATION_NOT_UNIQUE')
        ids.add(item['id']); commands.add(command)
    return ref, registry


def delegate_event(payload, registry):
    ref = registry['network_guard']; source = pinned(ref)
    require(ref['sha256'] in NETWORK_GUARD_SHA256, 'REVIEWED_NETWORK_GUARD_REQUIRED')
    guard = types.ModuleType('nlm_unchanged_network_guard_delegate'); guard.__file__ = ref['path']
    exec(compile(source, ref['path'], 'exec'), guard.__dict__)
    authority = registry['network_authority']; selected = authority['file']
    def loader():
        pinned(selected)
        method = guard.load_policy if authority['kind'] == 'policy' else guard.load_registry
        return method(selected['path'], selected['sha256'])
    return guard.event_check(payload, loader)


def load_authority(path):
    """A fixed installation-owned sidecar pins the replaceable outer registry.

    Maintainer updates are external to this guard. The sidecar deliberately has
    no command-line hash: hook command/trust stay stable when one exact offline
    input is registered. The sidecar still pins both dispatcher and registry.
    """
    source = Path(path)
    require(source.is_absolute() and str(source.resolve(strict=True)) == str(source), 'LITERAL_INSTALLED_AUTHORITY_PATH_REQUIRED')
    info = source.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o022,
            'INSTALLATION_OWNED_AUTHORITY_REQUIRED')
    _, raw = file_ref(source); authority = json.loads(raw)
    require(type(authority) is dict and set(authority) == {'schema', 'dispatcher', 'registry'}
            and authority['schema'] == 'nlm-offline-preparation-authority-v1', 'OFFLINE_AUTHORITY_SCHEMA')
    descriptor(authority['dispatcher']); descriptor(authority['registry'])
    require(authority['dispatcher'] == file_ref(__file__)[0], 'AUTHORITY_DISPATCHER_CHANGED')
    selected = authority['registry']
    actual_ref, registry = load_registry(selected['path'], selected['sha256'])
    require(actual_ref == selected, 'AUTHORITY_REGISTRY_CHANGED')
    return actual_ref, registry


def _argv(command):
    if not isinstance(command, str): return None
    lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|()<>\n')
    lexer.whitespace_split = True; lexer.whitespace = ' \t\r'; lexer.commenters = ''
    try:
        argv = list(lexer)
        if len(argv) >= 2 and Path(argv[0]).name == 'rtk' and argv[1] == 'proxy': argv = argv[2:]
        return argv
    except ValueError: return None


def exact_exec_wrapper(name, data):
    """Extract one complete, literal wrapper without evaluating JavaScript."""
    if name != 'functions.exec': return None
    code = data if isinstance(data, str) else data.get('code') if type(data) is dict and set(data) == {'code'} else None
    if not isinstance(code, str): return None
    match = re.fullmatch(r'\s*text\s*\(\s*await\s+tools\.exec_command\s*\(\s*(\{.*\})\s*\)\s*\)\s*;\s*', code, re.S)
    if not match: return None
    def unique_object(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj: raise ValueError('duplicate JSON key')
            obj[key] = value
        return obj
    def invalid_constant(_):
        raise ValueError('non-JSON constant')
    try:
        args = json.loads(match.group(1), object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except (ValueError, TypeError): return None
    if type(args) is not dict or 'cmd' not in args or not set(args) <= {'cmd', 'workdir', 'max_output_tokens', 'yield_time_ms'}:
        return None
    if type(args['cmd']) is not str or not args['cmd']: return None
    if 'workdir' in args and (type(args['workdir']) is not str or not args['workdir']): return None
    if any(type(args[key]) is not int or args[key] < 0 for key in ('max_output_tokens', 'yield_time_ms') if key in args):
        return None
    return args


def event_check(payload, registry_loader):
    require(isinstance(payload, dict), 'EVENT_OBJECT_REQUIRED')
    name = next((payload[k] for k in ('tool_name', 'toolName', 'tool', 'name') if payload.get(k)), '')
    data = next((payload[k] for k in ('tool_input', 'toolInput', 'input', 'arguments') if k in payload), {})
    inner = exact_exec_wrapper(name, data)
    if inner is not None:
        return event_check({'tool_name': 'exec_command', 'tool_input': inner,
                            'cwd': payload.get('cwd') or os.getcwd()}, registry_loader)
    if isinstance(name, str) and EXECUTION.search(name) and isinstance(data, dict):
        command = data.get('cmd') or data.get('command'); argv = _argv(command)
        candidates = {'root_prepare_once.py', 'install_once.py'}
        # These names do not get an allow here: the original guard still checks
        # their full syntax, including rg --pre, git flags and shell suffixes.
        original_read_commands = {'cat', 'head', 'tail', 'wc', 'ls', 'stat', 'shasum', 'sha256sum', 'rg', 'sed', 'git'}
        if argv and Path(argv[0]).name not in original_read_commands and any(Path(token).name in candidates for token in argv):
            _, registry = registry_loader()
            matched = [item for item in registry.get('offline_preparations', []) if item['argv'] == argv]
            if matched:
                require(len(matched) == 1, 'OFFLINE_REGISTRATION_NOT_UNIQUE')
                require('\n' not in command.strip() and '$' not in command and '`' not in command,
                        'OFFLINE_SHELL_COMPOSITION_FORBIDDEN')
                validate_offline_preparation(matched[0])
                return {'offline_preparation': matched[0]['id'], 'network': 'none'}
            cwd = data.get('workdir') or data.get('cwd') or payload.get('cwd') or os.getcwd()
            paths = {str((Path(token) if Path(token).is_absolute() else Path(cwd) / token).resolve()) for token in argv}
            require(not any(item['script']['path'] in paths for item in registry.get('offline_preparations', [])),
                    'UNREGISTERED_OFFLINE_PREPARATION_INVOCATION')
    # No monkey-patching or policy changes: network operations and all remaining
    # event types are checked by the exact original same-release implementation.
    _, registry = registry_loader()
    return delegate_event(payload, registry)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    choice = cli.add_mutually_exclusive_group(required=True)
    choice.add_argument('--authority'); choice.add_argument('--registry')
    cli.add_argument('--registry-sha256')
    args = cli.parse_args()
    def deadline(*_): raise Denied('NLM_NETWORK_GUARD_LOCAL_DEADLINE')
    signal.signal(signal.SIGALRM, deadline); signal.alarm(4)
    try:
        require((args.authority is not None and args.registry_sha256 is None)
                or (args.registry is not None and bool(args.registry_sha256)), 'EXACT_AUTHORITY_OR_DIAGNOSTIC_REGISTRY_REQUIRED')
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        require(len(raw) <= MAX_BYTES, 'EVENT_TOO_LARGE')
        loader = (lambda: load_authority(args.authority)) if args.authority else (lambda: load_registry(args.registry, args.registry_sha256))
        event_check(json.loads(raw), loader)
        print('{}', flush=True)
    except (ValueError, OSError, KeyError, TypeError, SyntaxError) as exc:
        reason = str(exc)
        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny', 'permissionDecisionReason': reason}}), flush=True)
        print(reason, file=sys.stderr, flush=True)
        return 2
    finally: signal.alarm(0)
    return 0


if __name__ == '__main__': raise SystemExit(main())
