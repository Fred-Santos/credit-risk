# F08 — operação do armazenamento local

A [decisão e arquitetura](DECISAO_E_ARQUITETURA.md) define camadas, licenças,
conector e o limite de um host/driver cooperante. A configuração está em
[object_store_v1.yaml](../../configs/object_store_v1.yaml).

## Preparar e iniciar

Na raiz, com o ambiente principal Python/Java já preparado:

```bash
bash scripts/bootstrap_objects.sh
bash scripts/objects.sh -m src.object_store.service start
bash scripts/objects.sh -m src.object_store.service status
```

O bootstrap verifica o SHA-256 oficial do tar SeaweedFS 4.53, extrai somente o
binário regular esperado e instala o cliente S3 pelas versões/hashes de
`requirements.objects.lock`. Tudo fica em `.runtime`; não é instalado um daemon
do sistema. Na primeira sessão S3A, Ivy resolve os JARs Hadoop/AWS fixados.

O serviço cria credenciais aleatórias em `.runtime/object-store/credentials.json`,
com modo 0600. A configuração de autenticação também é privada, fora do Git.
Não copiar chaves para YAMLs ou comandos. O bucket é `credit-risk-local`, região
técnica `us-east-1`, endpoint **http://127.0.0.1:18333**. Esse nome de região não
representa conexão à AWS.

| Componente | HTTP local | gRPC local |
|---|---|---|
| S3 | 18333 | 28333 |
| Filer | 18888 | 28888 |
| Master | 19333 | 29333 |
| Volume | 19340 | 29340 |
| Controle interno | 18535 | 28535 |

Todos os listeners são em 127.0.0.1. WebDAV, catálogos Iceberg/Lance, UI
administrativa e porta administrativa legada foram desabilitados; o modo mini
conserva as portas internas de controle declaradas acima. Telemetria externa
foi desativada. Não há acesso de rede de outros computadores configurado.

O volume é limitado a 32 segmentos de até 128 MiB, sem pré-alocação configurada.
O laboratório mantém metadados e arquivos persistentes em
`data/object-store/seaweedfs/`, ignorado pelo Git. Esse diretório pertence ao
servidor; a aplicação lê/grava dados pela API S3 e pelo conector S3A.

## Executar a demonstração com dados reais

Os relatórios de entrada precisam existir e estar aprovados:

```bash
bash scripts/objects.sh -m src.pipelines.run_objects_demo \
  --sample 7d58bbdaa00cbabfbce54d26 \
  --f04-report artifacts/f04/runs/20261113T020347Z_1609747b.json \
  --f06-report artifacts/f06/runs/20261113T040310Z_1f51ffa0.json
```

O comando inicia o serviço e o encerra no `finally`, preservando dados. Use
`--keep-service` somente quando quiser continuar consumindo depois. Não iniciar
outro escritor nem parar o serviço durante uma execução normal. As interrupções
deliberadas dos testes fazem parte de cenários controlados.

O fluxo copia e verifica entradas, reconcilia Bronze, aplica lotes/revisões em
Delta S3A, compara a reconstrução independente, congela o estado e publica
baseline/corrected/late. Cada publicação contém três Silver e duas Gold. As
saídas são comparadas com F04/F06 locais. Falha, retry, rollback e reinício
também fazem parte da demonstração; não são novos dados de negócio reais.

Relatórios completos: `artifacts/f08/runs/<run_id>.json`. Tentativas de publicação,
inclusive falhas quando o servidor está indisponível, ficam em
`artifacts/f08/attempts/`. O log do processo é
`.runtime/object-store/control/server.log`.

## Layout e consumo

```text
s3a://credit-risk-local/lakehouse-v1/
  inputs/<mirror_id>/                      # RAW, recorte, Bronze, eventos e hashes
  working/<selection_id>/<stream_id>/      # replay privado; _FROZEN após aceite
  published/<selection_id>/<publication_id>/
    silver/<table>/                       # dados e _delta_log
    gold/abt/
    gold/monthly_metrics/
  publications/<selection_id>/
    intents/  owners/  blobs/
    manifests/<publication_id>.json
    activations/
    _CURRENT.json
```

Para consultar a publicação aprovada atual, com serviço ligado:

```bash
bash scripts/objects.sh -m src.object_store.admin inspect \
  --sample 7d58bbdaa00cbabfbce54d26
```

`--publication` seleciona explicitamente um ID aprovado do relatório F08.
O consumidor confere arquivos, versões, schemas e UUIDs antes das ações. Um
CURRENT ausente é erro explícito; não há escolha automática de pasta ou versão
mais alta. A leitura histórica não precisa ativar aquele resultado como atual.

Em Python, [open_object_publication](../../src/object_store/publication.py)
devolve DataFrames sob contexto. Executar suas ações dentro do `with`; as
entradas são verificadas novamente ao sair. O leitor admite publicações
anteriores enquanto suas tabelas/manifestos continuam preservados.

## Recuperar uma publicação aprovada

O comando abaixo recebe um ID **já aprovado**, copiado do relatório F08. Ele
confere o conjunto antes de selecionar outro CURRENT; não regrava tabelas:

```bash
OBJECT_PUBLICATION_ID='substitua-pelo-id-aprovado-do-relatorio-F08'
bash scripts/objects.sh -m src.object_store.admin activate \
  --sample 7d58bbdaa00cbabfbce54d26 \
  --publication "$OBJECT_PUBLICATION_ID"
```

O placeholder precisa ser substituído; nomes de snapshots como baseline não são
IDs. Para restaurar o estado final após rollback, repetir com o ID de late.
Uma falha posterior à gravação do ponteiro pode deixar a publicação nova já
ativa: conferir CURRENT e executar retry, em vez de supor rollback automático.

## Parar, reiniciar e manter

```bash
bash scripts/objects.sh -m src.object_store.service stop
bash scripts/objects.sh -m src.object_store.service restart
```

Parar fecha o processo com SIGTERM e mantém arquivos, metadados, credenciais e
publicações. Reiniciar usa o mesmo diretório. O controlador verifica PID,
binário e diretório antes de sinalizar, evitando atingir um processo de PID
reutilizado. O código trata TIME_WAIT nas verificações de porta; uma porta
realmente ocupada por outro serviço impede iniciar.

Não executar VACUUM em tabelas reais, apagar entradas espelhadas ou remover
blobs/manifestos publicados. A retenção Delta é 30 dias, e pins de publicação
e entrada são indefinidos. Listar ou conhecer a versão não garante reprodução
se alguém remover os objetos necessários. O procedimento de descarte real
continua exigindo uma decisão explícita sobre os pins e seus consumidores.

O serviço tem varredura automática de vacuum de volumes desabilitada nesta
configuração. Isso é diferente de VACUUM Delta: um mantém a estrutura interna
do servidor e o outro remove arquivos obsoletos de tabelas. Nenhum descarte
destrutivo dos dados reais faz parte da demonstração.

## Testes e remoção do laboratório

```bash
bash scripts/objects.sh tests/object_store_integration.py
bash scripts/project.sh -m unittest discover -s tests -p test_object_store_policy.py
```

As fixtures geram namespaces imprevisíveis próprios e os removem por API. A
fixture de ciclo de vida cria outro serviço em TemporaryDirectory, com outras
portas, escreve dado sintético, para/reinicia, verifica persistência e remove
somente sua raiz temporária. Ela não recebe caminho do usuário para apagar.

Para encerrar o laboratório real, `stop` é suficiente e preserva sua história.
Excluir `data/object-store/seaweedfs` destruiria as cópias em objetos e sua
reprodução; isso não foi feito. Remoção do armazenamento real e retirada de pins
não são executadas automaticamente para limpar espaço. A remoção validada nesta
fase é a do laboratório temporário criado pela própria fixture.

## Limites

O serviço é um nó no host local, sem alta disponibilidade ou teste de perda de
energia. HTTP é restrito ao loopback; não foi configurado acesso remoto/TLS.
Os testes validam as operações e falhas deste runtime, não todos os recursos
S3 ou garantias de AWS. A operação completa e sua interface única seguem em F09.
