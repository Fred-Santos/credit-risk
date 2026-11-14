# F09.3 — métricas da operação

O [supervisor](ESTADOS_E_ERROS.md) mantém tempos e recursos em
`artifacts/f09/operations/<operation_id>.json`. Cada tentativa liga seu resultado
a `artifacts/f09/runs/<run_id>.json`, que contém as métricas do processamento.
Os arquivos se complementam: medir somente o executor exclui iniciar/encerrar
Spark e serviço, além da espera entre tentativas.

## Duração e escopo

`timing.total_seconds` e `timing.stage_seconds` usam `time.perf_counter`, relógio
monotônico. A soma das etapas exclusivas coincide com o total medido. Reentrar
numa etapa soma seu tempo; `intervals` preserva a sequência original.

No supervisor, a medição cobre desde a inicialização do relatório até o fim da
operação: configuração, serviço, Spark, processamento, cleanup e retry_wait.
Não inclui instalar dependências, imports e parsing do CLI. Há também timing
por tentativa. No executor, mede entradas, espelho/leitura dos pacotes,
incremento, reconciliação, publicação e coleta adicional de métricas.

| Etapa do executor | O que está incluído |
|---|---|
| inputs | Configuração, contratos e conferência dos snapshots de entrada |
| mirror_inputs | Conferência/cópia do espelho e leitura/contagens do catálogo de pacotes |
| incremental | Classificação, tratamentos, métricas planejadas, MERGE e contratos persistidos |
| reconciliation | Reconstrução independente, comparações, contagens, referências e conferência pré-publicação |
| publication | Silver gerenciada, Gold, validações, manifesto/ativação e conferência final do espelho |
| metrics_collection | Listagem adicional S3, consolidação de contadores e conferência de saída do contexto da entrada F04 |

`metrics_collection` identifica a janela da coleta, incluindo a guarda final
do contexto F04, que já existia antes da instrumentação. Portanto não é uma
medição isolada do custo da listagem S3. O amostrador de
recursos registra separadamente `sampling_work_seconds`, tempo de trabalho em
thread concorrente, que não deve ser somado ao tempo da operação nem subtraído
para alegar velocidade sem instrumentação. O custo de atualização de relatórios
permanece nas etapas em que ocorre.

As etapas incremental e publication já incluem ações de contagem e validação
necessárias aos contratos. Seus tempos **não são tempo puro de transformação**.
A instrumentação não separa individualmente cada count/check interno desses
componentes. Comparar update com replay ajuda a observar custo de validação sem
novos commits, mas não constitui benchmark controlado ou prova de causalidade.

## Linhas e entregas

`input_metrics` informa quantos pacotes do catálogo foram lidos, quantos foram
selecionados e o tamanho lógico do espelho. A partir da F10.5, a implementação seleciona os metadados do limite antes
de abrir os Parquets dos pacotes; o catálogo inteiro continua vinculado ao
relatório F04 aprovado e o espelho completo é conferido por hash. A leitura
tipada restringe-se aos pacotes selecionados. Execuções anteriores à F10.5
liam o catálogo inteiro, podendo registrar mais pacotes lidos que aplicados.
Tamanho do espelho não é tráfego de rede: um espelho reutilizado ainda é lido e
conferido por hash, sem implicar reenvio desses bytes.

`row_metrics.tables` soma somente os lotes concluídos e aprovados nesta execução:

- input_deliveries: entregas recebidas, incluindo reenvios;
- duplicate_deliveries: entregas repetidas da mesma revisão;
- superseded_revisions: revisões superadas na seleção de candidatos;
- inserts/updates: ações conferidas com os commits Delta;
- ignored_same_revision/ignored_older_revision: candidatos sem mudança aceita.

As entregas se repartem entre duplicadas, revisões superadas e essas quatro
ações sobre candidatos. Uma entrega não equivale a uma chave de negócio única.
O replay deve ter inserts/updates zero, mesmo que receba muitas entregas.
`counts` registra as linhas finais das três Silver; as linhas da Gold estão
em `publication_metrics.tables`. Não somar contagens finais com entregas.

Não há descarte silencioso ou quarentena por linha. Sucesso tem rejected_rows=0.
Na falha, `partial_row_metrics` contém somente lotes já concluídos e
rejected_rows=null: ausência de contagem não significa zero. Commits de um lote
interrompido podem existir e são inspecionados pelo mecanismo de retomada;
contadores parciais não alegam contar esses commits ainda não consolidados.

## Arquivos, bytes e memória

`publication_metrics` lista objetos sob as cinco tabelas aprovadas: linhas,
quantidade de objetos e arquivos, Parquets, logs e bytes lógicos. Marcadores
de diretório (chaves terminadas em `/`) aparecem em directory_markers e objects,
mas são excluídos de files, parquet_files e delta_log_files. Inclui versões
retidas dentro desses prefixos. Não é tamanho físico de disco nem quantidade de
bytes novos escritos na tentativa. Não inclui outras publicações, entradas ou
o estado de trabalho. Não remover versões para melhorar uma métrica.

`resources` do supervisor amostra RSS do processo e descendentes Linux a cada
0,5 s, incluindo Spark e serviço iniciado por ele. Serviço que já estava ativo
fica fora dessa árvore. RSS pode somar páginas compartilhadas e perder picos
curtos. Registrar samples, errors, intervalo e escopo junto ao pico; não é
memória heap, memória de todo o host nem limite de RAM garantido.

Métricas ficam também nas falhas e cancelamentos tratados. Encerramento forçado
ou armazenamento de relatórios indisponível pode impedir sua consolidação.
A instrumentação não muda as regras de negócio, retenção ou os limites de um
host/driver cooperante. O [inventário F09.4](LINEAGE_E_INVENTARIO.md) consolida lineage e referências entre etapas.
