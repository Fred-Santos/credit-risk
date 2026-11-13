# 8 — Delta Lake e execução Silver de ponta a ponta

[Percurso](../GUIA_ESTUDO_LAKEHOUSE.md) · Anterior: [Transformações](07_TRANSFORMACOES_SILVER.md)

Objetivo: conectar arquivos, tabelas transacionais, validação persistida e
aceite operacional. Pré-requisito: Spark, Parquet, locks e tratamentos Silver.

## O que o Delta acrescenta aos arquivos

Uma tabela Delta tem arquivos de dados e um log em `_delta_log`. Esse log
descreve os estados da tabela, incluindo arquivos ativos e metadados. Um
**commit** registra uma alteração; uma **versão** identifica um estado técnico.

Imagine uma correção que substitui dados de um arquivo. O arquivo antigo pode
continuar no disco para permitir leitura histórica, embora tenha deixado de
participar do estado atual. O leitor Delta interpreta o log; ler todos os
Parquets fisicamente presentes pode trazer registros antigos junto dos atuais.

As transações Delta dão garantias por tabela nas condições suportadas pelo
runtime e armazenamento. Elas não verificam automaticamente todas as nossas
regras de negócio e não fazem três tabelas independentes virarem uma transação
global. Leitura histórica também depende de preservar os arquivos necessários.

## Como persistimos a Silver inicial

`materialize_initial` escreve as três tabelas com `format('delta')` e
`mode('errorifexists')`. Cada tabela começa na versão 0. O writer lê de volta
com Delta, verifica schema e compara os valores com os candidatos tratados.

O conjunto é preparado em staging e publicado por rename local. Um manifesto
registra tabelas, UUIDs, versões, schemas, chaves, contagens e checksums. UUID
identifica a tabela Delta; versão identifica seu estado. Ambos são distintos
do `run_id`, que identifica a tentativa da pipeline.

O pacote inicial é imutável. Sua identidade combina entrada, política, código e
runtime. Se o pacote já existe, o retry revalida e reutiliza sem overwrite ou
novo commit. Mudança de identidade pode criar outra geração, preservando a antiga.

## Persistir, validar e aceitar são etapas diferentes

O manifesto do writer descreve o que ele gravou. O contrato Silver deriva uma
expectativa independente do contrato de origem e da política aprovada. Validar
o estado persistido contra essa expectativa ajuda a detectar defeitos que uma
declaração do próprio writer não revelaria.

O comando operacional só emite aceite após leitura, tratamentos, persistência,
contratos e conferências finais. O recibo fica separado do pacote, vinculado
ao relatório aprovado por hash. Um relatório `passed` sem o recibo final não
constitui o aceite inicial desse protocolo.

Os contextos de leitura mantêm locks durante as ações Spark e verificam os
artefatos ao sair. O lock operacional impede execuções Silver simultâneas da
mesma seleção entre programas que seguem o protocolo.

## Leitura guiada: acompanhe uma execução inteira

Abra [run_silver_initial.py](../../src/pipelines/run_silver_initial.py), função
`run_silver_initial`, e siga estas chamadas nesta ordem:

| Chamada | O que observar |
|---|---|
| `bind_sample` | Seleção explícita e contagens esperadas |
| `open_bronze_snapshot` | Entrada aprovada e ações dentro do contexto |
| `transform_snapshot` | Conversões e prova de preservação |
| `materialize_initial` | Criação ou reutilização do pacote técnico |
| `open_initial_tables` | Leitura Delta por versões fixadas |
| `validate_silver_frames` | Contratos sobre os dados persistidos |
| `publish_acceptance` | Conferência final, relatório e recibo |

Depois, abra [initial_delta.py](../../src/silver/initial_delta.py) para localizar
a escrita e leitura por versão, e [acceptance.py](../../src/silver/acceptance.py)
para acompanhar a ordem relatório → recibo. A função `verify_acceptance` audita
os vínculos e arquivos; não lê linhas como um consumidor Delta.

## Comando e evidência

Com o ambiente e a Bronze aprovados, este comando processa o recorte real e
registra uma nova tentativa. No padrão `reuse`, o pacote existente é revalidado:

```bash
bash scripts/project.sh -m src.pipelines.run_silver_initial \
  --sample 7d58bbdaa00cbabfbce54d26
```

O modo `--existing error` recusa o destino já existente. A
[evidência F03.6](../evidencias/F03_EXECUCAO_SILVER.md) registra criação e retry
com 29 checks, 315.390 linhas e mesmos UUIDs/versões. Relatórios ficam em
`artifacts/silver_runs/`; recibos ficam no namespace Silver da seleção.

## Atividade e conferência

A gravação Delta terminou, mas os contratos falharam. O que pode existir e o
que o retry precisa conferir?

**Conferência:** pode existir pacote técnico sem aceite. O retry deve verificar
identidade, arquivos, valores e contratos antes de emitir recibo. A validação
falha não autoriza apagar o pacote existente para forçar uma nova execução.

## Evoluir um contrato sem aceitar qualquer mudança

F05 acrescentou `_silver_contract_version int` às cópias gerenciadas da Silver,
com autorização em [silver_managed_v2.yaml](../../configs/contracts/silver_managed_v2.yaml).
Não precisamos dessa coluna para mudar valores de negócio; ela demonstra uma
migração controlada. Versão Delta 0 guarda o esquema antigo, 1 adiciona a coluna
e 2 preenche o valor 2. **Versão do contrato e versão Delta são identificadores
distintos**, mesmo quando os números coincidem nesse exemplo.

Em [evolution.py](../../src/publication/evolution.py), siga `migrate_table`:
confira esquema, reconheça commits do próprio intento, adicione somente a coluna
permitida e faça backfill. Todas as colunas antigas são comparadas à entrada.
Coluna obrigatória ausente, tipo incompatível e coluna extra bloqueiam a escrita;
não usamos aceitação automática de qualquer schema.

O aceite F03 continua cobrindo somente a Silver inicial. F05/F06 introduzem
[manifestos e ponteiros de publicação](../PUBLICACAO_E_RECUPERACAO.md), explicados
no capítulo 11; a atualização incremental é o próximo assunto.

Próximo: [9 — Incremento e correções](09_INCREMENTO_E_CORRECOES.md).
