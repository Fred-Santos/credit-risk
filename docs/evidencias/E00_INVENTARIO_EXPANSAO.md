# E00 — Inventário inicial e populações de 2020

Data de referência: 18/11/2026. Estado: E00.1 e E00.3 concluídos; E00.2 e E00.4 pendentes.

## Execução e reprodução

Consulta autenticada ao catálogo Kaggle, com paginação completa: **138 arquivos**
remotos. Seleção por diretório de treino e formato Parquet: **17 tabelas lógicas,
32 arquivos, 1.328.440.801 bytes** (aproximadamente 1,24 GiB). O dicionário tem
34.047 bytes. CSVs equivalentes e arquivos oficiais de teste ficam fora da seleção.
Nenhum arquivo de dados novo foi adquirido nesta etapa.

```bash
bash scripts/project.sh scripts/inventory_home_credit_remote.py
bash scripts/project.sh -m scripts.profile_expansion_populations
```

Catálogo versionado: [home_credit_expansion_catalog.yaml](../../configs/home_credit_expansion_catalog.yaml).
Evidências locais: `artifacts/expansion/remote_files.json` e
`artifacts/expansion/populations.json`. Os timestamps UTC nesses arquivos podem
corresponder ao dia seguinte à data local de referência.

A contagem Spark leu a `train_base` RAW completa, sem amostragem, usando o perfil
existente de 2 GB. Não houve alteração de Spark nem escrita nas tabelas do MVP.
Rede externa e sockets locais da JVM exigiram execução fora do sandbox restrito.
A execução aprovada terminou com sucesso; isso não mede a capacidade da expansão.

## Fontes

Os nomes lógicos consolidam os shards finais após o nível `_0`, `_1` ou `_2`.
Esse agrupamento por nome não comprova equivalência de schema ou semântica:
essas verificações pertencem a E00.2.

| Tabela | Arquivos | Bytes remotos | Arquivos já locais |
|---|---:|---:|---:|
| `train_applprev_1` | 2 | 179,812,569 | 2 |
| `train_applprev_2` | 1 | 28,484,608 | 0 |
| `train_base` | 1 | 7,048,047 | 1 |
| `train_credit_bureau_a_1` | 4 | 443,436,755 | 0 |
| `train_credit_bureau_a_2` | 11 | 327,408,412 | 0 |
| `train_credit_bureau_b_1` | 1 | 4,506,882 | 0 |
| `train_credit_bureau_b_2` | 1 | 2,067,641 | 0 |
| `train_debitcard_1` | 1 | 1,188,384 | 0 |
| `train_deposit_1` | 1 | 1,598,148 | 0 |
| `train_other_1` | 1 | 805,374 | 0 |
| `train_person_1` | 1 | 43,892,239 | 0 |
| `train_person_2` | 1 | 7,559,249 | 0 |
| `train_static_0` | 2 | 188,549,765 | 2 |
| `train_static_cb_0` | 1 | 30,654,579 | 0 |
| `train_tax_registry_a_1` | 1 | 21,687,764 | 0 |
| `train_tax_registry_b_1` | 1 | 9,915,038 | 0 |
| `train_tax_registry_c_1` | 1 | 29,825,347 | 0 |

## Populações medidas

| População | Casos | Target 1 | Target 0 | Rótulos inválidos |
|---|---:|---:|---:|---:|
| Desenvolvimento: janeiro–maio | 259,695 | 10,643 | 249,052 | 0 |
| Reserva temporal: junho–setembro | 187,610 | 4,114 | 183,496 | 0 |
| Público: janeiro–setembro | 447,305 | 14,757 | 432,548 | 0 |

A base completa tem 1.526.659 casos e igual número de chaves distintas.
As três populações também têm igualdade entre contagem e chaves distintas.
As datas extremas coincidem com os limites previstos, incluindo 31/05 e 30/09.
A soma de desenvolvimento e reserva é igual à população de público. Os filtros
semiabertos e a unicidade global asseguram disjunção dos casos entre as duas janelas.
Há registros em todos os nove meses; as contagens mensais estão no JSON local.
Os rótulos foram contados para inventário, sem seleção de atributos ou ajuste de modelo.

## Dependências e capacidade ainda pendentes

A classificação inicial por nível do nome orienta o levantamento, mas não define
chave: investigar `case_id`, índices de grupo, relações entre níveis, cobertura,
órfãos, duplicatas, tipos e disponibilidade temporal para cada tabela nova.
A atribuição de nomes não substitui o dicionário e a inspeção dos dados.

Os 1,24 GiB são somente entradas comprimidas de treino. Não constituem estimativa
para Silver/Gold, RAM ou disco máximo. Havia aproximadamente 945 GiB livres no
filesystem no levantamento inicial. Faltam medir expansão, shuffle, temporários,
cópias de publicação e versões para fechar E00.4 e E01.

Próximo passo: inspecionar o dicionário e preparar a aquisição das fontes ausentes
necessárias ao perfil completo E00.2, com journal/checksums do downloader existente.
A aquisição de apoio ao inventário deve ser registrada também em E02, evitando
baixar ou sobrescrever arquivos novamente. Reestimar esforço após fechar o perfil.

## Integridade das evidências locais

- `artifacts/expansion/remote_files.json`: SHA-256 `996501204847fec92bacc056fc0a35f8a18af49692879aacd4a4feb3e0873eb5`.
- `artifacts/expansion/populations.json`: SHA-256 `b809e9092a8ba3fd243d90181aaf3e60515bc2ea6824b46ec9880747482e0f4a`.

## Continuação

O [perfil completo](E00_PERFIL_FONTES.md) concluiu E00.2/E00.4.
A [aquisição de apoio](E02_AQUISICAO_EXPANSAO.md) acrescentou as fontes ausentes
sem alterar as tabelas publicadas do MVP. As pendências acima refletem o levantamento inicial.
