"""Synthetic offline arbitration/failure controls; these make zero NLM calls."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from nlm_ready_scheduler import ReadyQueue


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.serial = 0
        evidence = self.artifact({'fixture': 'synthetic live-result schema, never actual review credit'})
        capability = self.artifact({'status': 'LIVE_TWO_QUERY_CAPABILITY', 'account_key': 'test-account', 'validated_capacity': 2, 'evidence': [evidence]})
        self.policy = {'account_key': 'test-account', 'coordinator_id': 'test-coordinator', 'capacity': 2, 'admission_seconds': 600, 'parallel_capability': capability}
        self.queue = ReadyQueue(self.root / 'queue.db', self.policy)

    def tearDown(self):
        self.queue.db.close()
        self.tmp.cleanup()

    def artifact(self, obj):
        self.serial += 1
        p = self.root / (str(self.serial) + '.json')
        p.write_text(json.dumps(obj, sort_keys=True))
        return {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}

    def entry(self, task, position=1, notebook=None):
        token = task + ':' + str(position)
        owner = self.artifact({'synthetic_owner': token})
        return {'request_id': hashlib.sha256(token.encode()).hexdigest(), 'task_id': task, 'position': position, 'owner_reservation': owner, 'fixed_inputs': [owner], 'payload': {'prompt': token}, 'logical_identity': {'account_key': 'test-account', 'notebook_id': notebook or task, 'operation': 'query', 'document_sha256': 'd'*64, 'round_id': 'round-1', 'prompt_sha256': hashlib.sha256(token.encode()).hexdigest(), 'source_ids': ['source-b', 'source-a']}}

    def start(self, *entries, now=100):
        for entry in entries:
            self.queue.enqueue(entry)
        group = self.queue.claim(now=now)
        self.queue.mark_started(group['group_id'], now=now)
        return group

    def proof(self, group, failed=False, quota=False, omit_member=False, wrong_lease=False):
        lease = 'synthetic-lease'
        release = self.artifact({'id': lease, 'resource': 'nlm-account:test-account', 'status': 'RELEASED', 'release_proof': {'external_locks_probed_and_released': True}})
        terminal = self.artifact({'mode': 'real', 'status': 'FAILED' if failed else 'COMPLETE', 'in_flight_requests': [], 'remote_terminal': True, 'process_group_empty': True, 'resource_lease': {'id': 'wrong' if wrong_lease else lease}})
        members = []
        for entry in group['members']:
            state = 'FAILED' if failed else 'COMPLETE'
            receipt = {'request_id': entry['request_id'], **entry['logical_identity'], 'mode': 'real', 'network_terminal': True, 'remote_terminal': True, 'process_group_empty': True, 'resource_lease': {'id': lease}, 'status': state, 'fully_received': True, 'source_contract_valid': not failed, 'native_citations': 0 if failed else 1, 'quota_limited': quota}
            receipt['request'] = self.artifact({'operation': entry['logical_identity']['operation'], 'prompt': entry['payload']['prompt']})
            members.append({'origin_request_id': entry['request_id'], 'network_terminal': True, 'status': state, 'receipt': self.artifact(receipt)})
        if omit_member:
            members.pop()
        batch = self.artifact({'release': release, 'terminal': terminal, 'members': members})
        return self.artifact({'group_id': group['group_id'], 'batch_return': batch})

    def test_fair_rotation_and_task_order(self):
        a1, a2, b, c = self.entry('a'), self.entry('a', 2), self.entry('b'), self.entry('c')
        for entry in (a1, a2, b, c):
            self.queue.enqueue(entry)
        group = self.queue.claim(now=100)
        self.assertEqual([e['task_id'] for e in group['members']], ['a', 'b'])
        self.queue.mark_started(group['group_id'], now=100)
        self.queue.finish(group['group_id'], self.proof(group))
        following = self.queue.claim(now=105)
        self.assertEqual([e['task_id'] for e in following['members']], ['c', 'a'])
        self.assertEqual(following['members'][1]['position'], 2)

    def test_distinct_notebooks(self):
        for entry in (self.entry('a', notebook='shared'), self.entry('b', notebook='shared'), self.entry('c')):
            self.queue.enqueue(entry)
        group = self.queue.claim()
        self.assertEqual([e['task_id'] for e in group['members']], ['a', 'c'])

    def test_singleton_serial_route(self):
        self.queue.enqueue(self.entry('a'))
        self.assertIsNone(self.queue.claim(minimum=2))
        self.assertEqual(len(self.queue.claim(minimum=1)['members']), 1)

    def test_control_operation_is_exclusive(self):
        e = self.entry('a'); e['logical_identity']['operation'] = 'source_content'
        self.queue.enqueue(e); self.queue.enqueue(self.entry('b'))
        self.assertEqual(len(self.queue.claim()['members']), 1)

    def test_original_and_alias_dedup(self):
        e = self.entry('a')
        self.queue.enqueue(e)
        self.assertEqual(self.queue.enqueue(e)['status'], 'ALREADY_REGISTERED')
        alias = {**e, 'request_id': 'e'*64, 'executor_alias': 'new-transport'}
        with self.assertRaisesRegex(ValueError, 'ALREADY_REGISTERED'):
            self.queue.enqueue(alias)

    def test_source_order_does_not_evade_dedup(self):
        e = self.entry('a'); self.queue.enqueue(e)
        e['request_id'] = 'e'*64; e['logical_identity']['source_ids'].reverse()
        with self.assertRaisesRegex(ValueError, 'ALREADY_REGISTERED'):
            self.queue.enqueue(e)

    def test_actual_independent_round_is_distinct(self):
        e = self.entry('a'); self.queue.enqueue(e)
        e['request_id'] = 'e'*64; e['logical_identity']['round_id'] = 'round-2'
        self.assertEqual(self.queue.enqueue(e)['status'], 'READY')

    def test_pin_drift_before_admission(self):
        e = self.entry('a'); self.queue.enqueue(e)
        Path(e['owner_reservation']['path']).write_text('changed')
        with self.assertRaisesRegex(ValueError, 'ARTIFACT_CHANGED'):
            self.queue.claim()
        self.assertEqual(self.queue.status()['groups'], [])

    def test_two_coordinators_cannot_claim_four(self):
        for task in 'abcd': self.queue.enqueue(self.entry(task))
        self.queue.claim()
        other = ReadyQueue(self.root / 'queue.db', self.policy)
        try:
            with self.assertRaisesRegex(ValueError, 'UNRETURNED_GROUP'):
                other.claim()
        finally:
            other.db.close()

    def test_expired_admission_zero_network_can_requeue_same_id(self):
        e = self.entry('a'); self.queue.enqueue(e)
        group = self.queue.claim(now=100)
        with self.assertRaisesRegex(ValueError, 'EXPIRED_OR_FUTURE'):
            self.queue.mark_started(group['group_id'], now=701)
        self.queue.cancel_unstarted(group['group_id'], 'adapter never started')
        fresh = self.queue.claim(now=1000)
        self.assertEqual(fresh['expires_epoch'], 1600)
        self.assertEqual(fresh['members'][0]['request_id'], e['request_id'])

    def test_started_timeout_does_not_release(self):
        group = self.start(self.entry('a'), self.entry('b'))
        with self.assertRaisesRegex(ValueError, 'UNRETURNED_GROUP'):
            self.queue.claim(now=100000)
        with self.assertRaisesRegex(ValueError, 'MAY_HAVE_SENT'):
            self.queue.cancel_unstarted(group['group_id'], 'deadline passed')
        self.queue.finish(group['group_id'], self.proof(group))

    def test_unknown_quarantine_needs_real_return(self):
        group = self.start(self.entry('a'), self.entry('b'))
        self.queue.quarantine(group['group_id'], 'original stream unknown')
        with self.assertRaisesRegex(ValueError, 'UNRETURNED_GROUP'):
            self.queue.claim()
        self.assertEqual(self.queue.finish(group['group_id'], self.proof(group))['status'], 'RETURNED')

    def test_partial_group_and_mismatched_release_rejected(self):
        group = self.start(self.entry('a'), self.entry('b'))
        with self.assertRaisesRegex(ValueError, 'MEMBERS_MISMATCH'):
            self.queue.finish(group['group_id'], self.proof(group, omit_member=True))
        with self.assertRaisesRegex(ValueError, 'ACTUAL_RELEASE'):
            self.queue.finish(group['group_id'], self.proof(group, wrong_lease=True))
        self.assertEqual(self.queue.status()['groups'][0]['state'], 'STARTED')

    def test_zero_citations_terminal_fails_review_but_releases(self):
        group = self.start(self.entry('a'), self.entry('b'))
        self.queue.enqueue(self.entry('c'))
        returned = self.queue.finish(group['group_id'], self.proof(group, failed=True))
        self.assertFalse(returned['review_credit'])
        self.assertEqual(set(returned['outcomes'].values()), {'FAILED'})
        self.assertEqual(self.queue.claim()['members'][0]['task_id'], 'c')

    def test_known_quota_failure_pauses_after_release(self):
        group = self.start(self.entry('a'), self.entry('b'))
        self.queue.finish(group['group_id'], self.proof(group, failed=True, quota=True))
        self.queue.enqueue(self.entry('c'))
        with self.assertRaisesRegex(ValueError, 'ACCOUNT_PAUSED'):
            self.queue.claim()

    def test_dependencies_block_only_their_task(self):
        a = self.entry('a'); a2 = self.entry('a', 2)
        a['dependencies'] = ['f'*64]
        for e in (a, a2, self.entry('b')): self.queue.enqueue(e)
        self.assertEqual([e['task_id'] for e in self.queue.claim()['members']], ['b'])

    def test_capacity_three_is_not_enabled_by_configuration(self):
        with self.assertRaisesRegex(ValueError, 'ONLY_VALIDATED_CAPACITY'):
            ReadyQueue(self.root/'three.db', {**self.policy, 'capacity': 3})

    def test_foreign_capability_and_existing_conversation_rejected(self):
        bad = {**self.policy, 'account_key': 'another-account'}
        with self.assertRaisesRegex(ValueError, 'MATCHING_LIVE_CAPABILITY'):
            ReadyQueue(self.root/'foreign.db', bad)
        e = self.entry('a'); e['logical_identity']['conversation_id'] = 'existing'
        with self.assertRaisesRegex(ValueError, 'FRESH_CONVERSATION'):
            self.queue.enqueue(e)

    def test_receipt_hash_mutation_cannot_release(self):
        group = self.start(self.entry('a'))
        proof = self.proof(group)
        Path(proof['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'ARTIFACT_CHANGED'):
            self.queue.finish(group['group_id'], proof)

    def test_wrong_original_prompt_does_not_release(self):
        group = self.start(self.entry('a'))
        group['members'][0]['payload']['prompt'] = 'a different question'
        with self.assertRaisesRegex(ValueError, 'ORIGINAL_PROMPT'):
            self.queue.finish(group['group_id'], self.proof(group))

    def test_executable_pin_drift_stops_admission(self):
        artifact = self.artifact({'fixed_executor': 1})
        policy = {**self.policy, 'protected_artifacts': [artifact]}
        queue = ReadyQueue(self.root/'pinned.db', policy)
        try:
            queue.enqueue(self.entry('a'))
            Path(artifact['path']).write_text('changed')
            with self.assertRaisesRegex(ValueError, 'ARTIFACT_CHANGED'):
                queue.claim()
        finally:
            queue.db.close()

    def test_retry_requires_failed_original_and_new_identity(self):
        e = self.entry('a')
        prior = self.artifact({'request_id': 'f'*64, 'status': 'COMPLETE', 'network_terminal': True, 'mode': 'real'})
        e['retry_of'] = {'request_id': 'f'*64, 'receipt': prior, 'scope': 'narrow required coverage'}
        with self.assertRaisesRegex(ValueError, 'TERMINAL_FAILED_RETRY'):
            self.queue.enqueue(e)


if __name__ == '__main__':
    unittest.main(verbosity=2)
