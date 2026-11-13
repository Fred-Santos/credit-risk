# Evidência F03.2 — carregamento lógico da Bronze aprovada

Data: 12/11/2026. Runtime local: Python 3.11.14 e Spark 3.5.7.
Seleção `7d58bbdaa00cbabfbce54d26`. Leitura sem casts, tratamentos ou escrita
de tabelas Silver. Dados originais, recorte e Parquets Bronze preservados.

## Implementação e comandos

API: `src/silver/read_bronze.py`, função `open_bronze_snapshot`.
Manual: [LEITURA_BRONZE.md](../silver/LEITURA_BRONZE.md).

```bash
bash scripts/project.sh -m src.pipelines.check_silver_input \
  --sample 7d58bbdaa00cbabfbce54d26
bash scripts/project.sh -m unittest discover -s tests -p test_silver_input.py -v
bash scripts/project.sh scripts/run_tests.py --integration-required
```

O contexto valida o gate e mantém o lock do produtor durante as ações Spark.
Lê apenas tabelas/batches/arquivos explicitamente identificados, valida cada
schema antes da união e exige chaves únicas/não nulas no conjunto global.
Confere a publicação novamente na saída normal. O CLI escreve relatório de
sucesso somente depois dessa conferência e registra falhas sem alterar o gate
do produtor. Não existe publicação Silver nesta etapa.

## Resultado real

Run final: **`20261112T214501Z_eefc5fdc`**, status `passed`.
Publicação Bronze consumida: `20261112T212249Z_a5a41ff3`.
Relatório privado: `artifacts/silver_input/20261112T214501Z_eefc5fdc.json`.

| Tabela | Linhas validadas e consumidas | Colunas com metadados | Fragmentos |
|---|---|---|---|
| train_base | 50.000 | 9 | 1 |
| train_static_0 | 50.000 | 172 | 1 |
| train_applprev_1 | 215.390 | 45 | 1 |

Total: 315.390 linhas. Tipos e valores preservados; chaves validadas no grão
de cada tabela. Há 214 campos de negócio e quatro metadados por tabela. Os
shards originais já haviam sido consolidados no recorte; o leitor não volta
a procurar arquivos RAW por prefixo.

O recibo registra hashes do gate, contrato, execução, qualidade, reconciliação
e lineage, além de batches e contagens. O hash do gate é o mesmo da entrada
Bronze aprovada, sem revalidação/gravação do produtor por este consumidor.

| Artefato | SHA-256 |
|---|---|
| Gate consumido | `3c3a3ac440a1e6b3c87d14a5d988476f5ca517a4245eefce8dab8434a06a8ecc` |
| `src/silver/read_bronze.py` | `cbdea63005553c26b07b9494ec500e131c584af9243b471279608b6568aab2fa` |
| `src/pipelines/check_silver_input.py` | `04aa5eb72035eedf017c6058cae004701861da08a00b062e65aaf188b270cab9` |

Código ainda sem commit desta entrega; os hashes identificam a versão executada.

## Testes

Nove testes em `tests/test_silver_input.py`, com fixtures sintéticas reais de
Spark e filesystem, sem Kaggle:

- Leitura válida preserva valores e nulos; lock impede escritor e é liberado
  depois do consumo.
- Gate ausente bloqueia.
- Arquivo extra ou removido bloqueia inventário exato.
- Relatório alterado e gate reprovado bloqueiam.
- Seleção errada e path fora do namespace bloqueiam.
- Mudança do YAML exige nova aprovação Bronze.
- Mudança de gate durante o consumo reprova a saída do contexto.
- Duplicata entre dois fragmentos bloqueia após união global.
- Coluna ausente em um fragmento falha antes da união, sem preenchimento por null.

Os dois últimos testes constroem um envelope de hashes coerente para isolar a
validação independente de schema/chave. Não representam uma revalidação
legítima pela Bronze nem demonstram resistência a adulteração coordenada.

Nove testes específicos aprovados em 20,453 s. Suíte completa da versão final:
**92 testes aprovados em 115,478 s, nenhum ignorado**. Logs da sessão:
`/tmp/credit-risk-silver-input-tests-final.log` e `/tmp/credit-risk-tests-f032.log`.

## Aceite e limites

F03.2 aceita no modo de recorte explícito aprovado. Não atende ao modo RAW
legado nem ao histórico de eventos; esses grãos não são intercambiáveis.
Paths são locais; o lock é exclusivo, não bloqueante e depende da cooperação
dos programas. O chamador deve executar suas ações dentro do `with`.

Próxima entrega: F03.3, tratamentos e guardas de conversão definidos no catálogo.
Materialização Delta, contratos de saída e execução Silver repetível continuam
em F03.4–F03.6. Nenhum item posterior é aceito por esta leitura.
