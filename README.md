# Credit Risk Pipeline 🏦

> **⚠️ REPOSITÓRIO EM DESENVOLVIMENTO**  
> Pipeline completa de engenharia de dados + ML para modelagem de risco de crédito.

## 🎯 **Objetivo**
Montar **end-to-end** pipeline desde ingestão até predição de risco de crédito usando dataset **Home Credit**.

RAW → Bronze → Silver → Gold → ABT → Análise Público → Modelo Final
↓
[RAW concluído 👇]

## 🏗️ **Etapas Planejadas**

| Etapa | Status | Descrição |
|-------|--------|-----------|
| **1. RAW** | 🟢 **Concluído** | Ingestão + governança automática |
| **2. Bronze** | 🟢 **Concluído** | Rastreabilidade + append-only|
| **3. Silver** | 🟡 **Planejado** | Integração + limpeza |
| **4. Gold** | 🟡 **Planejado** | ABT (Analytical Base Table) |
| **5. Análise** | 🟡 **Planejado** | Análise público-alvo |
| **6. Modelagem** | 🟡 **Planejado** | Modelo preditivo risco crédito |
| **7. Produção** | 🟡 **Planejado** | Monitoramento + retrain |

## 📂 **Estrutura Atual**

data/raw/ # Dados brutos
docs/raw/ # Governança RAW
│ ├── datadictionary/ # Schema + profiling
│ ├── dataquality/ # Quality gates
│ ├── observability/ # Metrics + alerts
│ ├── lineage/ # Proveniência
│ └── governance/ # Inventário datasets
src/ingest/ # Scripts
└── run_raw_mvp.py # Orquestrador RAW

## 🚀 **Teste Rápido (RAW Layer)**

```bash
# Instalar
pip install pyspark kaggle

# Credenciais (opcional - repo root)
# kaggle.com/account → kaggle.json

# Executar
python src/ingest/raw_download.py  # Download dados
python run_raw_mvp.py              # Gerar docs

# Ver resultados
ls docs/raw/
cat docs/raw/datadictionary/README.md
```
## *📋 O que o RAW já faz*
Profiling: Schema, %null, unique values

Quality: Gates automáticos (YAML configurable)

Metrics: Bytes, linhas estimadas, alerts

Lineage: Hashes SHA256 + git commit

Inventory: Catálogo datasets + feature definitions

## *🛣️ Roadmap*

1. RAW ✅           (Governança completa)
2. Bronze ✅        (Parquet puro + run_id + ingest_date + append-only)
3. Silver ⏳        (Joins + limpeza)
4. Gold ⏳          (ABT + features finais)  
5. Análise ⏳       (Público-alvo + EDA)
6. Modelagem ⏳     (Predição risco crédito)
7. Produção ⏳      (Monitoramento)

## *🤝 Contribuições*

✅ Pull requests bem-vindos!

✅ RAW funcionando 100%

✅ Issues para sugestões/bugs

📄 Licença
MIT


## 👨‍💻 Frederico Costa
## 📅 Início: Fevereiro 2026
