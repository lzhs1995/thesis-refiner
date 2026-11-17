"""Portable NLM boundary tests; inspect source text without executing it.

Place this file in a repository's tests/ beside scripts/nlm_network_guard.py.
All inputs are synthetic. No installed SDK, browser, Herdr, network, private
checkout or historical release is needed.
"""
import importlib.util
import json
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch


GUARD_PATH = Path(__file__).resolve().parents[1] / "scripts" / "nlm_network_guard.py"
SPEC = importlib.util.spec_from_file_location("scope_boundary_guard", GUARD_PATH)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class ScopeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="scope-boundary-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def classify_python(self, source, arguments=()):
        return guard._python_mentions(
            source, self.root / "synthetic.py", arguments=arguments
        )

    def classify_javascript(self, source):
        return guard._javascript_mentions(source, self.root)

    def no_registry(self):
        raise AssertionError("Unrelated local work must not read the NLM registry")

    def empty_registry(self):
        return {}, {"schema": "nlm-loaded-entry-registry-v1", "entries": []}

    def test_generic_python_http_unknown_values_are_not_nlm_evidence(self):
        sources = [
            'import requests\nrequests.post(endpoint)',
            'import requests\nrequests.post("http://127.0.0.1:3000", json=payload, headers=headers)',
            'import httpx\nc=httpx.Client();c.request(method,endpoint,json=payload)',
            'import urllib.request\nurllib.request.urlopen(endpoint)',
        ]
        for source in sources:
            with self.subTest(source=source):
                self.assertFalse(self.classify_python(source))

    def test_python_message_payload_is_not_destination(self):
        sources = [
            'import requests\nrequests.post("http://localhost:3000",data="https://notebooklm.google.com")',
            'import requests\nrequests.request("POST",url="http://localhost:3000",json=payload,headers=headers)',
            'import requests\nrequests.get("http://localhost",params="notebooklm.google.com")',
        ]
        for source in sources:
            with self.subTest(source=source):
                self.assertFalse(self.classify_python(source))

    def test_python_explicit_nlm_destination_slots_remain_detected(self):
        sources = [
            'import requests\nrequests.request("POST","https://notebooklm.google.com",json=payload)',
            'import requests\ns=requests.Session();s.request(method,url="https://notebooklm.google.com",headers=headers)',
            'from urllib.request import Request,urlopen\nr=Request("https://notebooklm.google.com",data=payload);urlopen(r)',
            'import requests\ns=requests.Session();r=requests.Request("POST","https://notebooklm.google.com",json=payload);s.send(r)',
            'import httpx\nc=httpx.Client(base_url="https://notebooklm.google.com");c.post("/rpc",json=payload)',
            'import aiohttp\nc=aiohttp.ClientSession(base_url="https://notebooklm.google.com")',
        ]
        for source in sources:
            with self.subTest(source=source):
                self.assertTrue(self.classify_python(source))

    def test_literal_argv_destination_is_not_all_argument_text(self):
        self.assertTrue(
            self.classify_python(
                'import sys,requests\nrequests.post(sys.argv[1],json=payload)',
                arguments=("https://notebooklm.google.com",),
            )
        )
        self.assertFalse(
            self.classify_python(
                'import requests\nrequests.get("http://localhost")',
                arguments=("NLM maintenance mentions https://notebooklm.google.com",),
            )
        )

    def test_compile_only_is_not_execution(self):
        for source in (
            'compile("import notebooklm","fixture","exec")',
            'code=compile("import notebooklm","fixture","exec");print(code)',
        ):
            with self.subTest(source=source):
                self.assertFalse(self.classify_python(source))

    def test_executed_compiled_nlm_source_remains_detected(self):
        sources = [
            'exec(compile("import notebooklm","fixture","exec"))',
            'code=compile("import notebooklm","fixture","exec");exec(code)',
            'code=compile("import notebooklm","fixture","exec");alias=code;exec(alias)',
            'import builtins\nbuiltins.exec(builtins.compile("import notebooklm","fixture","exec"))',
            'eval(compile(\'__import__("notebooklm")\',"fixture","eval"))',
            'exec(compile(\'import requests;requests.post("https://notebooklm.google.com")\',"fixture","exec"))',
        ]
        for source in sources:
            with self.subTest(source=source):
                self.assertTrue(self.classify_python(source))

    def test_generic_javascript_http_and_message_body_are_not_nlm(self):
        sources = [
            'fetch(endpoint,{body:payload,headers:headers});',
            'const axios=require("axios");axios.request({url:endpoint,data:payload});',
            'const http=require("http");http.request({hostname:host,path:"/",headers:headers});',
            'fetch("http://localhost:3000","https://notebooklm.google.com");',
            'axios.request({url:"http://localhost",data:"https://notebooklm.google.com"});',
        ]
        for source in sources:
            with self.subTest(source=source):
                self.assertFalse(self.classify_javascript(source))

    def test_javascript_explicit_nlm_objects_remain_detected(self):
        sources = [
            'fetch("https://notebooklm.google.com",{body:payload});',
            'axios.request({url:"https://notebooklm.google.com",data:payload});',
            'https.request({hostname:"notebooklm.google.com",headers:headers});',
            'const options={url:"https://notebooklm.google.com",data:payload};axios.request(options);',
            'axios.create({baseURL:"https://notebooklm.google.com"});',
            'fetch(new Request("https://notebooklm.google.com",{body:payload}));',
            'fetch(new URL("https://notebooklm.google.com"));',
        ]
        for source in sources:
            with self.subTest(source=source):
                self.assertTrue(self.classify_javascript(source))

    def test_local_print_and_communication_text_need_no_registry(self):
        native = self.root / "synthetic-native"
        native.write_bytes(b"\x7fELF" + b"\x00" * 32)
        # The fake is only header-read. It is never executable or invoked.
        command = "herdr --session example pane message target --text " + shlex.quote(
            "NLM maintenance mentions https://notebooklm.google.com"
        )
        with patch.object(guard.shutil, "which", return_value=str(native)):
            guard.shell_command(command, self.no_registry, self.root)
        local = self.root / "local_message.py"
        local.write_text('print("NLM maintenance fixture")\n', encoding="utf-8")
        guard.shell_command(
            "python3 -BE " + shlex.quote(str(local)), self.no_registry, self.root
        )
        guard.event_check(
            {
                "tool_name": "functions.exec",
                "tool_input": 'text("NLM maintenance");text(await tools.exec_command({cmd:'
                + json.dumps("python3 -BE " + shlex.quote(str(local)))
                + "}));",
                "cwd": str(self.root),
            },
            self.no_registry,
        )

    def test_explicit_sdk_cli_mcp_and_wrappers_remain_guarded(self):
        for source in (
            "import notebooklm",
            "from notebooklm import Client",
            'import importlib\nimportlib.import_module("notebooklm")',
        ):
            with self.subTest(source=source):
                self.assertTrue(self.classify_python(source))
        inner = self.root / "inner.py"
        inner.write_text("import notebooklm\n", encoding="utf-8")
        outer = self.root / "outer.py"
        outer.write_text(
            "import runpy\nrunpy.run_path(" + repr(str(inner)) + ")\n",
            encoding="utf-8",
        )
        commands = [
            "nlm query fixture",
            "python3 -m notebooklm query fixture",
            "curl https://notebooklm.google.com",
            "python3 " + shlex.quote(str(outer)),
        ]
        for command in commands:
            with self.subTest(command=command):
                with self.assertRaises(guard.Denied):
                    guard.shell_command(command, self.empty_registry, self.root)
        with self.assertRaises(guard.Denied):
            guard.event_check(
                {"tool_name": "mcp__notebooklm__query", "tool_input": {}},
                self.empty_registry,
            )

    def test_registered_entry_still_delegates_to_policy_validation(self):
        entry = self.root / "registered_entry.py"
        entry.write_text('print("synthetic entry")\n', encoding="utf-8")
        registry = {
            "schema": "nlm-loaded-entry-registry-v1",
            "entries": [{"entry": {"path": str(entry.resolve())}}],
        }
        loader = lambda: ({}, registry)
        loader.scope_entry_paths = frozenset({str(entry.resolve())})
        with patch.object(guard, "select_registered", return_value=({}, {})) as select:
            with patch.object(guard, "approved_entry") as approve:
                guard.shell_command(
                    "python3 -BE " + shlex.quote(str(entry)), loader, self.root,
                )
                select.assert_called_once()
                approve.assert_called_once()


if __name__ == "__main__":
    unittest.main()

