#!/usr/bin/env python3
"""PreToolUse guard: only an administrator-pinned NLM entry may use the network.

The hook does no network I/O. The admitted entry repeats its live route gate
before preparation, admission and send. This is a tool boundary, not an OS
firewall or a proof about arbitrary opaque programs already running elsewhere.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import sys

MAX_BYTES = 2 * 1024 * 1024
NLM = re.compile(r'notebook[._-]?lm|notebook(?:lm)?\.google\.com|gemini.notebook|'
                 r'(?<![a-z0-9])nlm(?:[^a-z0-9]|$)', re.I)
EXECUTION = re.compile(r'bash|shell|exec|run_command|terminal|python|javascript|browser|navigate', re.I)
READ_TOOLS = {'read', 'read_file', 'read_text_file', 'view_image', 'glob', 'grep', 'search',
              'apply_patch', 'write', 'edit', 'write_file', 'edit_file', 'multi_edit', 'multiedit', 'tool_search'}


class Denied(ValueError):
    pass


def _scope_unknown(exc):
    """A bounded parser's uncertainty is not evidence of an NLM operation."""
    reason = str(exc)
    return (reason.endswith('_UNRESOLVED') or reason.endswith('_LOCAL_DEADLINE')
            or reason.endswith('_LOCAL_EXECUTABLE_TOO_LARGE'))


def _scope_probe(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except Denied as exc:
        if _scope_unknown(exc):
            return False
        raise


def require(ok, reason):
    if not ok:
        raise Denied('NLM_NETWORK_GUARD_' + reason)


def file_ref(path):
    path = Path(path).resolve(strict=True)
    require(path.is_file() and path.stat().st_size <= MAX_BYTES, 'BOUNDED_REGULAR_FILE_REQUIRED')
    body = path.read_bytes()
    return dict(path=str(path), bytes=len(body), sha256=hashlib.sha256(body).hexdigest()), body


def pinned(value):
    actual, body = file_ref(value['path'])
    require(actual == value, 'PIN_CHANGED')
    return body


def load_policy(path, sha256):
    ref, body = file_ref(path)
    require(ref['sha256'] == sha256, 'REGISTERED_POLICY_CHANGED')
    policy = json.loads(body)
    require(policy['schema'] == 'nlm-network-policy-v1'
            and policy['policy_role'] == 'mandatory-domain-route'
            and bool(policy['required_route_label']), 'POLICY_SCHEMA')
    # Labels explain the machine rule; the exact route object supplies authority.
    pinned(policy['route_binding'])
    for item in [policy['entry'], policy['python'], *policy['code_pins']]:
        pinned(item)
    scripts = Path(policy['entry']['path']).parent
    require({v['path'] for v in policy['code_pins']}
            == {str(p.resolve()) for p in scripts.glob('*.py')}, 'COMPLETE_ENTRY_CODE_PINS_REQUIRED')
    return ref, policy


def strip_wrappers(argv):
    argv = list(argv)
    depth = 0
    while len(argv) >= 2 and Path(argv[0]).name == 'rtk' and argv[1] == 'proxy':
        depth += 1
        require(depth <= 8, 'RTK_WRAPPER_NESTING_UNRESOLVED')
        argv = argv[2:]
    # Environment overrides can replace a policy, import root, proxy or actor.
    # Do not guess which ones a caller intended to be harmless.
    return argv


def read_only(argv):
    if not argv:
        return True
    cmd = Path(argv[0]).name
    if cmd in {'cat', 'head', 'tail', 'wc', 'ls', 'stat', 'shasum', 'sha256sum'}:
        return not any('$' in v or '`' in v for v in argv)
    if cmd == 'rg':
        return not any(v.startswith(('--pre', '--hostname-bin')) for v in argv)
    if cmd == 'sed':
        # Only the common, non-executing line-range read used for code review.
        return len(argv) >= 4 and argv[1] == '-n' and bool(re.fullmatch(r'\d+(?:,\d+)?p', argv[2]))
    if cmd == 'git':
        # Disable external diff/textconv and do not accept -c/alias indirection.
        return (len(argv) >= 2 and argv[1] in {'status', 'log', 'rev-parse'}
                and not any(v.startswith(('--exec-path', '--config-env', '--ext-diff')) for v in argv))
    return False


SDK_MODULES = {'notebooklm', 'notebook_lm', 'notebooklm_sdk', 'nlm'}
HTTP_ROOTS = {'requests', 'httpx', 'http', 'urllib', 'aiohttp', 'socket', 'websockets'}
SCRIPT_SUFFIXES = {'.py', '.sh', '.js', '.mjs', '.cjs', '.ts'}
CLI_NAMES = {'nlm', 'notebooklm', 'notebook-lm'}
DESTINATION = re.compile(r'notebook(?:lm)?\.google\.com|gemini\.notebook', re.I)


class PolicyLoader:
    """Bind classification hints separately from network authorization.

    Entry paths are installation-owned hook arguments, never an allowlist.
    Keeping them outside policy contents ensures a missing or altered policy
    cannot make an opaque registered entry disappear from classification.
    Unrelated local work does not need to open the policy at all.
    """
    def __init__(self, kind, path, sha256, entry_paths=()):
        require(kind in {'policy', 'registry'}, 'AUTHORITY_KIND_REQUIRED')
        self.kind, self.path, self.sha256 = kind, path, sha256
        require(all(isinstance(v, str) and Path(v).is_absolute() for v in entry_paths),
                'ABSOLUTE_ENTRY_SCOPE_REQUIRED')
        self.scope_entry_paths = frozenset(str(Path(v).resolve()) for v in entry_paths)

    def __call__(self):
        method = load_policy if self.kind == 'policy' else load_registry
        return method(self.path, self.sha256)


def _name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _name(node.value) + '.' + node.attr
    if isinstance(node, ast.Call):
        return _name(node.func) + '()'
    return ''


def _literal(node, values):
    """Safe literals and Path expressions only; no evaluation of source."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return values.get(node.id)
    if isinstance(node, (ast.List, ast.Tuple)):
        items = [_literal(v, values) for v in node.elts]
        return items if all(v is not None for v in items) else None
    if isinstance(node, ast.BinOp):
        left, right = _literal(node.left, values), _literal(node.right, values)
        if isinstance(node.op, ast.Add) and type(left) is type(right) and type(left) in (str, list):
            return left + right
        if isinstance(node.op, ast.Div) and isinstance(left, (str, Path)) and isinstance(right, str):
            return Path(left) / right
    if isinstance(node, ast.JoinedStr):
        parts = []
        for part in node.values:
            value = _literal(part.value, values) if isinstance(part, ast.FormattedValue) else _literal(part, values)
            if value is None:
                return None
            parts.append(str(value))
        return ''.join(parts)
    if isinstance(node, ast.Subscript):
        value, index = _literal(node.value, values), _literal(node.slice, values)
        if isinstance(value, (list, tuple)) and isinstance(index, int):
            try:
                return value[index]
            except IndexError:
                return None
    if isinstance(node, ast.Attribute):
        if _name(node) in values:
            return values[_name(node)]
        value = _literal(node.value, values)
        if isinstance(value, Path) and node.attr == 'parent':
            return value.parent
    if isinstance(node, ast.Call):
        name = _name(node.func)
        if name in {'Path', 'pathlib.Path', 'str'} and len(node.args) == 1:
            value = _literal(node.args[0], values)
            if isinstance(value, (str, Path)):
                return str(value) if name == 'str' else Path(value)
        if isinstance(node.func, ast.Attribute) and node.func.attr in {'resolve', 'absolute'}:
            value = _literal(node.func.value, values)
            if isinstance(value, Path):
                return value.resolve()
    return None


def _source_mentions(path, cwd, depth, seen, arguments=(), source_kind=None):
    path = Path(path)
    if not path.is_absolute():
        path = Path(cwd) / path
    if path.is_dir():
        # Explicit test discovery follows a bounded tree; arbitrary repo paths
        # are not recursively scanned during ordinary file operations.
        files = (list(path.glob('**/test*.py')) + list(path.glob('**/conftest.py'))
                 + list(path.glob('**/__init__.py')))
        files = list(dict.fromkeys(files))
        require(len(files) <= 128, 'TEST_DISCOVERY_UNRESOLVED')
        return any(_source_mentions(p, cwd, depth + 1, seen, arguments) for p in files)
    if not path.is_file():
        return False
    path = path.resolve()
    identity = (path, tuple(map(str, arguments)), source_kind)
    if identity in seen:
        return False
    require(depth <= 8, 'LOCAL_SOURCE_CHAIN_UNRESOLVED')
    # Classify a bounded header before imposing a source-text size limit.
    # Large manuscript data and native executables are not Python/shell source.
    with path.open('rb') as stream:
        header = stream.read(4096)
    native_magic = {b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe',
                    b'\xfe\xed\xfa\xcf', b'\xcf\xfa\xed\xfe',
                    b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca',
                    b'\xca\xfe\xba\xbf', b'\xbf\xba\xfe\xca', b'\x7fELF'}
    if source_kind is None and header[:4] in native_magic:
        return False  # Not source-inspected; this is not a no-network proof.
    first_line = header.split(b'\n', 1)[0].decode('utf-8', errors='replace')
    suffix = path.suffix.lower()
    shebang = first_line[2:] if first_line.startswith('#!') else ''
    kind = source_kind or ('python' if suffix == '.py' or re.search(r'\bpython[\d.]*\b', shebang)
            else 'shell' if suffix in {'.sh', '.bash', '.zsh'} or re.search(r'\b(?:sh|bash|zsh)\b', shebang)
            else 'javascript' if suffix in {'.js', '.mjs', '.cjs', '.ts'} or re.search(r'\b(?:node|deno|bun)\b', shebang)
            else None)
    if kind is None:
        return False  # Data or an opaque program is outside source classification.
    require(path.stat().st_size <= MAX_BYTES, 'LOCAL_EXECUTABLE_TOO_LARGE')
    seen.add(identity)
    text = path.read_text(errors='replace')
    if kind == 'python':
        return _python_mentions(text, path, depth, seen, arguments)
    if kind == 'shell':
        try:
            shell_command(text, lambda: (_ for _ in ()).throw(Denied('NLM_NETWORK_GUARD_WRAPPER_NETWORK')), path.parent, depth, seen)
        except Denied as exc:
            return not _scope_unknown(exc)
        return False
    if kind == 'javascript':
        return _javascript_mentions(text, path.parent, depth, seen)
    return False


def _python_mentions(text, path, depth=0, seen=None, arguments=()):
    seen = set() if seen is None else seen
    require(depth <= 8, 'LOCAL_PYTHON_CHAIN_UNRESOLVED')
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return bool(NLM.search(text))
    values = {'__file__': str(path), 'sys.argv': [str(path), *arguments]}
    aliases = {}
    http_variables = set()
    compiled_sources = {}

    def compiled_source(node):
        # Compilation makes a code object; inspect its source only when an
        # exec/eval consumer actually uses it. Never execute inspected code.
        if isinstance(node, ast.Name):
            return compiled_sources.get(node.id)
        if isinstance(node, ast.Call):
            name = _name(node.func)
            root = name.split('.')[0]
            resolved = aliases.get(root, root) + name[len(root):]
            if resolved in {'compile', 'builtins.compile'} and node.args:
                value = _literal(node.args[0], values)
                return value if isinstance(value, str) else None
        return None
    for _ in range(3):
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = _literal(node.value, values)
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                call_name = _name(node.value.func) if isinstance(node.value, ast.Call) else ''
                call_root = aliases.get(call_name.split('.')[0], call_name.split('.')[0])
                assigned_name = _name(node.value)
                assigned_root = assigned_name.split('.')[0]
                for target in targets:
                    if isinstance(target, ast.Name):
                        if value is not None:
                            values[target.id] = value
                        compiled = compiled_source(node.value)
                        if compiled is not None:
                            compiled_sources[target.id] = compiled
                        if call_root.split('.')[0] in HTTP_ROOTS:
                            http_variables.add(target.id)
                        if isinstance(node.value, (ast.Name, ast.Attribute)) and assigned_root in aliases:
                            aliases[target.id] = aliases[assigned_root] + assigned_name[len(assigned_root):]
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or '']
                for module in modules:
                    if module.split('.')[0].lower() in SDK_MODULES:
                        return True
                for alias in node.names:
                    target = alias.name if isinstance(node, ast.Import) else (node.module or '') + '.' + alias.name
                    aliases[alias.asname or alias.name.split('.')[0]] = target
                for module in modules:
                    local = Path(path).parent / (module.replace('.', '/') + '.py')
                    if _source_mentions(local, Path(path).parent, depth + 1, seen):
                        return True
                    package = Path(path).parent / module.replace('.', '/') / '__init__.py'
                    if _source_mentions(package, Path(path).parent, depth + 1, seen):
                        return True
                if isinstance(node, ast.ImportFrom) and node.level:
                    relative_root = Path(path).parent
                    for _level in range(node.level - 1):
                        relative_root = relative_root.parent
                    for alias in node.names:
                        local = relative_root / ((node.module or alias.name).replace('.', '/') + '.py')
                        if _source_mentions(local, Path(path).parent, depth + 1, seen):
                            return True
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _name(node.func)
        root = name.split('.')[0]
        resolved = aliases.get(root, root) + name[len(root):]
        args = [_literal(v, values) for v in node.args]
        kwargs = {v.arg: _literal(v.value, values) for v in node.keywords if v.arg}
        if resolved in {'importlib.import_module', '__import__'}:
            if args and isinstance(args[0], str) and args[0].split('.')[0].lower() in SDK_MODULES:
                return True
        is_http = resolved.split('.')[0] in HTTP_ROOTS or root in http_variables
        sink = resolved.rsplit('.', 1)[-1]
        if is_http and sink in {'get', 'post', 'put', 'patch', 'delete', 'head', 'options',
                                'request', 'send', 'connect', 'urlopen', 'urlretrieve',
                                'HTTPConnection', 'HTTPSConnection', 'create_connection',
                                'Request', 'Client', 'AsyncClient', 'Session', 'ClientSession'}:
            # NLM evidence must be in an endpoint slot, not headers/json/body
            # or an untracked value. This is not a general network allowlist.
            index = 1 if sink in {'request', 'Request'} and not resolved.startswith('urllib.') else 0
            destinations = [args[index]] if len(args) > index else []
            destinations += [kwargs[k] for k in ('url', 'uri', 'host', 'hostname', 'address', 'base_url') if k in kwargs]
            if any(DESTINATION.search(str(v)) for v in destinations if v is not None):
                return True
        if resolved.startswith(('subprocess.', 'os.exec', 'os.spawn')) or resolved in {'os.system', 'os.popen'}:
            if args:
                command = args[0]
                if isinstance(command, list) and executable_mentions([str(v) for v in command], Path(path).parent, depth + 1, seen):
                    return True
                if isinstance(command, str):
                    try:
                        shell_command(command, lambda: (_ for _ in ()).throw(Denied('NLM_NETWORK_GUARD_WRAPPER_NETWORK')), Path(path).parent, depth + 1, seen)
                    except Denied as exc:
                        if not _scope_unknown(exc):
                            return True
                if command is None and any(NLM.search(_name(v)) for v in node.args):
                    return True
        if resolved in {'runpy.run_path', 'runpy.run_module'} or name.endswith('spec_from_file_location'):
            value = args[1] if name.endswith('spec_from_file_location') and len(args) > 1 else (args[0] if args else None)
            if isinstance(value, (str, Path)):
                if resolved == 'runpy.run_module' and str(value).split('.')[0] in SDK_MODULES:
                    return True
                if _source_mentions(value, Path(path).parent, depth + 1, seen):
                    return True
        if name in {'source', 'load_module', 'load_source', 'load'}:
            for value in args:
                if isinstance(value, (str, Path)) and Path(value).suffix in SCRIPT_SUFFIXES:
                    if _source_mentions(value, Path(path).parent, depth + 1, seen):
                        return True
        if resolved in {'exec', 'eval', 'builtins.exec', 'builtins.eval'} and node.args:
            source = args[0] if isinstance(args[0], str) else compiled_source(node.args[0])
            if isinstance(source, str) and _python_mentions(source, path, depth + 1, seen, arguments):
                return True
    return False


def executable_mentions(argv, cwd, depth=0, seen=None):
    """Inspect executable positions and active source, never filenames/data alone."""
    seen = set() if seen is None else seen
    argv = strip_wrappers(argv)
    if not argv:
        return False
    require(depth <= 8, 'LOCAL_EXECUTABLE_CHAIN_UNRESOLVED')
    cmd = Path(argv[0]).name
    if cmd in CLI_NAMES:
        return True
    if cmd in {'uvx', 'pipx', 'npx', 'bunx'}:
        # These arguments select a package/executable, unlike message text
        # passed to arbitrary native commands.
        return any(v in CLI_NAMES or re.fullmatch(r'notebooklm[-_][A-Za-z0-9_.-]+', v)
                   for v in argv[1:])
    if cmd in {'env', 'sudo', 'command', 'nohup', 'timeout'}:
        rest = argv[1:]
        while rest and (rest[0].startswith('-') or '=' in rest[0] or rest[0].isdigit()):
            rest = rest[1:]
        return executable_mentions(rest, cwd, depth + 1, seen)
    if cmd in {'sh', 'bash', 'zsh'} and len(argv) >= 3 and argv[1] in {'-c', '-lc'}:
        try:
            shell_command(argv[2], lambda: (_ for _ in ()).throw(Denied('NLM_NETWORK_GUARD_WRAPPER_NETWORK')), cwd, depth + 1, seen)
        except Denied as exc:
            return not _scope_unknown(exc)
        return False
    if re.fullmatch(r'python(?:\d+(?:\.\d+)*)?', cmd, re.I):
        rest = argv[1:]
        for index, token in enumerate(rest):
            if token == '-c' and index + 1 < len(rest):
                return _python_mentions(rest[index + 1], Path(cwd) / '<inline>.py', depth, seen, rest[index + 2:])
            if token == '-m' and index + 1 < len(rest):
                module = rest[index + 1]
                if module.split('.')[0] in SDK_MODULES:
                    return True
                if module in {'pytest', 'unittest'}:
                    targets = [v for v in rest[index + 2:] if not v.startswith('-') and v != 'discover']
                    if not targets:
                        targets = [cwd]
                    return any(_source_mentions(v, cwd, depth + 1, seen) for v in targets)
                return _source_mentions(module.replace('.', '/') + '.py', cwd, depth + 1, seen)
            if not token.startswith('-'):
                return _source_mentions(token, cwd, depth + 1, seen, rest[index + 1:], source_kind='python')
        return False
    if cmd in {'pytest', 'py.test'}:
        targets = [v.split('::')[0] for v in argv[1:] if not v.startswith('-')] or [cwd]
        return any(_source_mentions(v, cwd, depth + 1, seen) for v in targets)
    if cmd in {'curl', 'wget', 'http', 'https', 'xh'}:
        return any(DESTINATION.search(v) or '$' in v or chr(96) in v for v in argv[1:])
    if cmd in {'node', 'deno', 'bun'} and len(argv) > 2 and argv[1] in {'-e', '--eval'}:
        return _javascript_mentions(argv[2], cwd, depth, seen)
    if cmd in {'node', 'deno', 'bun'} and len(argv) > 1:
        return _source_mentions(argv[1], cwd, depth + 1, seen, argv[2:])
    executable = argv[0]
    if '/' not in executable:
        executable = shutil.which(executable) or executable
    return _source_mentions(executable, cwd, depth + 1, seen, argv[1:])


def _js_tokens(code):
    """Lex comments and strings without evaluating JavaScript."""
    pattern = re.compile(r'''//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\x60(?:\\.|[^\x60\\])*\x60|[A-Za-z_$][\w$]*|[^\s]''')
    out = []
    for match in pattern.finditer(code):
        token = match.group()
        if token.startswith(('//', '/*')):
            continue
        if token[0] in "\"'" + chr(96):
            try:
                value = json.loads(token) if token[0] == '"' else ast.literal_eval(token) if token[0] == "'" else token[1:-1]
            except (SyntaxError, ValueError):
                value = None
            out.append(('string', value, token))
        else:
            out.append(('id' if re.fullmatch(r'[A-Za-z_$][\w$]*', token) else 'punct', token, token))
    return out


def _javascript_mentions(code, cwd, depth=0, seen=None, policy_loader=None):
    require(depth <= 8, 'LOCAL_JS_CHAIN_UNRESOLVED')
    tokens = _js_tokens(code)
    # Normalize literal member access; computed unknown names remain unresolved.
    normalized, i = [], 0
    while i < len(tokens):
        if (i > 0 and (tokens[i-1][0] == 'id' or tokens[i-1][1] in {')', ']'})
                and i + 2 < len(tokens) and tokens[i][1] == '['
                and tokens[i+1][0] == 'string' and tokens[i+2][1] == ']'):
            normalized += [('punct', '.', '.'), ('id', tokens[i+1][1], tokens[i+1][2])]
            i += 3
        else:
            normalized.append(tokens[i]); i += 1
    tokens = normalized
    values, aliases, network_objects = {}, {}, set()
    def split(items, delimiter=','):
        groups, current, nesting = [], [], 0
        for t in items:
            if t[1] in {'(', '[', '{'}:
                nesting += 1
            elif t[1] in {')', ']', '}'}:
                nesting -= 1
            if t[1] == delimiter and nesting == 0:
                groups.append(current); current = []
            else:
                current.append(t)
        groups.append(current)
        return groups
    def val(items):
        if not items:
            return None
        if len(items) == 1:
            token = items[0]
            value = token[1] if token[0] == 'string' else values.get(token[1])
            if isinstance(value, str) and '$' + '{' in value:
                unknown = False
                def replace(match):
                    nonlocal unknown
                    found = values.get(match.group(1))
                    if not isinstance(found, str):
                        unknown = True
                        return ''
                    return found
                value = re.sub(r'\$\{([A-Za-z_$][\w$]*)\}', replace, value)
                return None if unknown or '$' + '{' in value else value
            return value
        additions = split(items, '+')
        if len(additions) > 1:
            parts = [val(p) for p in additions]
            return ''.join(parts) if all(isinstance(p, str) for p in parts) else None
        if items[0][1] == '{' and items[-1][1] == '}':
            result = {}
            for prop in split(items[1:-1]):
                if len(prop) >= 3 and prop[1][1] == ':':
                    result[prop[0][1]] = val(prop[2:])
                elif len(prop) == 1:
                    result[prop[0][1]] = values.get(prop[0][1])
            return result
        if len(items) >= 4 and items[-1][1] == ')':
            start = 1 if items[0][1] == 'new' else 0
            if (len(items) > start + 2 and items[start][1] in {'URL', 'Request'}
                    and items[start+1][1] == '('):
                first = split(items[start+2:-1])[0]
                return {'url': val(first)}
        if items[0][1] == '[' and items[-1][1] == ']':
            parts = [val(p) for p in split(items[1:-1])]
            return parts if all(p is not None for p in parts) else None
        return None
    def chain(items):
        return ''.join(str(t[1]) for t in items) if all(t[0] == 'id' or t[1] == '.' for t in items) else ''
    statements = split(tokens, ';')
    for _ in range(3):
        for st in statements:
            if len(st) > 3 and st[0][1] in {'const', 'let', 'var'} and st[1][0] == 'id' and st[2][1] == '=':
                expr = st[3:]
                got = val(expr)
                if got is not None:
                    values[st[1][1]] = got
                target = chain(expr)
                if target:
                    aliases[st[1][1]] = aliases.get(target, target)
                if len(expr) >= 4 and expr[0][1] == 'require' and expr[1][1] == '(':
                    imported = val(expr[2:-1])
                    if imported in {'http', 'https', 'node:http', 'node:https', 'axios', 'undici'}:
                        network_objects.add(st[1][1])
            # Static import targets are executable imports, not fixture strings.
            if st and st[0][1] == 'import':
                imported = next((t[1] for t in reversed(st) if t[0] == 'string'), None)
                if isinstance(imported, str):
                    if imported.split('/')[0].lower() in SDK_MODULES:
                        return True
                    if imported.startswith(('.', '/')) and _source_mentions(imported, cwd, depth + 1, seen or set()):
                        return True
                    if imported in {'http', 'https', 'node:http', 'node:https', 'axios', 'undici'}:
                        network_objects.update(t[1] for t in st[1:] if t[0] == 'id' and t[1] not in {'from', 'as'})
    for i, token in enumerate(tokens):
        if token[0] != 'id' or i + 1 >= len(tokens) or tokens[i+1][1] != '(':
            continue
        begin = i
        while begin >= 2 and tokens[begin-1][1] == '.' and tokens[begin-2][0] == 'id':
            begin -= 2
        full = chain(tokens[begin:i+1])
        root = full.split('.')[0]
        full = aliases.get(root, root) + full[len(root):]
        name = full.rsplit('.', 1)[-1]
        end, balance = i + 2, 1
        while end < len(tokens) and balance:
            balance += tokens[end][1] == '('
            balance -= tokens[end][1] == ')'
            end += 1
        groups = split(tokens[i+2:end-1])
        arguments = [val(g) for g in groups]
        if full.startswith('tools.') and NLM.search(name):
            return True
        if name in {'require', 'import'}:
            target = arguments[0] if arguments else None
            if isinstance(target, str) and target.split('/')[0].lower() in SDK_MODULES:
                return True
            if isinstance(target, str) and target.startswith(('.', '/')) and _source_mentions(target, cwd, depth + 1, seen or set()):
                return True
        if name in {'eval', 'Function'}:
            target = arguments[0] if arguments else None
            if isinstance(target, str) and _javascript_mentions(target, cwd, depth + 1, seen):
                return True
        network = (full in {'fetch', 'globalThis.fetch'} or full.split('.')[0] in network_objects
                   or full.startswith(('https.', 'http.', 'axios.', 'undici.')))
        if network and name in {'fetch', 'get', 'post', 'request', 'put', 'patch', 'delete', 'connect', 'create'}:
            target = arguments[0] if arguments else None
            destinations = ([target.get(k) for k in ('url', 'uri', 'host', 'hostname', 'origin', 'baseURL', 'base_url')]
                            if isinstance(target, dict) else [target])
            if any(DESTINATION.search(str(a)) for a in destinations if a is not None):
                return True
        if name not in {'exec_command', 'run_command', 'execute_command', 'execSync', 'exec', 'spawn', 'spawnSync'}:
            continue
        command, command_cwd = None, cwd
        if groups and groups[0] and groups[0][0][1] == '{' and groups[0][-1][1] == '}':
            for prop in split(groups[0][1:-1]):
                key = prop[0][1] if prop else None
                if len(prop) >= 3 and prop[1][1] == ':':
                    got = val(prop[2:])
                elif len(prop) == 1:
                    got = values.get(key)
                else:
                    got = None
                if key in {'cmd', 'command'}:
                    command = got
                elif key in {'cwd', 'workdir'} and isinstance(got, str):
                    command_cwd = got
        elif arguments:
            command = arguments[0]
            if name in {'spawn', 'spawnSync'}:
                argv = arguments[1] if len(arguments) > 1 else []
                if isinstance(command, str) and isinstance(argv, list):
                    command = shlex.join([command, *map(str, argv)])
                else:
                    command = None
        # An actual shell execution sink with unresolved command cannot prove
        # it is outside NLM. Plain strings and local function names never enter.
        if not isinstance(command, str):
            return True
        if policy_loader is not None:
            shell_command(command, policy_loader, command_cwd, depth + 1, seen)
        else:
            try:
                shell_command(command, lambda: (_ for _ in ()).throw(Denied('NLM_NETWORK_GUARD_WRAPPER_NETWORK')), command_cwd, depth + 1, seen)
            except Denied as exc:
                if not _scope_unknown(exc):
                    return True
    return False



def approved_entry(argv, policy_ref, policy, cwd):
    require(len(argv) >= 7, 'EXACT_ENTRY_COMMAND_REQUIRED')
    require(str(Path(argv[0]).resolve()) == policy['python']['path'] and argv[1] == '-BE'
            and str(Path(argv[2]).resolve()) == policy['entry']['path'], 'PINNED_ENTRY_REQUIRED')
    mode = argv[3]
    allowed = policy.get('_registered_modes', ['prepare', 'run'])
    require(mode in allowed and mode in {'prepare', 'run', 'legacy-run'}, 'DIRECT_TRANSPORT_OR_UNKNOWN_MODE_FORBIDDEN')
    flags = {'--config', '--output-dir'} if mode == 'prepare' else {'--config', '--request'}
    require(len(argv) == 8 and set(argv[4::2]) == flags and len(set(argv[4::2])) == 2,
            'EXACT_ENTRY_ARGUMENTS_REQUIRED')
    args = dict(zip(argv[4::2], argv[5::2]))
    require(all(Path(v).is_absolute() and '$' not in v and '`' not in v for v in args.values()),
            'LITERAL_ABSOLUTE_ARGUMENTS_REQUIRED')
    _, body = file_ref(args['--config'])
    cfg = json.loads(body)
    require(cfg.get('route_policy') == policy_ref, 'TASK_NOT_BOUND_TO_REGISTERED_POLICY')
    require(cfg.get('route_binding') == policy['route_binding'] and cfg.get('python') == policy['python'],
            'TASK_ROUTE_OR_PYTHON_NOT_APPROVED')
    route = json.loads(pinned(policy['route_binding']))
    require(cfg.get('proxy') == route['proxy'], 'TASK_PROXY_NOT_APPROVED')
    if mode in {'run', 'legacy-run'}:
        require(cfg.get('code_pins') == policy['code_pins']
                and cfg.get('scripts') == str(Path(policy['entry']['path']).parent), 'PREPARED_ENTRY_CHANGED')
    if mode == 'legacy-run':
        require(cfg.get('schema') == 'nlm-legacy-task-v1'
                and cfg.get('legacy_contract') in policy.get('legacy_contracts', []), 'REGISTERED_LEGACY_CONTRACT_REQUIRED')
        pinned(cfg['legacy_contract'])
    # The entry checks actor/account/source/queue, and obtains fresh live route
    # evidence. The hook must not spend query budget or use historic TLS as PASS.


def _data_heredocs(command):
    """Remove quoted stdin data for literal data consumers, retaining commands.

    Unquoted documents and interpreter consumers are still inspected. This is
    bounded shell syntax handling, not execution of shell functions or branches.
    """
    lines = command.splitlines(keepends=True)
    index = 0
    while index < len(lines):
        match = re.fullmatch(r"(\s*(?:cat|tee)\b[^\n<>;|&]*?)<<(-?)\s*(['\"])([A-Za-z_][A-Za-z0-9_]*)\3[ \t]*\n?", lines[index])
        if not match:
            index += 1; continue
        end = index + 1
        while end < len(lines):
            marker = lines[end].rstrip('\r\n')
            if match.group(2):
                marker = marker.lstrip('\t')
            if marker == match.group(4):
                break
            end += 1
        if end == len(lines):
            index += 1; continue
        lines[index] = match.group(1) + '\n'
        for row in range(index + 1, end + 1):
            lines[row] = '\n'
        index = end + 1
    return ''.join(lines)


def _shell_comments(command):
    """Remove comments without losing their newline or touching quoted data."""
    result, quote, index = [], None, 0
    while index < len(command):
        char = command[index]
        if char == '\\' and quote != "'" and index + 1 < len(command):
            result.extend(command[index:index + 2]); index += 2; continue
        if char == '#' and quote is None and (index == 0 or command[index - 1] in ' \t\r\n;|&()'):
            end = command.find('\n', index)
            if end < 0:
                break
            index = end; continue
        if char == "'" and quote != '"':
            quote = None if quote == "'" else "'"
        elif char == '"' and quote != "'":
            quote = None if quote == '"' else '"'
        result.append(char); index += 1
    return ''.join(result)


def _check_shell_expansions(command, policy_loader, cwd, depth, seen):
    # Inspect actual shell expansions before shlex removes their quote context.
    # Single-quoted fixture data is deliberately excluded.
    quote, index = None, 0
    while index < len(command):
        char = command[index]
        if char == '#' and quote is None and (index == 0 or command[index - 1] in ' \t\r\n;|&()'):
            end = command.find('\n', index)
            if end < 0:
                break
            index = end + 1; continue
        if char == '\\' and quote != "'":
            index += 2; continue
        if char == "'" and quote != '"':
            quote = None if quote == "'" else "'"
            index += 1; continue
        if quote != "'" and (command.startswith('$(', index) or char == '`'):
            backtick = char == '`'
            start = index + (1 if backtick else 2)
            end, balance = start, 1
            while end < len(command) and balance:
                if command[end] == '\\':
                    end += 2; continue
                if backtick:
                    balance -= command[end] == '`'
                else:
                    balance += command[end] == '('
                    balance -= command[end] == ')'
                end += 1
            if balance:
                require(not NLM.search(command[start:]), 'NLM_SHELL_SYNTAX_UNRESOLVED')
                break
            def expansion_refused():
                raise Denied('NLM_NETWORK_GUARD_NLM_SHELL_COMPOSITION_FORBIDDEN')
            expansion_refused.scope_entry_paths = getattr(policy_loader, 'scope_entry_paths', ())
            shell_command(command[start:end - 1], expansion_refused, cwd, depth + 1, seen)
            index = end; continue
        if char == '"' and quote != "'":
            quote = None if quote == '"' else '"'
        index += 1


def shell_command(command, policy_loader, cwd, depth=0, seen=None):
    require(depth <= 6, 'SHELL_NESTING_UNRESOLVED')
    seen = set() if seen is None else seen
    command = _data_heredocs(command)
    # Literal Python stdin heredocs are a single interpreter invocation. Their
    # data paths must not become synthetic shell argv when parentheses/newlines
    # are tokenized. Only this precise syntax is handled here, without execution.
    if '\n' in command and '<<' in command.split('\n', 1)[0]:
        first, rest = command.split('\n', 1)
        match = re.fullmatch(r"(.*?)\s*<<\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2\s*", first)
        if match:
            header_argv = strip_wrappers(shlex.split(match.group(1)))
            lines = rest.splitlines(keepends=True)
            terminator = next((i for i, line in enumerate(lines) if line.rstrip('\r\n') == match.group(3)), None)
            if (header_argv and re.fullmatch(r'python(?:\d+(?:\.\d+)*)?', Path(header_argv[0]).name)
                    and header_argv[-1] == '-' and terminator is not None
                    and all(flag in {'-B', '-E', '-BE', '-EB', '-BES', '-I', '-u', '-s', '-S'} for flag in header_argv[1:-1])):
                require('$' not in first and chr(96) not in first,
                        'EXPANDING_PYTHON_HEREDOC_HEADER_UNRESOLVED')
                body = ''.join(lines[:terminator])
                require(bool(match.group(2)) or ('$' not in body and chr(96) not in body),
                        'EXPANDING_PYTHON_HEREDOC_UNRESOLVED')
                require(not _scope_probe(_python_mentions, body, Path(cwd) / '<stdin>.py', depth, seen),
                        'UNBOUND_PYTHON_HEREDOC_NETWORK')
                remainder = ''.join(lines[terminator + 1:]).strip()
                if remainder:
                    # The original command is compound. A preceding Python body
                    # could alter config after verification; do not turn a
                    # trailing registered entry into an independent approval.
                    def compound_network_refused():
                        raise Denied('NLM_NETWORK_GUARD_NLM_SHELL_COMPOSITION_FORBIDDEN')
                    compound_network_refused.scope_entry_paths = getattr(policy_loader, 'scope_entry_paths', ())
                    shell_command(remainder, compound_network_refused, cwd, depth + 1, seen)
                return
    _check_shell_expansions(command, policy_loader, cwd, depth, seen)
    command = _shell_comments(command)
    lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|()<>\n')
    lexer.whitespace_split = True
    lexer.whitespace = ' \t\r'
    # Comments are removed above while preserving their terminating newline;
    # shlex's own comment handling would hide a following command behind `cat`.
    lexer.commenters = ''
    try:
        tokens = list(lexer)
    except ValueError:
        require(not NLM.search(command), 'NLM_SHELL_SYNTAX_UNRESOLVED')
        return
    chunks, current = [], []
    for token in tokens:
        if token and set(token) <= set(';&|()\n'):
            if current:
                chunks.append(current); current = []
        else:
            current.append(token)
    if current:
        chunks.append(current)
    if len(chunks) > 1:
        original_loader = policy_loader
        def compound_refused():
            raise Denied('NLM_NETWORK_GUARD_NLM_SHELL_COMPOSITION_FORBIDDEN')
        compound_refused.scope_entry_paths = getattr(original_loader, 'scope_entry_paths', ())
        policy_loader = compound_refused
    # A command substitution/redirect can mutate input between verification and
    # execution. Never approve an NLM entry in compound or expanded shell text.
    for chunk in chunks:
        argv = strip_wrappers(chunk)
        if not argv:
            continue
        if Path(argv[0]).name in {'sh', 'bash', 'zsh'} and len(argv) == 3 and argv[1] in {'-c', '-lc'}:
            require(not _scope_probe(executable_mentions, argv, cwd, depth, seen) or (len(chunks) == 1
                    and '$' not in command and '`' not in command), 'NLM_SHELL_COMPOSITION_FORBIDDEN')
            shell_command(argv[2], policy_loader, cwd, depth + 1, seen)
            continue
        if Path(argv[0]).name in {'env', 'sudo', 'command', 'nohup', 'timeout'}:
            require(not _scope_probe(executable_mentions, argv, cwd, depth, seen), 'UNAPPROVED_NLM_WRAPPER')
            rest = argv[1:]
            while rest and (rest[0].startswith('-') or '=' in rest[0] or rest[0].isdigit()):
                rest = rest[1:]
            def wrapper_refused():
                raise Denied('NLM_NETWORK_GUARD_UNAPPROVED_NLM_WRAPPER')
            wrapper_refused.scope_entry_paths = getattr(policy_loader, 'scope_entry_paths', ())
            if rest:
                shell_command(shlex.join(rest), wrapper_refused, cwd, depth + 1, seen)
        if read_only(argv) and not any(v in {'>', '>>', '<', '<<'} or '$' in v or '`' in v for v in argv):
            continue
        # Registered executables always enter their original route validator,
        # even if static scanning cannot see a dynamic transport import. Compare
        # full resolved execution paths against the small installation registry.
        executable = argv[0]
        if re.fullmatch(r'python(?:\d+(?:\.\d+)*)?', Path(argv[0]).name, re.I):
            executable = next((v for v in argv[1:] if not v.startswith('-')), '')
            if any(v in {'-c', '-m'} for v in argv[1:]):
                executable = ''
        candidate = Path(executable) if executable else None
        if candidate is not None and not candidate.is_absolute():
            candidate = Path(cwd) / candidate
        registered = (candidate is not None and str(candidate.resolve()) in
                      getattr(policy_loader, 'scope_entry_paths', ()))
        if not registered and not _scope_probe(executable_mentions, argv, cwd, depth, seen):
            continue
        require(len(chunks) == 1 and '\n' not in command.strip() and '$' not in command and '`' not in command
                and not any(v in {'>', '>>', '<', '<<'} for v in argv), 'NLM_SHELL_COMPOSITION_FORBIDDEN')
        try:
            policy_ref, policy = policy_loader()
            if policy.get('schema') == 'nlm-loaded-entry-registry-v1':
                policy_ref, policy = select_registered(argv, policy)
            offline = [item for item in policy.get('offline_commands', []) if item.get('argv') == argv]
            if offline:
                require(len(offline) == 1 and offline[0].get('network') == 'none'
                        and bool(offline[0].get('files')), 'REVIEWED_OFFLINE_COMMAND_REQUIRED')
                for item in offline[0]['files']:
                    pinned(item)
                return
            approved_entry(argv, policy_ref, policy, cwd)
        except Denied as exc:
            # At this point there is positive scope evidence. A timeout during
            # authorization must never become the parser's unknown result.
            if str(exc).endswith('_LOCAL_DEADLINE'):
                raise Denied('NLM_NETWORK_GUARD_AUTHORIZATION_DEADLINE') from exc
            raise


def event_check(payload, policy_loader):
    require(isinstance(payload, dict), 'EVENT_OBJECT_REQUIRED')
    name = next((payload[k] for k in ('tool_name', 'toolName', 'tool', 'name') if payload.get(k)), '')
    require(isinstance(name, str) and bool(name), 'TOOL_NAME_REQUIRED')
    data = next((payload[k] for k in ('tool_input', 'toolInput', 'input', 'arguments') if k in payload), {})
    short = re.split(r'[.:/]', name.lower())[-1]
    if short in READ_TOOLS:
        return
    if NLM.search(name):
        raise Denied('NLM_NETWORK_GUARD_DIRECT_MCP_OR_UNBOUND_TOOL_FORBIDDEN')
    if not EXECUTION.search(name):
        # Explicit target URLs also cover browser/fetch tools with generic names.
        require(not re.search(r'https?://notebook(?:lm)?\.google\.com', json.dumps(data), re.I),
                'UNBOUND_NLM_DESTINATION')
        return
    cwd = payload.get('cwd') or os.getcwd()
    if isinstance(data, dict):
        cwd = data.get('workdir') or data.get('cwd') or cwd
        command = data.get('cmd') or data.get('command')
        code = data.get('code') or data.get('source')
        if isinstance(command, str):
            shell_command(command, policy_loader, cwd)
            return
    else:
        code = data if isinstance(data, str) else None
    if not isinstance(code, str):
        require(not NLM.search(json.dumps(data)), 'EXECUTION_PAYLOAD_UNRESOLVED')
        return
    # Parse executable calls; comments, labels and data strings are not calls.
    if 'python' in name.lower() and not name.endswith('functions.exec'):
        require(not _scope_probe(_python_mentions, code, Path(cwd) / '<tool-inline>.py'), 'DIRECT_PYTHON_NLM_NETWORK_FORBIDDEN')
    else:
        require(not _scope_probe(_javascript_mentions, code, cwd, policy_loader=policy_loader),
                'NLM_DYNAMIC_EXEC_OR_DIRECT_SDK_FORBIDDEN')


def load_registry(path, sha256):
    """Installation-pinned entry dispatch, never a task-selected policy list."""
    registry_ref, body = file_ref(path)
    require(registry_ref['sha256'] == sha256, 'REGISTERED_REGISTRY_CHANGED')
    registry = json.loads(body)
    require(registry.get('schema') == 'nlm-network-entry-registry-v1'
            and 1 <= len(registry.get('entries', [])) <= 8, 'ENTRY_REGISTRY_SCHEMA')
    paths = set()
    for item in registry['entries']:
        # Registry is pinned; inspect descriptors without coupling old entry
        # availability to another release's current files.
        for key in ('entry', 'authority', 'policy'):
            require(set(item[key]) == {'path', 'bytes', 'sha256'}
                    and Path(item[key]['path']).is_absolute(), 'REGISTRY_EXACT_DESCRIPTOR_REQUIRED')
        entry = item['entry']['path']
        require(item['authority']['path'] == str(Path(entry).parent.parent.parent / 'NLM-ROUTE-POLICY-PIN.json')
                and entry not in paths, 'ENTRY_AUTHORITY_NOT_UNIQUE')
        modes = item['modes']
        require(modes in (['prepare', 'run'], ['legacy-run']), 'EXACT_REGISTERED_MODES_REQUIRED')
        paths.add(entry)
    return registry_ref, {'schema': 'nlm-loaded-entry-registry-v1', 'entries': registry['entries']}


def select_registered(argv, registry):
    matches = [item for item in registry['entries'] if len(argv) >= 3
               and str(Path(argv[2]).resolve()) == item['entry']['path']]
    if not matches:
        # Preserve exact reviewed old offline commands; none is invented here.
        matches = [item for item in registry['entries'] if item['modes'] == ['prepare', 'run']
                   and argv in item.get('offline_argv', [])]
    require(len(matches) == 1, 'REGISTERED_ENTRY_REQUIRED')
    item = matches[0]
    authority = json.loads(pinned(item['authority']))
    require(authority.get('schema') == 'nlm-network-policy-authority-v1'
            and authority.get('policy') == item['policy'], 'REGISTRY_AUTHORITY_CHANGED')
    policy_ref, policy = load_policy(item['policy']['path'], item['policy']['sha256'])
    require(policy_ref == item['policy'] and policy['entry'] == item['entry'], 'REGISTRY_POLICY_CHANGED')
    if item['modes'] == ['legacy-run']:
        require(not policy.get('offline_commands') and not item.get('offline_argv'), 'LEGACY_OFFLINE_BYPASS_FORBIDDEN')
        contracts = policy.get('legacy_contracts')
        require(isinstance(contracts, list) and bool(contracts), 'LEGACY_POLICY_CONTRACTS_REQUIRED')
        for contract in contracts: pinned(contract)
    return policy_ref, {**policy, '_registered_modes': item['modes']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--policy')
    group.add_argument('--registry')
    parser.add_argument('--policy-sha256')
    parser.add_argument('--registry-sha256')
    parser.add_argument('--self-sha256')
    parser.add_argument('--entry-path', action='append', default=[],
                        help='Installation-owned exact entry path; repeat for every registry entry')
    args = parser.parse_args()
    def deadline(*_):
        raise Denied('NLM_NETWORK_GUARD_LOCAL_DEADLINE')
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, 4)
    try:
        if args.self_sha256:
            self_ref, _ = file_ref(__file__)
            require(self_ref['sha256'] == args.self_sha256, 'REGISTERED_HOOK_SOURCE_CHANGED')
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        require(len(raw) <= MAX_BYTES, 'EVENT_TOO_LARGE')
        payload = json.loads(raw)
        require(bool(args.policy_sha256) if args.policy else bool(args.registry_sha256), 'REGISTERED_PIN_REQUIRED')
        loader = PolicyLoader('policy' if args.policy else 'registry',
                              args.policy or args.registry,
                              args.policy_sha256 if args.policy else args.registry_sha256,
                              args.entry_path)
        event_check(payload, loader)
        print('{}')
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        # No raw payloads, source text, route credentials or arbitrary exception
        # messages are copied to the user-facing decision.
        reason = str(exc) if isinstance(exc, Denied) else 'NLM_NETWORK_GUARD_INVALID_OR_UNREADABLE_BINDING'
        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny', 'permissionDecisionReason': reason}}))
        print(reason, file=sys.stderr)
        return 2
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__':
    raise SystemExit(main())
