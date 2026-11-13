# Evidência F04 — lotes, revisões, merge e reconstrução

Data local: 12/11/2026, America/Sao_Paulo. Runtime do projeto: Python 3.11.14,
Java 17, Spark 3.5.7 e Delta 3.3.2. Identificadores de execução usam UTC.

Status: **F04.1–F04.6 aceitas no escopo local**. Suíte completa, execução real,
idempotência e reconstrução aprovadas. O roteiro passa a **30/72 itens e 5/12 fases**.

## Escopo implementado

| Item | Implementação e prova exigida |
|---|---|
| F04.1 | Três lotes temporais reais; correção, duplicata e caso atrasado separados; baseline reconciliado à Bronze |
| F04.2 | Maior revisão prevalece; conflito na mesma revisão rejeita lote, inclusive quando antiga |
| F04.3 | Deduplicação determinística por chave composta/revisão; entregas duplicadas e revisões suplantadas medidas |
| F04.4 | Merge Delta insere novas chaves e atualiza apenas revisão maior; ausência em lote parcial preserva linhas |
| F04.5 | Retry, duplicatas e revisão antiga preservam todos os valores, versões e diagnósticos; atraso entra no período original |
| F04.6 | Reconstrução independente por máximo agrupado/join; comparação integral nos dois sentidos com o estado incremental |

Código: [gerador/execução](../../src/pipelines/run_incremental_demo.py),
[transporte Parquet](../../src/bronze/event_parquet.py) e
[motor incremental](../../src/silver/incremental.py).
Política e limites: [manual F04](../silver/INCREMENTAL.md).

## Testes aprovados

```bash
bash scripts/project.sh scripts/run_tests.py --integration-required
```

Resultado: **117 verificações aprovadas em 927,001 s, nenhuma ignorada**.
O runner inclui uma verificação da suíte Delta anterior de 15 cenários e uma
da nova suíte F04 de nove cenários, ambas executadas em JVM própria. Os números
das suítes internas não devem ser somados ao total do runner como verificações
do mesmo nível. Dois testes novos cobrem configuração e diagnóstico de falha.

A suíte F04 usa quatro casos, quatro linhas estáticas e quatro observações
históricas sintéticas, com valores esperados calculados separadamente:

- Compatibilidade de hashes v1 no transporte distribuído, com Unicode, nulos,
  booleano e normalização de zero com sinal.
- Cobertura integral do baseline e retenção do caso 2 para chegada atrasada.
- Merge e reconstrução coincidentes com o oráculo: estática do caso 1 passa
  de 10 para 11; observação `(1,0)` passa de 5 para 6; `(1,1)` continua nula.
- Deduplicação com entrada embaralhada/reparticionada e preservação da chave composta.
- Recusa do lote inteiro com conflito de revisão antiga, após aplicar a revisão 2.
- Retry com mesmos valores, versões, manifesto e primeiro recibo de aplicação.
- Recusa de arquivo corrompido e estado sem vínculo, preservando o destino existente.
- Data auxiliar inválida bloqueia todas as escritas antes de qualquer novo commit.
- Correção apenas nas auxiliares preserva base e observações ausentes do pacote parcial.

Log final: `/tmp/credit-risk-f04-all-tests.log`. As integrações usam Spark,
Parquet e Delta reais. As fixtures não requerem credenciais nem dados Kaggle.

## Preparação da execução real

Recorte: `7d58bbdaa00cbabfbce54d26`, com 50.000 casos, 50.000 linhas estáticas
e 215.390 observações históricas. A RAW, o recorte e o gate Bronze não são
reescritos. Os pacotes Silver F03 permanecem no namespace `initial`.

Antes da execução, foram registrados checksums da origem e dos manifestos, e
conferidos dados/logs Delta dos pacotes F03 contra seus inventários. A referência
privada está em `/tmp/credit-risk-f04-before.json` para comparação posterior.

Comando operacional medido:

```bash
bash scripts/project.sh scripts/measure_resources.py \
  --output artifacts/f04/resources_first.json \
  --workdir data/silver/samples/7d58bbdaa00cbabfbce54d26/incremental \
  -- bash scripts/project.sh -m src.pipelines.run_incremental_demo \
  --sample 7d58bbdaa00cbabfbce54d26
```

O gerador usa a Bronze aprovada e prova a conservação do baseline nos dois
sentidos. As únicas alterações de negócio declaradas são +1.0 na estática e
em uma observação histórica do caso de correção. O caso atrasado e todas as
suas auxiliares são retirados do primeiro lote e entregues somente no último
pacote. Todos os envelopes registram simulação, origem, cenário, lote e revisão.

## Aplicação dos pacotes reais

Stream: `f04_166f033caaf6f5564446deb1`. O caso retido tem uma linha na base,
uma estática e oito observações históricas. Os recibos de aplicação registram:

| Pacote | Inserts base/estática/histórico | Updates base/estática/histórico | Duração da aplicação |
|---|---|---|---|
| b00_w000_051 | 35.045 / 35.045 / 136.679 | 0 / 0 / 0 | 117,359 s |
| b01_w052_077 | 10.022 / 10.022 / 50.044 | 0 / 0 / 0 | 74,822 s |
| b02_w078_091 | 4.932 / 4.932 / 28.659 | 0 / 0 / 0 | 58,119 s |
| correction_r2 | 0 / 0 / 0 | 0 / 1 / 1 | 46,097 s |
| duplicate_r2 | 0 / 0 / 0 | 0 / 0 / 0 | 32,397 s |
| old_revision_r1 | 0 / 0 / 0 | 0 / 0 / 0 | 35,971 s |
| late_case_r1 | 1 / 1 / 8 | 0 / 0 / 0 | 44,806 s |

Essas durações incluem classificação, tratamento, merge quando necessário e
contratos persistidos, sem isolar o tempo de merge. A primeira inclui a criação
das três tabelas vazias. O custo total também inclui geração, reconciliações,
diagnósticos e retry; não se resume à soma da coluna acima.

O pacote duplicado preserva quatro entregas na landing, deduplica duas cópias
dentro do lote e ignora duas candidatas de revisão já aplicada. O pacote antigo
ignora duas candidatas de revisão 1, preservando a revisão 2. Nenhum desses
pacotes produz commit Delta novo. A base continua na versão 3 durante a correção;
apenas as duas auxiliares avançam à versão 4. O atraso leva às versões 4/5/5.

As sete entregas aceitas somam 315.398 envelopes; a população de negócio final
permanece em 315.390 linhas, com as duas alterações simuladas declaradas. Os
contratos foram aprovados após cada lote, com ausência legítima de histórico
permitida e sem mudança de grão.

## Resultado final, retry e reconstrução

Execução: **`20261113T020347Z_1609747b`**, status `passed`, código de saída 0.
Relatório: `artifacts/f04/runs/20261113T020347Z_1609747b.json`.
Resumo privado: `artifacts/f04/summary.json`.

| Tabela | Linhas finais | Versão Delta | UUID |
|---|---:|---:|---|
| credit_cases | 50.000 | 4 | 946cd420-fbc0-4171-9e00-36473b236098 |
| credit_static | 50.000 | 5 | 6be7159c-3622-4a56-8f25-6aabc945d40b |
| previous_applications | 215.390 | 5 | 26fc9aa0-2d8a-437c-bab8-e7031194683b |

Os **29 checks finais** passaram, com 315.390 linhas aceitas. Existem 40.076
casos com histórico; a ausência nos demais é permitida pelo contrato.

O primeiro lote foi reaplicado após toda a sequência em **94,049 s**. O recibo
foi reutilizado sem reescrita; inserts e updates ficaram em zero. Na estática
e no histórico, uma candidata antiga por tabela foi ignorada; as demais já
estavam na mesma revisão. Todas as colunas, os diagnósticos e as versões
4/5/5 permaneceram iguais nos snapshots comparados.

A reconstrução lógica integral por máximo agrupado/join produziu **zero linhas
faltantes e zero extras em cada tabela**, comparando todas as colunas com o
estado Delta. A prova do baseline contra a Bronze também teve zero diferenças
nas três tabelas. O lote contraditório na revisão antiga foi recusado e não
existe na landing aceita.

## Recursos e reestimativa de capacidade

Medição: `artifacts/f04/resources_first.json`, com amostragem a cada 0,1 s e
10.668 amostras. Log operacional: `/tmp/credit-risk-f04-real.log`.

| Medida | Resultado |
|---|---:|
| Duração do core | 1.133,059 s — 18 min 53 s |
| Processo completo, incluindo sessão Spark | 1.138,779 s — 18 min 59 s |
| Pico de RSS somado da árvore de processos | 5.432.700.928 bytes — 5,06 GiB |
| Pico de bytes lógicos no namespace incremental | 68.294.223 bytes — 65,13 MiB |
| Landing Parquet ao final | 75,28 MiB |
| Landing + estado, incluindo logs/arquivos retidos | 140,41 MiB |

O heap de driver permaneceu em 2g, com `local[2]`; o RSS reúne Java, Python e
workers, e pode contar páginas compartilhadas mais de uma vez. A amostragem
pode perder picos curtos. Disco mede arquivos lógicos nos diretórios indicados,
sem incluir caches do sistema, temporários Spark ou blocos físicos de disco.

O comando executa validações de envelope, histórico, valores, contratos,
idempotência e reconstrução, além dos merges. Esses tempos não medem a latência
de uma atualização Delta isolada nem sustentam alegação de escala distribuída.
Não houve aumento de paralelismo, heap ou tamanho do recorte, nem falha de
processamento na execução real.

Com esta medição, um ciclo de runner completo mais demonstração real custa
aproximadamente **34,4 minutos**, antes do tempo de implementação. Permanecem
42 itens e sete fases. A próxima parcela de esforço concentra-se em evolução,
publicação/recuperação entre tabelas, Gold e adaptação a objetos. Não há base
para converter a contagem do roteiro em horas totais de desenvolvimento.
Mantemos o recorte atual; otimização orientada por perfil continua em F10.5.

## Preservação e código executado

`artifacts/f04/protected_inputs_check.json` registra `passed`: RAW, manifesto
do recorte, gate Bronze e manifestos/arquivos/logs dos dois pacotes F03 coincidem
com a referência anterior. Os dois recibos Silver F03 também foram auditados e
continuam válidos. Nenhuma publicação Gold foi criada.

A auditoria final também repetiu `bind_sample`/`verify_approval`, conferindo
integralmente os arquivos do recorte e a cadeia de aprovação Bronze após F04.
Hashes de código/configuração coincidem com o relatório executado; os links da
documentação, a contagem de 30/72 itens e `git diff --check` passaram.

Código ainda sem commit desta entrega; os hashes identificam o executado:

| Arquivo | SHA-256 |
|---|---|
| src/pipelines/run_incremental_demo.py | 917eeb06b1977ae3076969a1bd14aef2a511887fb5de0838e7cf30a204cb16a1 |
| src/bronze/event_parquet.py | 5e89f892d296d406fe3ec2a9e6d5c8d837ee7f159eb7cdb5605cef0b43fcc3bb |
| src/silver/incremental.py | 4290788d48b5f4c7167eec884aae14b53adb076f6b0f45922f4fc4f227c80c15 |
| configs/incremental_policy_v1.yaml | 8e61ccc91cbd32f2f342208c84be85f3417d809a4bdaa2ad924d6e128982a927 |

O relatório operacional guarda os hashes das demais dependências, contratos e
configurações. O aceite F04 se refere a esse experimento identificado.

## Limites de interpretação e continuidade

As contagens mensais e de cobertura no relatório são diagnósticos de
idempotência, sem produzir indicadores Gold ou análise de risco. Os dados
corrigidos são simulações identificadas, não novas observações Home Credit.

O estado F04 é uma área de trabalho mutável por experimento. Recibos por lote
não implementam uma publicação global para consumidores Gold. Evolução de
schema, ponteiro de publicação, matriz completa de falhas/retomada e retenção
continuam em F05. Locks, rename e hard links são mecanismos locais; objetos
ficam em F08. Não há transação global entre tabelas ou CDC real.

Próxima entrega: **F05.1**, evolução de schema controlada, com nova coluna
autorizada e rejeição de mudanças incompatíveis, versão/migração e testes.
