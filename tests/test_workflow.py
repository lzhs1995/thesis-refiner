"""Synthetic receipts exercise acceptance; these are never live NLM evidence."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import workflow as w


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.docx = self.root / "original.docx"
        with zipfile.ZipFile(self.docx, "w") as z:
            z.writestr("word/document.xml", '<w:document xmlns:w="' + w.NS['w'] + '"><w:body><w:p><w:r><w:t>Observed effect 0.25</w:t></w:r></w:p><w:p><w:r><w:t>Final appendix section</w:t></w:r></w:p></w:body></w:document>')
        self.pdf = self.root / "final.pdf"
        self.pdf.write_bytes(b"%PDF-1.7\nsynthetic fixture")
        self.e = self.file("local", {"inspection": "synthetic fixture"})
        original = w.inventory(self.docx)
        dispositions = {i["id"]: {"action": "retain", "reason": "reviewed", "category": "empirical" if i["numeric_mentions"] else "nonempirical", "claim_ids": ["claim"], "review_evidence": self.e, "numeric_dispositions": ["claim"] * len(i["numeric_mentions"])} for i in original["items"]}
        self.state = {"schema_version": 1, "task_id": "fixture", "original": original, "dispositions": dispositions,
                      "nodes": [{"id": "result", "kind": "output", "depends_on": ["sample"], "artifacts": [self.e], "sample_fingerprint": "sample-a"},
                                {"id": "claim", "kind": "claim", "empirical_kind": "descriptive", "depends_on": ["result"], "artifacts": [self.e], "same_sample_as": ["result"], "sample_fingerprint": "sample-a", "verification": {"traceability": "unique_source", "full_reproduction": False},
                                 "lineage": {"data": ["data"], "cleaning": ["cleaning"], "variables": ["variables"], "sample": ["sample"], "output": ["result"]}},
                                {"id": "data", "kind": "data", "artifacts": [self.e]},
                                {"id": "cleaning", "kind": "cleaning", "depends_on": ["data"], "artifacts": [self.e]},
                                {"id": "variables", "kind": "variables", "depends_on": ["cleaning"], "artifacts": [self.e]},
                                {"id": "sample", "kind": "sample", "depends_on": ["variables"], "artifacts": [self.e]}],
                      "required_documents": ["main", "appendix"], "documents": {}}
        for name in self.state["required_documents"]:
            d = {"docx": w.ref(self.docx), "pdf": w.ref(self.pdf), "scope_ids": ["start", "last"], "source": {"id": name}, "gates": {}, "rounds": [], "has_zotero": False}
            d["source"]["receipt"] = self.file(name + "-source", {"mode": "real", "status": "READY", "source_id": name, "pdf_sha256": d["pdf"]["sha256"]})
            for gate, kind in {"native": "docx", "format": "docx", "visual": "pdf", "pdf_fonts": "pdf"}.items():
                d["gates"][gate] = self.file(name + gate, {"mode": "real", "status": "PASS", kind + "_sha256": d[kind]["sha256"]})
            d["gates"]["export"] = self.file(name + "export", {"mode": "real", "status": "PASS", "backend": "word_native", "docx_sha256": d["docx"]["sha256"], "pdf_sha256": d["pdf"]["sha256"]})
            for r in range(2):
                round_ = {"id": str(r), "mode": "real", "conversation_id": name + str(r), "pdf_sha256": d["pdf"]["sha256"], "source_id": name, "issues": [], "issue_census_evidence": self.e, "queries": []}
                for t in sorted(w.TOPICS):
                    key = name + str(r) + t
                    raw = self.file(key + "answer", {"answer": "Synthetic grounded response", "conversation_id": name + str(r), "citations": [{"id": "1", "source_id": name}]})
                    receipt = self.file(key + "receipt", {"mode": "real", "request_id": key, "status": "COMPLETE", "exit_code": 0, "answer_sha256": raw["sha256"], "document_sha256": d["pdf"]["sha256"], "source_id": name, "round_id": str(r), "conversation_id": name + str(r)})
                    round_["queries"].append({"request_id": key, "source_id": name, "raw_answer": raw, "receipt": receipt, "local_coverage_evidence": self.e,
                                              "coverage": [{"scope_id": s, "topic": t, "locator": s, "citation_ids": ["1"]} for s in d["scope_ids"]]})
                d["rounds"].append(round_)
            self.state["documents"][name] = d

    def file(self, name, value):
        p = self.root / (name + ".json")
        p.write_text(json.dumps(value))
        return w.ref(p)

    def test_complete_but_not_full_reproduction(self):
        result = w.acceptance(self.state)
        self.assertEqual(result["status"], "COMPLETE", result)
        self.assertFalse(result["evidence_chain"]["full_reproduction"])

    def test_original_census_cannot_omit_untouched_appendix(self):
        self.state["original"]["items"].pop()
        self.assertFalse(w.audit_chain(self.state)["pass"])

    def test_sample_mirror_and_difference_claims(self):
        for change, code in [({"sample_fingerprint": "other"}, "SAMPLE_MISMATCH"), ({"claims_independent": True, "mirror_of": "spouse"}, "MIRROR_IS_NOT_INDEPENDENT"), ({"claims_difference": True}, "ENDPOINT_TEST_IS_NOT_CONTRAST")]:
            with self.subTest(code=code):
                state = copy.deepcopy(self.state)
                state["nodes"][1].update(change)
                self.assertIn(code, str(w.audit_chain(state)["errors"]))

    def test_removed_figure_requires_retained_evidence(self):
        d = next(iter(self.state["dispositions"].values()))
        d["action"] = "delete"
        self.assertFalse(w.audit_chain(self.state)["pass"])

    def test_last_scope_and_nonempty_answer_required(self):
        doc = self.state["documents"]["appendix"]
        doc["rounds"][-1]["queries"][-1]["coverage"].pop()
        self.assertFalse(w.audit_document(doc)["pass"])
        raw = self.file("control-frame", {"status": 200, "conversation_id": doc["rounds"][-1]["conversation_id"]})
        query = doc["rounds"][-1]["queries"][0]
        query["raw_answer"] = raw
        query["receipt"] = self.file("control-receipt", {"mode": "real", "status": "COMPLETE", "exit_code": 0, "request_id": query["request_id"], "answer_sha256": raw["sha256"], "document_sha256": doc["pdf"]["sha256"], "source_id": doc["source"]["id"], "round_id": doc["rounds"][-1]["id"], "conversation_id": doc["rounds"][-1]["conversation_id"]})
        self.assertIn("EMPTY_CONTROL_FRAME", str(w.audit_document(doc)["errors"]))

    def test_repeated_issue_is_not_a_termination_rule(self):
        doc = self.state["documents"]["main"]
        for r in doc["rounds"]:
            r["issues"] = [{"id": "same", "original_text": "mismatch", "locator": "p1", "disposition": "confirmed", "local_evidence": self.e}]
        doc["rounds"].append(copy.deepcopy(doc["rounds"][-1]))
        self.assertFalse(w.audit_document(doc)["pass"])

    def test_false_positive_retains_original_answer_and_passes(self):
        self.state["documents"]["main"]["rounds"][-1]["issues"] = [{"id": "caption", "original_text": "caption missing", "locator": "p40", "disposition": "false_positive", "local_evidence": self.e}]
        self.assertEqual(w.acceptance(self.state)["status"], "COMPLETE")

    def test_new_pdf_invalidates_only_changed_document(self):
        new = self.root / "successor.pdf"
        new.write_bytes(b"%PDF-1.7\nnew fixture")
        self.state["documents"]["main"]["pdf"] = w.ref(new)
        result = w.acceptance(self.state)
        self.assertFalse(result["documents"]["main"]["pass"])
        self.assertTrue(result["documents"]["appendix"]["pass"])

    def test_dependency_impact_and_cycle(self):
        self.assertEqual(w.affected_nodes(self.state["nodes"], ["result"]), ["claim", "result"])
        self.state["nodes"][0]["depends_on"] = ["claim"]
        self.assertFalse(w.audit_chain(self.state)["pass"])

    def test_simulation_and_unproven_merged_strategy_refused(self):
        doc = self.state["documents"]["main"]
        doc["query_strategy"] = "merged3"
        self.assertFalse(w.audit_document(doc)["pass"])
        doc["query_strategy"] = "six"
        doc["rounds"][-1]["mode"] = "simulation"
        self.assertFalse(w.audit_document(doc)["pass"])

    def test_real_cli_and_hook_positive_negative(self):
        checkpoint = self.root / "checkpoint.json"
        checkpoint.write_text(json.dumps(self.state))
        script = Path(w.__file__)
        proc = subprocess.run([sys.executable, str(script), "acceptance", "--input", str(checkpoint)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        hook = script.parents[1] / "hooks/a5-termination-auditor.js"
        payload = json.dumps({"workflow_checkpoint": str(checkpoint)})
        self.assertEqual(subprocess.run(["node", str(hook)], input=payload, capture_output=True, text=True).returncode, 0)
        self.state["documents"]["appendix"]["rounds"].pop()
        checkpoint.write_text(json.dumps(self.state))
        self.assertEqual(subprocess.run(["node", str(hook)], input=payload, capture_output=True, text=True).returncode, 2)

    def partition_document(self):
        doc = copy.deepcopy(self.state["documents"]["main"])
        doc["page_count"] = 2
        export = json.loads(Path(doc["gates"]["export"]["path"]).read_text())
        doc["gates"]["export"] = self.file("partition-export", {**export, "page_count": 2})
        doc["sources"] = []
        for page, scope in enumerate(doc["scope_ids"], 1):
            child = self.root / ("child-" + str(page) + ".pdf")
            child.write_bytes(b"%PDF-1.7\nsynthetic page " + str(page).encode())
            source = {"id": "source-" + str(page), "pdf": w.ref(child), "pages": [page], "scope_ids": [scope]}
            source["receipt"] = self.file("ready-" + str(page), {"mode": "real", "status": "READY", "source_id": source["id"], "pdf_sha256": source["pdf"]["sha256"]})
            source["equivalence_receipt"] = self.file("equiv-" + str(page), {"mode": "real", "status": "PASS", "text_and_visual_equivalent": True,
                "parent_pdf_sha256": doc["pdf"]["sha256"], "child_pdf_sha256": source["pdf"]["sha256"], "pages": [page], "parent_page_count": 2, "child_page_count": 1})
            doc["sources"].append(source)
        for round_ in doc["rounds"]:
            for query in round_["queries"]:
                conversation = query["request_id"] + "-conversation"
                query["conversation_id"] = conversation
                query["source_ids"] = [s["id"] for s in doc["sources"]]
                query["raw_answer"] = self.file(query["request_id"] + "-partition-answer", {"answer": "Synthetic partition review", "conversation_id": conversation,
                    "citations": [{"id": str(i), "source_id": s["id"]} for i, s in enumerate(doc["sources"], 1)]})
                receipt = json.loads(Path(query["receipt"]["path"]).read_text())
                receipt.update(source_ids=query["source_ids"], conversation_id=conversation, answer_sha256=query["raw_answer"]["sha256"])
                query["receipt"] = self.file(query["request_id"] + "-partition-receipt", receipt)
                for i, coverage in enumerate(query["coverage"], 1):
                    coverage["citation_ids"] = [str(i)]
        return doc

    def test_partition_families_with_independent_conversations(self):
        doc = self.partition_document()
        self.assertTrue(w.audit_document(doc)["pass"], w.audit_document(doc))
        doc["rounds"][-1]["queries"][0]["conversation_id"] = doc["rounds"][0]["queries"][0]["conversation_id"]
        self.assertIn("NOT_INDEPENDENT", str(w.audit_document(doc)))

    def test_partition_map_cannot_exceed_mother_even_with_full_source(self):
        doc = self.partition_document()
        doc["sources"].append(doc["source"])
        self.assertTrue(w.audit_document(doc)["pass"], w.audit_document(doc))
        source = doc["sources"][1]
        for pages in ([3], [2, 2], [2, 1]):
            with self.subTest(pages=pages):
                source["pages"] = pages
                mapping = json.loads(Path(source["equivalence_receipt"]["path"]).read_text())
                source["equivalence_receipt"] = self.file("bad-equivalence", {**mapping, "pages": pages})
                self.assertIn("PARTITION_PAGE_MAP_INVALID", str(w.audit_document(doc)))

    def test_partition_count_and_cited_scope_must_be_proven(self):
        doc = self.partition_document()
        source = doc["sources"][0]
        mapping = json.loads(Path(source["equivalence_receipt"]["path"]).read_text())
        source["equivalence_receipt"] = self.file("wrong-count", {**mapping, "child_page_count": 2})
        self.assertIn("PAGE_COUNTS_NOT_PROVEN", str(w.audit_document(doc)))
        doc = self.partition_document()
        doc["rounds"][-1]["queries"][0]["coverage"][0]["citation_ids"] = ["2"]
        self.assertIn("CITES_WRONG_PARTITION", str(w.audit_document(doc)))
        doc = self.partition_document()
        doc["page_count"] = 3
        self.assertIn("PAGE_COUNT_NOT_BOUND", str(w.audit_document(doc)))

    def test_model_health_limitations_propagate_to_each_dependent_claim(self):
        self.state["nodes"][0]["depends_on"] = ["model"]
        self.state["nodes"][1]["empirical_kind"] = "estimated"
        self.state["nodes"][1]["lineage"]["model"] = ["model"]
        self.state["nodes"].append({"id": "model", "kind": "model", "depends_on": ["sample"], "artifacts": [self.e], "model_health": {
            "normal_termination": True, "standard_errors_valid": False, "draws_requested": 1000, "draws_saved": 850, "replicate_convergence": "unknown"}})
        self.assertIn("PARTIAL_NOT_PROPAGATED", str(w.audit_chain(self.state)))
        claim = self.state["nodes"][1]
        claim.update(accepted_partial=True, provenance_gap="SE unresolved; limited descriptive interpretation", model_limitations={"model": "850/1000 saved; convergence unknown"})
        result = w.audit_chain(self.state)
        self.assertTrue(result["pass"], result)
        self.assertEqual(result["evidence_chain"], "CLOSED_WITH_PARTIALS")
        claim["verification"]["full_reproduction"] = True
        self.assertFalse(w.audit_chain(self.state)["pass"])

    def test_output_file_alone_does_not_close_empirical_lineage(self):
        claim = self.state["nodes"][1]
        del claim["lineage"]["cleaning"]
        self.assertIn("LINEAGE_INCOMPLETE", str(w.audit_chain(self.state)))
        claim.update(accepted_partial=True, lineage_gaps={"cleaning": {
            "accepted": True, "reason": "Historical cleaning unavailable; only compatible output evidence remains", "evidence": self.e}})
        result = w.audit_chain(self.state)
        self.assertTrue(result["pass"], result)
        self.assertEqual(result["evidence_chain"], "CLOSED_WITH_PARTIALS")
        self.state["original"]["items"][0]["numeric_mentions"] = []
        self.assertIn("CENSUS_INCOMPLETE_OR_CHANGED", str(w.audit_chain(self.state)))


if __name__ == "__main__":
    unittest.main()
