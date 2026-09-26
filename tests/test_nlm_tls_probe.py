"""No external traffic. The optional real TLS tests use a loopback CONNECT server."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from nlm_tls_probe import (OriginHTTPForbidden, classify_attempts, error_chain,
                           finish_origin_observation, load_httpx, new_row,
                           probe_async, probe_sync, trace_event, validate_config)


def config():
    return {'host': 'localhost', 'proxy': 'http://127.0.0.1:12345', 'verify': True,
            'trust_env': False, 'timeout_seconds': 2,
            'cases': [{'name': 'bound', 'mode': 'async', 'http2': True, 'alpn': ['h2', 'http/1.1']}]}


class TLSProbeTests(unittest.TestCase):
    def test_configuration_preserves_explicit_verified_route(self):
        value = config()
        self.assertEqual(validate_config(value), value)
        for changes in ({'verify': False}, {'trust_env': True}, {'timeout_seconds': 60},
                        {'host': 'https://localhost/'}, {'proxy': 'http://user:pw@localhost:12345'},
                        {'proxy': 'https://localhost:12345'}, {'cases': value['cases'] * 5}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_config(dict(value, **changes))

    def test_second_proxy_headers_and_direct_origin_are_blocked_before_send(self):
        row = new_row(config()['cases'][0])
        trace_event(row, 'http11.send_request_headers.started', {}, via_proxy=True)
        with self.assertRaises(OriginHTTPForbidden):
            trace_event(row, 'http11.send_request_headers.started', {}, via_proxy=True)
        with self.assertRaises(OriginHTTPForbidden):
            trace_event(new_row(config()['cases'][0]), 'http11.send_request_headers.started', {}, via_proxy=False)

    def test_unexpected_response_cannot_be_reported_as_zero_origin_http(self):
        row = new_row(config()['cases'][0])
        row.update(tls_stream_closed=True, unexpected_origin_response=True)
        finish_origin_observation(row)
        self.assertIsNone(row['origin_http_requests'])
        self.assertFalse(row['no_origin_http_proven'])

    def test_exception_chain_preserves_ssl_failure_details(self):
        cause = ssl.SSLCertVerificationError('fixture certificate failure')
        wrapper = OSError('connection failed')
        wrapper.__cause__ = cause
        rows = error_chain(wrapper)
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[1]['type'].endswith('SSLCertVerificationError'))

    def attempt(self):
        return {'attempt': 1, 'TLS_complete': False, 'origin_headers_started': False,
                'connection_closed': True, 'events': [
                    'connection.connect_tcp.started', 'connection.connect_tcp.complete',
                    'http11.send_request_headers.started', 'http11.send_request_headers.complete',
                    'http11.send_request_body.started', 'http11.send_request_body.complete',
                    'http11.receive_response_headers.started', 'http11.receive_response_headers.complete',
                    'proxy.start_tls.started', 'proxy.start_tls.failed']}

    def test_connect_200_is_not_an_origin_response(self):
        result = classify_attempts({'attempts': [self.attempt()]})
        self.assertEqual(result['status'], 'PROXY_TLS_FAILED_BEFORE_ORIGIN')
        self.assertFalse(result['account_authentication_failure_proven'])
        self.assertFalse(result['reconciliation_authorized'])

    def test_missing_trace_contradiction_or_partial_send_cannot_prove_zero_send(self):
        for change in ({'TLS_complete': True}, {'origin_headers_started': True},
                       {'connection_closed': False}, {'events': []}):
            with self.subTest(change=change):
                result = classify_attempts({'attempts': [dict(self.attempt(), **change)]})
                self.assertEqual(result['origin_http_submission'], 'NOT_PROVEN')
        self.assertEqual(classify_attempts({'attempts': []})['origin_http_submission'], 'NOT_PROVEN')

    def test_missing_dependency_fails_without_network(self):
        from importlib import metadata
        with patch('nlm_tls_probe.metadata.version', side_effect=metadata.PackageNotFoundError('httpx')):
            with self.assertRaisesRegex(RuntimeError, 'EXISTING_EXECUTOR'):
                load_httpx()


class LoopbackTLSProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.httpx, _ = load_httpx()
            import h2  # noqa: F401
        except (RuntimeError, ImportError) as exc:
            raise unittest.SkipTest('Use the existing executor dependencies for loopback TLS tests: ' + str(exc))
        binary = shutil.which('openssl')
        if binary is None:
            raise unittest.SkipTest('openssl needed only for disposable loopback certificates')
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.cert = cls.root / 'cert.pem'
        cls.key = cls.root / 'key.pem'
        subprocess.run([binary, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-keyout', str(cls.key), '-out', str(cls.cert), '-subj', '/CN=localhost',
                        '-addext', 'subjectAltName=DNS:localhost'], check=True, timeout=15,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def probe(self, mode, alpn, *, trusted=True):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(5)
        self.addCleanup(listener.close)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(self.cert), str(self.key))
        context.set_alpn_protocols(['h2', 'http/1.1'])
        observed = {'connect': b'', 'origin_bytes': b''}
        def serve():
            try:
                with listener.accept()[0] as connection:
                    connection.settimeout(5)
                    while not observed['connect'].endswith(b'\r\n\r\n'):
                        data = connection.recv(1)
                        if not data:
                            return
                        observed['connect'] += data
                    connection.sendall(b'HTTP/1.1 200 Connection established\r\n\r\n')
                    with context.wrap_socket(connection, server_side=True) as secured:
                        observed['origin_bytes'] = secured.recv(4096)
            except Exception as exc:
                observed['exception'] = type(exc).__name__
        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        value = config()
        value['proxy'] = 'http://127.0.0.1:' + str(listener.getsockname()[1])
        if trusted:
            value['ca_file'] = str(self.cert)
        case = dict(value['cases'][0], mode=mode, alpn=alpn)
        row = new_row(case)
        if mode == 'async':
            asyncio.run(probe_async(self.httpx, value, case, row))
        else:
            probe_sync(self.httpx, value, case, row)
        thread.join(6)
        self.assertFalse(thread.is_alive(), observed)
        self.assertTrue(observed['connect'].startswith(b'CONNECT localhost:443 HTTP/1.1\r\n'))
        self.assertEqual(observed['origin_bytes'], b'')
        self.assertEqual(row['origin_http_requests'], 0)
        self.assertTrue(row['transport_closed'])
        return row

    def test_sync_default_closes_before_origin_http(self):
        self.assertEqual(self.probe('sync', None)['status'], 'TLS_COMPLETE_CLOSED_BEFORE_ORIGIN_HTTP')

    def test_sync_h2_first_closes_before_origin_http(self):
        self.assertEqual(self.probe('sync', ['h2', 'http/1.1'])['status'], 'TLS_COMPLETE_CLOSED_BEFORE_ORIGIN_HTTP')

    def test_async_default_closes_before_origin_http(self):
        self.assertEqual(self.probe('async', None)['status'], 'TLS_COMPLETE_CLOSED_BEFORE_ORIGIN_HTTP')

    def test_async_h2_first_closes_before_origin_http(self):
        self.assertEqual(self.probe('async', ['h2', 'http/1.1'])['status'], 'TLS_COMPLETE_CLOSED_BEFORE_ORIGIN_HTTP')

    def test_invalid_certificate_remains_a_failure(self):
        row = self.probe('async', ['h2', 'http/1.1'], trusted=False)
        self.assertEqual(row['status'], 'CONNECTION_FAILURE')
        self.assertFalse(row['tls_completed'])


if __name__ == '__main__':
    unittest.main()
