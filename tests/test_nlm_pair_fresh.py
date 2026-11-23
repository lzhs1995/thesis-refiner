"""Offline only: exact wire-shaped fixtures, no SDK or network invocation."""
import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


if sys.version_info < (3, 11):
    raise unittest.SkipTest("Pair controller requires Python 3.11+")

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import nlm_pair_fresh as fresh
import nlm_sdk_pair_child as child

ID = '12345678-1234-1234-1234-123456789abc'


def wire(value, *, rpc='hPTbtc', error=None):
    row = ['wrb.fr', rpc, json.dumps(value), None, None, error]
    chunk = json.dumps([row])
    return ")]}'\n" + str(len(chunk.encode())) + '\n' + chunk + '\n'


class Client:
    def _build_url(self, rpc, path):
        self.url_args = (rpc, path)
        return 'https://example.invalid/_/LabsTailwindUi/data/batchexecute?rpcids=' + rpc
    def _build_request_body(self, rpc, params):
        self.body_args = (rpc, params)
        return 'mock-body'
    def _parse_response(self, raw):
        return raw
    def _extract_rpc_result(self, raw, rpc):
        return fresh.rpc_payload(raw)


class HTTP:
    def __init__(self, folder, payload):
        self.folder, self.payload, self.calls = folder, payload, []
    async def post(self, name, url, body):
        if name in self.calls:
            raise ValueError('SECOND_POST_FORBIDDEN')
        self.calls.append(name)
        if isinstance(self.payload, BaseException):
            raise self.payload
        raw = wire(self.payload)
        path = self.folder / (name + '.http.raw')
        path.write_text(raw)
        save(self.folder / 'HTTP.json', [{'name': name, 'raw': fresh.ref(path)}])
        return raw


def save(path, value):
    Path(path).write_text(json.dumps(value))


class FreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.no_network = patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_NETWORK'))
        self.no_network.start()
        self.addCleanup(self.no_network.stop)
        self.cfg = {'task_id': 'pair', 'account_key': 'account', 'provider': 'jacob',
                    'notebook_id': 'new-notebook', 'source_ids': ['source'],
                    'conversation_mode': 'fresh-task-notebook', 'conversation_id': None,
                    'fresh_round_id': 'pair-jacob-once',
                    'fresh_prompt_sha256': hashlib.sha256(b'question').hexdigest()}

    def pin_json(self, name, data):
        path = self.root / name
        save(path, data)
        return fresh.ref(path)

    def scope(self):
        raw = self.root / 'empty.raw'
        raw.write_text(wire([]))
        raw_pin = fresh.ref(raw)
        route = self.pin_json('route.json', {'status': 'MOCK_ROUTE_PASS'})
        http = self.pin_json('http.json', [{'name': fresh.BEFORE, 'send_calls': 1,
            'status': 200, 'http_eof': True, 'decoder_eof': True, 'raw': raw_pin}])
        base = {key: self.cfg[key] for key in ('task_id', 'account_key', 'provider', 'notebook_id')}
        create = self.pin_json('create.json', {**base, 'operation': 'notebook_create',
            'status': 'COMPLETE', 'raw': raw_pin, 'route': route, 'http': http})
        empty = self.pin_json('empty.json', {**base, 'schema': 'nlm-empty-history-observation-v1',
            'status': 'COMPLETE', 'rpc_id': fresh.RPC, 'operation': fresh.BEFORE,
            'params': [[], None, self.cfg['notebook_id'], 20],
            'source_path': '/notebook/' + self.cfg['notebook_id'],
            'shape_basis': fresh.EMPTY_BASIS, 'raw': raw_pin, 'route': route, 'http': http, 'payload': []})
        source = self.pin_json('source.json', {'marker': 'frozen-source'})
        scope = {**base, 'source_ids': self.cfg['source_ids'], 'schema': 'nlm-fresh-notebook-scope-v1',
            'status': 'FRESH_EMPTY_HISTORY_CONFIRMED', 'task_exclusive': True, 'conversation_id': None,
            'round_id': self.cfg['fresh_round_id'], 'prompt_sha256': self.cfg['fresh_prompt_sha256'],
            'source_binding': source, 'notebook_create': create, 'empty_history': empty}
        scope_pin = self.pin_json('scope.json', scope)
        self.cfg.update(source_binding=source, fresh_scope=scope_pin, conversation_receipt=scope_pin)
        return scope

    def test_exact_empty_and_unknown_layout_rejected(self):
        self.assertEqual(fresh.parse_conversations(Client(), wire([]), empty=True), [])
        for value in (None, {}, '', [[]], [None], [[[ID]]], [[], []]):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'EMPTY_HISTORY_SHAPE_UNVERIFIED'):
                fresh.parse_conversations(Client(), wire(value), empty=True)

    def test_explicit_empty_turns_and_timestamped_persistent_id(self):
        for value in ([], [None], [[]], [None, None], [[], None]):
            fresh.validate_empty_turns(value)
        for value in (None, {}, '', [False], [[['question']]], [[], 'next-page'], [None, None, None]):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'SERVER_TURNS_NOT_EXPLICITLY_EMPTY'):
                fresh.validate_empty_turns(value)
        self.assertEqual(fresh.persistent_id([[[ID, [1, 0], [2, 999999999]]]]), ID)
        for timestamp in ([True, 0], [-1, 0], [1, 1000000000]):
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                fresh.persistent_id([[[ID, timestamp, [2, 0]]]])

    def test_v2_history_requires_empty_turns_bound_to_exact_conversation(self):
        route = self.pin_json('v2-route.json', {'synthetic': True})
        base = {key: self.cfg[key] for key in ('task_id', 'account_key', 'provider', 'notebook_id')}
        def operation(name, rpc, payload, params):
            raw = self.root / (name + '.raw')
            raw.write_text(wire(payload, rpc=rpc))
            raw_ref = fresh.ref(raw)
            http = self.pin_json(name + '.http.json', [{'name': name, 'send_calls': 1,
                'status': 200, 'http_eof': True, 'decoder_eof': True, 'raw': raw_ref}])
            return dict(operation=name, rpc_id=rpc, params=params, payload=payload,
                        source_path='/notebook/' + self.cfg['notebook_id'], raw=raw_ref, http=http, route=route)
        listing = operation(fresh.BEFORE, fresh.RPC, [[ID]], [[], None, self.cfg['notebook_id'], 20])
        turns = operation(fresh.TURNS_BEFORE, fresh.TURNS_RPC, [[], None], fresh.turns_params(ID))
        evidence = dict(base, schema='nlm-empty-history-observation-v2', status='COMPLETE',
                        shape_basis=fresh.TURNS_BASIS, conversations=listing,
                        persistent_conversation_id=ID, turns=turns)
        fresh.validate_server_history(evidence, self.cfg)
        wrong_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
        with self.assertRaisesRegex(ValueError, 'SERVER_HISTORY_ID_CHANGED'):
            fresh.validate_server_history({**evidence, 'persistent_conversation_id': wrong_id}, self.cfg)
        bad_turns = operation(fresh.TURNS_BEFORE, fresh.TURNS_RPC, [[['prior question']]], fresh.turns_params(ID))
        with self.assertRaisesRegex(ValueError, 'SERVER_TURNS_NOT_EXPLICITLY_EMPTY'):
            fresh.validate_server_history({**evidence, 'turns': bad_turns}, self.cfg)

    def test_envelope_must_be_unique_successful_and_explicit(self):
        good = wire([])
        bad = [wire([], rpc='other'), wire([], error=[7, None, []]),
               good + good, '[]', 'null', wire([]).replace('"[]"', 'null')]
        for raw in bad:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                fresh.parse_conversations(Client(), raw, empty=True)

    def test_persistent_shapes_no_recursive_uuid_or_stream_fallback(self):
        for value in ([[ID]], [[[ID]]]):
            self.assertEqual(fresh.parse_conversations(Client(), wire(value), empty=False), ID)
        for value in ([], {'stream_id': ID}, [[ID], [ID]], [[ID, 'extra']], [ID], [[['stream-id']]]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                fresh.parse_conversations(Client(), wire(value), empty=False)

    def test_scope_binds_notebook_sources_question_and_raw(self):
        self.scope()
        fresh.validate_fresh_scope(self.cfg, {})
        for key, replacement in [('notebook_id', 'old-notebook'), ('source_ids', ['other']),
                                 ('fresh_round_id', 'other-round'), ('fresh_prompt_sha256', 'a' * 64),
                                 ('conversation_id', ID)]:
            cfg = {**self.cfg, key: replacement}
            with self.subTest(key=key), self.assertRaises(ValueError):
                fresh.validate_fresh_scope(cfg, {})
        (self.root / 'empty.raw').write_text(wire([[ID]]))
        with self.assertRaisesRegex(ValueError, 'PIN_CHANGED'):
            fresh.validate_fresh_scope(self.cfg, {})

    def test_http_truncated_or_repeated_is_not_empty_proof(self):
        self.scope()
        evidence = json.loads((self.root / 'empty.json').read_text())
        rows = json.loads((self.root / 'http.json').read_text())
        for key, value in [('http_eof', False), ('decoder_eof', False), ('send_calls', 2), ('status', 500)]:
            changed = copy.deepcopy(rows)
            changed[0][key] = value
            evidence['http'] = self.pin_json('bad-http.json', changed)
            with self.subTest(key=key), self.assertRaises(ValueError):
                fresh.check_http_evidence(evidence, fresh.BEFORE)

    def test_request_prompt_and_round_cannot_change(self):
        request = {'conversation_id': None, 'round_id': self.cfg['fresh_round_id'], 'prompt': 'question'}
        fresh.validate_fresh_request(self.cfg, request)
        for key, value in [('conversation_id', ID), ('round_id', 'changed'), ('prompt', 'changed')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                fresh.validate_fresh_request(self.cfg, {**request, key: value})

    def readback(self, http, route=lambda *a, **kw: {'route': 'mock-US2'}):
        return asyncio.run(fresh.read_persistent_once(self.cfg, Client(), http, self.root,
            began=time.monotonic(), check_route=route, save=save))

    def test_single_named_readback_and_raw_receipt_preserved(self):
        http = HTTP(self.root, [[[ID]]])
        route_calls = []
        identity, pin = self.readback(http, lambda *args, **kw: route_calls.append((args, kw)) or {'route': 'mock-US2'})
        self.assertEqual(identity, ID)
        self.assertEqual(http.calls, [fresh.AFTER])
        self.assertEqual(route_calls[0][0][1], 'pre_send')
        self.assertEqual(route_calls[0][1]['host'], 'example.invalid')
        result = fresh.read(pin)
        self.assertEqual(result['conversation_id'], ID)
        self.assertIsNone(result['original_request_conversation_id'])
        fresh.checked(result['raw'])
        with self.assertRaisesRegex(ValueError, 'SECOND_POST_FORBIDDEN'):
            self.readback(http)

    def test_route_denial_sends_no_metadata(self):
        http = HTTP(self.root, [[[ID]]])
        def denied(*args, **kwargs):
            raise ValueError('US2_DENIED')
        with self.assertRaisesRegex(ValueError, 'US2_DENIED'):
            self.readback(http, denied)
        self.assertEqual(http.calls, [])

    def test_metadata_failure_never_requeries_or_uses_stream_id(self):
        http = HTTP(self.root, TimeoutError('metadata'))
        original = self.root / 'PARSED-ANSWER.json'
        save(original, {'answer': 'complete answer', 'stream_id': ID})
        before = original.read_bytes()
        with self.assertRaises(TimeoutError):
            self.readback(http)
        self.assertEqual(http.calls, [fresh.AFTER])
        self.assertEqual(original.read_bytes(), before)
        self.assertFalse((self.root / 'PERSISTENT-CONVERSATION.json').exists())

    def test_metadata_post_flag_distinguishes_gate_and_post_failure(self):
        for gate_error in (True, False):
            state = {'http_post_attempted': True, 'metadata_http_post_attempted': False}
            http = HTTP(self.root, TimeoutError('metadata'))
            def route(*args, **kwargs):
                if gate_error:
                    raise ValueError('ROUTE_DENIED')
                return {'route': 'mock-US2'}
            with self.assertRaises((ValueError, TimeoutError)):
                asyncio.run(fresh.read_persistent_once(self.cfg, Client(), http, self.root,
                    began=time.monotonic(), check_route=route, save=save, post_state=state))
            self.assertEqual(state['metadata_http_post_attempted'], not gate_error)
            self.assertEqual(len(http.calls), int(not gate_error))

    def test_original_deadline_not_restarted(self):
        http = HTTP(self.root, [[[ID]]])
        with self.assertRaisesRegex(ValueError, 'CHILD_TOTAL_240_SECONDS'):
            asyncio.run(fresh.read_persistent_once(self.cfg, Client(), http, self.root,
                began=time.monotonic() - 241, check_route=lambda *a, **kw: {}, save=save))
        self.assertEqual(http.calls, [])

    def test_preflight_receipt_requires_control_flow_and_no_prior_http(self):
        budget = self.root / 'budget'
        receipt = budget / 'receipts' / 'request-id'
        receipt.mkdir(parents=True)
        cfg = {**self.cfg, 'budget_root': str(budget)}
        pin = self.pin_json('config.json', cfg)
        save(receipt / 'request.json', {'task_id': 'pair', 'account_key': 'account',
             'notebook_id': 'new-notebook', 'operation': 'query'})
        child.pair_preflight_failure(pin['path'], pin['sha256'], receipt, 'RouteError')
        result = json.loads((receipt / 'PAIR-PREFLIGHT-FAILURE.json').read_text())
        self.assertIs(result['http_post_attempted'], False)
        self.assertEqual(result['origin_http_calls'], 0)
        save(receipt / 'HTTP.json', [{'name': 'query'}])
        with self.assertRaisesRegex(ValueError, 'PRIOR_HTTP_EVIDENCE_EXISTS'):
            child.pair_preflight_failure(pin['path'], pin['sha256'], receipt, 'RouteError')


if __name__ == '__main__':
    unittest.main()
