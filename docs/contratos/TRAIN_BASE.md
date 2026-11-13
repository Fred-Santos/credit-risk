# Contrato — train_base

Versão 1. [Políticas comuns](README.md) e
[schema executável](../../configs/contracts/home_credit_v1.yaml).

Esta página descreve a origem. Na Silver, a tabela é `credit_cases` e
date_decision passa a date, sem estreitar os tipos numéricos. Contrato persistido
em [SILVER_INICIAL.md](SILVER_INICIAL.md).

| Item | Definição |
|---|---|
| Grão | Um caso de crédito |
| Chave | `case_id`, única e não nula |
| Fonte RAW | `parquet_files/train/train_base.parquet` |
| Mínimo de linhas | Uma |
| Relação | Tabela de referência das duas auxiliares selecionadas |

| Campo | Tipo RAW | Nulo permitido | Regra |
|---|---|---|---|
| `case_id` | bigint | Não | Chave única; não identifica necessariamente uma pessoa |
| `date_decision` | string | Não | Data válida no formato `yyyy-MM-dd` |
| `MONTH` | bigint | Não | Deve corresponder a `yyyyMM` da data de decisão |
| `WEEK_NUM` | bigint | Não | Inteiro não negativo; deve encontrar lote na política de seleção |
| `target` | bigint | Não | Domínio 0/1; rótulo retrospectivo |

O período 2019-01-01 a 2020-10-05 é uma observação da edição fixada, não um
domínio universal de datas. As semanas 0–91 orientam os lotes desta edição.
Uma ampliação da fonte exige rever a política de lotes e a versão de origem.

O recorte mantém os cinco campos originais e seus tipos. A atribuição de lote
fica em um dataset técnico separado. Datas e inteiros mais estreitos na Silver
continuam como desenvolvimento posterior.

O rótulo não deve ser usado como informação disponível na decisão original.
Ele não participa da seleção dos casos e não representa aprovação de crédito.
