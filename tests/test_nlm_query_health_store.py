"""Synthetic-only persistence tests; these fixtures are never live acceptance."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from nlm_query_health_store import QueryHealthJournal, verify_real_return


class HealthJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.account = 'synthetic-account'
        self.database = self.root / 'health.sqlite3'
        self.journal = QueryHealthJournal(self.database, self.account, create=True)
        self.serial = 0

    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()

    def save(self, name, value):
        p = self.root / (name + '-' + uuid.uuid4().hex + '.json')
        p.write_text(json.dumps(value))
        return {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}

    def returned(self, *, valid=False, request_id=None, remote=True, operation='query', count=None):
        self.serial += 1
        key = request_id or hashlib.sha256(str(self.serial).encode()).hexdigest()
        status = 'COMPLETE' if valid else 'FAILED'
        lease = {'id': uuid.uuid4().hex}
        release = self.save('release', {'status': 'RELEASED', 'id': lease['id'],
            'resource': 'nlm-account:' + self.account,
            'release_proof': {'external_locks_probed_and_released': True}})
        answer = 'synthetic answer' if valid else ''
        refs = [{'source_id': 's', 'cited_text': 'synthetic quote'}] if valid else []
        request = self.save('request', {'operation': operation, 'notebook_id': 'n'})
        raw = self.save('raw', {'answer': answer, 'references': refs})
        receipt = self.save('receipt', {'mode': 'real', 'status': status,
            'account_key': self.account, 'operation': operation, 'request_id': key,
            'notebook_id': 'n', 'resource_lease': lease, 'remote_terminal': remote,
            'network_terminal': True, 'process_group_empty': True, 'fully_received': True,
            'source_contract_valid': valid, 'in_flight_requests': [],
            'request': request, 'raw_answer': raw,
            'answer_characters': len(answer) if count is None else count,
            'native_citations': len(refs)})
        return self.save('return', {'terminal': receipt, 'release': release, 'members': [{
            'origin_request_id': key, 'status': status, 'network_terminal': True, 'receipt': receipt}]})

    def paused(self):
        return self.journal.bootstrap([self.returned()])

    def decision(self, state, request_id='a' * 64):
        evidence = self.save('synthetic-evidence', {'fixture_only': True})
        return self.save('decision', {'status': 'FIXED_SINGLE_RECOVERY_DECISION',
            'account_key': self.account, 'query_cap': 1,
            'recovery_condition_met': True, 'new_evidence_since_failure': True,
            'automatic_retry': False, 'necessary_existing_request': request_id,
            'failure_return': state.get('pause_return', state['last_return']), 'evidence': [evidence]})

    def test_missing_journal_cannot_reset_pause(self):
        with self.assertRaises(FileNotFoundError):
            QueryHealthJournal(self.root / 'missing.sqlite3', self.account)

    def test_empty_journal_does_not_authorize(self):
        with self.assertRaises(ValueError):
            self.journal.admit(['a' * 64])

    def test_pause_survives_reopen(self):
        expected = self.paused()
        self.journal.close()
        self.journal = QueryHealthJournal(self.database, self.account)
        self.assertEqual(self.journal.status(), expected)
        with self.assertRaisesRegex(ValueError, 'PAUSED'):
            self.journal.admit(['a' * 64])

    def test_late_success_preserves_the_failure_reference(self):
        paused = self.paused()
        latest = self.journal.record(self.returned(valid=True))
        self.assertEqual(latest['mode'], 'PAUSED')
        self.assertEqual(latest['pause_return'], paused['pause_return'])
        self.journal.recover(self.decision(latest))

    def test_recovery_admission_is_atomic_across_connections(self):
        state = self.paused()
        self.journal.recover(self.decision(state))
        other = QueryHealthJournal(self.database, self.account)
        try:
            self.assertEqual(self.journal.admit(['a' * 64])['mode'], 'RECOVERY')
            with self.assertRaisesRegex(ValueError, 'ALREADY_ADMITTED'):
                other.admit(['a' * 64])
        finally:
            other.close()

    def test_recovery_admission_survives_reopen(self):
        self.journal.recover(self.decision(self.paused()))
        self.journal.admit(['a' * 64])
        self.journal.close()
        self.journal = QueryHealthJournal(self.database, self.account)
        with self.assertRaisesRegex(ValueError, 'ALREADY_ADMITTED'):
            self.journal.admit(['a' * 64])

    def test_successful_recovery_allows_new_work(self):
        self.journal.recover(self.decision(self.paused()))
        self.journal.admit(['a' * 64])
        state = self.journal.record(self.returned(valid=True, request_id='a' * 64))
        self.assertEqual(state['mode'], 'HEALTHY')
        self.assertEqual(self.journal.admit(['b' * 64])['health_admission'], 'PASS')

    def test_failed_recovery_retains_pause(self):
        decision = self.decision(self.paused())
        self.journal.recover(decision)
        self.journal.admit(['a' * 64])
        state = self.journal.record(self.returned(request_id='a' * 64))
        self.assertEqual(state['mode'], 'PAUSED')
        with self.assertRaises(ValueError):
            self.journal.recover(decision)

    def test_historical_request_is_not_reissued(self):
        original = self.returned(valid=True, request_id='a' * 64)
        self.journal.bootstrap([original])
        with self.assertRaisesRegex(ValueError, 'ALREADY_SENT'):
            self.journal.admit(['a' * 64])

    def test_duplicate_return_is_idempotent(self):
        original = self.returned()
        before = self.journal.bootstrap([original])
        events = self.journal.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        self.assertEqual(self.journal.record(original), before)
        self.assertEqual(self.journal.db.execute('SELECT COUNT(*) FROM events').fetchone()[0], events)

    def test_no_bootstrap_reset(self):
        self.paused()
        with self.assertRaisesRegex(ValueError, 'NO_RESET'):
            self.journal.bootstrap([self.returned(valid=True)])

    def test_raw_answer_measurement_must_match(self):
        with self.assertRaisesRegex(ValueError, 'COUNTS_MISMATCH'):
            self.journal.bootstrap([self.returned(valid=True, count=0)])

    def test_unknown_remote_terminal_is_not_a_return(self):
        with self.assertRaisesRegex(ValueError, 'TERMINAL_AND_RELEASE'):
            self.journal.bootstrap([self.returned(remote=False)])

    def test_upload_success_cannot_restore_query_health(self):
        with self.assertRaisesRegex(ValueError, 'QUERY_IDENTITY'):
            self.journal.bootstrap([self.returned(valid=True, operation='source_add')])

    def test_changed_evidence_does_not_reset_state(self):
        before = self.paused()
        changed = self.returned(valid=True)
        Path(changed['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'HASH_MISMATCH'):
            self.journal.record(changed)
        self.assertEqual(self.journal.status(), before)


if __name__ == '__main__':
    unittest.main()
