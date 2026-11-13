# Evidência F02.4 — eventos e revisões

Data: 12/11/2026. Ambiente: runtime local isolado descrito em
[F01](F01_AMBIENTE.md); Python 3.11.14 e Spark 3.5.7.
Aceite restrito ao contrato e à landing local de pequenos lotes de referência.

## Entrada e versões

Seleção: `7d58bbdaa00cbabfbce54d26`; stream: `contract_demo_v1`.
O produtor verificou o manifesto e os arquivos do recorte antes de ler, antes
de publicar e ao terminar. Originais, recorte e Bronze do snapshot não foram
reescritos. Não houve download adicional nem submissão à competição.

| Artefato | SHA-256 |
|---|---|
| Contrato snapshot | `091e65bbee8e1c0907dd9bf23cf9b07dae512f62c3ecd99935a53c728c722cb6` |
| Contrato eventos | `edd15928237789010a09707be91753ac8852c2d70de6cd66129848d37ce80520` |
| Manifesto do recorte | `828bcaacbb6be130eb52dd23f941be5d1d4642ec0d36eac0a8cc36c44ac85646` |
| `src/quality/event_contracts.py` | `43f441f2a58103e3540a9b479257f300813f869b63cb69c20b185a28a81aadf1` |
| `src/bronze/event_batches.py` | `b57e688d724b30801bd505adcefd1041895b1c839763e98f19be189703ace42b` |
| `src/pipelines/check_event_contract.py` | `7b8c68f805585b45474fd4a6b22236c6ac01ac46b4f417fd916dddfd38e03e8e` |

Código ainda sem commit desta entrega; hashes acima identificam a implementação
executada. O schema completo é reutilizado do contrato snapshot, sem alterar a
identidade do recorte aceito.

## Execução real e reexecução

```bash
bash scripts/project.sh -m src.pipelines.check_event_contract \
  --sample 7d58bbdaa00cbabfbce54d26
```

Primeira execução: `20261112T210509Z_bd89e773`.
Reexecução: `20261112T210726Z_45bfa5b9`.
Relatórios privados em `artifacts/event_contract/<run_id>.json`, com estado
`passed`, vínculo de entrada, hashes do código e resumo sem valores individuais.

O produtor extraiu três linhas reais do mesmo caso (base, estática e uma
observação histórica), pertencente a `b00_w000_051`. Todos os envelopes declaram
chegada simulada. Apenas a correção altera o payload, adicionando 1,0 ao campo
`train_static_0.annuity_780A`, com origem explicitamente marcada.

| Pacote aceito | Entregas | Índice de recebimento | Primeira execução | Segunda execução |
|---|---|---|---|---|
| `demo_initial` | 3 | 1 | Publicado | Reutilizado |
| `demo_correction` | 1 | 2 | Publicado | Reutilizado |
| `demo_late` | 1 | 3 | Publicado | Reutilizado |
| `demo_duplicates` | 2 | 4 | Publicado | Reutilizado |

Esperado e obtido pela referência de estado: 3 inserts, 1 update, 1 revisão
antiga sem efeito e 2 repetições sem efeito. O retry explícito do pacote inicial
também retornou `reused=true`. Os recibos originais são preservados.

`demo_conflict` tentou outra imagem para a mesma chave/revisão 2: recebeu
`EventConflictError`, sem diretório de lote publicado, nas duas execuções.
Os sete envelopes válidos permanecem auditáveis; não há merge Silver aplicado.

## Testes automatizados

```bash
bash scripts/project.sh -m unittest discover -s tests -p test_event_contracts.py -v
bash scripts/project.sh scripts/run_tests.py --integration-required
```

15 novos testes aprovados em `tests/test_event_contracts.py`. Cobrem identidade
estável, chave composta/contexto, imagem completa e tipos, nulos opcionais,
normalização de double, falsificação de metadados, domínio da base, conflito em
revisão antiga, todas as ordens de três revisões, comparação entre chaves,
retry, duplicata de posição, mudança de lote, rejeição do lote inteiro, entregas
atrasadas, falha anterior ao commit, corrupção de saída e vínculo de contexto.

Suíte completa: **66 testes aprovados em 37,022 s, nenhum ignorado**, incluindo
as integrações Spark anteriores. Log da sessão: `/tmp/credit-risk-tests.log`.
Não depende de autenticação Kaggle ou dados reais para rodar os testes unitários.

## Aceite e trabalho restante

F02.4 aceito. Contrato, documentação, referência de precedência e publicação
imutável local estão implementados. A unicidade da entrega é por contexto,
lote, tabela e posição; a repetição do evento é preservada. Mesma revisão com
conteúdo diferente bloqueia o pacote, incluindo conflitos no histórico antigo.

F02.5 e F02.6 seguem pendentes. F04 ainda deve gerar os lotes completos, adaptar
o transporte/validação à execução distribuída e aplicar o merge Silver. Nenhum
teste de referência substitui a comparação incremental versus reconstrução,
atomicidade entre tabelas ou garantias de armazenamento de objetos.
