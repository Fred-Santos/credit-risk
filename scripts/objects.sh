#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -d "$PROJECT_ROOT/.runtime/object-python/boto3" ]]; then
  echo 'Cliente S3 ausente: execute bash scripts/bootstrap_objects.sh' >&2
  exit 1
fi
export PYTHONPATH="$PROJECT_ROOT/.runtime/object-python${PYTHONPATH:+:$PYTHONPATH}"
exec bash "$PROJECT_ROOT/scripts/project.sh" "$@"
