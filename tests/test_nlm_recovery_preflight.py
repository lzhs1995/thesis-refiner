"""Recovery must survive non-JSON evidence without changing identity or health."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from nlm_query_health import authorize_recovery, initial_state
from nlm_recovery_preflight import pin, prepare, validate_prepared, write_new


class RecoveryPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        failure = write_new(self.root / 'failure.json', {'fixture': 'original TLS failure'})
        self.state = dict(initial_state('synthetic-account'), mode='PAUSED',
                          last_return=failure, pause_return=failure, observed_request_ids=[])
        self.script = self.root / 'probe.py'
        self.script.write_text('raise RuntimeError("evidence must never execute")\n')
        self.decision = {'status': 'FIXED_SINGLE_RECOVERY_DECISION', 'account_key': 'synthetic-account',
                         'query_cap': 1, 'automatic_retry': False, 'necessary_existing_request': 'a' * 64,
                         'recovery_condition_met': True, 'new_evidence_since_failure': True,
                         'failure_return': failure, 'evidence': [pin(self.script)]}

    def original(self):
        return write_new(self.root / 'original.json', self.decision)

    def test_reproduces_old_failure_and_prepares_compatible_decision(self):
        original = self.original()
        before = deepcopy(self.state)
        with self.assertRaises(json.JSONDecodeError):
            authorize_recovery(self.state, original)
        result = prepare(self.state, original, self.root / 'prepared')
        restored = authorize_recovery(self.state, result['decision'])
        self.assertEqual(restored['mode'], 'RECOVERY')
        self.assertEqual(restored['recovery_request_id'], 'a' * 64)
        self.assertEqual(self.state, before)
        self.assertFalse(result['network_authorized'])
        self.assertFalse(result['health_changed'])
        self.assertEqual(self.script.read_text(), 'raise RuntimeError("evidence must never execute")\n')

    def test_binary_log_is_preserved_without_json_or_utf8_parsing(self):
        log = self.root / 'trace.log'
        log.write_bytes(b'\xff\xfe\x00binary TLS evidence')
        self.decision['evidence'].append(pin(log))
        result = prepare(self.state, self.original(), self.root / 'prepared')
        self.assertEqual(validate_prepared(self.state, result['decision'])['status'], 'RECOVERY_PREFLIGHT_PASS')

    def test_changed_attachment_rejected_at_actual_boundary(self):
        result = prepare(self.state, self.original(), self.root / 'prepared')
        self.script.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'HASH_MISMATCH'):
            validate_prepared(self.state, result['decision'])

    def test_prepared_scope_cannot_change_request_or_cap(self):
        result = prepare(self.state, self.original(), self.root / 'prepared')
        value = json.loads(Path(result['decision']['path']).read_text())
        value['necessary_existing_request'] = 'b' * 64
        changed = write_new(self.root / 'changed.json', value)
        with self.assertRaisesRegex(ValueError, 'SCOPE_CHANGED'):
            validate_prepared(self.state, changed)

    def test_returned_id_cannot_be_reissued(self):
        self.state['observed_request_ids'] = ['a' * 64]
        with self.assertRaisesRegex(ValueError, 'ALREADY_SENT'):
            prepare(self.state, self.original(), self.root / 'prepared')

    def test_paused_failure_must_still_be_current(self):
        result = prepare(self.state, self.original(), self.root / 'prepared')
        self.state['pause_return'] = write_new(self.root / 'new-failure.json', {'new': True})
        with self.assertRaisesRegex(ValueError, 'NEW_RECOVERY_EVIDENCE'):
            validate_prepared(self.state, result['decision'])

    def test_unknown_inflight_recovery_is_not_reset(self):
        self.state.update(mode='RECOVERY', recovery_claimed=True, recovery_request_id='b' * 64)
        before = deepcopy(self.state)
        with self.assertRaisesRegex(ValueError, 'NEW_RECOVERY_EVIDENCE'):
            prepare(self.state, self.original(), self.root / 'prepared')
        self.assertEqual(self.state, before)

    def test_reused_decision_and_noninteger_cap_are_rejected(self):
        self.decision['query_cap'] = True
        with self.assertRaisesRegex(ValueError, 'ONE_NECESSARY_QUERY'):
            prepare(self.state, self.original(), self.root / 'prepared')

    def test_used_original_decision_is_rejected_before_output(self):
        original = self.original()
        self.state['recovery_decisions'] = [original['sha256']]
        with self.assertRaisesRegex(ValueError, 'ALREADY_USED'):
            prepare(self.state, original, self.root / 'prepared')
        self.assertFalse((self.root / 'prepared').exists())

    def test_original_and_prepared_files_cannot_be_overwritten(self):
        original = self.original()
        prepare(self.state, original, self.root / 'prepared')
        with self.assertRaises(FileExistsError):
            prepare(self.state, original, self.root / 'prepared')
        self.assertEqual(pin(self.root / 'original.json'), original)


if __name__ == '__main__':
    unittest.main()
