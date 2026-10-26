#!/usr/bin/env python3
"""CPU verification with saved stdout, hand-designed integration fixture, integrity checks."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from datamate.io import sha256, write_json, write_jsonl


def verify(output, audit):
    if output.exists():
        raise FileExistsError("Verification output must be fresh")
    output.mkdir(parents=True)
    results = []
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}

    def run(name, command, expected_returncode=0):
        start = time.monotonic()
        process = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
        (output / f"{name}.log").write_text(process.stdout + process.stderr, encoding="utf-8")
        result = {"name": name, "command": command, "returncode": process.returncode,
                  "expected_returncode": expected_returncode, "passed": process.returncode == expected_returncode,
                  "elapsed_seconds": round(time.monotonic() - start, 4)}
        results.append(result)
        return process

    run("unittest", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp)
        train = fixture / "train"
        train.mkdir()
        refs = [
            {"id": "f01", "type": "number", "answer": 48250000},
            {"id": "f02", "type": "percent", "answer": -12.35},
            {"id": "f03", "type": "string", "answer": "Cà phê"},
            {"id": "f04", "type": "date", "answer": "2026-08"},
            {"id": "f05", "type": "boolean", "answer": False},
            {"id": "f06", "type": "list", "answer": ["Trà", "Sữa"], "alias": [["P1"], ["P2"]]},
            {"id": "f07", "type": "table", "answer": {"columns": ["khach", "no"], "rows": [["Lan", 30], ["Tú", 20]]}, "alias": [["C1"], ["C2"]]},
            {"id": "f08", "type": "unanswerable", "answer": None},
            {"id": "f09", "type": "number", "answer": 5},
            {"id": "f10", "type": "number", "answer": 7},
            {"id": "f11", "type": "number", "answer": 12},
            {"id": "f12", "type": "string", "answer": "Nước", "alias": ["P3"]}]
        predictions = [
            {"id": "f01", "type": "number", "answer": 48250000},
            {"id": "f02", "type": "percent", "answer": -12.345},
            {"id": "f03", "type": "string", "answer": "Ca phe"},
            {"id": "f04", "type": "date", "answer": "2026-08"},
            {"id": "f05", "type": "boolean", "answer": False},
            {"id": "f06", "type": "list", "answer": ["P1", "P2"]},
            {"id": "f07", "type": "table", "answer": {"columns": ["no", "khach"], "rows": [[20, "C2"], [30, "C1"]]}},
            {"id": "f08", "type": "unanswerable"},
            {"id": "f09", "type": "abstain"},
            {"id": "f11", "type": "percent", "answer": 12},
            {"id": "f12", "type": "string", "answer": "P3"}]
        write_jsonl(train / "questions.jsonl", [{"id": r["id"], "business_id": "fixture_shop", "question": "synthetic scorer test", "as_of_date": "2026-01-01"} for r in refs])
        write_jsonl(train / "answers.jsonl", refs)
        write_jsonl(fixture / "predictions.jsonl", predictions)
        write_json(fixture / "split.json", {"development_businesses": ["fixture_shop"], "holdout_businesses": ["unused"]})
        command = [sys.executable, "scripts/evaluate.py", "--train", str(train), "--splits", str(fixture / "split.json"),
                   "--predictions", str(fixture / "predictions.jsonl"), "--output", str(output / "fixture_evaluation")]
        run("fixture_cli", command)
        metrics = json.loads((output / "fixture_evaluation/metrics.json").read_text())
        expected = {"N": 12, "correct": 8, "wrong": 2, "abstain": 2, "PA": 0.5}
        results.append({"name": "hand_computed_fixture_score", "expected": expected,
                        "observed": {k: metrics[k] for k in expected}, "passed": all(metrics[k] == v for k, v in expected.items()),
                        "scope": "scorer integration only; NOT model quality"})
        write_jsonl(output / "fixture_questions.jsonl", [{"id": r["id"], "business_id": "fixture_shop"} for r in refs])
        write_jsonl(output / "fixture_references.jsonl", refs)
        write_jsonl(output / "fixture_predictions.jsonl", predictions)
        run("holdout_guard", command + ["--subset", "holdout"], expected_returncode=2)
    manifest = json.loads((audit / "input_manifest.json").read_text())
    changed = [r["path"] for r in manifest if sha256(ROOT / r["path"]) != r["sha256"]]
    results.append({"name": "raw_train_integrity", "files_checked": len(manifest), "changed_files": changed, "passed": not changed})
    source_records = []
    for directory in ("src", "scripts", "tests", "configs", "splits"):
        for path in sorted((ROOT / directory).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix in (".py", ".json", ".jsonl"):
                source_records.append({"path": str(path.relative_to(ROOT)), "sha256": sha256(path)})
    write_json(output / "code_and_config_manifest.json", source_records)
    write_json(output / "verification.json", {"status": "PASS" if all(r["passed"] for r in results) else "FAIL", "checks": results,
                                               "training_or_model_inference": False, "official_gpu_docker_validation": "NOT VERIFIED"})
    print(json.dumps({"status": "PASS" if all(r["passed"] for r in results) else "FAIL", "checks": len(results), "output": str(output)}, indent=2))
    return all(r["passed"] for r in results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()
    sys.exit(0 if verify(args.output.resolve(), args.audit) else 1)
