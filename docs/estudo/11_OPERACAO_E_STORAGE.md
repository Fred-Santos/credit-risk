# 11 — Operação, observabilidade, publicação e armazenamento

[Percurso](../GUIA_ESTUDO_LAKEHOUSE.md) · Anterior: [Gold e análise](10_GOLD_E_ANALISE.md)

Objetivo: entender como executar, acompanhar, recuperar e disponibilizar uma
pipeline com várias saídas. Pré-requisito: commits, versões e dependências.

Estado: comandos locais, locks, relatórios, lineage, aceite inicial, incremento
e publicações históricas Silver/Gold existem até F06. F07 consome a Gold para
análise; F08 validou o mesmo processamento em objetos locais. A operação
unificada e a observabilidade consolidada seguem em F09.

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

## Um comando para atualizar, repetir ou reconstruir

A interface F09.1 validada está em
[run_lakehouse.py](../../src/pipelines/run_lakehouse.py), função `execute`.
Ela valida RAW/recorte/Bronze e landing já aprovados, espelha entradas e coordena
incremento, reconstrução de conferência e publicação Silver + Gold em S3.
A preparação/aquisição dessas entradas continua com os comandos anteriores.

**Atualizar** significa aplicar até um lote escolhido, incluindo seus
predecessores. **Replay** reenvia pacotes ao estado existente: revisões e recibos
impedem duplicar linhas ou commits. **Rebuild** começa outro estado, identificado
pelo run_id, para recalcular sem apagar o anterior. Consultar uma publicação
histórica é uma leitura; reconstruir é uma nova execução com novas tabelas.

O código reúne as ações sob um lock operacional e registra a publicação em
outro registry, preservando CURRENT da demonstração F08. Uma tentativa de
atualizar até um limite anterior aos lotes já consumidos é recusada. Isso evita
apresentar o estado final como se fosse um resultado histórico intermediário.
A [operação do comando](../operacao/COMANDO_UNICO.md) explica parâmetros e limites.
O [supervisor F09.2](../operacao/ESTADOS_E_ERROS.md) registra operação, tentativas
e transições, incluindo falhas de inicialização. Métricas consolidadas e resumo
operacional continuam nas próximas tarefas F09.

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

## Ler métricas sem misturar significados

Na F09.3, um relógio monotônico mede durações; horários UTC identificam quando
algo ocorreu. O primeiro permite somar etapas mesmo se o relógio civil mudar.
O relatório do supervisor inclui iniciar/encerrar Spark e serviço e as esperas
de retry; o relatório do executor detalha o processamento. Não comparar um
tempo total com outro que exclui inicialização como se fossem equivalentes.

Entregas são eventos recebidos, incluindo repetições. Linhas finais são registros
na tabela. No primeiro lote, 206.769 entregas correspondem a 35.045 casos,
35.045 estáticos e 136.679 observações históricas. Ao reenviar o lote, as entregas
continuam existindo, mas inserts e updates devem ser zero. Os contadores
planejados continuam conferidos com os commits reais.

Bytes da publicação incluem arquivos retidos para suas versões anteriores.
Quantidade de objetos também pode incluir marcadores de diretório vazios; eles
não são arquivos Delta. O pico RSS é uma amostra da árvore de processos, não
memória heap ou capacidade garantida do host. Seu escopo precisa acompanhar o valor.

A coleta adicional de inventário tem uma etapa própria. Validações e contagens
já embutidas no incremento/publicação continuam nesses tempos; não chamamos
esse total de tempo puro da transformação. Em falha, linhas rejeitadas desconhecidas
ficam nulas, em vez de inventar zero. Consulte o [dicionário de métricas](../operacao/METRICAS.md)
e siga [metrics.py](../../src/operation/metrics.py): StageClock mede intervalos,
batch_counters reúne resultados e publication_inventory consulta tamanhos S3.

## Seguir o caminho de um número

**Lineage** descreve dependências: de quais entradas e regras uma saída depende.
**Inventário** registra o que existe, seus endereços, schema, grão, identidade e
versão. O inventário F09.4 reúne esses papéis para uma publicação aprovada.

Exemplo: `previous_amount_sum` vem de `credamount_590A` das observações
históricas, somado por case_id em ordem de num_group1. O valor passa à ABT por
join, sem multiplicar casos. `history_row_count` mensal soma as contagens por
caso da ABT. O inventário liga essas colunas às tabelas e versões que foram lidas.

Não confunda identidades: uma operação reúne tentativas; cada tentativa tem seu
run_id. Um replay pode ter outro run_id e reutilizar a mesma publication_id.
O auditor também tem seu próprio audit_run_id. Versão Delta é um commit de uma
tabela; revisão de origem determina precedência de eventos. São mecanismos diferentes.

Abra [lineage.py](../../src/operation/lineage.py): `validate_links` confere a
cadeia de relatórios, `column_lineage` declara as regras e `audit` verifica
manifestos, arquivos e leituras Delta antes de salvar o inventário. O mapa de
colunas é revisado e fixado ao código Gold conhecido, sem inferir regras de um
modelo futuro. A [operação](../operacao/LINEAGE_E_INVENTARIO.md) contém o comando,
o dicionário de IDs e o limite dos consumidores observados.

## Entender o resumo operacional

Uma execução falhou porque sua entrada não existia. Os dados que já haviam
sido aprovados precisam deixar de estar disponíveis? Não: o estado da tentativa
e o estado da publicação respondem a perguntas diferentes. A F09.5 mostra ambos.

O [resumo operacional](../operacao/RESUMO_OPERACIONAL.md) lê os relatórios e o
ponteiro da publicação, sem executar carga. A consulta normal confere metadados;
a opção de verificação completa lê as cinco tabelas com Delta. Qualidade
registrada no manifesto não significa que o SQL foi recalculado nesta consulta.

Se o S3 estiver parado, o cache descreve o que foi observado antes, com horário.
Não comprova CURRENT agora. Um relatório de execução sem estado final também
não comprova processo vivo. Essas distinções evitam apresentar certeza que os
artefatos não sustentam.

Os alertas de tempo e RSS usam operações F09.3 fixadas por hash: inicialmente
2× a duração e 1,5× o RSS observado para o mesmo modo/lote/coorte. São referências
para investigar mudanças, sem alegação de SLA ou comparação entre populações
diferentes. Em [status.py](../../src/operation/status.py), siga load_history,
validate_snapshot e compose. Identifique como uma falha recente pode coexistir
com uma publicação aprovada, e por que um cache não é rotulado como atual.

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

Um filesystem oferece diretórios, arquivos, rename e locks POSIX. Um serviço
S3 recebe requisições HTTP para **objetos**: cada objeto tem uma **chave**, que
identifica seu conteúdo dentro de um **bucket**. O **endpoint** é o endereço do
serviço. Barras nas chaves ajudam a organizar prefixos; não criam diretórios
com as garantias POSIX usadas na publicação F05.

Exemplo deste projeto:

```text
endpoint: http://127.0.0.1:18333
bucket:   credit-risk-local
chave:    lakehouse-v1/publications/7d58bbdaa00cbabfbce54d26/_CURRENT.json
```

O endpoint é local, mesmo usando a API S3. A chave de CURRENT aponta para um
manifesto aprovado; ela não é o caminho de uma tabela Delta. Os arquivos da tabela
ficam em outras chaves, sob `published/<seleção>/<publicação>/`.

### Quem conversa com quem

| Ferramenta | Papel na F08 | Exemplo |
|---|---|---|
| SeaweedFS 4.53 | Servidor persistente que atende a API S3 | Guarda objetos e metadados em disco |
| boto3 | Cliente Python para objetos de controle e espelhos | GET/PUT/listagem de manifestos e hashes |
| Hadoop S3A | Conector usado pelo Spark para ler/gravar tabelas | URI `s3a://credit-risk-local/...` |
| Delta Lake | Protocolo da tabela e suas versões | Parquet e `_delta_log` no bucket |
| S3SingleDriverLogStore | Implementação de acesso ao log Delta para esse destino | Um driver escritor cooperante |

Spark traz Hadoop 3.3.4; o conector hadoop-aws é da mesma versão e usa AWS Java
SDK 1.12.262. Não basta acrescentar o JAR mais recente: classes incompatíveis
podem impedir leitura ou commit. A fábrica S3A é separada da fábrica local já
aprovada. Credenciais e endpoint são configuração de acesso; tipos, chaves e
regras de negócio continuam nos contratos.

### O que foi migrado e o que foi preservado

F08 manteve os dados e publicações anteriores no filesystem como referência.
Espelhou RAW, recorte, Bronze e landing por API, conferindo bytes. Depois leu
os eventos do espelho e executou os sete pacotes em **novas tabelas Delta sobre
S3A**. Portanto, o teste cobre MERGE e reconstrução no destino, além da cópia.

O estado incremental terminou com 50.000 casos, 50.000 linhas estáticas e
215.390 observações históricas. Foi congelado após a reconciliação; dele saíram
três publicações privadas Silver v2 + Gold. Cada conjunto tem cinco tabelas.
A ABT final tem 50.000 linhas, os indicadores têm 22 meses e as quinze saídas
foram comparadas integralmente com os três cenários F06.

O relatório F07 existente continua vinculado aos manifestos locais F06.
Seu CLI atual usa o leitor do filesystem. Para consultar os DataFrames S3,
usamos `open_object_publication`; o consumidor `admin inspect` já foi executado
em processo Spark novo. A análise histórica permanece rastreável à sua origem.

### Acompanhar uma correção concreta

O caso 64 recebeu duas correções simuladas na F04: `annuity_780A` mudou de
2436 para 2437 na estática, e um `credamount_590A` histórico mudou de 6899 para
6900. Na F08, esses mesmos eventos foram lidos do espelho S3. O MERGE aceitou
a revisão maior nas duas auxiliares, mantendo a tabela de casos.

A Gold identificou um caso afetado e recalculou sua linha ABT. Como os
indicadores mensais v1 medem contagens, rótulo e cobertura, esses montantes
corrigidos não mudaram seus valores. Por isso verificamos também as colunas
da ABT, além do agregado mensal. Depois, o caso 135 atrasado acrescentou uma
linha e alterou a população de janeiro de 2019. São causas diferentes.

O servidor guarda os arquivos; S3A permite processá-los; Delta registra os
commits; o contrato decide se os dados podem ser aceitos; o manifesto escolhe
quais versões das cinco tabelas o analista pode consumir juntas. Cada ferramenta
resolve uma parte da mesma entrega. A [evidência F08](../evidencias/F08_OBJETOS.md)
permite conferir esse caminho, incluindo a falha entre commit privado e aprovação.

### Como aprovar um conjunto em objetos

1. Preparar tabelas em um prefixo privado pertencente à tentativa.
2. Validar contratos, dados, arquivos, UUIDs e versões.
3. Publicar o manifesto imutável com hashes e referências.
4. Atualizar CURRENT por PUT condicional, exigindo o ETag que foi lido.
5. No consumo, resolver o manifesto uma vez e ler suas versões explícitas.

O **ETag** atua como token para detectar uma troca concorrente do ponteiro.
O **SHA-256** confere os bytes do conteúdo. Não assumimos que um ETag seja
sempre um hash de conteúdo. Um mutex no controle local impede dois escritores
cooperantes no mesmo host; ele não é um lock distribuído no bucket. Essa é a
razão de limitar a execução a um host/driver escritor. Manifesto continua sendo
um protocolo de visibilidade para consumidores, sem transação global entre tabelas.

Uma falha após MERGE privado da correção manteve CURRENT no baseline. O retry
usou o commit já feito e terminou a publicação sem novo MERGE. O serviço também
foi parado: a leitura falhou, e após reinício as cinco tabelas e o ponteiro foram
verificados. Retenção configurada em 30 dias e pins indefinidos preservam história;
nenhum VACUUM foi executado nos dados reais.

### Operar sem confundir parada e remoção

`service stop` encerra o processo; os objetos continuam no backend persistente.
`service restart` reaproveita esse backend. Apagar o diretório interno do
servidor destruiria os objetos e a reprodução histórica. O teste de remoção
usa somente outro serviço em diretório temporário criado pela própria fixture.
Os comandos completos estão na [operação F08](../objetos/OPERACAO.md).

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
publicações e recuperação. A [matriz operacional](../operacao/MATRIZ_OPERACIONAL.md) documenta
a consolidação executada em F09. A
[evidência F08](../evidencias/F08_OBJETOS.md) registra o replay nativo S3A, as
comparações, a recuperação e os recursos medidos.

Em [run_objects_demo.py](../../src/pipelines/run_objects_demo.py), siga o espelho,
o replay, o congelamento e as três publicações. Em
[client.py](../../src/object_store/client.py), compare `put_new` e `replace`:
qual condição evita sobrescrever algo inesperado? Em
[publication.py](../../src/object_store/publication.py), acompanhe
`publish_object_snapshot` e `open_object_publication`. Em
[spark.py](../../src/object_store/spark.py), identifique conector, endpoint,
versões e implementação de LogStore. Relacione cada configuração à tabela acima.

## Atividade e conferência

Uma publicação usa Silver versão 2 e Gold versão 5. A próxima tentativa grava
Silver versão 3 e falha antes da nova Gold. Qual conjunto o consumidor deve usar?

**Conferência:** o conjunto aprovado anterior, 2/5, até uma nova publicação
completa ser validada. Esses números são versões por tabela e não precisam
ser iguais entre si. O ponteiro e os arquivos necessários precisam ser preservados.

Atividade adicional: o servidor foi parado depois de uma publicação aceita.
Os objetos foram apagados? O leitor pode escolher simplesmente a maior versão
de cada tabela quando o serviço voltar?

**Conferência:** parar conserva o backend. Após reinício, o leitor verifica
CURRENT e o manifesto com suas cinco versões, pois versões mais altas isoladas
podem pertencer a uma tentativa privada incompleta.

Próximo: [12 — Testes, CI e entrega](12_TESTES_E_ENTREGA.md).
