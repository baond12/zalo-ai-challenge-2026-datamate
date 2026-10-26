#!/usr/bin/env python3
"""Freeze metadata-based business groups BEFORE model development. No answer values used."""
import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from datamate.audit import folded
from datamate.io import read_jsonl, sha256, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261026


def metadata(audit):
    businesses = json.loads((audit / "businesses.json").read_text())
    tables = json.loads((audit / "tables.json").read_text())
    records = []
    for b in businesses:
        key = b["business_id"]
        readme = (ROOT / b["README"]).read_text()
        # Documentary analyst annotations are evaluation metadata only, NOT inference branches.
        if "**Thuốc**" in readme or "hoạt chất" in readme:
            sector, evidence = "pharmacy", "README Thuốc/hoạt chất conventions"
        elif "Xi măng" in readme or "cát đá" in readme:
            sector, evidence = "building_materials", "README product conversions/delivery conventions"
        elif "Phí phục vụ" in readme:
            sector, evidence = "restaurant", "README service-fee convention and food/beverage products"
        elif "Bánh croissant" in readme:
            sector, evidence = "cafe", "README croissant/tiramisu conversions plus cafe product schema"
        elif "Coca Cola" in readme:
            sector, evidence = "grocery", "README multi-category grocery product conversion list"
        else:
            sector, evidence = "unknown", "README insufficient to establish industry"
        # Verified product-only observations from stage-A metadata review, no answers consulted.
        observations = {
            "biz_102": ("grocery", "DanhSachQuyDoi.xlsx: Coca Cola/Pepsi/Sting"),
            "biz_103": ("grocery", "DanhSachQuyDoi.xlsx: Coca Cola/Pepsi/Sting"),
            "biz_104": ("cafe", "DanhSachQuyDoi.xlsx: croissant/tiramisu"),
            "biz_105": ("cafe", "SoBanHang_1.xlsx: Đá xay cookie, cà phê đen, nước ép"),
            "biz_106": ("cafe", "BaoCaoTonKho.xlsx: cà phê đen/sữa size M,L"),
            "biz_109": ("grocery", "DuLieuBanHang.xlsx/DanhSachSanPham: Coca Cola/Pepsi/Sting")}
        if key in observations:
            sector, evidence = observations[key]
        btables = [t for t in tables if t["business_id"] == key]
        signatures = sorted(set(tuple(folded(c["name"]) for c in t["columns"]) for t in btables if t["rows"] >= 1000))
        records.append({"business_id": key, "sector_annotation": sector, "sector_evidence": evidence,
                        "sector_status": "analyst metadata annotation; not official label" if sector != "unknown" else "unknown, do not guess",
                        "readme_path": b["README"], "readme_sha256": sha256(ROOT / b["README"]),
                        "readme_completeness": "field_dictionary_present" if b["field_dictionary_entries"] else "informal_conventions_only",
                        "question_count": b["questions"], "answer_type_counts": b["answer_types"],
                        "primary_input_shape": "no_order_id_line_log" if b["declared_no_order_id"] else "order_only" if "mỗi dòng một đơn hàng" in b["readme_intro"] else "sqlite_relational" if any(t.get("sqlite") for t in btables) else "multitable_or_order_lines",
                        "fact_header_signatures": [hashlib.sha256(json.dumps(sig).encode()).hexdigest() for sig in signatures]})
    return records, tables


def create_split(records, tables):
    ids = sorted(r["business_id"] for r in records)
    parent = {b: b for b in ids}

    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    # Group exact normalized SALE fact schemas, excluding side tables, dimensions and purchasing.
    signatures = defaultdict(set)
    for table in tables:
        cols = [folded(c["name"]) for c in table["columns"]]
        names = " ".join(cols)
        has_status = any(c["role_candidate"] == "status" for c in table["columns"])
        has_quantity = any("so luong" in c or c in ("sl", "s l", "soluong") for c in cols)
        has_order = any(c["role_candidate"] == "order_id" for c in table["columns"])
        # A sale detail table may have no status (header holds it); filename/table evidence supplies scope.
        location = folded(table["path"] + " " + table["table"])
        sale_detail = any(word in location for word in ("chitiet", "chi tiet", "chi_tiet")) and not any(word in location for word in ("nhap", "lohang", "lo hang"))
        if table["rows"] >= 1000 and has_order and has_quantity and (has_status or sale_detail):
            signatures[tuple(cols)].add(table["business_id"])
    grouping_evidence = []
    for signature, businesses in sorted(signatures.items()):
        if len(businesses) < 2:
            continue
        members = sorted(businesses)
        for b in members[1:]:
            parent[find(b)] = find(members[0])
        grouping_evidence.append({"businesses": members, "normalized_columns": list(signature), "reason": "exact normalized sale-fact header schema"})
    clusters = defaultdict(list)
    for b in ids:
        clusters[find(b)].append(b)
    groups = sorted(clusters.values())
    # Hold out a whole common schema family spanning grocery/cafe/pharmacy, plus one restaurant.
    # Chosen from metadata, not scores or answer values; scope intentionally documented.
    target = {"biz_102", "biz_129"}
    holdout = sorted(b for group in groups if set(group) & target for b in group)
    dev = sorted(set(ids) - set(holdout))
    by_id = {r["business_id"]: r for r in records}
    dev_groups = [g for g in groups if not set(g) & set(holdout)]
    folds = [[] for _ in range(4)]
    loads = [0] * 4
    tie = lambda group: hashlib.sha256((str(SEED) + "|" + "|".join(group)).encode()).hexdigest()
    for group in sorted(dev_groups, key=lambda g: (-sum(by_id[b]["question_count"] for b in g), tie(g))):
        index = min(range(4), key=lambda i: (loads[i], len(folds[i]), i))
        folds[index].extend(group)
        loads[index] += sum(by_id[b]["question_count"] for b in group)
    result = {"version": "business_v1", "seed": SEED, "selection_uses_answer_values": False,
              "selection_basis": "raw train schema/README, question counts; no model scores; aggregate types reported after grouping",
              "holdout_businesses": holdout, "development_businesses": dev,
              "leakage_groups": groups, "grouping_evidence": grouping_evidence,
              "folds": [{"fold": i, "validation_businesses": sorted(f), "training_businesses": sorted(set(dev)-set(f))} for i, f in enumerate(folds)],
              "leave_one_sector_out": [],
              "holdout_limitations": ["not pristine blind: raw inputs and aggregate answer types audited before freeze",
                                      "building_materials absent in holdout; use grouped CV and sector stress test",
                                      "unknown industry excluded from claims of unseen-industry validation",
                                      "holdout common-schema family intentionally unavailable in development"]}
    for sector in sorted(set(r["sector_annotation"] for r in records) - {"unknown"}):
        validation = sorted(b for b in dev if by_id[b]["sector_annotation"] == sector)
        if not validation:
            continue
        blocked_groups = {b for g in groups if set(g) & set(validation) for b in g}
        unknown = {b for b in dev if by_id[b]["sector_annotation"] == "unknown"}
        # Exclude schema-linked peers of held industry from training too.
        result["leave_one_sector_out"].append({"sector": sector, "validation_businesses": validation,
                                              "training_businesses": sorted(set(dev) - blocked_groups - unknown),
                                              "schema_linked_excluded_businesses": sorted((blocked_groups & set(dev)) - set(validation)),
                                              "unknown_sector_excluded_businesses": sorted(unknown),
                                              "status": "protocol only; no model evaluated"})
    def aggregate(bids):
        types = Counter()
        for b in bids:
            types.update(by_id[b]["answer_type_counts"])
        return {"businesses": len(bids), "questions": sum(by_id[b]["question_count"] for b in bids),
                "answer_types": dict(types), "sectors": dict(Counter(by_id[b]["sector_annotation"] for b in bids))}
    result["summary"] = {"development": aggregate(dev), "holdout": aggregate(holdout),
                         "folds": [aggregate(f) for f in folds]}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--version", default="business_v1")
    parser.add_argument("--supersedes", default=None)
    args = parser.parse_args()
    if not re_version(args.version):
        parser.error("version must be business_vN")
    dest = ROOT / f"splits/{args.version}.json"
    if dest.exists():
        parser.error("business_v1 already frozen; do not silently regenerate or overwrite")
    records, tables = metadata(args.audit)
    split = create_split(records, tables)
    split["version"] = args.version
    split["supersedes"] = args.supersedes
    split["provenance"] = {"audit_summary_sha256": sha256(args.audit / "summary.json"),
                           "questions_sha256": sha256(ROOT / "train/questions.jsonl"),
                           "answers_sha256": sha256(ROOT / "train/answers.jsonl")}
    write_json(ROOT / "docs/BUSINESS_TAXONOMY.json", {"usage": "split/evaluation metadata only; never import into predictor", "businesses": records})
    write_json(dest, split)
    qmeta = []
    for q in read_jsonl(ROOT / "train/questions.jsonl"):
        b = q["business_id"]
        fold = next((f["fold"] for f in split["folds"] if b in f["validation_businesses"]), None)
        qmeta.append({"id": q["id"], "business_id": b, "partition": "holdout" if b in split["holdout_businesses"] else "development", "cv_fold": fold})
    write_jsonl(ROOT / f"splits/question_assignments_{args.version.removeprefix('business_')}.jsonl", qmeta)
    write_json(ROOT / "splits/LOCK.json", {"manifest": str(dest.relative_to(ROOT)), "sha256": sha256(dest), "seed": SEED,
                                          "holdout_score_openings": 0, "policy": "append exposure log; do not edit frozen manifest"})
    print(json.dumps(split["summary"], ensure_ascii=False, indent=2))


def re_version(value):
    import re
    return bool(re.fullmatch(r"business_v\d+", value))


if __name__ == "__main__":
    main()
