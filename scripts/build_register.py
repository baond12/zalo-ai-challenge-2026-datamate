#!/usr/bin/env python3
"""Traceable documentary registers; never generate inference rules from test data."""
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from datamate.io import sha256, write_json

ROOT = Path(__file__).resolve().parents[1]


def extract(path):
    if path.suffix == ".docx":
        with ZipFile(path) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
            return ["".join(t.text or "" for t in p.findall(".//{*}t")) for p in root.findall(".//{*}p")]
    return path.read_text(encoding="utf-8").splitlines()


def requirement(key, text, source, section, module, tests, status="documented_not_implemented", example=None):
    return {"id": key, "requirement": text, "source": source, "section": section,
            "source_sha256": sha256(ROOT / source), "scope": "competition/global",
            "condition": "applies unless explicitly limited by source", "example": example,
            "target_module": module, "verification": tests, "implementation_status": status,
            "certainty": "verified_from_supplied_document; current portal not checked"}


def main():
    sources = ["Description.txt", "Evaluation.docx", "Data.docx", "Rule.txt", "Submission Guidance.txt", "train/rulebook.md", "public_test/rulebook.md"]
    snapshot = ROOT / "docs/source_extracts"
    snapshot.mkdir(parents=True, exist_ok=True)
    source_manifest = []
    for source in sources:
        lines = extract(ROOT / source)
        dest = snapshot / (Path(source).stem.replace(" ", "_") + ("_public" if source.startswith("public") else "_train" if source.startswith("train") else "") + ".txt")
        dest.write_text("\n".join(f"{i:04d}: {line}" for i, line in enumerate(lines, 1)) + "\n", encoding="utf-8")
        source_manifest.append({"path": source, "sha256": sha256(ROOT / source), "extract": str(dest.relative_to(ROOT)), "extract_unit": "paragraph" if source.endswith("docx") else "line"})
    items = [
        requirement("INPUT-01", "Raw CSV/XLSX/SQLite + README, Vietnamese question, as_of_date, split rulebook/calendar", "Description.txt", "Input", "src/datamate/contracts.py; src/datamate/ingest.py", ["RuntimeContextTests", "ReadersTests"], "implemented_input_scaffold; no semantics"),
        requirement("INPUT-02", "Private includes unseen business types", "Data.docx", "Business types", "splits/business_v1.json; docs/VALIDATION_PROTOCOL.md", ["SplitTests"], "protocol_and_split_implemented; model_generalization_unmeasured"),
        requirement("INPUT-03", "Use the active split rulebook; it can differ from train", "Data.docx", "Business rules", "src/datamate/contracts.py", ["test_context_reads_runtime_rulebook_not_answers", "test_missing_rulebook_fails_instead_of_train_fallback"], "loading_tested; semantic_application_not_implemented"),
        requirement("EVAL-01", "PA=(correct-wrong)/N; missing or abstain gives zero", "Evaluation.docx", "Score", "src/datamate/evaluation.py", ["test_pa_denominator_includes_missing", "test_unanswerable_and_abstain"], "implemented_local_approximation", "+1,-1,0,+1 => PA=0.25"),
        requirement("EVAL-02", "Answer type must equal reference; no partial credit", "Evaluation.docx", "Per-question scoring", "src/datamate/evaluation.py", ["test_wrong_type_has_no_partial_credit"], "implemented_local_approximation"),
        requirement("EVAL-03", "Number exact; floating point serialization noise only", "Evaluation.docx", "number", "src/datamate/evaluation.py", ["test_number_exact_and_float_noise", "test_large_number_has_no_relative_tolerance"], "implemented_local_approximation"),
        requirement("EVAL-04", "Percent exact after rounding to 2 decimals, correct sign", "Evaluation.docx", "percent", "src/datamate/evaluation.py", ["test_percent_rounding_and_sign"], "implemented_local_approximation"),
        requirement("EVAL-05", "NFC/lowercase/punctuation/whitespace normalization preserves accents, accepts aliases/code", "Evaluation.docx", "string", "src/datamate/evaluation.py", ["test_normalize_nfc_case_punctuation_whitespace", "test_scalar_alias", "test_diacritics_preserved"], "implemented_local_approximation"),
        requirement("EVAL-06", "Date ISO day/month and boolean exact", "Evaluation.docx", "date/boolean", "src/datamate/evaluation.py; src/datamate/io.py", ["test_date_exact_month_and_day", "test_boolean"], "implemented_local_approximation"),
        requirement("EVAL-07", "List ordered, positionwise string/number matches", "Evaluation.docx", "list", "src/datamate/evaluation.py", ["test_ordered_list_and_item_aliases", "test_mixed_numeric_list"], "implemented_local_approximation"),
        requirement("EVAL-08", "Table normalized column names, fallback position; rows a set; cells string/number", "Evaluation.docx", "table", "src/datamate/evaluation.py", ["test_table_rows_unordered_columns_reordered_and_aliases", "test_table_column_position_fallback", "test_table_bipartite_not_greedy"], "implemented_local_approximation"),
        requirement("EVAL-09", "Unanswerable is correct only if reference is unanswerable", "Evaluation.docx", "unanswerable", "src/datamate/evaluation.py", ["test_unanswerable_and_abstain"], "implemented_local_approximation"),
        requirement("EVAL-10", "Ranking requested/default criterion, descending; tie code ascending; return fewer than k if needed", "Evaluation.docx", "Ranking questions", "src/datamate/semantics/ranking.py (planned)", ["planned: top_k_boundary, tie_code_ascending, short_top_k"]),
        requirement("EVAL-11", "Final ranking tie-break by re-run inference time, then earlier submission", "Evaluation.docx", "Score", "docs/RELEASE_CHECKLIST.md (planned)", ["planned: full cold-start benchmark"]),
        requirement("MODEL-01", "Weights publicly released before 2026-10-01, suitable license, declare all models", "Rule.txt", "Technical requirements 2", "configs/model_inventory.json (planned)", ["planned: license/date/revision evidence"]),
        requirement("MODEL-02", "Total parameters of ALL inference models <=15B; count full MoE; quantization does not change count", "Rule.txt", "Technical requirements 2", "scripts/check_model_inventory.py (planned)", ["planned: inventory parameter sum"]),
        requirement("RUNTIME-01", "Fully offline inference, no APIs/download/network", "Rule.txt", "Technical requirements 3", "Dockerfile (planned)", ["planned: --network none cold start"]),
        requirement("RUNTIME-02", "No manual answers or logic keyed on question/business IDs", "Rule.txt", "Technical requirements 4", "all inference modules (planned)", ["planned: ID-renaming invariance and code review"]),
        requirement("RUNTIME-03", "Input mount read-only; generated code may run, temporary writes elsewhere", "Rule.txt", "Technical requirements 5", "src/datamate/ingest.py", ["test_sqlite_is_readonly", "planned: read-only container mount"], "readers_tested; container_not_verified"),
        requirement("DATA-01", "Provided train, self-synthetic, public datasets/models allowed; test training or collecting test answers forbidden", "Rule.txt", "Technical requirements 6", "docs/VALIDATION_PROTOCOL.md", ["SplitTests", "planned: training lineage enforcement"], "protocol_only; no_training_started"),
        requirement("COMPUTE-01", "Whole private <=6h including loading on 2xRTX5090 32GB and 512GB RAM", "Rule.txt", "Technical requirements 7", "scripts/benchmark.py (planned)", ["planned: reference-hardware full run"]),
        requirement("COMPUTE-02", "CUDA>=12.8 and matching PyTorch/vLLM; follow organizer Docker base image guideline", "Rule.txt", "Technical requirements 7", "Dockerfile (planned)", ["planned: guideline and Blackwell smoke test"]),
        requirement("REPRO-01", "BTC Docker private re-run final; absolute uploaded/re-run PA difference <=0.03", "Rule.txt", "Technical requirements 8", "scripts/replay.py (planned)", ["planned: repeated cold-start replay"]),
        requirement("REPRO-02", "If timeout/termination, only already-written answers count; remainder abstain", "Rule.txt", "Technical requirements 8", "src/datamate/serialization.py (planned)", ["planned: interruption and flush test"]),
        requirement("PACKAGE-01", "predict.sh reads /data and writes /result/submission.jsonl; include source, weights and README", "Data.docx", "Docker image", "predict.sh; Dockerfile (planned)", ["planned: packaging contract"]),
        requirement("PACKAGE-02", "Per-question logs include id, final answer and elapsed time", "Data.docx", "Docker image", "src/datamate/logging.py (planned)", ["planned: required log keys"]),
        requirement("SUBMIT-01", "Public 2026-10-26..11-16; <=5 submissions/day reset end of day", "Submission Guidance.txt", "I. Public Test Round", "docs/competition/01_COMPETITION_BRIEF.md", ["document review"], "documented"),
        requirement("SUBMIT-02", "Docker due 2026-11-16 23:59 GMT+7; <=2 submissions, last evaluated; public Drive link+checksum", "Submission Guidance.txt", "I. Public Test Round", "releases/ (planned)", ["planned: release checksum and delivery"]),
        requirement("SUBMIT-03", "Private released 2026-11-20 09:00; outputs due 11-23 23:59 GMT+7; use frozen solution", "Submission Guidance.txt", "II. Private Test Round", "docs/VALIDATION_PROTOCOL.md", ["planned: frozen release integrity"]),
        requirement("ELIGIBILITY-01", "General regulations apply; not supplied in this workspace", "Rule.txt", "Technical requirements 1", "docs/OPEN_QUESTIONS.md", ["NOT VERIFIED: obtain general regulations"], "not_verified")
    ]
    write_json(ROOT / "docs/requirements.json", {"version": 1, "sources": source_manifest, "requirements": items})
    rule_records, differences = [], []
    by_split = {}
    modules = {"1": "semantics/revenue.py", "2": "semantics/time.py", "3": "semantics/ranking.py", "4": "semantics/debt.py",
               "5": "semantics/inventory.py", "6": "semantics/industry.py", "7": "verification/answerability.py", "8": "ingest.py", "9": "evaluation.py", "10": "schema/units.py"}
    examples = {
        "Đơn tính vào doanh thu": {"given": "Đơn có 2 dòng, chỉ một dòng được trả", "expected": "Loại cả đơn khỏi doanh thu", "test": "planned: partial_return_excludes_whole_order"},
        "Doanh thu một đơn": {"given": "Thành tiền dòng:100+200; voucher đơn:50; VAT:30; ship:20", "expected": "Doanh thu=300", "test": "planned: revenue_not_checkout_total"},
        "Phần trăm thay đổi, tăng trưởng": {"given": "Kỳ trước=100; kỳ hỏi=90", "expected": "-10 percent", "test": "planned: negative_growth"},
        "Chênh lệch, hơn / kém, tăng / giảm bao nhiêu (số, không phải %)": {"given": "Kỳ hỏi=90; kỳ so=100", "expected": "-10, cùng đơn vị số đo", "test": "planned: signed_difference"},
        "Tuần": {"given": "as_of=2026-03-04", "expected": "Tuần này:03-02..03-04; tuần trước:02-23..03-01", "test": "planned: monday_week_window"},
        "Tháng này": {"given": "as_of=2026-03-31; so tháng trước", "expected": "2026-03-01..03-31 so 2026-02-01..02-28", "test": "planned: previous_month_clamp"},
        "N ngày gần nhất": {"given": "as_of=2026-03-04, N=3", "expected": "2026-03-02..03-04 bao gồm hai đầu", "test": "planned: inclusive_rolling_window"},
        "Quá N, hơn N, trên N, dưới N": {"given": "quá 30 ngày; tuổi nợ=30", "expected": "Không thỏa điều kiện", "test": "planned: strict_age_boundary"},
        "Nợ một đơn tại ngày X": {"given": "Tổng phải trả=120; đã trả đến X=50", "expected": "Còn nợ=70; không dùng doanh thu thay tổng phải trả", "test": "planned: debt_checkout_total"},
        "Giá nhập bình quân một mặt hàng trong tháng": {"given": "Nhập 2 đơn vị giá10 và 8 đơn vị giá20", "expected": "18 mỗi đơn vị nhập", "test": "planned: quantity_weighted_purchase_price"},
        "Lãi gộp": {"given": "Dòng bán hợp lệ: revenue=100; SL bán=2; giá vốn trên dòng=30", "expected": "Lãi gộp=40, không tự tính lại giá vốn từ lô", "test": "planned: line_cost_authority"},
        "Khách trung thành nhất": {"given": "A mua 4 đơn trong 1 ngày; B mua 3 đơn trong 3 ngày", "expected": "B theo số ngày mua, nếu các đơn hợp lệ", "test": "planned: runtime_loyalty_rule"},
        "Nhà cung cấp chính": {"given": "A:2 phiếu trị giá200; B:3 phiếu trị giá100", "expected": "B theo số phiếu hợp lệ", "test": "planned: runtime_supplier_rule"}}
    for split in ("train", "public_test"):
        path = ROOT / split / "rulebook.md"
        section = "preamble"
        records = []
        for line_no, line in enumerate(path.read_text().splitlines(), 1):
            if line.startswith("##"):
                section = line.lstrip("# ")
            if line.startswith("| ") and not line.startswith("| Luật |") and not line.startswith("| Cách nói |") and not line.startswith("| Từ |") and not line.startswith("| type |"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) < 2:
                    continue
                term, content = cells[0], " | ".join(cells[1:])
            elif line.startswith(("- ", "**Hôm nay**", "Mọi đáp án", "Trường `reason`", "**Mỗi type")):
                term, content = "paragraph", line
            else:
                continue
            number = re.match(r"(\d+)\.", section)
            module = modules.get(number[1] if number else "", "contracts.py")
            record = {"id": split + "." + hashlib.sha256((section + "|" + term + "|" + content).encode()).hexdigest()[:12],
                      "section": section, "term": term, "requirement": content, "source": str(path.relative_to(ROOT)),
                      "source_line": line_no, "source_sha256": sha256(path), "scope": split,
                      "precedence": "explicit question > defaults; industry > general when specified; README conflict unresolved",
                      "condition": "as described in original requirement", "example": None,
                      "example_status": "not authored; original prose retained",
                      "target_module": "src/datamate/" + module,
                      "verification": "planned semantic fixture; do not infer coverage from register presence",
                      "implementation_status": "documented_only (scoring coverage tracked separately in requirements.json)",
                      "certainty": "verified_document_text; semantic implementation not verified"}
            if term in examples:
                record["example"] = examples[term]
                record["example_status"] = "analyst-authored tiny example, not an actual dataset answer"
                record["verification"] = examples[term]["test"]
            records.append(record)
        by_split[split] = records
        rule_records.extend(records)
    train_map = {(r["section"], r["term"]): r for r in by_split["train"] if r["term"] != "paragraph"}
    public_map = {(r["section"], r["term"]): r for r in by_split["public_test"] if r["term"] != "paragraph"}
    for key in sorted(set(train_map) | set(public_map)):
        tr, pu = train_map.get(key), public_map.get(key)
        if tr and pu and tr["requirement"] == pu["requirement"]:
            continue
        differences.append({"section": key[0], "term": key[1], "change": "added" if tr is None else "removed" if pu is None else "modified",
                            "train_rule": tr["id"] if tr else None, "public_rule": pu["id"] if pu else None})
    write_json(ROOT / "docs/RULE_REGISTER.json", {"version": 1, "execution_policy": "documentary evidence, not executable runtime defaults",
                                                 "rules": rule_records, "train_public_differences": differences})
    readmes = []
    for path in sorted((ROOT / "train/data").glob("*/README.md")):
        lines = path.read_text().splitlines()
        readmes.append({"business_id": path.parent.name, "source": str(path.relative_to(ROOT)), "sha256": sha256(path),
                        "lines": [{"line": i, "text": line} for i, line in enumerate(lines, 1) if line.strip()]})
    write_json(ROOT / "docs/TRAIN_README_REGISTER.json", {"scope": "input metadata from train; no runtime answer lookup", "businesses": readmes})
    print(json.dumps({"requirements": len(items), "rulebook_records": len(rule_records), "split_differences": len(differences), "train_readmes": len(readmes)}))


if __name__ == "__main__":
    main()
