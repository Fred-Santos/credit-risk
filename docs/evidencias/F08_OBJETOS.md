# F08 — armazenamento de objetos local validado

Execução real em 13/11/2026, após F07. Código produtor e configurações estão
fixados pelos hashes do relatório; base de trabalho commit `61e7c75`.
O consumidor administrativo e a documentação foram acrescentados depois.

## Resultado e escopo

SeaweedFS 4.53 nativo, Apache 2.0, executado no host local. Endpoint
`http://127.0.0.1:18333`, bucket `credit-risk-local`. Todos os dez listeners
HTTP/gRPC foram verificados em loopback. Credenciais/configuração de autenticação
0600, ignoradas pelo Git; bootstrap valida SHA-256 do binário e dependências.
Comparação das alternativas, fontes primárias e posição das camadas:
[decisão e arquitetura](../objetos/DECISAO_E_ARQUITETURA.md).

F08.1–F08.6 demonstram seleção, configuração, I/O por objetos, execução Delta,
reconciliação e operação. RAW, recorte, Bronze e resultados anteriores do
filesystem foram preservados. As entradas foram espelhadas por API e conferidas
por SHA-256; o replay e as publicações usam Delta nativo sobre S3A.

## Execução reproduzível

```bash
bash scripts/bootstrap_objects.sh
bash scripts/project.sh scripts/measure_resources.py \
  --output artifacts/f08/resources_real.json \
  --workdir data/object-store/seaweedfs \
  -- bash scripts/objects.sh -m src.pipelines.run_objects_demo \
  --sample 7d58bbdaa00cbabfbce54d26 \
  --f04-report artifacts/f04/runs/20261113T020347Z_1609747b.json \
  --f06-report artifacts/f06/runs/20261113T040310Z_1f51ffa0.json
```

Relatório: `artifacts/f08/runs/20261113T140429Z_ca01e8a7.json`, status `passed`.
O comando inicia/para o serviço, conservando os dados. Runtime: Spark 3.5.7,
Delta 3.3.2, Hadoop/hadoop-aws 3.3.4, AWS Java SDK 1.12.262, boto3 1.44.2.
O relatório registra os hashes dos quatro JARs principais e de código/configuração.
As dependências S3 ficam isoladas de `requirements.lock` e das dependências F07.

Espelho `eeafc75f0683e0bb7b57b139`: **482.059.588 bytes** dos arquivos de entrada
inventariados em 113 arquivos. O tamanho não inclui o próprio marcador `_INPUTS.json`.
Estado de replay: `lakehouse-v1/working/7d58bbdaa00cbabfbce54d26/7e4f89a37859fa7e4d7db2d9`.
Sete pacotes reais simulados, 315.398 entregas, com versões finais 4/5/5.
Duplicata/revisão antiga e retry não geraram novos commits. Reconstrução
independente comparou todas as colunas, nos dois sentidos, antes de `_FROZEN.json`.

As três Bronze espelhadas coincidem com o filesystem. Os três snapshots de
Silver incremental coincidem com F04 (nove comparações). As cinco tabelas de
cada publicação coincidem com F06 (quinze comparações), sem linhas extras ou
ausentes. UUIDs e versões pertencem a cada reconstrução; sua igualdade física
entre filesystem e S3 não é um requisito.

| Snapshot | Publicação S3 | Linhas ABT | Versão ABT |
|---|---|---:|---:|
| baseline | `a2e682c7afad9fd51668df2a` | 49.999 | 0 |
| corrected | `0ed80cf8c98c041993328102` | 49.999 | 1 |
| late | `cdbf1a434ffc2a4a8670509b` | 50.000 | 1 |

CURRENT S3: `cdbf1a434ffc2a4a8670509b`. A publicação final fixa três Silver
(50.000/50.000/215.390 linhas), ABT de 19 colunas e indicadores de 22 meses.
Cada Silver gerenciada é versão 2; indicadores são versão 0. A ABT é versão
0 no baseline e 1 nos cenários derivados.

## Recuperação, histórico e consumo

Na correção houve falha deliberada depois do MERGE privado da ABT. CURRENT
permaneceu baseline. O retry concluiu sem segundo MERGE: uma atualização lógica,
zero inserts/updates adicionais nessa retomada. O atraso inseriu um caso.
A reexecução da publicação final reutilizou o manifesto já aprovado.

Rollback selecionou baseline e comparou suas duas Gold com o resultado antigo;
a ativação final restaurou late. Depois, serviço parado produziu
`EndpointConnectionError`; após reinício, CURRENT, inventários, UUIDs/versões
e todas as cinco tabelas continuaram válidos e iguais. As versões publicadas e
versão 0 das quinze tabelas foram lidas na auditoria de retenção.

Um processo Spark novo executou `src.object_store.admin inspect`, verificou a
publicação atual e retornou os 22 meses. Evidência em
`artifacts/f08/validation/consumer.json` e `consumer.log`.
A [operação](../objetos/OPERACAO.md) reúne iniciar/parar/reiniciar, leitura
histórica, ativação e manutenção. Parar conserva o backend. A fixture de ciclo
de vida demonstrou parar/reiniciar e remover somente seu laboratório temporário
internamente criado (`artifacts/f08/lifecycle_fixture.json`).

## Recursos medidos

| Medida | Resultado |
|---|---:|
| Core da demonstração, com validações e interrupção | 1.076,138 s |
| Processo completo | 1.088,267 s — 18 min 8 s |
| Pico RSS somado da árvore, incluindo Spark e SeaweedFS | 6.533.419.008 bytes — 6,08 GiB |
| Pico de arquivos lógicos no diretório do backend | 892.605.589 bytes |
| Soma dos tamanhos dos objetos no bucket ao fechar | 891.424.674 bytes |

Amostragem de 0,1 s pode perder picos curtos; RSS soma páginas compartilhadas.
Bytes de arquivos locais não são blocos físicos nem incluem ambiente/caches/SO.
O bucket inclui entradas, estado privado, três publicações e histórico; não é
apenas o tamanho da ABT atual. Não foi um benchmark isolado do MERGE nem comparação
controlada de velocidade entre fornecedores. Há espaço configurado de 32 volumes
de até 128 MiB, sem pré-alocação, e nenhuma expansão do recorte foi necessária.

## Validações

Dez testes reais S3A/Delta passaram em 440,785 s, sem ignorados, além de dois
testes de política. Cobertura: autenticação/listagem/condições de PUT; falhas
após commit Silver/Gold; janelas antes de manifesto e ponteiro; falha depois do
ponteiro; qualidade/schema/entre Silver e Gold; indisponibilidade/retry;
exclusão de escritor no host; corrupção de arquivo; replay/reconstrução/congelamento;
ciclo de vida e remoção da fixture. O smoke S3A também criou, alterou e leu versão
histórica de uma tabela temporária. Logs em `artifacts/f08/validation/`.

Regressão global: **129 verificações aprovadas em 1565.709 s, sem
ignorados**, com cinco suítes Delta (15/9/9/8/10 cenários, incluindo S3A) e uma
analítica Spark (seis). Os seis verificadores de subprocesso estão incluídos no
total do runner; não somar os níveis. Resultado e log com hash em
`artifacts/f08/validation/full_suite.json` e `full_suite.log`.
Comando: `bash scripts/project.sh scripts/run_tests.py --integration-required`.

Auditoria `artifacts/f08/protected_inputs_check.json`: seis RAW, recorte/Bronze,
dois recibos F03, 90 arquivos de tabelas publicadas F05 e 127 de F06, blobs e
referências conferidos por hash. Os dois CURRENT locais permanecem aprovados;
os dois bundles F07 mantêm os hashes de todas as saídas. Código/configuração
produtores F05/F06/F07 e F08 coincidem com suas referências registradas.

A conferência posterior às dez fixtures S3 verificou novamente CURRENT, os
127 arquivos das quinze tabelas publicadas (40/43/44 por cenário), os 83 arquivos
do estado incremental congelado e as 113 entradas espelhadas. Todos os hashes
permaneceram iguais. Resultado: `artifacts/f08/validation/s3_after_regression.json`.
O serviço foi parado novamente, preservando o backend. Credenciais locais não
foram encontradas nos arquivos rastreados/disponíveis ao Git nem nos logs salvos
(`artifacts/f08/validation/credential_check.json`).

## Limites das garantias

Um host e um driver Spark cooperante por vez. A exclusão de escritor fica no
controle local; dados, intentos, manifestos e ponteiro usam chaves S3, sem rename
POSIX nos caminhos de objetos. Publicação usa PUT condicional e ETag para
concorrência do ponteiro; SHA-256 verifica conteúdo. Os testes não certificam
múltiplos hosts/JVMs escritores, equivalência completa à AWS, alta disponibilidade
ou perda de energia. Leitura histórica usa `versionAsOf`; timestamps S3 podem
ter granularidade insuficiente para distinguir commits muito próximos.

Retenção Delta configurada em 30 dias; pins de entradas/publicações indefinidos.
Não houve VACUUM real ou simulação da passagem de 30 dias. Retirada de pins e
remoção do laboratório real dependem de procedimento explícito futuro.
Próxima fase: F09.1, comando único de operação e consolidação de observabilidade.
