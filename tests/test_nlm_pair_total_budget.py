import concurrent.futures
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

if sys.version_info < (3, 11):
    raise unittest.SkipTest("Pair controller requires Python 3.11+")

from pair_total_budget import TotalBudgetError, check_total_cap


def database(path):
    db = sqlite3.connect(path, isolation_level=None, timeout=5)
    db.execute('CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,account TEXT,task_id TEXT,operation TEXT,state TEXT)')
    return db


def setup(path):
    db = database(path)
    rows = [('old-' + str(i), 'account', 'old-main' if i < 6 else 'old-failed' if i == 6 else 'old-success', 'query', 'FAILED' if i in (5, 6) else 'COMPLETE') for i in range(8)]
    db.executemany('INSERT INTO requests VALUES(?,?,?,?,?)', rows)
    db.close()
    return dict(schema='s39-original-query-cap-v1', account_key='account',
        historical_task_ids=['old-main', 'old-failed', 'old-success'],
        new_pair_task_id='new-pair', total_query_cap=10, historical_queries_used=8,
        historical_request_ids=[x[0] for x in rows]), rows


REQUESTS = [{'account_key': 'account', 'task_id': 'new-pair', 'operation': 'query'}] * 2


class TotalBudgetTests(unittest.TestCase):
    def test_failed_history_counts_and_guard_requires_original_transaction(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'budget.sqlite3')
            scope, rows = setup(path)
            db = database(path)
            with self.assertRaisesRegex(TotalBudgetError, 'TRANSACTION'):
                check_total_cap(db, 'account', REQUESTS, scope)
            db.execute('BEGIN IMMEDIATE')
            self.assertEqual(check_total_cap(db, 'account', REQUESTS, scope)['used_after'], 10)
            db.execute('ROLLBACK')
            self.assertEqual(db.execute('SELECT * FROM requests ORDER BY id').fetchall(), rows)
            db.close()

    def test_new_historical_query_or_scope_tamper_fails_without_partial_booking(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'budget.sqlite3')
            scope, _ = setup(path)
            db = database(path)
            db.execute("INSERT INTO requests VALUES('late','account','old-main','query','FAILED')")
            db.execute('BEGIN IMMEDIATE')
            with self.assertRaisesRegex(TotalBudgetError, 'HISTORICAL_QUERY_SET_CHANGED'):
                check_total_cap(db, 'account', REQUESTS, scope)
            db.execute('ROLLBACK')
            db.execute('BEGIN IMMEDIATE')
            with self.assertRaisesRegex(TotalBudgetError, 'FIXED_EIGHT'):
                check_total_cap(db, 'account', REQUESTS, {**scope, 'total_query_cap': 12})
            db.execute('ROLLBACK')
            self.assertEqual(db.execute("SELECT count(*) FROM requests WHERE task_id='new-pair'").fetchone()[0], 0)
            db.close()

    def test_concurrent_reservations_share_one_atomic_total_cap(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'budget.sqlite3')
            scope, rows = setup(path)
            barrier = threading.Barrier(2)
            def book(index):
                db = sqlite3.connect(path, isolation_level=None, timeout=5)
                barrier.wait(timeout=5)
                db.execute('BEGIN IMMEDIATE')
                try:
                    check_total_cap(db, 'account', REQUESTS, scope)
                    db.executemany('INSERT INTO requests VALUES(?,?,?,?,?)',
                        [(f'pair-{index}-{i}', 'account', 'new-pair', 'query', 'STARTED') for i in range(2)])
                    db.execute('COMMIT')
                    return 'booked'
                except TotalBudgetError:
                    db.execute('ROLLBACK')
                    return 'rejected'
                finally:
                    db.close()
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(sorted(pool.map(book, (0, 1))), ['booked', 'rejected'])
            db = database(path)
            self.assertEqual(db.execute('SELECT count(*) FROM requests').fetchone()[0], 10)
            self.assertEqual(db.execute("SELECT * FROM requests WHERE id LIKE 'old-%' ORDER BY id").fetchall(), rows)
            db.close()


if __name__ == '__main__':
    unittest.main()
