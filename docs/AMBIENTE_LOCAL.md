# Ambiente local e aquisição da Home Credit

Atualizado em 13/11/2026. Implementação validada em Linux x86_64/WSL2.

## 1. O que está preparado

O ambiente do projeto fica em `.venv/` e `.runtime/`, sem substituir o Python do
sistema. Home Credit continua sendo a fonte da ABT e das análises. Os dois casos
da prova de ambiente e as fixtures dos testes servem somente à validação técnica.

| Componente | Versão de trabalho | Papel |
|---|---|---|
| Python | 3.11.14 | Aplicação e cliente Kaggle |
| Java Temurin | 17.0.21+9, JRE | Execução da JVM Spark |
| PySpark | 3.5.7 | Leitura, transformação e consultas |
| Delta Lake | 3.3.2 | Tabelas transacionais |
| PyYAML | 6.0.3 | Configuração e regras |
| Kaggle CLI | 2.2.5 | API oficial para baixar os dados reais |
| six | 1.17.0 | Import exigido pelo cliente Kaggle instalado |

A linha Delta 3.3 é compatível com Spark 3.5. Java 17 é suportado pela linha
Spark escolhida. Python 3.11 evita depender do Python 3.14 do sistema para este
primeiro ambiente. A combinação foi exercitada localmente; versões mais novas
não são requisito do MVP.
[Referências: matriz Delta](https://docs.delta.io/releases/) e
[instalação Spark 3.5.7](https://spark.apache.org/docs/3.5.7/api/python/getting_started/install.html).

## 2. Preparar em outra instalação Linux x86_64

Na raiz do repositório, com Python 3, Bash e acesso à internet:

```bash
bash scripts/bootstrap_environment.sh
```

O bootstrap usa uv 0.9.9, instala Python isolado, sincroniza `requirements.lock`
com hashes e baixa um runtime Temurin cujo SHA-256 está fixado no script.
Dependências diretas estão em `requirements.in`; o lock registra também as
transitivas. Não é necessário instalar Spark separadamente nem manter Docker
ativo para esta etapa.

O download inicial acessa PyPI, os releases oficiais usados pelo Python/Java e
Maven Central para os JARs Delta. Após resolver esses JARs, o cache fica em
`.runtime/ivy`. Rede indisponível ou configuração de proxy podem impedir essa
etapa; não é um erro dos dados.

O bootstrap está limitado à plataforma descrita. Em outros sistemas, preparar
Python/Java compatíveis e adaptar os scripts antes de alegar reprodução validada.
O diretório `.runtime` contém ferramentas/cache; não contém dados analíticos.

Desde F07, a camada gráfica tem um lock separado, sem modificar o ambiente
principal. Antes do relatório e do runner completo, preparar:

```bash
bash scripts/bootstrap_analysis.sh
```

Matplotlib/NumPy e transitivas ficam em `.runtime/analysis`; o wrapper
`scripts/analysis.sh` acrescenta esse diretório ao caminho Python do processo.
Detalhes, plataforma, versões e hashes em [execução analítica](analise/EXECUCAO.md).

## 3. Validar e medir

```bash
bash scripts/project.sh -m src.pipelines.check_environment
bash scripts/project.sh scripts/run_tests.py --integration-required
bash scripts/project.sh scripts/measure_resources.py -- bash scripts/project.sh -m src.pipelines.check_environment
```

A prova cria uma tabela temporária, corrige um registro via merge e compara a
versão atual com a versão 0. Remove os dados de teste ao encerrar. O relatório
local fica em `artifacts/environment_check.json`; os recursos amostrados ficam
em `artifacts/resource_check.json`. Essas pastas estão fora do Git.

O runner obrigatório falha se houver testes ignorados. O runner padrão do
`unittest` continua útil em máquinas sem JVM, mas testes ignorados não comprovam
integração. O cache de módulos falsos da suíte unitária foi isolado para que
não contamine o build Bronze usado pela integração real.

A medição soma RSS da árvore Python/Java, amostrada a cada 0,1 s. Pode contar
páginas compartilhadas mais de uma vez e perder picos curtos. O disco amostrado
é somente `.runtime/tmp`; não representa toda a instalação, arquivos baixados,
caches externos ou o pico futuro da Home Credit. Uma métrica de `/usr/bin/time`
do driver isolado não deve ser apresentada como RAM total do Spark.

## 4. Configuração realmente aplicada

[spark.yaml](../configs/spark.yaml) define `local[2]`, memória do driver de 2 GB,
quatro partições de shuffle e timezone UTC. Os entrypoints RAW e Bronze usam a
mesma factory em [spark.py](../src/utils/spark.py). A prova registra configurações
observadas na sessão.

[paths.yaml](../configs/paths.yaml) define camadas e diretórios documentais.
[RunContext](../src/utils/run_context.py) carrega os valores e os compartilha com
qualidade, métricas, dicionário, inventário e lineage. O MVP aceita caminhos
locais relativos dentro do repositório; camadas não podem compartilhar ou conter
o caminho de outra camada. Objetos locais serão integrados em F08.

Não aumentar paralelismo, memória ou partições apenas por haver mais recursos.
Primeiro medir o recorte real; os valores iniciais são um ponto de partida.

## 5. Autenticar a conta Kaggle

A inscrição na competição foi informada pelo usuário. O acesso desta sessão foi
confirmado em 12/11/2026 e o conjunto selecionado já foi baixado. As instruções
abaixo servem para preparar outra instalação ou renovar acesso. A inscrição pelo
navegador não configura automaticamente as credenciais da API no terminal.

Execute no terminal do projeto:

```bash
bash scripts/project.sh -m kaggle auth login --no-launch-browser
```

No WSL, usar o modo manual acima evita depender de `gio` para abrir o navegador
e de um callback para uma porta localhost. O cliente imprime uma URL nova;
abra-a no navegador do Windows, conclua o login e cole o código de verificação
fornecido pelo Kaggle **no terminal que está aguardando**, não no chat.

Na tentativa informada pelo usuário em 12/11/2026, `gio` retornou `Operation not
supported` e o callback recebeu `GET /` com HTTP 400. Isso não comprova problema
na conta. O código instalado mostra que `--no-launch-browser` usa URL e código
manual, sem iniciar aquele servidor de callback. Não reutilizar a URL antiga,
pois ela pertence à tentativa encerrada. Posteriormente, o usuário configurou
o token e a API respondeu com sucesso; a validação efetiva está registrada na
[evidência da fonte real](evidencias/F00_F02_FONTE_REAL.md).

Alternativamente, gere um token em
[Kaggle Settings / API](https://www.kaggle.com/settings/api), em **Generate New Token**,
e execute:

```bash
bash scripts/project.sh scripts/configure_kaggle_token.py
```

Cole o token no prompt oculto do terminal. O script salva `.kaggle/access_token`
com permissão restrita, sem incluí-lo no histórico. O wrapper aponta
`KAGGLE_API_TOKEN` para esse arquivo, pois o SDK instalado não usa
`KAGGLE_CONFIG_DIR` para localizar o arquivo de token automaticamente.
Também é possível usar o arquivo legado `.kaggle/kaggle.json`.
O wrapper usa `KAGGLE_CONFIG_DIR=.kaggle` por padrão e respeita um diretório já
definido por essa variável. Não envie tokens no chat nem os inclua em logs.
[Referência oficial: autenticação Kaggle](https://github.com/Kaggle/kaggle-cli/blob/main/docs/README.md).

Uma configuração `servers.kaggle` com URL `https://www.kaggle.com/mcp` conecta
um cliente MCP ao Kaggle; ela não autentica automaticamente a CLI usada pela
pipeline. Não é necessário alterar `settings.json` para executar a aquisição
atual. A opção de token acima atende ao cliente que já está instalado.

Após autenticar, confira o acesso e os nomes publicados:

```bash
bash scripts/project.sh -m kaggle competitions files home-credit-credit-risk-model-stability --page-size 200
```

Não executar comandos de submissão: nosso fluxo atual apenas lê a fonte.
Revisar divulgação externa antes da publicação continua sendo uma etapa distinta.

## 6. Baixar o conjunto inicial

```bash
# Mostra o plano sem autenticar, baixar ou iniciar Spark.
bash scripts/project.sh -m src.pipelines.download_home_credit --plan

# Baixa os seis arquivos selecionados e registra checksums.
bash scripts/project.sh -m src.pipelines.download_home_credit
```

O comando seleciona `feature_definitions.csv`, `train_base`, os dois shards de
`train_static_0` e os dois de `train_applprev_1`. São arquivos reais completos
dessas tabelas, não o recorte final de até 50 mil casos. A seleção determinística
de casos será implementada na etapa do recorte, preservando a RAW selecionada.

O downloader chama `competitions download --file` do cliente oficial em staging
e preserva os caminhos de origem. Não baixa a competição inteira nem apaga CSVs
ou dados de teste já existentes. O antigo `python -m src.pipelines.ingest_raw`
passa a delegar a essa aquisição seletiva.
[Referência: download seletivo Kaggle](https://github.com/Kaggle/kaggle-cli/blob/main/docs/competitions.md).

Um journal em `data/raw/_acquisition/` identifica arquivo, competição, instante,
tamanho, checksum e estado. Dados são publicados sem sobrescrever arquivos
existentes. Reexecução verifica conteúdo e evita novo download; uma interrupção
entre publicação e confirmação do journal é recuperável. Fonte existente sem
manifesto ou com checksum divergente é preservada e causa erro para investigação.
Isso garante integridade local; não comprova automaticamente que a origem remota
não foi atualizada desde a aquisição.

A implementação de lock/publicação foi feita para filesystem Linux/WSL. Ela
precisará de adaptação para armazenamento de objetos. O download autenticado
foi validado para os seis arquivos selecionados, com nomes e tamanhos conferidos
contra a API e reexecução sem novo download.

## 7. Depois do download

A inspeção inicial dos arquivos reais já confirmou esquemas, contagens, chaves
e período. Para reproduzir o relatório local, sem modificar os arquivos RAW:

```bash
bash scripts/project.sh -m src.profiling.inspect_home_credit
```

Saída: `artifacts/source_inspection/<run_id>.json`, contendo esquemas, nulos/NaN,
unicidade após união dos shards, domínio do rótulo, datas e cobertura das fontes.
O script não exporta registros individuais. Os resultados atuais estão na
[evidência da fonte real](evidencias/F00_F02_FONTE_REAL.md).

Contratos e recorte já foram definidos e validados. Para materializar ou conferir
a seleção atual:

```bash
bash scripts/project.sh -m src.pipelines.build_sample
```

Política, layout e limitações em [RECORTE_E_LOTES.md](RECORTE_E_LOTES.md);
regras em [contratos](contratos/README.md). A pasta de saída é separada da RAW,
com nome derivado da identidade da fonte/configuração/código.

A Bronze já aceita o recorte explicitamente, com saídas e relatórios separados:

```bash
bash scripts/project.sh -m src.pipelines.run_bronze_mvp --sample 7d58bbdaa00cbabfbce54d26
```

O identificador deve ser o do recorte publicado. O entrypoint exige `--sample`
ou `--raw`; os modos ficam isolados. Execução e recuperação estão em
[BRONZE_DO_RECORTE.md](BRONZE_DO_RECORTE.md). O antigo perfil RAW continua
disponível em `src.pipelines.run_raw_mvp`, usando a origem configurada.

Esses comandos ainda não entregam Silver/Gold. A prova Delta também não aceita
por si só o Lakehouse completo. O andamento continua em
[ROTEIRO_EXECUCAO_LAKEHOUSE.md](ROTEIRO_EXECUCAO_LAKEHOUSE.md).

## 8. Encerrar

Os comandos encerram a sessão Spark ao finalizar. Não há serviço Docker deste
projeto para manter ativo. Dados de teste temporários são removidos; `.runtime`,
`.venv`, autenticação local e arquivos reais adquiridos permanecem em disco.
Não apagar esses diretórios durante execuções. A reprodução em ambiente limpo
e o procedimento de manutenção completo serão novamente conferidos em F10/F11.
