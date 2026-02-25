# Credit Risk Pipeline 🏦

> **⚠️ REPOSITÓRIO EM DESENVOLVIMENTO**  
> Pipeline completa de engenharia de dados + ML para modelagem de risco de crédito.

## 🎯 **Objetivo**
Montar **end-to-end** pipeline desde ingestão até predição de risco de crédito usando dataset **Home Credit**.

RAW → Silver → Gold → ABT → Análise Público → Modelo Final
↓
[RAW concluído 👇]

## 🏗️ **Etapas Planejadas**

| Etapa | Status | Descrição |
|-------|--------|-----------|
| **1. RAW** | 🟢 **Concluído** | Ingestão + governança automática |
| **2. Silver** | 🟡 **Planejado** | Integração + limpeza |
| **3. Gold** | 🟡 **Planejado** | ABT (Analytical Base Table) |
| **4. Análise** | 🟡 **Planejado** | Análise público-alvo |
| **5. Modelagem** | 🟡 **Planejado** | Modelo preditivo risco crédito |
| **6. Produção** | 🟡 **Planejado** | Monitoramento + retrain |

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
📋 O que o RAW já faz
Profiling: Schema, %null, unique values

Quality: Gates automáticos (YAML configurable)

Metrics: Bytes, linhas estimadas, alerts

Lineage: Hashes SHA256 + git commit

Inventory: Catálogo datasets + feature definitions

🛣️ Roadmap
text
1. RAW ✅           (Governança completa)
2. Silver ⏳        (Joins + limpeza)
3. Gold ⏳          (ABT + features finais)  
4. Análise ⏳       (Público-alvo + EDA)
5. Modelagem ⏳     (Predição risco crédito)
6. Produção ⏳      (Monitoramento)
🤝 Contribuições

✅ Pull requests bem-vindos!

✅ RAW funcionando 100%

✅ Issues para sugestões/bugs

📄 Licença
MIT

👨‍💻 Frederico Costa
📅 Início: Fevereiro 2026
