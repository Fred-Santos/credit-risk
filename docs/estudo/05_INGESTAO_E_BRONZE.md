# 5 — Aquisição, recorte e ingestão Bronze

[Percurso](../GUIA_ESTUDO_LAKEHOUSE.md) · Anterior: [Spark](04_SPARK_E_PARQUET.md)

Objetivo: reconstruir o caminho dos arquivos recebidos até a Bronze aprovada.
Pré-requisito: arquivos, DataFrames, chaves e ambiente de execução.

## Aquisição e identidade da origem

Uma **API** expõe operações de um serviço para programas. O cliente Kaggle
autenticado permite adquirir os arquivos selecionados da competição. Autenticar
a conta, ter acesso à competição e avaliar condições de uso são responsabilidades
distintas da transformação dos dados.

O downloader seleciona seis arquivos em vez de baixar toda a competição.
Registra tamanho e **SHA-256**, um hash que permite detectar alteração de bytes.
Mesmo nome de arquivo não prova mesmo conteúdo. Um hash também não comprova
significado, qualidade ou anonimização dos dados.

Na RAW preservamos os arquivos adquiridos. `feature_definitions.csv` descreve
campos; os Parquets carregam as linhas das tabelas. A inspeção mede schemas,
chaves, contagens e período antes de fechar regras de processamento.

## Por que materializamos um recorte

A origem tem mais de 1,5 milhão de casos na base. Para desenvolver com custo
controlado, selecionamos até 50 mil por uma regra determinística: calculamos
o hash de uma seed fixa combinada com `case_id`, ordenamos e escolhemos os
primeiros. Repetir a regra sobre a mesma população mantém a seleção.

Depois preservamos todas as linhas auxiliares desses casos com **semi-joins**.
Um semi-join filtra a esquerda pelas chaves existentes na direita, sem trazer
as colunas da direita. Amostrar cada auxiliar independentemente poderia perder
relações necessárias à análise.

O recorte fica separado da RAW. `target` não participa da seleção, e a regra
não garante representatividade estatística da carteira. Isso será uma limitação
explícita das análises.

## O que a Bronze acrescenta

A Bronze preserva os valores e adiciona `_run_id`, `_ingest_date`,
`_source_file` e `ingest_batch`. Esses **metadados** descrevem a ingestão.
`run_id` identifica uma tentativa; um batch identifica uma unidade de entrada.
Um retry pode gerar outro relatório sem regravar os dados do batch já válido.

Para escrever com segurança local, a pipeline usa:

- **Staging:** pasta temporária onde prepara a saída.
- **Manifesto:** registro de origem, saída e hashes necessários à verificação.
- **Lock:** exclusão entre programas cooperantes para evitar escritores concorrentes.
- **Rename:** publicação local da pasta preparada, sob as condições do filesystem.
- **Gate `_READY.json`:** indicação de aprovação Bronze após as verificações.

Um commit de arquivo pode existir antes do aceite da execução inteira.
**Idempotência** significa repetir sem duplicar o efeito de negócio. O retry
confere o que já existe; um arquivo alterado não é aceito apenas por ter o mesmo nome.

## Leitura guiada da execução

1. Em [download_home_credit.py](../../src/pipelines/download_home_credit.py),
   siga `download_selected` e a função `sha256`.
2. Em [build_sample.py](../../src/pipelines/build_sample.py), siga
   `select_cases` e depois `build_sample`: filtro das auxiliares, validação,
   escrita temporária, reconciliação e publicação.
3. Em [build_bronze.py](../../src/bronze/build_bronze.py), observe
   `_add_bronze_columns` e `_materialize`: metadados e compromisso de escrita.
4. Em [run_bronze_mvp.py](../../src/pipelines/run_bronze_mvp.py), leia
   `run_bronze` até a gravação do gate. Identifique as verificações anteriores.

## Resultados e continuidade

O recorte tem 50.000 casos, 50.000 registros estáticos e 215.390 observações
históricas. A Bronze usa namespace separado por seleção. Criação, repetição e
falhas foram exercitadas. Consulte a [evidência do recorte](../evidencias/F00_CONTRATOS_RECORTE.md)
e a [evidência Bronze](../evidencias/F02_BRONZE_RECORTE.md).

Os três lotes temporais foram atribuídos ao recorte e entregues/processados
em F04, estudada no capítulo 9. O replay Parquet e o estado incremental usam
namespaces próprios, preservando esta Bronze e o snapshot Silver F03.

## Atividade e conferência

Uma tentativa gravou dois de três batches e falhou antes do gate. O que o retry
deve fazer? O consumidor Silver pode assumir aprovação pela presença dos Parquets?

**Conferência:** verificar os batches já publicados, reutilizar os válidos,
concluir o faltante e repetir os checks. A Silver deve exigir o gate aprovado
e seus vínculos. Existência física de arquivos não prova aceite completo.

Próximo: [6 — Qualidade e governança](06_QUALIDADE_E_GOVERNANCA.md).
