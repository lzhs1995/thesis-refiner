"""Local admission decisions from real returns; no network, budget or lease writes."""
from copy import deepcopy
import json
from evidence_refs import checked_bytes, same_identity


def checked_json(ref):
    return json.loads(checked_bytes(ref))


def initial_state(account_key):
    return {'account_key': account_key, 'mode': 'HEALTHY', 'empty_responses': 0,
            'returns': {}, 'recovery_decisions': [], 'recovery_request_id': None}


def record_return(state, return_ref):
    """Apply once after the scheduler accepts an actual terminal/release proof."""
    value = checked_json(return_ref)
    release = checked_json(value['release'])
    if (release.get('status') != 'RELEASED'
            or release.get('resource') != 'nlm-account:' + state['account_key']):
        raise ValueError('ACCOUNT_RELEASE_REQUIRED')
    key = release['id']
    if key in state['returns']:
        if not same_identity(state['returns'][key], return_ref):
            raise ValueError('RETURN_IDENTITY_CHANGED')
        return deepcopy(state)
    members = value['members']
    if not 1 <= len(members) <= 2:
        raise ValueError('VALIDATED_CAPACITY_EXCEEDED')
    receipts = [checked_json(m['receipt']) for m in members]
    ids = [m['origin_request_id'] for m in members]
    if len(set(ids)) != len(ids):
        raise ValueError('DUPLICATE_ORIGIN')
    for member, receipt in zip(members, receipts):
        if (receipt.get('mode') != 'real' or not receipt.get('network_terminal')
                or not receipt.get('remote_terminal') or not receipt.get('process_group_empty')
                or receipt.get('status') not in ('COMPLETE', 'FAILED')
                or member.get('status') != receipt['status']
                or member.get('origin_request_id') != receipt.get('request_id')
                or receipt.get('account_key') != state['account_key']
                or receipt.get('resource_lease', {}).get('id') != key):
            raise ValueError('ORIGINAL_TERMINAL_REQUIRED')
        if receipt['status'] == 'COMPLETE' and not (
                receipt.get('fully_received') and receipt.get('source_contract_valid')
                and receipt.get('answer_characters', 0) > 0 and receipt.get('native_citations', 0) > 0):
            raise ValueError('COMPLETE_ANSWER_CONTRACT_REQUIRED')
    empty = sum(r.get('fully_received') is True and r.get('answer_characters') == 0
                and r.get('native_citations') == 0 for r in receipts)
    hard = any(r.get('quota_limited') is True or r.get('http_status') in (401, 403, 429)
               for r in receipts)
    incomplete = any(r.get('fully_received') is not True for r in receipts)
    result = deepcopy(state)
    result['returns'][key] = return_ref
    result['last_return'] = return_ref
    result['empty_responses'] = state['empty_responses'] + empty if empty else 0
    recovering = state['mode'] == 'RECOVERY'
    if recovering and ids != [state['recovery_request_id']]:
        raise ValueError('RECOVERY_ORIGINAL_ID_MISMATCH')
    if recovering:
        result['mode'] = 'HEALTHY' if receipts[0]['status'] == 'COMPLETE' and not (hard or incomplete) else 'PAUSED'
        result['reason'] = 'RECOVERY_ANSWER_VALID' if result['mode'] == 'HEALTHY' else 'RECOVERY_FAILED'
        result['recovery_request_id'] = None
        if result['mode'] == 'PAUSED':
            result['pause_return'] = return_ref
    elif hard or incomplete or result['empty_responses'] >= 2 or (empty and len(members) == 1):
        result['mode'] = 'PAUSED'
        result['reason'] = 'EXPLICIT_HTTP_OR_QUOTA_FAILURE' if hard else (
            'TERMINAL_TRANSPORT_FAILURE' if incomplete else 'EMPTY_ANSWER_CAUSE_UNKNOWN')
        result['pause_return'] = return_ref
    # A late successful ordinary return never clears an existing pause.
    return result


def authorize_recovery(state, decision_ref):
    """Accept a coordinator's new evidence-based decision for one necessary ID."""
    decision = checked_json(decision_ref)
    if (state['mode'] != 'PAUSED' or decision.get('status') != 'FIXED_SINGLE_RECOVERY_DECISION'
            or decision.get('account_key') != state['account_key']
            or decision.get('recovery_condition_met') is not True
            or decision.get('new_evidence_since_failure') is not True
            or decision.get('query_cap') != 1 or decision.get('automatic_retry') is not False
            or not decision.get('necessary_existing_request')
            or not decision.get('evidence')
            or not same_identity(decision.get('failure_return'), state.get('pause_return', state.get('last_return')))):
        raise ValueError('NEW_RECOVERY_EVIDENCE_REQUIRED')
    if decision_ref['sha256'] in state['recovery_decisions']:
        raise ValueError('RECOVERY_DECISION_ALREADY_USED')
    for ref in decision['evidence']:
        checked_json(ref)
    request_id = decision['necessary_existing_request']
    if len(request_id) != 64 or any(c not in '0123456789abcdef' for c in request_id):
        raise ValueError('ORIGINAL_REQUEST_ID_REQUIRED')
    result = deepcopy(state)
    result.update(mode='RECOVERY', recovery_request_id=request_id)
    result['recovery_decisions'].append(decision_ref['sha256'])
    result['recovery_decision'] = decision_ref
    return result


def assert_admission(state, original_ids):
    if not original_ids or len(original_ids) > 2 or len(set(original_ids)) != len(original_ids):
        raise ValueError('INVALID_QUERY_GROUP')
    if state['mode'] == 'PAUSED':
        raise ValueError('QUERY_HEALTH_PAUSED')
    if state['mode'] == 'RECOVERY' and original_ids != [state['recovery_request_id']]:
        raise ValueError('ONLY_FIXED_SINGLE_RECOVERY_ALLOWED')
    if state['mode'] not in ('HEALTHY', 'RECOVERY'):
        raise ValueError('UNKNOWN_QUERY_HEALTH_STATE')
