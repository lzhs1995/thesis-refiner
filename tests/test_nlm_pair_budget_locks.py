import ast
import concurrent.futures
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest


if sys.version_info < (3, 11):
    raise unittest.SkipTest("Pair controller requires Python 3.11+")

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from nlm_pair_budget import PairBudget, runtime, request_key
from nlm_pair_group import admit_under_original_lease
from nlm_pair_locks import own_existing_locks
from nlm_pair_identity import verify_admitted_request


def pin(path):
    body = Path(path).read_bytes()
    return {'path': str(path), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def fixture(root):
    budget_root = root / 'budget'
    budget_root.mkdir()
    budget = runtime.Budget(budget_root)
    budget.configure('account', {'regime': 'unknown', 'observed_at': 1, 'source': 'synthetic-only'})
    budget.allocate('account', 'pair', 2)
    old = [(f'old-{i}', 'account', 'main' if i < 6 else 'failed' if i == 6 else 'success',
            'query', float(i), 'FAILED' if i in (5, 6) else 'COMPLETE', None, None, 'final') for i in range(8)]
    budget.db.executemany('INSERT INTO requests VALUES(?,?,?,?,?,?,?,?,?)', old)
    budget.db.close()
    resource_root = root / 'resources'
    resource_root.mkdir()
    lock = root / 'transport.lock'
    lock.touch()
    db = sqlite3.connect(resource_root / 'queue.sqlite3')
    db.executescript('CREATE TABLE tickets(id TEXT,status TEXT,token TEXT,task_id TEXT,resource TEXT,expires REAL,pgid INTEGER); CREATE TABLE resources(name TEXT,external_locks TEXT);')
    db.execute('INSERT INTO tickets VALUES(?,?,?,?,?,?,?)', ('ticket', 'ACTIVE', 'token', 'pair', 'nlm-account:account', time.time()+120, os.getpgrp()))
    db.execute('INSERT INTO resources VALUES(?,?)', ('nlm-account:account', json.dumps([str(lock)])))
    db.commit()
    db.close()
    scope = {'schema': 's39-original-query-cap-v1', 'account_key': 'account',
             'historical_task_ids': ['main', 'failed', 'success'], 'new_pair_task_id': 'pair',
             'total_query_cap': 10, 'historical_queries_used': 8,
             'historical_request_ids': [row[0] for row in old]}
    scope_path = root / 'scope.json'
    scope_path.write_text(json.dumps(scope))
    requests = [{'account_key': 'account', 'task_id': 'pair', 'notebook_id': f'notebook-{i}',
                 'operation': 'query', 'prompt': f'known answer {i}', 'source_ids': [f'source-{i}'],
                 'document_sha256': 'a'*64, 'round_id': 'conditional-pair', 'phase': 'final'} for i in range(2)]
    authority = {'max_in_flight': 2, 'origin_request_ids': [request_key(r) for r in requests],
                 'issued_epoch': time.time()-1, 'expires_epoch': time.time()+120,
                 'total_query_scope': pin(scope_path)}
    config = {'account_key': 'account', 'task_id': 'pair', 'budget_root': str(budget_root),
              'resource_root': str(resource_root), 'external_locks': [str(lock)]}
    return config, {'id': 'ticket', 'token': 'token'}, requests, authority, old


class BudgetIntegration(unittest.TestCase):
    def test_exact_started_identity_required_and_payload_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg, lease, requests, authority, _ = fixture(Path(folder))
            keys = admit_under_original_lease(cfg, lease, requests, authority)
            budget = PairBudget(cfg['budget_root'])
            try:
                self.assertEqual(verify_admitted_request(budget.db, keys[0], requests[0], cfg), keys[0])
                for key, value in [('prompt', 'changed'), ('account_key', 'other'),
                                   ('operation', 'list'), ('round_id', 'other'),
                                   ('conversation_id', 'not-fresh')]:
                    with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'ORIGINAL_REQUEST_KEY_CHANGED'):
                        verify_admitted_request(budget.db, keys[0], {**requests[0], key: value}, cfg)
                for field in ('account_key', 'task_id'):
                    with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'ORIGINAL_STARTED'):
                        verify_admitted_request(budget.db, keys[0], requests[0], {**cfg, field: 'other'})
                for state in ('COMPLETE', 'FAILED', 'UNCERTAIN'):
                    budget.db.execute('UPDATE requests SET state=? WHERE id=?', (state, keys[0]))
                    with self.subTest(state=state), self.assertRaisesRegex(ValueError, 'ORIGINAL_STARTED'):
                        verify_admitted_request(budget.db, keys[0], requests[0], cfg)
            finally:
                budget.db.close()

    def test_ten_used_never_refunded_or_rebooked(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg, lease, requests, authority, old = fixture(Path(folder))
            keys = admit_under_original_lease(cfg, lease, requests, authority)
            budget = PairBudget(cfg['budget_root'])
            try:
                budget.finish(keys[0], 'FAILED', {'synthetic': True})
                budget.finish(keys[1], 'UNCERTAIN', {'synthetic': True})
                before = [tuple(row) for row in budget.db.execute('SELECT * FROM requests ORDER BY id')]
            finally:
                budget.db.close()
            with self.assertRaisesRegex(ValueError, 'TEN_QUERY_CAP_EXHAUSTED'):
                admit_under_original_lease(cfg, lease, requests, authority)
            budget = PairBudget(cfg['budget_root'])
            try:
                self.assertEqual([tuple(row) for row in budget.db.execute('SELECT * FROM requests ORDER BY id')], before)
            finally:
                budget.db.close()

    def test_reordered_or_expired_authority_books_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg, lease, requests, authority, _ = fixture(Path(folder))
            for delta, error in [({'origin_request_ids': list(reversed(authority['origin_request_ids']))}, 'IDENTITIES'),
                                 ({'expires_epoch': 0}, 'EXPIRED'),
                                 ({'issued_epoch': time.time() + 1000}, 'FUTURE')]:
                with self.subTest(delta=delta), self.assertRaisesRegex(ValueError, error):
                    admit_under_original_lease(cfg, lease, requests, {**authority, **delta})
            budget = PairBudget(cfg['budget_root'])
            try:
                self.assertEqual(budget.db.execute('SELECT count(*) FROM requests').fetchone()[0], 8)
            finally:
                budget.db.close()

    def test_actual_pair_admission_blocks_unchanged_single_runtime_and_preserves_eight(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg, lease, requests, authority, old = fixture(Path(folder))
            keys = admit_under_original_lease(cfg, lease, requests, authority)
            self.assertEqual(keys, authority['origin_request_ids'])
            budget = runtime.Budget(cfg['budget_root'])
            try:
                self.assertEqual([tuple(r) for r in budget.db.execute("SELECT * FROM requests WHERE id LIKE 'old-%' ORDER BY id")], old)
                self.assertEqual(budget.db.execute('SELECT count(*) FROM requests').fetchone()[0], 10)
                with self.assertRaisesRegex(runtime.AdmissionError, 'ACCOUNT_REQUEST_IN_FLIGHT'):
                    budget.admit('account', {**requests[0], 'round_id': 'another'})
            finally:
                budget.db.close()

    def test_original_quota_failure_after_first_insert_rolls_back_both(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg, lease, requests, authority, old = fixture(Path(folder))
            budget = runtime.Budget(cfg['budget_root'])
            budget.configure('account', {'regime': 'legacy_daily_count', 'observed_at': time.time()-1,
                'source': 'synthetic-only', 'limit': 1, 'observed_used': 0, 'window_ends_at': time.time()+120})
            budget.db.close()
            with self.assertRaisesRegex(runtime.AdmissionError, 'RESERVE_PROTECTED'):
                admit_under_original_lease(cfg, lease, requests, authority)
            budget = runtime.Budget(cfg['budget_root'])
            self.assertEqual(budget.db.execute('SELECT count(*) FROM requests').fetchone()[0], 8)
            budget.db.close()

    def test_wrong_ticket_and_paused_account_do_not_book(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg, lease, requests, authority, old = fixture(Path(folder))
            with self.assertRaisesRegex(ValueError, 'LIVE_ORIGINAL'):
                admit_under_original_lease(cfg, {**lease, 'token': 'wrong'}, requests, authority)
            budget = runtime.Budget(cfg['budget_root'])
            budget.pause('account')
            budget.db.close()
            with self.assertRaisesRegex(runtime.AdmissionError, 'PAUSED_ACCOUNT'):
                admit_under_original_lease(cfg, lease, requests, authority)
            budget = runtime.Budget(cfg['budget_root'])
            self.assertEqual(budget.db.execute('SELECT count(*) FROM requests').fetchone()[0], 8)
            budget.db.close()

    def test_two_real_group_admissions_race_without_oversubscription(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg, lease, requests, authority, old = fixture(Path(folder))
            barrier = threading.Barrier(2)
            def reserve(_):
                barrier.wait(timeout=5)
                try:
                    return ('ok', admit_under_original_lease(cfg, lease, requests, authority))
                except ValueError:
                    return ('rejected', None)
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                rows = list(pool.map(reserve, (0, 1)))
            self.assertEqual(sorted(r[0] for r in rows), ['ok', 'rejected'])
            budget = runtime.Budget(cfg['budget_root'])
            self.assertEqual(budget.db.execute('SELECT count(*) FROM requests').fetchone()[0], 10)
            budget.db.close()


CHILD = '''import json,sys,os
from pathlib import Path
def no_network(event,args):
    if event.startswith('socket.') and event not in ('socket.__new__','socket.gethostname'):
        raise AssertionError('SYNTHETIC_LOCK_CHILD_NETWORK_FORBIDDEN:'+event)
sys.addaudithook(no_network)
sys.path.insert(0, sys.argv[1])
from nlm_pair_locks import inherited_locks
value=json.loads(Path(sys.argv[2]).read_text())
fds=[x['fd'] for x in value['locks']]
with inherited_locks(value,[x['path'] for x in value['locks']],fds):
    print('HELD',flush=True)
    sys.stdin.readline()
print('CLOSED_DUPLICATES',flush=True)
'''


class LockIntegration(unittest.TestCase):
    def blocked(self, path):
        fd = os.open(path, os.O_RDWR)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            return False
        finally:
            os.close(fd)

    def start(self, root, binding, *, fds=None):
        script = root / 'child.py'
        script.write_text(CHILD)
        manifest = root / f'manifest-{time.time_ns()}.json'
        manifest.write_text(json.dumps(binding))
        return subprocess.Popen([sys.executable, '-BE', str(script), str(SCRIPTS), str(manifest)],
            pass_fds=tuple(fds if fds is not None else [x['fd'] for x in binding['locks']]),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def held(self, process):
        self.assertTrue(select.select([process.stdout], [], [], 5)[0], 'child never reported lock state')
        self.assertEqual(process.stdout.readline().strip(), 'HELD')

    def test_two_children_share_lock_and_early_parent_close_cannot_release_live_sibling(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            lock = root / 'transport.lock'
            lock.touch()
            children = []
            try:
                with own_existing_locks([str(lock)]) as binding:
                    children = [self.start(root, binding), self.start(root, binding)]
                    for child in children:
                        self.held(child)
                    self.assertTrue(self.blocked(lock))
                    children[0].communicate('\n', timeout=5)
                    self.assertEqual(children[0].returncode, 0)
                    self.assertTrue(self.blocked(lock))
                self.assertTrue(self.blocked(lock), 'surviving child must retain original open-description lock')
                children[1].communicate('\n', timeout=5)
                self.assertEqual(children[1].returncode, 0)
                self.assertFalse(self.blocked(lock))
            finally:
                for child in children:
                    if child.poll() is None:
                        child.communicate('\n', timeout=5)

    def test_separate_open_descriptor_cannot_impersonate_inherited_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            lock = root / 'transport.lock'
            lock.touch()
            with own_existing_locks([str(lock)]) as binding:
                impostor = os.open(lock, os.O_RDWR)
                try:
                    changed = {**binding, 'locks': [{**binding['locks'][0], 'fd': impostor}]}
                    child = self.start(root, changed, fds=[impostor])
                    child.communicate('\n', timeout=5)
                    self.assertNotEqual(child.returncode, 0)
                    self.assertTrue(self.blocked(lock))
                finally:
                    os.close(impostor)

    def test_replaced_lock_path_is_rejected_without_unlocking_original(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            lock = root / 'transport.lock'
            lock.touch()
            with own_existing_locks([str(lock)]) as binding:
                original = root / 'original.lock'
                lock.rename(original)
                lock.touch()
                child = self.start(root, binding)
                _, err = child.communicate('\n', timeout=5)
                self.assertNotEqual(child.returncode, 0)
                self.assertIn('INHERITED_LOCK_IDENTITY_CHANGED', err)
                self.assertTrue(self.blocked(original))


if __name__ == "__main__":
    unittest.main()
