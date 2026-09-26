#!/usr/bin/env python3
"""Prepare a legacy-compatible recovery decision; no network or live-state writes.

The bound health journal accepts JSON evidence. Scripts, logs and other binary
attachments are checked as bytes and referenced by a JSON manifest, never parsed
as JSON and never executed. Call validate_prepared again at the coordinator's
existing admission boundary, then use its existing journal/queue/broker.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from nlm_query_health import authorize_recovery
from nlm_query_health_store import checked, checked_json, verify_embedded_pins
from evidence_refs import same_identity


def pin(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return pin(path)


def check_original(state, decision_ref):
    decision = checked_json(decision_ref)
    if not isinstance(decision, dict) or not isinstance(state, dict):
        raise ValueError('DECISION_AND_HEALTH_OBJECTS_REQUIRED')
    if (type(decision.get('query_cap')) is not int or decision['query_cap'] != 1
            or decision.get('automatic_retry') is not False):
        raise ValueError('ONE_NECESSARY_QUERY_WITHOUT_AUTOMATIC_RETRY_REQUIRED')
    if decision_ref['sha256'] in state.get('recovery_decisions', []):
        raise ValueError('RECOVERY_DECISION_ALREADY_USED')
    if decision.get('necessary_existing_request') in state.get('observed_request_ids', []):
        raise ValueError('ALREADY_SENT_REQUEST_CANNOT_RECOVER')
    evidence = decision.get('evidence')
    if not isinstance(evidence, list) or not evidence:
        raise ValueError('NEW_RECOVERY_EVIDENCE_REQUIRED')
    verify_embedded_pins(decision)
    for ref in evidence:
        checked(ref)
    return decision


def validate_prepared(state, prepared_ref):
    """Read-only revalidation against a fresh state, including all attachments."""
    prepared = checked_json(prepared_ref)
    normalization = prepared['evidence_normalization']
    original_ref = normalization['original_decision']
    original = check_original(state, original_ref)
    manifest_ref = normalization['manifest']
    manifest = checked_json(manifest_ref)
    if (manifest.get('status') != 'RECOVERY_EVIDENCE_BYTE_MANIFEST'
            or not same_identity(manifest.get('original_decision'), original_ref)
            or manifest.get('artifacts') != original['evidence']):
        raise ValueError('ORIGINAL_EVIDENCE_IDENTITY_CHANGED')
    expected = dict(original, evidence=[manifest_ref], evidence_normalization=normalization)
    if prepared != expected:
        raise ValueError('RECOVERY_SCOPE_CHANGED_BY_NORMALIZATION')
    verify_embedded_pins(manifest)
    authorize_recovery(state, prepared_ref)
    return {'status': 'RECOVERY_PREFLIGHT_PASS', 'decision': prepared_ref,
            'request_id': prepared['necessary_existing_request'],
            'network_authorized': False, 'query_calls': 0, 'review_credit': False,
            'health_changed': False, 'queue_changed': False,
            'fresh_coordinator_boundary_still_required': True}


def prepare(state, decision_ref, output):
    """Write only a new private directory. Preserve the old failed decision."""
    before = deepcopy(state)
    original = check_original(state, decision_ref)
    output = Path(output)
    if not output.is_absolute():
        raise ValueError('ABSOLUTE_NEW_OUTPUT_DIRECTORY_REQUIRED')
    # Validate semantic fields with JSON-only evidence before making any output.
    # The original decision itself is JSON and all of its attachments were just
    # checked as bytes. The final manifest is rechecked below by the same engine.
    if (state.get('mode') != 'PAUSED'
            or original.get('status') != 'FIXED_SINGLE_RECOVERY_DECISION'
            or original.get('account_key') != state.get('account_key')
            or not same_identity(original.get('failure_return'), state.get('pause_return', state.get('last_return')))
            or original.get('new_evidence_since_failure') is not True
            or original.get('recovery_condition_met') is not True):
        raise ValueError('NEW_RECOVERY_EVIDENCE_REQUIRED')
    output.mkdir(parents=True, exist_ok=False)
    manifest_ref = write_new(output / 'EVIDENCE.json', {
        'status': 'RECOVERY_EVIDENCE_BYTE_MANIFEST',
        'original_decision': decision_ref, 'artifacts': original['evidence'],
        'attachment_content_not_rewritten': True, 'network_authorized': False})
    prepared = dict(original, evidence=[manifest_ref], evidence_normalization={
        'original_decision': decision_ref, 'manifest': manifest_ref})
    prepared_ref = write_new(output / 'DECISION.json', prepared)
    result = validate_prepared(state, prepared_ref)
    if state != before:
        raise AssertionError('PREFLIGHT_MUST_NOT_MUTATE_HEALTH')
    write_new(output / 'PREFLIGHT.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['prepare', 'validate'])
    parser.add_argument('--state', required=True, help='fresh health snapshot JSON')
    parser.add_argument('--state-sha256', required=True)
    parser.add_argument('--decision', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', help='new private directory, required for prepare')
    args = parser.parse_args()
    state = checked_json({'path': args.state, 'sha256': args.state_sha256})
    ref = {'path': args.decision, 'sha256': args.sha256}
    if args.operation == 'prepare':
        if not args.output:
            parser.error('--output required for prepare')
        result = prepare(state, ref, args.output)
    else:
        result = validate_prepared(state, ref)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
