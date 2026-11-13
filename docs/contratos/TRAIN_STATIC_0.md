# Contrato — train_static_0

Versão 1. [Políticas comuns](README.md) e
[schema completo dos 168 campos](../../configs/contracts/home_credit_v1.yaml).

Esta página descreve a origem. Na Silver, a tabela é `credit_static`, com 15
datas nativas e demais valores/tipos preservados. Contrato persistido e
diagnóstico temporal em [SILVER_INICIAL.md](SILVER_INICIAL.md).

| Item | Definição |
|---|---|
| Grão | Um registro estático por caso de crédito |
| Shards RAW | `train_static_0_0.parquet` e `train_static_0_1.parquet`, na pasta de treino |
| Chave | `case_id` bigint, única e não nula após união dos shards |
| Referência | `case_id` deve existir em `train_base` |
| Cobertura | Todo caso da base deve ter um registro estático no snapshot publicado deste MVP |
| Mínimo de linhas | Uma |
| Atributos não chave | Presentes no schema, mas valores nulos permitidos |

Os tipos existentes são bigint, double, boolean e string. A lista de todos os
campos é mantida no YAML executável para evitar definições divergentes. Não
inferir precisão monetária, unidade ou disponibilidade temporal apenas pelo nome.

A cobertura integral foi escolhida porque os shards atuais cobrem todos os
casos e o recorte preserva os relacionados. É uma regra da publicação deste
snapshot, não uma afirmação de que todo sistema de crédito entrega todas as
fontes simultaneamente. O modelo de chegada/revisões será separado em F02.4.

Datas auxiliares permanecem strings; códigos, sentinelas e nulos não são alterados
sem validação na Silver. Campos empiricamente sem nulos não viram obrigatórios
automaticamente. Duplicatas entre arquivos devem bloquear a publicação.
