# Execução Silver inicial — F03.6

Entrypoint: [run_silver_initial.py](../../src/pipelines/run_silver_initial.py).
Aceite: [acceptance.py](../../src/silver/acceptance.py).
O comando reúne as funções de F03.2–F03.5 numa execução sem sessão de notebook.

## Executar

Na raiz, com o ambiente preparado e a Bronze do recorte aprovada:

```bash
bash scripts/project.sh -m src.pipelines.run_silver_initial \
  --sample 7d58bbdaa00cbabfbce54d26
```

`--sample` é obrigatório; não há descoberta automática da seleção ou de `latest`.
Os paths e parâmetros Spark vêm de `configs/paths.yaml` e `configs/spark.yaml`.
Contrato e política v1 são explícitos no código e fixados por hashes, sem opção
para pular validações ou aceitar regras arbitrárias.

`--existing reuse` é o padrão: se o pacote da mesma identidade existir, verifica
seus arquivos, versões, UUIDs, schema e valores contra os candidatos tratados.
Repete os contratos persistidos antes de emitir outro recibo. `reused=true` não
significa que a qualidade foi dispensada.

```bash
bash scripts/project.sh -m src.pipelines.run_silver_initial \
  --sample 7d58bbdaa00cbabfbce54d26 --existing error
```

`error` recusa um pacote já existente sob a identidade calculada. Em nenhum modo
há overwrite, append ou merge. Mudança na identidade técnica cria outro pacote,
preservando o anterior. A identidade tem a composição de F03.4; a adição do
controle `existing` ao writer altera seu hash e, portanto, gera um novo pacote
em relação à execução histórica de F03.4.

O notebook revisado é consultado somente como arquivo de proveniência, por hash.
Nenhuma célula é executada, nem há dependência de variável ou sessão interativa.

## Etapas e proteção

1. Validar parâmetros, configurações, hashes e vínculo com o recorte.
2. Adquirir `.silver_pipeline.lock` exclusivo por seleção, sem espera.
3. Abrir a Bronze aprovada sob seu lock, mantendo as ações Spark no contexto.
4. Aplicar as conversões de datas e provar preservação integral.
5. Criar ou verificar/reutilizar o pacote Delta imutável.
6. Ler as três versões persistidas pelo leitor Delta e executar seus contratos.
7. Sair normalmente dos leitores, que revalidam seus artefatos ao encerrar.
8. Conferir estabilidade de código/configuração e do pacote sob lock Silver;
   gravar relatório aprovado e, por último, recibo de aceite.

O lock operacional cobre todas as etapas depois da configuração. Os locks
Bronze e Delta continuam protegendo suas responsabilidades próprias. São locks
cooperativos de filesystem local; o segundo escritor falha para retry explícito.

## Relatório, recibo e manifesto técnico

| Artefato | Caminho | Papel |
|---|---|---|
| Relatório operacional | `artifacts/silver_runs/<run_id>.json` | Etapa, resultado, duração, entrada, hashes, transformações, pacote e contratos |
| Pacote técnico | `data/silver/samples/<selection_id>/initial/<materialization_id>/` | Três tabelas Delta imutáveis e `_materialization.json` |
| Recibo de aceite | `data/silver/samples/<selection_id>/acceptances/<run_id>.json` | Aprovação inicial explícita vinculada ao relatório, manifesto, versões e UUIDs |

Relatórios aprovados e recibos são publicados completos com hard link local
sem substituir destino existente. O relatório vem antes do recibo: relatório
`passed` sozinho não é aceite. Não há ponteiro global nem escolha implícita da
última geração. Cada tentativa precisa de um novo `RunContext`/`run_id`.

O manifesto técnico mantém seu status histórico
`materialized_pending_silver_acceptance`: não é editado para registrar o aceite.
A aprovação operacional é comprovada pelo recibo separado. Não há `_READY`
dentro do pacote imutável.

Para auditar um recibo explícito, sem iniciar JVM:

```python
from pathlib import Path
from src.silver.acceptance import verify_acceptance

receipt = verify_acceptance(Path.cwd(), Path("data/silver/samples/SELECAO/acceptances/RUN_ID.json"))
```

A auditoria verifica vínculo, hashes do relatório/manifesto e arquivos Delta;
não carrega linhas. Consultas tabulares continuam exigindo `open_initial_tables`
e todas as ações dentro de seu contexto. Código histórico é registrado por hash,
sem exigir que os arquivos atuais continuem iguais para auditar uma execução
anterior. Esses hashes não são uma assinatura contra adulteração coordenada.

## Falha e retomada

Falhas registram `failed`, etapa e causa, com código de saída não zero. Falhas
de tratamento/contrato incluem seus diagnósticos. Falha ao iniciar Spark também
gera relatório. Identificador inválido é recusado antes de iniciar a JVM.

Não há recibo novo quando tratamento, materialização, contrato ou conferência
final falham. Se a falha ocorrer depois de materializar, o pacote técnico pode
permanecer sem aceite: o retry revalida e reutiliza esse pacote. Falha entre
relatório e recibo deixa o relatório da tentativa como `failed`; recibos e
pacotes das execuções anteriores são preservados. Não se remove saída existente
para forçar um retry. Em interrupção abrupta do processo, pode restar relatório
sem recibo; ele continua sem aceite.

## Limites e continuidade

O recibo aceita somente o **snapshot Silver inicial local**. F03 fica concluída
com sua evidência, mas revisões, lotes incrementais e merge são F04. Publicação
com ponteiro seguro, evolução, recuperação histórica e retenção são F05; Gold
e ABT são F06. O aceite inicial não autoriza pular essas dependências.
Não há transação global entre tabelas Delta, garantia de persistência após
perda de energia, adaptação a objetos ou política de coleta automática.

Validação e resultados em [F03_EXECUCAO_SILVER.md](../evidencias/F03_EXECUCAO_SILVER.md).
