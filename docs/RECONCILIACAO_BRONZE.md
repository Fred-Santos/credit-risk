# Reconciliação da Bronze — F02.6

Implementação: [reconcile_bronze.py](../src/quality/reconcile_bronze.py), chamada
automaticamente por `run_bronze_mvp`, depois da qualidade e emissão do lineage,
antes de aprovar o gate. Não altera RAW, recorte ou Parquets Bronze.

## O que é comparado

| Elo | Verificação |
|---|---|
| RAW → Bronze da coorte | Fixar arquivos originais pelo contrato; semi-join com case_id da base do recorte; comparar todas as linhas e campos de negócio |
| Recorte → Bronze | Comparar todas as linhas e campos, projetados na mesma ordem e sem casts |
| Origem de cada linha | Repetir comparação incluindo `_source_file`, calculado por `input_file_name()` na leitura atual da origem |
| Arquivo → batch | Repetir comparação no batch específico esperado para o caminho de cada arquivo |
| Manifesto | Formato v2, caminho/checksum de origem, arquivos/checksums de saída, conjunto exato de batches |
| Primeira execução | `_run_id` das linhas corresponde ao run_id no manifesto do arquivo; retry não substitui a execução original |
| Lineage | Execução atual, entrada imediata, saída, vínculo com seleção/RAW e checksums de todos os Parquets e manifestos auditados |

No modo `--raw`, a origem imediata e original coincidem. No modo `--sample`, a
RAW é filtrada pelos casos do recorte, preservando todas as observações de cada
caso. Isso confere o elo completo, sem comparar a Bronze de 50 mil casos com o
snapshot inteiro de mais de 1,5 milhão de casos. O contrato do recorte permanece
congelado.

## Como comparar

`exceptAll` nos dois sentidos compara multiconjuntos: diferenças de ordem e
particionamento físico não importam, mas diferenças de multiplicidade importam.
Projetamos os mesmos campos na mesma ordem e conferimos tipos antes da operação,
pois `exceptAll` é posicional. Não converter tipos ou arredondar antes de comparar.

Os resultados seguem a igualdade de valores do Spark SQL, incluindo a semântica
de nulos em operações de conjuntos; não são uma comparação binária de floats ou
dos arquivos Parquet. A integridade física é coberta separadamente por SHA-256.
Não coletamos as linhas completas no driver nem publicamos valores individuais
no relatório: diferenças são contabilizadas por direção e tabela.

O campo `missing_rows` contabiliza ocorrências da origem ausentes na Bronze;
`extra_rows` contabiliza o inverso. Uma alteração pode aparecer nas duas direções:
a linha original falta e uma versão alterada sobra. Não somar essas contagens
como se fossem necessariamente duas entidades distintas rejeitadas.

## Aprovação e diagnóstico

Qualquer divergência bloqueia a publicação inteira. Não há descarte ou quarentena
de linhas nesta etapa: `rejected_rows=0` significa nenhum registro removido pelo
pipeline. `accepted_rows` é zero na falha, e é a soma das linhas reconciliadas
na aprovação. As diferenças ficam nos campos `missing_rows`/`extra_rows`.

Relatório em `<data_quality_dir>/reconciliation/<run_id>.json`, com estado,
contrato, comparações, contagens por tabela e auditoria por arquivo. O relatório
de execução referencia esse arquivo; `_READY.json` só é publicado após aprovação
e inclui `reconciliation_report_sha256`. Em falha, o relatório é preservado e
o gate permanece ausente. Corrigir a causa antes de tentar novamente.

O lineage pode ter sido emitido antes da falha de reconciliação. O evento técnico
`COMPLETE` sozinho não autoriza consumo; o gate representa o aceite da execução.
Essa separação será incorporada ao leitor Silver em F03. Não existe transação
global entre tabelas e relatórios nesta implementação local.

Checksums dos arquivos de dados e manifestos sempre entram no lineage, mesmo
quando o limite de checksums para outros artefatos é atingido. A auditoria não
é uma assinatura contra adulteração maliciosa coordenada. Paths absolutos em
`_source_file` referenciam o checkout de origem: mover os dados para outra raiz
exige planejar essa migração, sem reescrever metadados silenciosamente.

## Executar e testar

```bash
bash scripts/project.sh -m src.pipelines.run_bronze_mvp \
  --sample 7d58bbdaa00cbabfbce54d26
bash scripts/project.sh scripts/run_tests.py --integration-required
```

Os testes usam dados sintéticos mínimos, incluindo nulos, ordem física diferente,
duplicidade, tipo incompatível, caminho de origem errado e alteração de valor
com manifesto de saída recalculado. Esse último caso isola a reconciliação: os
checksums voltam a corresponder aos arquivos alterados, mas a origem ainda prova
que o valor mudou. O teste deve falhar na reconciliação e remover o gate.

Limite: isto reconcilia o snapshot Bronze. As regras ainda não demonstram merge
incremental, reconstrução da Silver, igualdade da ABT ou publicação histórica
Gold. Esses itens continuam nas fases correspondentes do roteiro.
