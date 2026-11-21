# E05 — Duas ABTs retrospectivas e reserva temporal

Estado: E05.1–E05.4 aceitos. Pacote `363ce1dd9aec8f446a69eb1b`, pinado à Silver `ef9c66b2a9d86511bcb8d3d5`.
Não há ativação CURRENT/S3 ampliada nesta fase; isso permanece na E07.

| ABT composta | Casos | Janela |
|---|---:|---|
| Desenvolvimento | 259,695 | 01/01–31/05/2020 |
| Avaliação temporal | 187,610 | 01/06–30/09/2020 |

Cada produto tem features Delta de **170 colunas** e labels Delta com somente
`case_id/target`. A ABT lógica reconstruída possui **171 colunas**, com schema
comum aos dois períodos. As labels da reserva ficam separadas fisicamente das
features; nenhum atributo contém target ou parâmetro ajustado com a reserva.

Os **16 blocos** passaram por oráculo SQL independente, incluindo contagens,
presença, ponderação hierárquica e categorias. Na comparação numérica agregada
admite-se 1e-8 absoluto mais 1e-10 relativo; contagens/datas/categorias e readback
exigem igualdade. Os joins preservaram uma linha por caso. As populações
coincidem com filtros SQL na Silver; a interseção é **zero** e a união contém
**447.305 casos**. Rótulos, tipos e todas as features foram relidos e conferidos.
A reexecução confirmou reuso do mesmo pacote, sem reescrita.
O manifesto inclui pins de todas as fontes, contrato, política, limites,
contagens, rótulos e lista de elegibilidade. `eligible_predictors=[]`;
**nenhum modelo foi treinado** e a aprovação temporal continua pendente.

`open_abt` retorna features sem target. Juntar labels de avaliação exige dois
argumentos explícitos. `open_ml_inputs` recusa treino enquanto a evidência
histórica e a maturação não forem comprovadas. São guardas da API, não uma
promessa de impedir acesso direto do proprietário aos arquivos locais.
A fixture exercitou essas recusas e a leitura autorizada com schema equivalente.

| Medição Gold | Resultado |
|---|---:|
| Processo completo | 221.888 s |
| Pico RSS da árvore | 5.11 GiB |
| Pico de temporários medidos | 0.18 GiB |

Validação desta entrega: **101 unitários e sete verificações adicionais**
(seis Spark e um wrapper Delta com cenário integrado), todos aprovados e sem
skips. O relatório direto de oito testes repete a guarda unitária de leitores;
essa repetição não é contada duas vezes. O catálogo completo é conferido
estaticamente; não se declara que todos os testes históricos foram reexecutados.

```bash
bash scripts/project.sh -m scripts.run_expansion gold --silver-id ef9c66b2a9d86511bcb8d3d5
bash scripts/project.sh -m unittest tests.test_expansion_stages tests.test_expansion_revision_delta -q
bash scripts/project.sh scripts/run_tests.py --suite unit --integration-required --report artifacts/expansion/e03_e05_unit_tests.json
```

## Manifestos e evidências locais

- `data/silver/expansion/ef9c66b2a9d86511bcb8d3d5/_silver.json`: SHA-256 `04cb9f15b0b0adec9bf04fe970298d5a0761fb93d7e57836453b851b8aa1d2a5`.
- `data/gold/expansion/363ce1dd9aec8f446a69eb1b/_gold.json`: SHA-256 `d94019b656a8b009a3a12312d62520f74b227e8fbb5aff8b770a48c70bfbe708`.
- `artifacts/expansion/temporal/ef9c66b2a9d86511bcb8d3d5.json`: SHA-256 `4016ea3dce3673163685ae05bf144defb0915ccf4b1509f2d0404d4754d85d85`.
- `artifacts/expansion/revision_demo/ef9c66b2a9d86511bcb8d3d5/result.json`: SHA-256 `2a0cd964c14a03cf09b412c15f00f340cffbca28766ef003019a8a89c09b0875`.
- `artifacts/expansion/e03_e05_unit_tests.json`: SHA-256 `cccf1a6c4cf76c268effa459b69b0c8f07d2727554b04de9bb610bc6ec05dd15`.
- `artifacts/expansion/e03_e05_integration_tests.json`: SHA-256 `7d966e0d2251edff0d0f43b7f5b1fb37be3568067388e8561fe40c931227f87f`.
- `artifacts/expansion/e03_silver_resources.json`: SHA-256 `b91b300995276a4c99d67c79dbe4ac15c8861b05d247a4ef68520c0965981b71`.
- `artifacts/expansion/e04_audit_resources.json`: SHA-256 `240616de8cd2e325965bf6dbe535320a57c2f0938c4a062424320eb2641ed9be`.
- `artifacts/expansion/e05_gold_resources.json`: SHA-256 `54f9d6993054dd13f41b075f1826fe374302fc7e1bb7562e4e1118febaf065bb`.
- `artifacts/expansion/e03_silver_replay_resources.json`: SHA-256 `f0ab808d3e069d4d7cbeedcae6e3bef6ff9d1a88fe9a56158dc2971877cac104`.
- `artifacts/expansion/e05_gold_replay_resources.json`: SHA-256 `77a894ecb6f0dedf372a68c097f7d858099402c917665f05a681c21b85da63fc`.
- `artifacts/expansion/e03_revision_resources.json`: SHA-256 `378cb26ab99f7b51a22e2a0c4e8b85854c0da1b566d767bfbe33f213ff190004`.
- `data/silver/expansion/c5cdbdab075752f4f5af26cf/_silver.json`: SHA-256 `886d5f16a18f85946c384bd48317cbdf539ac7c6b1728e935b1afa78fdb4eb5a`.
- `artifacts/expansion/e03_rejection_recheck.log`: SHA-256 `bbf5af92c3cce35e170e3c314064385ea4d9cfa8815426e849956e40abeb56c8`.
