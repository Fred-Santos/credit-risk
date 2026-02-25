# Observability - RAW Metrics

**Run ID**: `20260225T134256-abcd1234`

## 📈 KPIs Monitorados

| Métrica | Descrição | Alert se |
|---------|-----------|----------|
| **Total Bytes** | Soma `data/raw/` | Drop >30% |
| **File Count** | Total arquivos | Arquivos faltando |
| **Row Estimates** | Amostragem 2% | - |
| **Duration** | Tempo pipeline | - |

## 🚨 Alerts Automáticos
🔴 FAIL: missing_files

🟡 WARN: new_files, bytes_drop

## 📊 Últimos Runs
latest_rawmetrics.json ← Atualizado sempre
runid_rawmetrics.json ← Run específico
runid_rawalerts.json ← Diferenças vs anterior
