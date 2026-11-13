# Evidência F07 — análise, comunicação e reprodução

Data local: 13/11/2026. F07.1–F07.6 implementadas no filesystem local,
consumindo as publicações aprovadas F06. O relatório é uma saída analítica;
nenhuma tabela ou CURRENT foi modificado.

## Critérios atendidos

| Item | Evidência |
|---|---|
| F07.1 | [Matriz P01–P06](../analise/PERGUNTAS_E_METODO.md), campos, população, períodos, fórmulas e limitações |
| F07.2 | [Comando de consumo](../analise/EXECUCAO.md), três IDs explícitos, processo novo, metadata/UUIDs/versões e bundle com aceite |
| F07.3 | Figuras volume/desfecho, contagens e denominadores, flags de grupos pequenos e datas observadas parciais |
| F07.4 | Cobertura mensal e composição por observações; ausência e preenchimento com denominadores distintos |
| F07.5 | Baseline versus correção com mesmos casos/rótulos; atraso separado; gráficos históricos reproduzidos byte a byte |
| F07.6 | [Conclusões revisadas](../analise/RESULTADOS.md), SQL independente, totais reconciliados e autorrevisão declarada |

## Testes

`bash scripts/analysis.sh tests/analysis_integration.py`: **seis cenários Spark
aprovados em 38,403 s**, sem ignorados. O teste usa dados sintéticos, sem Kaggle
ou dados restritos. Dois testes de política/linhagem também passaram pelo Python
principal. O runner global `bash scripts/project.sh scripts/run_tests.py --integration-required`
aprovou **126 verificações em 1100,675 s, sem ignorados**. Inclui quatro
suítes Delta isoladas (15/9/9/8 cenários) e a nova suíte analítica Spark
(seis cenários). Os cinco verificadores de subprocesso já estão no total
do runner; não somar níveis. Registro e log: `artifacts/f07/validation/full_suite.json`
e `full_suite.log`.

Foram exercitados contagens calculadas à mão, cobertura versus completude,
grupos vazios, rótulo nulo, denominador zero, indicador mensal corrompido,
correção auxiliar, atraso, tentativa de trocar população/rótulos e duplicidade
no grão. O teste de indicador corrompido altera seu numerador e exige reprovação
contra o SQL independente, mesmo conservando a quantidade de linhas.

Matplotlib é uma camada isolada em `.runtime/analysis`, com lock próprio e
hashes. `bash scripts/bootstrap_analysis.sh` foi executado com sucesso usando
o lock final; `requirements.lock` e `.venv` do processamento permaneceram
preservados. O runner inclui o wrapper F07 como um subprocesso analítico Spark;
as quatro suítes Delta anteriores permanecem separadas.

## Execução real

```bash
bash scripts/project.sh scripts/measure_resources.py \
  --output artifacts/f07/resources_real.json \
  --workdir artifacts/analysis/7d58bbdaa00cbabfbce54d26 \
  -- bash scripts/analysis.sh -m src.pipelines.run_analysis \
  --sample 7d58bbdaa00cbabfbce54d26 \
  --publication 6f4406dd0180850e23d5283e \
  --baseline c711e23bdd5145ae78537a61 \
  --corrected e709bcefce9adab4b7d60562
```

| Artefato | Valor |
|---|---|
| Primeira execução | 20261113T102239Z_0addbf44 — passed, saída 0 |
| Reprodução em processo novo | 20261113T102427Z_4544dd57 — passed, saída 0 |
| Identidade da análise | 7aba0b9fbdf88f350726cc70 |
| Relatórios de execução | `artifacts/f07/runs/<run_id>.json` |
| Bundles | `artifacts/analysis/7d58bbdaa00cbabfbce54d26/7aba0b9fbdf88f350726cc70/<run_id>/` |
| Hash semântico | 1d68257186139f31740c9b77fa0519849df02b6f44b4f0400889a3b1ce1c706d |

Os dois bundles têm `_SUCCESS.json` aprovado; todos os arquivos inventariados
coincidiram com seus hashes. Reproduzir o comando não substitui uma tentativa.
Os 19 arquivos de resultados comparados coincidiram byte a byte: semantic.json,
seis CSVs e 12 gráficos PNG/SVG, incluindo os gráficos baseline. Metadata e HTML
registram run_id próprio e não são usados como oráculo de igualdade semântica.
Registro: `artifacts/f07/reproduction_check.json`.

## Resultados e revisão

- População final: 50.000 casos, 50.000 rótulos válidos, 1.578 target=1:
  **3,156%**, com zero rótulos ausentes/inválidos.
- Período observado: 01/01/2019–05/10/2020, em 22 meses. Abril/2020 tem 276
  casos; outubro/2020 tem 292. Março começa em 02/03 no recorte; outubro termina
  em 05/10. Sinais de leitura não provam perda de dados na fonte.
- Cobertura histórica: **40.076/50.000 = 80,152%**. Estática e annuity estão
  presentes/preenchidas nos 50 mil casos; isso não torna o campo obrigatório.
- Das 215.390 observações históricas, 208.576 têm montante preenchido e 6.814
  não têm. Há 79 casos com histórico presente mas todos os montantes nulos;
  ausência de observação e ausência de valor são estados distintos.
- Mesma população baseline/corrected: 49.999 casos. Somente caso 64 mudou:
  static_annuity 2436→2437; sum/mean/min/max históricos 6899→6900; revisões
  auxiliares 1→2. Os indicadores mensais de contagens/cobertura/rótulos
  permaneceram iguais, como esperado.
- Atraso separado: caso 135, mês 201901, target=0 e oito observações. Janeiro
  passou de 2.520 para 2.521 casos, mantendo numerador 69; nenhum caso anterior
  mudou. Não atribuir essa diferença à correção de montantes.

Para cada uma das três publicações, SQL de consumo conferiu todos os campos
dos indicadores mensais; SQL independente conferiu os quatro segmentos.
Meses e segmentos reconciliaram com a população. O produtor F06 tem sua
própria prova ABT/Silver, sem ser reexecutado como transformação neste relatório.

A autorrevisão inspecionou as três figuras finais e revisou eixos, unidades,
denominadores, meses pequenos, hipóteses e limites. Não houve avaliador externo.
Detalhes numéricos, interpretação descritiva e investigação futura estão em
[RESULTADOS.md](../analise/RESULTADOS.md); não há conclusão causal, validação de
maturação do rótulo ou recomendação de concessão.

## Recursos e preservação

Primeiro core: **46,422 s**; processo completo medido: **49,844 s**. Segunda
execução, core: **48,496 s**. Pico RSS somado da primeira árvore:
**2.455.621.632 bytes** (aproximadamente 2,29 GiB). Pico de bytes lógicos no
diretório de resultados: **2.479.221 bytes** (aproximadamente 2,36 MiB).

O disco medido inclui o primeiro bundle, sem temporários Spark, cache de fontes
ou dependências gráficas. RSS pode contar páginas compartilhadas e a amostragem
pode perder picos curtos. Não havia outro job Spark pesado simultâneo durante
a medição. O tempo inclui verificações recursivas de publicações, consultas,
gráficos e relatório, sem reprocessar Bronze/Silver/Gold.

Os três manifestos e suas tabelas foram conferidos antes/depois das consultas,
com mesmos hashes, UUIDs e versões; CURRENT permaneceu inalterado nas duas
execuções. Código/configuração foram arquivados por hash nos bundles e
conferidos antes do aceite. Logs em `artifacts/f07/validation/`: integration.log,
real.log, reproduction.log e bootstrap.log. Fonte e resultados continuam locais,
sob as condições de uso já registradas no projeto.

Auditoria adicional em `artifacts/f07/protected_inputs_check.json`: seis arquivos
RAW coincidem com os fingerprints anteriores; recorte e Bronze passaram na
verificação integral; os dois pacotes/recibos iniciais F03 foram conferidos.
Os inventários dos registries Silver e analítico verificaram respectivamente
90 e 127 arquivos publicados, além de blobs e referências de manifestos. Ambos
os ponteiros CURRENT permaneceram nas publicações aprovadas anteriores.
