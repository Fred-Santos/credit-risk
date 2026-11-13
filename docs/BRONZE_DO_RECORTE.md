# Bronze do recorte — entrada explícita e recuperação

Implementada e validada em Linux/WSL em 12/11/2026. Escopo: F02.3.

Atualizações posteriores: [qualidade F02.5](QUALIDADE_BRONZE.md) e
[reconciliação F02.6](RECONCILIACAO_BRONZE.md) agora fazem parte do mesmo CLI e
precedem o gate. Os resultados originais da F02.3 são históricos.

## Executar

Na raiz, para a seleção validada nesta entrega:

```bash
bash scripts/project.sh -m src.pipelines.run_bronze_mvp --sample 7d58bbdaa00cbabfbce54d26
```

Use o identificador retornado pelo construtor do recorte se houver outra seleção.
O comando exige `--sample` ou `--raw`; não escolhe uma entrada silenciosamente.
`--raw` é o modo explícito do fluxo anterior, com saída própria em `data/bronze/raw/`.
Ele não é necessário para executar esta entrega.

| Origem/saída | Local |
|---|---|
| RAW original preservada | `data/raw/` |
| Entrada imediata | `data/samples/<selection_id>/` |
| Bronze desta seleção | `data/bronze/samples/<selection_id>/` |
| Relatórios desta seleção | `artifacts/bronze/samples/<selection_id>/` |

Não modificar `configs/paths.yaml` para apontar a RAW à seleção. O
[vínculo de entrada](../src/bronze/inputs.py) cria um contexto derivado:
`raw_dir` continua apontando à origem original; `ingestion_dir` identifica a
entrada imediata. Outras seleções e o modo RAW têm namespaces separados.

## Verificação da entrada

Antes de iniciar Spark, o vínculo exige identificador válido, manifesto publicado,
identidade consistente, contrato compatível, aprovações de origem/recorte e
checksums dos arquivos da seleção. Não é preciso regenerar o recorte porque
o código de uma etapa posterior mudou.

Um `_input.json` vincula o namespace Bronze à entrada e ao hash do manifesto.
Uma pasta existente com dados sem esse vínculo é bloqueada para revisão, em vez
de ser adotada automaticamente. A entrada é novamente verificada antes da aprovação.

## Unidade de publicação e retry

O [builder](../src/bronze/build_bronze.py) mantém a publicação por arquivo:

```text
<namespace Bronze>/<dataset>/ingest_batch=<hash do caminho relativo>/
  part-*.parquet
  _SUCCESS
  _ingestion.json
```

Os dados são escritos em `.staging`, conferidos e publicados por rename no mesmo
filesystem. O manifesto de ingestão v2 registra origem, checksum, primeiro
`run_id` e checksums dos Parquets de saída. Dados e manifesto ficam visíveis juntos.

Na reexecução, origem e arquivos confirmados precisam coincidir com os registros.
Se coincidirem, o arquivo não é regravado. Saída alterada, arquivo extra ou
manifesto sem checksums bloqueia a tentativa; não há reparo destrutivo automático.
Bronze antiga sem os registros necessários deve ser revisada e reconstruída em
namespace separado, preservando a versão anterior.

Uma falha pode deixar arquivos anteriores já confirmados. O retry reconhece
esses commits e retoma os restantes. Isso produz efeito idempotente nas condições
do contrato, sem alegar transação distribuída ou rollback da execução inteira.

## Gate da execução

[run_bronze_mvp.py](../src/pipelines/run_bronze_mvp.py) grava `_READY.json` somente
após materialização, regras atuais de qualidade, contagens esperadas e geração
de métricas/lineage/inventário. O marcador registra execução verificadora,
identidade da entrada, contagens e checksums de dados/manifestos de controle.

| Estado | Marcador e dados |
|---|---|
| Entrada recusada no preflight | Nenhuma nova carga iniciada |
| Execução iniciada | `_READY.json` retirado; commits anteriores podem existir |
| Falha após iniciar | Marcador ausente; relatório `failed`; commits preservados para retry |
| Execução aprovada | Marcador `passed` e relatório com referência à entrada |

Consumidores deverão exigir a conclusão do namespace escolhido. Uma pasta com
Parquets, isoladamente, não informa se qualidade e etapas seguintes passaram.
F03 integrará esse protocolo ao consumo Silver. Para revalidar o estado atual,
repetir o comando acima; corrupção será detectada pelos checksums.

O lock `.pipeline.lock` cobre o entrypoint inteiro; `.ingestion.lock` protege o
builder. São locks locais não bloqueantes. O teste entre processos também
conferiu sua liberação após a morte do processo que mantinha o lock.

## Metadados de linha

| Campo | Significado |
|---|---|
| `_run_id` | Execução que confirmou a primeira ingestão daquele arquivo |
| `_ingest_date` | Data de ingestão no laboratório, na sessão UTC |
| `_source_file` | URI do Parquet imediato do recorte |
| `ingest_batch` | Partição técnica derivada da identidade do arquivo |

Na reexecução, `_run_id` e `_ingest_date` anteriores são preservados. A execução
que verificou o estado mais recentemente aparece no relatório e em `_READY.json`.
O lineage referencia recorte e RAW original, permitindo seguir a cadeia.

`ingest_batch` não é o lote de semanas `b00`/`b01`/`b02`. Nesta entrega, o snapshot
inteiro foi ingerido: 50 mil casos e seus relacionados. A entrega cronológica
dos lotes, correções e merges ainda será desenvolvida em F04.

## Evidências e limites

Resultados reais e testes em [F02_BRONZE_RECORTE.md](evidencias/F02_BRONZE_RECORTE.md).
Relatórios por execução, regras, inventário e lineage ficam em `artifacts/bronze/`,
fora do Git. O tempo do relatório de métricas difere do tempo da função de pipeline.

O gate verifica as regras atuais e contagens; F02.5 ainda alinhará integralmente
as regras ao contrato novo, incluindo auxiliar histórica vazia legítima.
F02.6 fará a comparação completa de valores recorte → Bronze e a reconciliação
de proveniência. Isso não foi declarado concluído por uma comparação de contagens.

Os testes de interrupção induzem exceções após escrita Spark e após rename.
Não foi simulado desligamento do computador ou morte abrupta da árvore JVM durante
a escrita. As garantias de filesystem serão revistas para objetos em F08.

Esta Bronze continua em Parquet. Transações Delta nas camadas seguintes e
publicação consistente entre tabelas Silver/Gold permanecem no roteiro.
