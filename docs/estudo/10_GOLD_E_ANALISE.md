# 10 — Gold, ABT, indicadores e análise de dados

[Percurso](../GUIA_ESTUDO_LAKEHOUSE.md) · Anterior: [Incremento](09_INCREMENTO_E_CORRECOES.md)

Objetivo: explicar como tabelas técnicas se tornam uma entrega analítica
interpretável. Pré-requisito: grão, joins, agregações, nulos e revisões.

Estado: ABT Delta e indicadores SQL publicados em F06; relatório, gráficos e
interpretação entregues em F07. Os números pequenos
abaixo são fixtures didáticas, separados das evidências com o recorte real.

## ABT como contrato de consumo

**ABT**, Analytical Base Table, é uma tabela preparada para uma finalidade
analítica. Aqui tem uma linha por `case_id`, combinando a base de casos,
atributos estáticos e agregações do histórico. Isso facilita consultar as
informações sem repetir a preparação a cada análise.

O contrato precisa explicar cada coluna: origem, fórmula, tipo, interpretação
de nulo e disponibilidade temporal. Uma ABT pode servir à análise retrospectiva
sem ser adequada para treino de modelo no momento da decisão de crédito.

Na Gold, agregamos o histórico por caso antes do join. A fixture tem casos
`{1,2,3}` e observações `[(1,0,5),(1,1,NULL),(2,0,7)]`. Um left join direto
produziria quatro linhas. Depois do GROUP BY case_id, o histórico tem duas
linhas; juntá-lo à base produz os três casos originais. Para o caso 1:
`previous_application_count=2`, `previous_amount_non_null_count=1`, soma=5 e
média=5. O caso 3 tem contagem zero e montantes nulos. Não observar um montante
é diferente de observar montantes cuja soma é zero.

O [contrato Gold](../contratos/ABT.md) define as 19 colunas, tipos e semântica.
`static_annuity` preserva o campo opcional da estática. `has_static` registra
existência da linha: pode ser true mesmo quando a anuidade está nula. Todos os
históricos relacionados entram na agregação retrospectiva; não há comprovação
de disponibilidade na data da decisão, portanto não é uma base de treino pronta.

## Indicador exige população e denominador

Um **indicador** resume uma pergunta por população, período e regra. O percentual
sozinho esconde o tamanho do grupo e o tratamento das ausências.

Exercício sintético: três linhas têm rótulos `1`, `0` e nulo. A proporção entre
rótulos válidos é `1/2`, não `1/3`. A base atual exige target não nulo; esse
exemplo serve para entender por que a regra do denominador deve ser explícita.

SQL didático sobre uma view da ABT chamada `abt`. A consulta de produção fica
na função `monthly_sql`, com nomes do contrato e guarda explícita do denominador:

```sql
SELECT
    MONTH,
    COUNT(*) AS casos,
    SUM(CASE WHEN target = 1 THEN 1 ELSE 0 END) AS casos_target_1,
    SUM(CASE WHEN target IN (0, 1) THEN 1 ELSE 0 END) AS rotulos_validos,
    1.0 * SUM(CASE WHEN target = 1 THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN target IN (0, 1) THEN 1 ELSE 0 END), 0)
        AS proporcao_target_1
FROM abt
GROUP BY MONTH;
```

`NULLIF(..., 0)` evita divisão por zero nesse exemplo. Um grupo sem rótulos
válidos não deve ser apresentado como uma proporção observada de zero.
Numerador e denominador precisam acompanhar o percentual no relatório.

## Cobertura, completude e ausência

**Cobertura de fonte** mede quantos casos têm correspondência na auxiliar.
**Completude de campo** mede preenchimento de uma coluna na população definida.
Um caso pode ter histórico com campos opcionais nulos, ou não ter histórico.
Esses estados respondem a perguntas diferentes.

O contrato permite ausência de observações históricas. Não se deve interpretar
essa ausência automaticamente como falha de qualidade ou como característica
financeira sem evidência semântica.

## Da consulta à interpretação

Uma **análise descritiva** relata padrões observados. Uma **hipótese** propõe
uma explicação a investigar. Uma conclusão causal exige desenho e evidência
além de uma diferença entre grupos.

O relatório mostra períodos, unidades, denominadores, grupos pequenos,
ausências e limites do recorte. A seleção de 50 mil casos controla o custo de
desenvolvimento; não foi desenhada como estimativa da carteira operacional.
`target=1` no conjunto rotulado não equivale automaticamente à taxa operacional
de inadimplência de uma instituição.

Gráficos temporais devem distinguir período do negócio e ordem de ingestão.
Uma correção recebida hoje pode alterar um indicador de mês antigo. Para
comparar antes/depois, usamos o mesmo recorte em publicações identificadas.

## Leitura guiada da implementação

Abra [ESCOPO_PRODUTO.md](../ESCOPO_PRODUTO.md) e acompanhe P01–P05. Para cada
pergunta, identifique fonte, população e limite. Em seguida:

1. Em [model.py](../../src/gold/model.py), acompanhe `build_abt`: agregação por
   caso, soma ordenada por num_group1, dois left joins e preenchimento somente
   de contagens/flags. A ordenação torna a soma double reproduzível sem arredondar.
2. Siga `affected_cases`: compare mudanças nas três Silver. Uma correção apenas
   no histórico deve selecionar o caso mesmo sem mudança na base principal.
3. Em [publish.py](../../src/gold/publish.py), leia `prepare_gold`: copie a ABT
   pai para destino privado, recalcule casos afetados, faça MERGE e compare com
   a recomputação integral. A cópia tem custo físico; o MERGE é por caso afetado.
4. Volte a `monthly_sql`. Indicadores são pequenos e materializados por inteiro
   após cada atualização. Isso inclui períodos antigos e remove meses vazios.
5. Em [quality.py](../../src/gold/quality.py), compare os oráculos: ABT contra
   SQL Silver e indicadores contra contagens diretas Silver. Aceitar somente
   uma contagem igual não detectaria uma soma errada.

A [operação Gold](../gold/ABT_E_INDICADORES.md) mostra execução e consumo por
manifesto. A [evidência F06](../evidencias/F06_GOLD.md) registra correções,
atraso, falha/retomada e reprodução histórica. F07 usa essas saídas aprovadas
para responder às perguntas e revisar a interpretação, sem refazer o ETL no notebook.

## Consumo, visualização e comunicação em F07

**Transformar** prepara o produto de dados; **consumir** consulta o produto
aprovado para uma pergunta. O relatório não reexecuta a Silver ou constrói
outra ABT. Isso conserva as regras produtivas num único lugar e permite
identificar exatamente os dados analisados.

A [matriz de perguntas](../analise/PERGUNTAS_E_METODO.md) define população,
período, colunas e limite antes de apresentar as respostas. A análise mensal
usa todos os casos da publicação final; a comparação de correção usa somente
as duas publicações que têm os mesmos casos e rótulos. Chegada atrasada é outra
comparação: muda o denominador, e misturá-la à correção impediria explicar o efeito.

Em [run_analysis.py](../../src/pipelines/run_analysis.py), siga `require_triplet`
e `collect_view`. O trio de IDs é explícito. Cada manifesto fixa cinco
tabelas por versão/UUID; CURRENT continua inalterado. Em
[queries.py](../../src/analytics/queries.py), leia `monthly_analysis`: o SQL de
consumo conta novamente casos/rótulos/cobertura e compara todos os indicadores
com a tabela Gold. Uma consulta que só exibisse os números publicados não
seria essa conferência independente.

**Cobertura** e **completude** têm denominadores diferentes. No recorte real,
40.076/50.000 casos têm histórico, mas 208.576/215.390 observações têm montante
preenchido. A primeira fração responde sobre casos; a segunda, sobre linhas
históricas. Há 79 casos com histórico presente e montantes todos nulos. Isso
não é o mesmo estado dos 9.924 casos sem observações.

Em [report.py](../../src/analytics/report.py), `charts` recebe somente agregados
conferidos. Matplotlib exporta PNG e SVG para figuras independentes; o HTML
embute PNGs para abrir offline. O [wrapper analítico](../analise/EXECUCAO.md)
carrega dependências gráficas isoladas, sem mudar o ambiente produtivo anterior.

Um **sinal de leitura** chama atenção, sem constituir um teste estatístico.
Aqui, grupos com n<500 ou menos de 20 target=1 são destacados e continuam na
tabela. A janela observada parcial mostra as datas extremas; não prova perda
na origem. Março/2020 começa no dia 2 neste recorte e outubro termina no dia 5.
Não apresentar a diferença de percentuais como tendência causal de uma carteira.

A [leitura dos resultados](../analise/RESULTADOS.md) responde P01–P06. Na
correção, o caso 64 muda de annuity 2436 para 2437 e montante histórico 6899 para
6900; contagens e taxas mensais ficam iguais. O caso tardio 135 aumenta janeiro
de 2.520 para 2.521 casos, mantendo 69 target=1. Essas são explicações distintas.

**Reproduzir** exige mais que reencontrar um gráfico semelhante. Duas execuções
em processos novos fixaram o mesmo trio, código e configuração: semantic.json,
seis CSVs e 12 PNG/SVG coincidiram byte a byte. Metadata e HTML registram run_id
próprio, então não são usados como teste de igualdade dos resultados. A
[evidência F07](../evidencias/F07_ANALISE.md) registra a prova.

## Atividade e conferência

Um caso ganha uma observação histórica, mas sua linha na base não muda.
Quais saídas podem precisar de atualização?

**Conferência:** agregações desse caso, sua linha ABT e indicadores dos grupos
afetados, como cobertura no período original. Atualizar Gold somente quando
`train_base` muda perderia correções originadas nas auxiliares.

Próximo: [11 — Operação e armazenamento](11_OPERACAO_E_STORAGE.md).
