"""Measured CLI envelopes; no account, browser or network is used."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from nlm_contracts import cli_argv, normalized_result


class CLIContracts(unittest.TestCase):
    def test_native_list_empty_and_nonempty_arrays_and_wrappers(self):
        for rows in ([], [{"id": "notebook", "title": "Synthetic", "source_count": 1}]):
            for data in (rows, {"notebooks": rows}, {"value": rows}):
                self.assertEqual(normalized_result("list", data)["notebooks"], rows)
        for data in ([{"error": "failed"}], ["notebook"], {"status": "ERROR", "notebooks": []}, {}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                normalized_result("list", data)
        with self.assertRaises(ValueError):
            normalized_result("query", [])

    def test_fulltext_requires_matching_source_and_optional_notebook(self):
        text = "中文长文 " * 2000
        valid = {"source_id": "source", "notebook_id": "notebook", "content": text}
        self.assertEqual(normalized_result("source_fulltext", valid, source_id="source", notebook_id="notebook")["content"], text)
        for change in ({"source_id": "other"}, {"source_id": None}, {"notebook_id": "other"}, {"content": ""}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                normalized_result("source_fulltext", {**valid, **change}, source_id="source", notebook_id="notebook")

    def test_upload_errors_and_processing_are_distinct_from_ready(self):
        result = normalized_result("source_add", {"source": {"id": "s", "status": "processing"}})
        self.assertFalse(result["ready"])
        self.assertTrue(normalized_result("source_add", {"source_id": "s", "status": "READY"})["ready"])
        for data in ({"status": "ERROR", "source_id": "s"}, {"source": {"id": "s", "ok": False}}):
            with self.assertRaises(ValueError):
                normalized_result("source_add", data)

    def test_exact_provider_argv_and_no_destructive_fresh_conversation(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp).resolve() / "file with 中文.pdf"
            pdf.write_bytes(b"%PDF-1.7\nsynthetic argv fixture")
            self.assertEqual(cli_argv("notebooklm", "source_add", notebook_id="n", file=pdf),
                             ["notebooklm", "source", "add", str(pdf), "-n", "n", "--type", "file", "--json"])
            self.assertEqual(cli_argv("nlm", "source_add", notebook_id="n", file=pdf),
                             ["nlm", "source", "add", "n", "--file", str(pdf), "--wait", "--json"])
            with self.assertRaises(FileNotFoundError):
                cli_argv("notebooklm", "source_add", notebook_id="n", file=pdf.parent / "missing.pdf")
        self.assertEqual(cli_argv("nlm", "source_fulltext", notebook_id="n", source_ids=["s"]),
                         ["nlm", "content", "source", "s", "--json"])
        self.assertEqual(cli_argv("notebooklm", "source_fulltext", notebook_id="n", source_ids=["s"]),
                         ["notebooklm", "source", "fulltext", "s", "-n", "n", "--json"])
        with self.assertRaisesRegex(ValueError, "NONDESTRUCTIVE"):
            cli_argv("notebooklm", "query", notebook_id="n", prompt="review", source_ids=["s"])
        with self.assertRaisesRegex(ValueError, "NOT_VERIFIED"):
            cli_argv("notebooklm", "copy", notebook_id="n")


if __name__ == "__main__":
    unittest.main()
