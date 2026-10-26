#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
python_bin="${PYTHON_BIN:-python3}"
if [[ ! -f train/questions.jsonl || ! -f train/answers.jsonl ]]; then
  echo 'Unpack train.tar.gz into the repo (or copy the original train folder) before full CPU tests.' >&2
  exit 2
fi
export PYTHONPATH="$repo_root/src${PYTHONPATH:+:$PYTHONPATH}"
"$python_bin" -m unittest discover -s tests -v
