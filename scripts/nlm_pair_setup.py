"""Serial metadata setup behind the registered pair parent's prepare/run CLI.

No import-time I/O, queries, retries, allocation changes or shared STATE file.
Each run is one original account-broker window: create, add text, or fulltext
plus one explicitly named history read. Repeat with the other provider only
after the first operation's original receipt is COMPLETE and lease released.
The module is a library; only the registered parent exposes execution commands.
"""
from __future__ import annotations

import asyncio
from contextlib import ExitStack, closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time
import types
from urllib.parse import urlparse

import nlm_sdk_entry as single
from nlm_pair_policy import enforce_pair_route_policy

SCRIPTS = Path(__file__).resolve().parent
OPERATIONS = frozenset(('notebook_create', 'source_text_add', 'source_fulltext'))
RPCS = {'notebook_create': ('CCqFvf',), 'source_text_add': ('izAoDd',),
        'source_fulltext': ('hizoJc', 'hPTbtc')}
SERVER_HISTORY_MODE = 'explicit-server-turns-v1'
require, checked, read, ref, freeze = (single.require, single.checked, single.read,
                                      single.ref, single.freeze)


def config_checked(path, expected=None):
    with single.phase_deadline(single.PREFLIGHT_SECONDS, 'SETUP_CONFIG_30_SECONDS'):
        actual = ref(path)
        require(expected is None or actual['sha256'] == expected, 'SETUP_CONFIG_CHANGED')
        cfg = json.loads(Path(path).read_text())
        require(cfg.get('schema') == 'nlm-pair-setup-v1'
                and cfg.get('execution_mode') == 'setup', 'SETUP_CONFIG_SCHEMA')
        for field in ('task_id', 'account_key', 'target_id', 'profile_name', 'email',
                      'proxy', 'budget_root', 'resource_root', 'setup_namespace'):
            require(isinstance(cfg.get(field), str) and cfg[field].strip(), 'REQUIRED:' + field)
        require(cfg.get('provider') in {'jacob', 'teng'}, 'SETUP_PROVIDER')
        require(cfg['setup_namespace'].startswith('new-notebook:' + cfg['provider'] + ':'),
                'EXPLICIT_NEW_NOTEBOOK_NAMESPACE')
        require(cfg.get('single_request_per_process') is True
                and threading.active_count() == 1, 'DEDICATED_SETUP_PROCESS')
        single.actor_check(cfg)
        for key in ('authorization', 'material', 'broker_module', 'route_binding'):
            checked(cfg[key])
        enforce_pair_route_policy(cfg, caller_path=__file__)
        require(Path(sys.executable).resolve() == checked(cfg['python']), 'PINNED_PYTHON_REQUIRED')
        require(sys.flags.ignore_environment and sys.dont_write_bytecode and not sys.flags.optimize,
                'PYTHON_BE_WITHOUT_OPTIMIZE_REQUIRED')
        # A setup has no fresh conversation or accepted source yet. The ordinary
        # continuation validator would require both and cannot be reused here.
        single.sdk_preflight(cfg)
        single.queue_preflight(cfg)
        return cfg


def prepare(config_path, output_dir):
    """Parent prepare dispatch; validates pins/actor and a credential-free route."""
    cfg = config_checked(config_path)
    route = single.check_route(cfg, 'prepare')
    out = Path(output_dir).resolve()
    require(not out.exists(), 'FRESH_SETUP_DIRECTORY_REQUIRED')
    out.mkdir(parents=True)
    prepared = freeze(out / 'CONFIG.json', {**cfg, 'prepared_from': ref(config_path)})
    freeze(out / 'PREPARED.json', {'schema': 'nlm-setup-prepared-v1', 'config': prepared,
        'route': route, 'origin_http_requests': 0, 'query_posts': 0,
        'budget_mutations': False, 'setup_operations_executed': 0})
    return prepared


def _pin_read(pin):
    """Legacy runtime refs may omit bytes; new outward refs always contain it."""
    actual = ref(pin['path'])
    require(actual['sha256'] == pin['sha256']
            and ('bytes' not in pin or pin['bytes'] == actual['bytes']), 'ORIGINAL_RECEIPT_CHANGED')
    return json.loads(Path(actual['path']).read_text())


def confirmed_operation(cfg, pin, operation):
    """A wrapper alone is insufficient: bind original canonical ledger receipt."""
    value = read(pin)
    require(value.get('schema') == 'nlm-setup-operation-v1'
            and value.get('status') == 'COMPLETE' and value.get('operation') == operation,
            'COMPLETE_SETUP_PREDECESSOR_REQUIRED')
    for key in ('task_id', 'account_key', 'provider', 'setup_namespace'):
        require(value.get(key) == cfg[key], 'SETUP_PREDECESSOR_SCOPE:' + key)
    original = _pin_read(value['original_receipt'])
    original_request = _pin_read(original['request'])
    require(original.get('status') == 'COMPLETE' and original.get('operation') == operation
            and original_request.get('task_id') == cfg['task_id']
            and original_request.get('provider') == cfg['provider']
            and original.get('account_key') == cfg['account_key']
            and original.get('request_id') == value.get('request_id')
            and original.get('remote_terminal') is True
            and original.get('process_group_empty') is True, 'ORIGINAL_SETUP_NOT_COMPLETE')
    canonical = Path(cfg['budget_root']).resolve() / 'receipts' / original['request_id'] / 'receipt.json'
    require(Path(value['original_receipt']['path']).resolve() == canonical,
            'ORIGINAL_SETUP_RECEIPT_ROOT')
    raw = _pin_read(original['raw_answer'])
    expected_notebook = cfg['setup_namespace'] if operation == 'notebook_create' else value['notebook_id']
    require(original.get('notebook_id') == expected_notebook, 'ORIGINAL_NOTEBOOK_BINDING')
    if operation == 'notebook_create':
        require(raw.get('created_notebook_id') == value.get('notebook_id')
                and bool(value.get('notebook_id')), 'CREATE_REMOTE_ID_MISMATCH')
    else:
        require(raw.get('source_id') == value.get('source_id')
                and raw.get('notebook_id') == value.get('notebook_id'), 'SOURCE_REMOTE_ID_MISMATCH')
    for key in ('raw', 'http', 'route'):
        checked(value[key])
    return value


def operation_request(cfg, operation_input):
    """Explicit prior receipts determine remote IDs; callers cannot supply IDs."""
    item = dict(operation_input)
    operation = item.get('operation')
    require(operation in OPERATIONS, 'SETUP_METADATA_ONLY')
    common = {'operation', 'round_id', 'phase'}
    extras = {'notebook_create': {'title'}, 'source_text_add': {'create_receipt'},
              'source_fulltext': {'create_receipt', 'source_receipt', 'observation_id'}}[operation]
    if 'history_mode' in item:
        require(operation == 'source_fulltext' and item['history_mode'] == SERVER_HISTORY_MODE,
                'UNSUPPORTED_EXPLICIT_HISTORY_MODE')
        extras = extras | {'history_mode'}
    require(set(item) == common | extras, 'SETUP_OPERATION_FIELDS')
    require(isinstance(item['round_id'], str) and item['round_id'].strip()
            and item['phase'] in {'draft', 'final', 'recovery'}, 'SETUP_ROUND_PHASE')
    request = {key: item[key] for key in common}
    request.update(task_id=cfg['task_id'], provider=cfg['provider'],
                   document_sha256=cfg['material']['sha256'], conversation_id=None)
    if 'history_mode' in item:
        request['history_mode'] = item['history_mode']
    if operation == 'notebook_create':
        require(isinstance(item['title'], str) and item['title'].strip(), 'SETUP_TITLE_REQUIRED')
        request.update(notebook_id=cfg['setup_namespace'], title=item['title'], source_ids=[])
    else:
        create = confirmed_operation(cfg, item['create_receipt'], 'notebook_create')
        request.update(notebook_id=create['notebook_id'], create_receipt=item['create_receipt'])
        if operation == 'source_text_add':
            request.update(source_ids=[], file_sha256=cfg['material']['sha256'])
        else:
            source = confirmed_operation(cfg, item['source_receipt'], 'source_text_add')
            require(source['notebook_id'] == create['notebook_id'], 'SOURCE_CREATE_NOTEBOOK_MISMATCH')
            require(source.get('document_sha256') == cfg['material']['sha256'], 'SOURCE_MATERIAL_MISMATCH')
            require(isinstance(item['observation_id'], str) and item['observation_id'],
                    'EXPLICIT_OBSERVATION_ID_REQUIRED')
            request.update(source_id=source['source_id'], source_ids=[source['source_id']],
                           source_receipt=item['source_receipt'], observation_id=item['observation_id'])
    return request


def operation_binding(cfg, config_path, request, operation_pin):
    artifacts = [*cfg['code_pins'], cfg['python'], ref(config_path), cfg['sdk_manifest'],
                 cfg['material'], cfg['authorization'], cfg['route_binding'], cfg['route_policy'],
                 ref(SCRIPTS.parent.parent / 'NLM-ROUTE-POLICY-PIN.json'), operation_pin]
    artifacts.extend(request[key] for key in ('create_receipt', 'source_receipt') if key in request)
    return {'account_key': cfg['account_key'], 'notebook_id': request['notebook_id'],
        'target_id': cfg['target_id'] + ':setup:' + cfg['provider'],
        'workspace_uuid': cfg['actor']['workspace_uuid'], 'surface_uuid': cfg['actor']['surface_uuid'],
        'existing_target_only': True, 'no_navigation': True, 'no_login': True,
        'no_default_write': True, 'no_browser_launch': True,
        'broker_module': cfg['broker_module'], 'resource_root': cfg['resource_root'],
        'external_locks': cfg['external_locks'], 'transport_artifacts': artifacts, 'lease_ttl': 360,
        'commands': {request['operation']: [cfg['python']['path'], '-BE',
            str(SCRIPTS / 'nlm_sdk_pair_parent.py'), 'setup-transport', '--config', str(config_path),
            '--config-sha256', ref(config_path)['sha256'], '--output-dir', '{output_dir}']}}


def setup_operation(config_path, expected_sha, operation_input, output_dir):
    """Run one metadata operation; no automatic retry or next-operation loop."""
    cfg = config_checked(config_path, expected_sha)
    request = operation_request(cfg, operation_input)
    out = Path(output_dir).resolve()
    require(not out.exists(), 'NEW_SETUP_OPERATION_DIRECTORY_REQUIRED')
    out.mkdir(parents=True)
    operation_pin = freeze(out / 'OPERATION.json', operation_input)
    route = single.check_route(cfg, 'pre_admission')
    freeze(out / 'ROUTE-PRE-ADMISSION.json', route)
    import nlm_runtime as runtime
    binding = operation_binding(cfg, config_path, request, operation_pin)
    # Exact input is pinned into transport_contract, checked by the child before
    # any request. The account broker, not a batch-private lock, serializes work.
    request['setup_operation_input'] = operation_pin
    with single.locked(Path(config_path).resolve().parent / 'setup-submit.lock'):
        budget = runtime.Budget(cfg['budget_root'])
        try:
            # Never allocate/configure: metadata rows have units=None. Existing
            # 8/10 query accounting and any UNKNOWN account block remain intact.
            with single.bounded_runtime(runtime):
                result = runtime.run_bound(binding, request, budget)
        finally:
            budget.db.close()
    receipt = _pin_read(result['receipt'])
    result['status'] = receipt['status']
    freeze(out / 'RUNTIME-RESULT.json', result)
    if receipt['status'] != 'COMPLETE':
        return result
    require(receipt.get('remote_terminal') is True and receipt.get('process_group_empty') is True,
            'ORIGINAL_SETTLEMENT_REQUIRED')
    child_out = Path(receipt['raw_answer']['path']).resolve().parent
    candidate = json.loads((child_out / 'OPERATION-EVIDENCE.json').read_text())
    require(candidate['request_id'] == receipt['request_id'], 'ORIGINAL_EVIDENCE_REQUEST_MISMATCH')
    candidate.update(status='COMPLETE', original_receipt=ref(result['receipt']['path']))
    result['operation_receipt'] = freeze(out / 'OPERATION-RECEIPT.json', candidate)
    # A source acceptance and fresh scope require explicit root review; metadata
    # completion alone does not certify scientific content or pair eligibility.
    return result


def run(config_path, request_path):
    """Parent run dispatch; output path is explicitly frozen in the input."""
    request = json.loads(Path(request_path).read_text())
    require(set(request) == {'operation_input', 'output_dir'}, 'SETUP_RUN_FIELDS')
    return setup_operation(config_path, ref(config_path)['sha256'],
                           request['operation_input'], request['output_dir'])


def check_child(cfg, out, config_path):
    """Require this exact live original broker group and STARTED ledger row."""
    import nlm_runtime as runtime
    require(out.parent == Path(cfg['budget_root']).resolve() / 'receipts', 'ORIGINAL_RECEIPT_ROOT')
    request = json.loads((out / 'request.json').read_text())
    lease = json.loads((out / 'lease.json').read_text())
    expected = operation_request(cfg, read(request['setup_operation_input']))
    require(set(request) == set(expected) | {'account_key', 'transport_contract', 'setup_operation_input'}
            and all(request.get(key) == value for key, value in expected.items()),
            'ORIGINAL_SETUP_REQUEST_SCOPE')
    binding = operation_binding(cfg, config_path, expected, request['setup_operation_input'])
    contract = hashlib.sha256(json.dumps({'artifacts': binding['transport_artifacts'],
        'commands': binding['commands'], 'target_id': binding['target_id']}, sort_keys=True).encode()).hexdigest()
    require(request['transport_contract'] == contract, 'ORIGINAL_SETUP_TRANSPORT_CONTRACT')
    require(request.get('account_key') == cfg['account_key']
            and runtime.request_key(request) == out.name, 'ORIGINAL_SETUP_REQUEST_ID')
    with closing(sqlite3.connect((Path(cfg['resource_root']) / 'queue.sqlite3').as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT * FROM tickets WHERE id=?', (lease['id'],)).fetchone()
        require(row is not None, 'ORIGINAL_LEASE_MISSING')
        ticket = dict(row)
    require(ticket['status'] == 'ACTIVE' and ticket['token'] == lease['token']
            and ticket['task_id'] == cfg['task_id']
            and ticket['resource'] == 'nlm-account:' + cfg['account_key']
            and ticket['pgid'] == os.getpgrp() and ticket['expires'] > time.time(),
            'LIVE_ORIGINAL_BROKER_CHILD')
    with closing(sqlite3.connect((Path(cfg['budget_root']) / 'budget.sqlite3').as_uri() + '?mode=ro', uri=True)) as db:
        require(db.execute("SELECT 1 FROM requests WHERE id=? AND account=? AND task_id=? AND operation=? AND state='STARTED'",
                (out.name, cfg['account_key'], cfg['task_id'], request['operation'])).fetchone(),
                'ORIGINAL_STARTED_METADATA_REQUIRED')
    return request


class SetupRPC:
    """Fixed per-operation sequence; one pre-send route per actual built host."""
    def __init__(self, cfg, client, http, out, request, began):
        self.cfg, self.client, self.http = cfg, client, http
        self.out, self.request, self.began = Path(out), request, began
        self.used = []
        self.evidence = []
        self.sequence = list(RPCS[request['operation']])
        self.history_id = None

    def call(self, rpc_id, params, path='/', **kwargs):
        sequence = self.sequence
        require(len(self.used) < len(sequence) and rpc_id == sequence[len(self.used)],
                'EXTRA_OR_OUT_OF_ORDER_SETUP_RPC')
        # Fixed Jacob add_text_source passes timeout=SOURCE_ADD_TIMEOUT. This is
        # a builder hint, never permission to extend our 240/90-second bounds.
        require(not kwargs or (rpc_id == 'izAoDd' and set(kwargs) == {'timeout'}
                and type(kwargs['timeout']) in {int, float} and 0 < kwargs['timeout'] <= 240),
                'UNSUPPORTED_SETUP_RPC_OPTIONS')
        require(time.monotonic() - self.began < single.CHILD_SECONDS, 'CHILD_TOTAL_240_SECONDS')
        self.used.append(rpc_id)  # A route or POST failure still consumes this attempt.
        name = 'rpc-hPTbtc-before-query' if rpc_id == 'hPTbtc' else 'rpc-' + rpc_id
        if rpc_id == 'hPTbtc':
            require(params == [[], None, self.request['notebook_id'], 20]
                    and path == '/notebook/' + self.request['notebook_id'], 'HISTORY_SCOPE_MISMATCH')
        if rpc_id == 'khqZz':
            from nlm_pair_fresh import turns_params, TURNS_BEFORE
            require(self.request.get('history_mode') == SERVER_HISTORY_MODE
                    and params == turns_params(self.history_id)
                    and path == '/notebook/' + self.request['notebook_id'], 'SERVER_TURNS_SCOPE')
            name = TURNS_BEFORE
        url = self.client._build_url(rpc_id, path)
        body = self.client._build_request_body(rpc_id, params)
        route = single.check_route(self.cfg, 'pre_send', host=urlparse(url).hostname)
        route_pin = freeze(self.out / ('ROUTE-' + name + '.json'), route)
        require(time.monotonic() - self.began < single.CHILD_SECONDS, 'CHILD_TOTAL_240_SECONDS')
        raw = asyncio.run(self.http.post(name, url, body))
        evidence = {'rpc_id': rpc_id, 'operation': name, 'params': params, 'source_path': path,
                    'raw': ref(self.out / (name + '.http.raw')), 'route': route_pin}
        self.evidence.append(evidence)
        if rpc_id == 'hPTbtc':
            from nlm_pair_fresh import parse_conversations, rpc_payload, persistent_id
            if self.request.get('history_mode') == SERVER_HISTORY_MODE:
                payload = rpc_payload(raw, self.client)
                if payload != []:
                    self.history_id = persistent_id(payload)
                    self.sequence.append('khqZz')
                return payload
            return parse_conversations(self.client, raw, empty=True)
        if rpc_id == 'khqZz':
            from nlm_pair_fresh import rpc_payload, validate_empty_turns
            payload = rpc_payload(raw, self.client, rpc_id='khqZz')
            # Preserve original payload even when the exact-empty assertion fails.
            freeze(self.out / 'SERVER-TURNS-PAYLOAD.json', {'conversation_id': self.history_id,
                   'payload': payload, 'evidence': evidence})
            validate_empty_turns(payload)
            return payload
        try:
            return self.client._extract_rpc_result(self.client._parse_response(raw), rpc_id)
        except Exception as exc:
            # Do not feed RPCError into the SDK's add-text fallback/reconcile
            # branch. Keep the raw response and terminate this original attempt.
            raise ValueError('SETUP_RPC_PARSE_FAILED_NO_RETRY') from exc


def perform_operation(cfg, request, client, rpc, out):
    operation = request['operation']
    if operation == 'notebook_create':
        value = client.create_notebook(request['title'])
        require(value is not None and isinstance(value.id, str) and value.id, 'CREATE_NOT_CONFIRMED')
        result = {'created_notebook_id': value.id, 'title': value.title, 'provider': cfg['provider']}
        notebook = value.id
    elif operation == 'source_text_add':
        material = checked(cfg['material'])
        value = client.add_text_source(request['notebook_id'], material.read_text(),
                                       title='SDK known-answer fixture 20261110', wait=False)
        require(isinstance(value, dict) and isinstance(value.get('id'), str) and value['id'],
                'SOURCE_ID_NOT_CONFIRMED')
        notebook = request['notebook_id']
        result = {**value, 'source_id': value['id'], 'notebook_id': notebook}
    else:
        value = client.get_source_fulltext(request['source_id'])
        require(isinstance(value, dict) and any(isinstance(value.get(k), str) and value[k]
                for k in ('content', 'fulltext', 'text')), 'FULLTEXT_CONTENT_REQUIRED')
        notebook = request['notebook_id']
        result = {**value, 'source_id': request['source_id'], 'notebook_id': notebook}
        freeze(Path(out) / 'SOURCE-FULLTEXT.json', result)
        payload = rpc.call('hPTbtc', [[], None, notebook, 20], path='/notebook/' + notebook)
        from nlm_pair_fresh import EMPTY_BASIS, TURNS_BASIS, turns_params
        listing = dict(rpc.evidence[-1], payload=payload)
        turns = None
        if request.get('history_mode') == SERVER_HISTORY_MODE and payload != []:
            turn_payload = rpc.call('khqZz', turns_params(rpc.history_id), path='/notebook/' + notebook)
            turns = dict(rpc.evidence[-1], payload=turn_payload)
        empty = {**listing, 'schema': 'nlm-empty-history-observation-v1',
                 'status': 'COMPLETE', 'task_id': cfg['task_id'], 'account_key': cfg['account_key'],
                 'provider': cfg['provider'], 'notebook_id': notebook, 'payload': payload,
                 'shape_basis': EMPTY_BASIS, 'http': ref(Path(out) / 'HTTP.json')}
        if request.get('history_mode') == SERVER_HISTORY_MODE:
            final_http = ref(Path(out) / 'HTTP.json')
            listing['http'] = final_http
            if turns is not None:
                turns['http'] = final_http
            empty = {key: empty[key] for key in ('status', 'task_id', 'account_key', 'provider', 'notebook_id')}
            empty.update(schema='nlm-empty-history-observation-v2', shape_basis=TURNS_BASIS,
                         conversations=listing, turns=turns, persistent_conversation_id=rpc.history_id)
        result['empty_history'] = freeze(Path(out) / 'EMPTY-HISTORY.json', empty)
    require(rpc.used == rpc.sequence, 'SETUP_RPC_SEQUENCE_INCOMPLETE')
    first = rpc.evidence[0]
    evidence = {'schema': 'nlm-setup-operation-v1', 'status': 'TRANSPORT_COMPLETE_NOT_SETTLED',
        'operation': operation, 'task_id': cfg['task_id'], 'account_key': cfg['account_key'],
        'provider': cfg['provider'], 'setup_namespace': cfg['setup_namespace'],
        'notebook_id': notebook, 'source_id': result.get('source_id'),
        'document_sha256': cfg['material']['sha256'], 'request_id': Path(out).name,
        'raw': first['raw'], 'route': first['route'], 'http': ref(Path(out) / 'HTTP.json'),
        'query_posts': 0, 'empty_history': result.get('empty_history')}
    freeze(Path(out) / 'OPERATION-EVIDENCE.json', evidence)
    return result


def failure_summary(exc):
    from nlm_contracts import SAFE_TRANSPORT_CODES
    result = {'status': 'UNCERTAIN', 'error_type': type(exc).__name__}
    if isinstance(exc, ValueError) and str(exc) in SAFE_TRANSPORT_CODES:
        result['error_code'] = str(exc)
    return result


def transport(config_path, expected_sha, output_dir):
    """Internal parent dispatch, reachable only as the original broker child."""
    began = time.monotonic()
    with single.phase_deadline(single.PREFLIGHT_SECONDS, 'SETUP_CHILD_PREFLIGHT_30_SECONDS'):
        cfg = config_checked(config_path, expected_sha)
        out = Path(output_dir).resolve()
        request = check_child(cfg, out, config_path)
        from nlm_sdk_adapter_v3 import BoundedHTTP, save
        from notebooklm_tools.services.auth import AuthManager
        from notebooklm_tools.core.client import NotebookLMClient
        manager = AuthManager(cfg['profile_name'])
        before = [ref(manager.cookies_file), ref(manager.metadata_file)]
    record = {'task_id': cfg['task_id'], 'account_key': cfg['account_key'],
              'request_id': out.name, 'operation': request['operation'], 'query_posts': 0,
              'auth_files_before': before, 'automatic_retry': False,
              'child_hard_seconds': 240, 'idle_seconds': 90, 'cleanup_seconds': 5}
    client, http, code = None, None, 2
    result = {'status': 'UNCERTAIN', 'error_type': 'SetupNotCompleted'}
    try:
        with single.phase_deadline(max(.001, single.CHILD_SECONDS - (time.monotonic() - began)),
                                   'SETUP_CHILD_TOTAL_240_SECONDS'):
            with ExitStack() as stack:
                for lock in cfg['external_locks']:
                    stack.enter_context(single.locked(lock))
                profile = manager.load_profile()
                require(profile.email == cfg['email'] and profile.csrf_token and profile.session_id,
                        'BOUND_CACHED_ACCOUNT_AUTH_REQUIRED')
                client = NotebookLMClient(cookies=profile.cookies, csrf_token=profile.csrf_token,
                    session_id=profile.session_id, build_label=profile.build_label,
                    base_host=profile.base_host, profile_name=cfg['profile_name'], rpc_transport='http')
                def prohibited(*args, **kwargs):
                    raise RuntimeError('NO_AUTH_REFRESH_LOGIN_OR_DEFAULT_WRITE')
                for method in ('_prepare_cdp_transport', '_refresh_auth_tokens', '_reconcile_source',
                               '_try_reload_or_headless_auth', '_update_cached_tokens'):
                    setattr(client, method, prohibited)
                remaining = max(.001, single.CHILD_SECONDS - (time.monotonic() - began))
                http = BoundedHTTP(out, proxy=cfg['proxy'], cookies=client._get_httpx_cookies(),
                                   total=remaining, idle=90)
                rpc = SetupRPC(cfg, client, http, out, request, began)
                client._call_rpc = types.MethodType(lambda self, *args, **kw: rpc.call(*args, **kw), client)
                result = perform_operation(cfg, request, client, rpc, out)
                code = 0
    except BaseException as exc:
        result = failure_summary(exc)
        record['error_type'] = type(exc).__name__
        if result.get('error_code'):
            record['error_code'] = result['error_code']
        if getattr(exc, 'route_observation', None) is not None:
            record['route_observation_failure'] = exc.route_observation
        if isinstance(exc, TimeoutError):
            code = 124
    finally:
        try:
            with single.phase_deadline(single.CLEANUP_SECONDS, 'SETUP_CLEANUP_5_SECONDS'):
                if client:
                    client.close()
                record['auth_files_after'] = [ref(manager.cookies_file), ref(manager.metadata_file)]
                record['auth_files_unchanged'] = before == record['auth_files_after']
                if not record['auth_files_unchanged']:
                    code = 124 if code == 124 else 2
                    result = {'status': 'UNCERTAIN', 'error_type': 'AuthFilesChanged'}
                record.update(exit_code=code, finished_at=time.time(),
                              network_requests=http.calls if http else [])
                save(out / 'TRANSPORT.json', record)
        except BaseException as exc:
            code = 124 if code == 124 or isinstance(exc, TimeoutError) else 2
            result = {'status': 'UNCERTAIN', 'error_type': 'Cleanup' + type(exc).__name__}
    print(json.dumps(result, ensure_ascii=False))
    return code
