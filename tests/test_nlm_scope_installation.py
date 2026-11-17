"""Public installation scope hints never grant network authorization."""
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import nlm_network_guard as guard


class InstallationScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.dynamic = self.root / 'runtime.py'
        self.dynamic.write_text('print("synthetic dynamic entry")\n')
        self.local = self.root / 'report.py'
        self.local.write_text('print("NLM report text, no networking")\n')
        self.registry = self.root / 'missing-registry.json'
        self.loader = guard.PolicyLoader('registry', self.registry, '0' * 64,
                                         [str(self.dynamic)])

    def event(self, script):
        return {'tool_name': 'exec_command', 'tool_input': {
            'cmd': shlex.join([sys.executable, '-BE', str(script)])}}

    def test_missing_authority_does_not_block_unrelated_local_task(self):
        guard.event_check(self.event(self.local), self.loader)
        guard.event_check({'tool_name': 'functions.exec', 'tool_input':
                          'text("NLM receipt summary");'}, self.loader)

    def test_missing_or_changed_authority_still_blocks_bound_dynamic_entry(self):
        with self.assertRaises((OSError, guard.Denied)):
            guard.event_check(self.event(self.dynamic), self.loader)
        self.registry.write_text('{"schema": "changed"}')
        with self.assertRaisesRegex(guard.Denied, 'REGISTERED_REGISTRY_CHANGED'):
            guard.event_check(self.event(self.dynamic), self.loader)
        guard.event_check(self.event(self.local), self.loader)

    def test_empty_registry_hint_is_not_permission(self):
        self.registry.write_text(json.dumps({'schema': 'nlm-network-entry-registry-v1',
                                            'entries': []}))
        ref = guard.file_ref(self.registry)[0]
        loader = guard.PolicyLoader('registry', self.registry, ref['sha256'],
                                    [str(self.dynamic)])
        with self.assertRaisesRegex(guard.Denied, 'ENTRY_REGISTRY_SCHEMA'):
            guard.event_check(self.event(self.dynamic), loader)

    def test_explicit_sdk_and_url_remain_guarded_without_scope_hints(self):
        loader = guard.PolicyLoader('registry', self.registry, '0' * 64)
        for command in ('python3 -c "import notebooklm"',
                        'curl https://notebooklm.google.com/'):
            with self.subTest(command=command), self.assertRaises((OSError, guard.Denied)):
                guard.event_check({'tool_name': 'Bash', 'tool_input': {'command': command}}, loader)

    def test_main_propagates_scope_hints_with_zero_network(self):
        cmd = [sys.executable, '-BE', guard.__file__, '--registry', str(self.registry),
               '--registry-sha256', '0' * 64, '--entry-path', str(self.dynamic)]
        for script, expected in ((self.local, 0), (self.dynamic, 2)):
            with self.subTest(script=script.name):
                result = subprocess.run(cmd, input=json.dumps(self.event(script)),
                                        capture_output=True, text=True, timeout=6)
                self.assertEqual(result.returncode, expected, result.stderr)
                if expected:
                    self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']
                                     ['permissionDecision'], 'deny')
                else:
                    self.assertEqual(json.loads(result.stdout), {})


if __name__ == '__main__':
    unittest.main()
