#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
python3 -m pip install --target .runtime/bootstrap uv==0.9.9
export UV_CACHE_DIR="$PROJECT_ROOT/.runtime/uv-cache"
export UV_PYTHON_BIN_DIR="$PROJECT_ROOT/.runtime/bin"
UV="$PROJECT_ROOT/.runtime/bootstrap/bin/uv"
"$UV" python install 3.11.14 --install-dir "$PROJECT_ROOT/.runtime/python"
"$UV" venv .venv --allow-existing --python "$PROJECT_ROOT/.runtime/python/cpython-3.11.14-linux-x86_64-gnu/bin/python3.11"
"$UV" pip sync requirements.lock --python .venv/bin/python --require-hashes
.venv/bin/python scripts/install_java.py
echo 'Ambiente preparado. Valide: bash scripts/project.sh -m src.pipelines.check_environment'
