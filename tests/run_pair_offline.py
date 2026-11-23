#!/usr/bin/env python3
"""Run only portable synthetic pair tests with network operations denied."""
import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.abc
import io
import json
import os
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
TESTS = ('test_nlm_pair_budget_locks', 'test_nlm_pair_fresh',
         'test_nlm_pair_http', 'test_nlm_pair_total_budget')
FORBIDDEN = {'nlm_network_guard', 'hook_doctor',
             'test_nlm_network_guard', 'test_hook_doctor'}
BLOCKED = []


class RejectHooks(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in FORBIDDEN:
            raise ImportError('HOOK_MODULE_OUTSIDE_PAIR_TEST_SCOPE:' + fullname)
        return None


def audit(event, args):
    if event.startswith('socket.') and event not in ('socket.__new__', 'socket.gethostname'):
        BLOCKED.append(event)
        raise AssertionError('PAIR_OFFLINE_NETWORK_FORBIDDEN:' + event)
    if event in {'os.system', 'os.posix_spawn', 'os.posix_spawnp', 'os.exec'}:
        BLOCKED.append(event)
        raise AssertionError('PAIR_OFFLINE_EXTERNAL_EXEC_FORBIDDEN:' + event)
    if event == 'subprocess.Popen':
        argv = args[1]
        module = sys.modules.get('test_nlm_pair_budget_locks')
        permitted = (module is not None and isinstance(argv, (list, tuple))
            and len(argv) == 5 and argv[0] == sys.executable and argv[1] == '-BE'
            and Path(argv[2]).name == 'child.py'
            and Path(argv[2]).read_text() == module.CHILD
            and Path(argv[3]).resolve() == ROOT / 'scripts'
            and Path(argv[4]).parent == Path(argv[2]).parent
            and Path(argv[4]).name.startswith('manifest-'))
        if not permitted:
            BLOCKED.append(event)
            raise AssertionError('ONLY_SYNTHETIC_LOCK_CHILD_ALLOWED')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, help='Create-only JSON result, outside the source tree in CI.')
    args = parser.parse_args()
    if sys.version_info < (3, 11) or os.name != 'posix':
        raise SystemExit('Pair offline acceptance requires Python 3.11+ and POSIX.')
    if not sys.dont_write_bytecode or not sys.flags.ignore_environment:
        raise SystemExit('Use python -BE tests/run_pair_offline.py')
    if args.report is not None and args.report.exists():
        raise SystemExit('REPORT_ALREADY_EXISTS_NO_OVERWRITE')
    os.environ.pop('COLLABORATION_BROKER', None)
    sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
    sys.meta_path.insert(0, RejectHooks())
    sys.addaudithook(audit)
    started = time.monotonic()
    output = io.StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        suite = unittest.defaultTestLoader.loadTestsFromNames(TESTS)
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    passed = result.wasSuccessful() and not result.skipped and not BLOCKED
    report = dict(status='PASS_PAIR_OFFLINE' if passed else 'FAIL_PAIR_OFFLINE',
        tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        skipped=[test.id() for test, _ in result.skipped],
        blocked_events=BLOCKED, elapsed_seconds=time.monotonic() - started,
        interpreter=sys.version, platform=sys.platform,
        test_sha256={name: hashlib.sha256((ROOT / 'tests' / (name + '.py')).read_bytes()).hexdigest()
                     for name in TESTS},
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        output=output.getvalue(),
        scope='Synthetic temporary SQLite, RPC bodies and HTTPX transports; real inherited POSIX locks; no NLM calls.')
    if args.report is not None:
        with args.report.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    print(output.getvalue(), end='')
    print(json.dumps({key: value for key, value in report.items() if key != 'output'}, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
