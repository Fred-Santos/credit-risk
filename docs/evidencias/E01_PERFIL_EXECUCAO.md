# E01 — Perfil Spark de 8 GiB e capacidade inicial

Data de referência: 18/11/2026. Estado: E01.1–E01.4 aceitos para a carga
representativa; capacidade do fluxo completo permanece em E07.

## Configuração e isolamento

Perfil novo: [spark_expansion.yaml](../../configs/spark_expansion.yaml).
`configs/spark.yaml` permanece com driver de 2 GB para reprodução do MVP.
O novo perfil usa `local[2]`, heap `8g`, quatro partições de shuffle,
paralelismo dois e `maxResultSize=256m`. Não houve aumento de concorrência.

As duas fábricas Spark aceitam `config_path` explícito. Esse uso exige um
processo sem contexto nem gateway JVM preexistentes: parar uma sessão não
redimensiona o heap da JVM. O perfil de expansão não substitui o padrão
implicitamente; os novos fluxos devem selecioná-lo na inicialização.

A carga gera uma cópia efetiva do perfil por execução, com `spark.local.dir`
privado e event logs locais. O relatório guarda a configuração sem credenciais,
o hash do perfil e o heap real. Nenhuma Bronze, Silver, Gold ou CURRENT foi
modificada. A agregação local em Delta fica em `artifacts/expansion/e01/`.

## Execução observada

ID: `3fab4caf7f6d4479b2e7491918a64646`.

| Verificação | Resultado |
|---|---:|
| Heap máximo real da JVM | 8,589,934,592 bytes = 8 GiB |
| Spark / Delta | 3.5.7 / 3.3.2 |
| Java / Hadoop | 17.0.21 / 3.3.4 |
| Tempo total, incluindo inicialização e encerramento | 47.808 s |
| Pico RSS amostrado da árvore | 3.85 GiB |
| Menor memória disponível no Linux/WSL | 9.20 GiB |
| Maior uso de swap observado no host | 0 bytes |
| Pico de arquivos lógicos no scratch medido | 502.09 MiB |
| Pico de arquivos lógicos no diretório de artefatos | 30.98 MiB |
| Disk spill / memory spill reportados nas tarefas | 0 / 0 bytes |
| Shuffle escrito / lido | 84,801,460 / 84,801,460 bytes |
| Tarefas registradas | 67 |

A maior tabela, `train_credit_bureau_a_2`, foi projetada nas chaves
`case_id/num_group1` e agregada sobre **188.298.452 observações**, em 11 arquivos.
A escrita Delta local produziu **7.580.244 grupos**. A releitura reconciliou a
soma de observações com E00 e encontrou **1.385.288 casos**, com máximo de
**9.404 linhas por caso**. Duração dessa etapa: **20.322 s**.

A leitura da tabela larga percorreu suas **168 colunas e 1.526.659 linhas**,
calculando contagens de valores não nulos: **9.636 s**.
A carga não traz históricos completos ou linhas individuais ao Python:
apenas estatísticas agregadas são coletadas no driver.

A prova S3 usou somente dados sintéticos em prefixo de fixture único: escrita
Delta com dez linhas, append de cinco, releitura de **15 linhas** e leitura
histórica da versão zero com **dez linhas**. Os **nove objetos** da fixture
foram removidos ao final, e o serviço SeaweedFS, inicialmente parado, foi
encerrado preservando seus dados persistentes. A execução exigiu sockets
locais fora do sandbox; a tentativa restrita anterior falhou antes do Spark.

## Decisão de capacidade

**Manter 8 GiB, `local[2]` e quatro partições inicialmente.** Esta carga terminou
sem spill reportado, swap ou pressão de memória sustentada; não há evidência
que justifique aumentar o heap para 12/16 GB ou mudar partições agora.
O Linux/WSL enxerga aproximadamente **15,46 GiB**, apesar dos 32 GB físicos
informados. Reavaliar esse limite antes de qualquer aumento.

Heap máximo não é memória residente nem reserva exclusiva. A folga observada
vale para esta carga e serviços presentes. As leituras são projetadas e as
agregações específicas: o resultado não aprova joins completos, todas as
transformações Silver, uma ABT larga ou publicação de todas as tabelas juntas.
Também não comparar o tempo desta carga com os 401,889 s de E00: os trabalhos
executados são diferentes, sem experimento controlado de desempenho.

O scratch passou a ser medido no diretório efetivamente configurado para esta
JVM. RSS inclui descendentes e pode somar páginas compartilhadas; amostras de
0,5 s podem perder picos. O disco medido não inclui arquivos internos do
SeaweedFS, que recebeu apenas a fixture pequena. Métricas de spill/shuffle vêm
dos eventos das tarefas; valores de tentativas repetidas seriam somados.
O orçamento provisório de armazenamento de E00 continua como hipótese para
materializações, cópias e retenção, a ser substituída pela medição completa.

## Reprodução e validação

```bash
bash scripts/objects.sh -m scripts.measure_expansion_benchmark
bash scripts/project.sh -m unittest tests.test_spark_config tests.test_expansion_catalog tests.test_download_home_credit -q
```

A medição exige inicialmente ao menos 10 GiB disponíveis no Linux/WSL; o monitor
interrompe a carga se observar menos de 1 GiB disponível por três amostras
consecutivas. O processo deve rodar sozinho em relação a outros jobs Spark.
Os artefatos ficam em um novo ID, sem sobrescrever a execução acima.

**15 testes aprovados**, incluindo seleção de perfil, preservação do padrão,
recusa de perfil novo com contexto ou JVM preexistente, catálogo e downloader.
A prova Spark/Delta/S3 real terminou com exit code zero.
Para repetir o perfil E00 com o novo heap, a seleção de `--spark-config` exige
um novo `--output` (por exemplo, `artifacts/expansion/source_profiles_8g.json`).
Um destino explícito existente é recusado para preservar a evidência anterior.

## Evidências locais

- `artifacts/expansion/e01/3fab4caf7f6d4479b2e7491918a64646/report.json`: SHA-256 `7d83ac77048921a149c2cf356f52b66e6872f02243d0863b7624f1e77484c01b`.
- `artifacts/expansion/e01/3fab4caf7f6d4479b2e7491918a64646/resources.json`: SHA-256 `43be965717c13e7edbe938cffa17ae00beecf5fa730358205a621e53e764c2d2`.
- `artifacts/expansion/e01/3fab4caf7f6d4479b2e7491918a64646/spark_effective.yaml`: SHA-256 `19de2ab124bcf0c9b8ab663196fbee03a593dbe973320ad2436f05fa6ece50c3`.
