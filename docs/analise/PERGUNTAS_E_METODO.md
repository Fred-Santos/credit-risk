# F07 — perguntas, população e método analítico

Definição de consumo da Gold v1, em 13/11/2026. O [escopo do produto](../ESCOPO_PRODUTO.md)
apresentou P01–P06 como objetivos; esta matriz fecha o que será calculado.
Política executável: [analysis_policy_v1.yaml](../../configs/analysis_policy_v1.yaml).

## População e publicações

O caso de crédito (`case_id`) é a unidade de análise. A seleção determinística
tem 50 mil casos, preserva suas relações e não foi desenhada para inferência
da carteira operacional. O rótulo não participa da [seleção por hash](../RECORTE_E_LOTES.md).

| Papel | Publicação Gold | População |
|---|---|---|
| baseline | c711e23bdd5145ae78537a61 | 49.999 casos; um caso ainda retido na simulação |
| corrected | e709bcefce9adab4b7d60562 | Mesmos 49.999 casos; duas revisões auxiliares declaradas |
| final | 6f4406dd0180850e23d5283e | 50.000 casos após a chegada tardia |

São snapshots aprovados da mesma seleção. O comando exige os três IDs,
confere o contrato Gold e a cadeia de pais. Não usa CURRENT como escolha de
entrada, não troca ponteiros e não reexecuta transformações Silver/Gold.

## Perguntas fechadas

| ID | Pergunta operacionalizada | Campos e cálculo | População/período | Limite e evidência |
|---|---|---|---|---|
| P01 | Quantos casos há por mês da decisão? | MONTH, date_decision, COUNT(*) | Todos os casos final; datas observadas de cada mês | Volume do recorte; limites de datas não comprovam cobertura operacional completa |
| P02 | Qual a proporção de target=1 entre rótulos válidos? | COUNT(target=1) / COUNT(target em {0,1}); nulos separados | Total final e por MONTH | Fração descritiva; maturação/horizonte operacional não auditados; sem inferência de carteira |
| P03 | Qual a cobertura das auxiliares e como se compõe o histórico? | has_static, has_previous_applications; preenchimento de static_annuity; contagens históricas; grupos 0, 1, 2–5, 6+ | Final por mês e por número de observações | Cobertura é existência de linha; completude tem outro denominador; observações não comprovam empréstimos distintos |
| P04 | O que a correção simulada mudou mantendo os mesmos casos? | Diferenças por caso/coluna entre baseline e corrected; indicadores mensais antes/depois | Mesmos IDs, datas, semanas e rótulos obrigatoriamente | Mudanças só de valores podem deixar indicadores de contagem iguais; atraso final é outra comparação |
| P05 | A mesma análise anterior pode ser reproduzida? | Versões/UUIDs por manifesto, hashes de código/configuração, semantic.json, PNG/SVG baseline | Mesmo trio explícito em processos novos | Resultados sem run_id/horário devem coincidir; arquivos e dependências precisam ser preservados |
| P06 | Os números apresentados têm suporte verificável? | SQL de consumo ABT versus todos os indicadores Gold; segmentos versus SQL independente; totais meses/segmentos versus população | Cada uma das três publicações | Validação local das regras definidas; não equivale a auditoria de produção ou de semântica temporal |

## Denominadores, ausência e grupos

- Volume: número de casos, nunca linhas históricas depois de join 1:N.
- Desfecho: target=1 dividido pelos rótulos 0/1. Nulo é ausente; outro valor
  bloqueia o relatório. Zero rótulos válidos produz taxa NULL.
- Cobertura estática/histórica: casos com linha correspondente / todos os casos.
- Completude de annuity: casos com valor preenchido / todos os casos. O contrato
  atual exige cobertura estática completa; isso não obriga preencher annuity.
- Completude do montante histórico: observações com credamount preenchido /
  todas as observações históricas, preservando esse denominador diferente.
- Composição: grupos de contagem 0, 1, 2–5 e 6+. Grupo vazio é mostrado com n=0
  e taxa não calculável; não imputar zero como desfecho observado.

Os gráficos sinalizam n<500 ou menos de 20 target=1. São convenções de leitura,
sem teste de significância, ocultação ou promessa de precisão estatística.
A tabela apresenta todos os grupos e denominadores. Se a primeira/última data
observada não abrange o mês calendário, o gráfico marca **janela observada
parcial**. O sinal não é prova de falta de registros na origem: recorte, janela
de aquisição e disponibilidade podem explicar a cobertura observada.

## Interpretação permitida

O relatório diferencia achado calculado, hipótese e investigação futura. Pode
descrever variação de composição, cobertura e rótulos; não pode concluir que
histórico causa inadimplência, que a fonte está completa ou que mudou uma taxa
operacional real. Maturação do rótulo e disponibilidade dos atributos no momento
da decisão não foram comprovadas. Nenhum segmento orienta concessão de crédito.

Unidades monetárias não foram confirmadas. Comparamos valores individuais do
caso corrigido sem somar montantes da população como dívida/exposição. Há um
limite de 50 casos alterados para apresentação; acima dele o relatório falha,
evitando coleta acidental da ABT completa no driver.

## Execução e revisão

As consultas de consumo estão em [queries.py](../../src/analytics/queries.py).
O [gerador](../../src/pipelines/run_analysis.py) registra entradas e ambiente;
[report.py](../../src/analytics/report.py) produz relatório e gráficos a partir
dos agregados conferidos. A análise mantém o grão por caso e não altera tabelas.

F07.6 é uma autorrevisão documentada: comparar números com os oráculos e
interpretar os limites. Não alegar avaliação independente por outra pessoa.
Instruções e resultados serão registrados junto da evidência de execução.
