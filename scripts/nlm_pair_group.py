"""Actual pair budget/lock seams beneath the unchanged global account broker.

This module does not request/grant/release tickets or perform network calls.
The future managed SDK pair parent invokes these seams under its original
broker ticket; independently invoking single-query runtime twice is forbidden.
"""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time

from nlm_pair_budget import PairBudget
from nlm_pair_identity import verify_admitted_request
from nlm_pair_locks import own_existing_locks


def checked_json(reference):
    path = Path(reference['path']).resolve(strict=True)
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != reference['sha256']:
        raise ValueError('PAIR_INPUT_PIN_CHANGED')
    if 'bytes' in reference and len(body) != reference['bytes']:
        raise ValueError('PAIR_INPUT_SIZE_CHANGED')
    return json.loads(body)


def live_ticket(config, lease, *, worker=False):
    queue = Path(config['resource_root']).resolve(strict=True) / 'queue.sqlite3'
    with closing(sqlite3.connect(queue.as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT * FROM tickets WHERE id=?', (lease['id'],)).fetchone()
        if row is None:
            raise ValueError('ORIGINAL_TICKET_MISSING')
        row = dict(row)
        resource = db.execute('SELECT external_locks FROM resources WHERE name=?',
                              ('nlm-account:' + config['account_key'],)).fetchone()
    if (row['status'] != 'ACTIVE' or row['token'] != lease['token']
            or row['task_id'] != config['task_id']
            or row['resource'] != 'nlm-account:' + config['account_key']
            or row['expires'] <= time.time()
            or resource is None or json.loads(resource[0]) != config['external_locks']
            or (worker and row['pgid'] != os.getpgrp())):
        raise ValueError('LIVE_ORIGINAL_ACCOUNT_GROUP_REQUIRED')
    return row


def admit_under_original_lease(config, lease, requests, authority):
    """Reuse original PairBudget, with the total cap inside its single write txn."""
    live_ticket(config, lease)
    if any(request.get('task_id') != config['task_id'] for request in requests):
        raise ValueError('SAME_GROUP_TASK_REQUIRED')
    budget = PairBudget(config['budget_root'])
    try:
        # Allocation must already be a reviewed two-query allocation. This seam
        # cannot allocate silently or modify any historical task's budget.
        row = budget.db.execute('SELECT query_budget FROM allocations WHERE account=? AND task_id=?',
                                (config['account_key'], config['task_id'])).fetchone()
        if row is None or row[0] != 2:
            raise ValueError('EXPLICIT_ORIGINAL_TWO_QUERY_ALLOCATION_REQUIRED')
        return budget.admit_pair(config['account_key'], requests, authority)
    finally:
        budget.db.close()


def await_worker_ticket(config, lease, *, startup_seconds=2):
    """Original broker publishes pgid after Popen; wait only for that publication."""
    if not 0 <= startup_seconds <= 2:
        raise ValueError('BOUNDED_WORKER_STARTUP_REQUIRED')
    deadline = time.monotonic() + startup_seconds
    while True:
        # Every observation still checks exact ticket/token/account/task,
        # ACTIVE state, expiry and the original resource's lock set.
        row = live_ticket(config, lease)
        if row['pgid'] == os.getpgrp():
            return row
        if row['pgid'] is not None:
            raise ValueError('DIFFERENT_PUBLISHED_PROCESS_GROUP')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError('ORIGINAL_BROKER_PGID_PUBLICATION_TIMEOUT')
        time.sleep(min(.025, remaining))


def validate_pair_members(config, members):
    """Validate both original receipts before launching either SDK process."""
    if len(members) != 2:
        raise ValueError('TWO_EXPLICIT_CHILDREN_REQUIRED')
    configurations = [checked_json(member['config']) for member in members]
    paths = [Path(member['config']['path']).resolve(strict=True) for member in members]
    if len(set(paths)) != 2 or len({(p.stat().st_dev, p.stat().st_ino) for p in paths}) != 2:
        raise ValueError('DISTINCT_MEMBER_CONFIG_FILES_REQUIRED')
    ids = [member['origin_request_id'] for member in members]
    if len(set(ids)) != 2:
        raise ValueError('DISTINCT_ORIGINAL_REQUEST_IDS_REQUIRED')
    receipts = [Path(member['receipt_dir']).resolve(strict=True) for member in members]
    if any(a == b or a.is_relative_to(b) or b.is_relative_to(a)
           for a, b in [(receipts[0], receipts[1])]):
        raise ValueError('NONOVERLAPPING_ORIGINAL_RECEIPT_DIRS_REQUIRED')
    budget_root = Path(config['budget_root']).resolve(strict=True)
    for member, cfg, receipt in zip(members, configurations, receipts):
        if str(receipt) != member['receipt_dir'] or receipt != budget_root / 'receipts' / member['origin_request_id']:
            raise ValueError('CANONICAL_ORIGINAL_RECEIPT_REQUIRED')
        if any(path == receipt or path.is_relative_to(receipt) for path in paths):
            raise ValueError('CONFIG_MUST_BE_OUTSIDE_MUTABLE_RECEIPTS')
        if Path(member['request']['path']) != receipt / 'request.json':
            raise ValueError('ORIGINAL_REQUEST_PIN_REQUIRED')
        request = checked_json(member['request'])
        if any(cfg[key] != config[key] for key in ('task_id', 'account_key', 'budget_root', 'resource_root', 'external_locks', 'python')):
            raise ValueError('CHILD_GROUP_BINDING_MISMATCH')
        if request.get('notebook_id') != cfg['notebook_id'] or request.get('source_ids') != cfg['source_ids']:
            raise ValueError('ORIGINAL_NOTEBOOK_SOURCE_BINDING_REQUIRED')
        with closing(sqlite3.connect((budget_root / 'budget.sqlite3').as_uri() + '?mode=ro', uri=True)) as db:
            verify_admitted_request(db, member['origin_request_id'], request, cfg)
    if len({cfg['notebook_id'] for cfg in configurations}) != 2:
        raise ValueError('DIFFERENT_NOTEBOOKS_REQUIRED')
    return configurations


def worker_children(config, lease, members, output, *, total_seconds=240):
    """Run exactly two pinned SDK child command arrays with inherited locks.

    Missing/failing child evidence returns pending; this helper cannot release a
    lease. The original broker parent owns the whole process group's hard limit.
    """
    await_worker_ticket(config, lease)
    if len(members) != 2:
        raise ValueError('TWO_EXPLICIT_CHILDREN_REQUIRED')
    child = Path(__file__).resolve().with_name('nlm_sdk_pair_child.py')
    child_body = child.read_bytes()
    child_pin = {'path': str(child), 'bytes': len(child_body),
                 'sha256': hashlib.sha256(child_body).hexdigest()}
    if config['pair_child'] != child_pin:
        raise ValueError('PAIR_CHILD_PIN_CHANGED')
    python = Path(config['python']['path']).resolve(strict=True)
    python_body = python.read_bytes()
    if (len(python_body) != config['python']['bytes']
            or hashlib.sha256(python_body).hexdigest() != config['python']['sha256']):
        raise ValueError('PAIR_PYTHON_PIN_CHANGED')
    validate_pair_members(config, members)
    if total_seconds <= 0 or total_seconds > 240:
        raise ValueError('ORIGINAL_CHILD_DEADLINE_REQUIRED')
    out = Path(output)
    out.mkdir(exist_ok=False)
    children = []
    streams = []
    began = time.monotonic()
    result = {'status': 'PENDING', 'children': [], 'worker_pid': os.getpid(),
              'pgid': os.getpgrp(), 'lease_id': lease['id'], 'release_authorized': False}
    try:
        with own_existing_locks(config['external_locks']) as locks:
            lock_path = out / 'LOCKS.json'
            body = (json.dumps(locks, indent=2) + '\n').encode()
            with lock_path.open('xb') as handle:
                handle.write(body)
            lock_sha = hashlib.sha256(body).hexdigest()
            fds = tuple(row['fd'] for row in locks['locks'])
            for index, member in enumerate(members):
                live_ticket(config, lease, worker=True)
                checked_json(member['config'])
                if hashlib.sha256(child.read_bytes()).hexdigest() != child_pin['sha256']:
                    raise ValueError('CHILD_CODE_CHANGED')
                stdout = (out / f'{index}.stdout').open('xb')
                stderr = (out / f'{index}.stderr').open('xb')
                streams.extend((stdout, stderr))
                argv = [str(python), '-BE', str(child),
                        '--config', member['config']['path'], '--config-sha256', member['config']['sha256'],
                        '--output-dir', member['receipt_dir'],
                        '--locks', str(lock_path), '--locks-sha256', lock_sha,
                        '--lock-fds', ','.join(map(str, fds))]
                process = subprocess.Popen(argv, pass_fds=fds, stdout=stdout, stderr=stderr)
                children.append(process)
                result['children'].append({'index': index, 'pid': process.pid,
                                           'started_monotonic': time.monotonic()})
            for row, process in zip(result['children'], children):
                row['exit_code'] = process.wait(timeout=max(.001, total_seconds - (time.monotonic() - began)))
                row['ended_monotonic'] = time.monotonic()
                row['reaped'] = True
            result['status'] = 'CHILDREN_REAPED_NOT_NETWORK_ACCEPTED'
    except BaseException as exc:
        result['error_type'] = type(exc).__name__
        result['children_alive'] = [p.pid for p in children if p.poll() is None]
        # No guessed remote terminal, cancellation, retry or lease release.
    finally:
        for stream in streams:
            stream.close()
        with (out / 'WORKER-RESULT.json').open('x') as handle:
            handle.write(json.dumps(result, indent=2) + '\n')
    return result
