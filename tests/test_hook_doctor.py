import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import selectors

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import hook_doctor


class HookDoctorTests(unittest.TestCase):
    def test_utf8_split_across_confirmed_node_data_events_passes_through_bytes(self):
        env = os.environ.copy()
        for key in ("THESIS_REFINER_ROOT", "THESIS_REFINER_CHECKPOINT", "THESIS_REFINER_DELIVERY_CHECKPOINT"):
            env.pop(key, None)
        script = ("require(process.argv[1]); "
                  "process.stdin.on('data',()=>process.stderr.write('CHUNK\\n')); "
                  "process.stderr.write('READY\\n');")
        payload = '{"task":"论文😀", "count":1}\n'.encode("utf-8")
        first = payload.index("论".encode()) + 1
        second = payload.index("😀".encode()) + 2
        chunks = [payload[:first], payload[first:second], payload[second:]]
        with subprocess.Popen(["node", "-e", script, str(ROOT / "hooks/a5-termination-auditor.js")],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) as proc:
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(proc.stderr, selectors.EVENT_READ)
                    self.assertTrue(selector.select(5), "Node did not become ready")
                    self.assertEqual(proc.stderr.readline(), b"READY\n")
                    for chunk in chunks[:-1]:
                        proc.stdin.write(chunk)
                        proc.stdin.flush()
                        self.assertTrue(selector.select(5), "Node did not consume prior chunk")
                        self.assertEqual(proc.stderr.readline(), b"CHUNK\n")
                out, err = proc.communicate(chunks[-1], timeout=5)
                self.assertEqual(proc.returncode, 0, err)
                self.assertEqual(err, b"CHUNK\n")
                self.assertEqual(out, payload)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()

    def test_native_config_is_separate_from_legacy_and_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            active = root / "settings.json"
            active.write_text(json.dumps({"env": {"token": "SYNTHETIC_SECRET"}, "hooks": {"Stop": [{"hooks": [{"command": f'node "{ROOT}/hooks/a5-termination-auditor.js"'}]}]}}))
            legacy = root / "hooks.json"
            legacy.write_text(json.dumps({"hooks": {"Stop": [{"command": 'node "$env:USERPROFILE\\.claude\\hooks\\thesis-refiner\\a5-termination-auditor.js"'}]}}))
            report = hook_doctor.doctor(ROOT, [active], [legacy])
            self.assertTrue(report["entrypoint_pass"])
            self.assertTrue(report["canonical_registration_found"])
            self.assertEqual(report["client_invocation"], "NOT_MEASURED")
            self.assertNotIn("SYNTHETIC_SECRET", json.dumps(report))
            self.assertFalse(report["configs"][1]["declared_active_config"])
            self.assertIsNone(report["configs"][1]["registrations"][0]["resolved_hook"])

    def test_relocated_hook_requires_explicit_skill_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            hook = Path(tmp) / "hooks/a5-termination-auditor.js"
            hook.parent.mkdir()
            shutil.copyfile(ROOT / "hooks/a5-termination-auditor.js", hook)
            env = os.environ.copy()
            for k in ("THESIS_REFINER_ROOT", "THESIS_REFINER_CHECKPOINT", "THESIS_REFINER_DELIVERY_CHECKPOINT"):
                env.pop(k, None)
            env["THESIS_PYTHON"] = sys.executable
            def run(payload):
                return subprocess.run(["node", str(hook)], input=json.dumps(payload), text=True, capture_output=True, env=env)
            self.assertEqual(run({}).returncode, 0)
            r = run({"workflow_checkpoint": str(Path(tmp) / "missing.json")})
            self.assertEqual(r.returncode, 2)
            self.assertIn("SKILL_ENTRYPOINT_MISSING", r.stderr)
            env["THESIS_REFINER_ROOT"] = str(ROOT)
            r = run({"workflow_checkpoint": str(Path(tmp) / "missing.json")})
            self.assertEqual(r.returncode, 2)
            self.assertNotIn("SKILL_ENTRYPOINT_MISSING", r.stderr)
            self.assertEqual(run({"workflow_checkpoint": True}).returncode, 2)
            for value in (False, None, "", 0):
                self.assertEqual(run({"workflow_checkpoint": value}).returncode, 2)
            self.assertEqual(run({"workflow_checkpoint": "relative.json"}).returncode, 2)
            self.assertEqual(run([]).returncode, 2)

    def test_cli_reports_missing_registration_without_claiming_hook_loaded(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts/hook_doctor.py")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(r.stdout)
        self.assertFalse(report["canonical_registration_found"])
        self.assertEqual(report["client_reload"], "NOT_MEASURED")

    def test_report_cannot_overwrite_client_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "settings.json"
            original = '{"hooks": {}}'
            config.write_text(original)
            r = subprocess.run([sys.executable, str(ROOT / "scripts/hook_doctor.py"), "--config", str(config), "--output", str(config)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertEqual(config.read_text(), original)


if __name__ == "__main__":
    unittest.main()
