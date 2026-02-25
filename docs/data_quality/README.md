# Data Quality - RAW Gates

**Run ID**: `20260225T134256-abcd1234`

## ✅ Checks Implementados

| Check | Descrição | Severity |
|-------|-----------|----------|
| `nonempty` | Tabela tem ≥1 linha | `fail`/`warn` |
| `require_columns` | Colunas obrigatórias | `fail`/`warn` |

## ⚙️ Configuração
configs/quality_rules.yaml
↓
Pattern matching → Aplica checks específicos


## 📊 Results
docs/dataquality/results/runid_rawchecks.json
{
"failed_checks": 0,
"results": [...]
}

> **🚫 Pipeline falha** se `failed_checks > 0` + `action_on_fail=fail`

