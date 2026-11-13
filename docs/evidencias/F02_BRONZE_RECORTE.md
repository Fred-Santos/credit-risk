# Evidência — entrada explícita e recuperação Bronze

Data: 12/11/2026. Aceite F02.3 no ambiente Linux/WSL da sessão.

## Entrada e execução

Seleção: `7d58bbdaa00cbabfbce54d26`, validada na entrega anterior.
Saída: `data/bronze/samples/7d58bbdaa00cbabfbce54d26/`.
Relatórios: `artifacts/bronze/samples/7d58bbdaa00cbabfbce54d26/`.

```bash
bash scripts/project.sh -m src.pipelines.run_bronze_mvp --sample 7d58bbdaa00cbabfbce54d26
bash scripts/project.sh -m src.pipelines.run_bronze_mvp --sample 7d58bbdaa00cbabfbce54d26
bash scripts/project.sh scripts/run_tests.py --integration-required
```

| Execução | Run ID | Datasets gravados | Duração da função |
|---|---|---:|---:|
| Primeira | `20261112T192324Z_cd25cc8e` | 3 | 11,429 s |
| Reexecução | `20261112T194601Z_d5de686a` | 0 | 6,714 s |

Os tempos excluem criação da sessão Spark/preflight e são medidos até validar
os dados e gerar metadados, antes das gravações finais de controle. Não constituem
benchmark comparativo nem incluem download ou materialização do recorte.

## Resultados reais

| Dataset | Linhas Bronze | Esperadas no manifesto do recorte |
|---|---:|---:|
| `train_base` | 50.000 | 50.000 |
| `train_static_0` | 50.000 | 50.000 |
| `train_applprev_1` | 215.390 | 215.390 |

As duas execuções passaram nas **24 regras atuais de qualidade**, com zero
falhas e zero avisos. Três arquivos de dados e três manifestos de ingestão v2
foram confirmados. Não restaram Parquets em staging após as tentativas normais.

`_READY.json` passou a referenciar a reexecução, enquanto os manifestos de arquivo
continuaram com o `run_id` da primeira carga. Os arquivos confirmados foram
verificados por checksum e não regravados no retry.

A configuração RAW original permaneceu `data/raw`. Os fingerprints dos seis
arquivos originais foram novamente conferidos contra o contrato e coincidiram.
O recorte teve seus arquivos e manifesto verificados antes/depois da carga.
Nenhum arquivo de dados real foi alterado para provocar falhas nos testes.

## Testes de recuperação e isolamento

Suíte obrigatória: **51 testes aprovados, nenhum ignorado**, em 37,826 s.
Os nove testes adicionados cobrem:

| Cenário | Evidência observada com fixtures |
|---|---|
| Vínculo de duas seleções e modo RAW | Pastas de dados/relatórios distintas; `raw_dir` original preservado |
| ID inválido, entrada não aprovada ou corrompida | Rejeição antes da ingestão |
| Primeira carga e repetição | Contagens corretas, nenhuma nova gravação, metadados iniciais preservados |
| Exceção após a escrita Spark em staging | Dataset incompleto não publicado; commit anterior preservado e pulado no retry |
| Exceção após rename de publicação | Commit reconhecido no retry, sem duplicação; `_READY` ausente até aprovação |
| Regra de qualidade inválida na fixture | Relatório `failed`, sem `_READY`; após corrigir a regra, retry aprova sem regravar dados |
| Locks mantidos por processo separado | Escritor concorrente recusado; morte do detentor libera o lock para carga posterior |
| Corrupção da saída já confirmada | Retry bloqueado; arquivo não sobrescrito e marcador de conclusão retirado |

Os testes de escrita, qualidade e retomada usam Parquets e DataFrames Spark reais
com dados sintéticos pequenos. O produtor da fixture emula o manifesto mínimo
de um snapshot, para testar o protocolo consumidor sem depender do Kaggle.
Os números de linhas da tabela anterior vieram da execução com Home Credit real.

## Rastreabilidade e artefatos

Cada namespace tem `_input.json`. Cada arquivo confirmado tem `_ingestion.json`
com origem/checksum, primeiro run e checksums de saída. O relatório por execução
registra código, regra de qualidade, estado, erro quando houver, contagens e
referências aos artefatos. O marcador `_READY.json` vincula esses registros à
execução verificadora final.

O lineage informa a origem imediata no recorte e a referência à RAW original.
Métricas e inventário ficam isolados por seleção. A Bronze continua em Parquet;
esses manifestos não constituem um log transacional Delta.

## Critério de aceite e próxima entrega

F02.3 foi aceita pela entrada explícita, isolamento, primeira carga/reexecução,
recuperação com Spark real, bloqueio de concorrência e ausência de aprovação
da execução incompleta. Não foi alegada atomicidade da execução inteira.

F02.4 segue pendente: contrato de eventos/revisões e precedência, separado da
chave de negócio do snapshot. F02.5 alinhará as regras Bronze ao novo contrato;
F02.6 comparará valores/proveniência de forma completa. Contagens coincidentes
e checksums de saída não substituem essa reconciliação de negócio.
