#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
python_bin="${PYTHON_BIN:-python3.11}"
venv_dir="${VENV_DIR:-$repo_root/.venv-p100}"
torch_flavor="${TORCH_FLAVOR:-cu118}"

case "$torch_flavor" in
  cu118|cu124) ;;
  *) echo 'TORCH_FLAVOR must be cu118 or cu124.' >&2; exit 2 ;;
esac
"$python_bin" -c 'import sys; assert sys.version_info[:2] == (3, 11), "Use Python 3.11 for the pinned P100 environment"'
if [[ ! -x "$venv_dir/bin/python" ]]; then
  "$python_bin" -m venv "$venv_dir"
fi
"$venv_dir/bin/python" -c 'import sys; assert sys.version_info[:2] == (3, 11), "Existing venv is not Python 3.11"'
"$venv_dir/bin/python" -m pip install 'pip==25.1.1' 'setuptools==80.9.0' 'wheel==0.45.1'
"$venv_dir/bin/python" -m pip install 'torch==2.6.0' --index-url "https://download.pytorch.org/whl/$torch_flavor"
"$venv_dir/bin/python" -m pip install -r "$repo_root/requirements/p100.txt"
"$venv_dir/bin/python" -m pip install --no-deps --no-build-isolation -e "$repo_root"
"$venv_dir/bin/python" -m pip check
echo "Environment prepared: $venv_dir. Run scripts/gpu_preflight.py on the server next."
