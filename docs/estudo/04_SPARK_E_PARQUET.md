# 4 — Spark, DataFrames, SQL e arquivos Parquet

[Percurso](../GUIA_ESTUDO_LAKEHOUSE.md) · Anterior: [Ambiente](03_PYTHON_AMBIENTE_E_GIT.md)

Objetivo: explicar quando Spark processa os dados, como divide o trabalho e
qual o papel dos arquivos. Pré-requisito: ambiente e operações tabulares.

## DataFrame é uma representação tabular com um plano

Spark é o motor de processamento. Sua interface PySpark permite descrever
operações em Python. Um **DataFrame** representa dados com schema e um plano
de operações. Muitas transformações são avaliadas de forma **preguiçosa**:
Spark prepara o plano e executa quando uma ação exige o resultado.

Exemplo didático; `spark` representa uma sessão já preparada:

```python
casos = spark.createDataFrame([(101, 0), (102, 1)], 'case_id long, target long')
positivos = casos.filter('target = 1').select('case_id')
positivos.explain()
total = positivos.count()
```

`filter` e `select` constroem o plano. `explain` permite inspecioná-lo.
`count` exige um resultado e dispara processamento. O resultado esperado é 1.
Executar outra ação pode recalcular partes do plano; atribuir um DataFrame
a uma variável não significa persistir seus dados.

## SQL e DataFrames usam o mesmo motor

Após `casos.createOrReplaceTempView('casos_exemplo')`, uma consulta SQL pode
expressar o filtro: `SELECT case_id FROM casos_exemplo WHERE target = 1`.
A view temporária pertence à sessão. SQL e API de DataFrames são formas de
descrever operações que Spark planeja e executa.

O código produtivo atual usa principalmente a API de DataFrames. A futura Gold
terá consultas de indicadores. Conhecer as duas formas ajuda a conferir o
grão dos resultados e a ler os planos.

## Partições, shuffle e recursos

Spark divide o trabalho em **partições de execução**. Uma agregação por chave
pode redistribuir linhas entre partições, operação chamada **shuffle**. Essa
redistribuição usa CPU, memória, disco e comunicação entre componentes.

Não confunda partição de execução, pasta física por coluna e shard de origem.
Um shard é um pedaço da tabela distribuído em arquivo pela fonte. Uma pasta
como `ingest_batch=...` organiza dados físicos. Os planos Spark têm suas próprias
partições de execução, que podem mudar durante o processamento.

`collect()` traz todas as linhas para o processo Python que coordena a execução,
o **driver**. Para grandes resultados, isso pode esgotar sua memória. `count()`
retorna uma contagem, mas ainda custa processamento. Cache pode evitar trabalho
repetido; precisa ter benefício medido e ser liberado quando não for necessário.

## Parquet e tabela lógica

Parquet é um formato colunar: organiza dados por colunas dentro dos arquivos,
favorecendo leituras de subconjuntos de campos. Uma tabela lógica pode ter
vários arquivos. Conferir cada arquivo isoladamente não prova unicidade no
conjunto completo.

Na Bronze, unimos fragmentos de uma mesma tabela por nome. **Union** acrescenta
linhas de conjuntos compatíveis; **join** relaciona colunas por uma condição.
Usar união permissiva para aceitar uma coluna ausente pode esconder um desvio
de schema, então o leitor verifica cada fragmento antes de unir.

## Leitura guiada do projeto

Abra [read_bronze.py](../../src/silver/read_bronze.py), função
`open_bronze_snapshot`. Acompanhe `spark.read`, `check_schema`, `select`,
`unionByName`, `groupBy` e `count`. Relacione leitura, transformação e ação.

Observe o `with` usado pelo consumidor no
[entrypoint Silver](../../src/pipelines/run_silver_initial.py). Ele mantém a
proteção dos arquivos enquanto as ações Spark efetivamente leem os dados.
Construir um plano dentro do contexto e executá-lo depois pode deixar a leitura
fora dessa proteção.

## Evidência e atividade

A [leitura Bronze](../evidencias/F03_LEITURA_BRONZE.md) verificou 315.390 linhas
reais. O projeto roda localmente; essa prova não representa operação de cluster.

Preveja a contagem após unir dois fragmentos contendo respectivamente
`[(101,0)]` e `[(101,0),(102,1)]`. O que uma verificação de chave deve encontrar?

**Conferência:** três linhas após a união; `case_id=101` aparece duas vezes.
A união não deduplica automaticamente. A chave global deve reprovar o conjunto.

Próximo: [5 — Aquisição, recorte e Bronze](05_INGESTAO_E_BRONZE.md).
