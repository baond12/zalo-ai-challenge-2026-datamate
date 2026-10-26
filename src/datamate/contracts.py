"""Interfaces for later inference stages. No model or business answer logic here."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from datamate.io import ContractError, read_jsonl, sha256


@dataclass(frozen=True)
class BusinessContext:
    business_id: str
    directory: Path
    readme: str
    data_files: tuple[Path, ...]


@dataclass(frozen=True)
class SplitContext:
    root: Path
    rulebook: str
    calendar: tuple[dict, ...]
    rulebook_sha256: str
    calendar_sha256: str
    questions: tuple[dict, ...]

    def business(self, business_id: str) -> BusinessContext:
        # Identifiers locate input directories only; never select answer algorithms.
        directory = (self.root / "data" / business_id).resolve()
        if directory.parent != (self.root / "data").resolve():
            raise ContractError("Business directory escapes data root")
        readme = directory / "README.md"
        if not readme.is_file():
            raise ContractError(f"Missing business README: {business_id}")
        files = tuple(sorted(p for p in directory.iterdir() if p.suffix in (".csv", ".xlsx", ".sqlite") and p.is_file()))
        return BusinessContext(business_id, directory, readme.read_text(encoding="utf-8"), files)


def load_split(root: Path) -> SplitContext:
    """Input-only context. Never read answers.jsonl, never fall back to train rules."""
    root = root.resolve()
    for name in ("rulebook.md", "calendar.csv", "questions.jsonl"):
        if not (root / name).is_file():
            raise ContractError(f"Missing split input: {name}")
    questions = read_jsonl(root / "questions.jsonl")
    for q in questions:
        if any(not isinstance(q.get(k), str) or not q[k] for k in ("business_id", "question", "as_of_date")):
            raise ContractError("Question fields must be nonempty strings")
        try:
            date.fromisoformat(q["as_of_date"])
        except ValueError as exc:
            raise ContractError("Invalid as_of_date") from exc
    with (root / "calendar.csv").open(encoding="utf-8-sig", newline="") as stream:
        calendar = tuple(csv.DictReader(stream))
    if not calendar or "date" not in calendar[0]:
        raise ContractError("Calendar must contain date rows")
    return SplitContext(root, (root / "rulebook.md").read_text(encoding="utf-8"), calendar,
                        sha256(root / "rulebook.md"), sha256(root / "calendar.csv"), tuple(questions))


@dataclass(frozen=True)
class QueryPlan:
    output_type: str
    operation: str
    parameters: dict
    supporting_rule_locations: tuple[str, ...]
    required_fields: tuple[str, ...]


class Planner(Protocol):
    def plan(self, question: dict, split: SplitContext, business: BusinessContext) -> QueryPlan: ...


class Executor(Protocol):
    def execute(self, plan: QueryPlan, business: BusinessContext) -> dict: ...
