"""Synthetic RPC/CLI contract tests; no browser, source upload or network."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from nlm_fulltext import normalize_rpc_fulltext
from nlm_contracts import normalized_result


class FulltextProvenance(unittest.TestCase):
    def setUp(self):
        self.content = "中文全文\n\nAppendix end"
        self.cli = {"content": self.content, "title": "Synthetic.pdf", "source_type": "pdf",
                    "url": None, "char_count": len(self.content)}
        self.payload = [[["server-source"], "Synthetic.pdf", []], None, None,
                        [[[0, 4, [["中文全文", ["Appendix end"]]]]]]]

    def response(self, payload=None, copies=1, rpc="hizoJc"):
        frame = ["wrb.fr", rpc, json.dumps(self.payload if payload is None else payload, ensure_ascii=False)]
        body = json.dumps([frame] * copies, ensure_ascii=False)
        return (")]}'\n\n" + str(len(body.encode())) + "\n" + body + "\n").encode()

    def normalize(self, *, cli=None, payload=None, expected="server-source", response=None, digest=None):
        raw = self.response(payload) if response is None else response
        return normalize_rpc_fulltext(self.cli if cli is None else cli, raw,
             response_sha256=digest or hashlib.sha256(raw).hexdigest(), expected_source_id=expected)

    def test_omitted_id_is_recovered_from_server_without_mutating_cli(self):
        before = copy.deepcopy(self.cli)
        value = self.normalize()
        self.assertEqual(value["source_id"], "server-source")
        self.assertNotIn("notebook_id", value)
        self.assertEqual(value["identity_provenance"]["notebook_identity"], "request_binding_only")
        self.assertFalse(value["identity_provenance"]["cli_source_id_present"])
        self.assertEqual(self.cli, before)
        self.assertEqual(normalized_result("source_fulltext", value, source_id="server-source")["content"], self.content)

    def test_matching_existing_source_id_is_preserved(self):
        self.assertTrue(self.normalize(cli={**self.cli, "source_id": "server-source"})["identity_provenance"]["cli_source_id_present"])

    def test_request_id_cannot_replace_wrong_server_id(self):
        with self.assertRaisesRegex(ValueError, "RESPONSE_SOURCE_MISMATCH"):
            self.normalize(expected="requested-other")

    def test_cli_cannot_replace_server_id(self):
        for key in ("id", "source_id"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "CLI_AND_SERVER_SOURCE_MISMATCH"):
                self.normalize(cli={**self.cli, key: "forged"})

    def test_hash_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "HASH_MISMATCH"):
            self.normalize(digest="0" * 64)

    def test_missing_and_duplicate_rpc_frames_are_rejected(self):
        for raw in (self.response(copies=0), self.response(copies=2), self.response(rpc="another-rpc"), b"200"):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, "ONE_FULLTEXT_RPC_RESPONSE_REQUIRED"):
                self.normalize(response=raw)

    def test_missing_server_identity_is_rejected(self):
        for ids in ([], [None], [""], ["one", "two"]):
            payload = copy.deepcopy(self.payload)
            payload[0][0] = ids
            with self.subTest(ids=ids), self.assertRaisesRegex(ValueError, "SERVER_SOURCE_ID_MISSING"):
                self.normalize(payload=payload)

    def test_text_and_title_are_bound_to_same_server_response(self):
        for change, message in (({"content": "Truncated"}, "FULLTEXT_MISMATCH"),
                                ({"title": "Other.pdf"}, "TITLE_MISMATCH"),
                                ({"char_count": 1}, "CHARACTER_COUNT_MISMATCH"),
                                ({"char_count": True}, "CHARACTER_COUNT_MISMATCH")):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                self.normalize(cli={**self.cli, **change})

    def test_empty_text_and_remote_error_stay_failures(self):
        payload = copy.deepcopy(self.payload)
        payload[3] = [[]]
        with self.assertRaisesRegex(ValueError, "FULLTEXT_MISMATCH"):
            self.normalize(payload=payload)
        with self.assertRaisesRegex(ValueError, "REMOTE_ERROR"):
            self.normalize(cli={**self.cli, "status": "ERROR"})

    def test_existing_strict_gate_still_rejects_unproven_cli_output(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_ID_MISSING"):
            normalized_result("source_fulltext", self.cli, source_id="server-source")


if __name__ == "__main__":
    unittest.main()
