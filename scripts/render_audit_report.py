#!/usr/bin/env python3
"""Render observations from a completed full train audit; no new label analysis."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from datamate.io import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()
    audit = args.audit
    summary = json.loads((audit / "summary.json").read_text())
    tables = json.loads((audit / "tables.json").read_text())
    businesses = json.loads((audit / "businesses.json").read_text())
    relationships = json.loads((audit / "relationships.json").read_text())
    taxonomy = json.loads((ROOT / "docs/BUSINESS_TAXONOMY.json").read_text())["businesses"]
    sectors = {b["business_id"]: b["sector_annotation"] for b in taxonomy}
    tags = Counter()
    for line in (audit / "question_taxonomy.jsonl").read_text().splitlines():
        tags.update(json.loads(line)["tags"])
    headers = Counter(t.get("header_row") for t in tables)
    date_modes = Counter()
    for t in tables:
        for c in t["columns"]:
            date_modes.update(c["date_parse_modes"])
    derived = {
        "header_rows": dict(headers), "date_parse_modes": dict(date_modes),
        "date_parsed_cells": sum(c["date_count"] for t in tables for c in t["columns"]),
        "date_unparsed_cells": sum(c["date_parse_failures"] for t in tables for c in t["columns"]),
        "all_null_column_occurrences": sum(c["nulls"] == t["rows"] and t["rows"] > 0 for t in tables for c in t["columns"]),
        "partially_null_column_occurrences": sum(0 < c["nulls"] < t["rows"] for t in tables for c in t["columns"]),
        "columns_with_negative_numeric_values": sum(c["negative_count"] > 0 for t in tables for c in t["columns"]),
        "candidate_relationships": len(relationships),
        "candidate_relationships_with_zero_unmatched_distinct": sum(r["child_unmatched_distinct"] == 0 for r in relationships),
        "question_tags_nonexclusive_heuristic": dict(tags),
        "readmes_without_field_dictionary": [b["business_id"] for b in businesses if not b["field_dictionary_entries"]]}
    write_json(audit / "derived_findings.json", derived)
    lines = [
        "# Train audit — stage A, 26/10/2026", "",
        f"Bằng chứng chính: `{audit}/summary.json`, `tables.json`, `businesses.json`, `relationships.json`, `input_manifest.json` và `derived_findings.json`. Báo cáo được sinh bằng `scripts/render_audit_report.py` từ full physical scan, không dựa trên sampling để đếm dòng/null/duplicate.", "",
        "## Phạm vi và tình trạng", "",
        f"Đã đọc {summary['businesses']} README, {summary['questions']:,} questions và kiểm tra contract/ID của {summary['references']:,} train references; quét tất cả CSV/XLSX/SQLite trong train. Có {summary['tables']} bảng/sheet, {summary['physical_rows']:,} dòng vật lý sau header/preamble được nhận diện. Đây là tổng trên mọi bảng, **không phải số giao dịch độc lập**. Audit hoàn tất trong {summary['elapsed_seconds']:.3f} giây ở lượt cuối, không có lỗi đọc file.", "",
        "Đã đọc năm tài liệu cuộc thi và đối chiếu rulebook train/public. Không giải public questions, không đọc business data public/private trong stage A. Reference values chỉ phục vụ contract và thống kê shape/type; không có candidate được chấm trên holdout.", "",
        "## Phát hiện đã đo", "",
        f"- Header row distribution: {dict(sorted(headers.items()))}. {sum(v for k, v in headers.items() if k != 1)} sheet/table có header sau dòng 1; parser không thể mặc định hàng đầu là header.",
        f"- {summary['raw_duplicate_rows']:,} dòng có cùng decoded values với dòng trước đó trong cùng bảng/sheet. Đây là count quan sát, không phải số lỗi cần xóa. Không fill/dedup dữ liệu gốc; merged/blank order fields có thể khiến dòng trông giống nhau trước khi khôi phục nhóm.",
        f"- {derived['all_null_column_occurrences']} column occurrences hoàn toàn trống, {derived['partially_null_column_occurrences']} có null một phần. Đếm theo bảng/sheet nên cột lặp qua các tháng được đếm nhiều lần. Không tự biến missing thành zero.",
        f"- {derived['columns_with_negative_numeric_values']} column occurrences có giá trị số âm. Chưa kết luận toàn bộ là trả hàng; cần role và README/status để diễn giải.",
        f"- {derived['date_parsed_cells']:,} ô trong các cột date-candidate được nhận diện ngày; {derived['date_unparsed_cells']} ô không trống còn unparsed theo heuristic hiện tại. Không có nghĩa mọi mapping/ngữ nghĩa ngày đã được xác minh.",
        f"- Date parse modes: {dict(date_modes)}. Có text tiếng Việt `thg`, serial dạng numeric và serial lưu trong string; serial không style được đánh dấu inferred.",
        f"- Calendar có {summary['calendar']['rows']} ngày duy nhất, liên tục {summary['calendar']['date_min']}..{summary['calendar']['date_max']}. Chưa kiểm chứng tính đúng của từng quy đổi âm dương bằng nguồn ngoài; runtime dùng lịch BTC cung cấp.",
        f"- {derived['candidate_relationships']} candidate joins từ role/unique-key/overlap; {derived['candidate_relationships_with_zero_unmatched_distinct']} không có distinct child key ngoài parent. Các candidate còn lại có thể do partition theo tháng, phạm vi khác hoặc mapping sai; chưa gọi là referential-integrity violations.",
        f"- README không có section dictionary cột: {', '.join(derived['readmes_without_field_dictionary'])}. Các README này vẫn có conventions hữu ích; cần schema discovery thay vì đòi đủ dictionary.",
        "- Không có formula cell được reader phát hiện. Không thực hiện tính lại công thức Excel.", "",
        "Ví dụ quan hệ có bằng chứng: biz_111 `don_hang.csv` có 66.469 distinct order IDs; `chi_tiet_don.csv` có 106.585 dòng gắn đủ 66.469 IDs, không có distinct orphan; tối đa 3 dòng hàng/đơn. `thanh_toan.csv` có thể có tới 4 dòng/đơn. Join trực tiếp cả hai detail tables vào header có nguy cơ nhân chéo tiền/số lượng: cần aggregate theo grain trước join.", "",
        "## Taxonomy", "",
        "Nhãn ngành là annotation BA dựa README và product-only observations. Có 6 grocery, 5 cafe, 6 building_materials, 6 pharmacy, 6 restaurant và 1 unknown. biz_110 chỉ có invoice-level data, chưa có đủ bằng chứng ngành nên giữ unknown. Không dùng các nhãn/ID này như routing rules trong solution.", "",
        "Question tags dưới đây là regex không loại trừ nhau, có thể false positive/negative; không phải intent labels chính thức hoặc độ khó đã xác nhận:", "",
        "| Tag | Câu match |", "|---|---:|",
    ]
    lines.extend(f"| {tag} | {count} |" for tag, count in tags.most_common())
    lines += ["", "Answer type: " + "; ".join(f"{k}={v}" for k, v in summary["answer_types"].items()) + ". Number+percent=2.462/3.000 (82,07%); đây là cơ sở ưu tiên deterministic execution, không phải cam kết private có cùng phân bố.", "",
              "## Inventory theo business", "", "| Business | Ngành (annotation) | Bảng/sheet | Dòng vật lý | Raw duplicate | Câu hỏi | Cutoff README |", "|---|---|---:|---:|---:|---:|---|"]
    lines.extend(f"| {b['business_id']} | {sectors[b['business_id']]} | {b['tables']} | {b['physical_rows']:,} | {b['raw_duplicate_rows']:,} | {b['questions']} | {b['readme_declared_cutoff']} |" for b in businesses)
    lines += ["", "## Chưa xác minh / giả định", "",
              "- Header và role detection là heuristic. Stage B phải dùng README + raw provenance, kiểm tra grouping, metadata rows, status và cardinality trước tính đáp án; không coi profile là semantic adapter hoàn chỉnh.",
              "- Số có dấu phân cách tiền chưa được ép thành numeric trong audit; các thống kê numeric chỉ chắc cho plain numbers. Không tự đoán dấu chấm/phẩy là thập phân hay hàng nghìn ở inference.",
              "- Date ranges theo column có thể là order date, payment date, expiry, registration…; không dùng min/max của mọi cột làm coverage của doanh nghiệp.",
              "- Chưa aggregate các file/sheet cùng một logical table, chưa xác minh toàn bộ composite keys, cross-file duplicate và entity aliases. Các profile là vật lý, joins là candidate.",
              "- Chưa chạy SQL trả lời câu train, chưa xác minh reference từng câu, chưa có accuracy/PA của mô hình, chưa có confidence calibration.",
              "- Chưa có GPU/Docker reference benchmark; chỉ xác nhận công cụ nvidia-smi và docker không có trên PATH hiện tại.", "",
              "## Lịch sử audit", "",
              "v1 là full scan đầu tiên; v2 sửa phân biệt quantity/unit/duration, format `thg` và numeric serial; v3 bổ sung serial-as-text và duration label, là bản hiện hành. Ba bản giữ nguyên count physical rows/duplicate. Giữ các bản cũ để truy nguyên; không chỉnh source data. Verification cuối kiểm tra lại SHA-256 toàn bộ 162 file train.", ""]
    (ROOT / "docs/AUDIT_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(derived, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
