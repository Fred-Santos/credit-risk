#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
EXPANSION_BASE_SILVER="${1:?Informe o ID Silver base}"
EXPANSION_BASE_GOLD="${2:?Informe o ID Gold base}"
EXPANSION_BASE_ANALYSIS="${3:?Informe o ID da análise base}"
EXPANSION_CHILD_SILVER="${4:?Informe o ID Silver da correção simulada}"
for EXPANSION_INPUT_ID in "$EXPANSION_BASE_SILVER" "$EXPANSION_BASE_GOLD" "$EXPANSION_BASE_ANALYSIS" "$EXPANSION_CHILD_SILVER"; do
  [[ "$EXPANSION_INPUT_ID" =~ ^[0-9a-f]{24}$ ]] || { echo 'ID inválido' >&2; exit 1; }
done
bash scripts/project.sh scripts/measure_resources.py --output artifacts/expansion/e07_corrected_audit_resources.json --workdir .runtime/tmp/expansion-stages -- .venv/bin/python -m scripts.run_expansion audit --silver-id "$EXPANSION_CHILD_SILVER"
bash scripts/project.sh scripts/measure_resources.py --output artifacts/expansion/e07_corrected_gold_resources.json --workdir .runtime/tmp/expansion-stages -- .venv/bin/python -m scripts.run_expansion gold --silver-id "$EXPANSION_CHILD_SILVER"
EXPANSION_CHILD_GOLD="$(bash scripts/project.sh -c 'import json,pathlib,sys; matches=[json.loads(p.read_text())["id"] for p in pathlib.Path("data/gold/expansion").glob("*/_gold.json") if json.loads(p.read_text())["identity"]["silver_id"]==sys.argv[1]]; assert len(matches)==1,matches; print(matches[0])' "$EXPANSION_CHILD_SILVER")"
bash scripts/analysis.sh scripts/measure_resources.py --output artifacts/expansion/e07_corrected_analysis_resources.json --workdir .runtime/tmp/expansion-stages -- .venv/bin/python -m scripts.run_expansion analysis --silver-id "$EXPANSION_CHILD_SILVER" --gold-id "$EXPANSION_CHILD_GOLD"
EXPANSION_CHILD_ANALYSIS="$(bash scripts/project.sh -c 'import json,pathlib,sys; matches=[json.loads(p.read_text())["id"] for p in pathlib.Path("data/gold/expansion-analysis").glob("*/_analysis.json") if json.loads(p.read_text())["gold_id"]==sys.argv[1]]; assert len(matches)==1,matches; print(matches[0])' "$EXPANSION_CHILD_GOLD")"
bash scripts/objects.sh scripts/measure_resources.py --output artifacts/expansion/e07_publication_resources.json --workdir .runtime/tmp/expansion-delivery -- .venv/bin/python -m scripts.deliver_expansion deliver --silver-id "$EXPANSION_BASE_SILVER" --gold-id "$EXPANSION_BASE_GOLD" --analysis-id "$EXPANSION_BASE_ANALYSIS" --corrected-silver-id "$EXPANSION_CHILD_SILVER" --corrected-gold-id "$EXPANSION_CHILD_GOLD" --corrected-analysis-id "$EXPANSION_CHILD_ANALYSIS"
EXPANSION_SELECTION="$(bash scripts/project.sh -c 'import json; print(json.load(open("artifacts/expansion/e07_delivery.json"))["selection_id"])')"
bash scripts/objects.sh scripts/measure_resources.py --output artifacts/expansion/e07_consumer_resources.json --workdir .runtime/tmp/expansion-delivery -- .venv/bin/python -m scripts.deliver_expansion consume --selection-id "$EXPANSION_SELECTION"
