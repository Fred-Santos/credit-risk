# 1 — Produto de dados e arquitetura

[Percurso completo](../GUIA_ESTUDO_LAKEHOUSE.md) · Próximo: [Dados e SQL](02_DADOS_E_SQL.md)

Objetivo: explicar o produto que queremos entregar e relacionar a arquitetura
com as necessidades de engenharia e análise. Este é o início do percurso.

## O problema que orienta a construção

Um analista quer estudar casos de crédito: quantos existem por período, qual a
proporção de um desfecho e qual a cobertura das informações auxiliares. Se uma
informação for corrigida, ele precisa explicar por que o indicador mudou e
conseguir consultar o resultado anterior.

Isso exige mais do que executar uma consulta. Precisamos conhecer a população,
interpretar os campos, preparar os dados, verificar a transformação e identificar
qual estado foi consultado. Um **produto de dados** reúne uma saída útil, seu
significado e condições de uso. Uma **pipeline** é a sequência de processamento
que ajuda a produzi-lo.

Neste projeto, o produto terá três partes: uma tabela por caso chamada ABT,
indicadores calculados sobre essa base e uma análise que interpreta os resultados.
A existência de código de ingestão ainda não equivale à entrega dessas partes.

## Lake, Warehouse e Lakehouse

Um **Data Warehouse** organiza dados integrados para análise, frequentemente
com tabelas modeladas para consumo. Um **Data Lake** armazena dados em arquivos
e outros formatos, com organização e governança definidas pela solução.
Um **Lakehouse** combina esse armazenamento com mecanismos de gestão de tabelas,
como transações e versões, para sustentar processamento e consumo confiáveis.

As arquiteturas podem compartilhar características. Incremento, qualidade e
histórico também podem existir em um Warehouse. Aqui, demonstraremos as
garantias concretas de Spark, Delta e do protocolo de execução local.

## Separar responsabilidades na arquitetura

| Camada | Responsabilidade neste projeto | Exemplo |
|---|---|---|
| RAW | Preservar a entrada adquirida | Arquivos Home Credit recebidos |
| Bronze | Registrar ingestão e origem, preservando valores | Coluna `_source_file` e manifestos |
| Silver | Aplicar tratamentos aprovados e validar tabelas | Datas convertidas e tabelas Delta |
| Gold | Preparar dados para consumo analítico | ABT por caso e indicadores publicados em F06 |

Esses nomes são uma convenção. A separação ajuda a investigar falhas: se um
valor Silver estiver errado, podemos voltar à Bronze e à RAW e localizar a
etapa responsável. Persistir todas as etapas também tem custo de disco e
manutenção; o recorte e a política de retenção fazem parte dessa escolha.

## Ferramentas dentro do processo

Python organiza os programas. Spark processa as tabelas. Parquet guarda dados
tabulares em arquivos. Delta registra os estados das tabelas Silver. YAML
guarda configurações e contratos. Git registra mudanças de código. SeaweedFS
atende a API S3 local; Hadoop S3A conecta Spark aos objetos. Cada papel
será estudado com sua implementação nos capítulos seguintes.

Uma configuração de pastas chamada Bronze/Silver/Gold, isoladamente, não prova
transações, reprodução ou correção dos indicadores. Essas propriedades precisam
de implementação e evidência.

## Leitura guiada do projeto

Abra [ESCOPO_PRODUTO.md](../ESCOPO_PRODUTO.md), seção “Perguntas e evidências
necessárias”. Acompanhe P01, P03 e P05: volume, cobertura e reprodução histórica.
Observe que cada pergunta exige campos ou artefatos diferentes.

Depois, abra [DECISOES.md](../DECISOES.md) e leia D01–D07. Relacione o foco
analítico, o uso de Spark/Delta, as simulações declaradas e o adiamento de ML/AWS.
Essas escolhas delimitam o laboratório que está sendo construído.

## O que já foi executado e o que será entregue

F00 definiu o produto; F01 preparou o ambiente; F02 validou ingestão e Bronze;
F03 concluiu a Silver inicial e F04 validou o incremento com correções simuladas
e reconstrução equivalente. F05 acrescentou migração, publicação e recuperação;
F06 entrega ABT e indicadores; F07 entrega análise, gráficos e reprodução do
relatório. F08 validou replay e publicações Delta em objetos locais com
reconciliação, falha/retry e reinício. F09 consolidou a operação; F10 aprovou testes em ambiente novo e declarou CI
com dados inventados. F11 preparou a entrega local com demo sintética e autorrevisão. O uso de dados de uma competição
limita as conclusões sobre uma carteira operacional real.

Evidência: [abertura do escopo](../evidencias/F00_ABERTURA.md) e
[estado inicial F03.6](../evidencias/F03_EXECUCAO_SILVER.md) e
[incremento F04](../evidencias/F04_INCREMENTAL.md),
[publicação F05](../evidencias/F05_PUBLICACAO.md) e
[Gold F06](../evidencias/F06_GOLD.md) e
[análise F07](../analise/RESULTADOS.md) e
[objetos F08](../evidencias/F08_OBJETOS.md).

## Atividade e conferência

Para a pergunta “Uma correção mudou a proporção de `target=1`?”, descreva a
saída analítica e os registros de engenharia necessários.

**Conferência:** precisamos comparar o mesmo recorte em dois estados identificados,
com numerador/denominador explícitos, e rastrear lote, revisão e chaves alteradas.
Sem fixar a população e as versões, uma diferença pode vir de outra causa.

Ao seguir, leve esta pergunta: o que exatamente uma linha de cada tabela representa?

Próximo: [2 — Dados, relacionamentos e SQL](02_DADOS_E_SQL.md).
