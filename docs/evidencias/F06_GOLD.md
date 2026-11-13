# Evidência F06 — ABT incremental e indicadores publicados

Data local: 13/11/2026. Python 3.11.14, Java 17, Spark 3.5.7 e Delta 3.3.2,
`local[2]`, driver 2 GiB, quatro partições shuffle. F06.1–F06.6 aceitas no
filesystem local, após a execução aprovada de F05.

## Escopo aceito

| Item | Evidência |
|---|---|
| F06.1 | [Contrato](../contratos/ABT.md): grão, 19 colunas, tipos, fórmulas, nulos e disponibilidade retrospectiva |
| F06.2 | Agregação histórica antes dos joins; fixture de dois históricos preserva os três casos |
| F06.3 | ABT Delta validada e manifesto com três Silver e duas Gold |
| F06.4 | Correção auxiliar seleciona um caso; chegada tardia insere um; igualdade integral nos dois sentidos |
| F06.5 | SQL mensal com contagens, denominadores e taxas; período antigo recalculado |
| F06.6 | Oráculos Silver independentes, falha/retomada, retry e reprodução histórica aprovados |

## Testes

`bash scripts/project.sh tests/gold_integration.py`: **oito cenários Delta em
253,046 s**, todos aprovados, sem ignorados. Duas verificações de contrato
também passaram. Logs preservados em `artifacts/f06/validation/integration.log`.
O runner global `bash scripts/project.sh scripts/run_tests.py --integration-required`
aprovou **123 verificações em 1050,522 s**, sem ignorados. Inclui as quatro
suítes Delta isoladas (15 F03, nove F04, nove F05 e oito F06); os quatro
verificadores de subprocesso já fazem parte do total do runner. Registro e log:
`artifacts/f06/validation/full_suite.json` e `full_suite.log`.

Os cenários incluem histórico 1:N, somas calculáveis à mão, montantes todos
nulos, auxiliar ausente, rótulo nulo, denominador zero, população vazia, correção
somente no histórico, atraso, mudança de mês eliminando grupo vazio, remoção
de caso rejeitada, falha entre Silver/Gold, falha após MERGE, retry sem novo
MERGE, qualidade Gold realmente reprovada e rollback do conjunto. Rótulo nulo
é uma fixture da matemática dos indicadores; a Silver de produção continua
exigindo rótulo preenchido.

## Execução com Home Credit

```bash
bash scripts/project.sh scripts/measure_resources.py \
  --output artifacts/f06/resources_real.json \
  --workdir data/gold/samples/7d58bbdaa00cbabfbce54d26/published \
  -- bash scripts/project.sh -m src.pipelines.run_gold_demo \
  --sample 7d58bbdaa00cbabfbce54d26 \
  --f05-report artifacts/f05/runs/20261113T033217Z_04372370.json
```

Execução `20261113T040310Z_1f51ffa0`, status `passed`, saída 0. Relatório:
`artifacts/f06/runs/20261113T040310Z_1f51ffa0.json`.

| Snapshot | Publicação analítica | Publicação Silver F05 | ABT: linhas / versão | Indicadores: linhas / versão |
|---|---|---|---|---|
| baseline | c711e23bdd5145ae78537a61 | b5e320496adccfe70f22542d | 49.999 / 0 | 22 / 0 |
| corrected | e709bcefce9adab4b7d60562 | 54647e547afac85a7f72c6ca | 49.999 / 1 | 22 / 0 |
| late | 6f4406dd0180850e23d5283e | 1d081af9769d86abc373f48f | 50.000 / 1 | 22 / 0 |

As três Silver são referenciadas por UUID/versão 2 e seus arquivos originais
da F05, sem outra cópia. Cada Gold tem UUID próprio. O registry analítico é
`artifacts/publications/7d58bbdaa00cbabfbce54d26/analytics/`; CURRENT aponta
para **6f4406dd0180850e23d5283e**. CURRENT Silver F05 permanece em late.

O caso 64 recebeu as correções declaradas de +1 na estática e em uma observação
histórica. A base principal não mudou. A Gold identificou **um caso afetado,
zero inserts e um update**; a soma/média histórica e o valor estático foram
reconciliados com SQL das entradas aprovadas. Como os indicadores mensais v1
medem contagens/cobertura/rótulos, a mudança de montantes não deve alterar suas
contagens ou taxas. Esse é um resultado esperado, não uma correção perdida.

O caso atrasado 135 chegou com estática e oito observações. A Gold identificou
**um caso afetado, um insert e zero updates**, no mês original **201901**.
O mês termina com 2.521 casos, 69 target=1 e proporção `69/2521`.
Os 22 períodos vão de 201901 a 202010, sem criar grupos para meses ausentes.

Totais reconciliados da publicação final:

| Medida | Resultado |
|---|---|
| Casos / rótulos válidos | 50.000 / 50.000 |
| target=1 | 1.578 |
| Casos cobertos pela estática | 50.000 |
| Casos com histórico | 40.076 |
| Observações históricas | 215.390 |
| Montantes históricos preenchidos | 208.576 |

São contagens descritivas do recorte, sem inferência causal ou alegação de taxa
operacional de carteira. O contrato explicita a ausência de validação point-in-time.
Interpretação, gráficos e relatório analítico pertencem à F07.

## Falhas, retomada e histórico

Na correção, uma falha deliberada ocorreu após o commit MERGE ABT privado e antes
de criar os indicadores. CURRENT continuou no baseline. A retomada reconheceu
a ABT versão 1 e concluiu as saídas: zero inserts/updates **na tentativa de
retomada**, embora a alteração lógica pai→publicação fosse um update.

Cada ABT incremental coincidiu exatamente com a recomputação integral em todas
as colunas, sem faltas ou excessos. O oráculo SQL direto da Silver conferiu o
contrato ABT; o oráculo mensal usou contagens diretas da Silver, sem derivar
seu resultado da mesma consulta Gold. A tolerância pequena de soma/média no
oráculo SQL não arredonda dados e não relaxa a igualdade incremental/integral.

O rollback ativou baseline. ABT e indicadores foram comparados a uma nova
recomputação das versões Silver originais do baseline: **zero diferenças**.
Depois foi restaurado late. Repetir late reutilizou manifesto e todos os
inventários de arquivos, sem novas escritas Delta. A auditoria confirmou leitura
das três publicações e versões iniciais. Não houve VACUUM de dados reais.

## Recursos e preservação

Core: **190,721 s**; processo completo: **193,323 s** (3 min 13 s). Pico RSS
somado da árvore: **3.171.622.912 bytes**, aproximadamente 2,95 GiB. Pico de bytes
lógicos no diretório Gold medido: **4.999.717 bytes**, aproximadamente 4,77 MiB.
Inclui cópias e versões Gold das três publicações; não inclui Silver, temporários
Spark, caches ou blocos físicos. RSS pode contar páginas compartilhadas e a
amostragem pode perder picos curtos. Não foi executado outro job Spark pesado
simultaneamente durante a medição.

A conferência `artifacts/f06/protected_inputs_check.json` confirmou os hashes
da RAW, manifesto/arquivos do recorte, gate/arquivos Bronze e os dois pacotes
iniciais F03. Os dois recibos de aceite F03 foram verificados. Os 90 arquivos
de dados/logs das três publicações F05 coincidiram com seus inventários;
proveniência arquivada e CURRENT F05 permaneceram íntegros. F06 só lê essas entradas.

Código/configuração estão arquivados por hash nos manifestos. O relatório liga
o relatório F05 por hash; os manifestos ligam as publicações Silver e o pai
analítico. Logs: `artifacts/f06/validation/integration.log` e
`artifacts/f06/validation/real.log`. Operação em
[ABT_E_INDICADORES.md](../gold/ABT_E_INDICADORES.md).

O custo inclui cópia privada da ABT, MERGE por casos afetados, materialização
SQL mensal integral e várias reconciliações completas. Não representa latência
de produção ou benchmark isolado. Publicação usa protocolo POSIX com escritor
cooperante; objetos e orquestração completa seguem em F08/F09.
