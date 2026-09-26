import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("thesis_installer", Path(__file__).resolve().parents[1] / "scripts/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def test_rollback_rechecks_after_temporary_fsync_and_keeps_concurrent_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            canonical = root / "canonical"
            canonical.mkdir()
            target = canonical / "SKILL.md"
            target.write_bytes(b"original")
            plan = installer.install(canonical, apply=True)
            actual_fsync = os.fsync
            injections = []

            def interleave(fd):
                actual_fsync(fd)
                target.write_bytes(b"concurrent revision")
                injections.append(fd)

            with patch.object(installer.os, "fsync", side_effect=interleave):
                with self.assertRaisesRegex(ValueError, "ROLLBACK_CONCURRENT_CHANGE"):
                    installer.rollback(plan["manifest"], apply=True)
            self.assertEqual(len(injections), 1)
            self.assertEqual(target.read_bytes(), b"concurrent revision")
            backup = Path(plan["backup_root"])
            self.assertFalse((backup / "ROLLED-BACK.json").exists())
            self.assertTrue((backup / "ROLLBACK-INCOMPLETE.json").exists())
            self.assertFalse(list(canonical.glob(".thesis-install-*")))
            with installer.mutation_locks(canonical):
                pass  # The failed rollback released its OS lock.

    def test_install_rechecks_after_temporary_fsync_and_keeps_concurrent_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / "source"
            source.mkdir()
            (source / "SKILL.md").write_bytes(b"next version")
            (source / "README.md").write_bytes(b"readme")
            canonical = root / "canonical"
            canonical.mkdir()
            target = canonical / "README.md"
            target.write_bytes(b"prior version")
            actual_fsync = os.fsync
            def interleave(fd):
                actual_fsync(fd)
                target.write_bytes(b"concurrent install edit")
            with patch.object(installer, "ROOT", source), patch.object(installer.os, "fsync", side_effect=interleave):
                with self.assertRaisesRegex(ValueError, "CONCURRENT_INSTALL_CHANGE"):
                    installer.install(canonical, apply=True)
            self.assertEqual(target.read_bytes(), b"concurrent install edit")
            backups = list(root.glob("canonical.backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertTrue((backups[0] / "INCOMPLETE.json").exists())
            self.assertFalse((backups[0] / "INSTALLED.json").exists())

    def test_os_lock_rejects_competing_install_and_rollback_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            canonical, adapter = root / "canonical", root / "adapter"
            plan = installer.install(canonical, adapter, apply=True)
            original = (canonical / "SKILL.md").read_bytes()
            script = Path(installer.__file__)
            # Holding either resource must protect both operations, including
            # rollback's deletion of files introduced by the original install.
            for held in (canonical, adapter):
                with installer.mutation_locks(held):
                    for args in (("--canonical", str(canonical), "--codex-adapter", str(adapter)),
                                 ("--rollback", plan["manifest"])):
                        p = subprocess.run([sys.executable, "-B", str(script), *args, "--apply"],
                                           capture_output=True, text=True, timeout=10)
                        self.assertNotEqual(p.returncode, 0)
                        self.assertIn("INSTALL_ROOT_BUSY", p.stderr)
                        self.assertEqual((canonical / "SKILL.md").read_bytes(), original)
                        self.assertFalse((Path(plan["backup_root"]) / "ROLLED-BACK.json").exists())
            with installer.mutation_locks(canonical, adapter):
                pass


    def test_adapter_cannot_overlap_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / "source"
            source.mkdir()
            for adapter in (source, source / "nested", root):
                with patch.object(installer, "ROOT", source):
                    with self.assertRaisesRegex(ValueError, "ADAPTER_AND_SOURCE"):
                        installer.install(root / "dest", adapter, apply=True)
            self.assertFalse((root / "dest").exists())

    def test_nonboolean_rollback_marker_is_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            plan = installer.install(root / "canonical", apply=True)
            manifest = Path(plan["manifest"])
            original = json.loads(manifest.read_text())
            for bad in ("true", "false", 0, 1, None):
                altered = json.loads(json.dumps(original))
                altered["files"][0]["changed"] = bad
                manifest.write_text(json.dumps(altered))
                with self.assertRaisesRegex(ValueError, "BOOLEAN_CHANGE"):
                    installer.rollback(manifest, apply=True)
                self.assertTrue((root / "canonical/SKILL.md").exists())

    def test_rollback_restores_bytes_removes_new_files_and_preserves_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            canonical, adapter = root / "canonical", root / "adapter"
            canonical.mkdir()
            (canonical / "SKILL.md").write_text("old")
            (canonical / "private.log").write_text("untouched")
            plan = installer.install(canonical, adapter, apply=True)
            preview = installer.rollback(plan["manifest"])
            self.assertFalse(preview["applied"])
            self.assertNotEqual((canonical / "SKILL.md").read_text(), "old")
            receipt = installer.rollback(plan["manifest"], apply=True)
            self.assertTrue(receipt["applied"])
            self.assertEqual((canonical / "SKILL.md").read_text(), "old")
            self.assertEqual((canonical / "private.log").read_text(), "untouched")
            self.assertFalse((canonical / "scripts/workflow.py").exists())
            self.assertFalse((adapter / "SKILL.md").exists())

    def test_rollback_checks_all_drift_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            plan = installer.install(root / "canonical", apply=True)
            current = root / "canonical/SKILL.md"
            first = current.read_bytes()
            tail = root / "canonical/scripts/workflow.py"
            tail.write_text("concurrent writer")
            with self.assertRaisesRegex(ValueError, "CONCURRENT_CHANGE"):
                installer.rollback(plan["manifest"], apply=True)
            self.assertEqual(current.read_bytes(), first)
            self.assertEqual(tail.read_text(), "concurrent writer")

    def test_backup_corruption_and_symlink_parent_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            c = root / "canonical"
            c.mkdir()
            (c / "SKILL.md").write_text("original")
            plan = installer.install(c, apply=True)
            old = next(r for r in plan["files"] if r["path"] == str(c / "SKILL.md"))
            Path(old["backup"]).write_text("corrupt")
            with self.assertRaisesRegex(ValueError, "BACKUP_HASH"):
                installer.rollback(plan["manifest"], apply=True)
            link = root / "link"
            link.symlink_to(c, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "SYMLINKED"):
                installer.install(link / "nested", apply=True)

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
