# 3 — Python, ambiente, configuração e Git

[Percurso](../GUIA_ESTUDO_LAKEHOUSE.md) · Anterior: [Dados e SQL](02_DADOS_E_SQL.md)

Objetivo: entender como o projeto executa fora de uma sessão interativa e quais
elementos permitem repeti-lo em outro ambiente. Pré-requisito: capítulos 1–2.

## Como Python organiza a implementação

Uma **função** recebe argumentos e executa uma responsabilidade. Um **módulo**
é um arquivo Python que pode importar outros módulos. Aqui, `src/pipelines/`
contém entradas de execução; `src/silver/` reúne transformação e persistência;
`src/quality/` concentra validações.

O comando `python -m src.pipelines.run_silver_initial` executa o módulo pelo
nome dentro do projeto. `argparse` interpreta parâmetros como `--sample`.
Esses parâmetros tornam a entrada explícita, sem depender de uma variável
que ficou na memória de um notebook.

Um `dict` agrupa valores; JSON registra relatórios; YAML declara configurações.
`Path` representa caminhos de filesystem. Exceções comunicam falhas, e
`try/finally` ajuda a encerrar recursos mesmo quando uma etapa falha.

## Por que existe um ambiente próprio

Bibliotecas precisam de versões compatíveis. A `.venv` isola as dependências
Python do projeto. Spark também executa na JVM, a máquina virtual Java: instalar
apenas Python não prepara todo o runtime. Os JARs Delta fornecem os componentes
Java/Scala usados pela integração com Spark.

| Elemento | Definição local |
|---|---|
| Python | 3.11.14 |
| Java | 17 |
| PySpark | 3.5.7 |
| delta-spark | 3.3.2 |
| `requirements.in` | Dependências diretas declaradas |
| `requirements.lock` | Dependências fixadas, incluindo transitivas |

Essa é a matriz adotada e validada no laboratório. Uma atualização futura exige
revalidar compatibilidade e testes. O runtime fica em `.runtime/` e `.venv/`;
dados e credenciais também têm regras para ficar fora do Git.

## Configuração só funciona quando o código a aplica

Em `configs/spark.yaml`, `local[2]` configura a execução local com duas threads
de trabalho. A sessão usa UTC para o tratamento de datas. `configs/paths.yaml`
define caminhos das camadas; loaders verificam essa configuração.

YAML é texto estruturado, não executa a configuração sozinho. A função
`load_spark_settings` lê e valida o documento, e `create_spark_session` aplica
as opções no construtor da sessão Spark.

## Leitura guiada do projeto

1. Abra [project.sh](../../scripts/project.sh). Observe os caminhos de Java,
   Python e o `exec` que inicia o comando recebido.
2. Abra [spark.py](../../src/utils/spark.py). Siga a configuração desde o YAML
   até a criação da sessão, incluindo a preparação Delta antes da JVM.
3. Abra [run_context.py](../../src/utils/run_context.py), `RunContext.create`.
   Localize `run_id`, horário UTC e paths: esse objeto reúne o contexto técnico.
4. No [entrypoint Silver](../../src/pipelines/run_silver_initial.py), leia
   `main`: parâmetros, contexto, sessão, chamada da pipeline e encerramento.

O comando abaixo apenas mostra a ajuda do entrypoint; não processa dados:

```bash
bash scripts/project.sh -m src.pipelines.run_silver_initial --help
```

## Git e reprodução

Git registra alterações dos arquivos de código e documentação. `git diff`
mostra mudanças locais; um commit identifica uma revisão registrada. Uma revisão
de código não identifica, sozinha, os arquivos de dados usados: por isso também
registramos hashes, contratos e versões de entrada/saída.

Veja [AMBIENTE_LOCAL.md](../AMBIENTE_LOCAL.md) para preparar o ambiente e a
[evidência F01](../evidencias/F01_AMBIENTE.md) para conferir a prova executada.
Ambiente compatível sustenta todas as etapas posteriores.

## Atividade e conferência

Descreva o que seria necessário para repetir uma execução além de possuir o
arquivo Python principal.

**Conferência:** módulos importados, dependências/runtime compatíveis,
configurações, parâmetros e entradas identificadas. Para conferir o resultado,
também são necessários contratos e evidências da saída. Um notebook aberto em
uma máquina não registra automaticamente esse conjunto.

Próximo: [4 — Spark e Parquet](04_SPARK_E_PARQUET.md).
