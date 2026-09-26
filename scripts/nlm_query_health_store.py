"""Persistent query health from original returns. No network, budget or lease writes."""
from __future__ import annotations

import argparse
import contextlib
from copy import deepcopy
import json
from pathlib import Path
import re
import sqlite3
import time

from nlm_query_health import initial_state, record_return, authorize_recovery, assert_admission
from evidence_refs import checked_bytes


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def checked(ref):
    return checked_bytes(ref)


def checked_json(ref):
    return json.loads(checked(ref))


def verify_embedded_pins(value):
    if isinstance(value, dict):
        if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
            checked(value)
        for child in value.values():
            verify_embedded_pins(child)
    elif isinstance(value, list):
        for child in value:
            verify_embedded_pins(child)


def verify_real_return(ref, account_key):
    """Accept the existing pair and normalized serial schemas without editing them."""
    returned = checked_json(ref)
    verify_embedded_pins(returned)
    release = checked_json(returned['release'])
    terminal = checked_json(returned['terminal'])
    verify_embedded_pins(release)
    verify_embedded_pins(terminal)
    if (release.get('status') != 'RELEASED'
            or release.get('resource') != 'nlm-account:' + account_key
            or release.get('release_proof', {}).get('external_locks_probed_and_released') is not True
            or terminal.get('mode') != 'real'
            or terminal.get('status') not in ('COMPLETE', 'FAILED')
            or terminal.get('remote_terminal') is not True
            or terminal.get('process_group_empty') is not True
            or terminal.get('in_flight_requests') != []
            or terminal.get('resource_lease', {}).get('id') != release.get('id')):
        raise ValueError('ORIGINAL_TERMINAL_AND_RELEASE_REQUIRED')
    members = returned.get('members', [])
    if not 1 <= len(members) <= 2:
        raise ValueError('VALIDATED_CAPACITY_EXCEEDED')
    ids = []
    for member in members:
        receipt = checked_json(member['receipt'])
        verify_embedded_pins(receipt)
        key = member.get('origin_request_id', '')
        if (not re.fullmatch(r'[0-9a-f]{64}', key)
                or member.get('network_terminal') is not True
                or receipt.get('mode') != 'real'
                or receipt.get('operation') != 'query'
                or receipt.get('account_key') != account_key
                or receipt.get('request_id') != key
                or receipt.get('resource_lease', {}).get('id') != release['id']):
            raise ValueError('ORIGINAL_QUERY_IDENTITY_REQUIRED')
        request = checked_json(receipt['request'])
        if request.get('operation') != 'query' or request.get('notebook_id') != receipt.get('notebook_id'):
            raise ValueError('ORIGINAL_REQUEST_MISMATCH')
        raw = checked_json(receipt['raw_answer'])
        answer = raw.get('answer', '')
        refs = raw.get('references', [])
        if not isinstance(answer, str) or not isinstance(refs, list):
            raise ValueError('INVALID_RAW_ANSWER')
        if (receipt.get('answer_characters') != len(answer)
                or receipt.get('native_citations') != len(refs)):
            raise ValueError('RAW_ANSWER_COUNTS_MISMATCH')
        if receipt.get('status') == 'COMPLETE' and (
                not answer.strip() or not refs or any(not isinstance(r, dict)
                or not r.get('source_id') or not r.get('cited_text') for r in refs)):
            raise ValueError('COMPLETE_NATIVE_REFERENCES_REQUIRED')
        if receipt.get('http_status') is not None and 'native_fetch' in receipt:
            fetch = checked_json(receipt['native_fetch'])
            if 'http_status' in fetch and fetch['http_status'] != receipt['http_status']:
                raise ValueError('HTTP_STATUS_EVIDENCE_MISMATCH')
        ids.append(key)
    if len(ids) != len(set(ids)):
        raise ValueError('DUPLICATE_ORIGINAL_QUERY')
    # The pure state machine checks terminal flags, release identity and COMPLETE
    # contracts too. This temporary result never establishes current availability.
    record_return(initial_state(account_key), ref)
    return returned


class QueryHealthJournal:
    """One task-bound health journal reused by the actual resource coordinator."""

    def __init__(self, database, account_key, *, create=False):
        path = Path(database)
        if not path.is_absolute():
            raise ValueError('ABSOLUTE_DATABASE_REQUIRED')
        if not account_key:
            raise ValueError('ACCOUNT_REQUIRED')
        if create:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb'):
                pass
        elif not path.is_file():
            raise FileNotFoundError('HEALTH_STATE_MISSING_NO_AUTOMATIC_RESET')
        self.account_key = account_key
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        if create:
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.executescript('''
                CREATE TABLE health (id INTEGER PRIMARY KEY CHECK(id=1), account TEXT NOT NULL,
                    initialized INTEGER NOT NULL, state TEXT NOT NULL);
                CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL,
                    kind TEXT NOT NULL, evidence TEXT NOT NULL, state TEXT NOT NULL);
            ''')
            state = initial_state(account_key)
            state.update(mode='PAUSED', reason='INITIAL_EVIDENCE_REQUIRED')
            self.db.execute('INSERT INTO health VALUES(1,?,0,?)', (account_key, canonical(state)))
        row = self.db.execute('SELECT account FROM health WHERE id=1').fetchone()
        if not row or row['account'] != account_key:
            self.db.close()
            raise ValueError('PERSISTED_ACCOUNT_MISMATCH')

    @contextlib.contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def _load(self, *, initialized=True):
        row = self.db.execute('SELECT * FROM health WHERE id=1').fetchone()
        if initialized and not row['initialized']:
            raise ValueError('REAL_RETURN_HISTORY_REQUIRED')
        state = json.loads(row['state'])
        if state.get('account_key') != self.account_key:
            raise ValueError('CORRUPT_ACCOUNT_STATE')
        return state

    def _save(self, state, kind, evidence):
        self.db.execute('UPDATE health SET state=? WHERE id=1', (canonical(state),))
        self.db.execute('INSERT INTO events(at,kind,evidence,state) VALUES(?,?,?,?)',
                        (time.time(), kind, canonical(evidence), canonical(state)))

    def bootstrap(self, returns):
        if not returns:
            raise ValueError('REAL_RETURN_HISTORY_REQUIRED')
        with self.transaction():
            if self.db.execute('SELECT initialized FROM health WHERE id=1').fetchone()[0]:
                raise ValueError('ALREADY_INITIALIZED_NO_RESET')
            state = initial_state(self.account_key)
            observed = []
            for ref in returns:
                value = verify_real_return(ref, self.account_key)
                state = record_return(state, ref)
                observed.extend(m['origin_request_id'] for m in value['members'])
                self._save(state, 'REPLAY_ORIGINAL_RETURN', ref)
            state['observed_request_ids'] = sorted(set(observed))
            state['recovery_claimed'] = False
            self._save(state, 'BOOTSTRAP_COMPLETE', {'returns': returns})
            self.db.execute('UPDATE health SET initialized=1 WHERE id=1')
        return deepcopy(state)

    def record(self, ref):
        with self.transaction():
            state = self._load()
            value = verify_real_return(ref, self.account_key)
            updated = record_return(state, ref)
            if updated == state:
                return deepcopy(state)
            updated['observed_request_ids'] = sorted(set(state.get('observed_request_ids', []))
                | {m['origin_request_id'] for m in value['members']})
            if state['mode'] == 'RECOVERY':
                updated['recovery_claimed'] = False
            self._save(updated, 'ORIGINAL_RETURN', ref)
        return deepcopy(updated)

    def recover(self, ref):
        with self.transaction():
            state = self._load()
            checked_json(ref)
            updated = authorize_recovery(state, ref)
            if updated['recovery_request_id'] in state.get('observed_request_ids', []):
                raise ValueError('ALREADY_SENT_REQUEST_CANNOT_RECOVER')
            updated['recovery_claimed'] = False
            self._save(updated, 'FIXED_RECOVERY_DECISION', ref)
        return deepcopy(updated)

    def admit(self, request_ids):
        """Call inside the adapter's existing broker/OS-lock boundary before POST."""
        with self.transaction():
            state = self._load()
            if any(not re.fullmatch(r'[0-9a-f]{64}', key) for key in request_ids):
                raise ValueError('ORIGINAL_REQUEST_ID_REQUIRED')
            assert_admission(state, request_ids)
            if set(request_ids) & set(state.get('observed_request_ids', [])):
                raise ValueError('ALREADY_SENT_REQUEST')
            if state['mode'] == 'RECOVERY':
                if state.get('recovery_claimed'):
                    raise ValueError('RECOVERY_ALREADY_ADMITTED')
                state['recovery_claimed'] = True
                self._save(state, 'RECOVERY_ADMITTED_ONCE', {'request_ids': request_ids})
            return {'health_admission': 'PASS', 'mode': state['mode'],
                    'request_ids': request_ids, 'network_authorized': False,
                    'budget_or_lease_changed': False, 'review_credit': False}

    def status(self):
        return deepcopy(self._load(initialized=False))

    def close(self):
        self.db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['bootstrap', 'record', 'recover', 'admit', 'status'])
    parser.add_argument('--database', required=True)
    parser.add_argument('--account', required=True)
    parser.add_argument('--input')
    parser.add_argument('--sha256')
    parser.add_argument('--request-id', action='append')
    args = parser.parse_args()
    ref = {'path': args.input, 'sha256': args.sha256} if args.input and args.sha256 else None
    if args.operation in ('bootstrap', 'record', 'recover') and ref is None:
        parser.error('--input and --sha256 required')
    returns = checked_json(ref)['returns'] if args.operation == 'bootstrap' else None
    if returns is not None:
        for value in returns:
            verify_real_return(value, args.account)
    journal = QueryHealthJournal(args.database, args.account, create=args.operation == 'bootstrap')
    try:
        if args.operation == 'bootstrap':
            result = journal.bootstrap(returns)
        elif args.operation == 'record':
            result = journal.record(ref)
        elif args.operation == 'recover':
            result = journal.recover(ref)
        elif args.operation == 'admit':
            result = journal.admit(args.request_id or [])
        else:
            result = journal.status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        journal.close()


if __name__ == '__main__':
    main()
