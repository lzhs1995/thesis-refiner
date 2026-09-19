#!/usr/bin/env python3
"""Evidence-driven thesis refinement. No model execution or simulated acceptance."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from nlm_contracts import unwrap

TOPICS = {"theory_methods", "data_figures", "structure", "language", "citations", "format"}
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}


class EvidenceError(ValueError):
    pass


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def ref(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha(path)}


def checked_ref(value):
    if not isinstance(value, dict) or not value.get("path") or not value.get("sha256"):
        raise EvidenceError("MISSING_ARTIFACT_REFERENCE")
    path = Path(value["path"])
    if not path.is_absolute() or not path.is_file() or sha(path) != value["sha256"]:
        raise EvidenceError("ARTIFACT_MISSING_OR_CHANGED: " + str(path))
    return path


def read_receipt(value):
    data = json.loads(checked_ref(value).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("mode") != "real":
        raise EvidenceError("REAL_RECEIPT_REQUIRED")
    return data


def inventory(docx):
    """Mechanical original census; an agent still atomizes and reviews each claim."""
    items = []
    with zipfile.ZipFile(docx) as z:
        parts = sorted(n for n in z.namelist() if re.fullmatch(
            r"word/(document|footnotes|endnotes|header\d+|footer\d+)\.xml", n))
        for part in parts:
            root = ET.fromstring(z.read(part))
            tags = {f"{{{NS['w']}}}p": "paragraph", f"{{{NS['w']}}}tbl": "table",
                    f"{{{NS['m']}}}oMath": "formula", f"{{{NS['w']}}}drawing": "figure"}
            counters = {}
            for node in root.iter():
                kind = tags.get(node.tag)
                if not kind:
                    continue
                counters[kind] = counters.get(kind, 0) + 1
                text = "".join(n.text or "" for n in node.iter()
                               if n.tag in {f"{{{NS['w']}}}t", f"{{{NS['m']}}}t"})
                if kind == "paragraph" and not text.strip() and not list(node.iter(f"{{{NS['w']}}}drawing")):
                    continue
                raw = ET.tostring(node, encoding="utf-8")
                items.append({"id": f"{part}:{kind}:{counters[kind]}", "kind": kind,
                              "locator": f"{part}/{kind}[{counters[kind]}]", "text": text,
                              "content_sha256": hashlib.sha256(raw).hexdigest(),
                              "numeric_mentions": [m.group() for m in re.finditer(
                                  r"(?<![\w])[-+]?\d+(?:\.\d+)?(?:%|％)?", text)]})
        for name in sorted(n for n in z.namelist() if n.startswith("word/media/")):
            items.append({"id": name, "kind": "media", "locator": name,
                          "content_sha256": hashlib.sha256(z.read(name)).hexdigest(),
                          "text": "", "numeric_mentions": []})
    if not items:
        raise EvidenceError("EMPTY_ORIGINAL_INVENTORY")
    return {"schema_version": 1, "baseline": ref(docx), "items": items}


def affected_nodes(nodes, changed):
    ids = {n["id"] for n in nodes}
    if not set(changed) <= ids:
        raise EvidenceError("UNKNOWN_CHANGED_NODE")
    affected = set(changed)
    while True:
        downstream = {n["id"] for n in nodes if affected.intersection(n.get("depends_on", []))}
        if downstream <= affected:
            return sorted(affected)
        affected |= downstream


def check_reproduction(state, claim, by_id, ancestors):
    """Bind full reproduction to this claim's domain execution contract."""
    from empirical_trace import audit_contract
    run = read_receipt(claim.get("reproduction_receipt"))
    contract_ref = claim.get("empirical_contract") or state.get("empirical_contract")
    contract = json.loads(checked_ref(contract_ref).read_text())
    claim_ids = contract.get("claim_ids")
    if (not isinstance(claim_ids, list) or claim["id"] not in claim_ids
            or run.get("claim_ids") != claim_ids or contract.get("task_id") != state.get("task_id")
            or run.get("task_id") != state.get("task_id")
            or contract.get("execution_receipt") != claim.get("reproduction_receipt")
            or contract.get("full_reproduction") is not True
            or run.get("end_to_end") is not True or not run.get("target_machine")):
        raise EvidenceError("FULL_REPRODUCTION_BINDING_MISMATCH: " + claim["id"])
    def refs_for(keys):
        return {(a["path"], a["sha256"]) for key in keys for a in by_id[key].get("artifacts", [])}
    script = contract.get("script") or {}
    executable_nodes = [key for key in ancestors if by_id[key].get("kind") in {"cleaning", "variables", "model"}]
    if (script.get("path"), script.get("sha256")) not in refs_for(executable_nodes):
        raise EvidenceError("REPRODUCTION_SCRIPT_OUTSIDE_LINEAGE: " + claim["id"])
    for layer, field in (("data", "inputs"), ("output", "outputs")):
        expected = refs_for(claim["lineage"].get(layer, []))
        recorded = {(a.get("path"), a.get("sha256")) for a in contract.get(field, [])}
        if not expected or not expected <= recorded:
            raise EvidenceError("REPRODUCTION_ARTIFACTS_OUTSIDE_LINEAGE: " + claim["id"] + "/" + layer)
    result = audit_contract(contract)
    if not result["pass"] or result["full_reproduction"] is not True:
        raise EvidenceError("FULL_REPRODUCTION_NOT_PROVEN: " + claim["id"] + ": " + str(result["errors"]))


def check_numeric_dispositions(item, disposition, by_id):
    mentions = item.get("numeric_mentions", [])
    rows = disposition.get("numeric_dispositions")
    if not isinstance(rows, list) or len(rows) != len(mentions):
        raise EvidenceError("NUMERIC_MENTIONS_UNACCOUNTED: " + item["id"])
    for mention, row in zip(mentions, rows):
        if isinstance(row, str):
            claim_id = row  # v1 shorthand: positional reference to a bound claim.
        elif isinstance(row, dict) and row.get("mention") == mention:
            if row.get("kind") == "nonempirical":
                if not isinstance(row.get("reason"), str) or not row["reason"].strip():
                    raise EvidenceError("NUMERIC_NONEMPIRICAL_REASON_REQUIRED: " + item["id"])
                checked_ref(row.get("evidence"))
                continue
            if row.get("kind") != "empirical":
                raise EvidenceError("NUMERIC_DISPOSITION_KIND_REQUIRED: " + item["id"])
            claim_id = row.get("claim_id")
        else:
            raise EvidenceError("NUMERIC_DISPOSITION_INVALID: " + item["id"])
        if (not isinstance(claim_id, str) or claim_id not in disposition.get("claim_ids", [])
                or by_id.get(claim_id, {}).get("kind") != "claim"):
            raise EvidenceError("NUMERIC_CLAIM_BINDING_INVALID: " + item["id"])


def audit_chain(state):
    errors, partials = [], []
    original = state.get("original", {})
    try:
        regenerated = inventory(checked_ref(original.get("baseline")))
        supplied = original.get("items", [])
        if supplied != regenerated["items"]:
            errors.append("ORIGINAL_CENSUS_INCOMPLETE_OR_CHANGED")
    except (EvidenceError, KeyError, zipfile.BadZipFile) as e:
        errors.append(str(e))
        supplied = original.get("items", [])
    nodes = state.get("nodes", [])
    by_id = {n["id"]: n for n in nodes}
    if len(by_id) != len(nodes):
        errors.append("DUPLICATE_NODE_ID")
    visiting, visited = set(), set()

    def visit(key):
        if key in visiting:
            raise EvidenceError("DEPENDENCY_CYCLE: " + key)
        if key not in by_id:
            raise EvidenceError("MISSING_DEPENDENCY: " + key)
        if key in visited:
            return
        visiting.add(key)
        for dep in by_id[key].get("depends_on", []):
            visit(dep)
        visiting.remove(key)
        visited.add(key)

    for n in nodes:
        try:
            visit(n["id"])
            for a in n.get("artifacts", []):
                checked_ref(a)
            if n.get("kind") == "model":
                health = n.get("model_health") or {}
                required = ("normal_termination", "standard_errors_valid", "draws_requested", "draws_saved", "replicate_convergence")
                if not n.get("artifacts") or any(k not in health for k in required):
                    raise EvidenceError("MODEL_HEALTH_AXES_REQUIRED: " + n["id"])
                if health["draws_requested"] is not None and (type(health["draws_requested"]) is not int
                        or type(health["draws_saved"]) is not int or not 0 <= health["draws_saved"] <= health["draws_requested"]):
                    raise EvidenceError("SAVED_DRAWS_CONTRACT_INVALID: " + n["id"])
            if n.get("kind") == "claim":
                if not n.get("artifacts") or not n.get("depends_on"):
                    raise EvidenceError("CLAIM_WITHOUT_LOCAL_EVIDENCE: " + n["id"])
                for dep in n.get("same_sample_as", []):
                    if not n.get("sample_fingerprint") or n["sample_fingerprint"] != by_id[dep].get("sample_fingerprint"):
                        raise EvidenceError("SAMPLE_MISMATCH: " + n["id"])
                if n.get("claims_independent") and n.get("mirror_of"):
                    raise EvidenceError("MIRROR_IS_NOT_INDEPENDENT: " + n["id"])
                if n.get("claims_difference") and not any(by_id[d].get("kind") == "contrast_test" for d in n.get("depends_on", [])):
                    raise EvidenceError("ENDPOINT_TEST_IS_NOT_CONTRAST: " + n["id"])
                axes = n.get("verification", {})
                ancestors, pending = set(), list(n.get("depends_on", []))
                while pending:
                    key = pending.pop()
                    if key not in ancestors:
                        ancestors.add(key)
                        pending.extend(by_id[key].get("depends_on", []))
                if n.get("empirical_kind") not in {"descriptive", "estimated"}:
                    raise EvidenceError("EMPIRICAL_CLAIM_KIND_REQUIRED: " + n["id"])
                required_layers = {"data", "cleaning", "variables", "sample", "output"}
                if n["empirical_kind"] == "estimated":
                    required_layers.add("model")
                lineage = n.get("lineage") or {}
                for layer in sorted(required_layers):
                    members = lineage.get(layer, [])
                    if members:
                        if any(key not in ancestors or by_id[key].get("kind") != layer or not by_id[key].get("artifacts") for key in members):
                            raise EvidenceError("EMPIRICAL_LINEAGE_BINDING_INVALID: " + n["id"] + "/" + layer)
                    else:
                        gap = (n.get("lineage_gaps") or {}).get(layer, {})
                        if (not n.get("accepted_partial") or gap.get("accepted") is not True
                                or not gap.get("reason") or axes.get("full_reproduction") is True):
                            raise EvidenceError("EMPIRICAL_LINEAGE_INCOMPLETE: " + n["id"] + "/" + layer)
                        checked_ref(gap.get("evidence"))
                        partials.append(n["id"])
                for key in ancestors:
                    model = by_id[key]
                    if model.get("kind") != "model":
                        continue
                    health = model.get("model_health") or {}
                    incomplete = (health.get("normal_termination") is not True
                                  or health.get("standard_errors_valid") is not True
                                  or health.get("replicate_convergence") not in {True, "not_applicable"}
                                  or health.get("draws_requested") != health.get("draws_saved"))
                    if incomplete:
                        if (not n.get("accepted_partial") or not n.get("provenance_gap")
                                or axes.get("full_reproduction") is True or key not in n.get("model_limitations", {})):
                            raise EvidenceError("MODEL_HEALTH_PARTIAL_NOT_PROPAGATED: " + n["id"])
                        partials.append(n["id"])
                if axes.get("traceability") not in {"unique_source", "compatible_candidates", "documented_partial"}:
                    raise EvidenceError("TRACEABILITY_UNRESOLVED: " + n["id"])
                if axes.get("traceability") != "unique_source":
                    if not n.get("accepted_partial") or not n.get("provenance_gap"):
                        raise EvidenceError("UNDOCUMENTED_PROVENANCE_GAP: " + n["id"])
                    partials.append(n["id"])
                if n.get("numerical_comparison"):
                    spec = n["numerical_comparison"]
                    if any(k not in spec for k in ("storage_precision", "display_rounding", "tolerance", "ci_method", "draws_requested", "draws_saved")):
                        raise EvidenceError("INCOMPLETE_NUMERICAL_CONTRACT: " + n["id"])
                if n.get("verification", {}).get("full_reproduction") is True:
                    check_reproduction(state, n, by_id, ancestors)
        except (ValueError, KeyError, TypeError, OSError) as e:
            errors.append(str(e))
    dispositions = state.get("dispositions", {})
    if set(dispositions) != {i["id"] for i in supplied}:
        errors.append("ORIGINAL_DISPOSITIONS_INCOMPLETE")
    for item in supplied:
        d = dispositions.get(item["id"], {})
        try:
            if d.get("action") not in {"retain", "rewrite", "move", "delete"} or not d.get("reason"):
                raise EvidenceError("MISSING_DISPOSITION: " + item["id"])
            if d.get("category") == "empirical":
                claims = d.get("claim_ids", [])
                if not claims or any(by_id.get(k, {}).get("kind") != "claim" for k in claims):
                    raise EvidenceError("CLAIM_ATOMIZATION_MISSING: " + item["id"])
            elif d.get("category") != "nonempirical":
                raise EvidenceError("UNREVIEWED_ORIGINAL_ITEM: " + item["id"])
            checked_ref(d.get("review_evidence"))
            check_numeric_dispositions(item, d, by_id)
            if d.get("action") in {"move", "delete"} and d.get("category") == "empirical" and not d.get("retained_evidence_destination"):
                raise EvidenceError("REMOVED_RESULT_WITHOUT_DESTINATION: " + item["id"])
        except EvidenceError as e:
            errors.append(str(e))
    return {"pass": not errors, "errors": errors, "documented_partials": partials,
            "evidence_chain": "CLOSED_WITH_PARTIALS" if not errors and partials else "CLOSED" if not errors else "OPEN",
            "full_reproduction": bool(nodes) and bool([n for n in nodes if n.get("kind") == "claim"]) and all(
                n.get("verification", {}).get("full_reproduction") is True for n in nodes if n.get("kind") == "claim") and not errors}


def answer_payload(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise EvidenceError("ANSWER_OBJECT_REQUIRED")
    inner = unwrap(data)
    if isinstance(inner, dict) and isinstance(inner.get("answer"), dict):
        return inner["answer"].get("text", ""), inner["answer"].get("citations", [])
    citations = inner.get("citations", [])
    if isinstance(citations, dict):
        references = inner.get("references", [])
        if not isinstance(references, list):
            raise EvidenceError("NATIVE_REFERENCE_LIST_REQUIRED")
        normalized = [{"id": str(c.get("citation_number")), "source_id": c.get("source_id"),
                       "cited_text": c.get("cited_text")} for c in references if isinstance(c, dict)]
        if any(str(c.get("id")) in citations and citations[str(c["id"])] != c["source_id"] for c in normalized):
            raise EvidenceError("CITATION_REFERENCE_MAP_CONFLICT")
        if not set(map(str, citations)) <= {c["id"] for c in normalized}:
            raise EvidenceError("CITATION_REFERENCE_MISSING")
        citations = normalized
    return inner.get("answer", ""), citations


def audit_round(round_, document):
    errors = []
    try:
        sources = document.get("sources") or [document["source"]]
        source_ids = {s["id"] for s in sources}
        if round_.get("pdf_sha256") != document["pdf"]["sha256"]:
            raise EvidenceError("STALE_REVIEW_SOURCE")
        if round_.get("mode") != "real":
            raise EvidenceError("REAL_INDEPENDENT_CONVERSATION_REQUIRED")
        needed = {(s, t) for s in document["scope_ids"] for t in TOPICS}
        covered = set()
        queries = round_.get("queries", [])
        if not queries:
            raise EvidenceError("NO_QUERIES")
        for q in queries:
            requested_sources = q.get("source_ids") or [q.get("source_id")]
            conversation = q.get("conversation_id") or round_.get("conversation_id")
            if not conversation or not requested_sources or not set(requested_sources) <= source_ids:
                raise EvidenceError("EXPLICIT_QUERY_SOURCE_AND_CONVERSATION_REQUIRED")
            receipt = read_receipt(q.get("receipt"))
            if receipt.get("status") != "COMPLETE" or receipt.get("exit_code") != 0 or receipt.get("request_id") != q.get("request_id") or not q.get("request_id"):
                raise EvidenceError("QUERY_DID_NOT_COMPLETE")
            bindings = {"document_sha256": document["pdf"]["sha256"],
                        "round_id": round_["id"], "conversation_id": conversation}
            if any(receipt.get(k) != v for k, v in bindings.items()):
                raise EvidenceError("QUERY_RECEIPT_BINDING_MISMATCH")
            if set(receipt.get("source_ids") or [receipt.get("source_id")]) != set(requested_sources):
                raise EvidenceError("QUERY_RECEIPT_SOURCE_MISMATCH")
            answer_path = checked_ref(q.get("raw_answer"))
            if receipt.get("answer_sha256") != sha(answer_path):
                raise EvidenceError("ANSWER_RECEIPT_MISMATCH")
            text, citations = answer_payload(answer_path)
            raw_payload = json.loads(answer_path.read_text())
            raw_payload = unwrap(raw_payload)
            if raw_payload.get("conversation_id") != conversation:
                raise EvidenceError("RAW_CONVERSATION_MISMATCH")
            if not isinstance(text, str) or not text.strip() or not citations:
                raise EvidenceError("EMPTY_CONTROL_FRAME_OR_UNGROUNDED_ANSWER")
            if any(not isinstance(c, dict) or c.get("source_id") not in requested_sources for c in citations):
                raise EvidenceError("CITATION_SOURCE_MISMATCH")
            if not set(raw_payload.get("sources_used") or []) <= set(requested_sources):
                raise EvidenceError("RAW_SOURCE_USAGE_MISMATCH")
            for c in q.get("coverage", []):
                if not c.get("locator") or not c.get("citation_ids"):
                    raise EvidenceError("UNPROVEN_REVIEW_COVERAGE")
                citation_ids = {str(x.get("id")) for x in citations if isinstance(x, dict)}
                if not set(map(str, c["citation_ids"])) <= citation_ids:
                    raise EvidenceError("FABRICATED_CITATION_ID")
                cited = {x["source_id"] for x in citations if str(x["id"]) in set(map(str, c["citation_ids"]))}
                scoped = {s["id"]: s.get("scope_ids") for s in sources}
                if all(scoped[s] is not None for s in cited) and not any(c["scope_id"] in scoped[s] for s in cited):
                    raise EvidenceError("COVERAGE_CITES_WRONG_PARTITION")
                covered.add((c["scope_id"], c["topic"]))
            checked_ref(q.get("local_coverage_evidence"))
        if needed - covered:
            errors.append("MISSING_SCOPE_TOPIC_COVERAGE: " + repr(sorted(needed - covered)))
        for issue in round_.get("issues", []):
            if not issue.get("id") or not issue.get("original_text") or not issue.get("locator"):
                raise EvidenceError("INCOMPLETE_ISSUE_RECORD")
            checked_ref(issue.get("local_evidence"))
            if issue.get("disposition") not in {"false_positive", "already_resolved", "not_actionable"}:
                errors.append("CONFIRMED_OR_UNRESOLVED_ISSUE: " + issue["id"])
        checked_ref(round_.get("issue_census_evidence"))
    except (ValueError, OSError, KeyError, TypeError) as e:
        errors.append(str(e))
    return {"pass": not errors, "errors": errors}


def audit_document(document):
    errors = []
    try:
        checked_ref(document["docx"])
        if checked_ref(document["pdf"]).read_bytes()[:5] != b"%PDF-":
            raise EvidenceError("PDF_REQUIRED")
        if not document.get("scope_ids") or len(set(document["scope_ids"])) != len(document["scope_ids"]):
            raise EvidenceError("EXPLICIT_UNIQUE_REVIEW_SCOPE_REQUIRED")
        sources = document.get("sources") or [document["source"]]
        if len({s["id"] for s in sources}) != len(sources):
            raise EvidenceError("DUPLICATE_SOURCE_BINDING")
        export = read_receipt(document.get("gates", {}).get("export"))
        if export.get("status") != "PASS" or export.get("backend") != "word_native" or any(export.get(k + "_sha256") != document[k]["sha256"] for k in ("docx", "pdf")):
            raise EvidenceError("DOCX_TO_WORD_PDF_BINDING_MISSING")
        page_count = document.get("page_count")
        has_partitions = any(s.get("pdf", document["pdf"])["sha256"] != document["pdf"]["sha256"] for s in sources)
        # The Word export producer reads the actual PDF count.  An unbound
        # manifest number is not evidence of the mother's length.
        if page_count is not None or has_partitions:
            if type(page_count) is not int or page_count < 1 or export.get("page_count") != page_count:
                raise EvidenceError("PDF_PAGE_COUNT_NOT_BOUND_TO_EXPORT")
        partition_pages = set()
        full_source = False
        for source in sources:
            source_pdf = source.get("pdf", document["pdf"])
            checked_ref(source_pdf)
            binding = read_receipt(source["receipt"])
            if binding.get("pdf_sha256") != source_pdf["sha256"] or binding.get("source_id") != source["id"] or binding.get("status") != "READY":
                raise EvidenceError("SOURCE_NOT_BOUND_TO_FROZEN_PDF")
            if source_pdf["sha256"] == document["pdf"]["sha256"]:
                full_source = True
            else:
                mapping = read_receipt(source.get("equivalence_receipt"))
                if mapping.get("status") != "PASS" or mapping.get("parent_pdf_sha256") != document["pdf"]["sha256"] or mapping.get("child_pdf_sha256") != source_pdf["sha256"] or mapping.get("text_and_visual_equivalent") is not True:
                    raise EvidenceError("PARTITION_EQUIVALENCE_NOT_PROVEN")
                if not mapping.get("pages") or mapping["pages"] != source.get("pages"):
                    raise EvidenceError("PARTITION_PAGE_MAP_MISSING")
                pages = mapping["pages"]
                if (any(type(page) is not int or not 1 <= page <= page_count for page in pages)
                        or pages != sorted(set(pages))):
                    raise EvidenceError("PARTITION_PAGE_MAP_INVALID")
                if mapping.get("parent_page_count") != page_count or mapping.get("child_page_count") != len(pages):
                    raise EvidenceError("PARTITION_PAGE_COUNTS_NOT_PROVEN")
                if not source.get("scope_ids") or not set(source["scope_ids"]) <= set(document["scope_ids"]):
                    raise EvidenceError("PARTITION_SCOPE_MAP_MISSING")
                partition_pages.update(mapping["pages"])
        if not full_source and (not document.get("page_count") or partition_pages != set(range(1, document["page_count"] + 1))):
            raise EvidenceError("PARTITION_COVERAGE_INCOMPLETE")
        gates = {"native": "docx", "format": "docx", "visual": "pdf", "pdf_fonts": "pdf"}
        if document.get("has_zotero", True):
            gates["zotero"] = "docx"
        for name, kind in gates.items():
            proof = read_receipt(document.get("gates", {}).get(name))
            if proof.get("status") != "PASS" or proof.get(kind + "_sha256") != document[kind]["sha256"]:
                raise EvidenceError("FINAL_NATIVE_FORMAT_VISUAL_GATE_FAILED: " + name)
        if document.get("query_strategy", "six") != "six":
            benchmark = read_receipt(document.get("query_benchmark"))
            if benchmark.get("status") != "PASS" or benchmark.get("coverage_loss") != 0 or benchmark.get("recall_loss") != 0:
                raise EvidenceError("MERGED_QUERY_STRATEGY_NOT_VALIDATED")
        rounds = document.get("rounds", [])
        if len(rounds) < 2:
            raise EvidenceError("TWO_COMPLETE_ROUNDS_REQUIRED")
        pair = rounds[-2:]
        conversations = [{q.get("conversation_id") or r.get("conversation_id") for q in r.get("queries", [])} for r in pair]
        if conversations[0].intersection(conversations[1]) or pair[0].get("id") == pair[1].get("id"):
            raise EvidenceError("ROUNDS_ARE_NOT_INDEPENDENT")
        ids = [q.get("request_id") for r in pair for q in r.get("queries", [])]
        if len(ids) != len(set(ids)):
            raise EvidenceError("DUPLICATED_QUERY_RECEIPT")
        for r in pair:
            errors.extend(audit_round(r, document)["errors"])
        if document.get("open_confirmed_issues"):
            errors.append("PREVIOUS_CONFIRMED_ISSUES_STILL_OPEN")
    except (EvidenceError, KeyError, TypeError, json.JSONDecodeError) as e:
        errors.append(str(e))
    return {"pass": not errors, "errors": errors}


def acceptance(state):
    chain = audit_chain(state)
    if state.get("empirical_contract"):
        from empirical_trace import audit_contract
        trace = audit_contract(json.loads(checked_ref(state["empirical_contract"]).read_text()))
        chain["empirical_trace"] = trace
        chain["pass"] = chain["pass"] and trace["pass"]
        chain["errors"].extend(trace["errors"])
        chain["full_reproduction"] = chain["full_reproduction"] and trace["full_reproduction"]
        if not trace["pass"]:
            chain["evidence_chain"] = "OPEN"
    documents = {k: audit_document(v) for k, v in state.get("documents", {}).items()}
    expected = set(state.get("required_documents", []))
    complete = bool(expected) and expected == set(documents) and chain["pass"] and all(d["pass"] for d in documents.values())
    return {"schema_version": 1, "task_id": state.get("task_id"), "status": "COMPLETE" if complete else "INCOMPLETE",
            "evidence_chain": chain, "documents": documents,
            "missing_documents": sorted(expected - set(documents)),
            "review_provenance": state.get("review_provenance", "solo_self_review")}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["inventory", "audit-chain", "acceptance", "affected"])
    p.add_argument("--input", required=True)
    p.add_argument("--output")
    p.add_argument("--changed", nargs="*", default=[])
    args = p.parse_args()
    try:
        if args.command == "inventory":
            result = inventory(args.input)
        else:
            state = json.loads(Path(args.input).read_text(encoding="utf-8"))
            result = audit_chain(state) if args.command == "audit-chain" else acceptance(state) if args.command == "acceptance" else {"affected": affected_nodes(state["nodes"], args.changed)}
    except (EvidenceError, ValueError, OSError, KeyError) as e:
        result = {"status": "INCOMPLETE", "pass": False, "errors": [str(e)]}
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 2 if result.get("pass") is False or result.get("status") == "INCOMPLETE" else 0


if __name__ == "__main__":
    sys.exit(main())
