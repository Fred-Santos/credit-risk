# Evidência F02.5 — qualidade Bronze alinhada aos contratos

Data: 12/11/2026. Runtime isolado local, Python 3.11.14 e Spark 3.5.7.
Critério: tabelas, tipos, obrigatoriedade, chaves e referências do snapshot
aplicados à publicação Bronze, com histórico vazio permitido e falhas bloqueantes.

## Implementação

O YAML Bronze referencia `configs/contracts/home_credit_v1.yaml`.
`src/quality/bronze_contract.py` deriva checks obrigatórios a partir dos schemas
e políticas existentes; o contrato congelado e o recorte não mudaram.
`src/quality/engine.py` valida configurações e executa também schema exato,
volume mínimo, cobertura do pai e calendário. Tabelas inesperadas bloqueiam.

Eventos continuam no protocolo próprio, já testado em F02.4: linha completa,
schema/tipos, nulos obrigatórios, domínios, contexto, posições de entrega,
checksums e conflitos entre revisões. Unicidade por caso e cobertura do snapshot
não são exigidas de um pacote de eventos; o estado consolidado será validado
na Silver. A entrega incremental completa permanece em F04.

## Execução real

```bash
bash scripts/project.sh -m src.pipelines.run_bronze_mvp \
  --sample 7d58bbdaa00cbabfbce54d26
```

Run: `20261112T211312Z_d39921f7`; status `passed`; duração interna 9,350 s.
Bronze íntegra reutilizada, sem datasets regravados. Contagens: base 50.000,
estática 50.000, histórico 215.390. **39 checks, zero falhas e zero avisos**.
Gate `_READY.json` atualizado para essa execução após as verificações.

Relatórios privados, relativos à raiz:

- `artifacts/bronze/samples/7d58bbdaa00cbabfbce54d26/runs/20261112T211312Z_d39921f7.json`.
- `artifacts/bronze/samples/7d58bbdaa00cbabfbce54d26/quality/bronze_results/20261112T211312Z_d39921f7_bronze_checks.json`.

SHA-256 identificam o código executado, ainda sem commit desta entrega:

| Arquivo | SHA-256 |
|---|---|
| engine.py | `736180dae6a7d41ff4c5568410cb5cf803415db9e90cd2b1f47ab3f42a768f8e` |
| bronze_contract.py | `fd7e86f9f4b1b0296a97bc29f385245874b1e4a70d592ab344512f1186f7fc87` |
| run_bronze_mvp.py | `ec55e3135b91dbcfefe48a72cc9fc134844f998aa490049046c32423ca506bf0` |
| Contrato snapshot inalterado | `091e65bbee8e1c0907dd9bf23cf9b07dae512f62c3ecd99935a53c728c722cb6` |

O relatório de qualidade registra o hash do contrato; o manifesto da execução
registra os hashes do código e do YAML. RAW e recorte foram verificados pelo
protocolo de entrada, sem reescrita. Os arquivos Bronze comprometidos também
foram conferidos pelo protocolo de retry antes da reutilização.

## Testes

```bash
bash scripts/project.sh scripts/run_tests.py --integration-required
```

Sete novos testes em `tests/test_bronze_quality_contract.py`: configuração
inválida mesmo sob default warn, histórico vazio/nulo opcional, tabela auxiliar
ausente/tabela extra, coluna extra/tipo incompatível, calendário/target/cobertura,
duplicatas/órfãos e Parquet ilegível. Usam schemas mínimos e dados sintéticos
temporários; não dependem do Kaggle. A fixture de recuperação recebeu contrato
válido compatível com seus dados, em lugar do antigo objeto vazio.

As integrações anteriores continuam cobrindo duplicata entre arquivos, nulos
obrigatórios, falha de qualidade removendo o gate e recuperação após correção.
O protocolo de eventos continua coberto pelos 15 testes de F02.4.

Suíte final: **73 testes aprovados em 56,824 s, nenhum ignorado**. Log da sessão:
`/tmp/credit-risk-tests-f025-final.log`. Contagem e links locais da documentação
conferidos; `git diff --check` sem erros.

F02.5 aceita; próxima entrega
F02.6: igualdade integral de chaves e valores entre origem e Bronze, além da
auditoria de `_source_file`, manifestos e lineage. Qualidade aprovada não conclui
essa reconciliação nem comprova disponibilidade temporal para modelagem.
