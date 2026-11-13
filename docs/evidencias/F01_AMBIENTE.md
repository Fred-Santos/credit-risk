# Evidência — F01, ambiente local e preparação da aquisição

Data: 12/11/2026. Aceite F01 limitado a Linux x86_64/WSL2 desta sessão.
Nenhum arquivo real Home Credit foi adquirido ainda. Não há execução Silver/Gold.

## 1. Inventário e decisão

| Item | Observado / escolhido |
|---|---|
| Sistema | Ubuntu 26.04.1 LTS, kernel WSL2 Linux x86_64 |
| CPUs lógicas visíveis | 12 |
| RAM visível | Aproximadamente 15,46 GiB |
| Disco livre inicial | Aproximadamente 949,81 GiB no filesystem do projeto |
| Python do sistema | 3.14.4, preservado |
| Python do projeto | 3.11.14 em `.runtime/python`, com ambiente `.venv` |
| Java | Temurin JRE 17.0.21+9 em `.runtime/java` |
| Spark / Delta | PySpark 3.5.7 / delta-spark 3.3.2 |
| Aquisição | Kaggle CLI 2.2.5; autenticação da conta ainda ausente |
| Containers | Não necessários nesta fase; Docker não encontrado no PATH |
| Paralelismo inicial | `local[2]`; driver 2 GB; shuffle 4 |
| Temporários da prova | `.runtime/tmp`, removidos ao encerrar |

Este inventário não altera a restrição de planejamento do computador do usuário
(32 GB de RAM e cerca de 200 GB disponíveis). Medições do recorte real terão de
caber no orçamento dele; não dimensionar a solução com base nos 950 GiB da sessão.

Dependências diretas em [requirements.in](../../requirements.in), transitivas
fixadas e com hashes em [requirements.lock](../../requirements.lock). Instalação
nativa isolada escolhida para reutilizar código sem manter stack Docker adicional.
A compatibilidade está justificada em [AMBIENTE_LOCAL.md](../AMBIENTE_LOCAL.md).

## 2. Arquivos e mudanças executadas

| Grupo | Implementação |
|---|---|
| Preparação | `scripts/bootstrap_environment.sh`, `scripts/install_java.py`, `scripts/project.sh` |
| Spark central | `src/utils/spark.py`, `configs/spark.yaml`, `configs/ivysettings.xml` |
| Paths centrais | `src/utils/paths.py`, `RunContext` e consumidores RAW/Bronze/qualidade/documentação |
| Prova e medição | `src/pipelines/check_environment.py`, `scripts/measure_resources.py` |
| Testes | Runner obrigatório, isolamento de stubs, configuração e integração real Bronze |
| Aquisição preparada | `src/pipelines/download_home_credit.py`; entrypoint antigo delega à aquisição seletiva |

Foram preservadas as alterações locais anteriores de Bronze/qualidade. Na suíte
unitária, o módulo Bronze é carregado em cópia privada com doubles, evitando
deixar funções falsas no módulo produtivo usado pela integração real.

Na instalação, o cliente Kaggle exigiu `six`, não resolvido inicialmente como
dependência transitiva. A dependência foi explicitada e fixada. O endpoint
Adoptium consultado retornou HTTP 403; o runtime foi obtido do release oficial
Temurin no GitHub e validado com SHA-256 fixado no script. Essas foram limitações
de instalação resolvidas, não rejeições de aprovação nem falhas da base de dados.

## 3. Prova Spark/Delta

Comando reproduzível:

```bash
bash scripts/project.sh -m src.pipelines.check_environment
```

Resultado: `passed`. Versões observadas: Python 3.11.14, Spark 3.5.7,
delta-spark 3.3.2 e Java 17.0.21. Sessão usou `local[2]` e shuffle 4.

Dados de teste sintéticos:

| Estado | case_id 101 | case_id 102 |
|---|---:|---:|
| Versão inicial 0 | target 0 | target 1 |
| Após merge | target 1 | target 1 |
| Leitura histórica da versão 0 | target 0 | target 1 |

As comparações foram feitas contra esses valores esperados. A sessão foi encerrada
e a tabela temporária removida. Isso prova o funcionamento inicial do runtime,
não o aceite de todos os cenários Lakehouse, nem uma conclusão analítica Home Credit.

## 4. Testes e verificações

```bash
bash scripts/project.sh scripts/run_tests.py --integration-required
bash scripts/project.sh -m unittest discover -s tests -p test_quality_spark.py -v
```

Suíte completa: **31 testes aprovados, nenhum ignorado**, em 8,642 s na execução
registrada. Inclui 4 testes com Spark real: unicidade entre arquivos, nulos/domínio,
referências e build Bronze após os doubles unitários. O teste Bronze usa paths
personalizados e verifica que o relatório de qualidade segue a configuração.

Testes de aquisição verificam repetição sem download, integridade da origem,
falha de transporte, retomada após publicação e conteúdo ZIP. Eles usam payloads
controlados; não comprovam transporte autenticado da Home Credit.

O runner obrigatório também foi executado com o Python do sistema sem PySpark:
retornou código 1 e diagnosticou integração ausente, em vez de aprovar testes
ignorados. Sintaxe dos scripts Bash foi conferida com `bash -n`.

## 5. Recursos da prova

```bash
bash scripts/project.sh scripts/measure_resources.py -- bash scripts/project.sh -m src.pipelines.check_environment
```

| Medida | Resultado observado |
|---|---:|
| Tempo total amostrado | 17,379 s |
| Pico amostrado de RSS da árvore de processos | 1.482.719.232 bytes, aproximadamente 1,38 GiB |
| Pico amostrado de arquivos lógicos no temporário | 7.955 bytes |
| Amostras / intervalo | 170 / 0,1 s |
| Tamanho observado `.runtime` via `du` | Aproximadamente 248 MiB |
| Tamanho observado `.venv` via `du` | Aproximadamente 367 MiB |

RSS é a soma da árvore de processos e pode contar páginas compartilhadas mais
de uma vez. A amostragem pode perder picos curtos. Os 7.955 bytes são somente
temporários da pequena tabela, não o disco total necessário ao projeto. Cache
de instalação em `/tmp`, dados reais futuros e imagens de outros projetos não
estão incluídos na soma acima. Essa medida não autoriza extrapolar capacidade
para o conjunto completo.

Uma medição anterior com `/usr/bin/time` mostrou somente cerca de 36 MB para o
driver e não capturou a RAM da JVM. Ela foi descartada como estimativa da memória
total, motivando o amostrador da árvore de processos.

## 6. Fonte real e pendência de continuidade

O usuário informou participação na competição e confirmou uso dos dados reais.
A aquisição seletiva foi implementada com seis arquivos previstos e manifestos
por fonte; o plano sem rede foi conferido. A tentativa de aquisição retornou erro
controlado, sem publicar arquivo real: falta autenticação Kaggle na sessão.

Próxima ação do usuário, no terminal:

```bash
bash scripts/project.sh -m kaggle auth login
```

Em seguida, conferir o acesso e executar o download conforme
[AMBIENTE_LOCAL.md](../AMBIENTE_LOCAL.md). F02.1 continua em andamento até validar
API, nomes e arquivos reais. A inspeção de F00.3, os contratos e o recorte não
foram marcados como concluídos.

Relatórios locais: `artifacts/environment_check.json` e
`artifacts/resource_check.json`, não rastreados no Git. Esta evidência registra
os resultados observados; reexecuções podem apresentar tempos e consumo diferentes.
