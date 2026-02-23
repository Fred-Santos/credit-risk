param(
  [string]$RepoRoot = (Get-Location).Path
)

$ErrorActionPreference = "Stop"

function Ensure-Dir([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Path $Path | Out-Null
  }
}

function Ensure-File([string]$Path, [string]$Content = "") {
  $dir = Split-Path -Parent $Path
  Ensure-Dir $dir
  if (-not (Test-Path -LiteralPath $Path)) {
    New-Item -ItemType File -Path $Path | Out-Null
    if ($Content -ne "") {
      Set-Content -LiteralPath $Path -Value $Content -Encoding UTF8
    }
  }
}

# --- Diretórios principais ---
$dirs = @(
  "configs",
  "data\raw",
  "data\bronze",
  "data\silver",
  "data\gold",
  "notebooks",
  "src\pipelines",
  "src\profiling",
  "src\quality",
  "src\quality\expectations",
  "src\lineage",
  "src\observability",
  "src\modeling",
  "src\utils",
  "docs\governance",
  "docs\lineage\lineage_events",
  "docs\data_dictionary\tables",
  "docs\feature_store\feature_groups",
  "docs\feature_store\variable_book",
  "docs\analytics_modeling\eda",
  "docs\analytics_modeling\statistical_modeling",
  "docs\analytics_modeling\reports",
  "docs\data_quality\rules",
  "docs\data_quality\results",
  "docs\data_quality\data_docs",
  "docs\observability\metrics",
  "docs\observability\incidents"
)

foreach ($d in $dirs) {
  Ensure-Dir (Join-Path $RepoRoot $d)
}

# --- Arquivos de config (templates mínimos) ---
Ensure-File (Join-Path $RepoRoot "configs\paths.yaml") @"
repo_root: .
data:
  raw: data/raw
  bronze: data/bronze
  silver: data/silver
  gold: data/gold
docs:
  data_dictionary: docs/data_dictionary/tables
  data_quality: docs/data_quality
  lineage: docs/lineage
  observability: docs/observability
"@

Ensure-File (Join-Path $RepoRoot "configs\spark.yaml") @"
spark:
  master: local[*]
  app_name: credit-risk
"@

Ensure-File (Join-Path $RepoRoot "configs\quality_rules.yaml") @"
# Exemplo de regras (você pode mapear por tabela)
rules:
  - table: "*"
    checks:
      - type: "row_count_nonzero"
      - type: "no_duplicate_keys"
        columns: ["case_id"]
"@

Ensure-File (Join-Path $RepoRoot "configs\feature_store.yaml") @"
features:
  registry_path: docs/feature_store/feature_registry.md
"@

# --- READMEs por área (placeholders) ---
Ensure-File (Join-Path $RepoRoot "docs\governance\README.md") @"
# Data Governance

- Objetivo: definir papéis, responsabilidades, políticas e evidências.
- Artefatos gerados automaticamente devem ser versionados em `docs/`.
"@

Ensure-File (Join-Path $RepoRoot "docs\lineage\README.md") @"
# Data Lineage

- Dataset lineage e column lineage.
- Eventos e evidências em `lineage_events/`.
"@

Ensure-File (Join-Path $RepoRoot "docs\data_dictionary\README.md") @"
# Data Dictionary

- Arquivos por tabela em `tables/`.
- Este material é gerado automaticamente a partir dos parquets.
"@

Ensure-File (Join-Path $RepoRoot "docs\feature_store\README.md") @"
# Feature Store & Book de Variáveis

- Registro de features e convenções de versionamento.
- Book de variáveis em `variable_book/`.
"@

Ensure-File (Join-Path $RepoRoot "docs\analytics_modeling\README.md") @"
# Analytics & Statistical Modeling

- EDA, relatórios e experimentos de modelagem.
"@

Ensure-File (Join-Path $RepoRoot "docs\data_quality\README.md") @"
# Data Quality

- Regras em `rules/` e resultados em `results/`.
- Data Docs (se aplicável) em `data_docs/`.
"@

Ensure-File (Join-Path $RepoRoot "docs\observability\README.md") @"
# Data Observability

- Métricas e SLAs em `metrics/`.
- Incidentes e post-mortems em `incidents/`.
"@

# --- Notebooks (placeholders vazios) ---
$nb = @(
  "notebooks\00_download.ipynb",
  "notebooks\10_dictionary.ipynb",
  "notebooks\20_quality.ipynb",
  "notebooks\30_features.ipynb",
  "notebooks\40_modeling.ipynb",
  "notebooks\50_observability.ipynb"
)
foreach ($n in $nb) { Ensure-File (Join-Path $RepoRoot $n) "{}" }

# --- .gitignore sugerido ---
Ensure-File (Join-Path $RepoRoot ".gitignore") @"
# Data (não versionar)
data/raw/
data/bronze/
data/silver/
data/gold/

# Spark
**/spark-warehouse/
**/*.crc

# Python
__pycache__/
*.pyc
.venv/
.env

# Jupyter
.ipynb_checkpoints/

# Logs e outputs
logs/
"@

# --- README raiz (mínimo) ---
Ensure-File (Join-Path $RepoRoot "README.md") @"
# Credit Risk — Data Product Repo

Este repositório contém pipelines/notebooks e documentação gerada:
- Data Governance
- Data Lineage
- Data Dictionary
- Feature Store & Book de Variáveis
- Analytics & Statistical Modeling
- Data Observability
- Data Quality
"@

Write-Host "OK: estrutura criada em: $RepoRoot"
