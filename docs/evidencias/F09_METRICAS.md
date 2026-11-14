# F09.3 — métricas operacionais consolidadas

Em 13/11/2026 foram acrescentados relógio monotônico por etapa/operação/tentativa,
contadores consolidados dos lotes, inventário lógico da publicação e amostragem
RSS da árvore de processos. Implementação: `src/operation/metrics.py`, executor
F09.1 e supervisor F09.2. [Dicionário e limites](../operacao/METRICAS.md).
Hashes da implementação executada estão nos relatórios dos runs aprovados.

## Execução real

Comandos de validação usam o supervisor sobre o lote `b00_w000_051`, na seleção
`7d58bbdaa00cbabfbce54d26`, com update, replay e fonte intencionalmente ausente.
O script `artifacts/f09/validation/f093/run_final.py` executa os três casos
sequencialmente e verifica as expectativas. Resultado: `results.json`, status
passed. Logs por caso no mesmo diretório. Não houve concorrência entre Spark jobs.

| Caso | Operação | Duração medida do supervisor (s) | Pico RSS somado (bytes) |
|---|---|---:|---:|
| Update | `20261113T173937Z_821632d2` | 211,212 | 5033197568 |
| Replay | `20261113T174309Z_698759ab` | 140,684 | 3777167360 |
| Fonte ausente | `20261113T174530Z_27471961` | 8,910 | 550842368 |

Update: **206.769 entregas e inserts**, zero updates, 35.045 casos, 35.045
estáticos e 136.679 históricos. A ABT tem 35.045 linhas e os indicadores 12 meses.
Replay: mesmas entregas, **zero inserts/updates**, sem novas versões ou publicação;
as entregas são classificadas como revisão já aceita. CURRENT F08 permaneceu
byte a byte igual antes/depois dos três casos. O supervisor encerrou o serviço,
preservando backend e dados reais.

A publicação selecionada contém **40 arquivos**, **45 objetos**, **74898004 bytes lógicos**. Janela de coleta e guarda final: **0,587 s** no update e **0,565 s** no replay.

Os marcadores S3A de diretório foram detectados e separados das contagens de
arquivos Parquet/log. Inventário conta os arquivos retidos nos cinco prefixos,
sem confundir bytes da publicação com tráfego, bytes novos ou blocos de disco.

Fonte ausente: código 3, uma tentativa; timing e recursos foram consolidados.
O relatório parcial registra rejected_rows=null, sem inventar zero rejeições.
As durações de etapas somam os totais medidos na operação, tentativa e executor.
Os contadores de entregas fecham com duplicatas, revisões superadas e ações.
A amostragem teve leituras válidas e nenhuma falha registrada nos três casos.

## Interpretação dos tempos

O supervisor inclui serviço, Spark, executor e cleanup, além de retry_wait quando
houver. O executor exclui essa inicialização. Incremento e publicação incluem
contagens e validações dos componentes; não são tempos puros de transformação.
A janela de coleta tem etapa própria e inclui a guarda final do contexto F04,
pré-existente; não é uma medição isolada da listagem S3. Custo de amostragem em thread é registrado
à parte e não deve ser somado ou subtraído dos tempos como correção de benchmark.
RSS amostrado pode somar páginas compartilhadas e perder picos curtos. A operação
medida não inclui bootstrap/imports/parsing do CLI; não é tempo total do shell.
Não houve experimento controlado para atribuir diferenças ao overhead da coleta.

## Testes e preservação

Três testes novos de métricas aprovados: intervalos exclusivos/repetidos,
balanço de entregas com replay e inventário com marcador de diretório. Oito
testes do supervisor foram novamente aprovados, agora conferindo os tempos
inclusive em falhas/cancelamentos, além do wrapper e dos três testes F09.1.
Não somar wrapper e cenários internos como testes do mesmo nível. A regressão
global F08 de 129 verificações continua como linha de base; não foi reexecutada
nesta alteração. A validação atual usou esses testes direcionados e os três casos
reais descritos, com provas dos hashes e da documentação ao fechar a fase.

Os produtores e resultados F00–F08 foram preservados. Novas versões de código
F09 criam outra identidade, mantendo publicações anteriores e blobs históricos.
A política de retenção e os limites de um host/driver cooperante permanecem.
Próxima: F09.4, consolidar lineage e inventário entre as etapas.
