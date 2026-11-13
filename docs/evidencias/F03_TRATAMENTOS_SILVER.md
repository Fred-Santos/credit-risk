# Evidência F03.3 — tratamentos com guarda de perda

Data: 12/11/2026. Python 3.11.14 / Spark 3.5.7, configuração local em UTC.
Escopo: funções executadas e validadas; nenhuma tabela Silver/Delta materializada.

## Identificação e execução

```bash
bash scripts/project.sh -m src.pipelines.check_silver_transforms \
  --sample 7d58bbdaa00cbabfbce54d26
bash scripts/project.sh -m unittest discover -s tests -p test_silver_transforms.py -v
bash scripts/project.sh scripts/run_tests.py --integration-required
```

Execução real: **`20261112T232900Z_56746a71`**, status `passed`.
Relatório privado: `artifacts/silver_transforms/20261112T232900Z_56746a71.json`.
Seleção `7d58bbdaa00cbabfbce54d26`; Bronze aprovada consumida:
`20261112T212249Z_a5a41ff3`. Gate antes/depois:
`3c3a3ac440a1e6b3c87d14a5d988476f5ca517a4245eefce8dab8434a06a8ecc`.

| Artefato | SHA-256 |
|---|---|
| src/silver/transforms.py | `f35a4bc30073bafbf39e6a735a0036048e4df5d9ab9c415883b18e88016812c8` |
| src/pipelines/check_silver_transforms.py | `2d1138a13348c0677e0c67ba9e238a6974f872ac27edda3d66f83f490f45fe0b` |
| src/silver/read_bronze.py | `cbdea63005553c26b07b9494ec500e131c584af9243b471279608b6568aab2fa` |
| Política executável | `ec07eb348542894caf9252c5f4e58c0e9486b47193f5ad113c2e2ddad1d076c9` |
| Contrato snapshot preservado | `091e65bbee8e1c0907dd9bf23cf9b07dae512f62c3ecd99935a53c728c722cb6` |

Código ainda sem commit desta entrega. Política vinculada também ao hash do
notebook revisado. A alteração de `implementation_status` da política reflete
a existência das funções; não representa publicação de tabelas.

## Esperado e obtido

Esperado: converter apenas as 23 datas, preservar nulos originais, nenhuma nova
perda de valor preenchido, mesmos tipos/valores nas demais colunas e nenhuma
linha adicionada, removida ou deduplicada.

| Tabela | Linhas | Datas | Células preenchidas convertidas | Células de data nulas preservadas | Novos nulos |
|---|---|---|---|---|---|
| train_base | 50.000 | 1 | 50.000 | 0 | 0 |
| train_static_0 | 50.000 | 15 | 305.208 | 444.792 | 0 |
| train_applprev_1 | 215.390 | 7 | 864.397 | 643.333 | 0 |

**315.390 linhas aceitas, zero descartadas.** As contagens de células não são
contagens de casos de crédito: uma linha pode ter várias datas.

Para cada tabela, o verificador restaurou somente a representação ISO string
das datas e comparou todas as colunas com a Bronze por `exceptAll` nos dois
sentidos. Resultado: zero faltas e zero excessos nas três tabelas. Isso confere
valores, multiplicidade, códigos, números, nulos e metadados, além das contagens.
Os schemas candidatos têm apenas as 23 mudanças de string para date.

Todas as ações ocorreram no contexto protegido do leitor, com revalidação de
entrada ao sair. Política, contrato e notebook foram conferidos novamente ao
terminar. RAW, recorte, Parquets Bronze e gate não foram reescritos.

## Falhas e testes

Oito testes novos em `tests/test_silver_transforms.py`:

- Política incompatível, destrutiva ou desvinculada do contrato/notebook bloqueia.
- Datas ausentes/duplicadas ou apontando para metadados bloqueiam a política.
- Data bissexta válida e null opcional preservam números, códigos, booleanos e metadados.
- Data impossível, vazio, espaços, formato abreviado e timestamp são rejeitados,
  com contagens, sob ANSI/CORRECTED, não ANSI/LEGACY e não ANSI/EXCEPTION.
- Dataset vazio e datas opcionais inteiramente nulas não criam perdas fictícias.
- Uma tabela inválida bloqueia o snapshot inteiro, mesmo depois de outra passar.
- Prova detecta número alterado, linha removida e booleano null preenchido com false.
- Schema incompatível e timezone diferente de UTC exigem resolução explícita.

Fixtures sintéticas pequenas, sem dependência de Kaggle ou dados reais. A guarda
gera métricas antes de retornar o DataFrame e lança `SilverTransformError` se
um preenchido se tornaria null. O CLI registra a falha e retorna erro; nenhuma
linha é descartada e não há quarentena automática nesta versão.

Logs da sessão: `/tmp/credit-risk-tests-f033.log` e
`/tmp/credit-risk-silver-transforms-tests-final.log`. Suíte completa:
**100 testes aprovados em 196,556 s, nenhum ignorado**.
Os oito testes específicos passaram em 30,723 s,
incluindo o parser EXCEPTION usado por padrão nesta sessão.

## Aceite e trabalho restante

F03.3 aceita como tratamentos executáveis e validados. Manual em
[TRATAMENTOS.md](../silver/TRATAMENTOS.md). Política v1 preserva todas as demais
informações; não aprova mapas de sentinela, drops ou estreitamento numérico.

F03.4 ainda deve materializar as três tabelas Delta e registrar suas versões.
F03.5 fechará contratos do estado Silver e F03.6 a execução repetível. Datas
válidas não comprovam disponibilidade point-in-time dos atributos.
