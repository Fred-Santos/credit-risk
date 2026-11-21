# E02 — Seleção temporal e Bronze expandida

Data de referência: 18/11/2026. Estado: E02.3/E02.4 aceitos.

Política: [temporal_policy_v1.yaml](../../configs/temporal_policy_v1.yaml).
Snapshot: `a728cbc74ed5507307b398a5` em `data/bronze/expansion/a728cbc74ed5507307b398a5/`.
Esse namespace é independente da Bronze do MVP e não altera Silver, Gold ou CURRENT.

## População e preservação

A base completa tem **1,526,659 casos**.
A seleção pública contém **447,305 casos**;
**1,079,354** ficam fora da janela.
São **259,695** no desenvolvimento
(janeiro–maio) e **187,610** na reserva
(junho–setembro). Os intervalos são semiabertos e incluem 31/05 e 30/09.
Não existe limite de 50 mil ou amostragem na nova política.

Somente a `date_decision` da base determina os casos. Auxiliares passam por
`left_semi` em `case_id`; todas as observações desses casos são preservadas,
independentemente de suas datas. Isso inclui registros anteriores a janeiro e
posteriores a setembro. A Bronze preserva o snapshot retrospectivo; elegibilidade
para ML e disponibilidade temporal serão investigadas em E04.

## Reconciliação e proveniência

Cada tabela foi escrita sem casts de negócio e comparada diretamente à RAW
selecionada, com `exceptAll` nos dois sentidos e mesmos tipos/ordem de colunas.
A comparação inclui todos os campos originais e `_source_file`, `_selection_id`,
`_run_id`, `_ingested_at_utc`. Assim, preserva multiplicidade, nulos, valores
e proveniência, sem substituir igualdade por contagens ou hashes de linhas.
Todos os arquivos de saída têm SHA-256 registrado no manifesto.

As contagens foram também confrontadas com E00, executada por rotina independente.

| Tabela | Linhas Bronze | Fora da janela de casos (linhas RAW) | Diferenças nos dois sentidos |
|---|---:|---:|---:|
| `train_applprev_1` | 2,316,343 | 4,209,636 | 0 / 0 |
| `train_applprev_2` | 5,084,023 | 8,991,464 | 0 / 0 |
| `train_base` | 447,305 | 1,079,354 | 0 / 0 |
| `train_credit_bureau_a_1` | 5,016,039 | 10,924,498 | 0 / 0 |
| `train_credit_bureau_a_2` | 74,277,008 | 114,021,444 | 0 / 0 |
| `train_credit_bureau_b_1` | 36,557 | 49,234 | 0 / 0 |
| `train_credit_bureau_b_2` | 544,870 | 741,885 | 0 / 0 |
| `train_debitcard_1` | 49,716 | 107,586 | 0 / 0 |
| `train_deposit_1` | 45,828 | 99,258 | 0 / 0 |
| `train_other_1` | 50,077 | 1,032 | 0 / 0 |
| `train_person_1` | 784,268 | 2,189,723 | 0 / 0 |
| `train_person_2` | 418,411 | 1,224,999 | 0 / 0 |
| `train_static_0` | 447,305 | 1,079,354 | 0 / 0 |
| `train_static_cb_0` | 446,999 | 1,053,477 | 0 / 0 |
| `train_tax_registry_a_1` | 1,145,923 | 2,129,847 | 0 / 0 |
| `train_tax_registry_b_1` | 1,063,435 | 44,498 | 0 / 0 |
| `train_tax_registry_c_1` | 0 | 3,343,800 | 0 / 0 |

Total entre tabelas: **92,174,107 linhas**. Não é quantidade de casos únicos.

## Identidade, falha e reexecução

A identidade inclui política, catálogo lógico, fontes com SHA-256/tamanho,
versão Spark e hashes da implementação. O ID é derivado dessa identidade.
O journal da aquisição e todos os bytes RAW foram conferidos antes e depois da
materialização; nenhuma fonte foi sobrescrita. Catálogo e política ficam no manifesto.

O lock serializa escritores cooperantes. Tabelas são escritas em staging privado;
um rename no mesmo filesystem torna o snapshot visível somente após aprovação
das 17 tabelas e gravação do manifesto. Não há ativação por CURRENT nesta camada.
Staging de uma falha permanece privado para diagnóstico e não é consumível como
snapshot aprovado. A retomada cria staging novo e preserva o anterior.

A segunda execução reutilizou o mesmo snapshot após verificar fontes,
identidade, aprovação e checksums das saídas, sem reescrever as tabelas.
Uma alteração de conteúdo provoca recusa, não sobrescrita automática.
O teste de falha injetada demonstrou ausência de snapshot público e retry válido;
o teste de corrupção de Parquet demonstrou bloqueio da reexecução.

## Recursos e validação

Heap efetivo: **8 GiB**.
Tempo de materialização/reconciliação no manifesto:
**1782.517 s**; tempo do processo monitorado:
**1786.294 s**.
Pico RSS amostrado da árvore: **9.36 GiB**.
Pico de bytes lógicos no scratch configurado:
**4.97 GiB**.

RSS pode contar páginas compartilhadas e perder picos; o disco medido não inclui
os arquivos Bronze nem outros diretórios. Esta é uma execução Bronze real, não
validação do futuro processamento Silver/Gold completo. A configuração efetiva
fica no diretório de runtime apontado pelo resumo local.

**100 testes unitários e dois testes Spark de integração aprovados**, sem
ignorados. A suíte unitária inclui política temporal, configuração Spark,
catálogo e downloader. Os três testes do arquivo novo também passaram
por execução direta (a política é contabilizada na suíte unitária, sem duplicar
a contagem de cenários distintos). As fixtures cobrem as bordas de datas,
histórico antigo e futuro, nulos, preservação de multiplicidade, reuso, corrupção
e falha privada seguida de retry. Os testes Spark usam JVM de 2 GB; a execução
real verificou 8 GiB. Sockets locais exigiram execução fora do sandbox restrito.

```bash
bash scripts/project.sh -m unittest tests.test_expansion_bronze -q
bash scripts/project.sh scripts/run_tests.py --suite unit --integration-required --report artifacts/expansion/e02_unit_tests.json
bash scripts/project.sh -m scripts.build_expansion_bronze
bash scripts/project.sh -m scripts.build_expansion_bronze
bash scripts/project.sh -m scripts.summarize_expansion_bronze a728cbc74ed5507307b398a5
```

O monitor usado na primeira execução foi `scripts/measure_resources.py`, com
`--workdir .runtime/tmp/bronze-expansion`. Os recursos da reexecução ficam
separados em `bronze_replay_resources.json`.

## Evidências locais

- `data/bronze/expansion/a728cbc74ed5507307b398a5/_bronze.json`: SHA-256 `3fb0296dc62e3d7aa3f782855d2389e3b9fefeec4b743fe1d4b27bd74a4cc39e`.
- `artifacts/expansion/bronze/a728cbc74ed5507307b398a5.json`: SHA-256 `36d6df00f49e08495ab4bf93f05694174a7fbebb627c3eb93ac4ce41949c4125`.
- `artifacts/expansion/bronze/a728cbc74ed5507307b398a5-reused.json`: SHA-256 `f9b15ba60286d685ef548f24f713f8480bb58d5ad30a68be1dda666d252f5746`.
- `artifacts/expansion/bronze_build_resources.json`: SHA-256 `aae53d4b47e833a45b0d254655b5b4b7def9c2e6ab530c441ca3a39b5b338f37`.
- `artifacts/expansion/bronze_replay_resources.json`: SHA-256 `5413b515fa29c05596d516d982c5e5969a5286bd53dad3da30c3680e3540f270`.
- `artifacts/expansion/e02_unit_tests.json`: SHA-256 `e48742fcbd6c8fd90715e1b0b6f19eed557d8471a5ca5eee144f6bd800a8903b`.
- `artifacts/expansion/e02_bronze_tests.json`: SHA-256 `1c9ee61e342325617fc0194c9a97374c1f971542a02a597d1ff2b20e83e2fb68`.
- `artifacts/expansion/e02_code_checks.json`: SHA-256 `1f29b655d183ab08dd3f41d5e115ef4ca4499fc155f0db0de65557ca2d050d21`.
- `artifacts/expansion/e02_acceptance_mapping.json`: SHA-256 `a7520337e1bdb00893ce115ed17e38acc1f867ef6fcbbb633cbdcc04d95fcaff`.
