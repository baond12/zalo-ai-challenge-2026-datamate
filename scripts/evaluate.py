#!/usr/bin/env python3
"""Score train subsets without using a predictor or opening holdout by default."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from datamate.evaluation import evaluate
from datamate.io import ContractError, read_jsonl, sha256, write_json, write_jsonl


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, default=Path("train"))
    parser.add_argument("--splits", type=Path, required=True)
    parser.add_argument("--subset", choices=["development", "holdout", "fold0", "fold1", "fold2", "fold3"], default="development")
    parser.add_argument("--allow-holdout", action="store_true")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.subset == "holdout" and not args.allow_holdout:
        parser.error("Holdout locked; require checkpoint authorization and --allow-holdout. Log exposure.")
    if args.output.exists():
        parser.error("Output must be fresh; do not overwrite evidence")
    split = json.loads(args.splits.read_text())
    lock_path = args.splits.parent / "LOCK.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text())
        if Path(lock["manifest"]).name == args.splits.name and sha256(args.splits) != lock["sha256"]:
            raise ContractError("Frozen split checksum mismatch")
    businesses = split["holdout_businesses"] if args.subset == "holdout" else split["development_businesses"]
    if args.subset.startswith("fold"):
        businesses = split["folds"][int(args.subset[-1])]["validation_businesses"]
    questions = [q for q in read_jsonl(args.train / "questions.jsonl") if q["business_id"] in businesses]
    if not questions:
        raise ContractError("Selected evaluation subset is empty")
    ids = {q["id"] for q in questions}
    # References are present in a shared train file; only selected records enter scoring.
    references = [r for r in read_jsonl(args.train / "answers.jsonl") if r["id"] in ids]
    predictions = read_jsonl(args.predictions)
    result, scores = evaluate(questions, references, predictions)
    result["provenance"] = {"subset": args.subset, "split_sha256": sha256(args.splits),
                            "questions_sha256": sha256(args.train / 'questions.jsonl'),
                            "references_sha256": sha256(args.train / 'answers.jsonl'),
                            "predictions_sha256": sha256(args.predictions)}
    write_json(args.output / "metrics.json", result)
    write_jsonl(args.output / "scores.jsonl", scores)
    print(json.dumps({k: v for k, v in result.items() if k != "slices"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except ContractError as exc:
        sys.exit(str(exc))
