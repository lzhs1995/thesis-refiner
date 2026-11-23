"""One installation-owned policy for the pair parent and its pinned children.

This is a local validation step. Each actual network operation must separately
pass the original live US2 route check; this module grants no network authority.
"""
import hashlib
import json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROUTE_POLICY_AUTHORITY = SCRIPTS.parent.parent / 'NLM-ROUTE-POLICY-PIN.json'
PARENT_NAME = 'nlm_sdk_pair_parent.py'
CALLERS = frozenset((PARENT_NAME, 'nlm_sdk_pair_child.py', 'nlm_pair_setup.py'))
ROUTE_LABEL = '链式代理-Gemini → kookeey-US2（US-2-gemini）'


def require(value, reason):
    if not value:
        raise ValueError('PAIR_POLICY_' + reason)


def ref(path):
    path = Path(path)
    require(path.is_absolute() and not path.is_symlink() and path.is_file(),
            'REGULAR_ABSOLUTE_FILE_REQUIRED')
    actual = path.resolve(strict=True)
    require(actual == path, 'CANONICAL_FILE_REQUIRED')
    body = actual.read_bytes()
    return dict(path=str(actual), bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


def read_checked(reference):
    path = Path(reference['path'])
    body = path.read_bytes()
    require(ref(path) == reference and len(body) == reference['bytes']
            and hashlib.sha256(body).hexdigest() == reference['sha256'], 'PIN_CHANGED')
    return json.loads(body)


def enforce_pair_route_policy(cfg, *, caller_path):
    """Validate the same pinned parent policy from three explicit entrypoints."""
    caller = Path(caller_path)
    require(caller.parent == SCRIPTS and caller.name in CALLERS, 'CALLER_NOT_IN_PAIR')
    caller_ref = ref(caller)
    require(Path(cfg['scripts']).resolve(strict=True) == SCRIPTS, 'SOURCE_ROOT_CHANGED')
    # Authority is chosen by this immutable installation, never from task args.
    ref(ROUTE_POLICY_AUTHORITY)
    authority = json.loads(ROUTE_POLICY_AUTHORITY.read_bytes())
    require(authority.get('schema') == 'nlm-network-policy-authority-v1', 'AUTHORITY_SCHEMA')
    require(cfg.get('route_policy') == authority.get('policy'), 'REGISTERED_POLICY_REQUIRED')
    policy = read_checked(authority['policy'])
    require(policy.get('schema') == 'nlm-network-policy-v1'
            and policy.get('policy_role') == 'mandatory-domain-route'
            and policy.get('required_route_label') == ROUTE_LABEL, 'MANDATORY_US2_POLICY')
    require(policy.get('entry') == ref(SCRIPTS / PARENT_NAME), 'EXACT_PARENT_ENTRY_REQUIRED')
    require(policy.get('python') == cfg.get('python')
            and policy.get('route_binding') == cfg.get('route_binding'), 'TASK_ROUTE_NOT_APPROVED')
    require(ref(cfg['python']['path']) == cfg['python'], 'PYTHON_PIN_CHANGED')
    expected = [ref(path) for path in sorted(SCRIPTS.glob('*.py'))]
    require(policy.get('code_pins') == expected and cfg.get('code_pins') == expected,
            'COMPLETE_APPROVED_CODE_REQUIRED')
    require(caller_ref in expected and ref(Path(__file__).resolve()) in expected,
            'CALLER_AND_VALIDATOR_MUST_BE_PINNED')
    route = read_checked(cfg['route_binding'])
    require(cfg.get('proxy') == route.get('proxy'), 'PROXY_CHANGED')
    return policy
