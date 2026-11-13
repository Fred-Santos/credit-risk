# 11 — Operação, observabilidade, publicação e armazenamento

[Percurso](../GUIA_ESTUDO_LAKEHOUSE.md) · Anterior: [Gold e análise](10_GOLD_E_ANALISE.md)

Objetivo: entender como executar, acompanhar, recuperar e disponibilizar uma
pipeline com várias saídas. Pré-requisito: commits, versões e dependências.

Estado: comandos locais, locks, relatórios, lineage, aceite inicial, incremento
e publicações históricas Silver/Gold existem até F06. Objetos e operação
consolidada permanecem em F08/F09.

## Orquestração é controlar dependências e estados

Uma pipeline só pode iniciar uma etapa quando suas dependências estão prontas.
**Orquestração** coordena essa ordem, parâmetros, resultados e erros. Ela pode
começar com um programa Python; um serviço dedicado depende de necessidade
operacional e não é requisito já implementado aqui.

O comando Silver reúne leitura, transformação, persistência e contratos. O
futuro comando completo coordenará RAW → Bronze → Silver → Gold → publicação.
Modos de atualização normal, replay e reconstrução precisam ter efeitos claros.
Um retry deve ser apropriado à causa; repetir indefinidamente uma regra de
schema reprovada não corrige o problema.

## O que observar durante uma execução

| Artefato | Pergunta respondida | Exemplo local |
|---|---|---|
| Log | O que aconteceu e onde falhou? | Mensagem de exceção e etapa |
| Métrica | Quanto foi processado e quanto custou? | Linhas, bytes e duração |
| Relatório de qualidade | Quais regras passaram ou falharam? | Checks e diagnósticos |
| Lineage | De onde vieram as saídas? | Entrada, execução e hashes |
| Recibo/manifesto | Qual conjunto foi aceito? | Paths, versões, UUIDs e relatório |

Medir uma etapa também custa recursos. A duração do core Silver registrada em
F03.6 exclui criação e encerramento de Spark; não deve ser rotulada como duração
total do processo. Métricas antigas em `docs/observability/metrics/` também não
certificam uma execução atual diferente.

## Por que precisamos de uma publicação entre tabelas

Imagine que Silver e Gold já tenham uma publicação aprovada. Uma tentativa nova
atualiza uma tabela, mas falha antes de concluir outra. Ler o estado mais recente
de cada pasta pode misturar saídas de tentativas diferentes.

F05 implementou um **manifesto de publicação** com versões aprovadas de
todas as saídas necessárias. O consumidor usa esse conjunto identificado.
O ponteiro da publicação só avança depois dos checks; falha preserva o conjunto
anterior. F06 acrescentou as versões Gold a esse controle.

O recibo inicial de F03.6 aceita um pacote Silver imutável por execução. F04
acrescenta recibos por lote em outro estado de trabalho mutável, com versões
registradas e reconstrução equivalente. F05 faz cópias gerenciadas e migração
v2; F06 publica um manifesto com três Silver e duas Gold. Os arquivos de cada
publicação aprovada permanecem imutáveis. `_CURRENT.json` seleciona o conjunto
ativo e é substituído atomicamente no filesystem após o manifesto completo.

Em [protocol.py](../../src/publication/protocol.py), siga `publish_snapshot`,
`PublicationTransaction.publish` e `_activate`. O lock admite um escritor local
cooperante. `open_publication` confere manifesto, blobs de código/configuração,
arquivos, UUIDs, schemas e versões; as ações Spark devem ficar dentro do contexto.
Manifesto não transforma vários commits Delta em uma transação global: oferece
visibilidade coerente para consumidores que seguem esse protocolo.

## Evolução, recuperação e retenção

**Evolução de schema** é uma mudança controlada do contrato da tabela. Uma nova
coluna autorizada e uma mudança incompatível de tipo precisam de tratamentos
diferentes. Aceitar tudo automaticamente remove a proteção do contrato.

**Recuperação** deve reconhecer o que já foi persistido após falha e retomar
sem duplicar ou expor resultado parcial. **Retenção** define quais arquivos e
logs preservar para reproduzir estados anteriores. Saber a versão Delta não
basta se os arquivos exigidos por ela já foram removidos.

F05 testou falhas antes/depois de commit, entre tabelas, evolução e leitura
histórica. Um intento identifica quais commits privados pertencem à tentativa;
o retry reaproveita esses commits e completa o que falta. Diretório desconhecido
não é sobrescrito. F06 repetiu a prova após MERGE Gold, antes dos indicadores.

Retenção Delta é configurada em 30 dias, mas publicações e entradas ficam fixadas
sem prazo de descarte. Não executamos VACUUM nos dados reais. Em uma fixture
internamente criada, VACUUM 0 removeu dados antigos e tornou a versão histórica
ilegível, preservando o estado atual. O teste ensina por que guardar somente
o número da versão não garante reprodução. Não houve simulação de 30 dias passados.

## Filesystem e armazenamento de objetos

Hoje usamos caminhos locais e operações de filesystem. Staging, rename, hard
link e locks locais dependem dessas garantias. Armazenamento de objetos oferece
operações por objetos/chaves e requer conector e protocolo adequados.

Uma API compatível com S3 não prova, sozinha, que a pipeline manterá as mesmas
garantias. F08 selecionará a implementação local e repetirá gravação Delta,
retry, indisponibilidade, persistência e reconciliação no destino. Credenciais,
endpoint e retenção precisam ser configurados e documentados. AWS permanece
fora do escopo desta entrega.

## Leitura guiada e evidência

Em [run_silver_initial.py](../../src/pipelines/run_silver_initial.py), acompanhe
as mudanças de `stage` e a gravação do relatório de falha. Em
[acceptance.py](../../src/silver/acceptance.py), veja a conferência final e
`_write_once`, que publica arquivos completos sem substituir aceites anteriores.

Em [run_bronze_mvp.py](../../src/pipelines/run_bronze_mvp.py), identifique as
chamadas de métricas, lineage e inventário. Compare seus papéis; um arquivo
de lineage não substitui o relatório de qualidade.

A [evidência F03.6](../evidencias/F03_EXECUCAO_SILVER.md) registra falhas e
preservação dos aceites; a [F04](../evidencias/F04_INCREMENTAL.md) mede o fluxo
incremental e prova conservação/reconstrução. As evidências
[F05](../evidencias/F05_PUBLICACAO.md) e [F06](../evidencias/F06_GOLD.md) registram
publicações e recuperação. O [roteiro](../ROTEIRO_EXECUCAO_LAKEHOUSE.md) define
os cenários ainda necessários em F08/F09.

## Atividade e conferência

Uma publicação usa Silver versão 2 e Gold versão 5. A próxima tentativa grava
Silver versão 3 e falha antes da nova Gold. Qual conjunto o consumidor deve usar?

**Conferência:** o conjunto aprovado anterior, 2/5, até uma nova publicação
completa ser validada. Esses números são versões por tabela e não precisam
ser iguais entre si. O ponteiro e os arquivos necessários precisam ser preservados.

Próximo: [12 — Testes, CI e entrega](12_TESTES_E_ENTREGA.md).
