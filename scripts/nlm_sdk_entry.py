#!/usr/bin/env python3
"""Explicit task preparation and single-process SDK queries via the original broker.

No credential writes, notebook/source creation, MCP switching, retries or
UNKNOWN settlement. One transport child handles exactly one query.
"""
from __future__ import annotations

import argparse
import base64
import asyncio
from contextlib import ExitStack, closing, contextmanager
import fcntl
import hashlib
import importlib.abc
import importlib.machinery
import json
import locale
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import types

SCRIPTS = Path(__file__).resolve().parent
PREFLIGHT_SECONDS = 30
CHILD_SECONDS = 240
CLEANUP_SECONDS = 5
DRAIN_SECONDS = 5


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
    require(sys.version_info >= (3, 11), 'SDK_ENTRY_REQUIRES_PYTHON_3_11')
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


def verify_sdk_tree(cfg):
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
    # -B prevents writes, not reads. Never accept an unrecorded cache, even an
    # empty cache directory; do not delete it to make validation pass.
    members = [p for root in roots for p in root.rglob('*')]
    require(not any(p.name == '__pycache__' or p.suffix in {'.pyc', '.pyo'}
                    for p in members), 'SDK_BYTECODE_CACHE_FORBIDDEN')
    actual = {str(p.resolve()) for p in members if p.is_file()}
    require(actual == declared, 'SDK_IMPORT_TREE_CHANGED')
    require(bool(manifest['sources']), 'SDK_PROVENANCE_REQUIRED')
    for source in manifest['sources']:
        checked(source['metadata'])
        require(source['version'] and source['upstream'], 'SDK_SOURCE_VERSION_REQUIRED')
    return manifest, roots


class PinnedSourceLoader(importlib.machinery.SourceFileLoader):
    def __init__(self, fullname, value):
        super().__init__(fullname, value['path'])
        self.value = value

    def get_code(self, fullname):
        # Compile the checked source directly. SourceFileLoader's default
        # get_code can read a new valid pyc added after the tree preflight.
        body = checked(self.value).read_bytes()
        require(len(body) == self.value['bytes']
                and hashlib.sha256(body).hexdigest() == self.value['sha256'],
                'SDK_SOURCE_CHANGED_DURING_LOAD')
        return self.source_to_code(body, self.value['path'])


class PinnedImportFinder(importlib.abc.MetaPathFinder):
    def __init__(self, roots, files):
        self.roots = tuple(Path(root).resolve() for root in roots)
        self.files = {item['path']: item for item in files}

    def find_spec(self, fullname, path=None, target=None):
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if not spec or not spec.origin or spec.origin in {'built-in', 'frozen'}:
            return None
        origin = Path(spec.origin).resolve()
        if not any(origin.is_relative_to(root) for root in self.roots):
            return None
        require(origin.suffix not in {'.pyc', '.pyo'} and '__pycache__' not in origin.parts,
                'SDK_BYTECODE_IMPORT_FORBIDDEN')
        require(str(origin) in self.files, 'UNPINNED_IMPORT_FORBIDDEN:' + str(origin))
        value = self.files[str(origin)]
        checked(value)
        if origin.suffix == '.py':
            spec.loader = PinnedSourceLoader(fullname, value)
            spec.cached = None
        return spec


def source_guard(roots, files):
    for old in list(sys.meta_path):
        if isinstance(old, PinnedImportFinder):
            require(old.roots == tuple(roots) and old.files == {v['path']: v for v in files},
                    'IMPORT_BINDING_CHANGED_IN_PROCESS')
            return
    sys.meta_path.insert(0, PinnedImportFinder(roots, files))


def sdk_preflight(cfg):
    manifest, roots = verify_sdk_tree(cfg)
    script_members = list(SCRIPTS.rglob('*'))
    require(not any(p.name == '__pycache__' or p.suffix in {'.pyc', '.pyo'}
                    for p in script_members), 'ENTRY_BYTECODE_CACHE_FORBIDDEN')
    script_pins = cfg.get('code_pins') or [ref(p) for p in sorted(SCRIPTS.glob('*.py'))]
    source_guard([SCRIPTS, *roots], [*script_pins, *manifest['files']])
    sys.path[:0] = [str(p) for p in roots]
    from importlib import metadata
    for package, version in manifest['versions'].items():
        require(metadata.version(package) == version, 'SDK_VERSION_CHANGED:' + package)
    from nlm_sdk_adapter_v3 import dependency_preflight
    return dependency_preflight({k: manifest['versions'][k] for k in ('h2', 'hpack', 'hyperframe')})


@contextmanager
def phase_deadline(seconds, label):
    """Local phase timer; parent process supplies the admitted child's hard cap."""
    require(threading.current_thread() is threading.main_thread(), 'MAIN_THREAD_REQUIRED')
    started = time.monotonic()
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    def expired(*_):
        raise TimeoutError(label)
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, min(seconds, previous_timer[0]) if previous_timer[0] else seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0]:
            signal.setitimer(signal.ITIMER_REAL,
                max(.001, previous_timer[0] - (time.monotonic() - started)), previous_timer[1])


def archive_deadline_output(command, ticket, token, pgid, stdout, stderr, drained):
    # Only the original runtime receipt directory supplied to this child. Never
    # put arbitrary child prose back into the legacy terminal/quota classifier.
    require(command.count('--output-dir') == 1, 'ORIGINAL_OUTPUT_DIRECTORY_REQUIRED')
    out = Path(command[command.index('--output-dir') + 1]).resolve(strict=True)
    lease = json.loads((out / 'lease.json').read_text())
    require(lease['id'] == ticket and lease['token'] == token, 'ORIGINAL_OUTPUT_LEASE_REQUIRED')
    streams = {}
    for name, body in (('stdout', stdout), ('stderr', stderr)):
        body = body or b''
        require(isinstance(body, bytes), 'RAW_CHILD_OUTPUT_REQUIRED')
        streams[name] = {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
                         'base64': base64.b64encode(body).decode('ascii')}
    return freeze(out / 'SDK-DEADLINE-OUTPUT.json', {
        'status': 'LOCAL_DEADLINE_REMOTE_UNKNOWN', 'ticket_id': ticket, 'pgid': pgid,
        'process_group_empty': drained, 'capture_complete': drained,
        'remote_terminal': False, 'streams': streams,
        'scope': 'complete captured pipes after drain; partial capture if drain unproven'})


def child_text(body, kwargs):
    if body is None or not (kwargs.get('text') or kwargs.get('universal_newlines')
                            or kwargs.get('encoding') or kwargs.get('errors')):
        return body
    encoding = kwargs.get('encoding') or ('utf-8' if sys.flags.utf8_mode else locale.getencoding())
    return body.decode(encoding, kwargs.get('errors') or 'strict').replace('\r\n', '\n').replace('\r', '\n')


def bounded_broker(module, *, total=CHILD_SECONDS, drain=DRAIN_SECONDS):
    """Override only run for new SDK callers; original queue/release rules stay."""
    class BoundedBroker(module.Broker):
        def run(self, ticket, token, command, **kwargs):
            started = time.monotonic()
            require(isinstance(command, list) and command, 'ARGV_REQUIRED')
            proc = None
            capture = {k: v for k, v in kwargs.items() if k not in {'text', 'universal_newlines', 'encoding', 'errors'}}
            with ExitStack() as stack:
                timed_out = False
                drain_unproven = False
                try:
                    with phase_deadline(min(PREFLIGHT_SECONDS, total), 'BROKER_PRELAUNCH_DEADLINE'):
                        row = self.require(ticket, token)
                        stack.enter_context(module.os_lock(self.lock_path(row['resource'])))
                        self.require(ticket, token)
                        self._external_free(row['resource'])
                        proc = subprocess.Popen(command, start_new_session=True, **capture)
                        self.db.execute('UPDATE tickets SET pgid=?,invocations=invocations+1 WHERE id=?',
                                        (proc.pid, ticket))
                    stdout, stderr = proc.communicate(timeout=max(.001, total - (time.monotonic() - started)))
                except (subprocess.TimeoutExpired, TimeoutError):
                    if proc is None:
                        raise
                    timed_out = True
                    # Popen created this session/PGID. Never inspect or kill any
                    # other application's group, and never infer remote cancel.
                    try: os.killpg(proc.pid, signal.SIGTERM)
                    except ProcessLookupError: pass
                    try:
                        stdout, stderr = proc.communicate(timeout=drain)
                    except subprocess.TimeoutExpired:
                        try: os.killpg(proc.pid, signal.SIGKILL)
                        except ProcessLookupError: pass
                        try:
                            stdout, stderr = proc.communicate(timeout=drain)
                        except subprocess.TimeoutExpired as exc:
                            # Preserve the captured prefix before the original
                            # runtime records UNKNOWN; never claim full drain.
                            stdout, stderr = exc.output, exc.stderr
                            drain_unproven = True
                # Child phase timers use the same reserved nonterminal code.
                # Their original logs also cannot become legacy quota proof.
                timed_out = timed_out or proc.returncode == 124
                empty = not module.group_alive(proc.pid)
                if empty:
                    self.db.execute('UPDATE tickets SET pgid=NULL WHERE id=?', (ticket,))
                if timed_out:
                    with phase_deadline(CLEANUP_SECONDS, 'DEADLINE_EVIDENCE_5_SECONDS'):
                        archive_deadline_output(command, ticket, token, proc.pid,
                                                stdout, stderr, empty and not drain_unproven)
                    if drain_unproven:
                        raise TimeoutError('OWN_CHILD_DRAIN_UNPROVEN')
                    # Deadline takes precedence over any quota/auth/terminal
                    # words in the raw evidence. Legacy runtime stays unchanged.
                    stdout = b'{"status":"UNCERTAIN","error_type":"SDK_CHILD_HARD_DEADLINE"}\n'
                    stderr = b'SDK_CHILD_HARD_DEADLINE_REMOTE_STATE_UNKNOWN\n'
                return {'exit_code': 124 if timed_out else proc.returncode,
                        'stdout': child_text(stdout, kwargs), 'stderr': child_text(stderr, kwargs),
                        'process_group_empty': empty, 'pgid': proc.pid}
    return BoundedBroker


@contextmanager
def bounded_runtime(runtime):
    require(threading.active_count() == 1, 'DEDICATED_RUNTIME_PROCESS_REQUIRED')
    original = runtime.broker_module
    def load(value):
        # The legacy loader uses SourceFileLoader and may consume pyc. Compile
        # the original pinned broker source without changing its on-disk bytes.
        path = checked(value['broker_module'])
        body = path.read_bytes()
        require(hashlib.sha256(body).hexdigest() == value['broker_module']['sha256'], 'BROKER_SOURCE_CHANGED')
        module = types.ModuleType('thesis_sdk_original_broker')
        module.__file__ = str(path)
        exec(compile(body, str(path), 'exec', dont_inherit=True), module.__dict__)
        return types.SimpleNamespace(Broker=bounded_broker(module))
    runtime.broker_module = load
    try:
        yield
    finally:
        runtime.broker_module = original


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
    with phase_deadline(PREFLIGHT_SECONDS, 'PREPARE_30_SECONDS'):
        return _prepare(config, output)


def _prepare(config, output):
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
        'no_network': True, 'budget_mutations': False, 'global_entry_changes': False,
        'preflight_seconds': PREFLIGHT_SECONDS, 'child_hard_seconds': CHILD_SECONDS,
        'cleanup_seconds': CLEANUP_SECONDS, 'termination_grace_seconds': DRAIN_SECONDS,
        'kill_drain_seconds': DRAIN_SECONDS})
    return prepared


def config_checked(path, expected=None):
    with phase_deadline(PREFLIGHT_SECONDS, 'CONFIG_PREFLIGHT_30_SECONDS'):
        return _config_checked(path, expected)


def _config_checked(path, expected=None):
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
            with bounded_runtime(runtime):
                result = runtime.run_bound(binding(cfg, path), request, budget)
            if result.get('cached'):
                receipt = result['receipt']
                require(ref(receipt['path'])['sha256'] == receipt['sha256'], 'CACHED_RECEIPT_CHANGED')
                result['status'] = json.loads(Path(receipt['path']).read_text())['status']
            return result
        finally:
            budget.db.close()


def transport(path, expected, output):
    began = time.monotonic()
    with phase_deadline(PREFLIGHT_SECONDS, 'CHILD_PREFLIGHT_30_SECONDS'):
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
              'native_actor_authentication': False, 'started_at': time.time(), 'auth_files_before': before,
              'preflight_seconds': PREFLIGHT_SECONDS, 'child_hard_seconds': CHILD_SECONDS,
              'cleanup_seconds': CLEANUP_SECONDS, 'hard_limit_owner': 'original broker child parent'}
    client = None
    code = 2
    try:
        with phase_deadline(max(.001, CHILD_SECONDS - (time.monotonic() - began)), 'CHILD_TOTAL_240_SECONDS'):
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
                remaining = max(.001, CHILD_SECONDS - (time.monotonic() - began))
                http = BoundedHTTP(out, proxy=cfg['proxy'], cookies=client._get_httpx_cookies(), total=remaining, idle=90)
                raw = asyncio.run(http.post('query', url, body))
                value = parse_answer(cfg['provider'], client, raw)
                save(out / 'PARSED-ANSWER.json', value)
                value.update(conversation_id=cfg['conversation_id'], notebook_id=cfg['notebook_id'],
                             request_conversation_id=wire_id, conversation_receipt=cfg['conversation_receipt'],
                             conversation_evidence='explicit previously confirmed persistent ID; no metadata POST')
                validate_answer(value, request)
                code = 0
    except BaseException as exc:
        value = {'status': 'UNCERTAIN', 'error_type': type(exc).__name__}
        record['error_type'] = type(exc).__name__
        if isinstance(exc, TimeoutError):
            code = 124
    finally:
        try:
            # Parent timeout remains active throughout close, auth readback and
            # TRANSPORT persistence. No unbounded cleanup after cancelling it.
            with phase_deadline(CLEANUP_SECONDS, 'CLEANUP_5_SECONDS'):
                if client:
                    client.close()
                record['auth_files_after'] = [ref(manager.cookies_file), ref(manager.metadata_file)]
                record['auth_files_unchanged'] = before == record['auth_files_after']
                if not record['auth_files_unchanged']:
                    code = 124 if code == 124 else 2
                    value = {'status': 'UNCERTAIN', 'error_type': 'AuthFilesChanged'}
                record.update(exit_code=code, ended_at=time.time())
                save(out / 'TRANSPORT.json', record)
        except BaseException as exc:
            code = 124 if code == 124 or isinstance(exc, TimeoutError) else 2
            value = {'status': 'UNCERTAIN', 'error_type': 'Cleanup' + type(exc).__name__}
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
        try:
            return transport(a.config, a.config_sha256, a.output_dir)
        except TimeoutError:
            # Includes preflight before transport's record/cleanup scope. The
            # parent archives pipes and passes only fixed UNKNOWN to runtime.
            return 124
    result = prepare(a.config, a.output_dir) if a.mode == 'prepare' else run(a.config, a.request)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if a.mode == 'prepare' or result.get('status') == 'COMPLETE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
