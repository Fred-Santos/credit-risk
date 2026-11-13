# Credit Risk Lakehouse

Laboratório local de Engenharia e Análise de Dados com Home Credit, PySpark e
Delta Lake. O objetivo é entregar uma ABT por caso de crédito e análises
retrospectivas, com cargas incrementais simuladas, correções rastreáveis e
reprodução de resultados por publicação.

## Estágio atual

**48/72 itens aceitos; F00–F07 concluídas no escopo local. Próxima: F08.1,
seleção do armazenamento de objetos local.**

O ambiente Linux/WSL usa Python 3.11.14, Java 17, Spark 3.5.7 e Delta 3.3.2.
Seis arquivos Home Credit foram adquiridos via API e inspecionados: base e
estática com 1.526.659 casos e histórico com 6.525.979 linhas. Um recorte
fixo de 50 mil casos conserva 215.390 observações históricas relacionadas.

A Bronze preserva valores e proveniência, com qualidade e reconciliação integral.
A Silver inicial converteu 23 datas sem perdas, materializou três tabelas Delta
e recebeu aceite operacional após 29 checks. F04 preservou esse pacote e
aplicou 315.398 entregas simuladas em outro estado: casos novos, duas correções
auxiliares, duplicatas, revisão antiga e atraso. O estado final coincidiu
integralmente com uma reconstrução independente.

F05 adicionou migração explícita para Silver v2, manifestos aprovados, ponteiro
CURRENT, retomada após falhas, rollback e retenção. Publicou os snapshots
baseline, corrected e late em 3 min 44 s, com pico RSS somado de 3,26 GiB.
Dados reais permanecem preservados; a prova destrutiva de VACUUM usa apenas fixture.

F06 publicou uma **ABT com 50.000 casos e 19 colunas** e indicadores SQL de
**22 meses**, com volume, proporção de target=1 e cobertura. Correções somente
nas auxiliares atualizam os casos afetados. Cada ABT incremental foi comparada
integralmente à recomputação; indicadores foram conferidos diretamente na
Silver. Falha após MERGE, retomada sem novo commit, retry e reprodução histórica
passaram. Execução completa: 3 min 13 s, pico RSS somado de 2,95 GiB.

A publicação analítica atual é `6f4406dd0180850e23d5283e`; seu manifesto fixa
três Silver e duas Gold. Os resultados são retrospectivos: não há validação de
disponibilidade dos atributos no instante da decisão. Objetos locais e operação
integrada seguem em F08/F09.

F07 entregou o **[relatório analítico com gráficos e tabelas](docs/analise/RESULTADOS.md)**,
respondendo às seis perguntas sobre volume, desfecho, cobertura, correção,
reprodução e confiabilidade. O relatório preserva denominadores, sinaliza
grupos pequenos e separa correção de montantes da chegada de um caso atrasado.
Duas execuções em processos novos reproduziram JSON, seis CSVs e 12 gráficos
PNG/SVG byte a byte. A primeira execução completa levou 49,844 s, com pico
RSS somado de aproximadamente 2,29 GiB, sem modificar dados ou CURRENT.

O runner global aprovou **126 verificações, sem ignorados**, incluindo quatro
suítes Delta isoladas (15/9/9/8 cenários) e seis cenários analíticos Spark. RAW, recorte,
Bronze, pacotes/aceites F03 e publicações F05 tiveram integridade conferida.

## Documentação

- [Contrato de eventos, revisões e demonstração local](docs/contratos/EVENTOS_REVISOES.md).
- [Qualidade Bronze e critérios de publicação](docs/QUALIDADE_BRONZE.md).
- [Reconciliação de valores e proveniência](docs/RECONCILIACAO_BRONZE.md).
- [Catálogo e política planejada da Silver](docs/silver/CATALOGO_REGRAS_SILVER.md).
- [Leitor lógico da Bronze aprovada](docs/silver/LEITURA_BRONZE.md).
- [Tratamentos Silver e controle de perdas](docs/silver/TRATAMENTOS.md).
- [Tabelas Delta iniciais e leitura por versão](docs/silver/DELTA_INICIAL.md).
- [Contrato do estado Silver persistido](docs/contratos/SILVER_INICIAL.md).
- [Execução repetível e aceite Silver inicial](docs/silver/EXECUCAO_INICIAL.md) e [evidência F03.6](docs/evidencias/F03_EXECUCAO_SILVER.md).
- [Lotes, revisões e merge incremental](docs/silver/INCREMENTAL.md) e [evidência F04](docs/evidencias/F04_INCREMENTAL.md).
- [Evolução, publicação, recuperação e retenção](docs/PUBLICACAO_E_RECUPERACAO.md) e [evidência F05](docs/evidencias/F05_PUBLICACAO.md).
- [Contrato ABT/indicadores](docs/contratos/ABT.md), [operação Gold](docs/gold/ABT_E_INDICADORES.md) e [evidência F06](docs/evidencias/F06_GOLD.md).
- [Perguntas e método analítico](docs/analise/PERGUNTAS_E_METODO.md), [relatório e conclusões](docs/analise/RESULTADOS.md), [execução F07](docs/analise/EXECUCAO.md) e [evidência](docs/evidencias/F07_ANALISE.md).
- [Execução local e autenticação Kaggle](docs/AMBIENTE_LOCAL.md).
- [Escopo do produto](docs/ESCOPO_PRODUTO.md).
- [Roteiro e controle de progresso](docs/ROTEIRO_EXECUCAO_LAKEHOUSE.md).
- [Curso aplicado de Engenharia e Análise de Dados](docs/GUIA_ESTUDO_LAKEHOUSE.md): 12 capítulos com conceitos, ferramentas, código e evidências do projeto.
- [Fonte e condições de uso](docs/governance/SOURCE.md).
- [Decisões](docs/DECISOES.md) e [evidência do ambiente](docs/evidencias/F01_AMBIENTE.md).
- [Aquisição e inspeção dos dados reais](docs/evidencias/F00_F02_FONTE_REAL.md).
- [Contratos](docs/contratos/README.md), [recorte/lotes](docs/RECORTE_E_LOTES.md) e [evidência da materialização](docs/evidencias/F00_CONTRATOS_RECORTE.md).
- [Bronze do recorte](docs/BRONZE_DO_RECORTE.md) e [evidências de recuperação](docs/evidencias/F02_BRONZE_RECORTE.md).

## Preparar e validar

Na raiz do projeto, em Linux x86_64 com Python 3 e acesso à internet:

```bash
bash scripts/bootstrap_environment.sh
bash scripts/bootstrap_analysis.sh
bash scripts/project.sh -m src.pipelines.check_environment
bash scripts/project.sh scripts/run_tests.py --integration-required
```

O bootstrap prepara Python e Java isolados, sem substituir o Python do sistema.
Dependências estão fixadas em requirements.lock. A prova usa somente dois casos
sintéticos descartáveis para testar o runtime; a ABT e as análises usam Home Credit por publicações aprovadas. As dependências
de gráficos são isoladas em .runtime/analysis com requirements.analysis.lock.

## Adquirir os dados reais

Usar a conta inscrita na competição:

```bash
bash scripts/project.sh -m kaggle auth login --no-launch-browser
bash scripts/project.sh -m kaggle competitions files home-credit-credit-risk-model-stability --page-size 200
bash scripts/project.sh -m src.pipelines.download_home_credit --plan
bash scripts/project.sh -m src.pipelines.download_home_credit
```

São selecionados seis arquivos, sem baixar a competição inteira ou apagar dados
existentes. Depois da aquisição, confirmar esquemas/chaves/período, fechar os
contratos e construir o recorte antes de ampliar o processamento. Os detalhes
estão no documento de ambiente.

Para repetir a inspeção exata, sem modificar a RAW:

```bash
bash scripts/project.sh -m src.profiling.inspect_home_credit
```

Dados e credenciais ficam fora do Git. Reprodução histórica e qualidade já foram
demonstradas até Gold no filesystem; arquitetura com objetos permanece no roteiro.

## Materializar ou verificar o recorte

```bash
bash scripts/project.sh -m src.pipelines.build_sample
```

O comando valida a edição da origem, aplica os contratos, seleciona casos por
hash e preserva seus relacionados. Publica um snapshot separado com manifesto;
reexecuções consistentes reutilizam a saída. A atribuição dos três lotes é
simulada. A RAW original permanece em seu caminho de origem.

## Ingerir o recorte na Bronze

```bash
bash scripts/project.sh -m src.pipelines.run_bronze_mvp --sample 7d58bbdaa00cbabfbce54d26
```

Use o identificador retornado pelo construtor se houver outra seleção. A saída
fica em `data/bronze/samples/<selection_id>/`; relatórios ficam em `artifacts/bronze/`.
O marcador `_READY.json` só é gravado após as verificações. O modo explícito
`--raw` tem outro namespace e não é necessário para este fluxo.

## Executar e aceitar a Silver inicial

```bash
bash scripts/project.sh -m src.pipelines.run_silver_initial \
  --sample 7d58bbdaa00cbabfbce54d26
```

O comando confere a Bronze aprovada, trata datas com guarda de perda, cria ou
reutiliza o pacote Delta e valida seus contratos. O padrão `--existing reuse`
revalida sem overwrite; `--existing error` recusa um pacote já existente.
O JSON final informa relatório, recibo de aceite, identidade e reutilização.

Relatórios ficam em `artifacts/silver_runs/<run_id>.json`; recibos ficam em
`data/silver/samples/<selection_id>/acceptances/<run_id>.json`. Uma falha retorna
código não zero e preserva os pacotes e aceites anteriores. O manifesto técnico
permanece imutável; o recibo aprova apenas o estado inicial da Silver.

## Executar a demonstração incremental

```bash
bash scripts/project.sh -m src.pipelines.run_incremental_demo \
  --sample 7d58bbdaa00cbabfbce54d26
```

O comando gera ou verifica os pacotes Parquet, aplica os lotes em estado Delta
próprio, testa reenvios/atraso e reconcilia com a reconstrução integral.
Relatórios ficam em `artifacts/f04/runs/`. O estado F04 começa vazio e preserva
a Silver inicial; os recibos por lote ainda não são uma publicação global Gold.
Medições, limitações e execução com o wrapper de recursos estão na evidência.

## Publicar Silver gerenciada e Gold

Com os relatórios de entrada aprovados disponíveis:

```bash
bash scripts/project.sh -m src.pipelines.run_publication_demo \
  --sample 7d58bbdaa00cbabfbce54d26 \
  --f04-report artifacts/f04/runs/20261113T020347Z_1609747b.json
bash scripts/project.sh -m src.pipelines.run_gold_demo \
  --sample 7d58bbdaa00cbabfbce54d26 \
  --f05-report artifacts/f05/runs/20261113T033217Z_04372370.json
```

Esses comandos verificam as entradas, publicam os três cenários e exercitam
falha/retomada e histórico. Se outra execução F05 for usada, forneça seu relatório
explícito à F06. Para consumir ABT/indicadores com versões coerentes, siga
[Gold por publicação](docs/gold/ABT_E_INDICADORES.md).

## Gerar o relatório analítico

```bash
bash scripts/analysis.sh -m src.pipelines.run_analysis \
  --sample 7d58bbdaa00cbabfbce54d26 \
  --publication 6f4406dd0180850e23d5283e \
  --baseline c711e23bdd5145ae78537a61 \
  --corrected e709bcefce9adab4b7d60562
```

O comando lê os três manifestos explícitos e produz um bundle por tentativa,
com HTML offline, tabelas CSV, gráficos PNG/SVG e metadata. Não transforma a Gold
ou troca CURRENT. Caminhos, aceite, reprodução e limites estão na
[execução analítica](docs/analise/EXECUCAO.md). O
[relatório já executado](docs/analise/RESULTADOS.md) está disponível localmente.

## Escopo e limites

O projeto representa um laboratório de portfólio. Modelo preditivo, feature store,
retreinamento e migração AWS ficam para entregas posteriores. Chegada incremental,
correções e falhas artificiais serão explicitamente identificadas como simulações.
Não há resultados financeiros ou operação de produção alegados.

O código está sob [licença MIT](LICENSE). Os dados Home Credit seguem as condições
próprias registradas na documentação da fonte. A inscrição informada pelo usuário
mantém a fonte no desenvolvimento; o alcance da divulgação externa será revisado
antes da publicação dos dados ou derivados.

Frederico Costa
