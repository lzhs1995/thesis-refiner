"""Aggregate the original S39 10-query cap inside PairBudget's transaction.

This helper never opens a database, begins/commits a transaction, allocates a
budget, or sends a request. The caller must call it immediately after the
original PairBudget BEGIN IMMEDIATE and before either original INSERT.
"""
import json


class TotalBudgetError(ValueError):
    pass


def check_total_cap(db, account, requests, scope):
    if not db.in_transaction:
        raise TotalBudgetError('ORIGINAL_WRITE_TRANSACTION_REQUIRED')
    if scope.get('schema') != 's39-original-query-cap-v1' or scope.get('account_key') != account:
        raise TotalBudgetError('ORIGINAL_SCOPE_REQUIRED')
    historical = scope.get('historical_task_ids', [])
    task = scope.get('new_pair_task_id')
    if (len(historical) != 3 or len(set(historical)) != 3 or not task or task in historical
            or scope.get('total_query_cap') != 10 or scope.get('historical_queries_used') != 8):
        raise TotalBudgetError('FIXED_EIGHT_OF_TEN_SCOPE_REQUIRED')
    if len(requests) != 2 or any(r.get('task_id') != task or r.get('operation') != 'query'
                                  or r.get('account_key') != account for r in requests):
        raise TotalBudgetError('ONLY_TWO_NEW_SCOPED_QUERIES')
    existing_ids = scope.get('historical_request_ids', [])
    if len(existing_ids) != 8 or len(set(existing_ids)) != 8:
        raise TotalBudgetError('EIGHT_ORIGINAL_REQUEST_IDS_REQUIRED')
    marks = ','.join('?' for _ in historical)
    original = db.execute(
        f"SELECT id FROM requests WHERE account=? AND operation='query' AND task_id IN ({marks})",
        (account, *historical)).fetchall()
    # Every state counts, including FAILED/UNCERTAIN; no refunds or old-row edits.
    if {row[0] for row in original} != set(existing_ids):
        raise TotalBudgetError('HISTORICAL_QUERY_SET_CHANGED_REVIEW_ORIGINAL_ROWS')
    used = len(original) + db.execute(
        "SELECT count(*) FROM requests WHERE account=? AND task_id=? AND operation='query'",
        (account, task)).fetchone()[0]
    if used + len(requests) > scope['total_query_cap']:
        raise TotalBudgetError('ORIGINAL_TEN_QUERY_CAP_EXHAUSTED')
    return {'historical_queries': len(original), 'used_before': used,
            'admitting': len(requests), 'used_after': used + len(requests)}


def read_scope(path, expected_sha256):
    """The root-approved immutable scope is checked before budget construction."""
    import hashlib
    from pathlib import Path
    body = Path(path).read_bytes()
    if hashlib.sha256(body).hexdigest() != expected_sha256:
        raise TotalBudgetError('SCOPE_PIN_CHANGED')
    return json.loads(body)
