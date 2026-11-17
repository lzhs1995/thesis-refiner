import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("codex_skill_alias", Path(__file__).resolve().parents[1] / "scripts/codex_skill_alias.py")
alias = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alias)


class CodexAliasTests(unittest.TestCase):
    def fixture(self, root):
        release = root / "release"
        release.mkdir()
        (release / "SKILL.md").write_text("complete canonical skill fixture")
        canonical = root / "stable"
        canonical.symlink_to(release, target_is_directory=True)
        adapter = root / "codex-alias"
        adapter.mkdir()
        (adapter / "SKILL.md").write_bytes(b"old discovery route")
        previous = alias.digest((adapter / "SKILL.md").read_bytes())
        return canonical / "SKILL.md", adapter, previous

    def approved(self, root, canonical, adapter, previous):
        plan = alias.preview(canonical, adapter, previous)
        raw = (json.dumps(plan, ensure_ascii=False, indent=2) + "\n").encode()
        path = root / "APPROVED.json"
        path.write_bytes(raw)
        return path, alias.digest(raw)

    def test_symlinked_canonical_preview_is_zero_write_and_apply_changes_only_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            canonical, adapter, previous = self.fixture(root)
            release_before = canonical.resolve().read_bytes()
            old = (adapter / "SKILL.md").read_bytes()
            entries = set(root.iterdir())
            plan = alias.preview(canonical, adapter, previous)
            self.assertEqual(set(root.iterdir()), entries)
            self.assertEqual((adapter / "SKILL.md").read_bytes(), old)
            self.assertIn(str(canonical), plan["content_utf8"])
            path, sha = self.approved(root, canonical, adapter, previous)
            result = alias.apply(path, sha, root / "journal")
            self.assertTrue(result["applied"])
            self.assertEqual(Path(result["backup"]).read_bytes(), old)
            self.assertEqual(canonical.resolve().read_bytes(), release_before)
            self.assertEqual((adapter / "SKILL.md").read_bytes(), alias.content_for(canonical))
            self.assertEqual(result["runtime_adoption"], "NOT_CLAIMED")

    def test_predecessor_or_plan_tamper_is_refused_without_alias_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            canonical, adapter, previous = self.fixture(root)
            with self.assertRaisesRegex(ValueError, "PREDECESSOR_SHA_MISMATCH"):
                alias.preview(canonical, adapter, "0" * 64)
            path, sha = self.approved(root, canonical, adapter, previous)
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "PLAN_SHA_MISMATCH"):
                alias.apply(path, sha, root / "journal")
            self.assertFalse((root / "journal").exists())
            self.assertEqual(alias.digest((adapter / "SKILL.md").read_bytes()), previous)

    def test_alias_drift_or_canonical_switch_after_preview_refuses_before_journal(self):
        for drift in ("alias", "canonical"):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                canonical, adapter, previous = self.fixture(root)
                path, sha = self.approved(root, canonical, adapter, previous)
                if drift == "alias":
                    (adapter / "SKILL.md").write_bytes(b"user edit")
                else:
                    other = root / "other"
                    other.mkdir()
                    (other / "SKILL.md").write_text("different canonical")
                    canonical.parent.unlink()
                    canonical.parent.symlink_to(other, target_is_directory=True)
                old = (adapter / "SKILL.md").read_bytes()
                with self.assertRaisesRegex(ValueError, "SHA_MISMATCH|PLAN_INPUT_CHANGED"):
                    alias.apply(path, sha, root / "journal")
                self.assertEqual((adapter / "SKILL.md").read_bytes(), old)
                self.assertFalse((root / "journal").exists())

    def test_symlinked_destination_and_source_overlap_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            canonical, adapter, previous = self.fixture(root)
            link = root / "linked-destination"
            link.symlink_to(adapter, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "SYMLINKED_INSTALL_PATH"):
                alias.preview(canonical, link, previous)
            with self.assertRaisesRegex(ValueError, "SEPARATE_FROM_SOURCE"):
                alias.preview(canonical, canonical.resolve().parent, "ABSENT")

    def test_noncooperating_edit_during_stage_is_preserved_with_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            canonical, adapter, previous = self.fixture(root)
            path, sha = self.approved(root, canonical, adapter, previous)
            target = adapter / "SKILL.md"
            original_replace = alias._installer.replace_bytes
            def interleave(*args, **kwargs):
                target.write_bytes(b"concurrent user edit")
                return original_replace(*args, **kwargs)
            with patch.object(alias._installer, "replace_bytes", side_effect=interleave):
                with self.assertRaisesRegex(ValueError, "ALIAS_CONCURRENT_CHANGE"):
                    alias.apply(path, sha, root / "journal")
            self.assertEqual(target.read_bytes(), b"concurrent user edit")
            self.assertEqual((root / "journal" / "BEFORE.md").read_bytes(), b"old discovery route")
            self.assertEqual(json.loads((root / "journal" / "INCOMPLETE.json").read_text())["outcome"], "CONCURRENT_TARGET_CHANGE")

    def test_symlinked_skill_file_is_refused_at_preview_including_dangling_links(self):
        for dangling in (False, True):
            with self.subTest(dangling=dangling), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                canonical, adapter, previous = self.fixture(root)
                external = root / "external.md"
                if not dangling:
                    external.write_bytes((adapter / "SKILL.md").read_bytes())
                target = adapter / "SKILL.md"
                target.unlink()
                target.symlink_to(external)
                entries = set(root.iterdir())
                with self.assertRaisesRegex(ValueError, "SYMLINKED_INSTALL_PATH"):
                    alias.preview(canonical, adapter, "ABSENT" if dangling else previous)
                self.assertEqual(set(root.iterdir()), entries)
                self.assertTrue(target.is_symlink())
                self.assertEqual(external.exists(), not dangling)
                if not dangling:
                    self.assertEqual(external.read_bytes(), b"old discovery route")

    def test_target_becomes_symlink_after_preview_refuses_before_journal(self):
        for dangling in (False, True):
            with self.subTest(dangling=dangling), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                canonical, adapter, previous = self.fixture(root)
                path, sha = self.approved(root, canonical, adapter, previous)
                external = root / "external.md"
                if not dangling:
                    external.write_bytes((adapter / "SKILL.md").read_bytes())
                target = adapter / "SKILL.md"
                target.unlink()
                target.symlink_to(external)
                with self.assertRaisesRegex(ValueError, "SYMLINKED_INSTALL_PATH"):
                    alias.apply(path, sha, root / "journal")
                self.assertFalse((root / "journal").exists())
                self.assertTrue(target.is_symlink())
                self.assertEqual(external.exists(), not dangling)
                if not dangling:
                    self.assertEqual(external.read_bytes(), b"old discovery route")

    def test_committed_sync_failure_keeps_new_alias_and_reports_uncertainty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            canonical, adapter, previous = self.fixture(root)
            path, sha = self.approved(root, canonical, adapter, previous)
            original_sync = alias.sync_directory
            def fail_target(directory):
                if directory == adapter:
                    raise OSError("directory sync failed")
                return original_sync(directory)
            with patch.object(alias, "sync_directory", side_effect=fail_target):
                with self.assertRaisesRegex(OSError, "sync failed"):
                    alias.apply(path, sha, root / "journal")
            self.assertEqual((adapter / "SKILL.md").read_bytes(), alias.content_for(canonical))
            diagnostic = json.loads((root / "journal" / "INCOMPLETE.json").read_text())
            self.assertEqual(diagnostic["outcome"], "COMMITTED_POSTCHECK_UNKNOWN")
            self.assertFalse(diagnostic["automatic_rollback"])

    def test_cooperating_install_lock_refuses_before_journal_or_alias_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            canonical, adapter, previous = self.fixture(root)
            path, sha = self.approved(root, canonical, adapter, previous)
            with alias._installer.mutation_locks(adapter):
                with self.assertRaisesRegex(RuntimeError, "INSTALL_ROOT_BUSY"):
                    alias.apply(path, sha, root / "journal")
            self.assertFalse((root / "journal").exists())
            self.assertEqual(alias.digest((adapter / "SKILL.md").read_bytes()), previous)

    def test_fresh_alias_and_identical_route_are_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            canonical, adapter, previous = self.fixture(root)
            target = adapter / "SKILL.md"
            target.unlink()
            path, sha = self.approved(root, canonical, adapter, "ABSENT")
            result = alias.apply(path, sha, root / "journal")
            self.assertIsNone(result["backup"])
            same = alias.preview(canonical, adapter, alias.digest(target.read_bytes()))
            self.assertFalse(same["changed"])
            other = root / "NOOP.json"
            raw = json.dumps(same).encode()
            other.write_bytes(raw)
            result = alias.apply(other, alias.digest(raw), root / "unused-journal")
            self.assertFalse(result["applied"])
            self.assertFalse((root / "unused-journal").exists())


if __name__ == "__main__":
    unittest.main()
