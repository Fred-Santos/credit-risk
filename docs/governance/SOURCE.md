# Fonte de dados — avaliação de adequação ao portfólio

Atualizado em 12/11/2026. Home Credit mantida para o desenvolvimento com dados
reais. O usuário informou inscrição na competição e autorizou a continuidade.
Acesso autenticado pela API confirmado: seis arquivos reais adquiridos e
inspecionados em 12/11/2026. Revisão da apresentação externa permanece separada,
antes da publicação. Evidência: [fonte real](../evidencias/F00_F02_FONTE_REAL.md).

## 1. Identificação da fonte existente

| Item | Registro |
|---|---|
| Nome | Home Credit — Credit Risk Model Stability |
| Publicador da competição | Home Credit |
| Plataforma | Kaggle |
| Identificador no código | `home-credit-credit-risk-model-stability` |
| Aquisição implementada | CLI Kaggle em [ingest_raw.py](../../src/pipelines/ingest_raw.py) |
| Dados atuais no checkout | Seis arquivos reais, 375.444.428 bytes, com journal e checksums |
| Evidências históricas | Dicionários e relatórios de fevereiro de 2026 |
| Período atual confirmado na base | 2019-01-01 a 2020-10-05 |

A aquisição atual seleciona cinco Parquets de treino e o CSV de definições;
preserva os originais selecionados sem apagar outros dados. O comportamento
antigo de baixar tudo e remover formatos/teste foi substituído. A licença MIT
do repositório refere-se ao código, sem estender permissão aos dados de terceiros.

## 2. Verificação das condições de uso

A página oficial de [regras](https://www.kaggle.com/c/home-credit-credit-risk-model-stability/rules)
identifica o acesso como **“Competition Use Only”**. A seção 7.A limita o uso à
participação e aos fóruns Kaggle; a seção 7.B restringe disponibilização dos dados
a não participantes. A consulta recuperou essas seções pelo índice de busca da
página oficial; a abertura direta não apresentou texto legível.

Inscrição informada pelo usuário sustenta o uso nos termos da competição.
O registro anterior que impedia qualquer novo processamento foi abrangente
demais e foi corrigido. Continuar o desenvolvimento com Home Credit; revisar
o alcance da divulgação externa antes de publicar dados ou derivados.

Não inferir autorização de posts, repositórios de terceiros ou regras de outra
competição Home Credit. Esta é uma decisão de adequação ao escopo, não uma
afirmação de que o uso anterior do usuário foi irregular.

## 3. Evidência e limites da consulta

| Verificação | Resultado | Localizador |
|---|---|---|
| Competição correta | Confirmada pelo identificador e regras | Página oficial e código local |
| Regra de acesso/uso | Restrição identificada | Termos específicos e seção 7.A |
| Disponibilização de dados | Restrição identificada | Seção 7.B |
| Autorização específica do usuário | Não examinada/não apresentada | Poderá alterar a decisão se cobrir o projeto |
| Inscrição na competição | Informada pelo usuário; acesso autenticado confirmado | API listou os arquivos e permitiu aquisição seletiva |
| Dados atuais, chaves e qualidade inicial | Inspeção exata aprovada nas três tabelas lógicas selecionadas | Relatório de 12/11/2026; não equivale a todos os contratos Silver/Gold |

Consultas reproduzíveis em mecanismo de busca:

```text
site:kaggle.com/c/home-credit-credit-risk-model-stability/rules "Data Access and Use" "only for participating"
site:kaggle.com/c/home-credit-credit-risk-model-stability/rules "Data Security"
```

Não foi salvo o texto integral das regras no repositório. O registro contém
localizadores e uma síntese; novas condições ou autorização específica exigem
revisão da decisão com data e evidência.

## 4. Alternativa avaliada, não adotada

O [Default of Credit Card Clients — UCI](https://archive.ics.uci.edu/dataset/350/default%2Bof%2Bcredit%2Bcard%2Bclients)
informa 30 mil observações, 23 atributos explicativos, arquivo XLS e licença
CC BY 4.0. Contém desfecho e históricos mensais de abril a setembro de 2005.
DOI: [10.24432/C55S3H](https://doi.org/10.24432/C55S3H). Registrar atribuição e
alterações ao adotá-lo.

Limitações para nosso desenho: unidade de análise de cliente no snapshot, sem
equivalente confirmado da sequência de decisões Home Credit. Chegada incremental
e correções seriam simulações. Derivar tabela mensal dos campos documentados é
uma transformação da mesma fonte, não integração de sistemas independentes.
Arquivo, códigos, chave e qualidade ainda precisam ser inspecionados.

Não aprovar a troca apenas pela licença. A fonte simplifica volume e acesso,
mas reduz a complexidade multitécnica/multitabela original; Spark atenderia ao
objetivo didático, sem alegar necessidade de escala para esse tamanho.

## 5. Alternativa secundária

[South German Credit — UCI](https://archive.ics.uci.edu/dataset/573/south%2Bgerman%2Bcredit)
também informa CC BY 4.0, mil registros e amostra de créditos reais de 1973–1975,
com sobreamostragem de créditos ruins. É menor e oferece menos material temporal;
não é a primeira recomendação para este escopo. Não foi baixada ou perfilada.

## 6. Comparação e efeito da decisão

| Critério do projeto | Home Credit atual | UCI Default candidata |
|---|---|---|
| Adequação ao portfólio externo | Não demonstrada nas condições consultadas | Candidata a validar |
| Desenho disponível | Múltiplas tabelas e casos por decisão | Snapshot e histórico em colunas |
| Aproveitamento direto do código | Alto para caminhos e contratos atuais | Parcial; adaptar aquisição e contratos |
| Históricos 1:N | Auxiliares existentes | Podem ser derivados; origem única deve ficar explícita |
| Incremento real da origem | Não fornecido pelo desenho atual | Não confirmado; planejar simulação |
| Merge, revisões, histórico e replay | Desenho de engenharia reaproveitável | Desenho de engenharia reaproveitável |

## 7. Próximo passo e aceite

O usuário esclareceu a inscrição e confirmou o uso dos dados reais Home Credit.
UCI não será adotada. O [rascunho de solicitação](SOLICITACAO_AUTORIZACAO.md)
permanece como referência para a revisão da divulgação externa, sem envio e
sem ser pré-requisito geral de preparação e desenvolvimento local.

O [ambiente e a aquisição seletiva](../AMBIENTE_LOCAL.md) estão preparados.
A autenticação funcionou; o inventário retornou 138 arquivos e os seis escolhidos
foram adquiridos. A inspeção confirmou chaves, período e cobertura, conforme a
[evidência atual](../evidencias/F00_F02_FONTE_REAL.md).

F00.2 foi aceita para o desenvolvimento local: fonte, acesso, condições e limite
de divulgação registrados. Isso não declara os dados como abertos nem libera
redistribuição de RAW, ABT individual ou resultados externos sem revisão. Essa
verificação permanece no aceite de publicação F10.6/F11. Os contratos v1 e o
recorte já foram validados, conforme [evidência](../evidencias/F00_CONTRATOS_RECORTE.md).
A Bronze do recorte já foi executada e repetida sem novas gravações; ver
[evidência](../evidencias/F02_BRONZE_RECORTE.md). A próxima entrega define o
contrato de eventos/revisões, antes de alinhar regras e reconciliar valores.

Referências de leitura relacionadas: [descrição dos dados Home Credit](https://www.kaggle.com/c/home-credit-credit-risk-model-stability/data)
e [licença CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
