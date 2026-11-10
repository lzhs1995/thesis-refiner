"""Read-only gate for a task-owned fixed local HTTP proxy listener.

This checks a pinned process/configuration and runtime proxy chain. It does not
probe Google, change selectors, claim a public egress country, or prove that a
control API independently exposes listener-to-node mappings.
"""
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import ssl
import stat
import subprocess
import time
from urllib.parse import quote, urlparse


class RouteGateError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise RouteGateError('NLM_ROUTE_' + reason)


def pinned(value):
    path = Path(value['path']).resolve(strict=True)
    body = path.read_bytes()
    require(len(body) == value['bytes'] and hashlib.sha256(body).hexdigest() == value['sha256'],
            'PIN_CHANGED')
    return path, body


def observe_process(pid, port, control_socket):
    def command(argv):
        result = subprocess.run(argv, capture_output=True, text=True, timeout=3, check=False)
        require(result.returncode == 0 and len(result.stdout) < 16384, 'PROCESS_OBSERVATION_FAILED')
        return result.stdout.strip()
    ps = command(['/bin/ps', '-p', str(pid), '-o', 'lstart=', '-o', 'command='])
    listener = command(['/usr/sbin/lsof', '-nP', '-a', '-p', str(pid),
                        '-iTCP:' + str(port), '-sTCP:LISTEN', '-Fpn'])
    control = command(['/usr/sbin/lsof', '-nP', '-a', '-p', str(pid), '-U', '-Fn'])
    return {'ps': ps, 'listener_lines': listener.splitlines(), 'control_lines': control.splitlines()}


def local_json(control_socket, endpoint, timeout=3):
    class LocalHTTP(http.client.HTTPConnection):
        def connect(self):
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.settimeout(timeout)
            self.sock.connect(control_socket)
    connection = LocalHTTP('localhost', timeout=timeout)
    try:
        connection.request('GET', endpoint)
        response = connection.getresponse()
        body = response.read(65537)
        require(response.status == 200 and len(body) <= 65536, 'CONTROL_RESPONSE_REQUIRED')
        value = json.loads(body)
        require(isinstance(value, dict), 'CONTROL_OBJECT_REQUIRED')
        return value
    finally:
        connection.close()


def observe_tls_chain(route, host, total=15):
    """One credential-free CONNECT/TLS; inspect its exact live local connection."""
    started = time.monotonic()
    deadline = started + total
    parsed = urlparse(route['proxy'])
    plain = tls = None
    observation = dict(host=host, proxy_port=parsed.port, connect_attempts=1,
                       origin_http_requests=0, credentials_read=0, query_posts=0)
    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise TimeoutError('NLM_ROUTE_TLS_DEADLINE')
        return seconds
    try:
        plain = socket.create_connection(('127.0.0.1', parsed.port), timeout=remaining())
        observation['client_source_port'] = plain.getsockname()[1]
        plain.sendall(('CONNECT ' + host + ':443 HTTP/1.1\r\nHost: ' + host
                       + ':443\r\n\r\n').encode('ascii'))
        header = bytearray()
        while not header.endswith(b'\r\n\r\n'):
            plain.settimeout(remaining())
            part = plain.recv(1)
            require(bool(part) and len(header) < 16384, 'CONNECT_HEADER_REQUIRED')
            header.extend(part)
        require(bytes(header).split(b'\r\n', 1)[0].split()[1:2] == [b'200'], 'CONNECT_REJECTED')
        observation['connect_status'] = 200
        context = ssl.create_default_context()
        context.set_alpn_protocols(['h2', 'http/1.1'])
        tls = context.wrap_socket(plain, server_hostname=host, do_handshake_on_connect=False)
        plain = None
        tls.settimeout(remaining())
        tls.do_handshake()
        observation.update(tls_version=tls.version(), alpn=tls.selected_alpn_protocol(),
                           peer_certificate_sha256=hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest())
        connections = local_json(route['control_socket']['path'], '/connections',
                                 timeout=min(3, remaining())).get('connections') or []
        remaining()
        matches = []
        for connection in connections:
            metadata = connection.get('metadata') or {}
            if (str(metadata.get('sourcePort')) == str(observation['client_source_port'])
                    and metadata.get('host') == host
                    and str(metadata.get('destinationPort')) == '443'
                    and str(metadata.get('inboundPort')) == str(parsed.port)):
                matches.append(connection)
        observation['exact_match_count'] = len(matches)
        require(len(matches) == 1, 'LIVE_CONNECTION_NOT_UNIQUE')
        current = matches[0]
        metadata = current['metadata']
        observation['connection'] = dict(id=current.get('id'),
            metadata={k: metadata.get(k) for k in ('host', 'sourceIP', 'sourcePort', 'destinationPort',
                                                  'inboundIP', 'inboundPort', 'inboundName')},
            chains=current.get('chains'), rule=current.get('rule'), rulePayload=current.get('rulePayload'))
        chain = current.get('chains')
        names = [node['name'] for node in route['nodes']]
        require(metadata.get('inboundName') == route['listener']['name'], 'LIVE_INBOUND_NAME_MISMATCH')
        require(isinstance(chain, list) and names[0] in chain and len(chain) == len(set(chain))
                and set(chain) <= set(names), 'LIVE_CHAIN_MISMATCH')
        observation['terminal_node_in_actual_chain'] = names[0]
        observation['fixed_dialers_from_runtime_proxy_checks'] = names[1:]
        observation['dialers_also_present_in_actual_chain'] = [name for name in names[1:] if name in chain]
        observation['status'] = 'TLS_AND_EXACT_RUNTIME_CHAIN_VERIFIED'
        return observation
    except BaseException as exc:
        observation['status'] = 'UNKNOWN_ROUTE_OBSERVATION_FAILED'
        observation['error_type'] = type(exc).__name__
        exc.route_observation = observation
        raise
    finally:
        if tls:
            tls.close()
        if plain:
            plain.close()
        observation['closed_at'] = datetime.now(timezone.utc).isoformat()
        observation['elapsed_seconds'] = time.monotonic() - started


def check_route(cfg, phase, *, host=None):
    """Fail closed before prepare/admission/send; at most one fixed local chain."""
    require('route_binding' in cfg, 'PRIVATE_BINDING_REQUIRED')
    _, body = pinned(cfg['route_binding'])
    route = json.loads(body)
    require(route['schema'] == 'nlm-fixed-proxy-route-v1', 'SCHEMA')
    require(route['evidence_mode'] == 'fixed-process-configuration', 'EVIDENCE_MODE')
    require(route.get('listener_api_mapping_unavailable_accepted') is True,
            'LISTENER_EVIDENCE_BOUNDARY_NOT_ACCEPTED')
    # The task must explicitly bind this narrower evidence boundary. No default
    # fallback is made when the local core lacks an independent listener API.
    pinned(route['scope_acceptance'])
    require(cfg['proxy'] == route['proxy'], 'PROXY_MISMATCH')
    parsed = urlparse(cfg['proxy'])
    require(parsed.scheme == 'http' and parsed.hostname == '127.0.0.1'
            and parsed.username is None and parsed.password is None
            and parsed.path == '' and not parsed.query and not parsed.fragment, 'LOOPBACK_HTTP_ONLY')
    require(set(route['hosts']) == {'notebook.google.com', 'notebooklm.google.com'}, 'BOUND_HOSTS_REQUIRED')
    if host is not None:
        require(host in route['hosts'], 'HOST_NOT_BOUND')
    config_path, config_body = pinned(route['config'])
    config = json.loads(config_body)
    expected = route['listener']
    require(expected['listen'] == '127.0.0.1' and expected['port'] == parsed.port
            and expected['type'] == 'http', 'LISTENER_SCOPE')
    found = [x for x in config.get('listeners', []) if x.get('port') == parsed.port]
    require(len(found) == 1 and found[0] == expected, 'LISTENER_CONFIG_MISMATCH')
    control_socket = route['control_socket']['path']
    require(config.get('external-controller-unix') == control_socket, 'CONTROL_SOCKET_MISMATCH')
    sock = os.stat(control_socket)
    require(stat.S_ISSOCK(sock.st_mode) and all(getattr(sock, key) == route['control_socket'][key]
            for key in ('st_dev', 'st_ino', 'st_uid')), 'CONTROL_SOCKET_REPLACED')
    process = route['process']
    require(type(process['pid']) is int and process['pid'] > 0, 'PID_REQUIRED')
    require(config_path.stat().st_mtime_ns <= process['born_epoch_ns'], 'CONFIG_NEWER_THAN_PROCESS')
    require((' -f ' + str(config_path)) in process['ps'], 'PROCESS_CONFIG_ARGUMENT_REQUIRED')
    before = observe_process(process['pid'], parsed.port, control_socket)
    require(before['ps'] == process['ps'], 'PROCESS_RESTARTED_OR_CHANGED')
    require('p' + str(process['pid']) in before['listener_lines']
            and 'n127.0.0.1:' + str(parsed.port) in before['listener_lines'], 'LISTENER_OWNER_MISMATCH')
    require('p' + str(process['pid']) in before['control_lines']
            and 'n' + control_socket in before['control_lines'], 'CONTROL_OWNER_MISMATCH')
    nodes = route['nodes']
    require(isinstance(nodes, list) and 1 <= len(nodes) <= 3
            and expected['proxy'] == nodes[0]['name'], 'FIXED_CHAIN_REQUIRED')
    proxies = {x['name']: x for x in config.get('proxies', [])}
    runtime_nodes = []
    for index, node in enumerate(nodes):
        actual = proxies.get(node['name'])
        require(actual is not None and actual['type'].lower() == node['type'].lower(), 'NODE_CONFIG_MISMATCH')
        require(hashlib.sha256(json.dumps(actual, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                == node['private_config_sha256'], 'NODE_PRIVATE_CONFIG_CHANGED')
        next_name = nodes[index + 1]['name'] if index + 1 < len(nodes) else ''
        require(actual.get('dialer-proxy', '') == next_name, 'FIXED_DIALER_CHAIN_REQUIRED')
        current = local_json(control_socket, '/proxies/' + quote(node['name'], safe=''))
        runtime_type = {'ss': 'shadowsocks'}.get(node['type'].lower(), node['type'].lower())
        require(current.get('name') == node['name'] and current.get('type', '').lower() == runtime_type
                and current.get('dialer-proxy', '') == next_name and not current.get('all')
                and current.get('now') is None, 'RUNTIME_NODE_OR_CHAIN_MISMATCH')
        runtime_nodes.append({key: current.get(key) for key in ('name', 'type', 'dialer-proxy')})
    live = observe_tls_chain(route, host or 'notebook.google.com')
    # Re-read identity/config to reject a replacement during local observation.
    pinned(route['config'])
    require(observe_process(process['pid'], parsed.port, control_socket) == before,
            'PROCESS_CHANGED_DURING_CHECK')
    after_socket = os.stat(control_socket)
    require(all(getattr(after_socket, key) == route['control_socket'][key]
                for key in ('st_dev', 'st_ino', 'st_uid')), 'CONTROL_SOCKET_REPLACED')
    return dict(phase=phase, at=datetime.now(timezone.utc).isoformat(),
        binding_sha256=cfg['route_binding']['sha256'], config_sha256=route['config']['sha256'],
        pid=process['pid'], listener=expected, runtime_nodes=runtime_nodes,
        live_connection=live,
        evidence_mode=route['evidence_mode'], independent_listener_api_mapping=False,
        origin_requests=0, route_mutations=0, service_region_verified=False)
