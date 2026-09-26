import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from evidence_refs import checked_bytes, same_identity
from delivery_audit import checked_ref


class EvidenceReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "receipt.json"
        self.path.write_bytes(b'{"status":"synthetic"}\n')
        self.ref = {"path": str(self.path), "sha256": hashlib.sha256(self.path.read_bytes()).hexdigest()}

    def test_extra_size_preserves_verified_identity(self):
        richer = {**self.ref, "bytes": self.path.stat().st_size}
        self.assertTrue(same_identity(richer, self.ref))
        self.assertEqual(checked_ref(richer), self.path)

    def test_same_bytes_at_a_different_path_are_not_same_identity(self):
        other = self.path.with_name("copy.json")
        other.write_bytes(self.path.read_bytes())
        self.assertFalse(same_identity(self.ref, {**self.ref, "path": str(other)}))

    def test_bad_size_cannot_be_discarded_as_metadata(self):
        for size in (True, None, -1, "23", self.path.stat().st_size + 1):
            for check in (checked_ref, checked_bytes):
                with self.subTest(size=size, check=check.__name__), self.assertRaises(ValueError):
                    check({**self.ref, "bytes": size})

    def test_same_size_changed_content_is_rejected(self):
        self.path.write_bytes(self.path.read_bytes().replace(b"synthetic", b"different"))
        with self.assertRaisesRegex(ValueError, "HASH_MISMATCH"):
            same_identity(self.ref, self.ref)


if __name__ == "__main__":
    unittest.main()
