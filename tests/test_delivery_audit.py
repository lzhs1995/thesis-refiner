"""Synthetic OOXML and receipts only; no fixture is live review/native evidence."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from xml.sax.saxutils import escape
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import delivery_audit as d


def aparas(values):
    return "".join("<a:p><a:r><a:t>" + escape(v) + "</a:t></a:r></a:p>" for v in values)


def shape(values, body=False):
    ph = '<p:ph type="body"/>' if body else ""
    return "<p:sp><p:nvSpPr><p:nvPr>" + ph + "</p:nvPr></p:nvSpPr><p:txBody>" + aparas(values) + "</p:txBody></p:sp>"


def rels(rows):
    return '<Relationships xmlns="' + d.REL + '">' + "".join(
        '<Relationship Id="%s" Type="%s/%s" Target="%s"/>' % (rid, d.NS["r"], kind, target)
        for rid, kind, target in rows) + "</Relationships>"


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.counter = 0
        self.image = b"synthetic image payload"
        self.ns = " ".join('xmlns:%s="%s"' % (k, v) for k, v in d.NS.items())
        self.e = self.file("evidence", {"fixture_only": True, "explanation": "not live evidence"})
        self.source = self.file("source", {"chapter": "synthetic content"})
        self.master = {"schema_version": 1, "task_id": "fixture", "speaker_prefix": ["Speaker script"],
                       "speaker_auxiliary": {"word/footer1.xml": ["Declared footer"]}, "slides": [
            {"id": "a", "status": "active", "blocks": [
                {"kind": "text", "paragraphs": ["First", "Result 0.25"]},
                {"kind": "table", "rows": [[["Estimate"], ["0.25"]]]},
                {"kind": "image", "sha256": hashlib.sha256(self.image).hexdigest()}],
             "speech": ["I describe the result.", "The limit remains."], "speaker_heading": "Slide 1",
             "sources": [{"id": "file-a", "locator": "table 1"}]},
            {"id": "old", "status": "archived", "blocks": [{"kind": "text", "paragraphs": ["OLD MANUSCRIPT"]}]},
            {"id": "b", "status": "active", "blocks": [{"kind": "text", "paragraphs": ["Second"]}],
             "speech": ["I conclude."], "speaker_heading": "Slide 2",
             "sources": [{"id": "file-a", "locator": "section 2"}]}]}
        master_ref = self.file("master", self.master)
        self.pptx = self.root / "slides.pptx"
        self.speaker = self.root / "speaker.docx"
        self.write_pptx()
        self.write_speaker()
        self.contract = {"schema_version": 1, "contract_kind": "derivative_delivery", "task_id": "fixture",
                         "binding_mode": "chapter", "master": master_ref,
                         "sources": [{"id": "file-a", "file": self.source}],
                         "required_review_rounds": 2, "artifacts": {}}
        for name, path, backend in (("pptx", self.pptx, "powerpoint_native"), ("speaker_docx", self.speaker, "word_native")):
            pdf = self.root / (name + ".pdf")
            pdf.write_bytes(b"%PDF-1.7\nsynthetic fixture " + name.encode())
            row = {"file": self.ref(path), "pdf": self.ref(pdf)}
            row["native_receipt"] = self.receipt(name + "-native", "native_export", backend=backend,
                input=row["file"], output=row["pdf"], page_count=2, operation_status="COMPLETE",
                resource_status="RELEASED", release_evidence=self.e)
            row["visual_receipt"] = self.receipt(name + "-visual", "visual_review", pdf=row["pdf"], page_count=2,
                pages=[{"page": i, "status": "PASS", "method": "inspected", "evidence": [self.e]} for i in (1, 2)])
            self.contract["artifacts"][name] = row
        self.contract["review_receipt"] = self.receipt("review", "content_review", master=master_ref,
            sources=self.contract["sources"], rounds=[{"id": "R" + str(i), "topics": sorted(d.TOPICS),
                "new_required_changes": 0, "unresolved_required_changes": 0, "content_scope_gaps": [],
                "evidence": [self.e]} for i in (1, 2)])

    def ref(self, path):
        return {"path": str(path), "sha256": d.sha(path)}

    def file(self, name, data):
        self.counter += 1
        path = self.root / (name + str(self.counter) + ".json")
        path.write_text(json.dumps(data), encoding="utf-8")
        return self.ref(path)

    def receipt(self, name, kind, **kwargs):
        return self.file(name, {"receipt_schema": "delivery-receipt-v1", "kind": kind, "task_id": "fixture",
            "mode": "real", "status": "PASS", "producer": "synthetic fixture producer",
            "created_at": "2026-01-01T00:00:00Z", "evidence": [self.e], **kwargs})

    def mutate(self, ref, **kwargs):
        data = json.loads(Path(ref["path"]).read_text())
        data.update(kwargs)
        return self.file("mutated", data)

    def write_pptx(self, swap=False, archived=False, cell="0.25", note=None, prefix="p"):
        first = shape(["First", "Result 0.25"]) + '<p:graphicFrame><a:graphic><a:graphicData><a:tbl><a:tr>' + "".join(
            "<a:tc><a:txBody>" + aparas([v]) + "</a:txBody></a:tc>" for v in ("Estimate", cell)) + '</a:tr></a:tbl></a:graphicData></a:graphic></p:graphicFrame><p:pic><p:blipFill><a:blip r:embed="image"/></p:blipFill></p:pic>'
        second = shape(["OLD MANUSCRIPT" if archived else "Second"])
        def xml(content):
            value = '<p:sld ' + self.ns + '><p:cSld><p:spTree>' + content + '</p:spTree></p:cSld></p:sld>'
            return value.replace("<p:", "<" + prefix + ":").replace("</p:", "</" + prefix + ":").replace("xmlns:p=", "xmlns:" + prefix + "=")
        with zipfile.ZipFile(self.pptx, "w") as z:
            ids = ["r1", "r2"] if swap else ["r2", "r1"]
            z.writestr("ppt/presentation.xml", '<p:presentation ' + self.ns + '><p:sldIdLst>' + "".join('<p:sldId r:id="' + rid + '"/>' for rid in ids) + '</p:sldIdLst></p:presentation>')
            z.writestr("ppt/_rels/presentation.xml.rels", rels([("r1", "slide", "slides/slide1.xml"), ("r2", "slide", "slides/slide9.xml")]))
            z.writestr("ppt/slides/slide9.xml", xml(first))
            z.writestr("ppt/slides/slide1.xml", xml(second))
            for num, speech in ((9, note or ["I describe the result.", "The limit remains."]), (1, ["I conclude."])):
                z.writestr("ppt/slides/_rels/slide%d.xml.rels" % num, rels([("notes", "notesSlide", "../notesSlides/notes%d.xml" % num), ("image", "image", "../media/image.png")]))
                z.writestr("ppt/notesSlides/notes%d.xml" % num, '<p:notes ' + self.ns + '><p:cSld><p:spTree>' + shape(speech, True) + '</p:spTree></p:cSld></p:notes>')
            z.writestr("ppt/media/image.png", self.image)

    def write_speaker(self, extra=None):
        paragraphs = ["Speaker script", "Slide 1", "I describe the result.", "The limit remains.", "Slide 2", "I conclude."]
        if extra:
            paragraphs.append(extra)
        text = "".join("<w:p><w:r><w:t>" + escape(v) + "</w:t></w:r></w:p>" for v in paragraphs)
        with zipfile.ZipFile(self.speaker, "w") as z:
            z.writestr("word/document.xml", '<w:document ' + self.ns + '><w:body>' + text + '</w:body></w:document>')
            z.writestr("word/footer1.xml", '<w:ftr ' + self.ns + '><w:p><w:r><w:t>Declared footer</w:t></w:r></w:p></w:ftr>')

    def assertReject(self, contract=None, code=None):
        result = d.audit(contract or self.contract)
        self.assertFalse(result["pass"], result)
        if code:
            self.assertIn(code, str(result["errors"]))

    def test_chapter_contract_passes_without_final_thesis_gate(self):
        result = d.audit(self.contract)
        self.assertEqual(result["status"], "INTEGRITY_VERIFIED", result)
        self.assertEqual((result["active_slides"], result["archived_slides"]), (2, 1))

    def test_relationship_order_not_filename_and_namespace_prefix_invariant(self):
        self.write_pptx(prefix="v")
        actual = d.read_pptx(self.pptx)
        self.assertEqual(actual[0]["blocks"][0]["paragraphs"][0], "First")
        self.assertEqual(actual[1]["blocks"][0]["paragraphs"][0], "Second")

    def test_verified_identical_delivery_copies_reuse_original_receipts(self):
        copied_pptx = self.root / "delivery-copy.pptx"
        copied_source = self.root / "source-copy.json"
        copied_pptx.write_bytes(self.pptx.read_bytes())
        copied_source.write_bytes(Path(self.source["path"]).read_bytes())
        self.contract["artifacts"]["pptx"]["file"] = self.ref(copied_pptx)
        self.contract["sources"][0]["file"] = self.ref(copied_source)
        self.assertTrue(d.audit(self.contract)["pass"], d.audit(self.contract))

    def test_swap_table_notes_and_archive_reintroduction_fail_after_repin(self):
        for kwargs in ({"swap": True}, {"cell": "0.26"}, {"note": ["Wrong speech"]}, {"archived": True}):
            with self.subTest(kwargs=kwargs):
                self.write_pptx(**kwargs)
                c = copy.deepcopy(self.contract)
                c["artifacts"]["pptx"]["file"] = self.ref(self.pptx)
                self.assertReject(c, "ORDER_CONTENT_TABLE_IMAGE_OR_NOTES_DRIFT")

    def test_speaker_exact_heading_and_speech(self):
        self.write_speaker("OLD MANUSCRIPT")
        self.contract["artifacts"]["speaker_docx"]["file"] = self.ref(self.speaker)
        self.assertReject(code="SPEECH_HEADING_OR_AUXILIARY_DRIFT")

    def test_master_archive_is_not_an_export_source(self):
        old = self.master["slides"][1]
        old["blocks"][0]["paragraphs"] = ["Anything archived is outside current export"]
        # Extraction is controlled by active entries only, independently of old text.
        active = [{"blocks": s["blocks"], "speech": s["speech"]} for s in self.master["slides"] if s["status"] == "active"]
        self.assertEqual(d.read_pptx(self.pptx), active)

    def test_missing_label_only_relative_and_drifted_source_fail(self):
        for value in ("semantic label only", {"path": "source.json", "sha256": "0" * 64}, {"path": str(self.root / "missing"), "sha256": "0" * 64}):
            c = copy.deepcopy(self.contract)
            c["sources"][0]["file"] = value
            self.assertReject(c)
        Path(self.source["path"]).write_text("changed")
        self.assertReject(code="FILE_DRIFT")

    def test_boolean_counts_and_missing_counts_fail(self):
        for count in (True, "2", None, 0):
            c = copy.deepcopy(self.contract)
            item = c["artifacts"]["pptx"]
            item["native_receipt"] = self.mutate(item["native_receipt"], page_count=count)
            self.assertReject(c, "INTEGER_REQUIRED")
        c = copy.deepcopy(self.contract)
        c["required_review_rounds"] = True
        self.assertReject(c, "INTEGER_REQUIRED")

    def test_old_unbound_wrong_task_and_unreleased_receipts_fail(self):
        for changes in ({"receipt_schema": None}, {"task_id": "old-task"}, {"resource_status": "PENDING"}, {"mode": "simulation"}):
            c = copy.deepcopy(self.contract)
            item = c["artifacts"]["pptx"]
            item["native_receipt"] = self.mutate(item["native_receipt"], **changes)
            self.assertReject(c)

    def test_stale_pdf_and_missing_visual_page_fail(self):
        c = copy.deepcopy(self.contract)
        item = c["artifacts"]["pptx"]
        old = self.file("wrong-pdf", {"wrong": True})
        item["native_receipt"] = self.mutate(item["native_receipt"], output=old)
        self.assertReject(c, "STALE_OR_WRONG_BINDING")
        item["native_receipt"] = self.contract["artifacts"]["pptx"]["native_receipt"]
        item["visual_receipt"] = self.mutate(item["visual_receipt"], pages=[])
        self.assertReject(c, "PAGE_COVERAGE_REQUIRED")

    def test_pdf_label_or_hash_alone_is_not_pdf_header(self):
        bad = self.file("not-pdf", {"not": "a PDF"})
        self.contract["artifacts"]["pptx"]["pdf"] = bad
        self.assertReject(code="PDF:HEADER_REQUIRED")

    def with_boundary(self):
        master = copy.deepcopy(self.master)
        master["boundaries"] = [{"id": "limit", "source": {"id": "file-a", "locator": "table 1"},
            "estimand": "declared association", "time_window": "declared window", "unit": "declared unit",
            "risk_set": "declared denominator", "tested_status": "not_tested", "interpretation_limit": "retain limitation",
            "applies_to": [{"slide_id": "a", "blocks_excerpts": ["Result 0.25"], "speech_excerpts": ["The limit remains."]}]}]
        c = copy.deepcopy(self.contract)
        c["master"] = self.file("bounded-master", master)
        c["review_receipt"] = self.mutate(c["review_receipt"], master=c["master"], boundary_ids=["limit"])
        return c, master

    def test_optional_declared_boundaries_preserve_display_speech_and_source(self):
        c, master = self.with_boundary()
        self.assertTrue(d.audit(c)["pass"], d.audit(c))
        for changed in ("denominator 10", "period 2019-2020", "not performed"):
            broken = copy.deepcopy(master)
            broken["boundaries"][0]["applies_to"][0]["speech_excerpts"] = [changed]
            c["master"] = self.file("missing-boundary", broken)
            self.assertReject(c, "BOUNDARY:EXCERPT_MISSING")
        c, master = self.with_boundary()
        c["review_receipt"] = self.mutate(c["review_receipt"], boundary_ids=[])
        self.assertReject(c, "REVIEW_BOUNDARY_IDS")
        c, master = self.with_boundary()
        master["boundaries"][0]["risk_set"] = "changed denominator"
        c["master"] = self.file("drifted-boundary", master)
        self.assertReject(c, "REVIEW_MASTER:STALE_OR_WRONG_BINDING")

    def test_review_round_requires_six_topics_actual_evidence_and_zero_open_changes(self):
        for mutation in ({"topics": ["theory_methods"]}, {"content_scope_gaps": ["figure"]}, {"new_required_changes": True}, {"evidence": []}):
            review = json.loads(Path(self.contract["review_receipt"]["path"]).read_text())
            review["rounds"][-1].update(mutation)
            c = copy.deepcopy(self.contract)
            c["review_receipt"] = self.file("review-bad", review)
            self.assertReject(c)

    def final_contract(self):
        c = copy.deepcopy(self.contract)
        c["binding_mode"] = "final_thesis"
        final = self.file("final-thesis", {"final": "synthetic"})
        freeze = self.receipt("freeze", "final_thesis_freeze", file=final)
        c["final_thesis"] = {"file": final, "freeze_receipt": freeze}
        mappings = [{"slide_id": s["id"], "source_id": src["id"], "source_locator": src["locator"],
                     "final_locator": "final PDF page " + str(i), "disposition": "equivalent", "evidence": [self.e]}
                    for i, s in enumerate(self.master["slides"], 1) if s["status"] == "active" for src in s["sources"]]
        c["mapping_receipt"] = self.receipt("mapping", "final_source_mapping", master=c["master"],
            final_thesis=final, freeze_receipt=freeze, sources=c["sources"], mappings=mappings)
        return c

    def test_final_binding_requires_real_pinned_freeze_and_complete_mapping(self):
        c = self.final_contract()
        self.assertTrue(d.audit(c)["pass"], d.audit(c))
        mapping = json.loads(Path(c["mapping_receipt"]["path"]).read_text())
        mapping["mappings"].pop()
        c["mapping_receipt"] = self.file("missing-locator", mapping)
        self.assertReject(c, "INCOMPLETE_SOURCE_COVERAGE")
        c = self.final_contract()
        del c["final_thesis"]["freeze_receipt"]
        self.assertReject(c)

    def test_cli_positive_negative_and_unchanged_inputs(self):
        path = self.root / "contract.json"
        path.write_text(json.dumps(self.contract))
        before = {str(p): d.sha(p) for p in self.root.iterdir() if p.is_file()}
        command = [sys.executable, "-B", d.__file__, "--input", str(path)]
        proc = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["status"], "INTEGRITY_VERIFIED")
        after = {str(p): d.sha(p) for p in self.root.iterdir() if p.is_file()}
        self.assertEqual(before, after)
        self.contract["required_review_rounds"] = True
        path.write_text(json.dumps(self.contract))
        proc = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        # Report mode must not clobber an existing input or evidence file.
        digest = d.sha(path)
        proc = subprocess.run(command + ["--output", str(path)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(d.sha(path), digest)

    def test_duplicate_json_keys_fail_cli(self):
        path = self.root / "duplicate.json"
        path.write_text('{"task_id":"a","task_id":"b"}')
        proc = subprocess.run([sys.executable, "-B", d.__file__, "--input", str(path)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("DUPLICATE_KEY", proc.stdout)


if __name__ == "__main__":
    unittest.main()
