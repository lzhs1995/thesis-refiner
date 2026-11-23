"""Bind the exact SDK payload to its original atomic budget admission."""
from nlm_pair_budget import request_key


def verify_admitted_request(db, receipt_id, request, config):
    if request_key(request) != receipt_id:
        raise ValueError('ORIGINAL_REQUEST_KEY_CHANGED')
    row = db.execute('SELECT id,task_id,account,operation,state FROM requests WHERE id=?',
                     (receipt_id,)).fetchone()
    expected = (receipt_id, config['task_id'], config['account_key'], 'query', 'STARTED')
    if row is None or tuple(row) != expected:
        raise ValueError('ORIGINAL_STARTED_ACCOUNT_OPERATION_REQUIRED')
    if (request.get('task_id') != config['task_id']
            or request.get('account_key') != config['account_key']
            or request.get('operation') != 'query'):
        raise ValueError('ORIGINAL_REQUEST_ACCOUNT_OPERATION_REQUIRED')
    return receipt_id
