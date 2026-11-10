import base64
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import py_compile
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import nlm_sdk_entry as entry


@unittest.skipUnless(sys.version_info >= (3, 11), 'SDK entry requires Python 3.11+')
class LocalBoundaries(unittest.TestCase):
    def test_preflight_phase_is_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config.json';p.write_text('{}')
            with patch.object(entry,'PREFLIGHT_SECONDS',.03), patch.object(entry,'_config_checked',side_effect=lambda *_:time.sleep(2)):
                started=time.monotonic()
                with self.assertRaisesRegex(TimeoutError,'CONFIG_PREFLIGHT'):
                    entry.config_checked(p)
                self.assertLess(time.monotonic()-started,1)

    def test_child_preflight_timeout_uses_reserved_unknown_exit(self):
        with patch.object(sys, 'argv', ['entry', 'transport', '--config', 'unused',
                '--config-sha256', 'unused', '--output-dir', 'unused']), \
                patch.object(entry, 'transport', side_effect=TimeoutError('synthetic')):
            self.assertEqual(entry.main(), 124)

    def test_cleanup_phase_is_bounded(self):
        class Client:
            def close(self):time.sleep(2)
        with self.assertRaisesRegex(TimeoutError,'CLEANUP'):
            with entry.phase_deadline(.03,'CLEANUP_5_SECONDS'):
                Client().close()

    def test_extra_valid_bytecode_is_rejected_before_sdk_import(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);module=root/'cached.py';module.write_text('value="never executed"\n')
            original=entry.ref(module)
            py_compile.compile(str(module),doraise=True,
                               invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
            manifest=root.parent/(root.name+'-manifest.json')
            self.addCleanup(manifest.unlink,missing_ok=True)
            manifest.write_text(json.dumps(dict(schema='nlm-sdk-environment-v1',import_roots=[str(root)],
                files=[original],sources=[],versions={})))
            with self.assertRaisesRegex(ValueError,'SDK_BYTECODE_CACHE_FORBIDDEN'):
                entry.sdk_preflight({'sdk_manifest':entry.ref(manifest)})
            self.assertNotIn('cached',sys.modules)

    def test_cache_added_after_check_is_never_executed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);name='sdk_guard_fixture';module=root/(name+'.py')
            module.write_text('value="checked source"\n');pin=entry.ref(module)
            finder=entry.PinnedImportFinder([root],[pin])
            module.write_text('value="unchecked cache"\n')
            py_compile.compile(str(module),doraise=True,
                               invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
            module.write_text('value="checked source"\n')
            sys.path.insert(0,str(root));sys.meta_path.insert(0,finder)
            try:
                self.assertEqual(importlib.import_module(name).value,'checked source')
            finally:
                sys.meta_path.remove(finder);sys.path.remove(str(root));sys.modules.pop(name,None)

    def test_sourceless_bytecode_added_after_check_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);name='sdk_sourceless_fixture';module=root/(name+'.py')
            module.write_text('value="untrusted"\n')
            py_compile.compile(str(module),cfile=str(root/(name+'.pyc')),doraise=True);module.unlink()
            finder=entry.PinnedImportFinder([root],[])
            sys.path.insert(0,str(root));sys.meta_path.insert(0,finder)
            try:
                with self.assertRaisesRegex(ValueError,'SDK_BYTECODE_IMPORT_FORBIDDEN'):
                    importlib.import_module(name)
            finally:
                sys.meta_path.remove(finder);sys.path.remove(str(root));sys.modules.pop(name,None)


@unittest.skipUnless(sys.version_info >= (3, 11) and os.environ.get('COLLABORATION_BROKER'),
                     'set COLLABORATION_BROKER for actual original broker integration')
class OriginalBrokerDeadlines(unittest.TestCase):
    def test_preflight_stream_and_cleanup_hangs_preserve_unknown_budget_and_lease(self):
        import nlm_runtime as runtime
        original_factory=entry.bounded_broker
        for stage in ('preflight','stream','cleanup','quota_stdout','quota_stderr','429_stdout','auth_stderr','child_timeout_quota','normal_quota','provider_region'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as d:
                root=Path(d);script=root/'child.py';counter=root/'synthetic-post-count.txt'
                # No network: model a zero-send preflight, one-send blocked stream,
                # and a complete-looking answer followed by a hung client.close.
                expected_stdout = expected_stderr = b''
                if stage in {'cleanup','quota_stdout','429_stdout'}:
                    value = dict(answer='quota exceeded' if stage=='quota_stdout' else 'complete-looking',
                        sources_used=['source'], citations={'1':'source'}, conversation_id='persistent', notebook_id='book')
                    if stage=='429_stdout':value['status']=429
                    expected_stdout=(json.dumps(value)+'\r\n').encode()
                if stage in {'quota_stderr','child_timeout_quota','normal_quota'}:expected_stderr=b'quota exceeded\r\n'
                if stage=='auth_stderr':expected_stderr=b'auth failed; unauthorized; token expired\r\nraw-byte:\xff'
                if stage=='provider_region':
                    expected_stdout=b'{"status":"UNCERTAIN","error_type":"ProviderApplicationError"}\n'
                script.write_text('import os,signal,time\nfrom pathlib import Path\n'
                    'signal.signal(signal.SIGTERM,signal.SIG_IGN)\n'
                    +('' if stage=='preflight' else f'Path({str(counter)!r}).write_text("1")\n')
                    +f'os.write(1,{expected_stdout!r})\nos.write(2,{expected_stderr!r})\n'
                    +'class Client:\n def close(self):time.sleep(30)\n'
                    +('raise SystemExit(124)\n' if stage=='child_timeout_quota' else 'raise SystemExit(2)\n' if stage in {'normal_quota','provider_region'} else 'Client().close()\n' if stage=='cleanup' else 'time.sleep(30)\n'))
                broker=entry.ref(os.environ['COLLABORATION_BROKER'])
                cfg=dict(account_key='a',notebook_id='book',target_id='test-only',
                    workspace_uuid='11111111-1111-1111-1111-111111111111',
                    surface_uuid='22222222-2222-2222-2222-222222222222',
                    existing_target_only=True,no_navigation=True,no_login=True,no_default_write=True,
                    no_browser_launch=True,broker_module=broker,resource_root=str(root/'resources'),
                    external_locks=[],transport_artifacts=[entry.ref(script)],lease_ttl=360,
                    commands={'query':[sys.executable,'-BE',str(script),'--output-dir','{output_dir}']})
                budget=runtime.Budget(root/'budget');budget.configure('a',dict(regime='unknown',observed_at=1,source='synthetic'))
                budget.allocate('a','task',2)
                request=dict(task_id='task',operation='query',round_id=stage,prompt='synthetic',phase='final',
                             source_ids=['source'],document_sha256='a'*64,conversation_id='persistent')
                started=time.monotonic()
                with patch.object(entry,'bounded_broker',side_effect=lambda m:original_factory(m,total=2,drain=.1)), entry.bounded_runtime(runtime):
                    result=runtime.run_bound(cfg,request,budget)
                self.assertLess(time.monotonic()-started,5)
                receipt=json.loads(Path(result['receipt']['path']).read_text())
                out=Path(result['receipt']['path']).parent
                module=runtime.broker_module(cfg);queue=module.Broker(cfg['resource_root'])
                ticket=queue.get(receipt['resource_lease']['id'])
                if stage=='provider_region':
                    self.assertEqual(result['status'],'UNCERTAIN')
                    self.assertEqual(receipt['exit_code'],2)
                    self.assertFalse(receipt['remote_terminal']);self.assertFalse(receipt['quota_limited'])
                    self.assertEqual(ticket['status'],'ACTIVE')
                    self.assertEqual(budget.report('a')['query_count'],1)
                    self.assertEqual(json.loads((out/'raw.json').read_text()),
                        {'status':'UNCERTAIN','error_type':'ProviderApplicationError'})
                    queue.db.close();budget.db.close();continue
                if stage=='normal_quota':
                    self.assertEqual(result['status'],'FAILED')
                    self.assertEqual(receipt['exit_code'],2)
                    self.assertTrue(receipt['remote_terminal']);self.assertTrue(receipt['quota_limited'])
                    self.assertEqual(ticket['status'],'RELEASED')
                    self.assertEqual(budget.report('a')['query_count'],1)
                    self.assertFalse((out/'SDK-DEADLINE-OUTPUT.json').exists())
                    self.assertEqual((out/'stderr.txt').read_text(),'quota exceeded\n')
                    queue.db.close();budget.db.close();continue
                self.assertEqual(result['status'],'UNCERTAIN')
                self.assertEqual(receipt['exit_code'],124)
                self.assertFalse(receipt['remote_terminal']);self.assertFalse(receipt['quota_limited'])
                self.assertTrue(receipt['process_group_empty'])
                evidence=json.loads((out/'SDK-DEADLINE-OUTPUT.json').read_text())
                self.assertTrue(evidence['capture_complete'])
                self.assertEqual(evidence['ticket_id'],ticket['id'])
                for name,original in [('stdout',expected_stdout),('stderr',expected_stderr)]:
                    saved=evidence['streams'][name]
                    self.assertEqual(base64.b64decode(saved['base64']),original)
                    self.assertEqual(saved['bytes'],len(original))
                    self.assertEqual(saved['sha256'],hashlib.sha256(original).hexdigest())
                self.assertEqual(json.loads((out/'raw.json').read_text()),
                    {'status':'UNCERTAIN','error_type':'SDK_CHILD_HARD_DEADLINE'})
                self.assertEqual(budget.db.execute("SELECT count(*) FROM requests WHERE state='UNCERTAIN'").fetchone()[0],1)
                self.assertEqual(budget.report('a')['query_count'],1)
                with self.assertRaisesRegex(runtime.AdmissionError,'IN_FLIGHT'):
                    budget.admit('a',{**request,'notebook_id':'book','round_id':'second'})
                self.assertEqual(ticket['status'],'ACTIVE');self.assertEqual(ticket['invocations'],1)
                self.assertIsNone(ticket['release_proof']);self.assertIsNone(ticket['pgid'])
                self.assertEqual(counter.read_text() if counter.exists() else '0','0' if stage=='preflight' else '1')
                queue.db.close();budget.db.close()


if __name__=='__main__':unittest.main()
