#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
export JAVA_HOME="${JAVA_HOME:-$PROJECT_ROOT/.runtime/java/jdk-17.0.21+9-jre}"
export PATH="$JAVA_HOME/bin:$PROJECT_ROOT/.venv/bin:$PATH"
export PYSPARK_PYTHON="$PROJECT_ROOT/.venv/bin/python"
export PYSPARK_DRIVER_PYTHON="$PYSPARK_PYTHON"
export SPARK_LOCAL_IP="${SPARK_LOCAL_IP:-127.0.0.1}"
export KAGGLE_CONFIG_DIR="${KAGGLE_CONFIG_DIR:-$PROJECT_ROOT/.kaggle}"
mkdir -p "$KAGGLE_CONFIG_DIR"
if [[ -z "${KAGGLE_API_TOKEN:-}" && -f "$KAGGLE_CONFIG_DIR/access_token" ]]; then
  # O SDK aceita caminho de arquivo nesta variável; o token não passa pelo shell.
  export KAGGLE_API_TOKEN="$KAGGLE_CONFIG_DIR/access_token"
fi
if [[ ! -x "$PYSPARK_PYTHON" ]]; then
  echo 'Ambiente ausente: execute bash scripts/bootstrap_environment.sh' >&2
  exit 1
fi
exec "$PYSPARK_PYTHON" "$@"
