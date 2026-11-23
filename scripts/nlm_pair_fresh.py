"""Fresh pair validation and one post-query persistent-ID readback.

No convenience SDK calls, retries, history deletion or resource admission.
The exact empty-list grammar is inferred from the fixed SDK contract; it has
not yet been validated against a live fresh-notebook response.
"""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import threading
import time
from urllib.parse import urlparse

import nlm_sdk_entry as single

SCRIPTS = Path(__file__).resolve().parent
RPC = 'hPTbtc'
BEFORE = 'rpc-hPTbtc-before-query'
AFTER = 'rpc-hPTbtc-after-query'
EMPTY_BASIS = 'fixed-sdk-contract-inference-not-live-validated'
TURNS_RPC = 'khqZz'
TURNS_BEFORE = 'rpc-khqZz-before-query'
TURNS_BASIS = 'pinned-jacob-0.16.1-teng-0.8.6-explicit-empty-turns-v1'
UUID = re.compile(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}')
require, checked, read, ref = single.require, single.checked, single.read, single.ref


def validate_empty_history(payload):
    require(type(payload) is list and len(payload) == 0,
            'EMPTY_HISTORY_SHAPE_UNVERIFIED')


def persistent_id(payload):
    # Both exact non-empty layouts are documented by fixed Jacob 0.16.1.
    require(type(payload) is list and len(payload) == 1,
            'PERSISTENT_CONVERSATION_SHAPE_OR_MULTIPLICITY')
    level = payload[0]
    require(type(level) is list and len(level) == 1,
            'PERSISTENT_CONVERSATION_SHAPE_OR_MULTIPLICITY')
    value = level[0]
    if type(value) is list:
        # Actual hPTbtc may include updated/created [seconds, nanoseconds].
        require(len(value) == 1 or len(value) == 3 and all(
            type(t) is list and len(t) == 2 and all(type(n) is int for n in t)
            and t[0] >= 0 and 0 <= t[1] < 1_000_000_000 for t in value[1:]),
            'PERSISTENT_CONVERSATION_SHAPE_OR_MULTIPLICITY')
        value = value[0]
    require(isinstance(value, str) and UUID.fullmatch(value) is not None,
            'PERSISTENT_CONVERSATION_UUID_REQUIRED')
    return value


def rpc_payload(raw, client=None, rpc_id=RPC):
    """Reject missing/duplicate/error envelopes before interpreting a payload."""
    text = raw[4:] if raw.startswith(")]}'") else raw
    chunks = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.isdecimal():
            continue
        chunks.append(json.loads(line))
    rows = [row for chunk in chunks if type(chunk) is list for row in chunk
            if type(row) is list and len(row) >= 2 and row[:2] == ['wrb.fr', rpc_id]]
    require(len(rows) == 1, 'ONE_EXPLICIT_HPTBTC_ENVELOPE_REQUIRED')
    row = rows[0]
    require(len(row) >= 3 and type(row[2]) is str,
            'HPTBTC_NON_NULL_JSON_PAYLOAD_REQUIRED')
    require(len(row) <= 5 or row[5] is None or row[5] == [],
            'HPTBTC_ERROR_ENVELOPE')
    value = json.loads(row[2])
    if client is not None:
        extracted = client._extract_rpc_result(client._parse_response(raw), rpc_id)
        require(extracted == value and type(extracted) is type(value),
                'HPTBTC_FIXED_PARSER_DISAGREEMENT')
    return value


def parse_conversations(client, raw, *, empty):
    payload = rpc_payload(raw, client)
    if empty:
        validate_empty_history(payload)
        return payload
    return persistent_id(payload)


def turns_params(conversation_id):
    require(isinstance(conversation_id, str) and UUID.fullmatch(conversation_id),
            'PERSISTENT_CONVERSATION_UUID_REQUIRED')
    return [[2, None, [1], [1, None, None, None, None, None, None, None, None, None, [1, 3]]],
            None, None, conversation_id, 20]


def validate_empty_turns(payload):
    # Explicit empty containers only; no error/null top-level or continuation.
    require(type(payload) is list and (payload == [] or
            len(payload) in (1, 2) and (payload[0] is None or type(payload[0]) is list and not payload[0])
            and (len(payload) == 1 or payload[1] is None)), 'SERVER_TURNS_NOT_EXPLICITLY_EMPTY')


def validate_server_history(empty, cfg):
    require(empty.get('schema') == 'nlm-empty-history-observation-v2'
            and empty.get('status') == 'COMPLETE' and empty.get('shape_basis') == TURNS_BASIS,
            'SERVER_HISTORY_SCHEMA_OR_STATUS')
    for key in ('task_id', 'account_key', 'provider', 'notebook_id'):
        require(empty.get(key) == cfg[key], 'SERVER_HISTORY_SCOPE:' + key)
    listing = empty['conversations']
    require(listing['rpc_id'] == RPC and listing['operation'] == BEFORE
            and listing['params'] == [[], None, cfg['notebook_id'], 20]
            and listing['source_path'] == '/notebook/' + cfg['notebook_id'], 'SERVER_LIST_SCOPE')
    check_http_evidence(listing, BEFORE)
    payload = rpc_payload(checked(listing['raw']).read_text())
    require(payload == listing['payload'], 'SERVER_LIST_PAYLOAD_CHANGED')
    if payload == []:
        require(empty.get('persistent_conversation_id') is None and empty.get('turns') is None,
                'EMPTY_LIST_UNEXPECTED_TURNS')
        return
    identity = persistent_id(payload)
    require(empty.get('persistent_conversation_id') == identity, 'SERVER_HISTORY_ID_CHANGED')
    turns = empty['turns']
    require(turns['rpc_id'] == TURNS_RPC and turns['operation'] == TURNS_BEFORE
            and turns['params'] == turns_params(identity)
            and turns['source_path'] == '/notebook/' + cfg['notebook_id'], 'SERVER_TURNS_SCOPE')
    check_http_evidence(turns, TURNS_BEFORE)
    value = rpc_payload(checked(turns['raw']).read_text(), rpc_id=TURNS_RPC)
    require(value == turns['payload'], 'SERVER_TURNS_PAYLOAD_CHANGED')
    validate_empty_turns(value)


def check_http_evidence(evidence, operation):
    rows = read(evidence['http'])
    require(type(rows) is list, 'HTTP_EVIDENCE_LIST_REQUIRED')
    matches = [row for row in rows if row.get('name') == operation]
    require(len(matches) == 1, 'EXACT_HISTORY_OPERATION_REQUIRED')
    row = matches[0]
    require(type(row.get('send_calls')) is int and row['send_calls'] == 1
            and row.get('status') == 200 and row.get('http_eof') is True
            and row.get('decoder_eof') is True and not row.get('error_type')
            and row.get('raw') == evidence['raw'], 'COMPLETE_HISTORY_HTTP_REQUIRED')
    checked(evidence['raw'])
    checked(evidence['route'])


def validate_fresh_scope(cfg, source):
    require(cfg.get('conversation_mode') == 'fresh-task-notebook'
            and cfg.get('conversation_id', 'missing') is None,
            'EXPLICIT_FRESH_PAIR_MODE_REQUIRED')
    require(cfg.get('fresh_scope') == cfg.get('conversation_receipt'),
            'SAME_FRESH_CONVERSATION_RECEIPT_REQUIRED')
    scope = read(cfg['fresh_scope'])
    require(scope.get('schema') == 'nlm-fresh-notebook-scope-v1'
            and scope.get('status') == 'FRESH_EMPTY_HISTORY_CONFIRMED'
            and scope.get('task_exclusive') is True
            and scope.get('conversation_id', 'missing') is None,
            'FRESH_SCOPE_SCHEMA_OR_STATUS')
    for key in ('task_id', 'account_key', 'provider', 'notebook_id', 'source_ids'):
        require(scope.get(key) == cfg[key], 'FRESH_SCOPE_MISMATCH:' + key)
    require(scope.get('round_id') == cfg.get('fresh_round_id')
            and isinstance(scope.get('round_id'), str) and scope['round_id']
            and scope.get('prompt_sha256') == cfg.get('fresh_prompt_sha256')
            and re.fullmatch(r'[a-f0-9]{64}', scope.get('prompt_sha256', '')),
            'FRESH_ORIGINAL_ROUND_AND_PROMPT_REQUIRED')
    require(scope.get('source_binding') == cfg['source_binding'],
            'FRESH_SOURCE_BINDING_CHANGED')
    create = read(scope['notebook_create'])
    require(create.get('status') == 'COMPLETE'
            and create.get('operation') == 'notebook_create', 'FRESH_CREATE_COMPLETE_REQUIRED')
    for key in ('task_id', 'account_key', 'provider', 'notebook_id'):
        require(create.get(key) == cfg[key], 'FRESH_CREATE_SCOPE:' + key)
    for key in ('raw', 'http', 'route'):
        checked(create[key])
    empty = read(scope['empty_history'])
    if empty.get('schema') == 'nlm-empty-history-observation-v2':
        validate_server_history(empty, cfg)
        return scope
    require(empty.get('schema') == 'nlm-empty-history-observation-v1'
            and empty.get('status') == 'COMPLETE' and empty.get('rpc_id') == RPC
            and empty.get('operation') == BEFORE
            and empty.get('params') == [[], None, cfg['notebook_id'], 20]
            and empty.get('source_path') == '/notebook/' + cfg['notebook_id']
            and empty.get('shape_basis') == EMPTY_BASIS, 'EMPTY_HISTORY_OPERATION_BINDING')
    for key in ('task_id', 'account_key', 'provider', 'notebook_id'):
        require(empty.get(key) == cfg[key], 'EMPTY_HISTORY_SCOPE:' + key)
    check_http_evidence(empty, BEFORE)
    payload = rpc_payload(checked(empty['raw']).read_text())
    require(payload == empty.get('payload') and type(empty.get('payload')) is list,
            'EMPTY_HISTORY_PAYLOAD_CHANGED')
    validate_empty_history(payload)
    return scope


def validate_pair_inputs(cfg, *, caller_path=None):
    """Same original safety checks, explicit fresh proof replacing continuation."""
    require(sys.version_info >= (3, 11), 'SDK_ENTRY_REQUIRES_PYTHON_3_11')
    require(cfg['schema'] == 'nlm-sdk-task-v1', 'TASK_SCHEMA')
    for field in ('task_id', 'account_key', 'notebook_id', 'target_id', 'profile_name', 'email',
                  'proxy', 'budget_root', 'resource_root'):
        require(isinstance(cfg[field], str) and cfg[field].strip(), 'REQUIRED:' + field)
    require(cfg['provider'] in {'jacob', 'teng'}, 'EXPLICIT_PROVIDER_REQUIRED')
    require(type(cfg['query_budget']) is int and cfg['query_budget'] == 2,
            'EXACT_PAIR_QUERY_ALLOCATION_REQUIRED')
    require(cfg['single_request_per_process'] is True, 'SINGLE_PROCESS_REQUEST_REQUIRED')
    require(threading.active_count() == 1, 'THREADED_SDK_ENTRY_FORBIDDEN')
    single.actor_check(cfg)
    checked(cfg['authorization'])
    checked(cfg['route_binding'])
    from nlm_pair_policy import enforce_pair_route_policy
    enforce_pair_route_policy(cfg, caller_path=caller_path or SCRIPTS / 'nlm_sdk_pair_parent.py')
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
    validate_fresh_scope(cfg, source)
    checked(cfg['broker_module'])
    return source


def config_pair_checked(path, expected=None, *, caller_path=None):
    with single.phase_deadline(single.PREFLIGHT_SECONDS, 'PAIR_CONFIG_PREFLIGHT_30_SECONDS'):
        actual = ref(path)
        require(expected is None or actual['sha256'] == expected, 'TASK_CONFIG_CHANGED')
        cfg = json.loads(Path(path).read_text())
        require(Path(cfg['scripts']).resolve() == SCRIPTS, 'ORIGINAL_RELEASE_REQUIRED')
        for item in cfg['code_pins']:
            checked(item)
        validate_pair_inputs(cfg, caller_path=caller_path)
        single.sdk_preflight(cfg)
        single.queue_preflight(cfg)
        return cfg


def validate_fresh_request(cfg, request):
    require(request.get('conversation_id', 'missing') is None
            and request.get('round_id') == cfg['fresh_round_id']
            and hashlib.sha256(request['prompt'].encode()).hexdigest() == cfg['fresh_prompt_sha256'],
            'FRESH_REQUEST_CHANGED')


async def read_persistent_once(cfg, client, http, out, *, began, check_route, save, post_state=None):
    """Uses the same BoundedHTTP instance and original 240-second deadline."""
    require(time.monotonic() - began < single.CHILD_SECONDS, 'CHILD_TOTAL_240_SECONDS')
    notebook = cfg['notebook_id']
    params, path = [[], None, notebook, 20], '/notebook/' + notebook
    url = client._build_url(RPC, path)
    body = client._build_request_body(RPC, params)
    route = check_route(cfg, 'pre_send', host=urlparse(url).hostname)
    route_path = Path(out) / 'ROUTE-PRE-SEND-CONVERSATION.json'
    save(route_path, route)
    require(time.monotonic() - began < single.CHILD_SECONDS, 'CHILD_TOTAL_240_SECONDS')
    if post_state is not None:
        post_state['metadata_http_post_attempted'] = True
    raw = await http.post(AFTER, url, body)
    identity = parse_conversations(client, raw, empty=False)
    raw_path = Path(out) / (AFTER + '.http.raw')
    value = {'schema': 'nlm-persistent-conversation-readback-v1', 'status': 'COMPLETE',
             'operation': AFTER, 'rpc_id': RPC, 'params': params, 'source_path': path,
             'task_id': cfg['task_id'], 'account_key': cfg['account_key'],
             'provider': cfg['provider'], 'notebook_id': notebook,
             'original_request_conversation_id': None, 'conversation_id': identity,
             'persistent_conversation_id': identity,
             'raw': ref(raw_path), 'http': ref(Path(out) / 'HTTP.json'), 'route': ref(route_path)}
    receipt = Path(out) / 'PERSISTENT-CONVERSATION.json'
    save(receipt, value)
    return identity, ref(receipt)
