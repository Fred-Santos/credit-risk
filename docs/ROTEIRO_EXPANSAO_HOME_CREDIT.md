# Roteiro de expansão — Home Credit e preparação para ML

Data: 18/11/2026. Estado: planejado; implementação e medições pendentes.

Este roteiro organiza a evolução do MVP de três tabelas e 50 mil casos para
integração de todas as tabelas de treino da competição Home Credit — Credit Risk
Model Stability. Preserva as evidências da entrega anterior e não declara a
nova capacidade ou os novos produtos como validados.

## 1. Decisões de organização

| Tema | Decisão para a expansão |
|---|---|
| Fontes | Todas as tabelas lógicas de treino, incluindo todos os seus shards; preferir Parquet, sem duplicar a mesma fonte em CSV |
| Teste oficial Kaggle | Inventariar separadamente; não misturar com a reserva temporal derivada do treino rotulado |
| População | Todos os casos elegíveis nas janelas abaixo; retirar o teto de 50 mil apenas no novo fluxo |
| RAW | Preservar arquivos completos e imutáveis, hashes, dicionário e proveniência; reutilizar aquisições íntegras |
| Desenvolvimento ML | Casos com `date_decision` de 01/01/2020 a 31/05/2020, inclusive |
| Avaliação temporal ML | Casos com `date_decision` de 01/06/2020 a 30/09/2020, inclusive |
| Análise de público | Casos com `date_decision` de 01/01/2020 a 30/09/2020, inclusive |
| Históricos auxiliares | Selecionar pelos casos elegíveis; preservar históricos anteriores a janeiro quando necessários |
| ABTs | Duas populações com o mesmo contrato de atributos: desenvolvimento e avaliação temporal |
| Atributos | Integrar todas as tabelas na RAW/Silver; justificar contribuição, agregação ou exclusão de campos na Gold |
| ML | Preparar dados e regras de avaliação; treinamento e escolha de modelo permanecem fora desta etapa |

O fim de maio foi organizado como **31/05**, incorporando o comentário sobre a
lacuna de um dia na proposta original. Implementar os filtros como intervalos
semiabertos: desenvolvimento `[2020-01-01, 2020-06-01)`, avaliação
`[2020-06-01, 2020-10-01)` e público `[2020-01-01, 2020-10-01)`.

As datas selecionam casos pela decisão; não representam a data de ingestão nem
uma janela obrigatória para todas as datas existentes nos históricos.

## 2. Recursos e capacidade

O computador dispõe de **32 GB de RAM**, conforme informado pelo responsável.
Adotar **8 GB de heap do driver Spark** como ponto inicial do novo perfil local.
Esse parâmetro não reserva nem limita toda a memória do ambiente: JVM fora do
heap, Python, workers, SeaweedFS e sistema operacional também consomem RAM.

A inspeção inicial do Linux/WSL encontrou aproximadamente **15 GiB visíveis**
(`artifacts/expansion/host_capacity.json`), abaixo dos 32 GB físicos informados.
Respeitar o limite efetivo da VM; 12/16 GB de heap dependem de revisar esse limite
e comprovar folga. Não alterar a configuração do WSL automaticamente.

Começar com `local[2]`; ajustar partições a partir de bytes, duração, spill e
distribuição das tarefas. Não aumentar concorrência junto com memória sem medir
o efeito de cada ajuste. Manter `maxResultSize` conservador e evitar trazer
tabelas ou históricos completos ao driver. Rever agregações com listas grandes
por caso e estruturas Python que cresçam proporcionalmente à base.

Se 8 GB forem insuficientes, investigar primeiro skew, planos, joins, partições,
spill e coleta no driver. Está autorizada a avaliação de aumentos para 12 GB e,
se necessário, 16 GB de heap, um passo por vez, condicionada à folga observada
no host. Esses valores são candidatos, não garantia de segurança. Registrar
consumo total, memória disponível, swap e serviços concorrentes; reduzir ou
interromper o job diante de pressão sustentada ou risco de OOM do host.

Medir também disco livre e picos de temporários, shuffle, cópias de publicação e
histórico Delta. O tamanho comprimido dos Parquets não estima sozinho RAM ou
disco necessários. Aumentar memória não substitui corrigir um plano inadequado.

## 3. Regras para preparação de ML

A ABT atual é retrospectiva e admite observações sem disponibilidade comprovada
na decisão. Ela não deve ser renomeada como base pronta para ML. A nova versão
deve classificar cada atributo por origem, significado, data do evento e evidência
de disponibilidade no momento da decisão. Data do evento anterior à decisão,
isoladamente, não comprova disponibilidade.

Campos sem evidência suficiente ficam excluídos dos atributos elegíveis para ML
ou explicitamente pendentes, podendo permanecer no produto retrospectivo.
`target`, identificadores técnicos e informações posteriores ao desfecho não
entram automaticamente no conjunto de preditores. Verificar também definição,
janela de observação e maturação do rótulo antes de aprovar a avaliação temporal.

A reserva de junho a setembro deve ser gerada com o mesmo contrato e isolada
por manifesto. Seus rótulos não devem orientar seleção de atributos, imputação,
normalização, codificação, ajuste de hiperparâmetros ou escolha de modelo.
Esses ajustes deverão ser aprendidos apenas no desenvolvimento, com validação
temporal interna a ser definida na etapa de modelagem.

A análise de público pode descrever janeiro a setembro. Registrar que escolhas
de modelagem orientadas pelos resultados da reserva comprometem sua independência;
se isso ocorrer, será necessário redefinir o protocolo e a avaliação final.
Separar descritivos de público dos artefatos de ajuste do modelo.

## 4. Fases e critérios de aceite

Marcar `[x]` apenas com evidência reproduzível. Cada fase depende da anterior,
salvo tarefas documentais independentes. Não misturar resultados do MVP com os
novos produtos; usar novos contratos, IDs de população e namespaces.

### E00 — Inventário e desenho das populações · peso médio

- [x] E00.1 Inventariar tabelas lógicas, shards, formatos, bytes e dicionário disponíveis; distinguir treino e teste oficial.
- [x] E00.2 Perfilar schemas, grãos, chaves, níveis de histórico, cobertura, datas e contagens exatas por tabela.
- [x] E00.3 Contar casos e distribuição mensal de rótulos nas três populações, sem amostragem de aprovação.
- [x] E00.4 Registrar dependências, estimativa inicial de armazenamento e ambiguidades semânticas por fonte.

Aceite: inventário cobre todas as tabelas de treino; calendário sem lacunas
acidentais; contagens conhecidas; lista explícita de pendências. Reestimar esforço
e capacidade neste ponto, sem inferir volume pelos três arquivos lógicos atuais.

### E01 — Perfil de execução e medição · peso médio

- [x] E01.1 Criar perfil Spark de expansão com driver de 8 GB e configuração registrada por execução, preservando reprodução do perfil anterior.
- [x] E01.2 Verificar aplicação da memória na inicialização da JVM, versões e leitura/escrita Delta/S3.
- [x] E01.3 Medir leitura e agregação representativas, incluindo a maior tabela e casos com históricos extensos.
- [x] E01.4 Registrar memória, duração, spill, disco, arquivos e decisão sobre partições, concorrência e eventual aumento de heap.

Aceite: execução medida com folga do host documentada; plano de armazenamento
inclui temporários e versões. Uma prova parcial não aprova o fluxo completo.

### E02 — Aquisição completa e seleção temporal · peso médio/alto

- [x] E02.1 Substituir a lista fixa de arquivos por catálogo versionado de todas as fontes de treino.
- [x] E02.2 Baixar somente ausentes ou inválidos; conferir hashes, integridade, completude de shards e retomada.
- [x] E02.3 Implementar política temporal versionada, sem teto de casos, e semi-joins das auxiliares pelos casos de janeiro a setembro.
- [x] E02.4 Materializar Bronze com proveniência, reconciliando linhas e valores contra RAW e política; registrar casos fora das janelas.

Aceite: nenhuma fonte lógica omitida, RAW anterior preservada, seleção exata e
reexecução idempotente. Nenhum filtro genérico descarta históricos anteriores a janeiro.

### E03 — Contratos e Silver extensível · peso alto

- [x] E03.1 Definir contratos por tabela: tipos, chaves, nulos, domínios, relacionamentos e política de datas.
- [x] E03.2 Generalizar mapeamentos e leitura para o catálogo; tratar diferenças de schema entre shards explicitamente.
- [x] E03.3 Implementar transformações e qualidade de cada fonte, com rejeições rastreáveis e reconciliação.
- [x] E03.4 Generalizar casos afetados por mudanças auxiliares, revisões, replay e dependências das publicações.

Aceite: todas as tabelas integradas e reconciliadas; chaves em níveis históricos
validadas sem supor que todo histórico usa apenas `case_id/num_group1`. Incremento
permanece simulação declarada, sem alegar CDC fornecido pela competição.

### E04 — Atributos e validade temporal · peso alto

- [x] E04.1 Criar catálogo de atributos com fórmula, fonte, agregação, unidade, ausência e regra temporal.
- [x] E04.2 Classificar elegibilidade para ML e investigar disponibilidade temporal e maturação de rótulos.
- [x] E04.3 Agregar cada relação antes do join no grão do caso; tratar níveis aninhados sem multiplicar observações.
- [x] E04.4 Definir contrato comum das duas ABTs e separar atributos retrospectivos daqueles elegíveis para ML.

Aceite: nenhum atributo de ML sem justificativa temporal; exclusões documentadas;
uma linha por caso. Pendências de disponibilidade impedem declarar prontidão
para ML dos campos afetados, mas não impedem a entrega retrospectiva identificada.

### E05 — Gold e reserva temporal · peso alto

- [x] E05.1 Gerar ABT de desenvolvimento para janeiro–maio e ABT de avaliação para junho–setembro com o mesmo schema.
- [x] E05.2 Garantir interseção vazia de `case_id`, limites exatos de datas e preservação da população elegível.
- [x] E05.3 Publicar manifestos com versões de fontes/contratos, limites, contagens, rótulos e lista de atributos elegíveis.
- [x] E05.4 Separar rótulos da reserva dos insumos de ajuste; registrar política para futuros preprocessadores e validação interna.

Aceite: produtos reproduzíveis, sem joins que expandam casos, sem ajuste de
transformações usando a reserva e com reconciliação independente. A separação
é por caso; verificar possibilidade de clientes repetidos e documentar limitações
se não houver identidade de cliente confiável. Não alegar independência por pessoa.

### E06 — Análise de público · peso médio

- [x] E06.1 Definir perguntas, dimensões, denominadores, cobertura e significado dos indicadores disponíveis.
- [x] E06.2 Produzir análise de janeiro–setembro a partir da população completa da janela, sem depender só da ABT de desenvolvimento.
- [x] E06.3 Apresentar evolução mensal, ausências, composição e comparações descritivas entre os períodos.
- [x] E06.4 Registrar limitações, maturação de rótulos e uso das análises; não interpretar retrospectiva como taxa operacional atual.

Aceite: nove meses tratados explicitamente, inclusive eventuais lacunas de dados;
indicadores reconciliados por SQL independente e conclusões com denominadores.

### E07 — Publicação, recuperação e capacidade completa · peso alto

- [x] E07.1 Generalizar manifestos, dependências, lineage, retenção e aprovação para o novo conjunto Silver/Gold.
- [x] E07.2 Preservar ativação de CURRENT somente após aprovação de todas as saídas exigidas; identificar publicações por versão do escopo.
- [x] E07.3 Validar falha antes/depois da ativação, retomada, correção auxiliar, replay e leitura independente.
- [x] E07.4 Executar fluxo completo real e medir pico de recursos, duração, bytes e crescimento de versões; reavaliar perfil.

Aceite: publicação consistente, recuperação demonstrada, MVP anterior preservado
e capacidade comprovada para o novo volume. Não extrapolar o desempenho para cluster.

### E08 — Testes, documentação e encerramento · peso médio/alto

- [x] E08.1 Ampliar fixtures sintéticas com formatos de relações identificados no inventário, limites de datas e casos sem auxiliares.
- [x] E08.2 Testar vazamento temporal, contratos equivalentes entre ABTs, disjunção dos casos e reconciliação de atributos.
- [x] E08.3 Executar regressões pertinentes, integração e e2e sintético sem credenciais; registrar nova matriz e resultados reais.
- [x] E08.4 Atualizar README, arquitetura, contratos, operação e guia de estudo; distinguir entrega retrospectiva, preparação ML e pendências.

Aceite: comandos reproduzíveis, evidências novas sem sobrescrever as antigas,
testes obrigatórios aprovados e sem declarar os 153 testes históricos como
validação automática da expansão. Nenhum treinamento de modelo é necessário.

## 5. Controle de progresso

| Fase | Estado | Evidência | Próximo passo |
|---|---|---|---|
| E00 | Concluída: 4/4 | [Inventário](evidencias/E00_INVENTARIO_EXPANSAO.md) / [Perfil completo](evidencias/E00_PERFIL_FONTES.md) | E01: perfil de 8 GB e medição |
| E01 | Concluída: 4/4 | [Perfil 8 GiB](evidencias/E01_PERFIL_EXECUCAO.md) | E02: seleção temporal e Bronze |
| E02 | Concluída: 4/4 | [Aquisição](evidencias/E02_AQUISICAO_EXPANSAO.md) / [Bronze temporal](evidencias/E02_BRONZE_TEMPORAL.md) | E03: contratos Silver por tabela |
| E03 | Concluída: 4/4 | [Silver e revisões](evidencias/E03_SILVER_EXPANSAO.md) | 17 Delta aprovadas; simulação isolada |
| E04 | Concluída: 4/4; aprovação ML não comprovada | [Atributos e tempo](evidencias/E04_ATRIBUTOS_E_TEMPO.md) | 166 atributos retrospectivos; zero aprovados PIT |
| E05 | Concluída: 4/4 | [ABTs temporais](evidencias/E05_ABTS_TEMPORAIS.md) | 259.695 / 187.610 casos; labels separadas |
| E06 | Concluída: 4/4 | [Público de nove meses](evidencias/E06_PUBLICO_EXPANSAO.md) | 447.305 casos, cinco tabelas e gráficos |
| E07 | Concluída: 4/4 | [Publicação e recuperação](evidencias/E07_PUBLICACAO_EXPANSAO.md) | 42 Delta no S3; CURRENT original; histórico simulado retido |
| E08 | Concluída: 4/4 | [Aceitação da expansão](evidencias/E08_ACEITACAO_EXPANSAO.md) | 174 testes sem ignorados; T01–T24 e X01–X17 aprovados |

São **36 itens planejados e concluídos**. A contagem representa cobertura, não percentual de
esforço. O maior trabalho está em E03–E05 e na adaptação do protocolo em E07.
E00–E08 encerradas no escopo retrospectivo. E06/E07 executadas em dados reais; S3 da expansão ativo por CURRENT e recuperação aprovada. Disponibilidade histórica para ML e maturação do target continuam não comprovadas. Este roteiro não define E09 nem autoriza treinamento de modelo como consequência do encerramento.

Referências: [roteiro do MVP](ROTEIRO_EXECUCAO_LAKEHOUSE.md),
[contrato ABT atual](contratos/ABT.md), [ambiente local](AMBIENTE_LOCAL.md) e
[fonte adquirida](evidencias/F00_F02_FONTE_REAL.md).
