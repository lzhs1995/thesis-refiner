#!/usr/bin/env python3
"""Offline derivative integrity checks; does not perform native/visual/NLM review."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
TOPICS = {"theory_methods", "data_figures", "structure", "language", "citations", "format"}
LIMITS = ["Checks evidence bindings and OOXML content, not the truth of receipt assertions.",
          "Does not run NLM, native Office, PDF rendering, visual inspection or semantic review.",
          "PDF page counts and graphical meaning remain external native/visual assertions."]


class AuditError(ValueError):
    pass


def need(condition, code):
    if not condition:
        raise AuditError(code)


def object_(value, label):
    need(isinstance(value, dict), label + ":OBJECT_REQUIRED")
    return value


def string(value, label):
    need(isinstance(value, str) and bool(value.strip()), label + ":STRING_REQUIRED")
    return value


def strings(value, label, nonempty=False):
    need(isinstance(value, list) and (not nonempty or bool(value))
         and all(isinstance(v, str) for v in value), label + ":STRINGS_REQUIRED")
    return value


def integer(value, label, minimum=0):
    need(type(value) is int and value >= minimum, label + ":INTEGER_REQUIRED")
    return value


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def checked_ref(value):
    object_(value, "REF")
    need({"path", "sha256"} <= set(value) <= {"path", "sha256", "bytes"}, "REF:PATH_AND_SHA_REQUIRED")
    path = Path(string(value.get("path"), "REF_PATH"))
    digest = value.get("sha256")
    need(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), "REF:INVALID_SHA256")
    need(path.is_absolute() and path.is_file(), "REF:MISSING_OR_RELATIVE_PATH")
    need(sha(path) == digest, "REF:FILE_DRIFT:" + str(path))
    if "bytes" in value:
        need(integer(value["bytes"], "REF_BYTES") == path.stat().st_size, "REF:SIZE_MISMATCH")
    return path


def json_file(path):
    def unique(pairs):
        data = {}
        for key, value in pairs:
            need(key not in data, "JSON:DUPLICATE_KEY:" + key)
            data[key] = value
        return data
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique)


def evidence(value):
    need(isinstance(value, list) and bool(value), "RECEIPT:EVIDENCE_REQUIRED")
    for item in value:
        checked_ref(item)


def receipt(ref, task, kind):
    row = object_(json_file(checked_ref(ref)), "RECEIPT")
    need(row.get("receipt_schema") == "delivery-receipt-v1"
         and row.get("kind") == kind, "RECEIPT:UNSUPPORTED_SCHEMA_OR_KIND")
    need(row.get("task_id") == task and row.get("mode") == "real"
         and row.get("status") == "PASS", "RECEIPT:TASK_OR_STATUS_MISMATCH")
    string(row.get("producer"), "RECEIPT_PRODUCER")
    when = datetime.fromisoformat(string(row.get("created_at"), "RECEIPT_TIME").replace("Z", "+00:00"))
    need(when.tzinfo is not None, "RECEIPT:TIMEZONE_REQUIRED")
    evidence(row.get("evidence"))
    return row


def same_ref(actual, expected, label):
    checked_ref(actual)
    checked_ref(expected)
    # A verified byte-identical delivery copy need not repeat native operations.
    need(actual["sha256"] == expected["sha256"], label + ":STALE_OR_WRONG_BINDING")


def same_sources(actual, expected, label):
    need(isinstance(actual, list) and len(actual) == len(expected), label + ":SOURCE_SET_MISMATCH")
    need(all(isinstance(s, dict) and isinstance(s.get("id"), str) for s in actual), label + ":SOURCE_SET_MISMATCH")
    by_id = {s["id"]: s for s in actual}
    need(len(by_id) == len(actual) and set(by_id) == {s["id"] for s in expected}, label + ":SOURCE_SET_MISMATCH")
    for row in expected:
        same_ref(by_id[row["id"]].get("file"), row["file"], label + "_SOURCE")


def checked_pdf(value):
    path = checked_ref(value)
    with path.open("rb") as stream:
        need(re.match(rb"%PDF-\d\.\d(?:\r|\n|\s)", stream.read(16)) is not None,
             "PDF:HEADER_REQUIRED")
    return path


def boundary_ids(master, active, pairs):
    """Check declared literal propagation, not scientific meaning or completeness."""
    declarations = master.get("boundaries", [])
    need(isinstance(declarations, list), "BOUNDARY:LIST_REQUIRED")
    ids, slides = set(), {s["id"]: s for s in active}
    for row in declarations:
        object_(row, "BOUNDARY")
        key = string(row.get("id"), "BOUNDARY_ID")
        need(key not in ids, "BOUNDARY:DUPLICATE_ID")
        ids.add(key)
        source = object_(row.get("source"), "BOUNDARY_SOURCE")
        for field in ("estimand", "time_window", "unit", "risk_set", "tested_status", "interpretation_limit"):
            string(row.get(field), "BOUNDARY_" + field)
        applications = row.get("applies_to")
        need(isinstance(applications, list) and bool(applications), "BOUNDARY:SCOPE_REQUIRED")
        seen = set()
        for app in applications:
            object_(app, "BOUNDARY_APPLICATION")
            sid = app.get("slide_id")
            need(sid in slides and sid not in seen, "BOUNDARY:UNKNOWN_OR_DUPLICATE_SLIDE")
            seen.add(sid)
            need((sid, source.get("id"), source.get("locator")) in pairs, "BOUNDARY:SOURCE_LOCATOR_UNBOUND")
            displayed = []
            for block in slides[sid]["blocks"]:
                if block.get("kind") == "text":
                    displayed.extend(block["paragraphs"])
                elif block.get("kind") == "table":
                    displayed.extend(p for cells in block["rows"] for cell in cells for p in cell)
            count = 0
            for field, contents in (("blocks_excerpts", displayed), ("speech_excerpts", slides[sid]["speech"])):
                excerpts = strings(app.get(field), "BOUNDARY_" + field)
                for excerpt in excerpts:
                    string(excerpt, "BOUNDARY_EXCERPT")
                    need(any(excerpt in text for text in contents), "BOUNDARY:EXCERPT_MISSING:" + key + ":" + sid + ":" + field)
                count += len(excerpts)
            need(count > 0, "BOUNDARY:EXCERPTS_REQUIRED")
    return ids


class Package:
    def __init__(self, path):
        self.zip = zipfile.ZipFile(path)
        names = self.zip.namelist()
        need(len(names) == len(set(names)), "OOXML:DUPLICATE_PART")

    def xml(self, name):
        return ET.fromstring(self.zip.read(name))

    def relations(self, part):
        base = PurePosixPath(part)
        name = str(base.parent / "_rels" / (base.name + ".rels"))
        if name not in self.zip.namelist():
            return {}
        out = {}
        for rel in self.xml(name):
            need(rel.tag == "{" + REL + "}Relationship", "OOXML:RELATION_NAMESPACE")
            key = rel.get("Id")
            need(bool(key) and key not in out, "OOXML:DUPLICATE_RELATION_ID")
            out[key] = rel
        return out

    def target(self, part, rel):
        need(rel is not None and rel.get("TargetMode") != "External", "OOXML:INTERNAL_RELATION_REQUIRED")
        target = string(rel.get("Target"), "REL_TARGET")
        need("\\" not in target and ":" not in target, "OOXML:INVALID_RELATION_TARGET")
        result = posixpath.normpath(posixpath.join(posixpath.dirname(part), target)) if not target.startswith("/") else posixpath.normpath(target[1:])
        need(not result.startswith("../") and result != ".." and result in self.zip.namelist(), "OOXML:MISSING_OR_ESCAPING_PART")
        return result


def paragraphs(node, namespace):
    prefix = "{" + NS[namespace] + "}"
    out = []
    for paragraph in node.iter(prefix + "p"):
        value = []
        for child in paragraph.iter():
            if child.tag == prefix + "t":
                value.append(child.text or "")
            elif child.tag == prefix + "tab":
                value.append("\t")
            elif child.tag in {prefix + "br", prefix + "cr"}:
                value.append("\n")
        out.append("".join(value))
    return out


def slide_blocks(pkg, part, tree):
    blocks = []
    rels = pkg.relations(part)
    for child in tree:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "grpSp":
            blocks.extend(slide_blocks(pkg, part, child))
        elif tag in {"sp", "cxnSp"}:
            body = child.find("p:txBody", NS)
            if body is not None:
                text = paragraphs(body, "a")
                if any(text):
                    blocks.append({"kind": "text", "paragraphs": text})
        elif tag == "graphicFrame":
            table = child.find("a:graphic/a:graphicData/a:tbl", NS)
            need(table is not None, "PPTX:UNSUPPORTED_GRAPHIC_FRAME")
            blocks.append({"kind": "table", "rows": [
                [paragraphs(cell, "a") for cell in row.findall("a:tc", NS)]
                for row in table.findall("a:tr", NS)]})
        elif tag == "pic":
            blip = child.find("p:blipFill/a:blip", NS)
            need(blip is not None and blip.get("{" + NS["r"] + "}link") is None, "PPTX:EMBEDDED_IMAGE_REQUIRED")
            target = pkg.target(part, rels.get(blip.get("{" + NS["r"] + "}embed")))
            blocks.append({"kind": "image", "sha256": hashlib.sha256(pkg.zip.read(target)).hexdigest()})
        else:
            need(tag in {"nvGrpSpPr", "grpSpPr", "extLst"}, "PPTX:UNSUPPORTED_SHAPE:" + tag)
    return blocks


def read_pptx(path):
    pkg = Package(path)
    try:
        part = "ppt/presentation.xml"
        rels = pkg.relations(part)
        listing = pkg.xml(part).find("p:sldIdLst", NS)
        need(listing is not None and len(listing) > 0, "PPTX:NO_SLIDES")
        slides, seen, seen_notes = [], set(), set()
        for item in listing:
            rel = rels.get(item.get("{" + NS["r"] + "}id"))
            need(rel is not None and rel.get("Type", "").endswith("/slide"), "PPTX:SLIDE_RELATION_REQUIRED")
            target = pkg.target(part, rel)
            need(target not in seen, "PPTX:DUPLICATE_SLIDE")
            seen.add(target)
            root = pkg.xml(target)
            need(root.get("show", "1") not in {"0", "false"}, "PPTX:HIDDEN_SLIDE_UNSUPPORTED")
            tree = root.find("p:cSld/p:spTree", NS)
            need(tree is not None, "PPTX:SHAPE_TREE_REQUIRED")
            notes = [r for r in pkg.relations(target).values() if r.get("Type", "").endswith("/notesSlide")]
            need(len(notes) == 1, "PPTX:ONE_NOTES_PART_REQUIRED")
            notes_part = pkg.target(target, notes[0])
            need(notes_part not in seen_notes, "PPTX:REUSED_NOTES_PART")
            seen_notes.add(notes_part)
            speech = []
            for shape in pkg.xml(notes_part).findall(".//p:sp", NS):
                text = paragraphs(shape, "a")
                placeholder = shape.find("p:nvSpPr/p:nvPr/p:ph", NS)
                kind = placeholder.get("type") if placeholder is not None else None
                if kind == "body":
                    speech.extend(text)
                elif any(text):
                    need(kind in {"sldNum", "hdr", "ftr", "dt"}, "PPTX:UNCONTROLLED_NOTE_TEXT")
            slides.append({"blocks": slide_blocks(pkg, target, tree), "speech": speech})
        return slides
    finally:
        pkg.zip.close()


def read_speaker(path):
    pkg = Package(path)
    try:
        root = pkg.xml("word/document.xml")
        body = root.find("w:body", NS)
        need(body is not None, "DOCX:BODY_REQUIRED")
        for tag in ("tbl", "ins", "del", "altChunk", "drawing", "pict", "txbxContent"):
            need(body.find(".//w:" + tag, NS) is None, "DOCX:UNSUPPORTED_CONTENT:" + tag)
        auxiliary = {}
        for name in sorted(pkg.zip.namelist()):
            if re.fullmatch(r"word/(header\d+|footer\d+|footnotes|endnotes)\.xml", name):
                text = paragraphs(pkg.xml(name), "w")
                if any(text):
                    auxiliary[name] = text
        return paragraphs(body, "w"), auxiliary
    finally:
        pkg.zip.close()


def audit(contract):
    """Return a binding/content-integrity result, never substantive acceptance."""
    result = {"schema_version": 1, "status": "INCOMPLETE", "pass": False,
              "task_id": None, "errors": [], "limitations": LIMITS}
    try:
        c = object_(contract, "CONTRACT")
        result["task_id"] = task = string(c.get("task_id"), "TASK")
        need(type(c.get("schema_version")) is int and c["schema_version"] == 1
             and c.get("contract_kind") == "derivative_delivery", "CONTRACT:SCHEMA_REQUIRED")
        need(c.get("binding_mode") in {"chapter", "final_thesis"}, "CONTRACT:BINDING_MODE_REQUIRED")
        master = object_(json_file(checked_ref(c.get("master"))), "MASTER")
        need(type(master.get("schema_version")) is int and master["schema_version"] == 1
             and master.get("task_id") == task, "MASTER:SCHEMA_OR_TASK_MISMATCH")
        sources = c.get("sources")
        need(isinstance(sources, list) and bool(sources), "SOURCES:FILES_REQUIRED")
        by_id = {}
        for source in sources:
            object_(source, "SOURCE")
            key = string(source.get("id"), "SOURCE_ID")
            need(key not in by_id, "SOURCE:DUPLICATE_ID")
            checked_ref(source.get("file"))
            by_id[key] = source["file"]
        rows = master.get("slides")
        need(isinstance(rows, list) and bool(rows), "MASTER:SLIDES_REQUIRED")
        active, ids, pairs = [], set(), set()
        for row in rows:
            object_(row, "SLIDE")
            key = string(row.get("id"), "SLIDE_ID")
            need(key not in ids and row.get("status") in {"active", "archived"}, "SLIDE:ID_OR_STATUS_INVALID")
            ids.add(key)
            if row["status"] == "archived":
                continue
            need(isinstance(row.get("blocks"), list) and bool(row["blocks"]), "SLIDE:BLOCKS_REQUIRED")
            strings(row.get("speech"), "SPEECH", True)
            need(any(p.strip() for p in row["speech"]), "SPEECH:NONEMPTY_CONTENT_REQUIRED")
            string(row.get("speaker_heading"), "SPEAKER_HEADING")
            refs = row.get("sources")
            need(isinstance(refs, list) and bool(refs), "SLIDE:SOURCE_LOCATORS_REQUIRED")
            for src in refs:
                object_(src, "SLIDE_SOURCE")
                need(src.get("id") in by_id, "SLIDE:SOURCE_FILE_UNBOUND")
                string(src.get("locator"), "SOURCE_LOCATOR")
                pair = (key, src["id"], src["locator"])
                need(pair not in pairs, "SLIDE:DUPLICATE_SOURCE_LOCATOR")
                pairs.add(pair)
            active.append(row)
        need(bool(active), "MASTER:NO_ACTIVE_SLIDES")
        declared_boundaries = boundary_ids(master, active, pairs)
        prefix = strings(master.get("speaker_prefix"), "SPEAKER_PREFIX")
        auxiliary = object_(master.get("speaker_auxiliary"), "SPEAKER_AUXILIARY")
        artifacts = object_(c.get("artifacts"), "ARTIFACTS")
        need(set(artifacts) == {"pptx", "speaker_docx"}, "ARTIFACTS:EXACT_PAIR_REQUIRED")
        pptx = checked_ref(object_(artifacts["pptx"], "PPTX").get("file"))
        actual = read_pptx(pptx)
        expected = [{"blocks": s["blocks"], "speech": s["speech"]} for s in active]
        need(actual == expected, "PPTX:ORDER_CONTENT_TABLE_IMAGE_OR_NOTES_DRIFT")
        speech = prefix + [p for s in active for p in [s["speaker_heading"], *s["speech"]]]
        actual_speech, actual_auxiliary = read_speaker(checked_ref(object_(artifacts["speaker_docx"], "SPEAKER").get("file")))
        need(actual_speech == speech and actual_auxiliary == auxiliary, "DOCX:SPEECH_HEADING_OR_AUXILIARY_DRIFT")
        for name, backend in (("pptx", "powerpoint_native"), ("speaker_docx", "word_native")):
            artifact = artifacts[name]
            checked_pdf(artifact.get("pdf"))
            native = receipt(artifact.get("native_receipt"), task, "native_export")
            need(native.get("backend") == backend, "NATIVE:BACKEND_MISMATCH")
            same_ref(native.get("input"), artifact["file"], "NATIVE_INPUT")
            same_ref(native.get("output"), artifact["pdf"], "NATIVE_OUTPUT")
            count = integer(native.get("page_count"), "NATIVE_PAGE_COUNT", 1)
            need(name != "pptx" or count == len(active), "NATIVE:SLIDE_COUNT_MISMATCH")
            need(native.get("operation_status") == "COMPLETE" and native.get("resource_status") == "RELEASED", "NATIVE:OPERATION_NOT_RETURNED")
            checked_ref(native.get("release_evidence"))
            visual = receipt(artifact.get("visual_receipt"), task, "visual_review")
            same_ref(visual.get("pdf"), artifact["pdf"], "VISUAL_PDF")
            need(integer(visual.get("page_count"), "VISUAL_PAGE_COUNT", 1) == count, "VISUAL:PAGE_COUNT_MISMATCH")
            pages = visual.get("pages")
            need(isinstance(pages, list) and len(pages) == count, "VISUAL:PAGE_COVERAGE_REQUIRED")
            for i, page in enumerate(pages, 1):
                object_(page, "VISUAL_PAGE")
                need(integer(page.get("page"), "PAGE", 1) == i and page.get("status") == "PASS", "VISUAL:PAGE_ORDER_OR_STATUS")
                need(page.get("method") in {"inspected", "pixel_identical"}, "VISUAL:METHOD_REQUIRED")
                evidence(page.get("evidence"))
                if page["method"] == "pixel_identical":
                    checked_pdf(page.get("previous_pdf"))
                    integer(page.get("previous_page"), "PREVIOUS_PAGE", 1)
                    checked_ref(page.get("comparison_evidence"))
        review = receipt(c.get("review_receipt"), task, "content_review")
        same_ref(review.get("master"), c["master"], "REVIEW_MASTER")
        same_sources(review.get("sources"), sources, "REVIEW")
        if declared_boundaries:
            accepted_boundaries = strings(review.get("boundary_ids"), "REVIEW_BOUNDARY_IDS", True)
            need(len(accepted_boundaries) == len(declared_boundaries) and set(accepted_boundaries) == declared_boundaries,
                 "REVIEW:BOUNDARY_COVERAGE_MISMATCH")
        rounds = review.get("rounds")
        required = integer(c.get("required_review_rounds"), "REQUIRED_ROUNDS", 2)
        need(isinstance(rounds, list) and len(rounds) == required, "REVIEW:ROUND_COUNT_MISMATCH")
        round_ids = set()
        for row in rounds:
            object_(row, "ROUND")
            rid = string(row.get("id"), "ROUND_ID")
            need(rid not in round_ids, "REVIEW:DUPLICATE_ROUND")
            round_ids.add(rid)
            topics = strings(row.get("topics"), "TOPICS", True)
            need(len(topics) == len(TOPICS) and set(topics) == TOPICS, "REVIEW:SIX_TOPICS_REQUIRED")
            for key in ("new_required_changes", "unresolved_required_changes"):
                need(integer(row.get(key), "ROUND_" + key) == 0, "REVIEW:REQUIRED_CHANGES_OPEN")
            need(row.get("content_scope_gaps") == [], "REVIEW:COVERAGE_GAPS_OPEN")
            evidence(row.get("evidence"))
        if c["binding_mode"] == "final_thesis":
            final = object_(c.get("final_thesis"), "FINAL_THESIS")
            checked_ref(final.get("file"))
            freeze = receipt(final.get("freeze_receipt"), task, "final_thesis_freeze")
            same_ref(freeze.get("file"), final["file"], "FINAL_FREEZE")
            mapping = receipt(c.get("mapping_receipt"), task, "final_source_mapping")
            for key, expected_ref in (("master", c["master"]), ("final_thesis", final["file"]), ("freeze_receipt", final["freeze_receipt"])):
                same_ref(mapping.get(key), expected_ref, "MAPPING_" + key)
            same_sources(mapping.get("sources"), sources, "MAPPING")
            mappings = mapping.get("mappings")
            need(isinstance(mappings, list), "MAPPING:ROWS_REQUIRED")
            observed = set()
            for row in mappings:
                object_(row, "MAPPING_ROW")
                key = (row.get("slide_id"), row.get("source_id"), row.get("source_locator"))
                need(key in pairs and key not in observed, "MAPPING:STALE_OR_DUPLICATE_LOCATOR")
                observed.add(key)
                string(row.get("final_locator"), "FINAL_LOCATOR")
                need(row.get("disposition") in {"equivalent", "updated"}, "MAPPING:DISPOSITION_REQUIRED")
                evidence(row.get("evidence"))
            need(observed == pairs, "MAPPING:INCOMPLETE_SOURCE_COVERAGE")
        else:
            need("final_thesis" not in c and "mapping_receipt" not in c, "CHAPTER:UNREQUESTED_FINAL_BINDING")
        result.update(status="INTEGRITY_VERIFIED", **{"pass": True}, active_slides=len(active),
                      archived_slides=len(rows) - len(active), binding_mode=c["binding_mode"])
    except (AuditError, ValueError, TypeError, KeyError, OSError, zipfile.BadZipFile, ET.ParseError) as exc:
        result["errors"].append(str(exc))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        path = Path(args.input)
        need(path.is_absolute(), "CONTRACT:ABSOLUTE_PATH_REQUIRED")
        result = audit(json_file(path))
    except (AuditError, OSError, ValueError) as exc:
        result = {"status": "INCOMPLETE", "pass": False, "errors": [str(exc)], "limitations": LIMITS}
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(args.output)
        # A report must not overwrite an input or pinned evidence file.
        if output.exists() or not output.is_absolute():
            print(json.dumps({"pass": False, "errors": ["OUTPUT:MUST_BE_NEW_ABSOLUTE_PATH"]}))
            return 2
        try:
            with output.open("x", encoding="utf-8") as f:
                f.write(encoded)
        except OSError as exc:
            print(json.dumps({"pass": False, "errors": ["OUTPUT:" + str(exc)]}))
            return 2
    print(encoded, end="")
    return 0 if result["pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
