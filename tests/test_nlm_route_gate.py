import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import nlm_route_gate as gate


def ref(path):
    body = path.read_bytes()
    return dict(path=str(path), bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


class RouteGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        self.control = socket.socket(socket.AF_UNIX); self.addCleanup(self.control.close)
        control_path = root / 'control.sock'; self.control.bind(str(control_path))
        state = control_path.stat()
        self.listener = dict(listen='127.0.0.1', port=43210, name='inbound', proxy='approved', type='http')
        nodes = [dict(name='approved', type='socks5', server='local.invalid', port=1,
                      username='not-output', password='not-output', **{'dialer-proxy': 'transit'}),
                 dict(name='transit', type='ss', server='local.invalid', port=2, password='not-output')]
        self.config = root / 'proxy.json'
        self.config.write_text(json.dumps(dict(listeners=[self.listener], proxies=nodes,
                                             **{'external-controller-unix': str(control_path)})))
        accepted = root / 'accepted.md'; accepted.write_text('isolated test scope')
        self.ps = 'bound birth and binary -f ' + str(self.config)
        self.route = dict(schema='nlm-fixed-proxy-route-v1', evidence_mode='fixed-process-configuration',
            listener_api_mapping_unavailable_accepted=True, scope_acceptance=ref(accepted),
            proxy='http://127.0.0.1:43210', hosts=['notebook.google.com', 'notebooklm.google.com'],
            config=ref(self.config), listener=self.listener,
            process=dict(pid=42, born_epoch_ns=self.config.stat().st_mtime_ns + 1, ps=self.ps),
            control_socket=dict(path=str(control_path), st_dev=state.st_dev, st_ino=state.st_ino, st_uid=state.st_uid),
            nodes=[dict(name=n['name'], type=n['type'], private_config_sha256=hashlib.sha256(
                json.dumps(n, sort_keys=True, ensure_ascii=False).encode()).hexdigest()) for n in nodes])
        self.binding = root / 'route.json'; self.freeze()
        self.process = dict(ps=self.ps, listener_lines=['p42', 'n127.0.0.1:43210'],
                            control_lines=['p42', 'n' + str(control_path)])
        self.patches = [patch.object(gate, 'observe_process', return_value=self.process),
                        patch.object(gate, 'observe_tls_chain', return_value={'fixture': 'exact chain'}),
                        patch.object(gate, 'local_json', side_effect=self.runtime)]
        self.mocks = [p.start() for p in self.patches]
        for p in self.patches: self.addCleanup(p.stop)

    def freeze(self):
        self.binding.write_text(json.dumps(self.route)); self.cfg = dict(proxy=self.route['proxy'], route_binding=ref(self.binding))

    def runtime(self, control, path, **kwargs):
        name = gate.quote('approved', safe='')
        if path == '/proxies/' + name:
            return dict(name='approved', type='Socks5', **{'dialer-proxy': 'transit'})
        return dict(name='transit', type='Shadowsocks', **{'dialer-proxy': ''})

    def test_fixed_process_chain_passes_without_credentials_in_result(self):
        result = gate.check_route(self.cfg, 'prepare')
        self.assertNotIn('not-output', json.dumps(result))
        self.assertFalse(result['service_region_verified'])

    def test_missing_binding_wrong_port_or_changed_config_refused_before_tls(self):
        with self.assertRaisesRegex(ValueError, 'PRIVATE_BINDING_REQUIRED'):
            gate.check_route({'proxy': self.cfg['proxy']}, 'prepare')
        with self.assertRaisesRegex(ValueError, 'PROXY_MISMATCH'):
            gate.check_route({**self.cfg, 'proxy': 'http://127.0.0.1:9999'}, 'prepare')
        self.config.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'PIN_CHANGED'):
            gate.check_route(self.cfg, 'prepare')
        self.mocks[1].assert_not_called()

    def test_process_birth_or_listener_owner_change_refused_before_tls(self):
        with patch.object(gate, 'observe_process', return_value={**self.process, 'ps': 'other birth'}):
            with self.assertRaisesRegex(ValueError, 'PROCESS_RESTARTED'):
                gate.check_route(self.cfg, 'prepare')
        with patch.object(gate, 'observe_process', return_value={**self.process, 'listener_lines': ['p41']}):
            with self.assertRaisesRegex(ValueError, 'LISTENER_OWNER'):
                gate.check_route(self.cfg, 'prepare')
        self.mocks[1].assert_not_called()

    def test_runtime_selector_or_foreign_dialer_refused(self):
        for extra in ({'all': ['approved'], 'now': 'approved'}, {'dialer-proxy': 'other'}):
            with self.subTest(extra=extra), patch.object(gate, 'local_json',
                    return_value={**self.runtime('', '/proxies/approved'), **extra}):
                with self.assertRaisesRegex(ValueError, 'RUNTIME_NODE_OR_CHAIN'):
                    gate.check_route(self.cfg, 'prepare')
        self.mocks[1].assert_not_called()

    def test_unknown_live_connection_cannot_pass(self):
        with patch.object(gate, 'observe_tls_chain', side_effect=ValueError('NLM_ROUTE_LIVE_CONNECTION_NOT_UNIQUE')):
            with self.assertRaisesRegex(ValueError, 'NOT_UNIQUE'):
                gate.check_route(self.cfg, 'pre_send', host='notebook.google.com')

    def test_wrong_destination_refused_before_tls(self):
        with self.assertRaisesRegex(ValueError, 'HOST_NOT_BOUND'):
            gate.check_route(self.cfg, 'pre_send', host='foreign.invalid')
        self.mocks[1].assert_not_called()


class ExactConnectionTests(unittest.TestCase):
    def run_case(self, metadata_delta=None, chains=None):
        class FakeSocket:
            def __init__(self): self.data = bytearray(b'HTTP/1.1 200 Connection established\r\n\r\n'); self.sent = []; self.closed = False
            def getsockname(self): return ('127.0.0.1', 41001)
            def sendall(self, data): self.sent.append(data)
            def recv(self, n): result = self.data[:n]; del self.data[:n]; return bytes(result)
            def settimeout(self, value): pass
            def close(self): self.closed = True
            def do_handshake(self): pass
            def version(self): return 'TLSv1.3'
            def selected_alpn_protocol(self): return 'h2'
            def getpeercert(self, binary_form): return b'fixture'
        sock = FakeSocket()
        class Context:
            def set_alpn_protocols(self, value): pass
            def wrap_socket(self, value, **kwargs): return value
        route = dict(proxy='http://127.0.0.1:43210', control_socket={'path': '/unused'},
                     listener={'name': 'inbound'}, nodes=[{'name': 'approved'}, {'name': 'transit'}])
        metadata = dict(sourcePort='41001', host='notebook.google.com', destinationPort='443', inboundPort='43210', inboundName='inbound')
        metadata.update(metadata_delta or {})
        connections = {'connections': [dict(id='exact', metadata=metadata, chains=chains or ['approved'])]}
        with patch.object(gate.socket, 'create_connection', return_value=sock), \
                patch.object(gate.ssl, 'create_default_context', return_value=Context()), \
                patch.object(gate, 'local_json', return_value=connections):
            try:
                return gate.observe_tls_chain(route, 'notebook.google.com')
            finally:
                self.assertTrue(sock.closed)
                self.assertEqual(len(sock.sent), 1)
                self.assertTrue(sock.sent[0].startswith(b'CONNECT notebook.google.com:443 '))
                self.assertNotIn(b'Cookie', sock.sent[0])

    def test_exact_connection_accepts_terminal_and_reports_dialer_separately(self):
        result = self.run_case()
        self.assertEqual(result['connection']['chains'], ['approved'])
        self.assertEqual(result['dialers_also_present_in_actual_chain'], [])
        self.assertEqual(result['query_posts'], 0)

    def test_other_source_host_inbound_or_chain_cannot_match(self):
        for delta in ({'sourcePort': '41002'}, {'host': 'other.invalid'},
                      {'inboundPort': '43211'}, {'inboundName': 'other'}):
            with self.subTest(delta=delta), self.assertRaises(ValueError): self.run_case(delta)
        with self.assertRaisesRegex(ValueError, 'LIVE_CHAIN_MISMATCH'):
            self.run_case(chains=['foreign'])


if __name__ == '__main__': unittest.main()
