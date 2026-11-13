# Evidência F02.6 — valores e proveniência Bronze

Data: 12/11/2026. Runtime local isolado: Python 3.11.14 e Spark 3.5.7.
Seleção `7d58bbdaa00cbabfbce54d26`, mesmas três tabelas e contrato congelado.
Sem commit desta entrega; execução identificada pelos hashes de código no
relatório de execução. Detalhes do protocolo em
[RECONCILIACAO_BRONZE.md](../RECONCILIACAO_BRONZE.md).

## Comandos

```bash
bash scripts/project.sh scripts/run_tests.py --integration-required
bash scripts/project.sh -m unittest discover -s tests -p test_bronze_reconciliation.py -v
bash scripts/project.sh -m src.pipelines.run_bronze_mvp \
  --sample 7d58bbdaa00cbabfbce54d26
```

## Expectativa e resultado real

Esperado: igualdade de todos os campos de negócio e multiplicidades nas três
tabelas, nos dois sentidos. Comparar o recorte e também a RAW filtrada pela
coorte contra a Bronze; nenhuma diferença é tolerada. Proveniência válida por
linha, arquivo, batch, manifesto e lineage; não regravar Parquets íntegros.

| Tabela | Linhas | Recorte → Bronze, ambos os sentidos | RAW selecionada → Bronze, ambos os sentidos |
|---|---|---|---|
| train_base | 50.000 | Zero diferenças | Zero diferenças |
| train_static_0 | 50.000 | Zero diferenças | Zero diferenças |
| train_applprev_1 | 215.390 | Zero diferenças | Zero diferenças |

Total: **315.390 linhas aceitas, nenhuma linha descartada**. Não há quarentena;
qualquer divergência bloqueia a publicação inteira. `accepted_rows=0` na falha;
`rejected_rows=0` identifica ausência de descarte, não aprovação de valores
divergentes. O diagnóstico usa contagens de faltas/excessos por direção.

`_source_file` coincide com a leitura de cada origem imediata. Cada arquivo foi
conferido contra seu batch esperado, manifestos v2 e checksums de saídas. As
linhas preservam o primeiro `_run_id`. Conjunto de batches sem extras. Lineage
confere entrada, saída, seleção, manifesto do recorte, RAW original e checksums
dos três Parquets e três manifestos. Qualidade: 39 checks, sem falhas/avisos.

A primeira execução foi `20261112T211858Z_8c84e087` (68,697 s). Uma reexecução com
auditoria adicional por arquivo/batch, `20261112T212104Z_ebd80f30` (70,894 s),
também passou. Ambas reutilizaram a Bronze, sem regravar datasets.
Tempos são durações internas da execução local, sem valor de benchmark.

Execução final: **`20261112T212249Z_a5a41ff3`**, status `passed`, duração interna
86,922 s, `written_datasets=[]`. Auditoria de seis arquivos de lineage aprovada;
três comparações arquivo/batch aprovadas. RAW conferida por fingerprints antes
e depois do processamento. Os resultados por tabela permaneceram sem diferenças.

| Código final | SHA-256 |
|---|---|
| `src/quality/reconcile_bronze.py` | `e295ee956b066e6c0182b5bb19f142175b53d4940f7842c1bbab948b6a9e4096` |
| `src/pipelines/run_bronze_mvp.py` | `4e33ff3483d7c21ce4c29bb79cc5de912403d7836f9dd6e0be6b69a56c274362` |
| `src/lineage/lineage_bronze.py` | `4c59f71b2df463bb94544bec5e5ce9efd605926904981d8765d5bbae266e6ef3` |

O relatório privado é salvo em
`artifacts/bronze/samples/<selection_id>/quality/reconciliation/<run_id>.json`.
O relatório `runs/<run_id>.json` guarda código, parâmetros, referência à
reconciliação e seu hash. O gate `_READY.json` inclui esse hash e só é emitido
depois da aprovação; não usar o evento de lineage isoladamente como aceite.

## Testes

Sete novos testes em `tests/test_bronze_reconciliation.py` cobrem:

- Nulos, ordem das linhas/colunas e mudança de particionamento físico.
- Mesmo número de linhas/chaves, com valor de negócio alterado.
- Mesmas linhas distintas e contagem total, mas multiplicidade diferente.
- Tipo incompatível bloqueado, sem cast silencioso.
- Valores de negócio iguais com `_source_file` incorreto.
- Alteração de valor com manifesto recalculado: qualidade passa, reconciliação
  falha, relatório é preservado e o gate é removido.
- Lineage com checksum ou execução divergente.

As fixtures de recuperação passaram a materializar também RAW sintética real
com fingerprints válidos, permitindo verificar toda a cadeia de proveniência.
Nenhum teste depende de dados Home Credit ou credenciais.

Suíte final da versão congelada: **80 testes aprovados em 140,649 s, nenhum
ignorado**, log `/tmp/credit-risk-tests-f026-accepted.log`. Os sete testes
específicos também passaram isoladamente em 31,234 s, antes da última conferência
integral. O log de Parquet ilegível pertence ao teste negativo de F02.5 e termina
com o comportamento de falha esperado.

Contagem de 18/72 aceites, links locais dos documentos alterados e hash de
reconciliação no gate conferidos. `git diff --check` sem erros.

## Aceite e limites

F02.6 e F02 aceitas no escopo local do snapshot e dos pequenos pacotes de
referência de revisões. Os originais, o recorte e os Parquets Bronze foram
preservados; somente relatórios, lineage e gate foram atualizados.

Não conclui Silver, merge incremental, ABT/Gold ou transação entre tabelas.
Próximo item: F03.1, catálogo e revalidação das transformações do notebook Silver.
