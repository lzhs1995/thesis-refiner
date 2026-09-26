#!/usr/bin/env python3
"""Bounded TLS-only diagnostics on the existing route, without origin HTTP.

Use the existing executor's interpreter/dependencies and its resource boundary.
No credentials are loaded; no query, upload, auth refresh or retry is performed.
The httpx/httpcore trace contract is version-scoped because the stop must happen
before any origin HTTP. This optional diagnostic never grants task admission.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
import re
import ssl
import sys
import time
from urllib.parse import urlsplit

from nlm_query_health_store import checked_json, verify_embedded_pins
from nlm_recovery_preflight import pin, write_new


class TLSCompleteWithoutOriginHTTP(Exception):
    pass


class OriginHTTPForbidden(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def error_chain(exc):
    result, seen = [], set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        result.append({'type': type(exc).__module__ + '.' + type(exc).__name__,
                       'repr': repr(exc), 'errno': getattr(exc, 'errno', None),
                       'ssl_library': getattr(exc, 'library', None),
                       'ssl_reason': getattr(exc, 'reason', None)})
        exc = exc.__cause__ if exc.__cause__ is not None else exc.__context__
    return result


def validate_config(value):
    if not isinstance(value, dict):
        raise ValueError('EXPLICIT_BOUND_ROUTE_REQUIRED')
    host = value.get('host', '')
    if (not isinstance(host, str) or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', host)
            or '..' in host):
        raise ValueError('HOSTNAME_WITHOUT_URL_OR_CREDENTIALS_REQUIRED')
    port = value.get('port', 443)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('VALID_TLS_PORT_REQUIRED')
    proxy = value.get('proxy')
    if proxy is not None:
        if not isinstance(proxy, str) or any(c.isspace() for c in proxy):
            raise ValueError('HTTP_CONNECT_PROXY_REQUIRED')
        parsed = urlsplit(proxy)
        if (parsed.scheme != 'http' or not parsed.hostname or parsed.port is None
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
            raise ValueError('EXISTING_HTTP_CONNECT_PROXY_WITHOUT_CREDENTIALS_REQUIRED')
    if value.get('verify', True) is not True or value.get('trust_env', False) is not False:
        raise ValueError('VERIFIED_TLS_WITH_EXPLICIT_ROUTE_REQUIRED')
    timeout = value.get('timeout_seconds', 15)
    if type(timeout) not in (int, float) or not 0 < timeout <= 15:
        raise ValueError('BOUNDED_TIMEOUT_REQUIRED')
    cases = value.get('cases')
    if not isinstance(cases, list) or not 1 <= len(cases) <= 4:
        raise ValueError('ONE_TO_FOUR_EXPLICIT_CASES_REQUIRED')
    names = set()
    for case in cases:
        if (not isinstance(case, dict) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', case.get('name', ''))
                or case['name'] in names or case.get('mode') not in ('sync', 'async')
                or type(case.get('http2')) is not bool
                or case.get('alpn') not in (None, ['h2', 'http/1.1'], ['http/1.1', 'h2'], ['http/1.1'])
                or (not case['http2'] and case.get('alpn') not in (None, ['http/1.1']))):
            raise ValueError('EXPLICIT_NONREPEATED_TLS_CASE_REQUIRED')
        names.add(case['name'])
    ca = value.get('ca_file')
    if ca is not None and (not Path(ca).is_absolute() or not Path(ca).is_file()):
        raise ValueError('EXISTING_BOUND_CA_FILE_REQUIRED')
    verify_embedded_pins(value)
    return value


def load_httpx():
    try:
        versions = {n: metadata.version(n) for n in ('httpx', 'httpcore', 'certifi')}
    except metadata.PackageNotFoundError as exc:
        raise RuntimeError('USE_EXISTING_EXECUTOR_PYTHON_AND_PYTHONPATH') from exc
    if versions['httpx'] != '0.28.1' or versions['httpcore'] != '1.0.9':
        raise RuntimeError('OPTIONAL_DIAGNOSTIC_TRACE_VERSION_NOT_VALIDATED')
    import httpx
    return httpx, versions


def new_row(case):
    return {'case': case, 'started': now(), 'events': [], 'alpn_calls': [],
            'tls_completed': False, 'connect_header_groups': 0,
            'origin_http_requests': None, 'attempts': 1, 'automatic_retries': 0}


def trace_event(row, name, info, *, via_proxy):
    entry = {'event': name, 'at': now()}
    if 'exception' in info:
        entry['exception_chain'] = error_chain(info['exception'])
    row['events'].append(entry)
    if name.endswith('send_request_headers.started'):
        # Exactly one plaintext CONNECT is allowed before destination TLS.
        if row['tls_completed'] or not via_proxy or row['connect_header_groups']:
            row['origin_http_guard_tripped'] = True
            raise OriginHTTPForbidden('ORIGIN_HTTP_BLOCKED_BEFORE_SEND')
        row['connect_header_groups'] += 1
    expected = 'proxy.start_tls.complete' if via_proxy else 'connection.start_tls.complete'
    if name == expected:
        stream = info['return_value']
        row['tls_completed'] = True
        ssl_object = stream.get_extra_info('ssl_object')
        if ssl_object is not None:
            row['selected_alpn'] = ssl_object.selected_alpn_protocol()
            row['tls_version'] = ssl_object.version()
            row['peer_certificate_sha256'] = hashlib.sha256(ssl_object.getpeercert(True)).hexdigest()
        return stream
    return None


def finish_origin_observation(row):
    events = [event['event'] for event in row['events']]
    failed_before_tls = (not row['tls_completed'] and bool(events)
                        and any(event in ('connection.connect_tcp.failed', 'proxy.start_tls.failed',
                                          'connection.start_tls.failed') for event in events))
    proven = (row.get('tls_stream_closed') is True or row.get('origin_http_guard_tripped') is True
              or failed_before_tls) and not row.get('unexpected_origin_response')
    row['origin_http_requests'] = 0 if proven else None
    row['no_origin_http_proven'] = proven


def context_for(httpx, config, case, row):
    context = httpx.create_ssl_context(verify=True, trust_env=False)
    if config.get('ca_file'):
        context = ssl.create_default_context(cafile=config['ca_file'])
        row['ca_file'] = pin(config['ca_file'])
    original = context.set_alpn_protocols
    def set_alpn(offered):
        actual = case.get('alpn') or list(offered)
        row['alpn_calls'].append({'library_offered': list(offered), 'actual': actual})
        original(actual)
    context.set_alpn_protocols = set_alpn
    row.update(certificate_store=context.cert_store_stats(), verify_mode=int(context.verify_mode),
               check_hostname=context.check_hostname)
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise ValueError('TLS_VERIFICATION_REQUIRED')
    return context


def request_for(httpx, config, trace):
    # Construction only: both transports stop inside start_tls.complete. No
    # authentication headers, cookie jar, SDK, or application request are used.
    seconds = config.get('timeout_seconds', 15)
    return httpx.Request('GET', 'https://' + config['host'] + ':' + str(config.get('port', 443)) + '/',
        extensions={'trace': trace, 'timeout': dict.fromkeys(('connect', 'read', 'write', 'pool'), seconds)})


def probe_sync(httpx, config, case, row):
    def trace(name, info):
        stream = trace_event(row, name, info, via_proxy=config.get('proxy') is not None)
        if stream is not None:
            stream.close()
            row['tls_stream_closed'] = True
            raise TLSCompleteWithoutOriginHTTP()
    transport = httpx.HTTPTransport(proxy=config.get('proxy'), verify=context_for(httpx, config, case, row),
                                    http2=case['http2'], trust_env=False, retries=0)
    try:
        transport.handle_request(request_for(httpx, config, trace))
        row['unexpected_origin_response'] = True
        raise RuntimeError('UNEXPECTED_ORIGIN_RESPONSE')
    except TLSCompleteWithoutOriginHTTP:
        row['status'] = 'TLS_COMPLETE_CLOSED_BEFORE_ORIGIN_HTTP'
    except Exception as exc:
        row['status'] = 'GUARD_BLOCKED_ORIGIN_HTTP' if isinstance(exc, OriginHTTPForbidden) else 'CONNECTION_FAILURE'
        row['exception_chain'] = error_chain(exc)
    finally:
        transport.close()
        row['transport_closed'] = True
        finish_origin_observation(row)


async def probe_async(httpx, config, case, row):
    async def trace(name, info):
        stream = trace_event(row, name, info, via_proxy=config.get('proxy') is not None)
        if stream is not None:
            await stream.aclose()
            row['tls_stream_closed'] = True
            raise TLSCompleteWithoutOriginHTTP()
    transport = httpx.AsyncHTTPTransport(proxy=config.get('proxy'), verify=context_for(httpx, config, case, row),
                                         http2=case['http2'], trust_env=False, retries=0)
    try:
        await transport.handle_async_request(request_for(httpx, config, trace))
        row['unexpected_origin_response'] = True
        raise RuntimeError('UNEXPECTED_ORIGIN_RESPONSE')
    except TLSCompleteWithoutOriginHTTP:
        row['status'] = 'TLS_COMPLETE_CLOSED_BEFORE_ORIGIN_HTTP'
    except Exception as exc:
        row['status'] = 'GUARD_BLOCKED_ORIGIN_HTTP' if isinstance(exc, OriginHTTPForbidden) else 'CONNECTION_FAILURE'
        row['exception_chain'] = error_chain(exc)
    finally:
        await transport.aclose()
        row['transport_closed'] = True
        finish_origin_observation(row)


def classify_attempts(value):
    """Classify the supported original CONNECT trace; never reconcile state."""
    attempts = value.get('attempts', [])
    findings = []
    for attempt in attempts:
        events = [x if isinstance(x, str) else x.get('event') for x in attempt.get('events', [])]
        expected = ['connection.connect_tcp.started', 'connection.connect_tcp.complete',
                    'http11.send_request_headers.started', 'http11.send_request_headers.complete',
                    'http11.send_request_body.started', 'http11.send_request_body.complete',
                    'http11.receive_response_headers.started', 'http11.receive_response_headers.complete',
                    'proxy.start_tls.started', 'proxy.start_tls.failed']
        proven = (events == expected and attempt.get('TLS_complete') is False
                  and attempt.get('origin_headers_started') is False
                  and attempt.get('connection_closed') is True)
        findings.append({'attempt': attempt.get('attempt'), 'proxy_tls_failed_before_origin': proven})
    proven = bool(findings) and all(x['proxy_tls_failed_before_origin'] for x in findings)
    return {'status': 'PROXY_TLS_FAILED_BEFORE_ORIGIN' if proven else 'TRACE_INSUFFICIENT_OR_DIFFERENT',
            'attempts': findings, 'physical_root_cause': 'UNKNOWN',
            'origin_http_submission': 'NOT_STARTED_IN_THIS_TRACE' if proven else 'NOT_PROVEN',
            'account_authentication_failure_proven': False, 'network_authorized': False,
            'reconciliation_authorized': False, 'query_calls': 0, 'review_credit': False}


def run_probe(config, output):
    validate_config(config)
    httpx, versions = load_httpx()
    if any(case['http2'] for case in config['cases']):
        try:
            import h2  # noqa: F401 - validate before any connection
        except ImportError as exc:
            raise RuntimeError('USE_EXISTING_EXECUTOR_HTTP2_DEPENDENCIES') from exc
    output = Path(output)
    if not output.is_absolute():
        raise ValueError('ABSOLUTE_NEW_OUTPUT_DIRECTORY_REQUIRED')
    output.mkdir(parents=True, exist_ok=False)
    intent = write_new(output / 'INTENT.json', {'at': now(), 'config': config,
        'implementation': pin(__file__), 'packages': versions, 'python': sys.version,
        'openssl': ssl.OPENSSL_VERSION, 'credentials_loaded': False,
        'origin_http_permitted': False, 'query_calls': 0, 'automatic_retries': 0})
    rows = []
    for case in config['cases']:
        row = new_row(case)
        start = time.monotonic()
        if case['mode'] == 'async':
            asyncio.run(probe_async(httpx, config, case, row))
        else:
            probe_sync(httpx, config, case, row)
        row.update(ended=now(), elapsed_seconds=round(time.monotonic() - start, 3))
        write_new(output / (case['name'] + '.json'), row)
        rows.append(row)
        print(json.dumps({'case': case['name'], 'status': row['status']}, ensure_ascii=False), flush=True)
    passed = all(row['status'] == 'TLS_COMPLETE_CLOSED_BEFORE_ORIGIN_HTTP' for row in rows)
    result = {'at': now(), 'status': 'TLS_ONLY_PASS' if passed else 'TLS_ONLY_NOT_ALL_PASS',
              'intent': intent, 'results': rows, 'query_calls': 0, 'source_calls': 0,
              'origin_http_requests': 0 if all(row['no_origin_http_proven'] for row in rows) else None,
              'credentials_loaded': False,
              'root_cause': 'NOT_INFERRED_FROM_COMPARISON', 'query_recovery_proven': False,
              'network_authorized': False, 'review_credit': False}
    write_new(output / 'RESULT.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['probe', 'classify'])
    parser.add_argument('--input', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', required=True, help='new directory for probe; new JSON file for classify')
    args = parser.parse_args()
    value = checked_json({'path': args.input, 'sha256': args.sha256})
    if args.operation == 'classify':
        result = classify_attempts(value)
        write_new(args.output, result)
    else:
        result = run_probe(value, args.output)
    print(json.dumps({'status': result['status'], 'output': args.output,
                      'query_calls': 0, 'review_credit': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
