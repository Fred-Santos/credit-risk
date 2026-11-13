# Qualidade da Bronze — F02.5

O CLI de snapshot continua sendo `run_bronze_mvp --sample <id>` ou `--raw`.
`configs/quality_rules_bronze.yaml` agora referencia o contrato de snapshot.
[bronze_contract.py](../src/quality/bronze_contract.py) gera regras a partir dele,
sem copiar os 214 campos para outro YAML ou modificar a identidade do recorte.
As regras anteriores complementam essas verificações. Regras geradas são sempre
obrigatórias, mesmo que a severidade padrão do YAML seja `warn`.

| Dimensão | Regra de publicação |
|---|---|
| Conjunto de tabelas | Base, estática e histórico devem existir; tabela fora do contrato bloqueia |
| Volume | Base/estática não vazias; histórico pode ter zero linhas e deve manter o schema |
| Schema | Todos os campos/tipos de negócio devem corresponder exatamente ao contrato |
| Metadados | `_run_id:string`, `_ingest_date:date`, `_source_file:string`, `ingest_batch:string`, todos não nulos |
| Chave | Única no dataset completo, incluindo todos os arquivos/batches; chaves não nulas |
| Nulos opcionais | Preservados; não são falhas nem recebem preenchimento automático |
| Referências | Auxiliares sem órfãos; estática deve cobrir todos os casos da base |
| Calendário | Data ISO válida, MONTH correspondente e WEEK_NUM não negativo |
| Rótulo | target obrigatório e pertencente a 0/1 |
| Leitura | Parquet ilegível bloqueia e gera resultado `readable=false` |
| Configuração | Checks, parâmetros e estruturas inválidas falham antes da execução; erro nunca vira warning |

`ingest_batch` é descoberto pelo Spark nas pastas `ingest_batch=<hash>` da
Bronze; não existe no payload original. O schema exato da Bronze soma campos de
negócio e esses quatro metadados. Não confundir isso com uma coluna extra na RAW.

Atualização F02.6: a [reconciliação integral](RECONCILIACAO_BRONZE.md) já foi
implementada e executada no recorte real. Ela agora complementa a qualidade e
também precisa passar antes da emissão do gate.

## Como a execução decide o aceite

`load_rules` valida a configuração. A engine descobre datasets, registra ausências,
lê cada dataset completo e avalia as regras. Erros de execução são obrigatórios,
mesmo quando o check foi configurado como aviso. O relatório JSON registra
resultado, severidade, divergências de schema e hash do contrato aplicado.
Uma mudança do contrato durante a avaliação também bloqueia a aprovação.

Para uma configuração inválida, a execução para antes do relatório de qualidade;
o orquestrador registra o erro no relatório de execução. Para falha de dados ou
leitura, o relatório de qualidade é gravado antes da exceção. Nos dois casos,
`run_bronze` mantém `_READY.json` ausente e preserva commits para investigação e
retry. O gate só reaparece após todas as verificações passarem.

Checksums do manifesto e qualidade têm funções diferentes: o primeiro detecta
mudança de arquivos; a segunda verifica se o conteúdo atende ao contrato. Nenhum
deles substitui a igualdade integral de valores RAW → Bronze, prevista em F02.6.

## Snapshot e eventos usam grãos diferentes

Estas regras são para o snapshot consolidado: uma linha por chave. Elas não devem
ser aplicadas à pasta `data/events`, que preserva entregas repetidas e revisões.
O [contrato de eventos](contratos/EVENTOS_REVISOES.md) já verifica imagem completa,
tipos, obrigatoriedade, calendário/domínios, hashes, contexto, posição única de
entrega e conflitos de revisões em todo o histórico. Repetir o mesmo evento em
outra entrega é permitido. Duas imagens diferentes da mesma revisão são erro.

Um pacote de eventos pode conter apenas correções na estática; não precisa trazer
a base inteira nem cobertura de todas as chaves em cada chegada. Referências e
cobertura devem ser conferidas sobre o estado consolidado na futura Silver.
Não foi criada uma opção para contornar a qualidade de snapshot e ingerir eventos
pelo CLI antigo. O transporte distribuído e o merge continuam em F04.

## Executar

```bash
bash scripts/project.sh scripts/run_tests.py --integration-required
bash scripts/project.sh -m src.pipelines.run_bronze_mvp \
  --sample 7d58bbdaa00cbabfbce54d26
```

A carga real já existente é reutilizada se íntegra. Esta etapa revalida a Bronze
com regras ampliadas e atualiza seus relatórios/gate; não modifica o contrato
congelado, a RAW ou o recorte. O modo `--raw` passa pelas mesmas regras de snapshot;
arquivos fragmentados devem formar datasets lógicos, como no recorte atual.
Conjuntos fora das três tabelas contratadas exigem novo escopo explícito.
