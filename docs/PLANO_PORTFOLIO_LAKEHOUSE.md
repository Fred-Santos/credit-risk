# Credit Risk como projeto de Data Lakehouse

Análise em 12/11/2026. Direção geral aprovada pelo usuário; execução em andamento.

Documentos de execução e aprendizagem:

- [Roteiro de execução e controle](ROTEIRO_EXECUCAO_LAKEHOUSE.md): tarefas, dependências, testes e critérios de conclusão.
- [Guia de estudo do projeto](GUIA_ESTUDO_LAKEHOUSE.md): conceitos, exemplos, exercícios e relação com o código.

O usuário concordou com a direção apresentada e confirmou que a Gold deve
entregar ABT e análises. Isso não comprova a adequação da fonte nem valida o
ambiente. Este diagnóstico é a referência inicial; o roteiro controla o avanço.

Atualização F00 em 12/11/2026: [escopo funcional definido](ESCOPO_PRODUTO.md),
[decisões registradas](DECISOES.md) e [avaliação da fonte](governance/SOURCE.md).
Após esclarecer sua inscrição na competição, o usuário confirmou o uso da Home
Credit no desenvolvimento; a revisão de divulgação externa fica antes da publicação.

Atualização F01: ambiente preparado e prova Spark/Delta validada. Execução,
autenticação e limites em [AMBIENTE_LOCAL.md](AMBIENTE_LOCAL.md); medições e testes
em [evidência F01](evidencias/F01_AMBIENTE.md). Os achados abaixo preservam o
diagnóstico inicial, anterior à instalação do runtime.

Atualização da aquisição/inspeção: seis arquivos reais foram adquiridos e as três
tabelas lógicas passaram pelas verificações iniciais. Contagens e limites em
[evidência da fonte real](evidencias/F00_F02_FONTE_REAL.md). Contratos e recorte
passam a ser a próxima entrega.

Atualização dos contratos/recorte: F00 concluída no escopo local, com três
contratos executáveis e seleção de 50 mil casos validada e reutilizada na
reexecução. [Evidência atual](evidencias/F00_CONTRATOS_RECORTE.md). O diagnóstico
inicial abaixo permanece como registro; a próxima entrega é a adaptação da Bronze.

Atualização F02.3: Bronze recebeu explicitamente o recorte em namespace separado.
Carga e retry passaram; falhas/locks foram testados com Spark real. Resultados e
limites em [evidência Bronze](evidencias/F02_BRONZE_RECORTE.md). A próxima entrega
é o contrato de eventos/revisões, seguido do alinhamento de regras e reconciliação.

Atualização F02.4: contrato de eventos, revisões e entregas implementado em
landing isolada de referência. Quatro pequenos pacotes com payloads reais e
correção declarada foram publicados e reutilizados; conflito foi rejeitado.
[Evidência de eventos](evidencias/F02_EVENTOS_REVISOES.md). Gerador completo e
merge Silver continuam em F04; próxima entrega: qualidade Bronze em F02.5.

Atualização F02.5: qualidade Bronze derivada dos schemas e políticas do contrato,
com 39 checks reais aprovados e nenhuma regravação. Histórico opcional vazio é
permitido com schema; tabelas ausentes, desvios e falhas de leitura/configuração
bloqueiam. [Evidência de qualidade](evidencias/F02_QUALIDADE_BRONZE.md).
Próxima entrega: reconciliação integral de valores e proveniência em F02.6.

Atualização F02.6: comparação integral de valores nos dois sentidos e auditoria
de proveniência integradas ao gate. As 315.390 linhas da Bronze foram
reconciliadas com o recorte e a RAW selecionada, sem diferenças. F02 concluída
no escopo local; próxima entrega: catálogo de regras Silver em F03.1.
[Evidência de reconciliação](evidencias/F02_RECONCILIACAO_BRONZE.md).

Atualização F03.1: notebook catalogado por célula/campo e propostas revalidadas
na Bronze real. A Silver inicial preservará números, códigos, colunas e nulos;
conversões de datas exigirão guarda de perda. A política ainda não foi aplicada.
[Catálogo Silver](silver/CATALOGO_REGRAS_SILVER.md). Próxima entrega: leitor lógico
da Bronze aprovada em F03.2.

Atualização F03.2: leitor lógico implementado e exercitado nas 315.390 linhas
reais, com gate, arquivos, schemas e chaves validados sob lock. Nenhuma tabela
Silver foi gravada. [Leitura aprovada](silver/LEITURA_BRONZE.md).
Próxima entrega: tratamentos com métricas de perda em F03.3.

Atualização F03.3: tratamentos executáveis validados no recorte. As 23 colunas
de datas foram convertidas sem novos nulos e as 315.390 linhas passaram na prova
de preservação integral. Não houve escrita de tabelas Silver.
[Tratamentos e guardas](silver/TRATAMENTOS.md). Próxima entrega: materialização
Delta inicial em F03.4.

Atualização F03.4: credit_cases, credit_static e previous_applications foram
materializadas em pacote Delta imutável, versão 0 por tabela, com leitura
reconciliada. [Materialização inicial](silver/DELTA_INICIAL.md). Próxima entrega:
contratos do estado persistido em F03.5; aceite operacional Silver ainda pendente.

Atualização F03.5: contratos do estado Delta persistido passaram em 29 checks,
com zero órfãos/duplicatas e cardinalidades medidas. Diagnósticos de datas
posteriores à decisão foram registrados sem alterar dados.
[Contrato Silver](contratos/SILVER_INICIAL.md). Próxima entrega: execução
repetível e aceite operacional em F03.6.

Atualização F03.6: comando Silver único com seleção explícita, controle de
pacote existente e recibo operacional separado. Criação e retry reais passaram
com 29 checks, preservando valores, UUIDs, versões e aceites anteriores. F03
concluída no escopo inicial local; 24/72 itens. Próxima entrega: gerador de
lotes/cenários em F04.1. [Execução e evidência](evidencias/F03_EXECUCAO_SILVER.md).

Atualização F04: os seis itens foram aceitos com replay Parquet distribuído,
precedência, deduplicação, merge e reconstrução equivalente. Novos casos,
correções auxiliares, reenvios, revisão antiga e atraso passaram no recorte real;
315.390 linhas finais, 29 checks e zero diferenças de valores. Runner com 117
verificações, sem ignorados. Demonstração em 18 min 59 s, pico RSS somado 5,06 GiB;
fonte e F03 preservadas. Andamento: 30/72, próxima F05.1. Detalhes e reestimativa
de capacidade em [evidência F04](evidencias/F04_INCREMENTAL.md).

Atualização F05/F06 em 13/11/2026: evolução Silver v2, manifestos/CURRENT,
recuperação, histórico e retenção locais aprovados; Gold com ABT de 50 mil
casos e indicadores de 22 meses, correções auxiliares e atraso reconciliados.
Andamento atual: **42/72**, próxima F07.1, perguntas analíticas. Evidências
[F05](evidencias/F05_PUBLICACAO.md) e [F06](evidencias/F06_GOLD.md). Os parágrafos
anteriores e o diagnóstico abaixo preservam o estado de cada etapa histórica.

Atualização F07 em 13/11/2026: perguntas P01–P06 respondidas em relatório
HTML/Markdown com gráficos e tabelas. As três publicações foram consumidas
explicitamente; duas execuções em processos novos reproduziram resultados e
figuras byte a byte. [Resultados](analise/RESULTADOS.md) e
[evidência](evidencias/F07_ANALISE.md). Andamento: **48/72**, próxima F08.1,
seleção de armazenamento de objetos local.

## Recomendação

O projeto é um candidato adequado, condicionado à validação das condições de
uso da fonte. Aproveitar a ingestão, governança, qualidade e exploração existentes
e mudar o objetivo principal para uma base analítica incremental e auditável de
risco de crédito. Modelo preditivo, feature store e retreinamento ficam para uma
evolução posterior. Essa proposta não altera a prioridade do Data Warehouse no
planejamento geral do portfólio.

O diferencial demonstrável será processar novos lotes e correções, recuperar
falhas, controlar mudanças de esquema e reproduzir indicadores de uma versão
anterior. Pastas Bronze/Silver/Gold, isoladamente, não entregam esse resultado.

## Diagnóstico do repositório

| Área | Evidência atual | Trabalho necessário |
|---|---|---|
| Fonte | `src/pipelines/ingest_raw.py` identifica a competição Home Credit — Credit Risk Model Stability | Validar termos, acesso, período e recorte; distinguir da competição Home Credit Default Risk |
| RAW | Download, profiling, inventário, checks, hashes e lineage | Fixar contrato de aquisição e seleção dos arquivos; registrar o que foi descartado |
| Bronze | Parquet com `_run_id`, `_ingest_date`, `_source_file`, manifesto por arquivo, staging e lock | Preservar a implementação local e desenhar a recepção de versões/correções |
| Recuperação | Código retoma arquivos pendentes e ignora os já publicados; rejeita fonte alterada | Testar com Spark real e desenvolver recuperação nas tabelas transacionais |
| Qualidade | Engine configurável, domínio de target, chaves, tipos, referências e severidades | Validar unicidade entre shards, regras Silver/Gold e qualidade antes da publicação para consumo |
| Silver | Notebook de 236 células com exploração e propostas de tratamento | Extrair transformações para módulos executáveis e contratos explícitos |
| Gold | Não há pipeline implementado identificado | Criar base por caso de crédito e agregações temporais com reconciliação |
| Lakehouse | Leituras/escritas atuais usam Parquet, sem formato de tabela transacional | Adotar um formato e demonstrar merge, snapshots, evolução de esquema e reprocessamento |
| Observabilidade | Artefatos por execução, inventário de arquivos e bytes | Medir duração do pipeline inteiro, contagens exatas, entradas/saídas, rejeições e status |
| Reprodução | Não foram encontrados manifesto de dependências, ambiente fixado ou CI | Fixar versões compatíveis, comandos e testes automatizados |
| Apresentação | README orientado a ML, estrutura antiga e comandos que não correspondem aos arquivos atuais | Atualizar propósito, arquitetura, estágio real e evidências |

A análise considerou as alterações locais já existentes sem modificá-las.

### Limites da validação realizada

- `python3 -m unittest discover -s tests -v`: 19 testes descobertos,
  16 aprovados e 3 ignorados por ausência de PySpark.
- Os testes aprovados usam doubles para Spark: demonstram contratos de código
  e recuperação de arquivos, não execução real de Spark/Delta.
- Não existe `data/` neste checkout. Não foi possível reconciliar os dados ou
  executar a pipeline ponta a ponta.
- Python 3 está disponível; PySpark e Delta não foram encontrados. `java` e
  `docker` não foram encontrados no PATH. Nada foi instalado.
- O ambiente desta sessão informa aproximadamente 15 GiB de RAM e 950 GiB livres.
  Isso não substitui a validação do computador informado no planejamento
  (32 GB de RAM e cerca de 200 GB disponíveis).
- As métricas históricas de fevereiro de 2026 registram aproximadamente 1,33 GB
  na RAW selecionada e 1,47 GB na Bronze antiga. Não representam o download
  completo, pico de disco, versões futuras ou consumo de memória.
- Os relatórios históricos antecedem o layout Bronze atual e os checks atuais.
  Um relatório antigo com zero falhas não comprova a validação do código atual.

## Fonte e problema de negócio

Proposta de problema: fornecer a uma equipe de análise de risco uma base
consistente por caso de crédito para acompanhar volume, composição e proporção
de desfechos rotulados ao longo do tempo, permitindo explicar alterações nos
indicadores após correções e reprocessamentos.

O grão inicial é um caso de crédito identificado por `case_id`, sujeito à
validação de unicidade. Não assumir que ele identifica uma pessoa única.

A documentação local de `train_base` registra `case_id`, `date_decision`,
`MONTH`, `WEEK_NUM` e `target`. O notebook registra datas de 2019-01-01 a
2020-10-05; o intervalo deve ser confirmado por uma execução reproduzível.
Contagens aproximadas distintas podem exceder o número de linhas e não servem
como prova de duplicidade ou de unicidade.

A descrição oficial da competição associa `target` ao desfecho de default
observado após um período. Isso não torna a base um extrato operacional em tempo
real. É necessário validar o significado e a disponibilidade temporal das
variáveis antes de interpretar indicadores.

Perguntas e entregas iniciais:

| Pergunta | Cálculo/entrega | Limite |
|---|---|---|
| Como varia o volume de casos no conjunto? | Contagem distinta de `case_id` por mês/semana | Não representa toda a operação de crédito da instituição |
| Como varia a proporção de `target=1`? | Casos com `target=1` / casos com rótulo válido, com numerador e denominador | Descrição retrospectiva da amostra; não presumir uma taxa operacional de inadimplência |
| Qual é a cobertura das fontes complementares? | Casos com correspondência / casos da base e percentual de nulos | Ausência de histórico pode ser legítima |
| Uma correção mudou o resultado? | Comparação do mesmo indicador e recorte entre versões publicadas | Identificar a simulação e o lote responsável |
| O processamento é confiável? | Duplicatas, rejeições, reconciliação, duração, bytes e status | Medir o pipeline, não só a escrita do relatório de métricas |

Segmentações por perfil e montantes dependem da validação de campos e definições.
Não propor aprovação/reprovação, lucro, perda esperada ou impacto financeiro sem
dados que sustentem esses cálculos. Diferenças entre grupos não provam causalidade.

### Condições de uso — atualização F00

A avaliação e os localizadores estão em [SOURCE.md](governance/SOURCE.md).
O usuário informou inscrição na competição e confirmou a continuidade com dados
reais. A aquisição depende de autenticação da API nesta sessão. O alcance da
divulgação externa será revisado antes da publicação, sem bloquear o desenvolvimento.

## Arquitetura proposta

```text
Home Credit / arquivos autorizados
    -> RAW preservada + manifesto de aquisição
    -> Bronze rastreável em Parquet
    -> Silver em Delta: casos e tabelas auxiliares tratadas
    -> Gold em Delta: base por caso e indicadores por período
    -> consultas SQL + relatório analítico reproduzível

Lotes simulados identificados -> Bronze -> mesmas regras de processamento
Execuções -> qualidade, métricas, lineage e manifesto de publicação
```

Recomenda-se Delta Lake como primeiro formato por aproveitar o PySpark existente
e atender a merge, histórico e evolução de esquema. Apache Iceberg é a alternativa
a considerar se interoperabilidade entre motores se tornar requisito concreto.
Delta passa a ser a escolha de trabalho para a execução aprovada; versões de
Python, Java, Spark e Delta devem ser validadas em conjunto antes de instalação.

Primeiro validar uma tabela Delta no filesystem local com recorte pequeno.
Depois concluir o armazenamento de objetos local previsto no planejamento,
selecionando uma implementação compatível e verificando leitura, escrita e
recuperação pelo conector. O lock e o rename da Bronze atual dependem de filesystem
local: não presumir que funcionem com as mesmas garantias em armazenamento de
objetos. Manter RAW/Bronze locais durante a prova inicial reduz a mudança inicial;
a posição final dessas camadas precisa constar no desenho aprovado.

Não é necessário acrescentar Kafka, cluster Spark, múltiplos motores ou catálogo
distribuído ao MVP. Registrar tabelas por nome para consultas SQL e documentar
localização, esquema, proprietário lógico e contratos. Orquestração inicial pode
ser um comando Python com etapas e status; uma ferramenta dedicada só entra
quando houver necessidade de agenda, dependências e operação.

## Recorte mínimo e contratos

Começar com `train_base`, `train_static_0` (unindo os shards `_0` e `_1`) e uma
tabela de profundidade 1, candidata `train_applprev_1` (também unindo os shards).
Selecionar inicialmente até 50 mil `case_id` por procedimento determinístico e
registrado, mantendo as linhas relacionadas nas auxiliares. Esse número é um
limite de desenvolvimento proposto, não uma amostra estatística representativa.

Validar chaves em cada dataset lógico após unir os shards. Repetições de
`case_id` em tabelas de profundidade 1/2 podem ser esperadas; confirmar as chaves
compostas com `num_group1`/`num_group2`. Antes de juntar tabelas 1:N à base por
caso, agregar ao grão desejado para evitar multiplicação de linhas e indicadores.
Evolução de esquema deve ser explícita: o `allowMissingColumns=True` do notebook
não deve mascarar divergências inesperadas.

O contrato Bronze também precisa evoluir: checks de unicidade adequados ao
snapshot atual não podem proibir todas as revisões válidas de um caso em lotes
diferentes. Separar identidade do evento/lote da chave de negócio da Silver.
Preservar fontes originais; representar correções como novas entradas identificadas,
sem sobrescrever o mesmo arquivo RAW e sem contornar a rejeição atual de fontes
alteradas. Mapear cada nova entrada ao dataset lógico de destino.

## Demonstrações obrigatórias do Lakehouse

A base é disponibilizada como arquivos da competição. A ingestão incremental
será uma reprodução controlada de lotes, não CDC real da Home Credit.

1. Separar os casos em lotes por `date_decision`/`WEEK_NUM`, sem deixar histórico
   auxiliar de casos futuros entrar antes da base correspondente. Datas de
   decisão não comprovam datas reais de chegada de cada fonte.
2. Executar carga inicial e lote de casos adicionais com `MERGE` por chave validada.
3. Reexecutar um lote e demonstrar que conteúdo e indicadores não duplicam.
4. Introduzir uma correção e um registro atrasado identificados como simulações.
   Registrar `batch_id`, versão de origem simulada e precedência; lote antigo não
   pode sobrescrever uma revisão mais recente. Empates conflitantes devem falhar
   ou ir para quarentena, não ser resolvidos por ordem arbitrária.
5. Injetar uma duplicata no lote e aplicar deduplicação determinística antes do
   merge. Não supor que Delta impõe unicidade de chave primária.
6. Adicionar uma coluna técnica de simulação com evolução autorizada de esquema;
   mudança incompatível de tipo deve bloquear a carga e produzir diagnóstico.
7. Ler uma versão anterior e reproduzir os indicadores daquela publicação.
   Registrar versões de todas as tabelas de entrada, commit do código,
   parâmetros e checksums/manifests. Histórico da tabela não substitui histórico
   de negócio nem garante reprodução após remoção dos arquivos antigos.
8. Interromper antes/depois de um commit e entre Silver/Gold; retomar sem expor
   uma publicação parcial ao consumidor. Transações por tabela não tornam a
   execução inteira atômica. Publicar um manifesto com versões aprovadas ao fim
   das verificações e fazer os consumidores usarem essa publicação.
9. Comparar processamento incremental com reconstrução integral dos mesmos
   lotes e revisões: igualdade de chaves, valores de negócio e indicadores,
   desconsiderando metadados de execução que legitimamente diferem.

Não usar o `target` final como dado disponível no momento da decisão de crédito.
No MVP ele serve para análise retrospectiva. Atualização tardia de rótulo, se
demonstrada, deve ser identificada como simulação com premissas explícitas.
Definir retenção das versões e não executar limpeza que inviabilize a demonstração.

## Entregas pequenas e critérios de aceitação

| Ordem | Entrega | Arquivos principais previstos | Critério de aceitação |
|---|---|---|---|
| 1 | Fonte, escopo e ambiente | `docs/governance/SOURCE.md`, contrato de tabelas e registro de decisões | Termos registrados; campos, período e grãos confirmados; recorte determinístico; recursos e espaço medidos; formato escolhido |
| 2 | Execução reproduzível | `pyproject.toml` ou requirements com versões, configuração central, README | Ambiente limpo executa RAW/Bronze do recorte; integração Spark passa; parâmetros de paths/Spark realmente são consumidos |
| 3 | Primeira Silver Delta | `src/silver/`, checks Silver, testes de integração | Casts com detecção de falhas, união de shards, chaves e referências válidas; primeira carga e reexecução corretas |
| 4 | Incremental e recuperação | gerador de lotes de demonstração, merge, manifesto de publicação | Todos os cenários acima passam; erros são rastreáveis; reconstrução integral reconcilia |
| 5 | Gold e análise | `src/gold/`, consultas SQL, relatório/notebook de consumo | Uma linha por caso na base; indicadores reconciliados; interpretação e limitações documentadas; versões de entrada registradas |
| 6 | Armazenamento de objetos local e automação | configuração de storage, adaptação de I/O, CI | Conector e garantias validados; pipeline do recorte e testes executáveis; falhas bloqueiam publicação; consumo de recursos medido |
| 7 | Apresentação | README, diagrama, evidências de execução e demonstração | Terceiro reproduz a entrega e verifica carga, correção, falha, recuperação e leitura histórica |

O recorte deve passar pelas etapas antes de ampliar para todas as tabelas.
Reservar espaço para arquivos de download, extração, dados tratados, shuffle,
histórico Delta e imagens de containers. Dimensionar após medir o pico de uma
execução; tamanho de Parquet não equivale à RAM necessária. Rever `coalesce(1)`
após medições. Não manter todas as soluções do portfólio ativas simultaneamente.

## Registro de decisões

Registro atualizado após a concordância do usuário em 12/11/2026. Aprovação da
direção não equivale a implementação ou validação. Fonte e fornecedor do
armazenamento continuam sujeitos às verificações indicadas.

| Decisão proposta | Status | Motivo e alternativas | Pendência / próximo passo |
|---|---|---|---|
| Priorizar engenharia e análise de risco auditável | Aprovada | Alinha ao portfólio; alternativa é manter ML como centro | Formalizar escopo e atualizar README durante a execução |
| Reaproveitar Home Credit Model Stability | Aprovada para continuidade do desenvolvimento | Usuário informou inscrição e confirmou fonte real | Configurar autenticação API e validar dados; revisar divulgação externa antes de publicar |
| Usar Delta Lake como único formato inicial | Aprovada | Reutiliza PySpark; alternativa Iceberg para requisito de múltiplos motores | Validar compatibilidade e ambiente |
| Preservar RAW/Bronze e iniciar mudanças na Silver | Aprovada | Reduz retrabalho; alternativa é converter toda a Bronze de início | Definir contrato de revisões e limites da publicação local |
| Simular chegada incremental e correções explicitamente | Aprovada | Fonte estática não fornece CDC operacional | Definir lotes, precedência, rótulos e cenários de teste |
| Usar armazenamento de objetos local após a prova Delta | Aprovada | Atende arquitetura planejada com validação gradual | Selecionar implementação e testar conector e garantias |
| Entregar ABT por caso, indicadores e análises | Aprovada | Atende Engenharia e Análise; alternativa é encerrar na Silver | Validar grãos, campos, fórmulas e publicação reproduzível |
| Adiar modelo preditivo, feature store e retreinamento | Aprovada | Evita ampliar escopo antes de concluir a entrega analítica | Reavaliar depois do MVP; migração AWS continua em projeto separado |

## Comandos atuais de verificação

Na raiz do repositório, sem instalar dependências:

```bash
python3 -m unittest discover -s tests -v
git status --short
```

Após preparar ambiente compatível e disponibilizar os dados conforme os termos,
os entrypoints existentes são:

```bash
python3 -m src.pipelines.run_raw_mvp
python3 -m src.pipelines.run_bronze_mvp
```

Esses comandos não implementam o Lakehouse proposto. A ingestão atual baixa o
conjunto da competição e remove ZIPs após extração, CSVs duplicados e a pasta
Parquet de teste; revisar essa seleção antes de executá-la para um novo recorte.

## Referências consultadas

- [Home Credit — descrição dos dados](https://www.kaggle.com/competitions/home-credit-credit-risk-model-stability/data): identificação da competição e descrição de `target`/`WEEK_NUM` nos resultados indexados. O conteúdo integral da página não ficou acessível na consulta.
- [Regras da competição](https://www.kaggle.com/c/home-credit-credit-risk-model-stability/rules): seções relevantes recuperadas na etapa F00; avaliação atual em SOURCE.
- [Delta Lake — merge e atualizações](https://docs.delta.io/delta-update/): semântica de merge, deduplicação e evolução de esquema.
- [Delta Lake — leitura, escrita e versões](https://docs.delta.io/delta-batch/): time travel, retenção, validação e evolução de esquema.


## Atualização F08 — 13/11/2026

O diagnóstico inicial acima permanece como registro histórico. F08 escolheu
SeaweedFS 4.53 nativo e validou S3A/Delta, espelho de entradas por hash, replay
incremental e três publicações Silver/Gold equivalentes à referência filesystem.
Falha/retry, rollback, reinício e consumidor independente passaram; a regressão
global passou com 129 verificações sem ignorados. Andamento atual: **54/72**,
F00–F08 aceitas. Operação unificada e observabilidade seguem em F09.1.
Consulte [evidência F08](evidencias/F08_OBJETOS.md),
[arquitetura](objetos/DECISAO_E_ARQUITETURA.md) e
[roteiro atual](ROTEIRO_EXECUCAO_LAKEHOUSE.md).


## Atualização F09 — 13/11/2026

Comando operacional, estados/erros e retry, métricas, lineage/inventário, resumo
e matriz de recuperação foram validados. Andamento atual: **60/72**, F00–F09
aceitas no escopo local. A matriz usou entradas aprovadas e destinos privados,
sem alterar publicações reais. Próxima: F10.1, organizar suítes e consolidar CI
e aceitação. [Evidência F09.6](evidencias/F09_MATRIZ_OPERACIONAL.md).

## Atualização F10 — 13/11/2026

**66/72 itens**, F00–F10 aceitas no escopo local. Suíte integral em ambiente
novo: 153 testes obrigatórios, zero ignorados; matriz T01–T24 e e2e sintético
aprovados. CI configurada, sem job remoto executado. A seleção antes da leitura
reduziu pacotes tipados de sete para um; cinco tabelas ficaram iguais. Export
sanitizado auditado e histórico preservado. Próxima: F11.1, revisão da entrega.
[Evidência F10](evidencias/F10_ACEITACAO.md).

## Encerramento F11 — 13/11/2026

**72/72 itens e 12/12 fases aceitos no escopo local.** README, arquitetura,
contratos/guia e caminhos revisados; demo sintética S3/Delta com correção,
falha/retomada e histórico; reprodução em cópia nova com seis CSVs idênticos.
Pacote de fonte sanitizada e demo inventada auditado. Autorrevisão declarada,
sem avaliador externo, job remoto, commit/tag, publicação ou AWS provisionada.
[Evidência F11](evidencias/F11_ENTREGA.md), [nota técnica](entrega/CONCLUSAO_TECNICA.md)
e [backlog/inventário AWS](entrega/EVOLUCAO_E_AWS.md).
