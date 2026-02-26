# Dataset lineage (RAW)

- Run ID: 20260223T175139Z_1bc1491e

- Started (UTC): 2026-02-23T17:51:39.648307+00:00


## Fluxo

- **Input:** kaggle://home-credit-credit-risk-model-stability

- **Output (raw):** `data/raw`


## Artefatos

- JSON do evento: `docs/lineage/lineage_events/20260223T175139Z_1bc1491e_raw_lineage.json`

- Arquivos em raw: 34


## Lista (top 50)

- `data/raw/feature_definitions.csv` (34047 bytes)
- `data/raw/parquet_files/train/train_applprev_1_0.parquet` (106951598 bytes)
- `data/raw/parquet_files/train/train_applprev_1_1.parquet` (72860971 bytes)
- `data/raw/parquet_files/train/train_applprev_2.parquet` (28484608 bytes)
- `data/raw/parquet_files/train/train_base.parquet` (7048047 bytes)
- `data/raw/parquet_files/train/train_credit_bureau_a_1_0.parquet` (64863053 bytes)
- `data/raw/parquet_files/train/train_credit_bureau_a_1_1.parquet` (183293106 bytes)
- `data/raw/parquet_files/train/train_credit_bureau_a_1_2.parquet` (123506425 bytes)
- `data/raw/parquet_files/train/train_credit_bureau_a_1_3.parquet` (71774171 bytes)
- `data/raw/parquet_files/train/train_credit_bureau_a_2_0.parquet` (5786632 bytes)
- `data/raw/parquet_files/train/train_credit_bureau_a_2_1.parquet` (10006927 bytes)
- `data/raw/parquet_files/train/train_credit_bureau_a_2_10.parquet` (7646586 bytes)
- `data/raw/parquet_files/train/train_credit_bureau_a_2_2.parquet` (30669743 bytes)
- `data/raw/parquet_files/train/train_credit_bureau_a_2_3.parquet` (47836939 bytes)
- `data/raw/parquet_files/train/train_credit_bureau_a_2_4.parquet` (49233367 bytes)
- `data/raw/parquet_files/train/train_credit_bureau_a_2_5.parquet` (60984109 bytes)
- `data/raw/parquet_files/train/train_credit_bureau_a_2_6.parquet` (45183113 bytes)
- `data/raw/parquet_files/train/train_credit_bureau_a_2_7.parquet` (14137608 bytes)
- `data/raw/parquet_files/train/train_credit_bureau_a_2_8.parquet` (23832969 bytes)
- `data/raw/parquet_files/train/train_credit_bureau_a_2_9.parquet` (32090419 bytes)
- `data/raw/parquet_files/train/train_credit_bureau_b_1.parquet` (4506882 bytes)
- `data/raw/parquet_files/train/train_credit_bureau_b_2.parquet` (2067641 bytes)
- `data/raw/parquet_files/train/train_debitcard_1.parquet` (1188384 bytes)
- `data/raw/parquet_files/train/train_deposit_1.parquet` (1598148 bytes)
- `data/raw/parquet_files/train/train_other_1.parquet` (805374 bytes)
- `data/raw/parquet_files/train/train_person_1.parquet` (43892239 bytes)
- `data/raw/parquet_files/train/train_person_2.parquet` (7559249 bytes)
- `data/raw/parquet_files/train/train_static_0_0.parquet` (113858592 bytes)
- `data/raw/parquet_files/train/train_static_0_1.parquet` (74691173 bytes)
- `data/raw/parquet_files/train/train_static_cb_0.parquet` (30654579 bytes)
- `data/raw/parquet_files/train/train_tax_registry_a_1.parquet` (21687764 bytes)
- `data/raw/parquet_files/train/train_tax_registry_b_1.parquet` (9915038 bytes)
- `data/raw/parquet_files/train/train_tax_registry_c_1.parquet` (29825347 bytes)
- `data/raw/sample_submission.csv` (114 bytes)

## Dataset lineage BRONZE
- Run ID: 20260225T235656Z_12a5a9fa
- Started UTC: 2026-02-25T23:56:56.388991+00:00
- Git commit: dce7491d90d8fcf17f960cdae318e3bf2c526218

### Fluxo
- Input: data/raw/parquet_files/train
- Output: data/bronze

### Artefatos
- JSON do evento: docs/lineage/lineage_events/20260225T235656Z_12a5a9fa_bronze_lineage.json
- Arquivos em bronze: 10

### Lista top 50
- data/bronze/train_root/._SUCCESS.crc (8 bytes)
- data/bronze/train_root/.part-00000-1b468f29-be0d-46b0-be84-6a2f64f5ffbe-c000.snappy.parquet.crc (2237608 bytes)
- data/bronze/train_root/.part-00000-433a2dc7-132f-44e8-8906-b4b38052d963-c000.snappy.parquet.crc (3291428 bytes)
- data/bronze/train_root/.part-00000-5ff4f360-39ce-4f75-937e-b858858461e5-c000.snappy.parquet.crc (368492 bytes)
- data/bronze/train_root/.part-00000-d21dd195-9ba9-48a5-94fd-034eb5da9946-c000.snappy.parquet.crc (139724 bytes)
- data/bronze/train_root/_SUCCESS (0 bytes)
- data/bronze/train_root/part-00000-1b468f29-be0d-46b0-be84-6a2f64f5ffbe-c000.snappy.parquet (286412442 bytes)
- data/bronze/train_root/part-00000-433a2dc7-132f-44e8-8906-b4b38052d963-c000.snappy.parquet (421301314 bytes)
- data/bronze/train_root/part-00000-5ff4f360-39ce-4f75-937e-b858858461e5-c000.snappy.parquet (47165592 bytes)
- data/bronze/train_root/part-00000-d21dd195-9ba9-48a5-94fd-034eb5da9946-c000.snappy.parquet (17883144 bytes)

## Dataset lineage BRONZE
- Run ID: 20260226T010510Z_b4c8535c
- Started UTC: 2026-02-26T01:05:10.282273+00:00
- Git commit: dce7491d90d8fcf17f960cdae318e3bf2c526218

### Fluxo
- Input: data/raw/parquet_files/train
- Output: data/bronze

### Artefatos
- JSON do evento: docs/lineage/lineage_events/20260226T010510Z_b4c8535c_bronze_lineage.json
- Arquivos em bronze: 128

### Lista top 50
- data/bronze/train_applprev_1_0/._SUCCESS.crc (8 bytes)
- data/bronze/train_applprev_1_0/.part-00000-7bfadc89-a55d-47c4-b88d-2e48141fa6db-c000.snappy.parquet.crc (837800 bytes)
- data/bronze/train_applprev_1_0/_SUCCESS (0 bytes)
- data/bronze/train_applprev_1_0/part-00000-7bfadc89-a55d-47c4-b88d-2e48141fa6db-c000.snappy.parquet (107237353 bytes)
- data/bronze/train_applprev_1_1/._SUCCESS.crc (8 bytes)
- data/bronze/train_applprev_1_1/.part-00000-0167deed-13cd-4e1c-a532-cf7d1e0447b5-c000.snappy.parquet.crc (567568 bytes)
- data/bronze/train_applprev_1_1/_SUCCESS (0 bytes)
- data/bronze/train_applprev_1_1/part-00000-0167deed-13cd-4e1c-a532-cf7d1e0447b5-c000.snappy.parquet (72647232 bytes)
- data/bronze/train_applprev_2/._SUCCESS.crc (8 bytes)
- data/bronze/train_applprev_2/.part-00000-0f6eba77-e119-499a-91ee-88adfb22e1e9-c000.snappy.parquet.crc (287492 bytes)
- data/bronze/train_applprev_2/_SUCCESS (0 bytes)
- data/bronze/train_applprev_2/part-00000-0f6eba77-e119-499a-91ee-88adfb22e1e9-c000.snappy.parquet (36797467 bytes)
- data/bronze/train_base/._SUCCESS.crc (8 bytes)
- data/bronze/train_base/.part-00000-936f09c4-0fe8-4d6e-aa26-39467eb98fc2-c000.snappy.parquet.crc (51408 bytes)
- data/bronze/train_base/_SUCCESS (0 bytes)
- data/bronze/train_base/part-00000-936f09c4-0fe8-4d6e-aa26-39467eb98fc2-c000.snappy.parquet (6578922 bytes)
- data/bronze/train_credit_bureau_a_1_0/._SUCCESS.crc (8 bytes)
- data/bronze/train_credit_bureau_a_1_0/.part-00000-95dfae4e-1bef-40a7-bcdc-b143f94e6b6c-c000.snappy.parquet.crc (597764 bytes)
- data/bronze/train_credit_bureau_a_1_0/_SUCCESS (0 bytes)
- data/bronze/train_credit_bureau_a_1_0/part-00000-95dfae4e-1bef-40a7-bcdc-b143f94e6b6c-c000.snappy.parquet (76512455 bytes)
- data/bronze/train_credit_bureau_a_1_1/._SUCCESS.crc (8 bytes)
- data/bronze/train_credit_bureau_a_1_1/.part-00000-f7601e62-ed7f-4c39-b2b6-b1deab80e616-c000.snappy.parquet.crc (1466456 bytes)
- data/bronze/train_credit_bureau_a_1_1/_SUCCESS (0 bytes)
- data/bronze/train_credit_bureau_a_1_1/part-00000-f7601e62-ed7f-4c39-b2b6-b1deab80e616-c000.snappy.parquet (187705071 bytes)
- data/bronze/train_credit_bureau_a_1_2/._SUCCESS.crc (8 bytes)
- data/bronze/train_credit_bureau_a_1_2/.part-00000-ace2b1fc-bdb1-414f-9e5e-e8bdaed9423a-c000.snappy.parquet.crc (986864 bytes)
- data/bronze/train_credit_bureau_a_1_2/_SUCCESS (0 bytes)
- data/bronze/train_credit_bureau_a_1_2/part-00000-ace2b1fc-bdb1-414f-9e5e-e8bdaed9423a-c000.snappy.parquet (126317203 bytes)
- data/bronze/train_credit_bureau_a_1_3/._SUCCESS.crc (8 bytes)
- data/bronze/train_credit_bureau_a_1_3/.part-00000-56e5ddb5-ed06-4a9f-9e64-d6e93dbf7413-c000.snappy.parquet.crc (571096 bytes)
- data/bronze/train_credit_bureau_a_1_3/_SUCCESS (0 bytes)
- data/bronze/train_credit_bureau_a_1_3/part-00000-56e5ddb5-ed06-4a9f-9e64-d6e93dbf7413-c000.snappy.parquet (73098903 bytes)
- data/bronze/train_credit_bureau_a_2_0/._SUCCESS.crc (8 bytes)
- data/bronze/train_credit_bureau_a_2_0/.part-00000-1e4dbd2f-628f-4a4c-becf-d19336ca581e-c000.snappy.parquet.crc (52596 bytes)
- data/bronze/train_credit_bureau_a_2_0/_SUCCESS (0 bytes)
- data/bronze/train_credit_bureau_a_2_0/part-00000-1e4dbd2f-628f-4a4c-becf-d19336ca581e-c000.snappy.parquet (6731224 bytes)
- data/bronze/train_credit_bureau_a_2_1/._SUCCESS.crc (8 bytes)
- data/bronze/train_credit_bureau_a_2_1/.part-00000-8f474bff-e765-4dec-a427-a8fdafb570b1-c000.snappy.parquet.crc (91352 bytes)
- data/bronze/train_credit_bureau_a_2_1/_SUCCESS (0 bytes)
- data/bronze/train_credit_bureau_a_2_1/part-00000-8f474bff-e765-4dec-a427-a8fdafb570b1-c000.snappy.parquet (11691755 bytes)
- data/bronze/train_credit_bureau_a_2_10/._SUCCESS.crc (8 bytes)
- data/bronze/train_credit_bureau_a_2_10/.part-00000-f2c385f9-145c-4cde-92cf-8c41b503aa51-c000.snappy.parquet.crc (69828 bytes)
- data/bronze/train_credit_bureau_a_2_10/_SUCCESS (0 bytes)
- data/bronze/train_credit_bureau_a_2_10/part-00000-f2c385f9-145c-4cde-92cf-8c41b503aa51-c000.snappy.parquet (8936878 bytes)
- data/bronze/train_credit_bureau_a_2_2/._SUCCESS.crc (8 bytes)
- data/bronze/train_credit_bureau_a_2_2/.part-00000-92d23ac7-1586-4e4b-8dad-78e033c2d435-c000.snappy.parquet.crc (417520 bytes)
- data/bronze/train_credit_bureau_a_2_2/_SUCCESS (0 bytes)
- data/bronze/train_credit_bureau_a_2_2/part-00000-92d23ac7-1586-4e4b-8dad-78e033c2d435-c000.snappy.parquet (53441180 bytes)
- data/bronze/train_credit_bureau_a_2_3/._SUCCESS.crc (8 bytes)
- data/bronze/train_credit_bureau_a_2_3/.part-00000-1631a2f3-cf55-4860-8469-0860b4a6e9ac-c000.snappy.parquet.crc (476680 bytes)
- ... 78 arquivos
