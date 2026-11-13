# Evidência F03.1 — catálogo e revisão das regras Silver

Data: 12/11/2026. Python 3.11.14 / Spark 3.5.7 no runtime local isolado.
Não houve alteração do notebook, RAW, recorte ou dados Bronze. Não há tabela
Silver materializada nesta entrega.

## Entrada e identificação

- Seleção: `7d58bbdaa00cbabfbce54d26`.
- Bronze aprovada: `20261112T212249Z_a5a41ff3`.
- Inspeção final: `20261112T213020Z_c4063c1a`, status `passed`.
- Relatório privado: `artifacts/silver_rule_review/20261112T213020Z_c4063c1a.json`.
- Notebook SHA-256: `350aa226f0fbed8851d1f86cf13d23b41a2ab66c5afc953922b4f8dbcf35111e`.
- Código `src/profiling/inspect_silver_candidates.py`: `58624e7f0609948238c673809c53058648f5cd52fe8909f55dc5b344408eb8a4`.
- Política planejada: `bd73ac1425e60209063198c8629423585784a6ce8fee0151640cba0636fbc124`.
- Inventário revisado: `44c2e5b39f94ed8fa45934ef9b52dc3201b1448a8152f6bf362350187b15f7ca`.

Código ainda sem commit desta entrega. Catálogo em
[CATALOGO_REGRAS_SILVER.md](../silver/CATALOGO_REGRAS_SILVER.md), política em
[silver_policy_v1.yaml](../../configs/silver_policy_v1.yaml) e inventário em
[INVENTARIO_NOTEBOOK.json](../silver/INVENTARIO_NOTEBOOK.json).

## Procedimento reproduzível

```bash
bash scripts/project.sh -m src.profiling.inspect_silver_candidates \
  --sample 7d58bbdaa00cbabfbce54d26
bash scripts/project.sh scripts/run_tests.py --integration-required
```

O inspetor confere gate, vínculo de entrada, hashes dos relatórios de qualidade
e reconciliação e checksums de saída. Lê schemas de negócio da Bronze e mede
hipóteses em blocos de 12 colunas. Confere a entrada, o gate, os arquivos e o
notebook novamente ao terminar. O único resultado persistido é um relatório
de diagnóstico, sem transformar ou regravar linhas reais.

O catálogo inclui todas as 236 células, 17 tabelas lógicas, 554 propostas por
campo e 223 propostas do MVP. A lista de campos do MVP corresponde aos 214
campos de negócio do contrato e três metadados por tabela. O catálogo acrescenta
a necessidade de preservar `ingest_batch`, ausente das análises originais.
Propostas das 14 tabelas fora do MVP ficam adiadas, sem ampliar aquisição.

## Expectativas e resultados

Base/estática com 50.000 linhas e histórico com 215.390 foram inspecionados.
Todas as 23 colunas de datas tiveram zero strings preenchidas ilegíveis/não ISO.
Os quatro candidatos double → int do histórico e os 64 da estática tiveram zero
frações e zero valores fora de int32 no recorte. Isso é evidência de conversão
representacional possível nesta amostra, não obrigação de reduzir tipos.

Confirmaram-se ocorrências de valores sondados, nulos e formatos alternativos.
Essas ocorrências não provaram sentinelas inválidas. As dez candidatas a drop
tinham um valor distinto preenchido; nove também tinham nulos. A evidência
detalhada e contagens representativas estão no catálogo.

Nove células markdown têm exemplos Python sintaticamente incompletos. Nenhum
bloco foi executado como transformação. Decisões: planejar casts de datas com
guarda de perda; preservar números, tipos numéricos, colunas, códigos, nulos,
booleanos e grãos; não implementar sentinelas por aparência. Joins para ABT
permanecem posteriores à agregação do histórico ao grão correto.

## Testes e aceite

Três testes novos em `tests/test_silver_rule_review.py`: sondagem numérica sem
alteração de valores; métricas definidas para dataset vazio; separação entre
nulos, constante preenchida, data inválida, formatos e booleanos. Usam apenas
fixtures sintéticas pequenas. **83 testes aprovados em 114,004 s, nenhum
ignorado**, incluindo as integrações existentes. Log da sessão:
`/tmp/credit-risk-tests-f031.log`.

F03.1 aceita como catálogo e revalidação de hipóteses. A política é declarativa
e ainda não é consumida por um transformador Silver. F03.2 construirá o leitor
lógico, seguido de tratamentos, materialização Delta, contratos e execução.
Não inferir disponibilidade point-in-time das features nem generalizar o perfil
do recorte para todos os casos da fonte.
