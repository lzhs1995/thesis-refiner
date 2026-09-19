"""Synthetic public completion checks: no statistical or NLM execution."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

import test_workflow
import workflow as w


class LineageBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_workflow.WorkflowTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.state = self.fixture.state
        self.claim = self.state['nodes'][1]

    def complete_reproduction(self):
        root = self.fixture.root
        data = root / 'input.csv'; data.write_text('id,x\na,1\nb,2\n')
        output = root / 'output.csv'; output.write_text('term,b\nx,0.25\n')
        script = root / 'analysis.R'; script.write_text('# synthetic source, never executed\n')
        for node in self.state['nodes']:
            if node['kind'] in {'data', 'sample'}: node['artifacts'] = [w.ref(data)]
            if node['kind'] == 'cleaning': node['artifacts'] = [w.ref(script)]
            if node['kind'] == 'output': node['artifacts'] = [w.ref(output)]
        runtime = {key: 'synthetic-' + key for key in ('session_id', 'job_id', 'transport', 'source_revision', 'installed_version', 'loaded_version')}
        proof = {'mode': 'real', 'fixture_only': True, 'status': 'PASS', 'end_to_end': True,
                 'target_machine': 'synthetic', 'task_id': self.state['task_id'], 'claim_ids': ['claim'],
                 'session_id': runtime['session_id'], 'job_id': runtime['job_id'],
                 'script_sha256': w.sha(script), 'input_sha256s': [w.sha(data)], 'output_sha256s': [w.sha(output)]}
        receipt = self.fixture.file('execution', proof)
        contract = {'schema_version': 1, 'task_id': self.state['task_id'], 'claim_ids': ['claim'],
                    'script': w.ref(script), 'inputs': [w.ref(data)], 'outputs': [w.ref(output)],
                    'runtime': runtime, 'samples': [{'artifact': w.ref(data), 'keys': ['id'], 'expected_n': 2}],
                    'full_reproduction': True, 'execution_receipt': receipt}
        self.claim.update(reproduction_receipt=receipt, empirical_contract=self.fixture.file('trace', contract))
        self.claim['verification']['full_reproduction'] = True
        return proof, contract

    def test_null_unknown_and_unbound_numeric_claims_fail(self):
        disposition = next(d for d in self.state['dispositions'].values() if d['numeric_dispositions'])
        for row in (None, '', 'nonexistent', 'result', {}, {'kind': 'empirical', 'mention': '999', 'claim_id': 'claim'}):
            with self.subTest(row=row):
                disposition['numeric_dispositions'] = [row]
                self.assertEqual(w.acceptance(self.state)['status'], 'INCOMPLETE')
        disposition['numeric_dispositions'] = [{'kind': 'empirical', 'mention': '0.25', 'claim_id': 'claim'}]
        self.assertEqual(w.acceptance(self.state)['status'], 'COMPLETE')

    def test_nonempirical_number_requires_reason_and_evidence(self):
        item = {'id': 'synthetic-year', 'numeric_mentions': ['2026']}
        row = {'kind': 'nonempirical', 'mention': '2026', 'reason': 'Publication year, not an estimate', 'evidence': self.fixture.e}
        w.check_numeric_dispositions(item, {'numeric_dispositions': [row]}, {})
        for key in ('reason', 'evidence', 'mention'):
            bad = copy.deepcopy(row); bad.pop(key)
            with self.subTest(missing=key), self.assertRaises(w.EvidenceError):
                w.check_numeric_dispositions(item, {'numeric_dispositions': [bad]}, {})

    def test_full_reproduction_binds_current_task_claim_and_execution(self):
        proof, contract = self.complete_reproduction()
        self.assertTrue(w.audit_chain(self.state)['full_reproduction'])
        changes = {'task_id': 'other', 'claim_ids': ['other'], 'script_sha256': '0' * 64,
                   'input_sha256s': ['0' * 64], 'output_sha256s': ['0' * 64],
                   'session_id': 'other', 'job_id': 'other', 'end_to_end': 1}
        for key, value in changes.items():
            with self.subTest(key=key):
                receipt = self.fixture.file('bad-' + key, {**proof, key: value})
                self.claim['reproduction_receipt'] = receipt
                self.claim['empirical_contract'] = self.fixture.file('bad-trace-' + key, {**contract, 'execution_receipt': receipt})
                result = w.audit_chain(self.state)
                self.assertFalse(result['full_reproduction'], result)
                self.assertFalse(result['pass'], result)

    def test_unrelated_contract_cannot_wrap_a_valid_receipt(self):
        proof, contract = self.complete_reproduction()
        extra = self.fixture.root / 'other.csv'; extra.write_text('id,x\nz,3\n')
        contract['inputs'] = [w.ref(extra)]
        proof['input_sha256s'] = [w.sha(extra)]
        receipt = self.fixture.file('unrelated-execution', proof)
        self.claim['reproduction_receipt'] = receipt
        self.claim['empirical_contract'] = self.fixture.file('unrelated-trace', {**contract, 'execution_receipt': receipt})
        self.assertIn('OUTSIDE_LINEAGE', str(w.audit_chain(self.state)))

    def test_public_cli_and_hook_reject_bad_reproduction(self):
        proof, contract = self.complete_reproduction()
        checkpoint = self.fixture.root / 'checkpoint.json'
        hook = Path(w.__file__).parents[1] / 'hooks/a5-termination-auditor.js'
        for expected in (0, 2):
            if expected:
                proof['task_id'] = 'wrong-task'
                receipt = self.fixture.file('wrong-execution', proof)
                self.claim['reproduction_receipt'] = receipt
                self.claim['empirical_contract'] = self.fixture.file('wrong-trace', {**contract, 'execution_receipt': receipt})
            checkpoint.write_text(json.dumps(self.state))
            run = subprocess.run([sys.executable, w.__file__, 'acceptance', '--input', str(checkpoint)], capture_output=True)
            self.assertEqual(run.returncode, expected, run.stdout)
            run = subprocess.run(['node', str(hook)], input=json.dumps({'workflow_checkpoint': str(checkpoint)}), text=True, capture_output=True)
            self.assertEqual(run.returncode, expected, run.stderr)


if __name__ == '__main__':
    unittest.main()
