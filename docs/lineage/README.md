# Data Lineage - RAW Pipeline

## 🔗 Fluxo Completo
Kaggle Competition → download → unzip → cleanup → RAW/
↓
[Este pipeline documenta 👇]

text

**Run ID**: `20260225T134256-abcd1234`

## 📄 Artefatos

| Artefato | Descrição |
|----------|-----------|
| [dataset_lineage.md](dataset_lineage.md) | Visão humana (top-50 arquivos) |
| `lineage_events/runid_rawlineage.json` | Evento estruturado + **SHA256 hashes** |

## 🔍 O que rastreia
✅ Input: kaggle/home-credit-credit-risk-model-stability
✅ Output: data/raw/ (X arquivos, Y GB)
✅ Git commit: abc1234
✅ Hashes: arquivo.parquet → a1b2c3d4...
✅ Timestamps UTC

text

> **🎯 Reprodutibilidade total**: Saiba exatamente o que foi baixado/gerado
