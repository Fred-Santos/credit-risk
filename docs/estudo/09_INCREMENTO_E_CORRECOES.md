# 9 — Lotes incrementais, eventos e correções

[Percurso](../GUIA_ESTUDO_LAKEHOUSE.md) · Anterior: [Delta](08_DELTA_E_EXECUCAO.md)

Objetivo: prever como novas entradas e correções devem atualizar o estado.
Pré-requisito: chaves, versões, idempotência e persistência Delta.

Estado: contrato de eventos e pequenos pacotes validados em F02.4; entrega
incremental completa, merge e reconstrução equivalentes validados em F04.
Publicação histórica e recuperação locais foram validadas em F05/F06.

## Snapshot, evento e entrega

Um **snapshot** descreve um estado do conjunto. Um **evento** representa uma
revisão identificada de um registro. Uma **entrega** é o envio desse evento em
um lote. O mesmo evento pode ser entregue mais de uma vez sem representar duas
alterações de negócio.

No projeto, a fonte adquirida é estática. Geraremos lotes, correções e atrasos
como simulações declaradas. Isso não é **CDC real**, a captura das mudanças
ocorridas num sistema operacional de origem.

Precisamos distinguir quatro identificadores: chave de negócio, revisão de
origem, identidade do evento e identidade da entrega. `run_id` ainda identifica
a tentativa técnica que processa a entrada; versão Delta identifica o estado
resultante da tabela.

## Precedência: qual alteração deve prevalecer?

Exemplo sintético de um caso, com valor monetário apenas ilustrativo:

| Chegada | Revisão | Valor | Resultado esperado |
|---|---|---|---|
| A | 1 | 10 | Inserir |
| B | 2 | 12 | Atualizar para 12 |
| Reenvio de A | 1 | 10 | Preservar revisão 2 |
| Reenvio de B | 2 | 12 | Preservar o mesmo estado |
| C | 2 | 99 | Rejeitar conflito na mesma revisão |

O horário de chegada não deve fazer uma revisão antiga vencer a nova.
Data do negócio, chegada técnica e disponibilidade do atributo também são
conceitos diferentes. O contrato usa revisão de origem explícita na simulação.

## Deduplicação, merge e ausência

**Deduplicação** identifica repetições e aplica uma escolha definida. Antes
de um merge, precisamos ter no máximo uma atualização elegível por chave e
detectar payloads conflitantes. Escolher arbitrariamente “a primeira linha”
pode produzir resultados dependentes da ordem física do lote.

**Merge/upsert** combina inserção e atualização por condição. A chave precisa
respeitar o grão, inclusive `case_id/num_group1` no histórico. A ausência de
uma linha em lote parcial não significa exclusão. O contrato atual proíbe
inferir delete dessa ausência.

**Idempotência** exige que reenvio não duplique o efeito de negócio. Para provar
correção do incremental, compararemos seu resultado com uma reconstrução a
partir das mesmas entradas e regras, em ambas as direções.

## Leitura guiada do que já existe

Abra [home_credit_events_v1.yaml](../../configs/contracts/home_credit_events_v1.yaml).
Leia `event_identity`, `delivery_identity` e `policies`. Depois, em
[event_contracts.py](../../src/quality/event_contracts.py), siga `make_event`,
`check_revision_history` e `revision_action`.

Essas funções definem e verificam o protocolo. Em
[event_batches.py](../../src/bronze/event_batches.py), observe `publish_batch`:
a landing local preserva pacotes e rejeita mudança no conteúdo do mesmo lote.
A implementação de referência usa pequenos pacotes em memória; sua existência
não demonstra transporte e merge do recorte completo.

## O que F04 construiu

A [política de lotes](../RECORTE_E_LOTES.md) atribui intervalos de `WEEK_NUM`
0–51, 52–77 e 78–91. Cada caso e suas auxiliares devem acompanhar o lote correto.
A coorte permanece fixa, para não confundir mudança de população com efeito
de correção.

A Silver inicial F03 usou o snapshot completo do recorte como prova inicial.
A demonstração incremental usa outro estado, vazio no início, e aplica os
pacotes por ordem de recebimento. A landing é preparada antes dos merges;
somente o lote aplicado altera o estado. Conferir conflitos no histórico não
insere antecipadamente os dados dos lotes futuros.

A [evidência F02.4](../evidencias/F02_EVENTOS_REVISOES.md) comprova o protocolo
de referência. A [evidência F04](../evidencias/F04_INCREMENTAL.md) comprova o
replay completo: 315.398 entregas, 315.390 linhas finais e zero diferenças na
reconstrução. O caso atrasado chegou com oito observações históricas; as duas
correções atualizaram uma estática e uma observação histórica de outro caso.

## Acompanhar a implementação F04

O [manual incremental](../silver/INCREMENTAL.md) descreve o fluxo completo
validado. Para ligar os conceitos ao código, siga este caminho:

1. Em [run_incremental_demo.py](../../src/pipelines/run_incremental_demo.py),
   leia `generate_demo`. Observe como o caso atrasado fica fora dos três lotes
   baseline e como a correção altera somente duas linhas auxiliares.
2. Em [event_parquet.py](../../src/bronze/event_parquet.py), siga `encode_events`
   e `publish_packet`. O transporte é Parquet, mas os hashes continuam usando
   a codificação Python tipada do contrato anterior, executada nos workers.
3. Em [incremental.py](../../src/silver/incremental.py), leia `deduplicate`.
   O conflito é verificado antes da janela por chave/revisão. O desempate por
   entrega só acontece entre valores e proveniências concordantes.
4. Siga `apply_packet` até o `merge`. As condições de revisão, os inserts e
   updates medidos explicam o que realmente pode modificar a tabela Delta.
   Sem alteração elegível, o comando não executa um commit vazio.
5. Compare com `reconstruct`: o oráculo usa máximo agrupado e join, em vez da
   janela e do merge. `reconcile_state` exige igualdade de todas as colunas.

O estado persistido guarda identidade de evento e revisão. Lote, cenário e
posição continuam na landing, que preserva todas as entregas. Essa separação
permite reconstruir o mesmo estado independentemente da entrega escolhida entre
cópias do mesmo evento. Os metadados Bronze continuam indicando a origem pai.

Na fixture de teste, o caso 1 tem duas observações históricas. Corrigir a
observação `(1,0)` deve preservar `(1,1)`. O caso 2, retido do primeiro lote,
chega depois dos demais e ainda pertence ao seu período original. Esses dois
resultados podem ser calculados à mão antes de executar Spark.

F06 consome três snapshots aprovados dessa evolução: baseline, corrected e late.
A [Gold](../../src/gold/publish.py) compara as três entradas Silver da publicação
pai com as novas e recalcula os casos afetados. Corrigir uma observação histórica
modifica a ABT do caso, sem duplicar sua linha ou depender de uma alteração na
base principal. Os meses original e novo são registrados; os indicadores SQL
são materializados novamente. Veja o capítulo seguinte para ligar o merge Silver
à entrega analítica.

## Atividade e conferência

Um caso já está na revisão 3. Chegam revisões 2 e 4, fora de ordem. Qual estado
deve prevalecer? E se chegarem dois valores diferentes para a revisão 4?

**Conferência:** revisão 4 prevalece independentemente da ordem de entrega;
revisão 2 não reverte estado. Dois payloads diferentes na mesma revisão são
conflito e devem impedir o aceite conforme a política, sem desempate arbitrário.

Próximo: [10 — Gold e análise](10_GOLD_E_ANALISE.md).
