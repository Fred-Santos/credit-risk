#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -d "$PROJECT_ROOT/.runtime/analysis/matplotlib" ]]; then
  echo 'Gráficos ausentes: execute bash scripts/bootstrap_analysis.sh' >&2
  exit 1
fi
export PYTHONPATH="$PROJECT_ROOT/.runtime/analysis${PYTHONPATH:+:$PYTHONPATH}"
export MPLCONFIGDIR="$PROJECT_ROOT/.runtime/analysis-mpl"
export MPLBACKEND=Agg
exec bash "$PROJECT_ROOT/scripts/project.sh" "$@"
