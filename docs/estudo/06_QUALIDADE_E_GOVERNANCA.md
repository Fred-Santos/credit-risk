# 6 — Contratos, qualidade, reconciliação e governança

[Percurso](../GUIA_ESTUDO_LAKEHOUSE.md) · Anterior: [Ingestão](05_INGESTAO_E_BRONZE.md)

Objetivo: distinguir as provas necessárias para confiar nos dados e localizar
onde elas bloqueiam a pipeline. Pré-requisito: schemas, chaves e ingestão.

## Da observação à regra

**Profiling** investiga os dados: tipos, intervalos, nulos, distribuições e
duplicatas. Um **contrato** declara o que uma entrada ou saída precisa cumprir.
Observar um máximo em uma amostra não transforma esse número em limite de negócio.

Por exemplo, o histórico do recorte teve até 20 observações por caso. O contrato
exige índice de grupo não negativo e chave composta única; não cria um teto de
20 por causa dessa observação. Uma regra precisa de justificativa e comportamento
definido quando falha.

No projeto, contratos YAML fixam schemas completos, campos obrigatórios,
chaves e referências. Os loaders validam também a própria configuração.
Configuração inválida e dado inválido têm causas diferentes; ambos podem impedir
aceite e devem produzir diagnóstico.

## Quais perguntas cada verificação responde?

| Verificação | Pergunta | Exemplo |
|---|---|---|
| Schema | Colunas e tipos correspondem ao combinado? | Data deve ser `date` na Silver |
| Qualidade | As regras do conjunto foram atendidas? | Chave única, target 0/1 |
| Reconciliação | Os valores esperados chegaram à saída? | Comparar todas as linhas nos dois sentidos |
| Proveniência | É possível rastrear a origem? | Arquivo, batch, execução e hashes |

Um conjunto pode satisfazer schema, chave e domínio mesmo com valores trocados.
Exemplo sintético: a origem tem `(101,10)` e `(102,20)`; a saída tem `(101,20)`
e `(102,10)`. Contagem e unicidade passam, mas o conteúdo mudou.

## Como provamos igualdade de conteúdo

`compare_rows` usa `exceptAll` nos dois sentidos. A primeira direção encontra
linhas esperadas que faltam; a segunda encontra linhas extras. A operação
preserva multiplicidade: uma duplicata adicional conta como diferença.

A comparação precisa alinhar colunas e tipos. Na transformação de datas,
restauramos a representação aprovada para comparar com a origem; não aplicamos
casts indiscriminados que poderiam esconder diferenças. Checksums físicos
conferem arquivos; comparação lógica confere valores segundo Spark SQL.

## Governança como registros utilizáveis

**Inventário** descreve os conjuntos disponíveis. **Dicionário** explica os
campos e seus perfis. **Lineage** registra relações entre entradas, etapas e
saídas. Neste projeto, essas informações aparecem em relatórios e arquivos
locais; não há catálogo corporativo externo implementado.

Esses registros ajudam a responder quem produziu um conjunto e com quais
entradas. O gate Bronze vincula o resultado de qualidade e reconciliação aos
arquivos que o leitor vai consumir. Um relatório antigo aprovado não certifica
automaticamente um arquivo ou código atual.

## Leitura guiada do projeto

Leia `validate_snapshot` em [contracts.py](../../src/quality/contracts.py).
Relacione cada regra ao conceito do capítulo 2. Depois, leia `compare_rows`
e `audit_lineage` em [reconcile_bronze.py](../../src/quality/reconcile_bronze.py).

Finalmente, abra `verify_approval` em
[read_bronze.py](../../src/silver/read_bronze.py). Siga o vínculo entre gate,
manifesto do recorte, arquivos, relatório de execução, qualidade, reconciliação
e lineage. Esse encadeamento explica por que o leitor exige mais que uma pasta.

## Evidência e resultado

A [qualidade Bronze](../evidencias/F02_QUALIDADE_BRONZE.md) aprovou 39 checks.
A [reconciliação](../evidencias/F02_RECONCILIACAO_BRONZE.md) conferiu as 315.390
linhas e a proveniência sem diferenças. Na Silver, o contrato persistido
acrescenta validação independente da declaração feita pelo writer.

## Atividade e conferência

Origem: `[(1,10),(2,20)]`. Saída: `[(1,10),(1,10)]`. Quais verificações podem
detectar o problema e por que a contagem isolada falha?

**Conferência:** ambas têm duas linhas. Unicidade encontra a duplicata, e a
reconciliação encontra `(2,20)` faltando e uma ocorrência extra de `(1,10)`.
As verificações se complementam, pois outras trocas poderiam preservar a chave.

Próximo: [7 — Transformações Silver](07_TRANSFORMACOES_SILVER.md).
