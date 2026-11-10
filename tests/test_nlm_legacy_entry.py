"""Synthetic policies and task data only; no live route, broker, SDK or account."""
from contextlib import contextmanager, nullcontext
import copy
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); sys.modules[name] = value; spec.loader.exec_module(value)
    return value


G = load('nlm_network_guard', SCRIPTS / 'nlm_network_guard.py')
L = load('legacy_candidate_under_test', SCRIPTS / 'nlm_legacy_entry.py')


def ref(path):
    path = Path(path).resolve(); body = path.read_bytes()
    return {'path': str(path), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value)); return ref(path)


def checked(value):
    if ref(value['path']) != value: raise ValueError('PIN_CHANGED')
    return Path(value['path'])


def require(ok, message):
    if not ok: raise ValueError(message)


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='legacy-registry-fixture-')
        self.root = Path(self.temp.name).resolve()
        self.python = self.root / 'python'; self.python.write_text('fixture interpreter descriptor')
        self.old = self.policy('old', False); self.new = self.policy('new', True)
        self.registry = self.freeze_registry()

    def tearDown(self): self.temp.cleanup()

    def policy(self, name, legacy):
        root = self.root / name
        script = root / 'source/scripts/nlm_sdk_entry.py'; script.parent.mkdir(parents=True)
        script.write_text('# Synthetic entry: never executed\n')
        route = write(root / 'route.json', {'proxy': 'http://127.0.0.1:49123'})
        contract = write(root / 'contract.json', {'schema': 'fixture-static-contract'})
        policy = {'schema': 'nlm-network-policy-v1', 'policy_role': 'mandatory-domain-route',
                  'required_route_label': 'fixture-approved-chain', 'entry': ref(script), 'python': ref(self.python),
                  'code_pins': [ref(script)], 'route_binding': route}
        if legacy: policy['legacy_contracts'] = [contract]
        policy_ref = write(root / 'policy.json', policy)
        authority = write(root / 'NLM-ROUTE-POLICY-PIN.json',
                          {'schema': 'nlm-network-policy-authority-v1', 'policy': policy_ref})
        cfg = {'schema': 'nlm-legacy-task-v1' if legacy else 'nlm-sdk-task-v1', 'route_policy': policy_ref,
               'route_binding': route, 'proxy': 'http://127.0.0.1:49123', 'python': ref(self.python),
               'scripts': str(script.parent), 'code_pins': [ref(script)]}
        if legacy: cfg['legacy_contract'] = contract
        config = write(root / 'config.json', cfg)
        item = {'entry': ref(script), 'authority': authority, 'policy': policy_ref,
                'modes': ['legacy-run'] if legacy else ['prepare', 'run']}
        return dict(root=root, script=script, policy=policy, item=item, config=config, cfg=cfg, contract=contract)

    def freeze_registry(self):
        return write(self.root / 'registry.json', {'schema': 'nlm-network-entry-registry-v1',
                                                   'entries': [self.old['item'], self.new['item']]})

    def argv(self, which, mode=None):
        mode = mode or ('legacy-run' if which is self.new else 'run')
        return [str(self.python), '-BE', str(which['script']), mode, '--config', which['config']['path'],
                '--output-dir' if mode == 'prepare' else '--request', str(which['root'] / 'request.json')]

    def event(self, argv):
        return {'tool_name': 'exec_command', 'tool_input': {'cmd': shlex.join(argv)}}

    def check(self, argv):
        G.event_check(self.event(argv), lambda: G.load_registry(self.registry['path'], self.registry['sha256']))

    def test_old_prepare_run_and_new_legacy_allowed(self):
        for argv in (self.argv(self.old), self.argv(self.old, 'prepare'), self.argv(self.new)):
            self.check(argv)

    def test_no_cross_entry_modes_or_direct_child(self):
        for argv in (self.argv(self.old, 'legacy-run'), self.argv(self.new, 'run'),
                     self.argv(self.new, 'legacy-transport'), self.argv(self.old, 'transport')):
            with self.subTest(argv=argv), self.assertRaises(G.Denied): self.check(argv)

    def test_arguments_compound_env_and_suffix_refused(self):
        argv = self.argv(self.new)
        bad = [argv + ['--lookup-original'], ['env', 'HTTPS_PROXY=elsewhere', *argv]]
        for value in bad:
            with self.assertRaises(G.Denied): self.check(value)
        for command in (shlex.join(argv) + '; true', shlex.join(argv) + ' > /tmp/fixture',
                        shlex.join(argv) + '\ntrue'):
            with self.assertRaises(G.Denied):
                G.event_check({'tool_name': 'exec_command', 'tool_input': {'cmd': command}},
                              lambda: G.load_registry(self.registry['path'], self.registry['sha256']))

    def test_task_cannot_choose_route_or_policy_or_contract(self):
        for field, value in [('proxy', 'http://127.0.0.1:49999'), ('route_policy', self.old['item']['policy']),
                             ('legacy_contract', self.old['contract']), ('code_pins', [])]:
            write(Path(self.new['config']['path']), {**self.new['cfg'], field: value})
            with self.subTest(field=field), self.assertRaises(G.Denied): self.check(self.argv(self.new))

    def test_legacy_failure_does_not_break_old_sdk(self):
        Path(self.new['contract']['path']).write_text('changed')
        self.check(self.argv(self.old))
        with self.assertRaises(G.Denied): self.check(self.argv(self.new))

    def test_old_failure_does_not_break_new_entry(self):
        Path(self.old['item']['policy']['path']).write_text('changed')
        self.check(self.argv(self.new))
        with self.assertRaises(G.Denied): self.check(self.argv(self.old))

    def test_unapproved_adapter_and_duplicate_registry_refused(self):
        adapter = self.root / 'nlm_old_adapter.py'; adapter.write_text('# original adapter fixture')
        with self.assertRaises(G.Denied): self.check([str(self.python), '-BE', str(adapter), 'run'])
        self.registry = write(Path(self.registry['path']), {'schema': 'nlm-network-entry-registry-v1',
                         'entries': [self.old['item'], self.old['item']]})
        with self.assertRaises(G.Denied): self.check(self.argv(self.old))

    def test_new_legacy_policy_offline_bypass_forbidden(self):
        self.new['policy']['offline_commands'] = [{'argv': self.argv(self.new), 'network': 'none',
                                                    'files': [self.new['item']['entry']]}]
        self.new['item']['policy'] = write(self.new['root'] / 'policy.json', self.new['policy'])
        self.new['item']['authority'] = write(self.new['root'] / 'NLM-ROUTE-POLICY-PIN.json',
             {'schema': 'nlm-network-policy-authority-v1', 'policy': self.new['item']['policy']})
        self.registry = self.freeze_registry()
        with self.assertRaises(G.Denied): self.check(self.argv(self.new))

    def test_real_guard_process_protocol_allow_and_deny(self):
        command = [sys.executable, '-BE', str(SCRIPTS / 'nlm_network_guard.py'), '--registry',
                   self.registry['path'], '--registry-sha256', self.registry['sha256']]
        for argv, code in ((self.argv(self.old), 0), (self.argv(self.new), 0),
                           (self.argv(self.new, 'legacy-transport'), 2)):
            done = subprocess.run(command, input=json.dumps(self.event(argv)), text=True, capture_output=True)
            self.assertEqual(done.returncode, code, done.stderr)
            value = json.loads(done.stdout)
            self.assertEqual(value, {} if code == 0 else {'hookSpecificOutput': value['hookSpecificOutput']})
            if code: self.assertEqual(value['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_explicit_same_release_guard_uses_actual_argv_and_authority(self):
        write(self.new['root'] / 'NLM-GUARD-REGISTRY-PIN.json',
              {'schema': 'nlm-network-entry-registry-authority-v1', 'registry': self.registry})
        entry = types.SimpleNamespace(SCRIPTS=self.new['script'].parent, __file__=str(self.new['script']),
                                      checked=checked, require=require, ref=ref,
                                      read=lambda value: json.loads(checked(value).read_text()),
                                      enforce_route_policy=lambda cfg: G.load_policy(
                                          self.new['item']['policy']['path'], self.new['item']['policy']['sha256'])[1])
        argv = self.argv(self.new)
        with patch.object(sys, 'orig_argv', argv), patch.object(sys, 'executable', str(self.python)):
            result = L.explicit_guard(entry, argv[5], argv[7])
        self.assertEqual(result['status'], 'EXPLICIT_SAME_RELEASE_GUARD_ALLOW')
        self.assertFalse(result['automatic_client_hook_observed'])
        with patch.object(sys, 'orig_argv', argv + ['--extra']), self.assertRaises(ValueError):
            L.explicit_guard(entry, argv[5], argv[7])


    def framework_fixture(self):
        # 完全合成的framework与kernel回件，跨平台测试不访问真实进程或网络。
        version = self.root / 'Synthetic.framework/Versions/fixture'
        self.python = version / 'bin/python'; self.python.parent.mkdir(parents=True)
        self.python.write_text('synthetic pinned launcher')
        runtime = version / 'Resources/Python.app/Contents/MacOS/Python'
        runtime.parent.mkdir(parents=True); runtime.write_text('synthetic pinned runtime')
        compat = {'kind': 'macos-framework-launcher-v1', 'launcher': ref(self.python), 'runtime': ref(runtime)}
        self.new['policy'].update(python=ref(self.python), python_invocation_compat=compat)
        self.new['item']['policy'] = write(self.new['root'] / 'policy.json', self.new['policy'])
        self.new['item']['authority'] = write(self.new['root'] / 'NLM-ROUTE-POLICY-PIN.json',
            {'schema': 'nlm-network-policy-authority-v1', 'policy': self.new['item']['policy']})
        self.new['cfg'].update(python=ref(self.python), route_policy=self.new['item']['policy'])
        self.new['config'] = write(self.new['root'] / 'config.json', self.new['cfg'])
        self.registry = self.freeze_registry()
        write(self.new['root'] / 'NLM-GUARD-REGISTRY-PIN.json',
              {'schema': 'nlm-network-entry-registry-authority-v1', 'registry': self.registry})
        entry = types.SimpleNamespace(SCRIPTS=self.new['script'].parent, __file__=str(self.new['script']),
            checked=checked, require=require, ref=ref, read=lambda value: json.loads(checked(value).read_text()),
            enforce_route_policy=lambda cfg: G.load_policy(
                self.new['item']['policy']['path'], self.new['item']['policy']['sha256'])[1])
        argv = self.argv(self.new); argv[0] = str(runtime)
        return entry, argv, runtime

    def framework_call(self, entry, argv, runtime, *, platform='darwin', process_image=None, executable=None):
        class ProcessPath:
            def __call__(self, pid, buffer, length):
                buffer.value = str(process_image or runtime).encode(); return len(buffer.value)
        with patch.object(sys, 'orig_argv', argv), patch.object(sys, 'platform', platform), \
             patch.object(sys, 'executable', str(executable or self.python)), \
             patch.object(ctypes, 'CDLL', return_value=types.SimpleNamespace(proc_pidpath=ProcessPath())):
            return L.explicit_guard(entry, self.new['config']['path'], str(self.new['root'] / 'request.json'))

    def test_framework_runtime_header_requires_pinned_process_mapping(self):
        entry, argv, runtime = self.framework_fixture()
        # 原guard直接看到app头会拒绝；兼容层核全证据后把原尾7项交回同一guard。
        with self.assertRaisesRegex(G.Denied, 'PINNED_ENTRY_REQUIRED'): self.check(argv)
        result = self.framework_call(entry, argv, runtime)
        self.assertEqual(result['invocation']['raw_orig_argv'], argv)
        self.assertEqual(result['invocation']['guard_argv'], [str(self.python), *argv[1:]])
        self.assertEqual(result['invocation']['runtime'], ref(runtime))
        self.assertEqual(result['invocation']['process_image'], str(runtime))

    def test_framework_missing_changed_or_cross_framework_mapping_refused(self):
        entry, argv, runtime = self.framework_fixture()
        base = copy.deepcopy(self.new['policy'])
        absent = copy.deepcopy(base); absent.pop('python_invocation_compat')
        bad_pin = copy.deepcopy(base); bad_pin['python_invocation_compat']['runtime']['sha256'] = '0' * 64
        cross = copy.deepcopy(base); cross['python_invocation_compat']['runtime'] = ref(self.python)
        wrong_launcher = copy.deepcopy(base); wrong_launcher['python_invocation_compat']['launcher'] = ref(runtime)
        for label, policy in [('missing', absent), ('bad_pin', bad_pin), ('cross', cross), ('launcher', wrong_launcher)]:
            with self.subTest(label=label), patch.object(entry, 'enforce_route_policy', return_value=policy), \
                 self.assertRaises(ValueError):
                self.framework_call(entry, argv, runtime)

    def test_framework_process_platform_executable_and_tail_refused(self):
        entry, argv, runtime = self.framework_fixture()
        for label, kw in [('platform', {'platform': 'linux'}), ('kernel_image', {'process_image': self.python}),
                          ('sys_executable', {'executable': runtime})]:
            with self.subTest(label=label), self.assertRaises(ValueError): self.framework_call(entry, argv, runtime, **kw)
        for changed in (argv + ['--extra'], [*argv[:-1], str(self.root / 'different-request.json')]):
            with self.subTest(argv=changed), self.assertRaises(ValueError): self.framework_call(entry, changed, runtime)



class LegacyFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='legacy-flow-fixture-'); self.root = Path(self.temp.name).resolve()
        self.events = []
        self.entry = types.SimpleNamespace(require=require, checked=checked, ref=ref,
            read=lambda value: json.loads(checked(value).read_text()), phase_deadline=lambda *a: nullcontext(),
            PREFLIGHT_SECONDS=30, __file__=str(self.root / 'nlm_sdk_entry.py'),
            enforce_route_policy=lambda cfg: self.events.append('authority'),
            actor_check=lambda cfg: self.events.append('actor'))
        def route(cfg, phase, **kw):
            self.events.append('fresh_route:' + phase); return {'phase': phase, 'service_region_verified': False}
        self.entry.check_route = route
        self.raw = {'task_id': 'fixture-task', 'notebook_id': 'fixture-notebook', 'operation': 'query',
                    'source_ids': ['source-a', 'source-b'], 'prompt': 'unchanged fixture question'}
        self.question = write(self.root / 'question.json', self.raw)
        broker = write(self.root / 'broker.json', {'fixture_only': True})
        self.cfg = {'task_id': 'fixture-task', 'account_key': 'fixture-account', 'notebook_id': 'fixture-notebook',
                    'budget_root': str(self.root / 'budget'), 'resource_root': str(self.root / 'resources'),
                    'query_budget': 48, 'proxy': 'http://127.0.0.1:49123', 'python': {'path': '/fixture/python'},
                    'actor': {'thread_id': 'fixture-owner'}}
        legacy = {**self.cfg, 'original_submit_lock': str(self.root / 'original.lock'),
                  'limits': {'query_total_seconds': 240, 'connect_seconds': 15}, 'original_controller': broker}
        self.cfg['legacy_config'] = write(self.root / 'legacy_config.json', legacy)
        self.contract = {k: self.cfg[k] for k in ('task_id', 'account_key', 'notebook_id', 'budget_root', 'resource_root', 'query_budget')}
        self.contract.update(original_request=self.question, original_submit_lock=legacy['original_submit_lock'],
            limits=legacy['limits'], broker_module=broker, original_controller_alias=broker,
            superseded_unsubmitted_keys=['old-unsubmitted'],
            adapter={'path': str(self.root / 'adapter.py')})
        self.cfg['legacy_contract'] = write(self.root / 'contract.json', self.contract)
        self.cfg_ref = write(self.root / 'CFG.json', self.cfg)
        self.binding = {'broker_module': broker, 'resource_root': self.cfg['resource_root'],
            'transport_artifacts': [self.cfg_ref], 'commands': {'query': ['/fixture/python', '-BE', self.entry.__file__,
            'legacy-transport', '--config', self.cfg_ref['path'], '--config-sha256', self.cfg_ref['sha256'],
            '--output-dir', '{output_dir}']}}
        self.bind_ref = write(self.root / 'binding.json', self.binding)
        self.op = {'request': self.question, 'config': self.cfg['legacy_config'], 'binding': self.bind_ref}
        self.op_ref = write(self.root / 'operation.json', self.op)
        class Budget:
            def __init__(inner, root): inner.root = Path(root)
            def admit(inner, *a): return None
        class PrivateBudget(Budget): pass
        self.runtime = types.SimpleNamespace(Budget=Budget, verified_prior=object(), request_key=lambda req: 'new-fixture-key')
        def run_bound(binding, req, budget):
            self.events.append('original_run_bound'); return {'status': 'COMPLETE', 'fixture_only': True}
        self.runtime.run_bound = run_bound
        self.adapter = types.SimpleNamespace(
            validate_operation_adoption=lambda *a, **kw: (self.op, legacy, self.binding),
            S=types.SimpleNamespace(transport_contract=lambda b: 'new-fixture-contract'),
            original=types.SimpleNamespace(), Q=types.SimpleNamespace(E=types.SimpleNamespace(reconciliation=lambda: None)))
        def derive(original, name, edits, extra):
            def execute(op, output):
                extra['validate_operation_adoption'](op)
                output.mkdir(); self.events.append('original_execute_and_lock')
                proxy = extra['legacy_runtime'](); budget = proxy.Budget(self.cfg['budget_root'])
                return proxy.run_bound(self.binding, {**self.raw, 'execution_adoption': self.op_ref}, budget)
            return execute
        self.adapter.B = types.SimpleNamespace(derive=derive, save=lambda path, value: write(path, value))
        self.bridge = types.SimpleNamespace(private_budget=lambda *a: PrivateBudget)
        self.ctx = (self.cfg_ref, self.cfg, self.contract, self.bridge, self.adapter, self.runtime)
        self.spec = {'schema': 'nlm-legacy-run-spec-v1', 'config': self.cfg_ref, 'binding': self.bind_ref,
            'operation_adoption': self.op_ref, 'request_key': 'new-fixture-key',
            'execution_output': str(self.root / 'execution'),
            'prepared': write(self.root / 'prepared.json', {'config': self.cfg['legacy_config'], 'binding': self.bind_ref})}
        adopted = {'schema': 'nlm-named-legacy-run-adoption-v1', 'status': 'ADOPTED_ONE_ORIGINAL_QUESTION',
            'task_id': self.cfg['task_id'], 'account_key': self.cfg['account_key'], 'notebook_id': self.cfg['notebook_id'],
            'supervisor_session': 'fixture-owner', 'config': self.cfg_ref, 'legacy_contract': self.cfg['legacy_contract'],
            'request': self.question, 'prepared': self.spec['prepared'], 'binding': self.bind_ref,
            'operation_adoption': self.op_ref, 'request_key': 'new-fixture-key', 'query_cap': 1,
            'automatic_retry': False, 'prior_attempts_preserved': True}
        self.spec['recovery_decision'] = write(self.root / 'decision.json', adopted)
        self.spec_ref = write(self.root / 'RUN_SPEC.json', self.spec)

    def tearDown(self): self.temp.cleanup()

    def test_metadata_preserves_original_request_and_controlled_child(self):
        _, _, _, request, key = L.metadata(self.entry, self.ctx, self.op_ref)
        self.assertEqual(request['prompt'], self.raw['prompt']); self.assertEqual(key, 'new-fixture-key')
        self.binding['commands']['query'][3] = 'transport'
        with self.assertRaisesRegex(ValueError, 'CONTROLLED_INTERNAL_CHILD'): L.metadata(self.entry, self.ctx, self.op_ref)

    def test_old_key_and_changed_proxy_refused(self):
        self.runtime.request_key = lambda req: 'old-unsubmitted'
        with self.assertRaisesRegex(ValueError, 'SUPERSEDED_KEY'): L.metadata(self.entry, self.ctx, self.op_ref)
        self.runtime.request_key = lambda req: 'new-fixture-key'
        self.cfg['proxy'] = 'http://127.0.0.1:49999'
        with self.assertRaisesRegex(ValueError, 'APPROVED_PROXY'): L.metadata(self.entry, self.ctx, self.op_ref)

    def test_controller_alias_preserved_and_resolves_to_approved_bytes(self):
        physical = self.contract['broker_module']; alias_path = self.root / 'original_broker_alias'
        alias_path.symlink_to(physical['path'])
        alias = {'path': str(alias_path), 'sha256': physical['sha256']}
        legacy = self.entry.read(self.cfg['legacy_config']); legacy['original_controller'] = alias
        self.cfg['legacy_config'] = write(Path(self.cfg['legacy_config']['path']), legacy)
        self.op['config'] = self.cfg['legacy_config']; self.binding['broker_module'] = alias
        self.contract['original_controller_alias'] = alias
        self.adapter.validate_operation_adoption = lambda *a, **kw: (self.op, legacy, self.binding)
        L.metadata(self.entry, self.ctx, self.op_ref)
        other = self.root / 'other_broker'; other.write_text('other bytes')
        alias_path.unlink(); alias_path.symlink_to(other)
        with self.assertRaisesRegex(ValueError, 'ORIGINAL_CONTROLLER'): L.metadata(self.entry, self.ctx, self.op_ref)

    def run_fixture(self):
        with patch.object(L, 'local_validation_limit', return_value=120), patch.object(L, 'context', return_value=self.ctx), patch.object(L, 'explicit_guard',
                side_effect=lambda *a: self.events.append('explicit_guard') or {'status': 'fixture-allow'}):
            return L.run(self.entry, self.cfg_ref['path'], self.spec_ref['path'])

    def test_parent_gate_precedes_exact_original_run_bound(self):
        self.run_fixture()
        self.assertEqual(self.events, ['explicit_guard', 'original_execute_and_lock', 'authority', 'actor',
                                      'fresh_route:legacy_pre_admission', 'original_run_bound'])
        self.assertTrue((self.root / 'execution/EXPLICIT-NETWORK-GUARD.json').is_file())

    def test_failed_route_does_not_reach_original_admission(self):
        self.entry.check_route = lambda *a, **kw: (_ for _ in ()).throw(ValueError('ROUTE_REJECTED'))
        with self.assertRaisesRegex(ValueError, 'ROUTE_REJECTED'): self.run_fixture()
        self.assertNotIn('original_run_bound', self.events)

    def test_new_key_requires_new_root_decision(self):
        value = json.loads(Path(self.spec['recovery_decision']['path']).read_text()); value['request_key'] = 'old-unsubmitted'
        self.spec['recovery_decision'] = write(Path(self.spec['recovery_decision']['path']), value)
        write(Path(self.spec_ref['path']), self.spec)
        with self.assertRaisesRegex(ValueError, 'ROOT_ADOPTION'): self.run_fixture()
        self.assertNotIn('original_execute_and_lock', self.events)

    def test_local_limit_only_from_approved_static_contract(self):
        path = self.root / 'bounded_static_contract.json'
        value = {'schema': 'nlm-legacy-task-contract-v1', 'status': 'APPROVED_STATIC_LEGACY_CONTRACT',
                 'local_validation_seconds': 120}
        selected = write(path, value)
        config = write(self.root / 'limit_config.json', {'legacy_contract': selected, 'local_validation_seconds': 9999})
        policy = {'legacy_contracts': [selected]}
        self.entry.enforce_route_policy = lambda cfg: policy
        self.assertEqual(L.local_validation_limit(self.entry, config['path']), 120)
        for seconds in (0, -1, True, 121, 120.5):
            selected = write(path, {**value, 'local_validation_seconds': seconds})
            config = write(Path(config['path']), {'legacy_contract': selected})
            policy['legacy_contracts'] = [selected]
            with self.subTest(seconds=seconds), self.assertRaisesRegex(ValueError, 'BOUNDED_APPROVED'):
                L.local_validation_limit(self.entry, config['path'])
        policy['legacy_contracts'] = []
        with self.assertRaisesRegex(ValueError, 'REGISTERED_LEGACY_CONTRACT'):
            L.local_validation_limit(self.entry, config['path'])

    def test_simulated_46_second_local_validation_fits_120_not_sdk30(self):
        elapsed = [0.0]; phases = []
        @contextmanager
        def deadline(seconds, label):
            began = elapsed[0]; phases.append((seconds, label))
            yield
            if elapsed[0] - began >= seconds: raise TimeoutError(label)
        self.entry.phase_deadline = deadline
        def context(*a): elapsed[0] += 46.812; return self.ctx
        with patch.object(L, 'local_validation_limit', return_value=120), patch.object(L, 'context', side_effect=context), \
             patch.object(L, 'explicit_guard', return_value={'status': 'fixture-allow'}):
            L.run(self.entry, self.cfg_ref['path'], self.spec_ref['path'])
        self.assertIn((120, 'LEGACY_LOCAL_VALIDATION_DEADLINE'), phases)
        self.assertIn((30, 'LEGACY_PRE_ADMISSION_ROUTE_30_SECONDS'), phases)
        self.assertIn((120, 'LEGACY_ORIGINAL_ENTRY_VALIDATION_DEADLINE'), phases)
        self.assertIn('original_run_bound', self.events)

    def test_simulated_local_budget_exhaustion_refuses_before_execute(self):
        elapsed = [0.0]
        @contextmanager
        def deadline(seconds, label):
            began = elapsed[0]
            yield
            if elapsed[0] - began >= seconds: raise TimeoutError(label)
        self.entry.phase_deadline = deadline
        def context(*a): elapsed[0] += 120.001; return self.ctx
        with patch.object(L, 'local_validation_limit', return_value=120), patch.object(L, 'context', side_effect=context), \
             patch.object(L, 'explicit_guard', return_value={'status': 'fixture-allow'}), self.assertRaises(TimeoutError):
            L.run(self.entry, self.cfg_ref['path'], self.spec_ref['path'])
        self.assertNotIn('original_execute_and_lock', self.events)

    def child_fixture(self, *, gate=True):
        folder = Path(self.cfg['budget_root']) / 'receipts/new-fixture-key'; folder.mkdir(parents=True)
        request = {**self.raw, 'execution_adoption': self.op_ref, 'account_key': self.cfg['account_key'],
                   'transport_contract': 'new-fixture-contract'}
        (folder / 'request.json').write_text(json.dumps(request))
        def configure(adapter, cfg, callback, *, validate_operation):
            def main():
                self.events.append(('original_clock_started', os.getpid(), os.getpgrp()))
                validate_operation(self.op_ref, request)
                if gate: callback('notebook.google.com')
                self.events.append('one_original_send'); return 0
            return types.SimpleNamespace(__file__='/fixture/original_transport.py', main=main)
        self.bridge.configure_child = configure
        with patch.object(L, 'context', return_value=self.ctx):
            return L.transport(self.entry, self.cfg_ref['path'], self.cfg_ref['sha256'], str(folder))

    def test_child_gate_after_clock_same_process_before_send(self):
        self.assertEqual(self.child_fixture(), 0)
        self.assertEqual(self.events[0], ('original_clock_started', os.getpid(), os.getpgrp()))
        self.assertLess(self.events.index('fresh_route:legacy_query_send'), self.events.index('one_original_send'))

    def test_child_route_failure_blocks_send_and_missing_gate_fails_success(self):
        self.entry.check_route = lambda *a, **kw: (_ for _ in ()).throw(ValueError('ROUTE_REJECTED'))
        with self.assertRaisesRegex(ValueError, 'ROUTE_REJECTED'): self.child_fixture()
        self.assertNotIn('one_original_send', self.events)

    def test_success_without_send_gate_refused(self):
        with self.assertRaisesRegex(ValueError, 'SUCCESS_WITHOUT_MANDATORY_SEND_GATE'): self.child_fixture(gate=False)


if __name__ == '__main__': unittest.main(verbosity=2)
