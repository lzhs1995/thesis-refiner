"""Original PairBudget with explicit adjacent 653fd8 runtime and S39 aggregate cap.

Caller must pass an already existing budget DB; original sources stay unchanged.
"""
from pathlib import Path
import hashlib
import json
import sys
import time
import types

SCRIPTS = Path(__file__).resolve().parent
PINNED_MODULES = {
    'nlm_contracts': 'd2cbeabdac0f3d91db9753fb649807e9ef3261d4d8dd782bdef2b5695a86c5ee',
    'workflow': '81a460c94b4537bad21a952989449081904083256e00b7c9e7d979aa8aedfa35',
    'nlm_runtime': '1fabeb8cda76fbb1d7571642bf993960fb7c878430aa36227c98a1332747bab7',
}

def load_current_runtime():
    for name, expected in PINNED_MODULES.items():
        path = SCRIPTS / (name + '.py')
        body = path.read_bytes()
        if hashlib.sha256(body).hexdigest() != expected:
            raise ValueError('CURRENT_RUNTIME_PIN_CHANGED:' + name)
        if name in sys.modules:
            module = sys.modules[name]
            if Path(module.__file__).resolve() != path:
                raise ValueError('OTHER_RUNTIME_ALREADY_LOADED:' + name)
        else:
            module = types.ModuleType(name)
            module.__file__ = str(path)
            sys.modules[name] = module
            try:
                exec(compile(body, str(path), 'exec', dont_inherit=True), module.__dict__)
            except BaseException:
                del sys.modules[name]
                raise
    return sys.modules['nlm_runtime']

runtime = load_current_runtime()
Budget, AdmissionError, request_key = runtime.Budget, runtime.AdmissionError, runtime.request_key
from pair_total_budget import check_total_cap, read_scope

def read(path):
    return json.loads(Path(path).read_text())

def logical_key(request):
    fields = ('account_key','notebook_id','task_id','operation','document_sha256','round_id','conversation_id','prompt')
    value = {k: request.get(k) for k in fields}
    value['sources'] = sorted(set(request.get('source_ids') or [request.get('source_id')]))
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

class PairBudget(Budget):
    def __init__(self, root):
        root = Path(root).resolve(strict=True)
        if not (root / 'budget.sqlite3').is_file():
            raise AdmissionError('EXISTING_ACCOUNT_BUDGET_REQUIRED')
        super().__init__(root)

    def admit_pair(self, account, requests, authority, now=None):
        """One atomic booking; reserve/allocations/paused accounts remain enforced."""
        now = time.time() if now is None else now
        if len(requests) != 2 or authority.get('max_in_flight') != 2:
            raise AdmissionError('EXACTLY_TWO_EXPLICIT_REQUESTS_REQUIRED')
        keys = [request_key(r) for r in requests]
        if keys != authority.get('origin_request_ids') or len(set(keys)) != 2:
            raise AdmissionError('PAIR_REQUEST_IDENTITIES_MISMATCH')
        if now >= authority['expires_epoch'] or now < authority['issued_epoch']:
            raise AdmissionError('PAIR_AUTHORIZATION_EXPIRED_OR_FUTURE')
        if len({r.get('notebook_id') for r in requests}) != 2:
            raise AdmissionError('PILOT_REQUIRES_DIFFERENT_NOTEBOOKS')
        for request in requests:
            if (request.get('operation') != 'query' or request.get('account_key') != account
                or request.get('conversation_id') or request.get('recovery_probe')
                or not request.get('prompt','').strip() or not request.get('document_sha256')
                or not request.get('round_id') or not (request.get('source_ids') or request.get('source_id'))
                or request.get('phase') not in ('draft','final','recovery') or not request.get('task_id')):
                raise AdmissionError('PINNED_NEW_CONVERSATION_QUERY_REQUIRED')
        scope_ref = authority['total_query_scope']
        scope = read_scope(scope_ref['path'], scope_ref['sha256'])
        self.db.execute('BEGIN IMMEDIATE')
        try:
            check_total_cap(self.db, account, requests, scope)
            if self.db.execute("SELECT 1 FROM requests WHERE account=? AND state IN ('STARTED','UNCERTAIN')", (account,)).fetchone():
                raise AdmissionError('ACCOUNT_REQUEST_IN_FLIGHT')
            row = self.db.execute('SELECT * FROM accounts WHERE id=?', (account,)).fetchone()
            if not row:
                raise AdmissionError('ACCOUNT_POLICY_NOT_CONFIGURED')
            if row['paused']:
                raise AdmissionError('PAUSED_ACCOUNT_REQUIRES_SERIAL_RECOVERY')
            policy = json.loads(row['policy'])
            if policy['regime'] not in ('legacy_daily_count','compute_weekly','unknown'):
                raise AdmissionError('QUOTA_REGIME_REQUIRED')
            for key, request in zip(keys, requests):
                if self.db.execute('SELECT 1 FROM requests WHERE id=?', (key,)).fetchone():
                    raise AdmissionError('ORIGIN_REQUEST_ALREADY_BOOKED_NO_REPLAY')
                priors = self.db.execute("SELECT id FROM requests WHERE account=? AND task_id=? AND operation='query'", (account,request['task_id'])).fetchall()
                for prior in priors:
                    if prior['id'] in keys:
                        prior_request=requests[keys.index(prior['id'])]
                        if logical_key(prior_request)==logical_key(request):
                            raise AdmissionError('LOGICAL_REQUEST_ALREADY_BOOKED_NO_REPLAY')
                        continue
                    prior_path = self.root / 'receipts' / prior['id'] / 'request.json'
                    if not prior_path.is_file():
                        raise AdmissionError('PRIOR_REQUEST_IDENTITY_UNAVAILABLE: '+prior['id'])
                    if logical_key(read(prior_path)) == logical_key(request):
                        raise AdmissionError('LOGICAL_REQUEST_ALREADY_BOOKED_NO_REPLAY')
                task_count = len(priors)
                allocation = self.db.execute('SELECT query_budget FROM allocations WHERE account=? AND task_id=?',(account,request['task_id'])).fetchone()
                limit = allocation[0] if allocation else policy.get('task_query_budget')
                if type(limit) is not int:
                    raise AdmissionError('TASK_PLANNING_BUDGET_REQUIRED')
                if task_count >= limit:
                    raise AdmissionError('TASK_PLANNING_BUDGET_EXHAUSTED')
                units = 1 if policy['regime']=='legacy_daily_count' else None
                if units is not None and policy.get('limit') is not None:
                    if policy.get('window_ends_at') is None or now >= policy['window_ends_at']:
                        raise AdmissionError('QUOTA_WINDOW_REQUIRES_FRESH_OBSERVATION')
                    used = self.db.execute('SELECT coalesce(sum(units),0) FROM requests WHERE account=? AND started>=?',(account,policy['observed_at'])).fetchone()[0]
                    remaining=policy['limit']-policy.get('observed_used',0)-used
                    reserve=0 if request['phase'] in ('final','recovery') else policy['limit']*policy.get('reserve_fraction',.2)
                    if remaining-units < reserve:
                        raise AdmissionError('FINAL_REVIEW_RESERVE_PROTECTED')
                self.db.execute("INSERT INTO requests(id,account,task_id,operation,started,state,units,phase) VALUES(?,?,?,'query',?,'STARTED',?,?)",(key,account,request['task_id'],now,units,request['phase']))
            self.db.execute('COMMIT')
            return keys
        except BaseException:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            raise
