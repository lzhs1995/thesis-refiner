import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("thesis_installer", Path(__file__).resolve().parents[1] / "scripts/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def test_dry_run_then_overlay_preserves_private_files_and_old_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            canonical, adapter = root / "canonical", root / "adapter"
            canonical.mkdir()
            (canonical / "SKILL.md").write_text("legacy instructions")
            (canonical / "private.log").write_text("preserve")
            plan = installer.install(canonical, adapter)
            self.assertFalse(plan["applied"])
            self.assertFalse(adapter.exists())
            plan = installer.install(canonical, adapter, apply=True)
            old = next(x for x in plan["files"] if x["path"] == str(canonical / "SKILL.md"))
            self.assertEqual(Path(old["backup"]).read_text(), "legacy instructions")
            self.assertEqual((canonical / "private.log").read_text(), "preserve")
            self.assertIn(str(canonical / "SKILL.md"), (adapter / "SKILL.md").read_text())
            result = subprocess.run([sys.executable, str(canonical / "scripts/workflow.py"), "--help"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run(["node", str(canonical / "hooks/a5-termination-auditor.js")], input=json.dumps({"workflow_checkpoint": str(root / "missing.json")}), capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
