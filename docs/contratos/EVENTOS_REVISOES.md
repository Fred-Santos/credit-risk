# Contrato de eventos e revisões — F02.4

Implementado em 12/11/2026. Definição executável:
[home_credit_events_v1.yaml](../../configs/contracts/home_credit_events_v1.yaml).
Ele referencia pelo SHA-256 o contrato do snapshot e reutiliza seus schemas.
Os arquivos originais, o recorte e a Bronze do snapshot permanecem imutáveis.

Atualização F04: o replay completo usa
[Parquet distribuído e merge Silver](../silver/INCREMENTAL.md), preservando
as identidades e a codificação canônica v1 deste contrato. A referência JSONL
descrita nesta página continua isolada para pequenos pacotes.

## Identidades e grãos

| Campo/conceito | Regra |
|---|---|
| Chave de negócio | `case_id` na base/estática; `(case_id,num_group1)` no histórico |
| `_source_system` | `home_credit_simulator_v1`; não representa CDC fornecido pela competição |
| `_selection_id` | Coorte determinística de 50 mil casos |
| `_stream_id` | Isola um experimento; a demonstração usa `contract_demo_v1` |
| `_source_revision` | Inteiro positivo atribuído pelo simulador; maior revisão prevalece |
| `_event_id` | SHA-256 de versão do algoritmo, origem, seleção, stream, tabela, chave e revisão |
| `_batch_id` | Identidade de um pacote imutável; conteúdo diferente exige outro ID |
| `_ordinal` | Posição não negativa, única por tabela dentro do lote |
| `_delivery_id` | SHA-256 de versão do algoritmo, origem, seleção, stream, lote, tabela e posição |
| `_payload_sha256` | SHA-256 da operação e linha completa, após normalização tipada |
| `run_id` | Tentativa técnica; guardada no recibo da primeira publicação, fora da identidade do evento |
| `receipt_index` | Ordem de recebimento local do lote; não define precedência de negócio |

A ordem dos componentes dos hashes está no `make_event` em
[event_contracts.py](../../src/quality/event_contracts.py). As chaves de negócio
entram como pares nome/valor na ordem do contrato. Não concatenamos valores sem
separadores nem dependemos da ordem física dos campos de um dicionário.

O evento identifica uma versão de negócio. A entrega identifica uma ocorrência
recebida desse evento. O mesmo evento pode chegar várias vezes; mantemos essas
entregas no histórico. Uma segunda ocorrência dentro do mesmo lote precisa de
outra posição. Repetir o mesmo arquivo/lote preserva as mesmas identidades e não
grava outra cópia. A unicidade do snapshot por chave não deve ser aplicada a
todo o histórico acumulado de eventos.

## Regras de conteúdo e precedência

O envelope v1 contém todos os campos declarados, sem extras. Só admite `upsert`
com imagem completa da linha; não aceita patch parcial, exclusão ou exclusão
inferida por ausência. Tipos e campos obrigatórios vêm do snapshot. Não verifica
cobertura total nem exige a presença da base em cada pacote de correção: essas
regras pertencem ao estado consolidado, a validar na Silver.

| Situação perante o estado atual da mesma chave | Ação de referência |
|---|---|
| Chave ainda ausente | Inserir |
| Revisão maior | Atualizar |
| Revisão menor, sem conflito no histórico | Preservar entrega; manter estado mais novo |
| Mesma revisão e mesmo hash de conteúdo | Preservar entrega; nenhum efeito adicional no estado |
| Mesma revisão e conteúdo diferente | Rejeitar todo o lote antes da publicação |

O conflito deve ser procurado em **todo o histórico aceito**, incluindo revisões
mais antigas que a atual. Caso contrário, uma revisão 1 contraditória poderia
passar despercebida depois de uma revisão 2. Não desempatar conflito por horário,
ordem de chegada, nome do arquivo ou ordem de partições Spark.

A classificação é implementada por `revision_action`; é uma referência Python.
Ainda não executa merge Delta. Uma chegada atrasada pode ser uma chave nova ou
uma revisão antiga: atraso descreve chegada, revisão define precedência.

## Origem real e simulações

Todos os envelopes têm `_is_simulated=true`: a Home Credit fornece o snapshot,
não o histórico de eventos que este laboratório constrói. `_payload_origin`
distingue `home_credit_snapshot`, `home_credit_with_simulated_change` e
`synthetic_fixture`. A última é reservada aos testes, sem substituir o recorte
real. A marcação é uma declaração do produtor; o envelope sozinho não comprova
que valores foram copiados fielmente. A demonstração lê o recorte verificado.

`baseline_replay` exige revisão 1. `correction_simulation` exige revisão >=2 e
origem `home_credit_with_simulated_change`. `late_arrival` e `duplicate_delivery`
registram a intenção do experimento; podem reenviar eventos previamente
definidos. Na demonstração, só `train_static_0.annuity_780A` recebe acréscimo
artificial de 1,0 na revisão 2. Isso testa comportamento técnico e não fornece
uma nova observação real para análise de risco.

## Codificação e integridade

`typed_python_json_v1`: JSON UTF-8, chaves ordenadas, separadores compactos e
`allow_nan=False`. `bigint` exige inteiro de 64 bits, sem aceitar boolean;
`double` normaliza números para float finito e zero para `0.0`. Nulos opcionais
são preservados. Não há arredondamento nem imputação. A base também verifica
data ISO válida, mês correspondente, semana não negativa e target 0/1.

NaN/Infinity são rejeitados neste transporte v1. Isso não altera o contrato RAW
nem cria uma política global de imputação. O recorte observado não contém NaN.
Outro serializador, inclusive Spark `to_json`, precisa provar equivalência ou
usar outra versão de codificação antes de gerar esses hashes.

## Publicação local e comandos

[event_batches.py](../../src/bronze/event_batches.py) valida envelopes, contexto,
posições e conflitos. Sob lock do stream, verifica lotes anteriores e publica
`events.jsonl` e `_batch.json` por staging seguido de rename no mesmo filesystem.
O `_stream.json` vincula o stream ao manifesto do recorte e aos contratos. Um
retry só reutiliza lote com mesmo hash canônico e arquivos íntegros. Falha antes
do rename não publica o lote. Falha depois do rename permite reconhecer o commit
na próxima tentativa. O recibo guarda a primeira execução e horário.

```bash
bash scripts/project.sh -m src.pipelines.check_event_contract \
  --sample 7d58bbdaa00cbabfbce54d26
bash scripts/project.sh scripts/run_tests.py --integration-required
```

Saída privada: `data/events/<selection_id>/contract_demo_v1/<batch_id>/`.
Relatório resumido: `artifacts/event_contract/<run_id>.json`. Esses caminhos são
ignorados pelo Git. O conflito deliberado `demo_conflict` não vira lote aceito.

## Limites de aceite

Esta landing é separada da Bronze do snapshot, sem alterar seu manifesto v2 ou
o CLI `run_bronze_mvp`. JSONL e validação integral do histórico em memória servem
aos pequenos pacotes de referência. Ainda não são o transporte ou algoritmo
distribuído dos 315.390 registros do recorte. Rename/lock locais não comprovam
garantias para armazenamento de objetos ou queda de energia; não há promessa de
atomicidade entre tabelas ou proteção contra edição maliciosa dos manifestos.

F02.5 alinhou as regras de qualidade Bronze. F02.6 reconciliou integralmente o
snapshot. F04 implementou os lotes completos, adaptação distribuída, aplicação
Silver, deduplicação e comparação com reconstrução. Seu aceite usa a
[evidência própria](../evidencias/F04_INCREMENTAL.md), além desta referência.
