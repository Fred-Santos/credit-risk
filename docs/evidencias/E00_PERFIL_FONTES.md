# E00 — Perfil completo das fontes de treino

Evidência gerada a partir de `artifacts/expansion/source_profiles.json`.
Dados de negócio não são exportados neste documento; todas as contagens são exatas.
As chaves abaixo são candidatas observadas, ainda sujeitas à definição semântica
em E03/E04. Ausência de duplicatas não prova identidade de contrato financeiro.

| Tabela | Linhas RAW | Linhas janeiro–setembro | Casos na janela | Chave candidata | Grupos duplicados | Casos órfãos |
|---|---:|---:|---:|---|---:|---:|
| `train_applprev_1` | 6,525,979 | 2,316,343 | 377,785 | case_id, num_group1 | 0 | 0 |
| `train_applprev_2` | 14,075,487 | 5,084,023 | 377,785 | case_id, num_group1, num_group2 | 0 | 0 |
| `train_base` | 1,526,659 | 447,305 | 447,305 | case_id | 0 | 0 |
| `train_credit_bureau_a_1` | 15,940,537 | 5,016,039 | 429,687 | case_id, num_group1 | 0 | 0 |
| `train_credit_bureau_a_2` | 188,298,452 | 74,277,008 | 429,550 | case_id, num_group1, num_group2 | 0 | 0 |
| `train_credit_bureau_b_1` | 85,791 | 36,557 | 14,544 | case_id, num_group1 | 0 | 0 |
| `train_credit_bureau_b_2` | 1,286,755 | 544,870 | 14,534 | case_id, num_group1, num_group2 | 0 | 0 |
| `train_debitcard_1` | 157,302 | 49,716 | 35,616 | case_id, num_group1 | 0 | 0 |
| `train_deposit_1` | 145,086 | 45,828 | 33,531 | case_id, num_group1 | 0 | 0 |
| `train_other_1` | 51,109 | 50,077 | 50,077 | case_id, num_group1 | 0 | 0 |
| `train_person_1` | 2,973,991 | 784,268 | 447,305 | case_id, num_group1 | 0 | 0 |
| `train_person_2` | 1,643,410 | 418,411 | 376,491 | case_id, num_group1, num_group2 | 0 | 0 |
| `train_static_0` | 1,526,659 | 447,305 | 447,305 | case_id | 0 | 0 |
| `train_static_cb_0` | 1,500,476 | 446,999 | 446,999 | case_id | 0 | 0 |
| `train_tax_registry_a_1` | 3,275,770 | 1,145,923 | 158,402 | case_id, num_group1 | 0 | 0 |
| `train_tax_registry_b_1` | 1,107,933 | 1,063,435 | 144,545 | case_id, num_group1 | 0 | 0 |
| `train_tax_registry_c_1` | 3,343,800 | 0 | 0 | case_id, num_group1 | 0 | 0 |

## Armazenamento e capacidade

- Entradas Parquet comprimidas: **1,328,440,801 bytes**.
- Column chunks descomprimidos, somados dos rodapés: **2,108,986,524 bytes**.
- Duração do perfil: **401.889 segundos**.

O tamanho descomprimido não representa memória de objetos Spark/Python nem
pico de disco; os chunks ainda usam codificação Parquet após descompressão.
Para planejamento inicial, adotar uma reserva de trabalho de
`max(64 GiB, 4 × column chunks descomprimidos + 2 × entradas comprimidas)`, arredondada para
cima e com folga adicional de 20%. O piso de 64 GiB é uma reserva operacional provisória, sem calibração de pico.
Essa é uma hipótese de orçamento para
materializações e temporários, não um limite superior garantido. Medir o fluxo
completo e a retenção para substituir essa hipótese em E01/E07.

Envelope inicial calculado: **76.80 GiB**, além dos dados já existentes.

## Limitações e encaminhamentos

O JSON contém tipos, nulos/NaNs por coluna, máximos de linhas por caso, cobertura
sobre a base completa, datas brutas e campos sem definição. Datas brutas não
comprovam validade, disponibilidade na decisão ou elegibilidade para ML.
A compatibilidade de schema foi conferida entre todos os shards de cada tabela.
Na execução, as 17 tabelas apresentaram zero nulos nas chaves candidatas, zero
grupos de chave duplicada e zero casos órfãos. Todos os campos de negócio
encontraram entrada no dicionário; isso não comprova clareza ou adequação temporal.

As relações entre níveis de histórico precisam de definição de negócio e
validação das chaves parentais antes dos joins Gold. Campos sem descrição devem
receber investigação ou exclusão explícita. Perfis e aquisição não equivalem
à aceitação de contratos Silver, nem demonstram capacidade de processamento e
publicação de todas as tabelas em conjunto.

Reprodução:

```bash
bash scripts/project.sh -m scripts.acquire_expansion
bash scripts/project.sh scripts/measure_resources.py --output artifacts/expansion/profile_resources.json --workdir .runtime/tmp -- .venv/bin/python -m scripts.profile_expansion_sources
bash scripts/project.sh -m scripts.summarize_expansion_profile
```

O perfil usou o heap atual de 2 GB. A memória visível no Linux/WSL foi cerca de
15 GiB. Aplicar o perfil de 8 GB e avaliar folga em E01; aumentos para 12/16 GB
não são seguros por pressuposto nesse limite da VM. A medição RSS soma a árvore
de processos e pode contar páginas compartilhadas mais de uma vez.

Pico RSS amostrado da árvore: **2.81 GiB**. A medição de disco cobre somente `.runtime/tmp`; o Spark pode usar `/tmp`, portanto não comprova pico total.

## Integridade

- `source_profiles.json`: SHA-256 `912aed16de44b0822870d65c8c185b845cd0f8fd018ff584e9aefc06b5f82498`.
- `profile_resources.json`: SHA-256 `9e53d5c237afc190b582223738365b6dbf0da4cedacf8b7930f58e988b01ae85`.
- `host_capacity.json`: SHA-256 `063020e1137a354c1167cdf6f00c8c28b8e0cee5c5d644cc577ca05af4a2dbbb`.
- `acquisition.json`: SHA-256 `ae0467e3e58c526b7de5c6d95533e4fa8792df1d2f5b2ad2d52b4cff9307533a`.
