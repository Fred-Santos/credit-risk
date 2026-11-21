# Aceitação da expansão Home Credit — E08

A [matriz executável](../../tests/expansion_acceptance_matrix.json) complementa
os cenários históricos [T01–T24](MATRIZ_ACEITACAO.md). A contagem da suíte é por
teste descoberto; os fluxos internos executados em JVMs isoladas contam uma vez
no respectivo wrapper. A evidência de execução está em
[E08](../evidencias/E08_ACEITACAO_EXPANSAO.md).

| Cenário | Garantia exercitada |
|---|---|
| X01 | Catálogo completo, shards únicos, escopo e caminhos válidos |
| X02 | Janelas sem lacunas/sobreposição e sem amostragem |
| X03 | Bronze preserva históricos antigos/futuros, nulos e multiplicidade; corrupção bloqueia reuso |
| X04 | Falha privada não ativa snapshot e retry reconstrói |
| X05 | Cast de datas sem novos nulos e bloqueio de calendário inválido |
| X06 | Comparação exata por chave detecta valores, faltas, extras e duplicatas |
| X07 | Revisões, reenvios, eventos ultrapassados e conflitos |
| X08 | Média hierárquica ponderada e distinção entre nulo e ausência |
| X09 | Solicitante de índice zero e moda com desempate determinístico |
| X10 | Rejeições rastreáveis por chave/regra e preservação da entrada |
| X11 | Labels da reserva exigem opt-in e treino sem evidência temporal é bloqueado |
| X12 | Delta MERGE, casos afetados, duas ABTs disjuntas e schemas iguais |
| X13 | Análise de nove meses, denominadores, ausências e categoria literal vs nulo |
| X14 | S3: falhas, rollback, reuso, histórico e labels individuais ocultos |
| X15 | Upload nunca sobrescreve objeto divergente e logs não escapam do snapshot |
| X16 | RAW inventada até S3 para MVP e expansão, sem Kaggle |
| X17 | Perfis 2/8 GiB separados e mudança de heap exige JVM nova |

Depois dos bootstraps de ambiente, análise e objetos:

```bash
bash scripts/project.sh scripts/check_code.py
bash scripts/project.sh scripts/run_tests.py --integration-required --report artifacts/expansion/e08/full_suite.json
bash scripts/project.sh scripts/check_acceptance.py --report artifacts/expansion/e08/full_suite.json --output artifacts/expansion/e08/mvp_acceptance.json
bash scripts/project.sh scripts/check_expansion_acceptance.py --report artifacts/expansion/e08/full_suite.json --output artifacts/expansion/e08/expansion_acceptance.json
```

O gate exige o catálogo completo atual, integrações obrigatórias, todos os testes
aprovados, nenhum ignorado e evidência do novo e2e. Sem `--report`, verifica apenas
o mapeamento estático e não atesta execução. O e2e usa cinco tabelas inventadas,
com relações de níveis 0/1/2, seis casos nos limites das janelas (quatro selecionados),
histórico antigo/futuro, valores zero/nulos e ausência de auxiliares. Publica 18
tabelas no seu próprio prefixo temporário S3 e remove apenas esse prefixo. A execução
completa em dados reais das 17 fontes permanece demonstrada em E02–E07.

Os testes provam os controles de prevenção de vazamento implementados: rótulos
separados, reserva por período, bloqueio do leitor ML e diagnóstico temporal.
Eles não comprovam disponibilidade histórica dos atributos nem maturação do target.
A entrega continua retrospectiva; `ml_ready=false`. A CI declara os mesmos gates;
a evidência local não implica execução remota do workflow.
