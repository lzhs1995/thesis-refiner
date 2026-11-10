import copy
import importlib.util
import json
from pathlib import Path
import shlex
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('offline_guard_under_test', ROOT / 'scripts/nlm_offline_preparation_guard.py')
D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)


class OfflinePreparationGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='offline-guard-fixture-')
        self.p = Path(self.tmp.name).resolve(); self.python = D.file_ref(sys.executable)[0]
        self.delegate = D.file_ref(ROOT / 'scripts/nlm_network_guard.py')[0]
        self.policy = self.network_policy('original')
        self.outer = {'schema':'nlm-offline-preparation-dispatch-registry-v1','network_guard':self.delegate,
            'network_authority':{'kind':'policy','file':self.policy['policy']},'offline_preparations':[]}

    def tearDown(self): self.tmp.cleanup()

    def write(self, path, value):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value,indent=2)+'\n'); path.chmod(0o600)
        return D.file_ref(path)[0]

    def script(self, name, body='# NLM offline fixture only\n'):
        p=self.p/name; p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body)
        return D.file_ref(p)[0]

    def item(self, action='static', apply=False):
        install=action=='maintenance-install'; script=self.script('install_once.py' if install else 'root_prepare_once.py')
        supplied={'schema':'fixture-input-v1','wrapper':script}
        authority={'schema':'fixture-authority-v1','status':'AUTHORIZED_ONE_LOCAL_INSTALL' if install else 'AUTHORIZED_OFFLINE_PREPARATION',
            'root_session':'fixture-root','supervisor_session':'fixture-root','network_queries_authorized':0,
            'network_calls_authorized':0,'runtime_execution_authorized':False,'budget_admission_authorized':False}
        if install: authority['approved_input']=dict(supplied)
        else: supplied['stage']=action;authority.update(stage=action,wrapper=script)
        auth=self.write(self.p/'authorization.json',authority);supplied['authorization']=auth
        inp=self.write(self.p/'input.json',supplied)
        argv=[self.python['path'],'-BE',script['path']]+([] if install else [action])
        if apply:
            argv+=['--input',inp['path'],'--input-sha256',inp['sha256'],'--self-sha256',script['sha256']]
            if install: argv+=['--plan-sha256','a'*64]
            argv+=['--apply']
        elif install: argv+=['--input',inp['path']]
        item={'schema':'nlm-offline-preparation-v1','id':'fixture-'+action,'action':action,'argv':argv,
            'python':self.python,'script':script,'input':inp,'authorization':auth,
            'input_schema':supplied['schema'],'authorization_schema':authority['schema'],'root_session':'fixture-root',
            'dependencies':[self.write(self.p/'dependency.json',{'fixture_only':True})],'network':'none'}
        if install:item['plan_sha256']='a'*64
        return item

    def network_policy(self,name,legacy=False):
        entry=self.script(name+'/source/scripts/nlm_sdk_entry.py','# NLM network fixture, never executed\n')
        route=self.write(self.p/name/'route.json',{'proxy':'http://fixture.invalid:1'})
        contract=self.write(self.p/name/'contract.json',{'fixture_only':True})
        body={'schema':'nlm-network-policy-v1','policy_role':'mandatory-domain-route','required_route_label':'fixture',
            'route_binding':route,'entry':entry,'python':self.python,'code_pins':[entry],
            'legacy_contracts':[contract],'offline_commands':[]}
        policy=self.write(self.p/name/'policy.json',body)
        authority=self.write(self.p/name/'NLM-ROUTE-POLICY-PIN.json',{'schema':'nlm-network-policy-authority-v1','policy':policy})
        cfg=self.write(self.p/name/'config.json',{'schema':'nlm-legacy-task-v1' if legacy else 'nlm-sdk-task-v1',
            'route_policy':policy,'route_binding':route,'python':self.python,'proxy':'http://fixture.invalid:1',
            'code_pins':[entry],'scripts':str(Path(entry['path']).parent),'legacy_contract':contract})
        return {'policy':policy,'entry':entry,'authority':authority,'cfg':cfg}

    def loader(self):
        ref=self.write(self.p/'outer.json',self.outer)
        return lambda:D.load_registry(ref['path'],ref['sha256'])

    def event(self,argv): return {'tool_name':'exec_command','tool_input':{'cmd':shlex.join(argv)}}

    def test_exact_static_prepare_and_install_actions(self):
        for action in ('static','prepare','maintenance-install'):
            for apply in (False,True):
                with self.subTest(action=action,apply=apply):
                    item=self.item(action,apply);self.outer['offline_preparations']=[item]
                    result=D.event_check(self.event(['rtk','proxy']+item['argv']),self.loader())
                    self.assertEqual(result['network'],'none')

    def test_changed_script_input_authorization_and_dependency_rejected(self):
        for target in ('script','input','authorization','dependency'):
            with self.subTest(target=target):
                item=self.item();self.outer['offline_preparations']=[item];loader=self.loader()
                ref=item['dependencies'][0] if target=='dependency' else item[target]
                p=Path(ref['path']);p.write_bytes(p.read_bytes()+b' ')
                with self.assertRaisesRegex(ValueError,'PIN_CHANGED'):D.event_check(self.event(item['argv']),loader)

    def test_inspect_does_not_authorize_apply_suffix_or_shell(self):
        item=self.item();self.outer['offline_preparations']=[item];loader=self.loader()
        for argv in (item['argv']+['--apply'],['env','X=1']+item['argv'],item['argv']+[';','echo','extra']):
            with self.subTest(argv=argv),self.assertRaises(ValueError):D.event_check(self.event(argv),loader)

    def test_read_of_registered_script_is_still_delegated(self):
        item=self.item();self.outer['offline_preparations']=[item]
        self.assertIsNone(D.event_check(self.event(['rtk','proxy','cat',item['script']['path']]),self.loader()))

    def test_exact_outer_exec_wrapper_string_and_code_object(self):
        item=self.item();self.outer['offline_preparations']=[item]
        args={'cmd':shlex.join(['rtk','proxy']+item['argv']), 'workdir':str(self.p),
              'max_output_tokens':1000,'yield_time_ms':1000}
        code='text(await tools.exec_command('+json.dumps(args)+'));'
        for value in (code, {'code':code}):
            with self.subTest(value_type=type(value).__name__):
                result=D.event_check({'tool_name':'functions.exec','tool_input':value},self.loader())
                self.assertEqual(result['network'],'none')

    def test_outer_wrapper_extra_dynamic_or_second_call_has_no_offline_allow(self):
        item=self.item();self.outer['offline_preparations']=[item]
        args=json.dumps({'cmd':shlex.join(item['argv'])})
        code='text(await tools.exec_command('+args+'));'
        variants=[code+' text("extra");', code+code,
                  'text(await tools.exec_command('+args[:-1]+', "yield_time_ms":delay}));',
                  'text(await tools.exec_command('+args[:-1]+', "env":{}}));',
                  'text(await tools.exec_command('+args[:-1]+', "cmd":"echo extra"}));']
        variants += ['text(await tools.exec_command('+args[:-1]+', "yield_time_ms":'+v+'}));'
                     for v in ('NaN','Infinity','-Infinity','true')]
        for variant in variants:
            with self.subTest(variant=variant),self.assertRaises(ValueError):
                D.event_check({'tool_name':'functions.exec','tool_input':variant},self.loader())

    def test_network_script_cannot_be_disguised_as_offline(self):
        item=self.item();item['script']=self.policy['entry'];item['argv'][2]=item['script']['path']
        with self.assertRaisesRegex(ValueError,'PREPARER_SCRIPT_REQUIRED'):D.validate_offline_preparation(item)

    def test_known_budget_or_route_call_rejected_even_with_new_pin(self):
        item=self.item();p=Path(item['script']['path']);p.write_text('def main():\n    client.run_bound()\n')
        item['script']=D.file_ref(p)[0]
        with self.assertRaisesRegex(ValueError,'NETWORK_OR_BUDGET_CALL_FORBIDDEN'):D.validate_offline_preparation(item)

    def test_missing_dependency_and_network_flag_rejected(self):
        item=self.item();item['dependencies']=[]
        with self.assertRaisesRegex(ValueError,'DEPENDENCIES_REQUIRED'):D.validate_offline_preparation(item)
        item=self.item();item['network']='allowed'
        with self.assertRaisesRegex(ValueError,'SCHEMA_REQUIRED'):D.validate_offline_preparation(item)

    def test_maintenance_scope_cannot_authorize_network(self):
        item=self.item('maintenance-install');auth=json.loads(Path(item['authorization']['path']).read_text())
        auth['network_queries_authorized']=1;item['authorization']=self.write(self.p/'authorization.json',auth)
        inp=json.loads(Path(item['input']['path']).read_text());inp['authorization']=item['authorization']
        item['input']=self.write(self.p/'input.json',inp)
        with self.assertRaisesRegex(ValueError,'INSTALL_APPROVED_INPUT_REQUIRED'):D.validate_offline_preparation(item)

    def test_wrong_root_session_and_schema_rejected(self):
        for field in ('root_session','authorization_schema','input_schema'):
            with self.subTest(field=field):
                item=self.item();item[field]='wrong'
                with self.assertRaises(ValueError):D.validate_offline_preparation(item)

    def test_duplicate_registration_rejected(self):
        item=self.item();self.outer['offline_preparations']=[item,copy.deepcopy(item)]
        with self.assertRaisesRegex(ValueError,'NOT_UNIQUE'):self.loader()()

    def test_original_policy_network_prepare_and_run_preserved(self):
        cfg=self.policy;loader=self.loader()
        for mode in ('prepare','run'):
            tail=['--output-dir',str(self.p/'new-output')] if mode=='prepare' else ['--request',str(self.p/'request.json')]
            argv=[self.python['path'],'-BE',cfg['entry']['path'],mode,'--config',cfg['cfg']['path']]+tail
            self.assertIsNone(D.event_check(self.event(argv),loader))
        with self.assertRaises(ValueError):D.event_check(self.event([self.python['path'],'-BE',cfg['entry']['path'],'legacy-transport']),loader)

    def test_network_registry_legacy_entry_preserved(self):
        old=self.policy;new=self.network_policy('new',legacy=True)
        entries=[{'entry':v['entry'],'authority':v['authority'],'policy':v['policy'],'modes':m}
                 for v,m in ((old,['prepare','run']),(new,['legacy-run']))]
        ref=self.write(self.p/'inner-registry.json',{'schema':'nlm-network-entry-registry-v1','entries':entries})
        self.outer['network_authority']={'kind':'registry','file':ref}
        argv=[self.python['path'],'-BE',new['entry']['path'],'legacy-run','--config',new['cfg']['path'],'--request',str(self.p/'request.json')]
        self.assertIsNone(D.event_check(self.event(argv),self.loader()))

    def test_missing_unused_offline_input_does_not_break_network(self):
        item=self.item();self.outer['offline_preparations']=[item];Path(item['input']['path']).unlink()
        argv=[self.python['path'],'-BE',self.policy['entry']['path'],'run','--config',self.policy['cfg']['path'],'--request',str(self.p/'request.json')]
        self.assertIsNone(D.event_check(self.event(argv),self.loader()))

    def test_sidecar_pins_dispatcher_and_registry_without_changing_command(self):
        item=self.item();self.outer['offline_preparations']=[item];outer=self.write(self.p/'outer.json',self.outer)
        path=self.p/'authority.json';authority={'schema':'nlm-offline-preparation-authority-v1',
            'dispatcher':D.file_ref(D.__file__)[0],'registry':outer}
        self.write(path,authority);command=['--authority',str(path)]
        self.assertEqual(D.load_authority(str(path))[0],outer)
        altered=copy.deepcopy(self.outer);altered['offline_preparations']=[]
        next_ref=self.write(self.p/'outer-next.json',altered);authority['registry']=next_ref;self.write(path,authority)
        self.assertEqual(D.load_authority(str(path))[0],next_ref);self.assertEqual(command,['--authority',str(path)])
        authority['dispatcher']['sha256']='0'*64;self.write(path,authority)
        with self.assertRaisesRegex(ValueError,'DISPATCHER_CHANGED'):D.load_authority(str(path))

    def test_sidecar_registry_requires_complete_descriptor(self):
        outer=self.write(self.p/'outer.json',self.outer)
        authority={'schema':'nlm-offline-preparation-authority-v1',
            'dispatcher':D.file_ref(D.__file__)[0],'registry':outer}
        authority['registry']['bytes']+=1
        path=self.p/'authority.json';self.write(path,authority)
        with self.assertRaisesRegex(ValueError,'AUTHORITY_REGISTRY_CHANGED'):D.load_authority(str(path))


if __name__=='__main__':unittest.main()
