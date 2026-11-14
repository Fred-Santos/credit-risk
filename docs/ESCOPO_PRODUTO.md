# Produto de dados — Credit Risk Lakehouse

Versão 1, em 12/11/2026. Entrega de F00.1.

Status atualizado em F07: fonte Home Credit, contratos, ingestão, Silver,
publicação e Gold aprovados. As perguntas P01–P06 foram operacionalizadas na
[matriz analítica](analise/PERGUNTAS_E_METODO.md) e respondidas no
[relatório retrospectivo](analise/RESULTADOS.md). Objetos locais e operação
integrada continuam no roteiro.

## 1. Problema e público

Construir uma base analítica de crédito cujo conteúdo e indicadores possam ser
explicados após novas cargas, correções e reprocessamentos. O consumidor precisa
confiar no grão, identificar qual publicação consultou e recuperar um resultado
anterior sem depender do estado atual das tabelas.

Público simulado: equipe de análise de risco. Responsável pelo laboratório e
pela explicação das decisões: Frederico Costa. Não há cliente empresarial nem
operação de produção representados neste projeto.

Enunciado do produto:

> Disponibilizar uma ABT de crédito, indicadores e análises retrospectivas,
> com ingestão rastreável, atualização incremental demonstrada e reprodução
> de resultados por publicação aprovada.

## 2. Unidade de análise e grãos

| Saída | Grão pretendido | Validação necessária |
|---|---|---|
| ABT | Uma linha por unidade de análise da fonte | Chave única, não nula e sem multiplicação nos joins |
| Indicadores de desfecho | Período/coorte e segmentos sustentados pela fonte | Mesmo denominador e população nas comparações |
| Indicadores de cobertura | Fonte auxiliar e recorte da base | Chave de relação e significado da ausência |
| Indicadores da pipeline | Execução, etapa e lote | Separar execução técnica de período do negócio |

No desenho Home Credit, a unidade é o caso de crédito (`case_id`), conforme a
[descrição oficial](https://www.kaggle.com/c/home-credit-credit-risk-model-stability/data).
Uma fonte substituta pode exigir outro grão, por exemplo cliente no snapshot.
Nesse caso, adaptar nomes e contrato antes do desenvolvimento. Não renomear um
cliente como caso de crédito apenas para manter os nomes atuais.

As tabelas 1:N devem manter seu grão na Silver e ser agregadas antes do join na
ABT. O número de linhas da ABT precisa coincidir com o conjunto de unidades
elegíveis do recorte, segundo a política de rejeição registrada no contrato.

## 3. Perguntas e evidências necessárias

Esta matriz preserva a motivação das perguntas do escopo inicial. A inspeção,
Gold e consumo já foram executados; a definição atual de população, períodos e
cálculos está na [matriz F07](analise/PERGUNTAS_E_METODO.md).

| ID | Pergunta | Campos ou artefatos necessários | Evidência já localizada | Condição de uso |
|---|---|---|---|---|
| P01 | Como se distribui o volume de unidades no conjunto e nos períodos disponíveis? | Identificador e período real documentado | Dicionário histórico de `train_base`: `case_id`, `date_decision`, `MONTH`, `WEEK_NUM` | Tendência só com múltiplos períodos comparáveis; snapshot único permite apenas composição |
| P02 | Qual a proporção do desfecho rotulado no recorte? | Identificador, rótulo e definição de rótulo válido | Dicionário histórico de `train_base`: `target` | Publicar numerador, denominador e ausências; não chamar automaticamente de taxa da carteira |
| P03 | Qual a cobertura das informações complementares? | Chave da base e chave auxiliar | Dicionários históricos de `train_static_0` e `train_applprev_1` | A ausência pode ser legítima; cobertura não é sinônimo de completude de todos os campos |
| P04 | Uma correção altera quais unidades e indicadores? | Lote/revisão, chaves afetadas e duas publicações | [Comparação baseline/corrected F07](analise/RESULTADOS.md) | Identificar correção como simulação e comparar exatamente o mesmo recorte |
| P05 | É possível reproduzir uma análise anterior? | Versões de tabelas, código, configuração e entradas | [Publicações F05/F06 e reprodução F07](analise/EXECUCAO.md) | A retenção deve preservar os arquivos necessários |
| P06 | A pipeline entrega dados confiáveis e recuperáveis? | Checks, métricas, logs e testes de falha | [Publicação F05](evidencias/F05_PUBLICACAO.md), [Gold F06](evidencias/F06_GOLD.md) e [análise F07](evidencias/F07_ANALISE.md) | Usar evidências vinculadas à execução e às publicações consultadas |

Referências locais da matriz:

- [Base principal](data_dictionary/tables/parquet_files__train__train_base.md).
- [Estática — shard 0](data_dictionary/tables/parquet_files__train__train_static_0_0.md) e [shard 1](data_dictionary/tables/parquet_files__train__train_static_0_1.md).
- [Histórico — shard 0](data_dictionary/tables/parquet_files__train__train_applprev_1_0.md) e [shard 1](data_dictionary/tables/parquet_files__train__train_applprev_1_1.md).
- [Implementação Bronze](../src/bronze/build_bronze.py) e [regras de qualidade](../src/quality/engine.py).

O mapeamento Home Credit foi confirmado nas etapas seguintes e a fonte foi
mantida para desenvolvimento. Uma eventual substituição deve refazer P01–P03
com os campos efetivamente disponíveis e preservar P04–P06 como requisitos de
engenharia.

## 4. Entregas obrigatórias

| Entrega | Conteúdo | Como será aceita |
|---|---|---|
| Fonte e contratos | Origem, condições de uso, campos, grãos, chaves, períodos e limites | Fonte adequada e contratos verificados contra arquivos |
| Ambiente | Dependências, configuração, instruções e recursos medidos | Execução em ambiente limpo |
| RAW/Bronze | Aquisição selecionada, origem preservada, manifestos e rastreabilidade | Reexecução e recuperação comprovadas |
| Silver Delta | Tabelas tratadas, chaves e revisões controladas | Contratos e merge aprovados nos cenários de teste |
| Gold | ABT e tabelas/views de indicadores | Unicidade e reconciliação com Silver |
| Análises | Relatório/notebook com gráficos, consultas e limitações | Perguntas respondidas e execução com publicação fixada |
| Operação | Comando de execução, logs, métricas, lineage e publicação | Falha impede avanço da publicação aprovada |
| Objetos locais | Serviço escolhido e integração validada | Persistência, transações e recuperação no destino |
| Testes e CI | Fixtures, integração e reconciliação | Cenários obrigatórios executados sem integração ignorada |
| Apresentação | README, arquitetura, decisões e demonstração | Terceiro consegue acompanhar e reproduzir |

ABT, indicadores e análise são produtos relacionados, mas diferentes. A ABT
preserva detalhe; indicadores agregam; análise interpreta. Não encerrar a Gold
apenas com uma tabela sem dicionário e reconciliação.

## 5. Limites do MVP

- Análise retrospectiva de um conjunto público com origem e condições verificáveis.
- Um único formato transacional inicial: Delta Lake.
- Desenvolvimento em recorte determinístico; volume final decidido após medição.
- Lotes, correções, atrasos e falhas artificiais identificados como simulações.
- Um escritor de pipeline por vez no laboratório, com proteção contra concorrência indevida.
- Relatório reproduzível é obrigatório; dashboard interativo é opcional.
- Sem modelo preditivo, feature store, retreinamento ou concessão automatizada.
- Sem provisionamento AWS; migração permanece em projeto posterior.
- Sem alegar produção, escala distribuída, retorno financeiro ou redução de risco não medidos.

Não há meta de latência, SLA, custo ou volume inventada nesta etapa. Registrar
limites locais após as primeiras medições e justificar qualquer objetivo adicional.

## 6. Regras para interpretar os resultados

O rótulo é um desfecho, não uma recomendação de concessão. Informações obtidas
após a decisão não podem ser apresentadas como disponíveis naquela decisão.
Percentuais devem ter denominadores definidos; grupos pequenos, nulos, períodos
incompletos e recorte precisam ser visíveis. Associação entre atributos e desfecho
não comprova causalidade.

Se a fonte escolhida tiver apenas um snapshot, não inventar tendência temporal
de desfecho. Nesse cenário, os meses históricos de pagamento podem sustentar
análise própria, quando documentados; a sequência de ingestão continua simulada.

## 7. Critério de aceite desta definição

F00.1 é atendida por: público e problema descritos, ABT/indicadores/análises
definidos, perguntas ligadas a evidências possíveis, escopo limitado e ausência
de promessas de impacto não medido. Esse aceite é documental. Não aceita F00.2,
F00.3 ou qualquer comportamento da pipeline.

Fonte mantida: Home Credit, com acesso API e inspeção inicial confirmados.
Contratos, recorte, Bronze reconciliada, protocolo de eventos e Silver inicial
com aceite operacional estão validados no escopo atual. F04 validou lotes,
revisões, merge, idempotência/atraso e reconstrução equivalente. F05 validou
publicação/recuperação, F06 entregou ABT e indicadores reconciliados e F07
entregou análise com gráficos e reprodução. F08 validou SeaweedFS/S3A, replay
incremental e três publicações reconciliadas, com recuperação e reinício;
a linha de base F08 teve 129 verificações globais sem ignorados. F09 consolidou
comando, supervisão, métricas, lineage e resumo, com matriz real de sucesso/falhas
e recuperação. F10 aprovou 153 testes obrigatórios em ambiente novo e T01–T24,
configurou CI sintética e validou o export sem dados ou outputs. F11 concluiu a
entrega técnica com demo, pacote e autorrevisão; 72/72 itens, conforme o
[roteiro](ROTEIRO_EXECUCAO_LAKEHOUSE.md). Condições de ambiente/fonte continuam em
[AMBIENTE_LOCAL.md](AMBIENTE_LOCAL.md) e [SOURCE.md](governance/SOURCE.md).
