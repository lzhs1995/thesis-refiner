import json
import contextlib
import io
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import nlm_sdk_entry as entry
from nlm_route_gate import RouteGateError


@unittest.skipUnless(sys.version_info >= (3, 11), 'Optional SDK entry requires Python 3.11+')
class TaskEntryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        def file(name, content):
            p = self.root / name
            p.write_text(content if isinstance(content, str) else json.dumps(content))
            return entry.ref(p)
        document = file('document.txt', 'fixed source')
        evidence = file('evidence.json', {'status': 'actually checked fixture'})
        self.cfg = dict(schema='nlm-sdk-task-v1', task_id='new-test-task', provider='jacob',
            account_key='account', notebook_id='book', target_id='target', profile_name='profile',
            email='fixture@example.invalid', proxy='http://127.0.0.1:1',
            budget_root=str(self.root/'budget'), resource_root=str(self.root/'resources'),
            query_budget=2, single_request_per_process=True, source_ids=['source'],
            conversation_id='persistent', actor=dict(thread_id='thread',workspace_uuid='workspace',surface_uuid='surface'),
            authorization=evidence, python=entry.ref(sys.executable), broker_module=evidence,
            route_binding=evidence,
            external_locks=[str(self.root/'original.lock')],
            source_binding=file('source.json',dict(notebook_id='book',source_ids=['source'],
                acceptance='ACCEPTED_FOR_REQUEST_SCOPE',document=document,evidence=[evidence])),
            conversation_receipt=file('conversation.json',dict(status='COMPLETE',account_key='account',
                notebook_id='book',conversation_id='persistent',raw_answer=document)))
        self.actor = patch.dict(os.environ, {'CODEX_THREAD_ID':'thread','CMUX_WORKSPACE_ID':'workspace','CMUX_SURFACE_ID':'surface'})
        self.actor.start(); self.addCleanup(self.actor.stop)
        # Parent CI uses -B; the wrapper itself additionally requires -E.
        flag_values = {key: getattr(sys.flags, key) for key in dir(sys.flags) if not key.startswith('_')}
        flag_values.update(ignore_environment=1, optimize=0)
        self.flags = patch.object(entry.sys, 'flags', SimpleNamespace(**flag_values))
        self.flags.start(); self.addCleanup(self.flags.stop)

    def test_actor_mismatch_rejected(self):
        entry.validate_inputs(self.cfg)
        with patch.dict(os.environ, {'CODEX_THREAD_ID':'different'}):
            with self.assertRaisesRegex(ValueError,'ACTUAL_TASK_EXECUTOR'):
                entry.validate_inputs(self.cfg)

    def test_changed_source_and_foreign_conversation_rejected(self):
        p=Path(self.cfg['source_binding']['path']); p.write_text('{}')
        with self.assertRaisesRegex(ValueError,'PIN_CHANGED'):
            entry.validate_inputs(self.cfg)

    def test_confirmed_conversation_scope_required(self):
        p=Path(self.cfg['conversation_receipt']['path'])
        v=json.loads(p.read_text());v['notebook_id']='foreign';p.write_text(json.dumps(v))
        self.cfg['conversation_receipt']=entry.ref(p)
        with self.assertRaisesRegex(ValueError,'CONFIRMED_EXPLICIT_CONVERSATION'):
            entry.validate_inputs(self.cfg)

    def test_threaded_capture_rejected(self):
        with patch.object(entry.threading,'active_count',return_value=2):
            with self.assertRaisesRegex(ValueError,'THREADED_SDK_ENTRY_FORBIDDEN'):
                entry.validate_inputs(self.cfg)

    def test_request_cannot_override_bound_identity(self):
        p=self.root/'request.json'
        p.write_text(json.dumps(dict(round_id='r1',prompt='question',phase='final',source_ids=['foreign'])))
        with self.assertRaisesRegex(ValueError,'ONLY_ROUND_PROMPT_PHASE'):
            entry.request_input(p)

    def test_prepare_uses_existing_queue_readonly_and_freezes(self):
        for folder in ['budget','resources']:(self.root/folder).mkdir()
        with sqlite3.connect(self.root/'resources/queue.sqlite3') as db:
            db.execute('CREATE TABLE resources(name TEXT,external_locks TEXT)')
            db.execute('INSERT INTO resources VALUES(?,?)',('nlm-account:account',json.dumps(self.cfg['external_locks'])))
        with sqlite3.connect(self.root/'budget/budget.sqlite3') as db:
            db.execute('CREATE TABLE accounts(id TEXT)');db.execute("INSERT INTO accounts VALUES('account')")
        databases=[entry.ref(self.root/'resources/queue.sqlite3'),entry.ref(self.root/'budget/budget.sqlite3')]
        p=self.root/'input.json';p.write_text(json.dumps(self.cfg));out=self.root/'prepared'
        with patch.object(entry,'sdk_preflight',return_value={'checked':'fixture'}), \
                patch.object(entry,'check_route',return_value={'route':'isolated fixture'}):
            prepared=entry.prepare(p,out)
            with self.assertRaisesRegex(ValueError,'FRESH_TASK_DIRECTORY'):
                entry.prepare(p,out)
        self.assertEqual([entry.ref(x['path']) for x in databases],databases)
        value=entry.read(prepared)
        self.assertEqual(value['actor'],self.cfg['actor'])
        self.assertTrue(value['code_pins'])

    def test_sdk_extra_import_file_rejected_before_import(self):
        root=self.root/'sdk';root.mkdir();(root/'injected.py').write_text('raise AssertionError("must not import")')
        p=self.root/'sdk.json';p.write_text(json.dumps(dict(schema='nlm-sdk-environment-v1',
            import_roots=[str(root)],files=[],sources=[],versions={})))
        with self.assertRaisesRegex(ValueError,'SDK_IMPORT_TREE_CHANGED'):
            entry.sdk_preflight({'sdk_manifest':entry.ref(p)})

    def test_route_failure_stops_prepare_before_freezing(self):
        p=self.root/'input.json';p.write_text(json.dumps(self.cfg));out=self.root/'prepared'
        with patch.object(entry,'sdk_preflight'), patch.object(entry,'queue_preflight'), \
                patch.object(entry,'check_route',side_effect=RouteGateError('NLM_ROUTE_LIVE_CHAIN_MISMATCH')):
            with self.assertRaisesRegex(RouteGateError,'LIVE_CHAIN_MISMATCH'):
                entry.prepare(p,out)
        self.assertFalse(out.exists())

    def test_route_failure_stops_run_before_allocation_or_admission(self):
        import nlm_runtime
        with patch.object(entry,'config_checked',return_value=self.cfg), \
                patch.object(entry,'check_route',side_effect=RouteGateError('NLM_ROUTE_PROCESS_RESTARTED')), \
                patch.object(nlm_runtime,'Budget') as budget:
            with self.assertRaisesRegex(RouteGateError,'PROCESS_RESTARTED'):
                entry.run(self.root/'unused.json',self.root/'request.json')
            budget.assert_not_called()

    def test_route_failure_in_actual_transport_prevents_post(self):
        import nlm_sdk_adapter_v3 as adapter
        cfg={**self.cfg};out=Path(cfg['budget_root'])/'receipts'/'request';out.mkdir(parents=True)
        resources=Path(cfg['resource_root']);resources.mkdir()
        request=dict(task_id=cfg['task_id'],operation='query',account_key=cfg['account_key'],
                     notebook_id=cfg['notebook_id'],source_ids=cfg['source_ids'],
                     conversation_id=cfg['conversation_id'],prompt='synthetic')
        (out/'request.json').write_text(json.dumps(request))
        (out/'lease.json').write_text(json.dumps(dict(id='lease',token='token')))
        with sqlite3.connect(resources/'queue.sqlite3') as db:
            db.execute('CREATE TABLE tickets(id,token,status,task_id,resource,pgid,expires)')
            db.execute('INSERT INTO tickets VALUES(?,?,?,?,?,?,?)',('lease','token','ACTIVE',
                cfg['task_id'],'nlm-account:'+cfg['account_key'],os.getpgrp(),entry.time.time()+60))
        with sqlite3.connect(Path(cfg['budget_root'])/'budget.sqlite3') as db:
            db.execute('CREATE TABLE requests(id,task_id,state)')
            db.execute('INSERT INTO requests VALUES(?,?,?)',('request',cfg['task_id'],'STARTED'))
        cookies=self.root/'cookies.json';cookies.write_text('{}')
        metadata=self.root/'metadata.json';metadata.write_text('{}')
        manager=SimpleNamespace(cookies_file=cookies,metadata_file=metadata,
            load_profile=lambda:SimpleNamespace(email=cfg['email'],csrf_token='synthetic',
                session_id='synthetic',cookies={},build_label='synthetic',base_host='notebook.google.com'))
        class Client:
            def __init__(self,**kwargs): pass
            def close(self): pass
        modules={'notebooklm_tools.services.auth':SimpleNamespace(AuthManager=lambda *_:manager),
                 'notebooklm_tools.core.client':SimpleNamespace(NotebookLMClient=Client)}
        with patch.dict(sys.modules,modules), patch.object(entry,'config_checked',return_value=cfg), \
                patch.object(adapter,'jacob_request',return_value=('https://notebook.google.com/query','body','persistent')), \
                patch.object(entry,'check_route',side_effect=RouteGateError('NLM_ROUTE_LIVE_CHAIN_MISMATCH')), \
                patch.object(adapter,'BoundedHTTP') as http, contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(entry.transport('unused','unused',out),2)
            http.assert_not_called()
        self.assertEqual(json.loads(stdout.getvalue()),{'status':'UNCERTAIN','error_type':'RouteGateError'})
        record=json.loads((out/'TRANSPORT.json').read_text())
        self.assertEqual(record['route_gate_failure'],'NLM_ROUTE_LIVE_CHAIN_MISMATCH')
        self.assertTrue(record['auth_files_unchanged'])


if __name__ == '__main__':
    unittest.main()
