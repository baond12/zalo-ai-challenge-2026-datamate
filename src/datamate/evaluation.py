"""Document-derived local scorer; not the undisclosed official implementation."""

from __future__ import annotations

import unicodedata
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP, localcontext

from datamate.io import ContractError, numeric, validate_answer

SCORER_VERSION = "local-v1"
# Intentional absolute tolerance for float serialization only; no relative tolerance.
NUMBER_EPSILON = Decimal("0.000000001")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    return " ".join("".join(c if c.isalpha() or c.isdigit() or c.isspace() else " " for c in text).split())


def rounded(value, places=2) -> Decimal:
    number = Decimal(str(value))
    with localcontext() as ctx:
        ctx.prec = max(40, number.adjusted() + places + 3)
        return number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def match_atom(pred, ref, aliases=()) -> bool:
    if numeric(ref):
        return numeric(pred) and abs(Decimal(str(pred)) - Decimal(str(ref))) <= NUMBER_EPSILON
    if isinstance(ref, str):
        forms = [ref] + [a for a in aliases if isinstance(a, str)]
        return isinstance(pred, str) and normalize(pred) in {normalize(a) for a in forms}
    return False


def _aliases_at(aliases, index):
    # Observed train shape: list/table aliases are lists aligned to reference items/rows.
    if isinstance(aliases, list) and index < len(aliases) and isinstance(aliases[index], list):
        return aliases[index]
    return []


def _row_set(rows):
    # Evaluation says rows are a set. Keep canonical raw duplicates once.
    result = []
    seen = set()
    for row in rows:
        key = tuple((type(v).__name__, v) for v in row)
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result


def match_table(pred, ref, aliases) -> bool:
    pc, rc = pred["columns"], ref["columns"]
    if len(pc) != len(rc):
        return False
    pn, rn = [normalize(c) for c in pc], [normalize(c) for c in rc]
    # If all normalized names form the same unique set, reorder; otherwise positional fallback.
    if len(set(pn)) == len(pn) and len(set(rn)) == len(rn) and set(pn) == set(rn):
        order = [pn.index(c) for c in rn]
    else:
        order = list(range(len(rc)))
    prows = _row_set([[row[i] for i in order] for row in pred["rows"]])
    rrows = _row_set(ref["rows"])
    if len(prows) != len(rrows):
        return False
    # Preserve aliases for the original reference row, including after exact deduplication.
    original_indices = [ref["rows"].index(row) for row in rrows]
    edges = []
    for row in prows:
        compatible = []
        for j, target in enumerate(rrows):
            row_aliases = _aliases_at(aliases, original_indices[j])
            if all(match_atom(p, r, row_aliases if k == 0 else []) for k, (p, r) in enumerate(zip(row, target))):
                compatible.append(j)
        edges.append(compatible)
    # Bipartite matching handles duplicate names/overlapping accepted aliases correctly.
    assigned = {}

    def augment(i, visited):
        for j in edges[i]:
            if j in visited:
                continue
            visited.add(j)
            if j not in assigned or augment(assigned[j], visited):
                assigned[j] = i
                return True
        return False

    return all(augment(i, set()) for i in range(len(prows)))


def score_answer(pred: dict | None, ref: dict) -> int:
    validate_answer(ref)
    if pred is None:
        return 0
    validate_answer(pred)
    if pred["type"] == "abstain":
        return 0
    if pred["type"] != ref["type"]:
        return -1
    kind, p, r = ref["type"], pred.get("answer"), ref.get("answer")
    aliases = ref.get("alias", [])
    if kind == "unanswerable":
        equal = True
    elif kind == "percent":
        equal = rounded(p) == rounded(r)
    elif kind in ("boolean", "date"):
        equal = p == r
    elif kind == "list":
        equal = len(p) == len(r) and all(match_atom(x, y, _aliases_at(aliases, i)) for i, (x, y) in enumerate(zip(p, r)))
    elif kind == "table":
        equal = match_table(p, r, aliases)
    else:
        equal = match_atom(p, r, aliases)
    return 1 if equal else -1


def metrics(scores) -> dict:
    counts = Counter(scores)
    n = sum(counts.values())
    c, w, a = counts[1], counts[-1], counts[0]
    return {"N": n, "correct": c, "wrong": w, "abstain": a,
            "PA": (c - w) / n if n else None,
            "coverage": (c + w) / n if n else None,
            "answered_accuracy": c / (c + w) if c + w else None,
            "wrong_rate": w / n if n else None}


def evaluate(questions: list[dict], references: list[dict], predictions: list[dict]) -> tuple[dict, list[dict]]:
    def indexed(records, label):
        result = {}
        for record in records:
            if record["id"] in result:
                raise ContractError(f"Duplicate {label} id: {record['id']}")
            result[record["id"]] = record
        return result

    qi, refs, preds = indexed(questions, "question"), indexed(references, "reference"), indexed(predictions, "prediction")
    if set(qi) != set(refs):
        raise ContractError("Reference IDs must exactly match evaluation question IDs")
    if set(preds) - set(qi):
        raise ContractError("Prediction contains unknown/out-of-subset IDs")
    for r in references + predictions:
        validate_answer(r)
    rows = []
    groups = {"business": defaultdict(list), "type": defaultdict(list)}
    for question in questions:
        key = question["id"]
        score = score_answer(preds.get(key), refs[key])
        row = {"id": key, "business_id": question["business_id"], "reference_type": refs[key]["type"],
               "prediction_type": preds.get(key, {}).get("type", "missing"), "score": score}
        rows.append(row)
        groups["business"][question["business_id"]].append(score)
        groups["type"][refs[key]["type"]].append(score)
    result = metrics(r["score"] for r in rows)
    result["slices"] = {group: {k: metrics(v) for k, v in sorted(values.items())} for group, values in groups.items()}
    business_scores = [v["PA"] for v in result["slices"]["business"].values()]
    result["business_macro_PA"] = sum(business_scores) / len(business_scores) if business_scores else None
    result["scorer_version"] = SCORER_VERSION
    result["official_scorer"] = False
    return result, rows
