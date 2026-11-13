#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
bash scripts/project.sh scripts/install_object_store.py
python3 -m pip --python .venv/bin/python install --target .runtime/object-python \
  --upgrade --only-binary=:all: --require-hashes -r requirements.objects.lock
