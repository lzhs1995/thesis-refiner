"""Shell data, recursion and parser uncertainty are distinct from NLM evidence."""
import importlib.util
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('shell_scope_guard',
    Path(__file__).resolve().parents[1] / 'scripts/nlm_network_guard.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class ShellScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def no_policy(self):
        raise AssertionError('Unrelated work must not request NLM policy')

    def denied_policy(self):
        raise guard.Denied('NLM_NETWORK_GUARD_WRAPPER_NETWORK')

    def test_quoted_help_document_is_data_not_recursive_execution(self):
        helper = self.root / 'helper'
        helper.write_text("#!/bin/sh\nusage() {\ncat <<'HELP'\nhelper read target\n"
                          "nlm query example\n$(nlm query example)\nHELP\n}\n"
                          "echo 'NLM help text'\n")
        with patch.object(guard.shutil, 'which', return_value=str(helper)):
            guard.shell_command(str(helper) + ' read target', self.no_policy, self.root)

    def test_interpreter_heredocs_and_post_document_commands_still_guarded(self):
        commands = [
            "python3 - <<'PY'\nimport notebooklm\nPY\n",
            "python3 -BES - <<'PY'\nimport notebooklm\nPY\n",
            "bash <<'SH'\nnlm query sample\nSH\n",
            "cat <<'TXT'\nnlm is documentation\nTXT\nnlm query sample",
            "cat <<TXT\n$(nlm query sample)\nTXT\n",
        ]
        for command in commands:
            with self.subTest(command=command), self.assertRaises(guard.Denied):
                guard.shell_command(command, self.denied_policy, self.root)
        guard.shell_command("python3 -BES - <<'PY'\nprint('NLM local fixture')\nPY\n",
                            self.no_policy, self.root)

    def test_shell_substitutions_and_package_runners_detect_execution(self):
        for command in ('cat "$(nlm query example)"', 'echo `nlm query example`',
                        'uvx --from notebooklm-mcp-cli nlm query example'):
            with self.subTest(command=command), self.assertRaises(guard.Denied):
                guard.shell_command(command, self.denied_policy, self.root)
        guard.shell_command("printf '%s' '$(nlm query example)'", self.no_policy, self.root)
        guard.shell_command("# $(nlm query example)\nprintf done", self.no_policy, self.root)
        guard.shell_command("python3 - <<'PY'\nprint('$(nlm query example)')\nPY\n",
                            self.no_policy, self.root)

    def test_uncertainty_is_not_network_evidence(self):
        for suffix in ('LOCAL_DEADLINE', 'LOCAL_SOURCE_CHAIN_UNRESOLVED',
                       'TEST_DISCOVERY_UNRESOLVED', 'LOCAL_EXECUTABLE_TOO_LARGE'):
            with self.subTest(suffix=suffix), patch.object(guard, 'executable_mentions',
                    side_effect=guard.Denied('NLM_NETWORK_GUARD_' + suffix)):
                guard.shell_command('python3 report.py', self.no_policy, self.root)

    def test_seen_sources_bound_recursion_without_hiding_following_nlm(self):
        helper = self.root / 'helper.sh'
        helper.write_text('#!/bin/sh\n' + shlex.quote(str(helper)) + '\nnlm query example\n')
        with self.assertRaises(guard.Denied):
            guard.shell_command(str(helper), self.denied_policy, self.root)
        helper.write_text('#!/bin/sh\n' + shlex.quote(str(helper)) + '\necho done\n')
        guard.shell_command(str(helper), self.no_policy, self.root)

    def test_authorization_deadline_remains_denied_in_nested_tools(self):
        def deadline():
            raise guard.Denied('NLM_NETWORK_GUARD_LOCAL_DEADLINE')
        with self.assertRaisesRegex(guard.Denied, 'AUTHORIZATION_DEADLINE'):
            guard.event_check({'tool_name': 'functions.exec', 'tool_input':
                              'text(await tools.exec_command({cmd:"nlm query sample"}));'},
                              deadline)


if __name__ == '__main__':
    unittest.main()
