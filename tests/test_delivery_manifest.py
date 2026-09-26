import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from delivery_manifest import audit


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "最终包 (一)"
        self.root.mkdir()
        self.audio = self.root / "演练 #1.m4a"
        self.audio.write_bytes(b"synthetic audio; not decoded or listened")
        self.source = self.base / "original.m4a"
        self.source.write_bytes(self.audio.read_bytes())
        self.manifest = self.root / "MANIFEST.json"
        self.rows = [{**self.pin(self.audio), "package_path": self.audio.name, "source": self.pin(self.source)}]
        self.manifest.write_text(json.dumps({"files": self.rows}))
        self.archive = self.base / "final.zip"
        self.rezip()
        self.contract = {"schema": "delivery-manifest-v1", "manifest": self.pin(self.manifest),
                         "package_root": str(self.root), "require_sources": True,
                         "zip": {"file": self.pin(self.archive), "prefix": "最终包/"},
                         "roles": [{"id": "audio", "member": self.audio.name,
                                    "label": "演练音频", "suffixes": [".m4a"]}]}

    def pin(self, path):
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}

    def rezip(self, extra=None):
        with warnings.catch_warnings(), zipfile.ZipFile(self.archive, "w") as archive:
            warnings.simplefilter("ignore", UserWarning)
            for p in self.root.iterdir():
                archive.write(p, "最终包/" + p.name)
            if extra:
                archive.writestr(*extra)

    def test_exact_prefix_files_sources_and_encoded_links(self):
        result = audit(self.contract)
        self.assertEqual(result["zip"]["members"], 2)
        self.assertEqual(result["source_mappings"], 1)
        self.assertIn("演练 %231.m4a", result["markdown"])
        self.assertIn("最终包 (一)", result["markdown"])
        self.assertEqual(result["semantic_visual_listening_review"], "NOT_PERFORMED")

    def test_wrong_prefix_suffix_or_missing_role_fail(self):
        for which in ("prefix", "suffix", "member", "empty"):
            c = copy.deepcopy(self.contract)
            if which == "prefix": c["zip"]["prefix"] = "other/"
            if which == "suffix": c["roles"][0]["suffixes"] = [".m4sh"]
            if which == "member": c["roles"][0]["member"] = "typo.m4a"
            if which == "empty": c["roles"] = []
            with self.subTest(which=which), self.assertRaises(ValueError): audit(c)

    def test_extra_duplicate_and_escaping_zip_names_fail(self):
        for name in ("最终包/extra.bin", "最终包/" + self.audio.name, "../outside"):
            self.rezip((name, b"extra"))
            self.contract["zip"]["file"] = self.pin(self.archive)
            with self.subTest(name=name), self.assertRaises(ValueError): audit(self.contract)

    def test_crc_corruption_is_detected_despite_new_archive_hash(self):
        content = self.archive.read_bytes().replace(b"synthetic audio", b"Synthetic audio", 1)
        self.archive.write_bytes(content)
        self.contract["zip"]["file"] = self.pin(self.archive)
        with self.assertRaises(zipfile.BadZipFile): audit(self.contract)

    def test_changed_original_is_not_hidden_by_valid_copy(self):
        self.source.write_bytes(b"different source")
        with self.assertRaisesRegex(ValueError, "FILE_DRIFT"): audit(self.contract)

    def test_undeclared_package_file_fails(self):
        (self.root / "unlisted.pdf").write_bytes(b"unlisted")
        with self.assertRaisesRegex(ValueError, "MEMBER_SET_MISMATCH"): audit(self.contract)

    def test_boolean_size_and_unsafe_member_fail(self):
        for change in ({"bytes": True}, {"package_path": "../original.m4a"}):
            rows = copy.deepcopy(self.rows)
            rows[0].update(change)
            self.manifest.write_text(json.dumps({"files": rows}))
            self.contract["manifest"] = self.pin(self.manifest)
            with self.subTest(change=change), self.assertRaises(ValueError): audit(self.contract)

    def test_cli_writes_new_links_and_never_overwrites(self):
        contract = self.base / "contract.json"
        contract.write_text(json.dumps(self.contract))
        out = self.base / "links.md"
        cmd = [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts/delivery_manifest.py"),
               "--contract", str(contract), "--markdown-output", str(out)]
        p = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        before = out.read_bytes()
        p = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertEqual(out.read_bytes(), before)
        self.assertTrue(self.audio.is_file())


if __name__ == "__main__":
    unittest.main()
