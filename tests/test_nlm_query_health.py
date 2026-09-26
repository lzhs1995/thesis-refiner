"""Offline behavioral fixtures only; no live calls or paper acceptance credit."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from nlm_query_health import initial_state, record_return, authorize_recovery, assert_admission


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.n = 0
        self.state = initial_state('fixture-account')

    def write(self, obj):
        self.n += 1
        path = self.root / (str(self.n) + '.json')
        raw = json.dumps(obj).encode()
        path.write_bytes(raw)
        return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}

    def returned(self, kinds, **overrides):
        lease = 'fixture-lease-' + str(self.n)
        release = self.write({'id': lease, 'status': 'RELEASED', 'resource': 'nlm-account:fixture-account'})
        members = []
        for i, kind in enumerate(kinds):
            rid = overrides.pop('request_id', None) or hashlib.sha256((lease + str(i)).encode()).hexdigest()
            receipt = {'mode': 'real', 'network_terminal': True, 'remote_terminal': True,
                'process_group_empty': True, 'fully_received': True,
                'status': 'COMPLETE' if kind == 'valid' else 'FAILED',
                'account_key': 'fixture-account', 'request_id': rid,
                'resource_lease': {'id': lease}, 'source_contract_valid': kind == 'valid',
                'answer_characters': 0 if kind == 'empty' else 100,
                'native_citations': 5 if kind == 'valid' else 0, **overrides}
            members.append({'origin_request_id': rid, 'status': receipt['status'], 'receipt': self.write(receipt)})
        return self.write({'release': release, 'members': members})

    def pause(self):
        return record_return(self.state, self.returned(['empty', 'empty']))

    def decision(self, state, request_id='a' * 64, **overrides):
        return self.write({'status': 'FIXED_SINGLE_RECOVERY_DECISION', 'account_key': 'fixture-account',
            'recovery_condition_met': True, 'new_evidence_since_failure': True,
            'query_cap': 1, 'automatic_retry': False, 'necessary_existing_request': request_id,
            'failure_return': state['last_return'], 'evidence': [self.write({'fixture_new_signal': True})], **overrides})

    def test_healthy_two_and_capacity_limit(self):
        state = record_return(self.state, self.returned(['valid', 'valid']))
        assert_admission(state, ['a', 'b'])
        with self.assertRaises(ValueError): assert_admission(state, ['a', 'b', 'c'])

    def test_two_empty_pause_without_claiming_quota(self):
        state = self.pause()
        self.assertEqual(state['reason'], 'EMPTY_ANSWER_CAUSE_UNKNOWN')
        with self.assertRaises(ValueError): assert_admission(state, ['a'])
        self.assertEqual(self.state['mode'], 'HEALTHY')

    def test_single_empty_pauses(self):
        self.assertEqual(record_return(self.state, self.returned(['empty']))['mode'], 'PAUSED')

    def test_empty_threshold_across_groups(self):
        state = record_return(self.state, self.returned(['empty', 'valid']))
        self.assertEqual(state['mode'], 'HEALTHY')
        self.assertEqual(record_return(state, self.returned(['valid', 'empty']))['mode'], 'PAUSED')

    def test_nonempty_missing_citations_is_separate(self):
        state = record_return(self.state, self.returned(['uncited', 'valid']))
        self.assertEqual((state['mode'], state['empty_responses']), ('HEALTHY', 0))

    def test_late_valid_answer_does_not_unpause(self):
        state = record_return(self.pause(), self.returned(['valid', 'valid']))
        self.assertEqual(state['mode'], 'PAUSED')

    def test_idempotent_return(self):
        ref = self.returned(['empty', 'valid'])
        state = record_return(self.state, ref)
        self.assertEqual(record_return(state, ref), state)

    def test_size_metadata_does_not_count_return_twice(self):
        ref = self.returned(['empty', 'valid'])
        state = record_return(self.state, ref)
        richer = {**ref, 'bytes': Path(ref['path']).stat().st_size}
        self.assertEqual(record_return(state, richer), state)
        self.assertEqual(state['empty_responses'], 1)
        with self.assertRaisesRegex(ValueError, 'SIZE_MISMATCH'):
            record_return(state, {**richer, 'bytes': richer['bytes'] + 1})

    def test_same_content_copy_does_not_change_original_return_path(self):
        ref = self.returned(['valid'])
        state = record_return(self.state, ref)
        copy = self.root / 'copy.json'
        copy.write_bytes(Path(ref['path']).read_bytes())
        with self.assertRaisesRegex(ValueError, 'RETURN_IDENTITY_CHANGED'):
            record_return(state, {**ref, 'path': str(copy)})

    def test_failure_size_metadata_preserves_recovery_binding(self):
        state = self.pause()
        richer = {**state['last_return'], 'bytes': Path(state['last_return']['path']).stat().st_size}
        recovered = authorize_recovery(state, self.decision(state, failure_return=richer))
        self.assertEqual(recovered['mode'], 'RECOVERY')
        self.assertEqual(state['mode'], 'PAUSED')

    def test_unknown_terminal_is_rejected(self):
        with self.assertRaises(ValueError):
            record_return(self.state, self.returned(['empty'], remote_terminal=False))

    def test_evidence_hash_mutation_is_rejected(self):
        ref = self.returned(['valid'])
        Path(ref['path']).write_text('{}')
        with self.assertRaises(ValueError): record_return(self.state, ref)

    def test_stale_banner_cannot_authorize(self):
        state = self.pause()
        with self.assertRaises(ValueError):
            authorize_recovery(state, self.decision(state, new_evidence_since_failure=False))

    def test_recovery_exactly_one_and_failed_stays_paused(self):
        paused = self.pause()
        state = authorize_recovery(paused, self.decision(paused))
        assert_admission(state, ['a' * 64])
        for ids in [['b' * 64], ['a' * 64, 'b' * 64]]:
            with self.assertRaises(ValueError): assert_admission(state, ids)
        failed = record_return(state, self.returned(['empty'], request_id='a' * 64))
        self.assertEqual(failed['mode'], 'PAUSED')

    def test_valid_recovery_reenables_existing_capacity(self):
        paused = self.pause()
        state = authorize_recovery(paused, self.decision(paused))
        restored = record_return(state, self.returned(['valid'], request_id='a' * 64))
        self.assertEqual(restored['mode'], 'HEALTHY')
        assert_admission(restored, ['b', 'c'])

    def test_explicit_quota_pauses_even_with_answer(self):
        state = record_return(self.state, self.returned(['valid'], quota_limited=True))
        self.assertEqual(state['mode'], 'PAUSED')


if __name__ == '__main__':
    unittest.main()
