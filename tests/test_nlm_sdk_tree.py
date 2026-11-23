"""Synthetic regression for SDK tree deadlines and symlink rejection."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import nlm_sdk_entry as entry


@unittest.skipUnless(sys.version_info >= (3, 11) and os.name == 'posix',
                     'SDK tree entry requires Python 3.11+ and POSIX')
class SDKTreeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / 'sdk'
        self.root.mkdir()
        package = self.root / 'package'
        package.mkdir()
        self.member = package / 'module.py'
        self.member.write_text('value = "synthetic; never imported"\n')
        metadata = self.base / 'metadata.json'
        metadata.write_text('{}\n')
        manifest = self.base / 'manifest.json'
        manifest.write_text(json.dumps(dict(schema='nlm-sdk-environment-v1',
            import_roots=[str(self.root)], files=[entry.ref(self.member)],
            sources=[dict(metadata=entry.ref(metadata), version='fixture', upstream='offline')],
            versions={})))
        self.cfg = dict(sdk_manifest=entry.ref(manifest))

    def test_complete_tree_and_unlisted_regular_member(self):
        manifest, roots = entry.verify_sdk_tree(self.cfg)
        self.assertEqual(roots, [self.root])
        self.assertEqual(manifest['files'], [entry.ref(self.member)])
        (self.root / 'unlisted.py').write_text('unexpected = True\n')
        with self.assertRaisesRegex(ValueError, 'SDK_IMPORT_TREE_CHANGED'):
            entry.verify_sdk_tree(self.cfg)

    def test_file_and_directory_symlinks_are_rejected_even_to_pinned_members(self):
        for target in (self.member, self.member.parent):
            link = self.root / 'alias'
            link.symlink_to(target, target_is_directory=target.is_dir())
            try:
                with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'SDK_TREE_SYMLINK_FORBIDDEN'):
                    entry.verify_sdk_tree(self.cfg)
            finally:
                link.unlink()

    def test_broken_symlink_is_rejected_before_tree_comparison(self):
        (self.root / 'broken').symlink_to(self.root / 'missing')
        with self.assertRaisesRegex(ValueError, 'SDK_TREE_SYMLINK_FORBIDDEN'):
            entry.verify_sdk_tree(self.cfg)

    def test_real_alarm_during_scandir_propagates_original_timeout(self):
        original = os.scandir
        hit = []
        def delayed(path):
            if Path(path) == self.root:
                hit.append(True)
                signal.setitimer(signal.ITIMER_REAL, .02)
                time.sleep(1)
            return original(path)
        with patch.object(os, 'scandir', side_effect=delayed):
            with self.assertRaisesRegex(TimeoutError, '^SYNTHETIC_TREE_DEADLINE$'):
                with entry.phase_deadline(3, 'SYNTHETIC_TREE_DEADLINE'):
                    entry.verify_sdk_tree(self.cfg)
        self.assertEqual(hit, [True])

    def test_real_alarm_during_direntry_stat_propagates_original_timeout(self):
        original = os.scandir
        hit = []
        class DelayedEntry:
            def __init__(self, item):
                self.path, self.item = item.path, item
            def stat(self, *, follow_symlinks):
                if Path(self.path) == self_target:
                    hit.append(True)
                    signal.setitimer(signal.ITIMER_REAL, .02)
                    time.sleep(1)
                return self.item.stat(follow_symlinks=follow_symlinks)
        self_target = self.member
        @contextmanager
        def delayed(path):
            with original(path) as rows:
                yield (DelayedEntry(item) for item in rows)
        with patch.object(os, 'scandir', side_effect=delayed):
            with self.assertRaisesRegex(TimeoutError, '^SYNTHETIC_TREE_DEADLINE$'):
                with entry.phase_deadline(3, 'SYNTHETIC_TREE_DEADLINE'):
                    entry.verify_sdk_tree(self.cfg)
        self.assertEqual(hit, [True])

    def test_scandir_permission_error_is_not_a_partial_tree(self):
        with patch.object(os, 'scandir', side_effect=PermissionError('SYNTHETIC_DENIED')):
            with self.assertRaisesRegex(PermissionError, '^SYNTHETIC_DENIED$'):
                entry.verify_sdk_tree(self.cfg)

    def test_root_stat_timeout_is_not_false_missing_directory(self):
        original = Path.stat
        def interrupted(path, *args, **kwargs):
            if path == self.root:
                raise TimeoutError('SYNTHETIC_ROOT_STAT_TIMEOUT')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'stat', interrupted):
            with self.assertRaisesRegex(TimeoutError, '^SYNTHETIC_ROOT_STAT_TIMEOUT$'):
                entry.verify_sdk_tree(self.cfg)


if __name__ == '__main__':
    unittest.main()
