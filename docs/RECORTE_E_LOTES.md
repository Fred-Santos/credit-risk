# Recorte determinístico e lotes simulados

Versão 1, em 12/11/2026. Políticas implementadas e validadas com dados reais.
Configuração: [sample_policy.yaml](../configs/sample_policy.yaml).
Código: [build_sample.py](../src/pipelines/build_sample.py).

## 1. Finalidade e seleção

O recorte limita o custo de desenvolvimento mantendo casos completos e suas
relações. Ele não foi desenhado para inferência estatística sobre a carteira da
Home Credit ou a população de clientes.

Após validar o snapshot de origem contra o contrato:

1. Representar `case_id` bigint como string decimal.
2. Calcular SHA-256 de `credit-risk-mvp-v1:<case_id>` em UTF-8.
3. Ordenar pelo hash hexadecimal, com `case_id` como desempate determinístico.
4. Selecionar os primeiros 50.000 casos, ou todos se houver menos casos na origem.
5. Usar semi-joins para preservar todas as linhas auxiliares relacionadas.

O `target` não participa da seleção. Não alterar seed ou limite para aproximar
uma taxa de desfecho desejada. A seleção independe da ordem física das linhas e
das partições de execução. Um teste compara o resultado Spark com uma referência
calculada usando `hashlib` Python, inclusive após mudar ordem e rótulos.

O hash é uma regra de seleção reproduzível; não é anonimização. IDs e atributos
reais continuam nos Parquets locais, fora do Git. Sem quotas por mês/semana ou
rebalanceamento de rótulos; distribuições serão medidas, não garantidas pela regra.

## 2. Identidade e preservação

A identidade do artefato inclui fingerprints dos seis arquivos de origem,
hash do contrato, hash da política, hashes dos arquivos de implementação
relevantes e versão Spark. O manifesto guarda a identidade completa e seu SHA-256;
o nome do diretório usa os primeiros 24 caracteres desse digest.

`run_id` identifica uma tentativa e não muda o conjunto selecionado. Um digest
adicional dos IDs ordenados permite comparar o conjunto entre execuções. Mudança
de fonte/política/implementação pode gerar outro artefato, preservando o anterior.
Mesmo após uma mudança técnica, o conjunto pode continuar igual se a regra e a
população não mudarem; compare o digest dos casos, não apenas o nome da pasta.

Não sobrescrever a RAW. O recorte é uma cópia filtrada com layout lógico próprio:

```text
data/samples/<selection_id>/
  _selection.json
  feature_definitions.csv
  case_batches/                  # case_id, WEEK_NUM e _batch_id
  parquet_files/train/
    train_base/
    train_static_0/
    train_applprev_1/
```

As auxiliares passam a ter pastas por tabela lógica, sem o sufixo físico de shard.
O manifesto relaciona essas saídas aos arquivos RAW originais. Não se afirma que
um arquivo de saída tenha correspondência individual com um único shard original.

## 3. Política dos lotes

| Lote | WEEK_NUM inclusivo | Uso planejado |
|---|---|---|
| `b00_w000_051` | 0–51 | Carga inicial |
| `b01_w052_077` | 52–77 | Novos casos do primeiro incremento |
| `b02_w078_091` | 78–91 | Novos casos do segundo incremento |

Os intervalos são contíguos, disjuntos e cobrem as semanas configuradas. Lacunas,
sobreposição, IDs repetidos ou casos selecionados sem lote bloqueiam a etapa.
Cada caso fica em um lote; suas linhas auxiliares acompanham esse caso. Os
totais dos lotes são reconciliados com as três tabelas selecionadas.

Esses lotes representam **chegada simulada**. `WEEK_NUM` e `date_decision` não
fornecem a data real de chegada de cada fonte. O arquivo `case_batches` é uma
atribuição persistida, não um CDC ou uma fonte oficial de eventos Home Credit.

O snapshot contém os 50 mil casos completos. F04 implementou a entrega
física/processamento dos lotes, revisões, duplicatas e atraso em namespace
separado, começando apenas com o primeiro intervalo. Um caso desse intervalo
foi retido com suas auxiliares para a chegada tardia. Execução e limites em
[Silver incremental](silver/INCREMENTAL.md). O rótulo final não é apresentado
como conhecido no instante original da decisão.

A coorte fica fixa para o experimento incremental: os lotes trazem partes dessa
mesma seleção. Não refazer a seleção global após cada chegada ou correção, pois
isso poderia trocar a população e confundir o efeito da alteração nos indicadores.

## 4. Execução e validação

```bash
bash scripts/project.sh -m src.pipelines.build_sample
```

O comando valida origem, materializa em staging, compara valores/multiplicidade
nos dois sentidos, valida o recorte, atribui lotes e só então publica o diretório
com manifesto. Não altera tipos, nomes de colunas ou valores das tabelas.

O manifesto `_selection.json` guarda relatórios completos de contrato para origem
e recorte, contagens, lotes, digests e checksums de saída. Relatórios por tentativa
ficam em `artifacts/samples/<run_id>.json`. Ambos estão fora do Git.

Uma reexecução confere identidade, checksums, conjunto de casos e integridade
da origem; se estiverem consistentes, reutiliza o artefato sem regravá-lo. Um
conteúdo alterado bloqueia a execução. Dados de uma escrita que falhou ficam
fora do diretório publicado; o staging da tentativa é removido ao tratar a falha.
Crash abrupto ainda pode deixar staging órfão para inspeção/limpeza posterior.

Um lock POSIX limita a um escritor no diretório de recortes. Publicação por
rename pressupõe filesystem local; F08 revisará essas garantias para objetos.

## 5. Uso posterior na Bronze

Não mudar `data.raw` para a pasta do recorte: a RAW original deve continuar
identificada e preservada. O carregador de paths impede sobreposição de camadas.
F02.3 implementou a entrada explícita com saídas separadas por seleção:

```bash
bash scripts/project.sh -m src.pipelines.run_bronze_mvp --sample 7d58bbdaa00cbabfbce54d26
```

Use o identificador retornado pelo construtor se for diferente. Detalhes e
limites em [BRONZE_DO_RECORTE.md](BRONZE_DO_RECORTE.md). O entrypoint exige uma
entrada explícita. A ingestão do snapshot não representa entrega dos três lotes
como incrementos; a reconciliação completa de valores continua em F02.6.

Resultados e identificadores atuais:
[evidência de contratos e recorte](evidencias/F00_CONTRATOS_RECORTE.md).
