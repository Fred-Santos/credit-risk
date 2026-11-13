# Evidência F03.4 — materialização Delta inicial

Data: 12/11/2026. Runtime local isolado: Python 3.11.14, Spark 3.5.7 e Delta
3.3.2. Recorte real `7d58bbdaa00cbabfbce54d26`, com a Bronze aprovada anterior.

## Execução e artefatos

```bash
bash scripts/project.sh -m src.pipelines.materialize_silver_initial \
  --sample 7d58bbdaa00cbabfbce54d26
bash scripts/project.sh tests/delta_initial_integration.py
bash scripts/project.sh scripts/run_tests.py --integration-required
```

Primeira execução real: **`20261112T233952Z_fa240df3`**, status `passed`,
`reused=false`. Pacote `41dabc26e228d2527ee553e8` em:
`data/silver/samples/7d58bbdaa00cbabfbce54d26/initial/41dabc26e228d2527ee553e8/`.

Manifesto técnico: `_materialization.json`, SHA-256
`2f33015dd965fff7352f37f55e3874822beb9cedeb2a416ee40b760d2e713ae3`.
Status: `materialized_pending_silver_acceptance`. Não foi criado `_READY` Silver.

| Tabela/path relativo | Linhas lidas por Delta | Versão | Operação | UUID |
|---|---|---|---|---|
| credit_cases | 50.000 | 0 | WRITE | becde333-3153-4206-aafe-1a6235f77d9d |
| credit_static | 50.000 | 0 | WRITE | fde478dc-0e92-4348-b2f4-f4224e06b6e1 |
| previous_applications | 215.390 | 0 | WRITE | 8050f829-fc03-4f86-944a-08d440a3aae5 |

Esperado e obtido: schemas tratados, 23 datas nativas, 315.390 linhas e demais
valores preservados. Leitura de volta por Delta/versionAsOf=0 produziu zero
faltas e zero excessos nos dois sentidos em cada tabela. Os paths finais
também foram consumidos pelo leitor Delta após o rename do staging.

Relatório privado:
`artifacts/silver_materialization/20261112T233952Z_fa240df3.json`, com política,
contrato, código, runtime, tratamento, manifesto e contagens consumidas.

## Versões do código

Ainda sem commit desta entrega; hashes identificam a implementação executada.

| Artefato | SHA-256 |
|---|---|
| src/silver/initial_delta.py | `d0a78580a5dbfad6daeab13da16b9e4e87272603375d37bf786a9755d575a0ce` |
| src/silver/transforms.py | `5ae7ab7378715004a097e4c346798db43ba12e69be4ed5d363092df3e39ff7da` |
| src/pipelines/materialize_silver_initial.py | `7258df70445697af3655ff7c9df5d6b29de359c7d6b8d1aa27593ded7d91a7c9` |
| configs/silver_policy_v1.yaml | `240fada60e8b7dde4a32c7fcd70f8029ea5335735f8eb54a11e172a41b6d1de2` |

A política passou a usar `implementation_status: transformations_implemented`,
que descreve a disponibilidade das funções e não o estado de um dataset.
As regras de tratamento não mudaram. Contrato do snapshot, recorte, RAW e
Bronze permanecem preservados. O gate Bronze consumido continua com hash
`3c3a3ac440a1e6b3c87d14a5d988476f5ca517a4245eefce8dab8434a06a8ecc`.

## Testes e reexecução

Suíte sintética Delta em `tests/delta_initial_integration.py`, com oito cenários:

- Ler paths finais com tipos, valores e versões corretos após mover o pacote.
- Reutilizar o pacote mantendo manifesto, primeiro run_id e versão 0.
- Bloquear conteúdo diferente sob a mesma identidade, sem sobrescrever.
- Bloquear arquivos removidos/alterados.
- Preservar diretório existente sem vínculo, recusando overwrite.
- Falhar antes do rename sem publicar pacote parcial; retry posterior funciona.
- Recusar commit externo no namespace inicial imutável.
- Demonstrar que leitura Parquet ignora remoção lógica Delta e pode contar mais linhas.

Os oito cenários passaram na execução isolada inicial em 49,860 s. Não houve
mutação dos dados reais nesses testes. A suíte roda em subprocesso com JVM
própria para carregar JARs Delta desde o início; o teste do runner principal
exige retorno bem-sucedido e nenhum cenário ignorado. Não confundir o número
de verificações do runner com o número de cenários internos desse subprocesso.

Logs da sessão: `/tmp/credit-risk-delta-initial-tests.log`,
`/tmp/credit-risk-tests-f034.log`, `/tmp/credit-risk-silver-initial.log` e
`/tmp/credit-risk-silver-initial-retry.log`.

Reexecução real: **`20261112T234204Z_b86dcb3d`**, status `passed`, `reused=true`.
Mesmo pacote, manifesto byte a byte com o mesmo hash, UUIDs e contagens. As três
versões continuaram em 0, preservando `created_by_run_id=20261112T233952Z_fa240df3`.
Não houve overwrite, novo commit ou reescrita do recibo original.

Runner completo: **101 verificações aprovadas em 280,001 s, nenhuma ignorada**,
incluindo a verificação que executou os oito cenários Delta em JVM isolada.
O arquivo de log registra o sucesso da suíte interna e o resultado do runner.

## Aceite e limites

F03.4 aceita como persistência Delta inicial e leitura verificada. Manual em
[DELTA_INICIAL.md](../silver/DELTA_INICIAL.md). Não representa aceite completo
Silver, publicação Gold ou uma transação Delta entre tabelas. O manifesto do
pacote é técnico, com aceite Silver ainda pendente.

Próximo item: F03.5, contratos explícitos do estado Silver persistido. Operação
repetível completa, novos lotes, merges, evolução de schema e recuperação entre
tabelas continuam nos itens próprios do roteiro.
