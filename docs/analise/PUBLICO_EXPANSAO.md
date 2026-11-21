# Público Home Credit — janeiro a setembro/2020

Análise retrospectiva da população completa de **447,305 casos** da janela.
Pacote `407b64011bf6d040484813e8`, ligado à Silver `ef9c66b2a9d86511bcb8d3d5` e à Gold
`363ce1dd9aec8f446a69eb1b`. Não há amostra de 50 mil nesta entrega.

## Perguntas e método

A análise pergunta como variam o volume e o desfecho observado, quais fontes
cobrem os casos, quais atributos estão ausentes, como se distribuem histórico,
produto e código de educação do solicitante, e como diferem os dois períodos.
Os cortes e dimensões estão fixados em `configs/expansion_analysis_v1.yaml`;
não foram escolhidos por desempenho preditivo ou correlação com target.

A população une as duas ABTs aprovadas. O acesso aos rótulos da avaliação foi
explícito e exclusivamente descritivo; nenhum imputador, escala, vocabulário,
modelo ou seletor foi ajustado. Usar essas conclusões futuramente para escolher
um modelo ou seus atributos comprometeria a independência da reserva e exigiria
redefinir a avaliação. Não tratar esse relatório como validação preditiva.

## Volume e target observado

O numerador é target=1; o denominador contém somente rótulos válidos em 0/1.
Há **14,757/447,305 = 3.299%** na janela. O horizonte de
maturação e a disponibilidade histórica continuam não comprovados: essa razão
não é uma taxa operacional atual de inadimplência.

| Mês | Casos | Target 1 | Rótulos válidos | Razão retrospectiva | Primeira/última data observada |
|---|---:|---:|---:|---:|---|
| 202001 | 86,750 | 3,537 | 86,750 | 4.077% | 2020-01-01 / 2020-01-31 |
| 202002 | 75,183 | 3,520 | 75,183 | 4.682% | 2020-02-01 / 2020-02-29 |
| 202003 | 60,748 | 2,772 | 60,748 | 4.563% | 2020-03-01 / 2020-03-31 |
| 202004 | 8,289 | 179 | 8,289 | 2.159% | 2020-04-01 / 2020-04-30 |
| 202005 | 28,725 | 635 | 28,725 | 2.211% | 2020-05-01 / 2020-05-31 |
| 202006 | 45,962 | 1,128 | 45,962 | 2.454% | 2020-06-01 / 2020-06-30 |
| 202007 | 28,912 | 660 | 28,912 | 2.283% | 2020-07-01 / 2020-07-31 |
| 202008 | 50,831 | 994 | 50,831 | 1.955% | 2020-08-01 / 2020-08-31 |
| 202009 | 61,905 | 1,332 | 61,905 | 2.152% | 2020-09-01 / 2020-09-30 |

O maior volume é 202001 (86,750) e o menor é
202004 (8,289). Isso descreve chegadas de casos na fonte;
não demonstra efeito de pandemia, política de concessão ou mudança real de risco.
Datas observadas que não alcançam os limites do calendário são sinalizadas no
JSON como `observed_partial_month`; isso não comprova perda de registros.

![Volume e razão retrospectiva](../../data/gold/expansion-analysis/407b64011bf6d040484813e8/report/monthly.png)

## Cobertura das fontes

Cobertura é casos com ao menos uma observação / casos do mês. Quantidade de
observações é outra medida e pode exceder o número de casos. Ausência de uma
fonte não equivale a zero financeiro nem preenchimento completo dos seus campos.

| Fonte | Casos cobertos na janela | Cobertura | Observações |
|---|---:|---:|---:|
| `train_applprev_1` | 377,785 | 84.458% | 2,316,343 |
| `train_applprev_2` | 377,785 | 84.458% | 5,084,023 |
| `train_credit_bureau_a_1` | 429,687 | 96.061% | 5,016,039 |
| `train_credit_bureau_a_2` | 429,550 | 96.031% | 74,277,008 |
| `train_credit_bureau_b_1` | 14,544 | 3.251% | 36,557 |
| `train_credit_bureau_b_2` | 14,534 | 3.249% | 544,870 |
| `train_debitcard_1` | 35,616 | 7.962% | 49,716 |
| `train_deposit_1` | 33,531 | 7.496% | 45,828 |
| `train_other_1` | 50,077 | 11.195% | 50,077 |
| `train_person_1` | 447,305 | 100.000% | 784,268 |
| `train_person_2` | 376,491 | 84.169% | 418,411 |
| `train_static_0` | 447,305 | 100.000% | 447,305 |
| `train_static_cb_0` | 446,999 | 99.932% | 446,999 |
| `train_tax_registry_a_1` | 158,402 | 35.413% | 1,145,923 |
| `train_tax_registry_b_1` | 144,545 | 32.315% | 1,063,435 |
| `train_tax_registry_c_1` | 0 | 0.000% | 0 |

`tax_registry_c_1` não possui observações nos casos desta janela. Sua estrutura
foi preservada, e a ausência não foi preenchida com registros artificiais.
Comparar fontes requer levar essas coberturas e calendários em conta.

![Cobertura mensal](../../data/gold/expansion-analysis/407b64011bf6d040484813e8/report/coverage.png)


A cobertura muda ao longo do tempo e deve acompanhar comparações de público ou estabilidade:

- `train_tax_registry_a_1`: janeiro 59,262/86,750 (68.31%); setembro 677/61,905 (1.09%).
- `train_tax_registry_b_1`: janeiro 0/86,750 (0.00%); setembro 40,258/61,905 (65.03%).
- `train_person_2`: janeiro 83,763/86,750 (96.56%); setembro 36,146/61,905 (58.39%).

Essa variação não comprova troca de fornecedor ou causa de negócio.

## Ausências, composição e períodos

A completude tem denominador igual aos casos do mês e conta nulos reais;
códigos mascarados não foram decodificados ou reinterpretados como nulos.
Os 166 atributos estão no CSV
`missingness.csv`, inclusive flags e contagens estruturais, que não devem ser
confundidas com medidas financeiras preenchidas. As modas categóricas e os
atributos do solicitante seguem o contrato Gold, sem escolher pessoa arbitrária.

`composition.csv` contém segmentos fixos de histórico (zero, um, dois–cinco,
seis ou mais registros), produto e código de educação. Categorias `VALUE:` são
códigos da fonte, sem inferir seu significado; `__NULL__` identifica ausência.
São registrados numeradores, denominadores e flags de grupos com menos de 500
casos ou 20 positivos. Essas flags não são testes de significância.

| Período | Casos | Target 1 / rótulos válidos | Razão retrospectiva |
|---|---:|---:|---:|
| development | 259,695 | 10,643/259,695 | 4.098% |
| evaluation | 187,610 | 4,114/187,610 | 2.193% |

As razões dos dois períodos diferem. Não se conclui melhora de carteira ou de
modelo: composição, cobertura e maturação podem diferir. `period_compare.csv`
inclui também contagens preenchidas e médias de três atributos, em unidades
transformadas da fonte; nenhuma média foi interpretada como reais ou moeda.
A identidade global de cliente não é comprovada, portanto a disjunção é por caso.

## Reconciliação e reprodução

Volumes/rótulos mensais foram conferidos com SQL na base Silver; cobertura e
observações com SQL nas 16 auxiliares. Completude, composição e comparação de
períodos têm oráculos SQL próprios. As cinco tabelas Delta foram relidas e
comparadas célula a célula. O relatório e os gráficos têm checksums e não alteram
nenhuma fonte. Somente agregados pequenos são coletados no Python.

Dados agregados e figuras exportáveis: [diretório local](../../data/gold/expansion-analysis/407b64011bf6d040484813e8/report/).

```bash
bash scripts/analysis.sh -m scripts.run_expansion analysis --silver-id ef9c66b2a9d86511bcb8d3d5 --gold-id 363ce1dd9aec8f446a69eb1b
```

`numeric_0`, `numeric_1` e `numeric_2` no CSV de períodos correspondem, respectivamente, a `static_0__annuity_780A`, `static_0__maininc_215A` e `other_1__amtdebitincoming_4809443A__mean`. Os sufixos indicam contagem não nula e média; o mapeamento também está na política do JSON.
