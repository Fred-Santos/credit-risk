# Evidência F03.5 — contratos Silver persistidos

Data: 12/11/2026. Runtime isolado local: Python 3.11.14, Spark 3.5.7 e Delta 3.3.2.
Validação somente por leitura do pacote inicial; nenhuma versão/tabela regravada.

## Identificação e comandos

```bash
bash scripts/project.sh -m src.pipelines.validate_silver_initial \
  --sample 7d58bbdaa00cbabfbce54d26 \
  --materialization 41dabc26e228d2527ee553e8
bash scripts/project.sh -m unittest discover -s tests -p test_silver_contracts.py -v
bash scripts/project.sh scripts/run_tests.py --integration-required
```

Run real: **`20261112T235339Z_754a4873`**, status `passed`.
Relatório privado:
`artifacts/silver_contract_validation/20261112T235339Z_754a4873.json`.

Pacote: `41dabc26e228d2527ee553e8`, seleção `7d58bbdaa00cbabfbce54d26`.
Manifesto técnico consumido: SHA-256
`2f33015dd965fff7352f37f55e3874822beb9cedeb2a416ee40b760d2e713ae3`.
As três tabelas foram lidas em versão 0, com os mesmos UUIDs registrados em F03.4.

| Artefato | SHA-256 |
|---|---|
| configs/contracts/silver_initial_v1.yaml | `14d41984e2c5199a999d4891fe0da89937d4303ecfcb03bf8bfbcfba465bf769` |
| src/quality/silver_contracts.py | `9dedce4088e9cde1409cd7f720aad9c42566a0dd816513dbcd4da6d2ee315cc4` |
| src/pipelines/validate_silver_initial.py | `96588f6a4eab9d9ed217419b838c6990a63cc29a76f61a355230cf397c199f51` |
| Snapshot fixado | `091e65bbee8e1c0907dd9bf23cf9b07dae512f62c3ecd99935a53c728c722cb6` |
| Política Silver preservada | `240fada60e8b7dde4a32c7fcd70f8029ea5335735f8eb54a11e172a41b6d1de2` |

Código ainda sem commit desta entrega. O relatório registra o contrato compilado,
hashes, input, versões, UUIDs e cada check. Definição e limites em
[SILVER_INICIAL.md](../contratos/SILVER_INICIAL.md).

## Esperado e obtido

**29 checks obrigatórios aprovados, zero falhas; 315.390 linhas aceitas, zero
descartadas.** Schemas exatos derivados do contrato/política, não apenas do
manifesto do writer: 226 campos no total, com 23 datas de negócio e três
ocorrências de `_ingest_date` nativas.

| Tabela | Linhas | Casos distintos | Grupos de chave duplicados |
|---|---|---|---|
| credit_cases | 50.000 | 50.000 | 0 |
| credit_static | 50.000 | 50.000 | 0 |
| previous_applications | 215.390 | 40.076 | 0 |

Nenhum nulo obrigatório/metadado vazio. Target, semana, mês da decisão e índice
de grupo atenderam aos domínios. Nulos opcionais foram preservados e perfilados,
sem imputação. O índice exige mínimo zero, sem impor teto pelo perfil observado.

| Relacionamento | Órfãos | Casos da base sem correspondência | Linhas no left join da base | Máximo de linhas por caso coberto |
|---|---|---|---|---|
| credit_static → credit_cases | 0 | 0 | 50.000 | 1 |
| previous_applications → credit_cases | 0 | 9.924 | 225.314 | 20 |

O filho unido à base manteve 50.000 linhas na estática e 215.390 no histórico.
A expansão do left join da base com o histórico é medida, sem reprovação:
o contrato admite 0:N observações por caso. Isso reforça a necessidade de
agregação antes do join da futura ABT. Nenhum desses joins regravou dados.

## Diagnóstico temporal

Foram contadas datas auxiliares posteriores à decisão por coluna. Exemplos:
`credit_static.dtlastpmtallstes_4499206D`: 4.156 linhas;
`previous_applications.dtlastpmtallstes_3545839D`: 11.608 observações.
As contagens completas estão no relatório, junto com os intervalos de datas.

Esses números são **diagnóstico**, não falha de contrato nem contagem agregável
de clientes distintos. Não houve filtro, exclusão ou nulificação. A disponibilidade
point-in-time continua sem comprovação; o produto é retrospectivo.

## Testes e oráculos

Nove testes novos em `tests/test_silver_contracts.py`, aprovados isoladamente em
53,575 s: configuração/hashes e regras suportadas; schema derivado; oráculo de
cardinalidades/datas posteriores; histórico vazio versus ausente; chave composta
duplicada/nula; órfãos e cobertura estática; schema de data/coluna extra;
domínios/calendário/metadados e contagem divergente da seleção.

O oráculo usa três casos, três linhas estáticas e três observações: dois casos
cobertos, um sem histórico, máximo de duas observações por caso e quatro linhas
no left join direto base/histórico. As expectativas são declaradas à mão.

A suíte isolada Delta ganhou um nono cenário: contratos aplicados sobre tabelas
persistidas, com schemas esperados definidos separadamente do writer e resultado
esperado de 2+2+3 linhas. O runner exige o sucesso dos nove cenários, sem skips.
Fixtures não dependem de dados Home Credit nem credenciais.

Logs: `/tmp/credit-risk-silver-contract-tests.log`,
`/tmp/credit-risk-silver-contract-real.log` e `/tmp/credit-risk-tests-f035.log`.
Runner completo: **110 verificações aprovadas em 276,091 s, nenhuma ignorada**,
incluindo a verificação da suíte Delta isolada de nove cenários. O log registra
o sucesso da suíte interna e o resultado final do runner.

## Aceite e pendências

F03.5 aceita: contratos do estado persistido e diagnóstico documentados. Logs,
manifesto técnico, UUIDs, versões e gate Bronze preservados. Não foi criado
`_READY` Silver; o status técnico do pacote permanece pendente de aceite global.

F03.6 consolidará a execução repetível e o aceite operacional, usando o pacote
e o resultado de contrato explicitamente vinculados. Não alterar o manifesto
imutável para simular uma aprovação, nem iniciar a Gold só com este relatório.
