# Contrato Gold v1 — ABT e indicadores mensais

Norma executável: [gold_v1.yaml](../../configs/contracts/gold_v1.yaml).
Entrada: três tabelas da [Silver gerenciada v2](SILVER_GERENCIADA.md),
identificadas por manifesto aprovado, UUID e versão Delta. Saída retrospectiva;
não é uma base de treino com disponibilidade comprovada na decisão de crédito.

## População, grão e tempo

ABT significa *Analytical Base Table*. Seu grão é **uma linha por `case_id`**
presente em `credit_cases` na publicação. Dois left joins preservam essa
população. Antes do segundo join, todas as observações de
`previous_applications` são agregadas por caso. A chave histórica
`case_id/num_group1` é validada na Silver; não se escolhe uma linha arbitrária.
`previous_application_count` conta essas observações; não comprova uma contagem
de empréstimos distintos, pois não validamos uma identidade de contrato financeiro.

A janela inclui **todo o histórico relacionado presente na Silver aprovada**.
Não aplicamos corte pela data da decisão: não há comprovação de quando cada
atributo ficou disponível, e datas auxiliares posteriores são admitidas no
contrato Silver. As colunas de valores, agregados e revisões servem à análise
retrospectiva. Nenhuma coluna é declarada elegível para um futuro treino sem
investigação temporal específica. `target` é desfecho, nunca atributo de entrada.

`MONTH` e `WEEK_NUM` vêm da fonte de casos, sem usar o mês da ingestão. Correções
e casos atrasados afetam seu período de negócio. Falta de um caso previamente
publicado reprova a atualização; exclusão automática não faz parte da v1.

## Dicionário da ABT

Tipos seguem Spark SQL. `bigint` corresponde a long, `int` ao inteiro de 32 bits.

| Coluna | Tipo | Origem/fórmula | Nulo e interpretação |
|---|---|---|---|
| case_id | bigint | credit_cases.case_id | Proibido; chave única |
| date_decision | date | credit_cases.date_decision | Proibido |
| MONTH | bigint | credit_cases.MONTH | Proibido; período original |
| WEEK_NUM | bigint | credit_cases.WEEK_NUM | Proibido; semana da fonte |
| target | bigint | credit_cases.target | 0/1; Silver atual exige preenchido; consulta trata nulo como rótulo indisponível |
| static_annuity | double | credit_static.annuity_780A | Valor opcional preservado; nulo não vira zero |
| has_static | boolean | Existe chave na estática | Nunca nulo; distingue ausência de fonte de annuity nula |
| has_previous_applications | boolean | Contagem histórica > 0 | Nunca nulo; false sem observações |
| previous_application_count | bigint | COUNT(*) do histórico por caso | Zero sem histórico |
| previous_amount_non_null_count | bigint | COUNT(credamount_590A) | Zero sem montantes preenchidos |
| previous_amount_sum | double | Soma de credamount_590A preenchido | Nulo sem valores; nunca soma vazia igual a zero |
| previous_amount_mean | double | Soma / contagem de montantes preenchidos | Nulo se denominador zero |
| previous_amount_min | double | MIN(credamount_590A) | Nulo sem montantes preenchidos |
| previous_amount_max | double | MAX(credamount_590A) | Nulo sem montantes preenchidos |
| case_source_revision | bigint | credit_cases._source_revision | Proibido |
| static_source_revision | bigint | credit_static._source_revision | Nulo se auxiliar ausente |
| previous_max_source_revision | bigint | MAX(_source_revision) do histórico | Nulo sem histórico |
| has_revised_source | boolean | Alguma das três revisões > 1 | Nunca nulo; revisão declarada na simulação |
| _abt_contract_version | int | Constante 1 | Proibido |

O dicionário adquirido da fonte descreve `annuity_780A` como valor mensal da
prestação (*monthly annuity amount*) e `credamount_590A` como montante do empréstimo ou limite do cartão de
aplicações anteriores. As unidades monetárias não foram confirmadas. Agregar
esses valores é uma estatística descritiva da fonte, sem representar dívida
atual, exposição, renda ou capacidade de pagamento.

A aritmética preserva doubles, sem arredondamento nem imputação. A soma por
caso percorre observações ordenadas por `num_group1`; isso torna reexecuções
independentes da ordem física de partições. Montantes todos nulos produzem
contagem de observações positiva, contagem de montantes zero e quatro agregados
nulos. Montantes preenchidos que somam zero produzem zero observado.

## Indicadores SQL

Tabela `monthly_metrics`: **uma linha por MONTH com casos**. Não gera meses
artificiais para lacunas. A população vazia gera tabela vazia com schema.

| Coluna | Tipo | Definição |
|---|---|---|
| MONTH | bigint | Período da base |
| case_count | bigint | COUNT(*) da ABT no período |
| valid_label_count | bigint | Casos com target em {0,1} |
| target_1_count | bigint | Casos com target=1 |
| target_1_rate | double | target_1_count / valid_label_count; NULL se zero |
| static_covered_count | bigint | Casos com has_static=true |
| static_coverage_rate | double | static_covered_count / case_count |
| history_covered_count | bigint | Casos com has_previous_applications=true |
| history_coverage_rate | double | history_covered_count / case_count |
| history_row_count | bigint | Soma de previous_application_count |
| history_amount_non_null_count | bigint | Soma de previous_amount_non_null_count |

Taxas são frações de 0 a 1; a apresentação em percentual pertence ao consumidor.
Cobertura mede existência de linhas, não preenchimento de todos os campos.
O contrato Silver atual exige cobertura estática completa, portanto essa taxa
é 1 no recorte aprovado mesmo havendo anuidades nulas. A função Gold também
representa ausência estática em fixtures, sem relaxar o contrato da entrada real.
Não rotular `target_1_rate` como taxa operacional de uma carteira real.

## Aceite e atualização

O writer exige tipos completos, chave única, contagem de casos preservada,
campos obrigatórios, domínio, números finitos e limites de contagens. Um SQL
independente calcula a ABT diretamente das três entradas: chaves, demais valores
e nulos devem coincidir. Apenas soma/média double admitem tolerância absoluta
1e-8 ou relativa 1e-12 nesse oráculo SQL, por diferença de ordem aritmética.
A comparação da ABT incremental com a recomputação integral usa igualdade exata.

Mudanças em qualquer tabela Silver identificam os casos afetados; auxiliares
sozinhas também provocam atualização. A publicação privada começa com cópia da
ABT pai e faz MERGE apenas das linhas derivadas diferentes. A consulta SQL mensal
é materializada integralmente depois desse merge, inclusive períodos antigos.
O oráculo mensal conta diretamente na Silver e reconcilia todos os numeradores,
denominadores e taxas. Somente então o manifesto Silver+Gold pode ser publicado.

Operação e decisões: [ABT e indicadores](../gold/ABT_E_INDICADORES.md).
