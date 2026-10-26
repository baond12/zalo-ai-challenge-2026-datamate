#!/usr/bin/env python3
"""Full train scan; creates a fresh evidence directory."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from datamate.audit import audit_train

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = audit_train(args.root.resolve(), args.output)
    print(summary)
    sys.exit(0 if summary["status"] == "completed" else 1)
