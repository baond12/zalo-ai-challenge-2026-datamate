"""Strict JSONL contracts and reproducible file hashes (stdlib only)."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date
from pathlib import Path

TYPES = {"number", "percent", "string", "date", "boolean", "list", "table", "unanswerable", "abstain"}


class ContractError(ValueError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ContractError(f"Non-finite JSON constant: {value}")


def read_jsonl(path: Path) -> list[dict]:
    records = []
    ids = set()
    with path.open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
                if not isinstance(record, dict) or not isinstance(record.get("id"), str) or not record["id"]:
                    raise ContractError("Expected object with a non-empty string id")
                if record["id"] in ids:
                    raise ContractError(f"Duplicate record id: {record['id']}")
            except (ValueError, TypeError) as exc:
                raise ContractError(f"{path}:{line_number}: {exc}") from exc
            ids.add(record["id"])
            records.append(record)
    return records


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")


def numeric(value) -> bool:
    return type(value) in (int, float) and (not isinstance(value, float) or math.isfinite(value))


def atom(value) -> bool:
    return isinstance(value, str) or numeric(value)


def validate_answer(record: dict) -> None:
    """Reject malformed submissions rather than silently choosing a BTC penalty."""
    if not isinstance(record.get("id"), str) or not record["id"]:
        raise ContractError("Missing string id")
    kind = record.get("type")
    if not isinstance(kind, str) or kind not in TYPES:
        raise ContractError(f"Unknown answer type: {kind!r}")
    if "reason" in record and not isinstance(record["reason"], str):
        raise ContractError("reason must be a string (train rulebook §7)")
    value = record.get("answer")
    valid = True
    if kind in ("number", "percent"):
        valid = numeric(value)
    elif kind == "string":
        valid = isinstance(value, str)
    elif kind == "boolean":
        valid = type(value) is bool
    elif kind == "date":
        valid = isinstance(value, str) and bool(re.fullmatch(r"\d{4}-\d{2}(?:-\d{2})?", value))
        if valid:
            try:
                date.fromisoformat(value + "-01" if len(value) == 7 else value)
            except ValueError:
                valid = False
    elif kind == "list":
        valid = isinstance(value, list) and all(atom(x) for x in value)
    elif kind == "table":
        valid = isinstance(value, dict) and isinstance(value.get("columns"), list) and isinstance(value.get("rows"), list)
        if valid:
            columns, rows = value["columns"], value["rows"]
            valid = bool(columns) and all(isinstance(c, str) for c in columns)
            valid = valid and all(isinstance(r, list) and len(r) == len(columns) and all(atom(c) for c in r) for r in rows)
    elif kind in ("unanswerable", "abstain"):
        valid = value is None
    if not valid:
        raise ContractError(f"{record.get('id')}: invalid {kind} answer")
