# Evidência F03.6 — execução repetível e aceite Silver inicial

Data local: 12/11/2026, America/Sao_Paulo. Os identificadores usam UTC e por isso
podem começar com `20261113`. Runtime isolado do projeto: Python 3.11.14,
Spark 3.5.7 e Delta 3.3.2. Dados reais Home Credit; fixtures separadas nos testes.

## Estado do projeto e lógica seguida

O objetivo é um laboratório de engenharia e análise retrospectiva de crédito:
RAW preservada → Bronze rastreável → Silver tratada/transacional → Gold com ABT
por caso e indicadores → análise reproduzível por publicação. ML, feature store,
retreinamento e AWS estão no backlog. Objetos locais, publicação histórica e CI
continuam em fases posteriores.

F00–F02 entregaram fonte real, contratos, ambiente, recorte determinístico de
50 mil casos, Bronze aprovada, protocolo de revisões e reconciliação integral.
F03.1–F03.5 entregaram catálogo, leitura protegida, tratamentos conservadores,
três tabelas Delta iniciais e 29 checks persistidos. A lacuna encontrada era o
aceite operacional consolidado: os comandos de materialização e contrato eram
separados e o manifesto técnico permanecia explicitamente pendente.

As regras mantidas nesta entrega preservam colunas, tipos numéricos, códigos,
nulos, valores e grãos. Somente 23 datas são convertidas, com guarda de perda e
comparação integral nos dois sentidos. Histórico 0:N é válido; a futura ABT
precisará agregá-lo antes do join. Datas posteriores à decisão são diagnóstico,
sem garantia de disponibilidade point-in-time. Métricas de fevereiro presentes
em `docs/observability/metrics/` são registros históricos do fluxo antigo e não
aceite atual do recorte.

## Execução real

```bash
bash scripts/project.sh -m src.pipelines.run_silver_initial \
  --sample 7d58bbdaa00cbabfbce54d26
```

Tentativa inicial: `20261113T004139Z_0b4e6b9a`, `passed`, `reused=false`.
Duração do core: **64,026 s**, sem incluir criação/encerramento da sessão Spark.
Foram aprovados os **29 checks** e **315.390 linhas**, sem descarte, perda de
datas ou diferença na reconciliação da materialização.

Pacote: `data/silver/samples/7d58bbdaa00cbabfbce54d26/initial/c47f99f6e0518861d8dc468b/`.
SHA-256 do manifesto técnico:
`00a4984a7425b602dab331e1e189a666f7b64dfdc0dfe2dcd4ad1470035afa50`.

| Tabela | Linhas | Versão | UUID Delta |
|---|---:|---:|---|
| credit_cases | 50.000 | 0 | 2e5e0d44-5231-45fb-9564-bbc053abdfe6 |
| credit_static | 50.000 | 0 | e4874ef8-98be-46e4-a4c6-05e71b7a151a |
| previous_applications | 215.390 | 0 | b0b865af-4abd-432d-ac26-f816d17afe04 |

Relatório: `artifacts/silver_runs/20261113T004139Z_0b4e6b9a.json`.
Recibo: `data/silver/samples/7d58bbdaa00cbabfbce54d26/acceptances/20261113T004139Z_0b4e6b9a.json`.
A auditoria `verify_acceptance` aprovou o vínculo com relatório, manifesto e
arquivos. O manifesto técnico não foi editado para marcar aceite.

Reexecução do mesmo comando: `20261113T005300Z_b7ae23e3`, `passed`,
`reused=true`, **55,500 s** no core, com os mesmos 29 checks e 315.390 linhas.
Comparação automatizada confirmou manifesto integralmente igual, mesmo hash,
UUIDs, versões e contagens. Os dois recibos passaram na auditoria; o primeiro
permaneceu preservado.

Recusa explícita no mesmo recorte:

```bash
bash scripts/project.sh -m src.pipelines.run_silver_initial \
  --sample 7d58bbdaa00cbabfbce54d26 --existing error
```

Tentativa `20261113T005451Z_28b93aff`: saída **1**, relatório `failed` na etapa
`materialization`, erro `FileExistsError`, **38,383 s** no core. Nenhum recibo
novo foi emitido. Os dois recibos anteriores foram auditados novamente e
continuaram aprovados, com mesmo pacote e manifesto. Falhas posteriores ao
commit/contrato foram exercitadas nas fixtures, sem corromper os dados reais.

O pacote histórico `41dabc26e228d2527ee553e8` foi preservado, com o mesmo hash
`2f33015dd965fff7352f37f55e3874822beb9cedeb2a416ee40b760d2e713ae3`.
O novo pacote decorre da mudança do writer para aceitar `existing=reuse|error`:
o hash de código integra a identidade de materialização. O gate Bronze também
permaneceu com hash
`3c3a3ac440a1e6b3c87d14a5d988476f5ca517a4245eefce8dab8434a06a8ecc`.

## Código executado

Sem commit desta entrega; os relatórios registram hashes dos módulos e definições.

| Arquivo | SHA-256 |
|---|---|
| src/pipelines/run_silver_initial.py | 96563e7a68f4ef4182edf55fb0283155e45248b42aceeb1e1f8ed7589040020c |
| src/silver/acceptance.py | 3b71af48d99bbc68b549b9c1043765312f425bab70dfddf7b68565e00a589725 |
| src/silver/initial_delta.py | 75a9a8b9a2f960c04e30577cb282e6fc3773c67bc0c1a0f1baf09f6b9cb1408a |

## Testes e falhas

Quatro testes de diagnóstico verificam identificador inválido antes da JVM,
rejeição de `run_id` reutilizado sem editar o relatório anterior, relatório de
falha ao iniciar Spark e código de saída não zero do CLI.

A suíte Delta isolada passou inicialmente em **15 cenários**, em **114,519 s**,
sem ignorados. Nove cobrem a materialização e seis cobrem a execução completa:

- Criação, retry, versões/UUIDs preservados e recusa por `--existing error`.
- Contrato reprovado sem recibo; retry reutiliza o pacote técnico ainda válido.
- Falha entre relatório e recibo preserva o aceite anterior; retry funciona.
- Mudança de configuração durante a validação bloqueia o aceite.
- Bronze sem gate e escritor concorrente impedem processamento/aceite.
- Recibo, relatório ou arquivo Delta alterados são recusados pela auditoria.

Esses testes usam arquivos Bronze e tabelas Delta reais com dados sintéticos.
As falhas de contrato/interrupção são injetadas explicitamente; os contratos
em si também possuem os oráculos independentes da entrega F03.5. A restauração
de fixtures no mesmo path limpa o cache Delta entre os cenários para não
confundir uma tabela de teste removida com a tabela recriada naquele endereço.

Runner final:

```bash
bash scripts/project.sh scripts/run_tests.py --integration-required
```

**114 verificações aprovadas em 301,601 s, nenhuma ignorada**, incluindo a
verificação que exige o sucesso dos **15 cenários Delta** em JVM isolada.
Os quatro testes de diagnóstico foram incluídos no runner. `git diff --check`
e os links locais da documentação atualizada também passaram.

O sandbox impediu inicialmente os sockets locais da JVM. A execução foi
repetida com a permissão de ambiente necessária, sem substituir integração por
mocks ou aceitar skips. Os JARs já estavam no cache; não houve download Kaggle.

Logs privados: `/tmp/credit-risk-f036-delta.log`,
`/tmp/credit-risk-f036-real.log`, `/tmp/credit-risk-f036-real-retry.log`,
`/tmp/credit-risk-f036-real-existing-error.log` e
`/tmp/credit-risk-f036-all-tests.log`.

## Alcance

F03.6 aceita: execução parametrizada, criação/reutilização, contratos e falhas
demonstrados; F03 concluída no escopo Silver inicial local. O roteiro passa a
**24/72 itens e 4/12 fases aceitas**.

Manual operacional em [EXECUCAO_INICIAL.md](../silver/EXECUCAO_INICIAL.md).
O recibo aceita o snapshot Silver inicial, com seleção e pacote explícitos.
Não há ponteiro global de publicação, merge incremental, ABT ou integração
com objetos nesta entrega. F04.1 é o próximo trabalho: gerar lotes reais e
fixtures declaradas de correção, atraso e duplicação usando o protocolo de F02.4.
Depois vêm precedência, deduplicação, merge e reconciliação de reconstrução;
F05 tratará publicação/recuperação entre gerações antes da Gold em F06.
