"""Reproducible train-only profiling. Findings are observations, not repairs."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from datamate.ingest import csv_rows, quote_identifier, sqlite_readonly, xlsx_package, xlsx_rows
from datamate.io import read_jsonl, sha256, validate_answer, write_json, write_jsonl


def folded(value):
    text = unicodedata.normalize("NFD", str(value).lower().replace("đ", "d"))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", "".join(c for c in text if not unicodedata.combining(c))).split())


def dictionary(readme):
    result = defaultdict(set)
    in_columns = False
    for line in readme.splitlines():
        if line.startswith("## "):
            in_columns = line.startswith("## Cột trong")
        if not in_columns:
            continue
        match = re.match(r"- \*\*(.+?)\*\*: (.+)", line)
        if match:
            result[folded(match[1])].add(match[2])
    return {k: sorted(v) for k, v in result.items()}


def column_role(name, descriptions):
    desc = folded(" ".join(descriptions))
    label = folded(name)
    compact = label.replace(" ", "")
    # Field dictionary is stronger evidence than a label heuristic. No runtime mappings are learned here.
    for phrase, role in [("ma phieu nhap", "purchase_id"), ("ma phieu thu", "payment_id"),
                         ("ma nha cung cap", "supplier_id"), ("ma khach", "customer_id"),
                         ("ma don", "order_id"), ("ma hang", "product_id"), ("ma lo", "lot_id")]:
        if phrase in desc:
            return role, "README field description (scope may be ambiguous)"
    for pattern, role in [(r"^(ma|id)(donhang|don|hoadon)$", "order_id"),
                          (r"^(ma|id)(sanpham|sp|hang|hanghoa)$", "product_id"),
                          (r"^(ma|id)(khachhang|khach|kh)$", "customer_id"),
                          (r"^(ma|id)(nhacungcap|ncc)$", "supplier_id"),
                          (r"^(ma|id)(phieunhap|nhaphang)$", "purchase_id"),
                          (r"^(ma|id)(lohang|lo)$", "lot_id")]:
        if re.match(pattern, compact):
            return role, "header heuristic; unverified semantics"
    if "trang thai" in desc or "trang thai" in label or label in ("status", "ket qua", "tinh trang", "tinh trang don"):
        return "status", "README/header candidate"
    if desc.startswith("so luong") or label.startswith(("so luong", "sl ")) or label in ("sl", "so luong", "quantity"):
        return "quantity_candidate", "README/header candidate"
    if desc.startswith("he so") or label in ("he so", "ti le quy doi"):
        return "conversion_factor_candidate", "README/header candidate"
    if desc.startswith("don vi") or label in ("dvt", "unit", "don vi tinh"):
        return "unit", "README/header candidate"
    if "so ngay" in label or "so ngay" in desc or label == "han no ngay":
        return "duration_candidate", "header duration, not a calendar date"
    if any(word in desc for word in ("ngay ban", "ngay nhap", "ngay tao", "thoi diem", "han dung", "ngay ap dung")) or any(word in label for word in ("ngay", "date", "thoi gian", "thoi diem", "han dung")) or compact.startswith("ngay"):
        return "date_candidate", "README/header candidate; locale dd/mm/yyyy"
    return None, None


def parsed_date(value, sheet, excel_date=False, date1904=False):
    # Date-column-only fallback for unstyled Excel serials, observed in train.
    # Caller records the inference separately; arbitrary numeric columns never enter here.
    serial_candidate = type(value) in (float, int) and 20000 <= value <= 80000
    if isinstance(value, (float, int)) and not isinstance(value, bool) and (excel_date or serial_candidate):
        try:
            return ((date(1904, 1, 1) if date1904 else date(1899, 12, 30)) + timedelta(days=int(value))).isoformat()
        except (OverflowError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    value = value.strip()
    if re.fullmatch(r"\d{5}(?:\.\d+)?", value) and 20000 <= float(value) <= 80000:
        return parsed_date(float(value), sheet, True, date1904)
    vietnamese = re.fullmatch(r"(\d{1,2})\s+thg\s+(\d{1,2})\s+(\d{4})(?:\s+.*)?", value, re.I)
    if vietnamese:
        day, month, year = map(int, vietnamese.groups())
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    match = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?:\s|$)", value)
    if match:
        d, m, y = map(int, match.groups())
    else:
        match = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})", value)
        year = re.search(r"20\d{2}", sheet)
        if not match or not year:
            return None
        d, m = map(int, match.groups())
        y = int(year[0])
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def _is_date_format(style, metadata):
    formats = metadata.get("cell_formats", [])
    if style is None or style >= len(formats):
        return False
    num_id = int(formats[style].get("numFmtId", 0))
    if num_id in range(14, 23) or num_id in range(45, 48):
        return True
    custom = {int(x["numFmtId"]): x.get("formatCode", "") for x in metadata.get("custom_number_formats", [])}
    return bool(re.search(r"[dy]", custom.get(num_id, ""), re.I))


def profile_table(rows, path, table_name, readme, metadata=None):
    metadata = metadata or {}
    fields = dictionary(readme)
    head = []
    for record in rows:
        head.append(record)
        if len(head) >= 12:
            break
    if not head:
        return {"path": str(path), "table": table_name, "rows": 0, "columns": []}, []
    # Prefer the widest text-rich row in the first 12; preserve evidence and mark heuristic.
    scores = []
    for rowno, values, _, _ in head:
        strings = sum(isinstance(v, str) and bool(v.strip()) for v in values)
        known = sum(folded(v) in fields for v in values if v is not None)
        scores.append((known * 5 + strings, rowno))
    best = max(range(len(head)), key=lambda i: (scores[i][0], -i))
    # All-string data rows must not displace a conventional row-one header on a tie.
    header_no, raw_names, _, _ = head[best]
    names = [str(v).strip() if v is not None else f"__blank_{i}" for i, v in enumerate(raw_names)]
    descriptors = [fields.get(folded(n), []) for n in names]
    roles = [column_role(n, d) for n, d in zip(names, descriptors)]
    columns = []
    unique = [set() for _ in names]
    capped = [False for _ in names]
    key_counts = [Counter() if (role or "").endswith("_id") else None for role, _ in roles]
    categories = [Counter() if role in ("status", "unit") else None for role, _ in roles]
    for name, desc, (role, evidence) in zip(names, descriptors, roles):
        columns.append({"name": name, "readme_descriptions": desc, "role_candidate": role,
                        "role_evidence": evidence, "nulls": 0, "value_types": {}, "numeric_count": 0,
                        "numeric_min": None, "numeric_max": None, "negative_count": 0,
                        "date_count": 0, "date_parse_failures": 0, "date_min": None, "date_max": None})
    type_counts = [Counter() for _ in names]
    date_modes = [Counter() for _ in names]
    hashes = set()
    duplicates = formulas = count = width_mismatch = 0
    blank_rows = 0
    style_counts = Counter()

    def all_rows():
        yield from head[best + 1:]
        yield from rows

    for rowno, values, formula_count, styles in all_rows():
        if not any(v is not None and v != "" for v in values):
            blank_rows += 1
            continue
        count += 1
        formulas += formula_count
        if len(values) > len(names):
            width_mismatch += 1
        raw = json.dumps(values, ensure_ascii=False, separators=(",", ":"), default=str).encode()
        digest = hashlib.blake2b(raw, digest_size=16).digest()
        duplicates += digest in hashes
        hashes.add(digest)
        for i, column in enumerate(columns):
            value = values[i] if i < len(values) else None
            if value is None or value == "":
                column["nulls"] += 1
                continue
            type_counts[i][type(value).__name__] += 1
            key = str(value)
            if len(unique[i]) < 1024:
                unique[i].add(key)
            elif key not in unique[i]:
                capped[i] = True
            if key_counts[i] is not None:
                key_counts[i][key] += 1
            if categories[i] is not None:
                categories[i][key] += 1
            number = None
            if type(value) in (int, float):
                number = value
            elif isinstance(value, str) and re.fullmatch(r"-?\d+(?:\.\d+)?", value.strip()):
                number = float(value) if "." in value else int(value)
            if number is not None:
                column["numeric_count"] += 1
                column["numeric_min"] = number if column["numeric_min"] is None else min(column["numeric_min"], number)
                column["numeric_max"] = number if column["numeric_max"] is None else max(column["numeric_max"], number)
                column["negative_count"] += number < 0
            if roles[i][0] == "date_candidate":
                result = parsed_date(value, table_name, _is_date_format(styles.get(i), metadata), metadata.get("date1904", False))
                if result:
                    mode = "numeric_excel_serial_styled" if _is_date_format(styles.get(i), metadata) else "numeric_excel_serial_inferred" if type(value) in (int, float) else "text_excel_serial_inferred" if re.fullmatch(r"\d{5}(?:\.\d+)?", str(value).strip()) else "text_date"
                    date_modes[i][mode] += 1
                    column["date_count"] += 1
                    column["date_min"] = result if column["date_min"] is None else min(result, column["date_min"])
                    column["date_max"] = result if column["date_max"] is None else max(result, column["date_max"])
                else:
                    column["date_parse_failures"] += 1
            if i in styles:
                style_counts[styles[i]] += 1
    keys = []
    for i, column in enumerate(columns):
        column["value_types"] = dict(type_counts[i])
        column["date_parse_modes"] = dict(date_modes[i])
        column["distinct_count"] = len(unique[i])
        column["distinct_count_is_lower_bound"] = capped[i]
        if categories[i] is not None:
            column["categories"] = dict(categories[i].most_common(100))
            column["categories_truncated"] = len(categories[i]) > 100
        if key_counts[i] is not None:
            counts = key_counts[i]
            column["key_stats"] = {"distinct": len(counts), "repeated_values": sum(n > 1 for n in counts.values()),
                                   "max_multiplicity": max(counts.values(), default=0), "nonnull_unique": all(n == 1 for n in counts.values())}
            keys.append({"path": str(path), "table": table_name, "column": column["name"], "role": roles[i][0], "counts": counts})
    result = {"path": str(path), "table": table_name, "header_row": header_no,
              "header_method": "first-12 text/README-score heuristic; review for semantic use",
              "preamble_rows": best, "rows": count, "blank_rows_after_header": blank_rows,
              "raw_duplicate_rows": duplicates, "duplicate_action": "observed only; no dedup performed",
              "formula_cells": formulas, "rows_wider_than_header": width_mismatch,
              "duplicate_header_names": [n for n, c in Counter(names).items() if c > 1],
              "style_counts": dict(style_counts), "columns": columns}
    return result, keys


def relationship_candidates(keys):
    results = []
    for parent in keys:
        pc = parent["counts"]
        if not pc or any(n != 1 for n in pc.values()):
            continue
        pset = set(pc)
        for child in keys:
            if parent is child or parent["role"] != child["role"]:
                continue
            cc = child["counts"]
            if not cc:
                continue
            overlap = pset.intersection(cc)
            if not overlap:
                continue
            results.append({"role": parent["role"],
                            "parent": {k: parent[k] for k in ("path", "table", "column")},
                            "child": {k: child[k] for k in ("path", "table", "column")},
                            "parent_distinct": len(pc), "child_distinct": len(cc),
                            "child_unmatched_distinct": len(set(cc) - pset),
                            "child_matched_rows": sum(cc[k] for k in overlap),
                            "child_nonnull_rows": sum(cc.values()),
                            "child_max_multiplicity": max(cc.values()),
                            "status": "candidate only; confirm scope, grain and partition union before joining"})
    return results


def question_tags(question):
    text = folded(question)
    patterns = {"revenue": r"doanh thu|ban.*tien|tien ban|thu ve", "debt": r"no|mua chiu|thu no",
                "inventory": r"ton|het hang|het han", "purchase": r"nhap|nha cung cap",
                "profit_cost": r"lai|loi|gia von|chi phi", "ranking": r"nhat|top|xep|liet ke",
                "comparison": r"so voi|tang|giam|chenh|hon|kem", "relative_time": r"nay|truoc|roi|gan nhat|hom qua",
                "lunar": r"tet|am lich", "units": r"thung|loc|bao|kg|tan|chai|lon|hop|vien"}
    return [tag for tag, pattern in patterns.items() if re.search(r"\b(?:" + pattern + r")\b", text)]


def environment():
    mem = {}
    path = Path("/proc/meminfo")
    if path.exists():
        mem = {line.split(":")[0]: line.split(":")[1].strip() for line in path.read_text().splitlines()
               if line.startswith(("MemTotal:", "MemAvailable:"))}
    return {"python": sys.version, "platform": platform.platform(), "cpu_count": os.cpu_count(), "memory": mem,
            "disk_bytes": dict(zip(("total", "used", "free"), shutil.disk_usage("."))),
            "nvidia_smi": shutil.which("nvidia-smi"), "docker": shutil.which("docker"),
            "gpu_status": "not verified: nvidia-smi unavailable" if not shutil.which("nvidia-smi") else "tool present; not queried",
            "credentials_inspected": False, "training_started": False}


def audit_train(root: Path, output: Path):
    """Full physical scan of train; no reads of public/private questions/data."""
    start = time.monotonic()
    if output.exists():
        raise FileExistsError(f"Use a fresh output directory: {output}")
    train = root / "train"
    questions = read_jsonl(train / "questions.jsonl")
    references = read_jsonl(train / "answers.jsonl")
    assert {q["id"] for q in questions} == {a["id"] for a in references}, "Unaligned train IDs"
    for ref in references:
        validate_answer(ref)
    answers = {a["id"]: a for a in references}
    output.mkdir(parents=True)
    write_json(output / "environment.json", environment())
    file_manifest, businesses, tables, joins = [], [], [], []
    qtags = [{"id": q["id"], "business_id": q["business_id"], "tags": question_tags(q["question"]),
              "tag_method": "nonexclusive lexical heuristics; not ground truth"} for q in questions]
    write_jsonl(output / "question_taxonomy.jsonl", qtags)
    for path in sorted(train.rglob("*")):
        if path.is_file():
            file_manifest.append({"path": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": sha256(path)})
    write_json(output / "input_manifest.json", file_manifest)
    for directory in sorted((train / "data").iterdir()):
        if not directory.is_dir():
            continue
        business_start = time.monotonic()
        readme = (directory / "README.md").read_text()
        bkeys, btables = [], []
        errors = []
        for path in sorted(directory.iterdir()):
            relative = path.relative_to(root)
            try:
                if path.suffix == ".csv":
                    table, keys = profile_table(iter(csv_rows(path)), relative, "csv", readme)
                    btables.append(table); bkeys.extend(keys)
                elif path.suffix == ".xlsx":
                    with xlsx_package(path) as (archive, strings, meta):
                        for sheet in meta["sheets"]:
                            structure = {}
                            table, keys = profile_table(iter(xlsx_rows(archive, strings, sheet["member"], structure)), relative, sheet["name"], readme, meta)
                            table["xlsx"] = {"date1904": meta["date1904"], "state": sheet["state"], **structure}
                            btables.append(table); bkeys.extend(keys)
                elif path.suffix == ".sqlite":
                    with sqlite_readonly(path) as con:
                        integrity = con.execute("PRAGMA quick_check").fetchone()[0]
                        for name, sql in con.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
                            cursor = con.execute("SELECT * FROM " + quote_identifier(name))
                            names = [x[0] for x in cursor.description]
                            def sql_rows():
                                yield 1, names, 0, {}
                                for i, row in enumerate(cursor, 2):
                                    yield i, list(row), 0, {}
                            table, keys = profile_table(iter(sql_rows()), relative, name, readme)
                            table["sqlite"] = {"quick_check": integrity, "ddl": sql,
                                               "foreign_keys": con.execute("PRAGMA foreign_key_list(" + quote_identifier(name) + ")").fetchall()}
                            btables.append(table); bkeys.extend(keys)
            except Exception as exc:
                errors.append({"path": str(relative), "error": f"{type(exc).__name__}: {exc}"})
        related = relationship_candidates(bkeys)
        joins.extend({"business_id": directory.name, **j} for j in related)
        bquestions = [q for q in questions if q["business_id"] == directory.name]
        banswers = [answers[q["id"]] for q in bquestions]
        cutoff = re.search(r"Dữ liệu có đến hết (\d{2}/\d{2}/\d{4})", readme)
        business = {"business_id": directory.name, "README": str((directory / 'README.md').relative_to(root)),
                    "readme_chars": len(readme), "field_dictionary_entries": len(dictionary(readme)),
                    "readme_declared_cutoff": parsed_date(cutoff[1], "") if cutoff else None,
                    "readme_intro": readme.split("##")[0].strip(),
                    "declared_no_order_id": "không ghi mã đơn" in readme,
                    "declared_no_customer": "không ghi tên khách" in readme,
                    "file_extensions": dict(Counter(p.suffix for p in directory.iterdir() if p.is_file())),
                    "questions": len(bquestions), "answer_types": dict(Counter(a["type"] for a in banswers)),
                    "as_of_min": min(q["as_of_date"] for q in bquestions), "as_of_max": max(q["as_of_date"] for q in bquestions),
                    "tables": len(btables), "physical_rows": sum(t["rows"] for t in btables),
                    "raw_duplicate_rows": sum(t.get("raw_duplicate_rows", 0) for t in btables),
                    "errors": errors, "elapsed_seconds": round(time.monotonic() - business_start, 3)}
        businesses.append(business)
        tables.extend({"business_id": directory.name, **t} for t in btables)
        print(f"{directory.name}: {business['tables']} tables, {business['physical_rows']} rows, {len(errors)} errors, {business['elapsed_seconds']}s", flush=True)
    with (train / "calendar.csv").open(encoding="utf-8-sig", newline="") as f:
        calendar = list(csv.DictReader(f))
    dates = [date.fromisoformat(r["date"]) for r in calendar]
    summary = {"status": "completed_with_errors" if any(b["errors"] for b in businesses) else "completed",
               "started_context_date": "2026-10-26 Asia/Ho_Chi_Minh (user context)",
               "execution_timestamp_utc": datetime.now(timezone.utc).isoformat(),
               "businesses": len(businesses), "questions": len(questions), "references": len(references),
               "answer_types": dict(Counter(a["type"] for a in references)), "tables": len(tables),
               "physical_rows": sum(t["rows"] for t in tables),
               "raw_duplicate_rows": sum(t.get("raw_duplicate_rows", 0) for t in tables),
               "formula_cells": sum(t.get("formula_cells", 0) for t in tables),
               "calendar": {"rows": len(calendar), "date_min": min(dates).isoformat(), "date_max": max(dates).isoformat(),
                            "unique_dates": len(set(dates)), "continuous": sorted(set(dates)) == [min(dates) + timedelta(days=i) for i in range((max(dates) - min(dates)).days + 1)]},
               "elapsed_seconds": round(time.monotonic() - start, 3),
               "scope": "full physical scan of train only; aggregate reference metadata; no semantic execution or answer verification",
               "public_private_data_read": False,
               "limitations": ["header/roles inferred and require review before semantics", "missingness raw, no forward fill",
                               "duplicates raw within table, not rulebook dedup", "candidate joins not semantic foreign keys",
                               "date recognition heuristic: dd/mm/yyyy, Vietnamese thg and plausible Excel serials in date-candidate columns",
                               "numeric statistics parse plain numbers only; currency separators not interpreted",
                               "general XLSX formulas not recalculated"]}
    write_json(output / "businesses.json", businesses)
    write_json(output / "tables.json", tables)
    write_json(output / "relationships.json", joins)
    write_json(output / "summary.json", summary)
    return summary
