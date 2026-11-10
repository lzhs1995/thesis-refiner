import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nlm_network_guard as guard


class NetworkGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();scripts=self.root/'source/scripts';scripts.mkdir(parents=True)
        self.entry=scripts/'nlm_sdk_entry.py';self.entry.write_text('# synthetic pinned entry\n')
        self.route=self.root/'route.json';self.route.write_text(json.dumps({'proxy':'http://127.0.0.1:1'}))
        self.ref=lambda p:guard.file_ref(p)[0]
        self.policy=dict(schema='nlm-network-policy-v1',policy_role='mandatory-domain-route',
            required_route_label='test chain -> test terminal',route_binding=self.ref(self.route),
            python=self.ref(sys.executable),entry=self.ref(self.entry),code_pins=[self.ref(self.entry)])
        self.policy_path=self.root/'policy.json';self.policy_path.write_text(json.dumps(self.policy))
        self.policy_ref=self.ref(self.policy_path)
        self.config=self.root/'task.json';self.cfg=dict(route_policy=self.policy_ref,
            route_binding=self.ref(self.route),python=self.ref(sys.executable),proxy='http://127.0.0.1:1',
            scripts=str(scripts),code_pins=self.policy['code_pins'])
        self.config.write_text(json.dumps(self.cfg))
        self.argv=[self.policy['python']['path'],'-BE',str(self.entry),'run','--config',str(self.config),
                   '--request',str(self.root/'request.json')]
        self.command='rtk proxy '+shlex.join(self.argv)

    def check(self,command):
        guard.event_check({'tool_name':'Bash','tool_input':{'command':command},'cwd':str(self.root)},
                          lambda:guard.load_policy(self.policy_path,self.policy_ref['sha256']))

    def test_exact_entry_and_simple_shell_wrapper_allowed(self):
        self.check(self.command)
        self.check('rtk proxy zsh -lc '+shlex.quote(self.command))

    def test_prepare_allowed_only_same_pinned_policy(self):
        args=self.argv[:];args[3]='prepare';args[-2]='--output-dir'
        self.check('rtk proxy '+shlex.join(args))
        self.cfg['route_policy']['sha256']='0'*64;self.config.write_text(json.dumps(self.cfg))
        with self.assertRaisesRegex(guard.Denied,'REGISTERED_POLICY'):self.check(self.command)

    def test_missing_route_and_wrong_proxy_deny(self):
        for field,value in [('route_binding',None),('proxy','http://127.0.0.1:9')]:
            cfg={**self.cfg,field:value};self.config.write_text(json.dumps(cfg))
            with self.assertRaises(guard.Denied):self.check(self.command)

    def test_changed_registered_policy_or_code_deny(self):
        self.policy_path.write_text('{}')
        with self.assertRaisesRegex(guard.Denied,'POLICY_CHANGED'):self.check(self.command)
        self.policy_path.write_text(json.dumps(self.policy));self.entry.write_text('changed')
        with self.assertRaisesRegex(guard.Denied,'PIN_CHANGED'):self.check(self.command)

    def test_direct_mcp_all_operations_deny(self):
        for name in ['mcp__notebooklm__notebook_query','mcp__notebooklm__notebook_list',
                     'mcp__nlm__status','mcp__notebooklm_mcp__source_get']:
            with self.assertRaisesRegex(guard.Denied,'DIRECT_MCP'):
                guard.event_check({'tool_name':name,'tool_input':{}},lambda:None)

    def test_direct_cli_sdk_http_and_browser_deny(self):
        for command in ['nlm notebook list','uvx --from notebooklm-mcp-cli nlm query x',
                'python -c "import notebooklm; notebooklm.query()"',
                'curl https://notebook.google.com/query','env HTTPS_PROXY=http://127.0.0.1:1 nlm query x']:
            with self.subTest(command=command):
                with self.assertRaises(guard.Denied):self.check(command)
        with self.assertRaises(guard.Denied):
            guard.event_check({'tool_name':'fetch','tool_input':{'url':'https://notebooklm.google.com/'}},lambda:None)

    def test_unrelated_and_known_readonly_allowed_without_policy(self):
        for command in ['rtk proxy git status --short','rtk proxy cat /tmp/nlm/receipt.json',
                "rtk proxy rg -n 'notebooklm' scripts",'rtk proxy sed -n 1,20p /tmp/nlm.py',
                'rtk proxy python -c "print(1+1)"']:
            guard.event_check({'tool_name':'exec_command','tool_input':{'cmd':command}},
                              lambda:(_ for _ in ()).throw(AssertionError('must not load')))

    def test_shell_composition_substitution_and_direct_transport_deny(self):
        for command in ['echo before; '+self.command,'cat /tmp/nlm.json\nnlm query x',
                'cat /tmp/readme # comment\nnlm query x',
                self.command+' > /tmp/log','cat "$(nlm query x)"',
                'sed -n 1,2p "$(nlm query x)"','echo before; sh -c '+shlex.quote(self.command),
                self.command.replace(' run ',' transport ')]:
            with self.subTest(command=command):
                with self.assertRaises(guard.Denied):self.check(command)

    def test_local_wrapper_source_is_inspected(self):
        inner=self.root/'inner.py';inner.write_text('import notebooklm\n')
        outer=self.root/'outer.py';outer.write_text('import runpy\nrunpy.run_path("inner.py")\n')
        with self.assertRaises(guard.Denied):self.check('python '+str(outer))
        opaque=self.root/'local-helper';opaque.write_text('#!/bin/sh\nnlm notebook list\n');opaque.chmod(0o700)
        with self.assertRaises(guard.Denied):self.check(str(opaque))

    def test_reviewed_exact_offline_command_can_read_or_settle_locally(self):
        script=self.root/'nlm_readback.py';script.write_text('# reviewed fixture: local evidence only\n')
        argv=[sys.executable,'-BE',str(script),'--receipt','original-fixed-id']
        self.policy['offline_commands']=[dict(argv=argv,network='none',files=[self.ref(script)])]
        self.policy_path.write_text(json.dumps(self.policy));self.policy_ref=self.ref(self.policy_path)
        self.check('rtk proxy '+shlex.join(argv))
        with self.assertRaises(guard.Denied):self.check('rtk proxy '+shlex.join(argv+['--query']))
        script.write_text('import notebooklm\n')
        with self.assertRaisesRegex(guard.Denied,'PIN_CHANGED'):self.check('rtk proxy '+shlex.join(argv))

    def test_exec_nested_literal_checked_and_dynamic_nlm_denied(self):
        loader=lambda:guard.load_policy(self.policy_path,self.policy_ref['sha256'])
        code='text(await tools.exec_command({cmd: '+json.dumps(self.command)+'}));'
        guard.event_check({'tool_name':'functions.exec','tool_input':code},loader)
        for code in ['await tools.mcp__notebooklm__query({})',
                     'const x="nlm query x"; await tools.exec_command({cmd:x})',
                     'await tools.exec_command({cmd:"nlm query x"})']:
            with self.assertRaises(guard.Denied):
                guard.event_check({'tool_name':'functions.exec','tool_input':code},loader)

    def test_nested_exec_respects_literal_workdir_and_dynamic_file_wrapper_denied(self):
        script=self.root/'go.py';script.write_text('import notebooklm\n')
        loader=lambda:guard.load_policy(self.policy_path,self.policy_ref['sha256'])
        for code in ['await tools.exec_command({cmd:"python go.py",workdir:'+json.dumps(str(self.root))+'})',
                     'const f='+json.dumps(str(script))+';await tools.exec_command({cmd:f})']:
            with self.assertRaises(guard.Denied):
                guard.event_check({'tool_name':'functions.exec','tool_input':code},loader)

    def test_protocol_variants_and_read_file_allowed(self):
        guard.event_check({'toolName':'Read','toolInput':{'file_path':'/tmp/nlm.py'}},lambda:None)
        guard.event_check({'tool':'shell','arguments':{'command':self.command}},
                         lambda:guard.load_policy(self.policy_path,self.policy_ref['sha256']))

    def test_hook_process_protocol_no_network(self):
        command=[sys.executable,'-BE',guard.__file__,'--policy',str(self.policy_path),
                 '--policy-sha256',self.policy_ref['sha256']]
        for payload,expected in [({'tool_name':'Bash','tool_input':{'command':'nlm query x'}},2),
                                 ({'tool_name':'Bash','tool_input':{'command':'cat /tmp/nlm.json'}},0),
                                 ({'tool_name':'Bash','tool_input':{'command':self.command}},0)]:
            result=subprocess.run(command,input=json.dumps(payload),text=True,capture_output=True,timeout=6)
            self.assertEqual(result.returncode,expected,result.stderr)
            data=json.loads(result.stdout)
            if expected:self.assertEqual(data['hookSpecificOutput']['permissionDecision'],'deny')
            else:self.assertEqual(data,{})


if __name__=='__main__':unittest.main()
