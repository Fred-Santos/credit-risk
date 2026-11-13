# F07 — resultados e revisão das conclusões

Análise local em 13/11/2026. Publicação final **6f4406dd0180850e23d5283e**,
com 50.000 casos. As consultas e unidades seguem
[perguntas e método](PERGUNTAS_E_METODO.md).

**Abra o [relatório HTML com gráficos e tabelas](../../artifacts/analysis/7d58bbdaa00cbabfbce54d26/7aba0b9fbdf88f350726cc70/20261113T102239Z_0addbf44/report.html).**
Os números verificáveis estão em
[semantic.json](../../artifacts/analysis/7d58bbdaa00cbabfbce54d26/7aba0b9fbdf88f350726cc70/20261113T102239Z_0addbf44/semantic.json).
Esses arquivos são locais; não são publicados remotamente por esta etapa.

## P01 — distribuição do volume

Os casos observados vão de **01/01/2019 a 05/10/2020**, distribuídos em 22
meses. Dezembro/2019 tem 4.132 casos; abril/2020 tem 276 e outubro/2020 tem
292. A queda observada nesses meses descreve o recorte, sem provar redução de
demanda, deterioração da carteira ou problema de ingestão.

Abril e outubro têm n<500. Abril tem cinco target=1, julho tem 17 e outubro
tem seis, todos abaixo do sinal de leitura de 20. Os grupos continuam visíveis
com seus numeradores e denominadores. Não foi feito teste de significância.

A primeira data observada de março/2020 é 02/03, e a última de outubro é
05/10. O relatório marca essas janelas observadas como parciais em relação
ao calendário. Isso não comprova que faltaram registros: seleção, dias de
atividade e janela da fonte precisam ser investigados. Os outros meses terem
datas extremas compatíveis com o calendário também não prova completude.

## P02 — desfecho rotulado

Há **1.578 target=1 / 50.000 rótulos válidos = 3,156%**, com zero rótulos
ausentes ou fora do domínio. A proporção mensal é apresentada com contagens;
por exemplo, março/2020 tem 97/1.914 = 5,068%, enquanto abril tem
5/276 = 1,812%. Comparar apenas esses percentuais esconde populações e tamanhos
diferentes. O relatório não atribui uma causa à variação.

O rótulo é retrospectivo. Seu horizonte operacional e a maturação por coorte
não foram auditados nesta análise; não chamar o resultado de taxa operacional
atual de inadimplência. A seleção por hash independe do target, mas não fornece
um desenho amostral para extrapolar essas proporções à carteira real.

## P03 — cobertura, completude e composição

| Medida | Numerador / denominador | Resultado |
|---|---|---|
| Cobertura estática | 50.000 / 50.000 casos | 100% |
| Preenchimento de annuity | 50.000 / 50.000 casos | 100% neste recorte; campo continua opcional no contrato |
| Cobertura histórica | 40.076 / 50.000 casos | 80,152% |
| Casos sem histórico | 9.924 / 50.000 casos | 19,848% |
| Montantes históricos preenchidos | 208.576 / 215.390 observações | 96,836% |

Há 6.814 observações com montante ausente e **79 casos com histórico presente
mas todos os montantes nulos**. Esses casos são distintos dos 9.924 sem nenhuma
observação histórica. A ausência permitida não é uma falha automática de qualidade.

| Observações históricas por caso | Casos | target=1 / válidos | Proporção |
|---|---|---|---|
| 0 | 9.924 | 201 / 9.924 | 2,025% |
| 1 | 7.411 | 217 / 7.411 | 2,928% |
| 2–5 | 18.410 | 604 / 18.410 | 3,281% |
| 6+ | 14.255 | 556 / 14.255 | 3,900% |

Neste recorte, os grupos com mais observações têm maior proporção rotulada.
É uma associação descritiva. Composição temporal, disponibilidade das fontes e
características dos casos podem diferir. Não há controle de confundimento,
validação point-in-time ou demonstração causal; o resultado não recomenda uma
regra de concessão. Uma observação histórica também não comprova um empréstimo
financeiro distinto.

## P04 — correção e atraso são efeitos diferentes

Baseline **c711e23bdd5145ae78537a61** e corrected
**e709bcefce9adab4b7d60562** têm exatamente os mesmos **49.999 casos**, datas,
meses, semanas e rótulos. A correção simulada alterou somente a ABT do caso 64:

| Campo | Antes | Depois |
|---|---|---|
| static_annuity | 2436,0 | 2437,0 |
| previous_amount_sum/mean/min/max | 6899,0 | 6900,0 |
| Revisões estática e máxima histórica | 1 | 2 |
| has_revised_source | false | true |

Há um montante histórico preenchido nesse caso; por isso soma/média/mínimo/máximo
coincidem. As unidades monetárias não foram confirmadas; esses valores não
representam dívida atual ou exposição da carteira.

Os **22 indicadores mensais permaneceram iguais**. Isso é esperado: a v1
mensura contagens, rótulos e cobertura, que a correção de montantes preservou.
O teste por diferenças de valores da ABT evita concluir incorretamente que a
correção foi perdida porque o percentual não mudou.

Corrected → final é outra comparação: o caso 135 chega em simulação tardia,
com oito observações, target=0 e mês original 201901. Foram inseridos um caso e
zero mudanças nos casos anteriores. Janeiro passa de **2.520 para 2.521 casos**,
com o mesmo numerador 69: a proporção passa de 69/2520 para 69/2521. Não atribuir
essa diferença à correção do caso 64 nem trocar o mês pelo horário de ingestão.

## P05 — reprodução histórica

Execuções `20261113T102239Z_0addbf44` e `20261113T102427Z_4544dd57`, cada uma
em novo processo Spark, usaram o mesmo trio explícito e a mesma implementação.
Coincidiram byte a byte: **semantic.json, seis CSVs e 12 arquivos PNG/SVG**,
incluindo todos os gráficos baseline. Metadata e HTML identificam tentativas
diferentes por run_id; isso não altera a análise. CURRENT e entradas foram
preservados. Identidade da análise: `7aba0b9fbdf88f350726cc70`.

## P06 — revisão técnica e limites

As três publicações passaram pela verificação de manifestos, UUIDs, versões,
arquivos e proveniência. Para cada uma, todos os indicadores mensais foram
reconciliados com SQL de consumo da ABT, e os segmentos com SQL independente.
Meses e segmentos coincidiram com os totais da população. O produtor F06 já
conferiu a ABT e os agregados diretamente contra Silver, em sua própria evidência.

Foi feita **autorrevisão técnica**, sem alegar um avaliador externo. As três
figuras finais foram inspecionadas visualmente: eixos, percentuais, nomes,
denominadores, flags e legibilidade. A execução de reprodução conferiu arquivos
numéricos e gráficos completos. Testes, hashes e comandos estão na
[evidência F07](../evidencias/F07_ANALISE.md).

**Achados:** contagens, proporções, cobertura e mudanças por caso apresentadas.
**Hipótese:** diferenças de composição das coortes/fontes podem explicar parte
da associação entre quantidade de observações e rótulo. **Investigar:** janela
original da fonte, maturação do target, disponibilidade dos atributos e
composição por período antes de testar essa hipótese. O projeto não mediu
causalidade, escala de produção, retorno financeiro ou impacto de uma decisão.
