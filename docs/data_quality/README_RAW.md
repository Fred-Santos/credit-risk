# Qualidade RAW e Bronze

As regras ficam em `configs/quality_rules.yaml` e `configs/quality_rules_bronze.yaml`.
O padrão `defaults.action_on_fail` fornece a severidade quando a regra a omite.
Uma regra com `severity: fail` sempre interrompe o pipeline em caso de falha,
mesmo quando o padrão é `warn`. Falhas `warn` são registradas sem interromper.

Checks: `non_empty` (`nonempty` também aceito), `require_columns`, `not_null`,
`column_types`, `unique`, `allowed_values` e `foreign_key`. Checks desconhecidos
ou severidades inválidas são erros de configuração. Erros ao executar checks
bloqueiam a execução. Camadas vazias também falham.

Na RAW, os padrões correspondem ao caminho relativo do arquivo. Na Bronze,
correspondem ao nome do diretório do dataset, como `train_base`. Cada dataset
Bronze é lido inteiro para verificar duplicatas entre arquivos/lotes. A numeração
de shards não define a granularidade da chave. A configuração explicita as
famílias de tabelas e suas chaves; novos nomes precisam de revisão dessas regras.
As verificações de unicidade não unem shards armazenados em datasets distintos.

A Bronze exige `train_base`, metadados de origem e `case_id` não nulos, tipos
esperados, chaves por granularidade e referências válidas a `train_base`.
O alvo de `train_base` deve ser 0 ou 1. As chaves compostas são contratos
explícitos: falhas devem ser investigadas nos dados antes de flexibilizar regras.

Relatórios são gravados antes da exceção em:

- `docs/data_quality/results/<run_id>_raw_checks.json`
- `docs/data_quality/bronze_results/<run_id>_bronze_checks.json`

Incluem `run_id`, `failed_checks`, `warning_checks` e resultados individuais.

Execute `python3 -m unittest discover -s tests -v`. Os testes de integração
Spark são executados quando PySpark está instalado e requerem Java configurado.
