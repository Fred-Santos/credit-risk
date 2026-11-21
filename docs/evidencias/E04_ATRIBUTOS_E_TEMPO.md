# E04 — Atributos e investigação temporal

Estado: E04.1–E04.4 aceitos como catálogo e investigação; aprovação operacional
para ML continua **não demonstrada**. Silver auditada: `ef9c66b2a9d86511bcb8d3d5`.

A seleção fixa produz **166 atributos retrospectivos**,
com fórmula, origem, tipo, unidade, ausência e status temporal no
[contrato Gold](../../configs/contracts/expansion_gold_v1.yaml). Todos os campos
de origem estão classificados no [catálogo de fontes](../../configs/contracts/expansion_feature_sources_v1.yaml).
As 16 auxiliares contribuem; `train_base` define a população. Campos não
selecionados continuam na Silver, sem seleção supervisionada por target.

São usadas fontes 1:1, solicitante de índice zero e históricos agregados antes
dos joins. Nível dois usa médias ponderadas por observações não nulas. Contagens,
flags, valores nulos, zeros reais e modas com desempate determinístico são
conferidos com SQL independente na E05. A fixture com grupos de tamanhos
diferentes impede aprovação de uma média de médias incorreta.

A auditoria examinou **57 campos de data**
(excluindo a decisão), em 13 tabelas; **44 campos**
apresentam alguma data posterior à decisão. Os contadores/min/max por campo
estão em `artifacts/expansion/temporal/ef9c66b2a9d86511bcb8d3d5.json`.
Datas programadas ou transformadas podem ser futuras: esses contadores sinalizam
investigação, não provam vazamento. Nenhuma observação foi apagada por essa regra.
Tempo da auditoria: 34.745 s.

A [descrição oficial](https://www.kaggle.com/c/home-credit-credit-risk-model-stability/data)
foi consultada pelo texto indexado; a abertura direta depende de JavaScript e
não apresentou linhas legíveis. Ela indica finalidade preditiva na competição
e rótulo observado após um período, sem especificar nesse texto o horizonte ou
`label_available_at`. O dicionário local não fornece disponibilidade histórica
por campo. Um escore externo que menciona um ano não define a maturação do target.

Decisão: **zero atributos aprovados point in time**, `ml_ready=false`.
Não inferir disponibilidade de data do evento, aquisição em 2026 ou ausência de
datas futuras. Não afirmar que todos os atributos vazam. Não inventar janela
de maturação ou embargo. Essas lacunas impedem declarar treino operacional
válido, mas não impedem a ABT retrospectiva identificada prevista no roteiro.

Identidade de cliente entre períodos não pôde ser comprovada: o caso de crédito
é identificável, a pessoa global não. A separação E05 garante disjunção de casos,
sem alegar ausência de clientes repetidos. Empregadores mascarados e índices
locais não são tratados como identificadores de pessoa.

```bash
bash scripts/project.sh -m scripts.prepare_expansion_features
bash scripts/project.sh -m scripts.run_expansion audit --silver-id ef9c66b2a9d86511bcb8d3d5
```
