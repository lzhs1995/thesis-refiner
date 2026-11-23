"""Managed two-query parent: one original account lease, two original IDs.

No allocation/configuration mutation, implicit retry, old task migration or
automatic UNKNOWN settlement. prepare performs the original TLS-only gate;
run is a real network-capable entry and requires exact execution authority.
"""
from contextlib import closing
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
import types

import nlm_sdk_pair_child as child
from nlm_pair_budget import PairBudget, runtime, request_key
from nlm_pair_group import (admit_under_original_lease, checked_json,
                            validate_pair_members, worker_children)
from nlm_pair_policy import enforce_pair_route_policy

SCRIPTS = Path(__file__).resolve().parent
COMMON = ('task_id', 'account_key', 'budget_root', 'resource_root', 'external_locks',
          'python', 'actor', 'broker_module', 'route_policy', 'route_binding', 'proxy',
          'scripts', 'code_pins')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def ref(path):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def write(path, value):
    path = Path(path)
    data = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return ref(path)


def read(reference):
    require(ref(reference['path']) == reference, 'EXACT_INPUT_PIN_CHANGED')
    return json.loads(Path(reference['path']).read_bytes())


def load_broker(reference):
    body = Path(reference['path']).read_bytes()
    require(ref(reference['path']) == reference, 'ORIGINAL_BROKER_PIN_CHANGED')
    module = types.ModuleType('sdk_pair_original_broker')
    module.__file__ = reference['path']
    sys.modules[module.__name__] = module
    exec(compile(body, reference['path'], 'exec', dont_inherit=True), module.__dict__)
    return module


def checked_group(reference, *, route_phase=None):
    group = read(reference)
    require(group['schema'] == 'nlm-sdk-pair-prepared-v1' and len(group['members']) == 2,
            'PREPARED_PAIR_REQUIRED')
    require(group['parent'] == ref(__file__) and group['pair_child'] == ref(SCRIPTS / 'nlm_sdk_pair_child.py'),
            'PAIR_EXECUTABLE_CHANGED')
    enforce_pair_route_policy(group, caller_path=__file__)
    configs = []
    for member in group['members']:
        cfg = read(member['config'])
        enforce_pair_route_policy(cfg, caller_path=__file__)
        child.actor_check(cfg)
        from nlm_pair_fresh import config_pair_checked, validate_fresh_request
        cfg = config_pair_checked(member['config']['path'], member['config']['sha256'])
        require(all(cfg[key] == group[key] for key in COMMON), 'PAIR_COMMON_BINDING_CHANGED')
        request = read(member['request'])
        require(request_key(request) == member['origin_request_id'], 'ORIGINAL_QUERY_ID_CHANGED')
        require(request['notebook_id'] == cfg['notebook_id'] and request['source_ids'] == cfg['source_ids']
                and request.get('conversation_id') is None and request['task_id'] == cfg['task_id']
                and request['account_key'] == cfg['account_key'], 'PAIR_MEMBER_SCOPE_CHANGED')
        validate_fresh_request(cfg, request)
        if route_phase:
            child.check_route(cfg, route_phase)
        configs.append(cfg)
    require(len({cfg['notebook_id'] for cfg in configs}) == 2, 'DIFFERENT_NOTEBOOKS_REQUIRED')
    scope = read(group['total_query_scope'])
    require(scope['new_pair_task_id'] == group['task_id'] and scope['account_key'] == group['account_key'],
            'TOTAL_SCOPE_GROUP_CHANGED')
    return group


def prepare(input_path, output):
    spec = json.loads(Path(input_path).read_bytes())
    require(spec['schema'] == 'nlm-sdk-pair-input-v1' and len(spec['members']) == 2, 'PAIR_INPUT_REQUIRED')
    enforce_pair_route_policy(spec, caller_path=__file__)
    out = Path(output).resolve()
    require(not out.exists(), 'FRESH_PREPARATION_DIRECTORY_REQUIRED')
    from nlm_pair_fresh import config_pair_checked, validate_fresh_request
    configs, requests, observations = [], [], []
    for member in spec['members']:
        cfg = read(member['config'])
        require(all(cfg[key] == spec[key] for key in COMMON), 'INPUT_GROUP_BINDING_CHANGED')
        enforce_pair_route_policy(cfg, caller_path=__file__)
        cfg = config_pair_checked(member['config']['path'], member['config']['sha256'])
        child.queue_preflight(cfg)
        request = child.request_input(member['request']['path'])
        read(member['request'])
        source = read(cfg['source_binding'])
        request.update(task_id=cfg['task_id'], account_key=cfg['account_key'], operation='query',
                       notebook_id=cfg['notebook_id'], source_ids=cfg['source_ids'],
                       document_sha256=source['document']['sha256'], conversation_id=None,
                       transport_contract=hashlib.sha256(json.dumps({'parent': ref(__file__),
                           'child': ref(SCRIPTS / 'nlm_sdk_pair_child.py'), 'config': member['config']},
                           sort_keys=True).encode()).hexdigest())
        validate_fresh_request(cfg, request)
        configs.append(cfg)
        requests.append(request)
        observations.append(child.check_route(cfg, 'prepare'))
    require(all(configs[0][key] == configs[1][key] for key in COMMON), 'COMMON_PAIR_BINDING_REQUIRED')
    require(len({cfg['notebook_id'] for cfg in configs}) == 2, 'DIFFERENT_NOTEBOOKS_REQUIRED')
    scope = read(spec['total_query_scope'])
    require(scope['new_pair_task_id'] == configs[0]['task_id'] and scope['account_key'] == configs[0]['account_key'],
            'ORIGINAL_TOTAL_BUDGET_SCOPE_REQUIRED')
    authority = read(spec['execution_authority'])
    provisional = {**{key: configs[0][key] for key in COMMON}, 'parent': ref(__file__),
                   'total_query_scope': spec['total_query_scope'],
                   'members': [{'origin_request_id': request_key(request)} for request in requests]}
    authorize(provisional, authority)
    out.mkdir()
    members = []
    for index, (member, request) in enumerate(zip(spec['members'], requests)):
        members.append({'config': member['config'], 'request': write(out / f'request-{index}.json', request),
                        'origin_request_id': request_key(request)})
    group = {'schema': 'nlm-sdk-pair-prepared-v1', 'execution_mode': 'pair', **{key: configs[0][key] for key in COMMON},
             'parent': ref(__file__), 'pair_child': ref(SCRIPTS / 'nlm_sdk_pair_child.py'),
             'members': members, 'total_query_scope': spec['total_query_scope'],
             'prepared_from': ref(input_path), 'execution_authority': spec['execution_authority']}
    pin = write(out / 'GROUP.json', group)
    write(out / 'PREPARED.json', {'group': pin, 'route_observations': observations,
          'query_posts': 0, 'origin_http_calls': 0, 'budget_mutations': 0,
          'network_scope': 'original credential-free CONNECT/TLS observations only'})
    return pin


def authorize(group, authority):
    require(authority['status'] == 'APPROVED_SDK_PAIR_EXECUTION' and authority['max_in_flight'] == 2
            and authority['task_id'] == group['task_id'] and authority['account_key'] == group['account_key']
            and authority['parent'] == group['parent'] and authority['total_query_scope'] == group['total_query_scope']
            and authority['origin_request_ids'] == [m['origin_request_id'] for m in group['members']]
            and authority['issued_epoch'] <= time.time() < authority['expires_epoch'],
            'EXACT_UNEXPIRED_PAIR_AUTHORITY_REQUIRED')


def query_body_observation(folder, child_process, calls):
    """Bind optional raw-read measurements; never decide network settlement."""
    path = folder / 'HTTP-MEASUREMENTS.json'
    if not path.exists():
        return {'status': 'UNAVAILABLE', 'reason': 'RAW_READ_MEASUREMENT_MISSING'}
    try:
        rows = json.loads(path.read_bytes())
        require(isinstance(rows, list) and [row['name'] for row in rows] == [c['name'] for c in calls],
                'EXACT_MEASURED_OPERATION_SET_REQUIRED')
        row = rows[0]
        call = calls[0]
        require(row['name'] == call['name'] == 'query'
                and row['schema'] == 'nlm-http-monotonic-observation-v1'
                and row['clock'] == 'time.monotonic_ns'
                and row['clock_scope'] == 'same-host-kernel-monotonic'
                and row['source'] == 'httpx.AsyncBaseTransport/AsyncByteStream'
                and row['hostname'] == socket.gethostname()
                and type(row['pid']) is int and row['pid'] > 0
                and row['pid'] == child_process['pid'], 'ORIGINAL_CHILD_MONOTONIC_CLOCK_REQUIRED')
        require(row['original_http_path'] == str((folder / 'HTTP.json').resolve())
                and row['response_status'] == call['status']
                and call['send_calls'] == 1 and call['http_eof'] is True
                and call['decoder_eof'] is True, 'ORIGINAL_DECODER_AND_HTTP_EOF_REQUIRED')
        fields = ('request_transport_monotonic_ns', 'response_headers_monotonic_ns',
                  'body_read_started_monotonic_ns', 'body_eof_monotonic_ns',
                  'post_finished_monotonic_ns')
        stamps = [row[key] for key in fields]
        require(all(type(value) is int and value > 0 for value in stamps)
                and stamps == sorted(stamps), 'ORDERED_BODY_READ_BOUNDARIES_REQUIRED')
        reads = row['raw_read_intervals']
        require(isinstance(reads, list) and reads and reads[-1]['result'] == 'EOF'
                and reads[-1]['ended_monotonic_ns'] == stamps[3], 'ACTUAL_RAW_STREAM_EOF_REQUIRED')
        previous = stamps[2]
        for index, item in enumerate(reads):
            start, end = item['started_monotonic_ns'], item['ended_monotonic_ns']
            require(type(start) is int and type(end) is int and previous <= start <= end <= stamps[3]
                    and item['result'] == ('EOF' if index == len(reads)-1 else 'CHUNK'),
                    'ORDERED_RAW_READ_RECORDS_REQUIRED')
            previous = end
        return {'status': 'BOUND_TO_ORIGINAL_HTTP_EOF', 'measurements': ref(path),
                'http': ref(folder / 'HTTP.json'), 'hostname': row['hostname'],
                'pid': row['pid'], 'clock': row['clock'],
                'interval_ns': stamps[2:4],
                'scope': 'raw response body read lifetime including inter-chunk waits; not simultaneous byte arrival or server compute'}
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        return {'status': 'UNUSABLE', 'reason': str(exc) if isinstance(exc, ValueError) else type(exc).__name__}


def classify_member(member, child_process, group_empty, raw_path):
    """HTTP termination and answer correctness are separate; unknown stays held."""
    folder = Path(member['receipt_dir'])
    request = read(member['request'])
    result = {'mode': 'real', 'request_id': member['origin_request_id'],
              'status': 'UNCERTAIN', 'remote_terminal': False, 'process_group_empty': group_empty,
              'account_key': request['account_key'], 'task_id': request['task_id'],
              'notebook_id': request['notebook_id'], 'operation': 'query',
              'document_sha256': request['document_sha256'], 'round_id': request['round_id'],
              'source_ids': request['source_ids'], 'request': member['request'], 'query_posts': None,
              'review_credit': False, 'quota_limited': False}
    require(request_key(request) == member['origin_request_id'], 'ORIGINAL_RECEIPT_REQUEST_CHANGED')
    if not group_empty or child_process.get('reaped') is not True:
        return {**result, 'reason': 'CHILD_GROUP_NOT_REAPED'}
    result['exit_code'] = child_process['exit_code']
    http_path = folder / 'HTTP.json'
    calls = json.loads(http_path.read_bytes()) if http_path.exists() else []
    failure = folder / 'PAIR-PREFLIGHT-FAILURE.json'
    if failure.exists():
        value = json.loads(failure.read_bytes())
        if (value.get('request_id') == member['origin_request_id']
                and value.get('http_post_attempted') is False and value.get('origin_http_calls') == 0
                and not calls and child_process['exit_code'] != 0):
            return {**result, 'status': 'FAILED', 'remote_terminal': True, 'query_posts': 0,
                    'no_request_submitted': True, 'preflight_failure': ref(failure)}
    transport_path = folder / 'TRANSPORT.json'
    if not transport_path.exists():
        return {**result, 'reason': 'ORIGINAL_TRANSPORT_RECEIPT_MISSING'}
    transport = json.loads(transport_path.read_bytes())
    if (transport.get('request_id') != member['origin_request_id']
            or transport.get('exit_code') != child_process['exit_code']
            or transport.get('auth_files_unchanged') is not True or not transport.get('ended_at')):
        return {**result, 'reason': 'ORIGINAL_CLEANUP_NOT_CONFIRMED'}
    result['transport'] = ref(transport_path)
    names = [c.get('name') for c in calls] if isinstance(calls, list) else []
    if names not in (['query'], ['query', 'rpc-hPTbtc-after-query']):
        return {**result, 'reason': 'EXACT_SENT_OPERATION_SET_NOT_PROVEN'}
    if (transport.get('http_post_attempted') is not True
            or type(transport.get('metadata_http_post_attempted')) is not bool
            or transport['metadata_http_post_attempted'] != ('rpc-hPTbtc-after-query' in names)):
        return {**result, 'reason': 'SENT_OPERATION_CONTROL_FLOW_MISMATCH'}
    # HTTPX raises on an error status before reading its body. A received
    # 401/403/429 header pauses future admission even when EOF is unproven;
    # it never upgrades that original attempt from UNKNOWN to drained.
    result['quota_limited'] = any(call.get('send_calls') == 1
                                  and call.get('status') in (401, 403, 429) for call in calls)
    result['query_posts'] = calls[0].get('send_calls')
    for call in calls:
        if (call.get('send_calls') != 1 or call.get('http_eof') is not True
                or call.get('decoder_eof') is not True or not call.get('ended_at')):
            return {**result, 'reason': 'ORIGINAL_HTTP_STREAM_NOT_COMPLETE'}
        raw = call.get('raw')
        if not raw or ref(raw['path']) != raw or Path(raw['path']).parent != folder:
            return {**result, 'reason': 'ORIGINAL_STREAM_PIN_CHANGED'}
    # Complete responses and cleanup settle the network, even when the answer
    # or persistent-ID parsing fails. No business failure holds a drained lease.
    result.update(remote_terminal=True, status='FAILED', http=ref(http_path),
                  quota_limited=any(c.get('status') in (401, 403, 429) for c in calls))
    result['query_body_observation'] = query_body_observation(folder, child_process, calls)
    result['query_call_interval'] = [transport.get('query_started_monotonic'),
                                     transport.get('query_finished_monotonic')]
    routes = []
    for name in (['ROUTE-PRE-SEND.json', 'ROUTE-PRE-SEND-CONVERSATION.json'] if len(calls) == 2
                 else ['ROUTE-PRE-SEND.json']):
        path = folder / name
        try:
            observation = json.loads(path.read_bytes())
            cfg = read(member['config'])
            require(observation['phase'] == 'pre_send'
                    and observation['binding_sha256'] == cfg['route_binding']['sha256'],
                    'ORIGINAL_PRE_SEND_ROUTE_REQUIRED')
            routes.append(ref(path))
        except (OSError, ValueError, KeyError, TypeError):
            return {**result, 'reason': 'DRAINED_ROUTE_EVIDENCE_INVALID'}
    result['pre_send_routes'] = routes
    if any(call.get('status') != 200 for call in calls):
        return {**result, 'reason': 'COMPLETE_HTTP_ERROR_RESPONSE'}
    if child_process['exit_code'] != 0:
        return {**result, 'reason': 'DRAINED_FRESH_CHILD_OR_METADATA_FAILED'}
    if names != ['query', 'rpc-hPTbtc-after-query']:
        return {**result, 'reason': 'PERSISTENT_READBACK_NOT_COMPLETED'}
    try:
        payload = json.loads(Path(raw_path).read_bytes())
    except (ValueError, OSError):
        return {**result, 'reason': 'DRAINED_INVALID_RESULT_JSON'}
    persistent = payload.get('persistent_conversation_receipt')
    if not persistent or Path(persistent['path']) != folder / 'PERSISTENT-CONVERSATION.json':
        return {**result, 'reason': 'PERSISTENT_CONVERSATION_PROOF_MISSING'}
    try:
        proof = read(persistent)
    except (ValueError, OSError, TypeError, KeyError):
        return {**result, 'reason': 'PERSISTENT_PROOF_INVALID'}
    if proof.get('conversation_id') != payload.get('conversation_id') or payload.get('persistent_conversation_id') != payload.get('conversation_id'):
        return {**result, 'reason': 'PERSISTENT_CONVERSATION_BINDING_CHANGED'}
    result.update(remote_terminal=True, status='FAILED', raw_answer=ref(raw_path),
                  answer_sha256=ref(raw_path)['sha256'], http=ref(http_path),
                  persistent_conversation_receipt=persistent)
    try:
        result['conversation_id'] = runtime.validate_response(request, raw_path)
        result['status'] = 'COMPLETE'
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        result['reason'] = 'SOURCE_CONTRACT_FAILED:' + type(exc).__name__
    return result


def settle(group, lease, run_root, members, process_result, broker, budget, broker_module):
    root = Path(run_root)
    worker_root = root / 'worker'
    group_empty = process_result.get('process_group_empty') is True
    pgid = process_result.get('pgid')
    group_empty = group_empty and not broker_module.group_alive(pgid)
    worker_path = worker_root / 'WORKER-RESULT.json'
    worker = json.loads(worker_path.read_bytes()) if worker_path.exists() else {}
    worker_failure = root / 'WORKER-PREFLIGHT-FAILURE.json'
    zero_children = json.loads(worker_failure.read_bytes()) if worker_failure.exists() else None
    children = worker.get('children', [])
    reports = []
    intervals = []
    body_observations = []
    for index, member in enumerate(members):
        raw_path = Path(member['receipt_dir']) / 'raw.json'
        captured = worker_root / f'{index}.stdout'
        if captured.exists() and not raw_path.exists():
            with raw_path.open('xb') as handle:
                handle.write(captured.read_bytes())
        row = children[index] if index < len(children) and children[index].get('index') == index else {}
        try:
            if (zero_children and zero_children.get('lease_id') == lease['id']
                    and zero_children.get('child_processes_started') == 0
                    and zero_children.get('origin_http_calls') == 0 and group_empty
                    and process_result.get('exit_code') != 0):
                receipt = {'mode': 'real', 'request_id': member['origin_request_id'], 'status': 'FAILED',
                           'remote_terminal': True, 'process_group_empty': True, 'query_posts': 0,
                           'no_request_submitted': True, 'worker_preflight_failure': ref(worker_failure)}
            elif process_result.get('exit_code') == 124:
                receipt = {'mode': 'real', 'request_id': member['origin_request_id'], 'status': 'UNCERTAIN',
                           'remote_terminal': False, 'process_group_empty': group_empty,
                           'reason': 'ORIGINAL_PARENT_HARD_DEADLINE'}
            else:
                receipt = classify_member(member, row, group_empty, raw_path)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            receipt = {'mode': 'real', 'request_id': member['origin_request_id'], 'status': 'UNCERTAIN',
                       'remote_terminal': False, 'process_group_empty': group_empty,
                       'reason': 'ORIGINAL_EVIDENCE_REQUIRES_RECONCILIATION:' + type(exc).__name__}
        receipt['resource_lease'] = lease
        pin = write(Path(member['receipt_dir']) / 'receipt.json', receipt)
        budget.finish(member['origin_request_id'], receipt['status'], pin,
                      quota_limited=receipt.get('quota_limited', False))
        reports.append({'request_id': member['origin_request_id'], 'status': receipt['status'],
                        'remote_terminal': receipt['remote_terminal'], 'receipt': pin})
        interval = receipt.get('query_call_interval', [])
        if (len(interval) == 2 and all(type(v) in (int, float) for v in interval)
                and 0 < interval[0] <= interval[1]):
            intervals.append(interval)
        body = receipt.get('query_body_observation', {})
        if body.get('status') == 'BOUND_TO_ORIGINAL_HTTP_EOF':
            body_observations.append(body)
    terminal = all(row['remote_terminal'] for row in reports) and group_empty
    body_comparable = (len(body_observations) == 2
                       and len({item['pid'] for item in body_observations}) == 2
                       and len({item['hostname'] for item in body_observations}) == 1)
    body_overlap = (max(0, min(item['interval_ns'][1] for item in body_observations)
                          - max(item['interval_ns'][0] for item in body_observations))
                    if body_comparable else None)
    aggregate = {'mode': 'real', 'request_id': 'pair-' + hashlib.sha256(json.dumps(
        [m['origin_request_id'] for m in members]).encode()).hexdigest(),
        'status': 'COMPLETE' if all(r['status'] == 'COMPLETE' for r in reports) else 'FAILED' if terminal else 'UNCERTAIN',
        'remote_terminal': terminal, 'process_group_empty': group_empty, 'resource_lease': lease,
        'members': reports, 'automatic_retry': False,
        'query_http_call_overlap_seconds': max(0, min(i[1] for i in intervals) - max(i[0] for i in intervals)) if len(intervals) == 2 else None,
        'overlap_scope': 'same-machine bounded HTTP call intervals, including client/decode; not exact receiving-only overlap',
        'query_body_read_observations': body_observations,
        'query_body_read_overlap_ns': body_overlap,
        'query_body_read_overlap_seconds': body_overlap / 1_000_000_000 if body_overlap is not None else None,
        'receiving_only_overlap_proven': body_overlap is not None and body_overlap > 0,
        'receiving_only_overlap_scope': 'distinct child raw response body read lifetimes on same kernel monotonic clock; includes inter-chunk waits, not simultaneous byte arrival or server compute'}
    terminal_pin = write(root / 'NETWORK-TERMINAL.json', aggregate)
    if terminal:
        release = broker.release(lease['id'], lease['token'], {'pending': False,
            'own_processes_empty': True, 'in_flight_requests': [], 'terminal_receipt': terminal_pin},
            reconcile=time.time() >= lease['expires'])
        release_pin = write(root / 'RELEASE.json', release)
        return write(root / 'RETURN.json', {'status': 'REAL_PAIR_RETURNED', 'terminal': terminal_pin,
                                             'release': release_pin, 'review_credit': False})
    return write(root / 'RECOVERY-NEEDED.json', {'status': 'RETAIN_ORIGINAL_PAIR_LEASE',
        'terminal': terminal_pin, 'retry': False,
        'next_action': 'Inspect original request/HTTP/cleanup/process receipts; explicit original-ID reconciliation only'})


def execute(group_ref, run_root, *, resume_waiting=False):
    group = checked_group(group_ref, route_phase='pre_admission')
    authority = read(group['execution_authority'])
    authorize(group, authority)
    root = Path(run_root).resolve()
    module = load_broker(group['broker_module'])
    broker = child.bounded_broker(module)(group['resource_root'])
    budget = PairBudget(group['budget_root'])
    lease = None
    admitted = False
    invoked = False
    members = []
    owns_attempt = False
    try:
        if resume_waiting:
            intent = json.loads((root / 'INTENT.json').read_bytes())
            require(intent['group'] == group_ref and not (root / 'lease.json').exists(), 'ONLY_ORIGINAL_WAITING_ADMISSION')
            ticket = read(ref(root / 'TICKET.json'))
            current_ticket = broker.get(ticket['id'])
            require(current_ticket['status'] == 'WAITING'
                    and all(current_ticket[key] == value for key, value in (
                        ('task_id', group['task_id']), ('resource', 'nlm-account:' + group['account_key']),
                        ('workspace_uuid', group['actor']['workspace_uuid']),
                        ('surface_uuid', group['actor']['surface_uuid']))), 'ORIGINAL_WAITING_TICKET_REQUIRED')
            owns_attempt = True
        else:
            root.mkdir(exist_ok=False)
            owns_attempt = True
            write(root / 'INTENT.json', {'group': group_ref, 'authority': group['execution_authority'],
                                        'automatic_retry': False, 'at': time.time()})
            ticket = broker.request('nlm-account:' + group['account_key'], group['task_id'],
                                    group['actor']['workspace_uuid'], group['actor']['surface_uuid'])
            write(root / 'TICKET.json', ticket)
        lease = broker.grant(ticket['id'], ttl=600)
        write(root / 'lease.json', lease)
        requests = [read(member['request']) for member in group['members']]
        pair_authority = {'max_in_flight': 2, 'origin_request_ids': [m['origin_request_id'] for m in group['members']],
            'issued_epoch': time.time(), 'expires_epoch': min(lease['expires'], authority['expires_epoch']),
            'total_query_scope': group['total_query_scope']}
        admit_under_original_lease(group, lease, requests, pair_authority)
        admitted = True
        for old, request in zip(group['members'], requests):
            receipt = Path(group['budget_root']) / 'receipts' / old['origin_request_id']
            receipt.mkdir(parents=True, exist_ok=False)
            request_pin = write(receipt / 'request.json', request)
            write(receipt / 'lease.json', lease)
            members.append({**old, 'request': request_pin, 'receipt_dir': str(receipt)})
        validate_pair_members(group, members)
        run_pin = write(root / 'RUN.json', {'group': group_ref, 'lease': lease, 'members': members,
                                          'output_dir': str(root)})
        command = [group['python']['path'], '-BE', str(Path(__file__).resolve()), 'worker',
                   '--input', run_pin['path'], '--sha256', run_pin['sha256'], '--output-dir', str(root)]
        invoked = True
        process_result = broker.run(lease['id'], lease['token'], command,
                                     text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        write(root / 'PROCESS-RESULT.json', process_result)
        return settle(group, lease, root, members, process_result, broker, budget, module)
    except BaseException as exc:
        if owns_attempt:
            failure_path = root / ('EXCEPTION-' + str(time.time_ns()) + '.json')
            failure = write(failure_path, {'error_type': type(exc).__name__, 'admitted': admitted,
                'invoked': invoked, 'lease': lease, 'automatic_retry': False})
            if lease and not invoked:
                if admitted:
                    for member in group['members']:
                        row = budget.db.execute('SELECT state FROM requests WHERE id=?', (member['origin_request_id'],)).fetchone()
                        if row and row[0] == 'STARTED':
                            budget.finish(member['origin_request_id'], 'FAILED', failure)
                release = broker.release(lease['id'], lease['token'], {'pending': False,
                    'own_processes_empty': True, 'in_flight_requests': [], 'no_request_submitted': True},
                    reconcile=time.time() >= lease['expires'])
                write(root / 'NO-CALL-RELEASE.json', release)
            elif admitted:
                for member in group['members']:
                    row = budget.db.execute('SELECT state FROM requests WHERE id=?', (member['origin_request_id'],)).fetchone()
                    if row and row[0] == 'STARTED':
                        budget.finish(member['origin_request_id'], 'UNCERTAIN', failure)
        raise
    finally:
        budget.db.close()
        broker.db.close()


def worker(input_path, expected, output):
    run = read({'path': str(Path(input_path).resolve()), 'bytes': Path(input_path).stat().st_size, 'sha256': expected})
    require(str(Path(output).resolve()) == run['output_dir'], 'ORIGINAL_GROUP_OUTPUT_REQUIRED')
    try:
        group = checked_group(run['group'])
    except BaseException as exc:
        write(Path(output) / 'WORKER-PREFLIGHT-FAILURE.json', {
            'lease_id': run['lease']['id'], 'child_processes_started': 0,
            'origin_http_calls': 0, 'error_type': type(exc).__name__})
        return 2
    result = worker_children(group, run['lease'], run['members'], Path(output) / 'worker')
    return 0 if result['status'] == 'CHILDREN_REAPED_NOT_NETWORK_ACCEPTED' else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='mode', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('--config', required=True)
    prep.add_argument('--output-dir', required=True)
    call = commands.add_parser('run')
    call.add_argument('--config', required=True)
    call.add_argument('--request', required=True)
    internal = commands.add_parser('worker')
    internal.add_argument('--input', required=True)
    internal.add_argument('--sha256', required=True)
    internal.add_argument('--output-dir', required=True)
    setup_child = commands.add_parser('setup-transport')
    setup_child.add_argument('--config', required=True)
    setup_child.add_argument('--config-sha256', required=True)
    setup_child.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    if args.mode == 'prepare':
        config = json.loads(Path(args.config).read_bytes())
        if config.get('execution_mode') == 'setup':
            from nlm_pair_setup import prepare as prepare_setup
            result = prepare_setup(args.config, args.output_dir)
        else:
            require(config.get('execution_mode') == 'pair', 'EXPLICIT_PAIR_OR_SETUP_MODE_REQUIRED')
            result = prepare(args.config, args.output_dir)
    elif args.mode == 'worker':
        return worker(args.input, args.sha256, args.output_dir)
    elif args.mode == 'setup-transport':
        from nlm_pair_setup import transport as setup_transport
        return setup_transport(args.config, args.config_sha256, args.output_dir)
    else:
        config = json.loads(Path(args.config).read_bytes())
        if config.get('execution_mode') == 'setup':
            from nlm_pair_setup import run as run_setup
            result = run_setup(args.config, args.request)
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result.get('status') == 'COMPLETE' else 2
        require(config.get('execution_mode') == 'pair', 'EXPLICIT_PAIR_OR_SETUP_MODE_REQUIRED')
        request = json.loads(Path(args.request).read_bytes())
        require(set(request) == {'group_sha256', 'output_dir', 'resume_waiting'}
                and type(request['resume_waiting']) is bool, 'PAIR_RUN_REQUEST_FIELDS_REQUIRED')
        value = {'path': str(Path(args.config).resolve()), 'bytes': Path(args.config).stat().st_size,
                 'sha256': request['group_sha256']}
        result = execute(value, request['output_dir'], resume_waiting=request['resume_waiting'])
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
