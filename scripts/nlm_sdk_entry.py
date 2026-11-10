#!/usr/bin/env python3
"""Explicit task preparation and single-process SDK queries via the original broker.

No credential writes, notebook/source creation, MCP switching, retries or
UNKNOWN settlement. One transport child handles exactly one query.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import ExitStack, closing, contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys
import threading
import time

SCRIPTS = Path(__file__).resolve().parent


def require(ok, message):
    if not ok:
        raise ValueError(message)


def ref(path):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def checked(value):
    require(ref(value['path']) == value, 'PIN_CHANGED:' + value['path'])
    return Path(value['path'])


def read(value):
    return json.loads(checked(value).read_text())


def freeze(path, value):
    path = Path(path)
    data = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == data, 'FROZEN_FILE_DIFFERS:' + str(path))
    else:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    return ref(path)


def actor_check(cfg):
    for variable, key in [('CODEX_THREAD_ID', 'thread_id'),
                          ('CMUX_WORKSPACE_ID', 'workspace_uuid'),
                          ('CMUX_SURFACE_ID', 'surface_uuid')]:
        require(bool(cfg['actor'].get(key)) and os.environ.get(variable) == cfg['actor'][key],
                'ACTUAL_TASK_EXECUTOR_REQUIRED:' + variable)


def validate_inputs(cfg):
    require(cfg['schema'] == 'nlm-sdk-task-v1', 'TASK_SCHEMA')
    for field in ('task_id', 'account_key', 'notebook_id', 'target_id', 'profile_name', 'email',
                  'proxy', 'budget_root', 'resource_root'):
        require(isinstance(cfg[field], str) and cfg[field].strip(), 'REQUIRED:' + field)
    require(cfg['provider'] in {'jacob', 'teng'}, 'EXPLICIT_PROVIDER_REQUIRED')
    require(type(cfg['query_budget']) is int and cfg['query_budget'] > 0, 'TASK_QUERY_BUDGET_REQUIRED')
    require(cfg['single_request_per_process'] is True, 'SINGLE_PROCESS_REQUEST_REQUIRED')
    require(threading.active_count() == 1, 'THREADED_SDK_ENTRY_FORBIDDEN')
    actor_check(cfg)
    checked(cfg['authorization'])
    checked(cfg['python'])
    require(Path(sys.executable).resolve() == checked(cfg['python']), 'PINNED_PYTHON_REQUIRED')
    require(sys.flags.ignore_environment and sys.dont_write_bytecode and not sys.flags.optimize,
            'PYTHON_BE_WITHOUT_OPTIMIZE_REQUIRED')
    source = read(cfg['source_binding'])
    require(source['notebook_id'] == cfg['notebook_id'] and source['source_ids'] == cfg['source_ids']
            and bool(cfg['source_ids']) and len(set(cfg['source_ids'])) == len(cfg['source_ids']),
            'EXPLICIT_SOURCE_BINDING_REQUIRED')
    require(source['acceptance'] == 'ACCEPTED_FOR_REQUEST_SCOPE' and bool(source['evidence']),
            'SOURCE_ACCEPTANCE_EVIDENCE_REQUIRED')
    checked(source['document'])
    for item in source['evidence']:
        checked(item)
    conversation = read(cfg['conversation_receipt'])
    require(conversation.get('status') == 'COMPLETE'
            and conversation.get('account_key') == cfg['account_key']
            and conversation.get('notebook_id') == cfg['notebook_id']
            and bool(cfg['conversation_id'])
            and conversation.get('conversation_id') == cfg['conversation_id'],
            'PREVIOUSLY_CONFIRMED_EXPLICIT_CONVERSATION_REQUIRED')
    if conversation.get('raw_answer'):
        require(ref(conversation['raw_answer']['path'])['sha256'] == conversation['raw_answer']['sha256'],
                'CONVERSATION_ORIGINAL_ANSWER_CHANGED')
    checked(cfg['broker_module'])
    return source


def sdk_preflight(cfg):
    manifest = read(cfg['sdk_manifest'])
    require(manifest['schema'] == 'nlm-sdk-environment-v1', 'COMPLETE_SDK_MANIFEST_REQUIRED')
    roots = [Path(p).resolve(strict=True) for p in manifest['import_roots']]
    require(all(p.is_dir() for p in roots), 'SDK_IMPORT_ROOT_REQUIRED')
    declared = set()
    for item in manifest['files']:
        path = checked(item)
        require(any(path.is_relative_to(root) for root in roots), 'SDK_FILE_OUTSIDE_IMPORT_ROOT')
        require(str(path) not in declared, 'DUPLICATE_SDK_FILE')
        declared.add(str(path))
    # Full immutable import trees: no silently added modules/dependency shadows.
    actual = {str(p.resolve()) for root in roots for p in root.rglob('*')
              if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    require(actual == declared, 'SDK_IMPORT_TREE_CHANGED')
    require(bool(manifest['sources']), 'SDK_PROVENANCE_REQUIRED')
    for source in manifest['sources']:
        checked(source['metadata'])
        require(source['version'] and source['upstream'], 'SDK_SOURCE_VERSION_REQUIRED')
    sys.path[:0] = [str(p) for p in roots]
    from importlib import metadata
    for package, version in manifest['versions'].items():
        require(metadata.version(package) == version, 'SDK_VERSION_CHANGED:' + package)
    from nlm_sdk_adapter_v3 import dependency_preflight
    return dependency_preflight({k: manifest['versions'][k] for k in ('h2', 'hpack', 'hyperframe')})


def request_input(path):
    request = json.loads(Path(path).read_text())
    require(set(request) == {'round_id', 'prompt', 'phase'}
            and isinstance(request['round_id'], str) and request['round_id'].strip()
            and isinstance(request['prompt'], str) and request['prompt'].strip()
            and request['phase'] in {'draft', 'final', 'recovery'},
            'ONLY_ROUND_PROMPT_PHASE_ALLOWED')
    return request


def queue_preflight(cfg):
    path = Path(cfg['resource_root']) / 'queue.sqlite3'
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        resource = db.execute('SELECT external_locks FROM resources WHERE name=?',
                              ('nlm-account:' + cfg['account_key'],)).fetchone()
    require(resource is not None and sorted(json.loads(resource[0])) == sorted(cfg['external_locks']),
            'EXISTING_ACCOUNT_RESOURCE_LOCKS_REQUIRED')
    with closing(sqlite3.connect((Path(cfg['budget_root']) / 'budget.sqlite3').as_uri() + '?mode=ro', uri=True)) as db:
        require(db.execute('SELECT 1 FROM accounts WHERE id=?', (cfg['account_key'],)).fetchone(),
                'EXISTING_ACCOUNT_POLICY_REQUIRED')


def prepare(config, output):
    cfg = json.loads(Path(config).read_text())
    validate_inputs(cfg)
    dependencies = sdk_preflight(cfg)
    queue_preflight(cfg)
    out = Path(output).resolve()
    require(not out.exists(), 'FRESH_TASK_DIRECTORY_REQUIRED')
    cfg['scripts'] = str(SCRIPTS)
    cfg['code_pins'] = [ref(p) for p in sorted(SCRIPTS.glob('*.py'))]
    cfg['prepared_from'] = ref(config)
    out.mkdir(parents=True)
    prepared = freeze(out / 'CONFIG.json', cfg)
    freeze(out / 'PREPARED.json', {'config': prepared, 'dependencies': dependencies,
        'native_actor_authentication': False, 'actor_check': 'actual caller environment; no root substitution',
        'no_network': True, 'budget_mutations': False, 'global_entry_changes': False})
    return prepared


def config_checked(path, expected=None):
    actual = ref(path)
    if expected:
        require(actual['sha256'] == expected, 'TASK_CONFIG_CHANGED')
    cfg = json.loads(Path(path).read_text())
    require(Path(cfg['scripts']).resolve() == SCRIPTS, 'ORIGINAL_RELEASE_REQUIRED')
    for item in cfg['code_pins']:
        checked(item)
    validate_inputs(cfg)
    sdk_preflight(cfg)
    queue_preflight(cfg)
    return cfg


@contextmanager
def locked(path):
    with Path(path).open('a+b') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def binding(cfg, path):
    path = Path(path).resolve()
    artifacts = [*cfg['code_pins'], cfg['python'], ref(path), cfg['sdk_manifest'],
                 cfg['source_binding'], cfg['conversation_receipt'], cfg['authorization']]
    return {'account_key': cfg['account_key'], 'notebook_id': cfg['notebook_id'],
        'target_id': cfg['target_id'] + ':' + cfg['provider'],
        'workspace_uuid': cfg['actor']['workspace_uuid'], 'surface_uuid': cfg['actor']['surface_uuid'],
        'existing_target_only': True, 'no_navigation': True, 'no_login': True,
        'no_default_write': True, 'no_browser_launch': True,
        'broker_module': cfg['broker_module'], 'resource_root': cfg['resource_root'],
        'external_locks': cfg['external_locks'], 'transport_artifacts': artifacts, 'lease_ttl': 360,
        'commands': {'query': [cfg['python']['path'], '-BE', str(Path(__file__).resolve()), 'transport',
            '--config', str(path), '--config-sha256', ref(path)['sha256'], '--output-dir', '{output_dir}']}}


def run(path, request_path):
    cfg = config_checked(path)
    source = read(cfg['source_binding'])
    request = request_input(request_path)
    request.update(task_id=cfg['task_id'], operation='query', source_ids=cfg['source_ids'],
        document_sha256=source['document']['sha256'], conversation_id=cfg['conversation_id'])
    import nlm_runtime as runtime
    # Cooperating task callers serialize admission. The shared broker still owns FIFO.
    with locked(Path(path).parent / 'submit.lock'):
        budget = runtime.Budget(cfg['budget_root'])
        row = budget.db.execute('SELECT query_budget FROM allocations WHERE account=? AND task_id=?',
                               (cfg['account_key'], cfg['task_id'])).fetchone()
        if row:
            require(row[0] == cfg['query_budget'], 'TASK_BUDGET_CHANGED')
        else:
            budget.allocate(cfg['account_key'], cfg['task_id'], cfg['query_budget'])
        try:
            result = runtime.run_bound(binding(cfg, path), request, budget)
            if result.get('cached'):
                receipt = result['receipt']
                require(ref(receipt['path'])['sha256'] == receipt['sha256'], 'CACHED_RECEIPT_CHANGED')
                result['status'] = json.loads(Path(receipt['path']).read_text())['status']
            return result
        finally:
            budget.db.close()


def transport(path, expected, output):
    cfg = config_checked(path, expected)
    out = Path(output).resolve()
    require(out.parent == Path(cfg['budget_root']).resolve() / 'receipts', 'ORIGINAL_RECEIPT_ROOT')
    request = json.loads((out / 'request.json').read_text())
    lease = json.loads((out / 'lease.json').read_text())
    require(request['task_id'] == cfg['task_id'] and request['operation'] == 'query'
            and request['account_key'] == cfg['account_key'] and request['notebook_id'] == cfg['notebook_id']
            and request['source_ids'] == cfg['source_ids'] and request['conversation_id'] == cfg['conversation_id'],
            'ORIGINAL_REQUEST_SCOPE_REQUIRED')
    with closing(sqlite3.connect((Path(cfg['resource_root']) / 'queue.sqlite3').as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        ticket = dict(db.execute('SELECT * FROM tickets WHERE id=?', (lease['id'],)).fetchone())
    require(ticket['status'] == 'ACTIVE' and ticket['token'] == lease['token']
            and ticket['task_id'] == cfg['task_id'] and ticket['resource'] == 'nlm-account:' + cfg['account_key']
            and ticket['pgid'] == os.getpgrp() and ticket['expires'] > time.time(), 'LIVE_ORIGINAL_BROKER_CHILD')
    with closing(sqlite3.connect((Path(cfg['budget_root']) / 'budget.sqlite3').as_uri() + '?mode=ro', uri=True)) as db:
        require(db.execute("SELECT 1 FROM requests WHERE id=? AND task_id=? AND state='STARTED'",
                           (out.name, cfg['task_id'])).fetchone(), 'ORIGINAL_BUDGET_ADMISSION')
    from nlm_sdk_adapter_v3 import BoundedHTTP, save, jacob_request, teng_request, parse_answer, validate_answer
    from notebooklm_tools.services.auth import AuthManager
    from notebooklm_tools.core.client import NotebookLMClient
    manager = AuthManager(cfg['profile_name'])
    before = [ref(manager.cookies_file), ref(manager.metadata_file)]
    record = {'provider': cfg['provider'], 'request_id': out.name, 'single_request_per_process': True,
              'native_actor_authentication': False, 'started_at': time.time(), 'auth_files_before': before}
    client = None
    code = 2
    def deadline(*_):
        raise TimeoutError('TOTAL_240_SECONDS')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(240)
    try:
        with ExitStack() as stack:
            for lock in cfg['external_locks']:
                stack.enter_context(locked(lock))
            profile = manager.load_profile()
            require(profile.email == cfg['email'] and profile.csrf_token and profile.session_id,
                    'BOUND_CACHED_ACCOUNT_AUTH_REQUIRED')
            client = NotebookLMClient(cookies=profile.cookies, csrf_token=profile.csrf_token,
                session_id=profile.session_id, build_label=profile.build_label,
                base_host=profile.base_host, profile_name=cfg['profile_name'], rpc_transport='http')
            def prohibited(*args, **kwargs):
                raise RuntimeError('NO_METADATA_RETRY_AUTH_REFRESH_OR_LOGIN')
            for method in ('_refresh_auth_tokens', '_try_reload_or_headless_auth', '_update_cached_tokens',
                           '_prepare_cdp_transport', '_call_rpc'):
                setattr(client, method, prohibited)
            require(threading.active_count() == 1, 'THREADED_JACOB_CAPTURE_FORBIDDEN')
            if cfg['provider'] == 'jacob':
                url, body, wire_id = jacob_request(client, cfg['notebook_id'], request['prompt'],
                                                   cfg['source_ids'], cfg['conversation_id'])
            else:
                url, body, wire_id = teng_request(profile, cfg['notebook_id'], request['prompt'],
                                                 cfg['source_ids'], cfg['conversation_id'])
            http = BoundedHTTP(out, proxy=cfg['proxy'], cookies=client._get_httpx_cookies(), total=240, idle=90)
            raw = asyncio.run(http.post('query', url, body))
            value = parse_answer(cfg['provider'], client, raw)
            # Always preserve a completed useful answer, including missing citations.
            save(out / 'PARSED-ANSWER.json', value)
            value.update(conversation_id=cfg['conversation_id'], notebook_id=cfg['notebook_id'],
                         request_conversation_id=wire_id, conversation_receipt=cfg['conversation_receipt'],
                         conversation_evidence='explicit previously confirmed persistent ID; no metadata POST')
            validate_answer(value, request)
            code = 0
    except BaseException as exc:
        value = {'status': 'UNCERTAIN', 'error_type': type(exc).__name__}
        record['error_type'] = type(exc).__name__
    finally:
        signal.alarm(0)
        if client:
            client.close()
        record['auth_files_after'] = [ref(manager.cookies_file), ref(manager.metadata_file)]
        record['auth_files_unchanged'] = before == record['auth_files_after']
        if not record['auth_files_unchanged']:
            code, value = 2, {'status': 'UNCERTAIN', 'error_type': 'AuthFilesChanged'}
        record.update(exit_code=code, ended_at=time.time())
        save(out / 'TRANSPORT.json', record)
    print(json.dumps(value, ensure_ascii=False))
    return code


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='mode', required=True)
    pre = sub.add_parser('prepare'); pre.add_argument('--config', required=True); pre.add_argument('--output-dir', required=True)
    call = sub.add_parser('run'); call.add_argument('--config', required=True); call.add_argument('--request', required=True)
    child = sub.add_parser('transport'); child.add_argument('--config', required=True); child.add_argument('--config-sha256', required=True); child.add_argument('--output-dir', required=True)
    a = p.parse_args()
    if a.mode == 'transport':
        return transport(a.config, a.config_sha256, a.output_dir)
    result = prepare(a.config, a.output_dir) if a.mode == 'prepare' else run(a.config, a.request)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if a.mode == 'prepare' or result.get('status') == 'COMPLETE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
