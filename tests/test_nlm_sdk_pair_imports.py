"""Fresh-process import-order acceptance for the complete pair entry closure."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'

# No entry operation is called. Runtime loading at import is part of the real
# pair module, so test both orders without substituting modules or functions.
PROGRAM = r'''
import importlib, json, pathlib, sys
scripts = pathlib.Path(sys.argv[1]).resolve()
order = sys.argv[2]
forbidden = {'nlm_network_guard', 'hook_doctor'}
sys.path.insert(0, str(scripts))
if order == 'ordinary-first':
    ordinary = importlib.import_module('nlm_runtime')
pair = importlib.import_module('nlm_pair_budget')
parent = importlib.import_module('nlm_sdk_pair_parent')
setup = importlib.import_module('nlm_pair_setup')
ordinary = importlib.import_module('nlm_runtime')
assert pair.runtime is ordinary
assert pair.Budget is ordinary.Budget
assert pair.AdmissionError is ordinary.AdmissionError
assert not forbidden.intersection(sys.modules)
expected = ('nlm_pair_budget', 'nlm_sdk_pair_child', 'nlm_pair_group', 'nlm_pair_identity',
            'nlm_pair_locks', 'nlm_pair_policy', 'nlm_pair_setup', 'nlm_sdk_pair_parent',
            'pair_total_budget', 'nlm_contracts', 'nlm_sdk_entry', 'nlm_runtime', 'workflow')
origins = {}
for name in expected:
    module = sys.modules[name]
    origin = pathlib.Path(module.__file__).resolve()
    assert origin == scripts / (name + '.py'), (name, str(origin))
    origins[name] = str(origin)
print(json.dumps({'status': 'PASS_IMPORT_ONLY', 'order': order, 'origins': origins}))
'''


@unittest.skipUnless(sys.version_info >= (3, 11) and os.name == 'posix',
                     'Pair controller imports require Python 3.11+ and POSIX')
class PairImportTests(unittest.TestCase):
    def check_order(self, order):
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([sys.executable, '-BE', '-c', PROGRAM, str(SCRIPTS), order],
                cwd=folder, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['status'], 'PASS_IMPORT_ONLY')
        self.assertEqual(report['order'], order)
        self.assertEqual(len(report['origins']), 13)

    def test_ordinary_runtime_imported_before_pair_entries(self):
        self.check_order('ordinary-first')

    def test_pair_entries_imported_before_ordinary_runtime(self):
        self.check_order('pair-first')


if __name__ == '__main__':
    unittest.main()
