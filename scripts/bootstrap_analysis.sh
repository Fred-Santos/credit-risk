#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
if [[ ! -x .venv/bin/python ]]; then
  echo 'Prepare primeiro o ambiente principal: bash scripts/bootstrap_environment.sh' >&2
  exit 1
fi
# O pip do sistema instala wheels para o interpretador 3.11 já preparado.
# O target separado não modifica .venv ou o lock do processamento.
python3 -m pip --python .venv/bin/python install --target .runtime/analysis \
  --upgrade --only-binary=:all: --require-hashes -r requirements.analysis.lock
