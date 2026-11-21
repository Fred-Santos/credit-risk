# E06 — Análise de público executada

Estado: E06.1–E06.4 aceitos no escopo local. Data de referência: 19/11/2026.
[Resultados e método](../analise/PUBLICO_EXPANSAO.md).

População: 447,305 casos, nove meses, 14,757 positivos observados.
Pacote `407b64011bf6d040484813e8`. Foram materializadas cinco Delta e seus CSVs:
- `monthly`: 9 linhas.
- `coverage`: 144 linhas.
- `missingness`: 1,494 linhas.
- `composition`: 117 linhas.
- `period_compare`: 2 linhas.

Os oráculos mensais, de cobertura, completude, composição e períodos passaram.
Os rótulos da reserva foram acessados explicitamente para descrição, sem ajuste
de modelo. Datas futuras e maturação permanecem limitações da E04, sem atribuir
causalidade ou taxa operacional aos resultados. As figuras PNG/SVG foram geradas
a partir dos agregados e conferidas visualmente.

Execução: **97.94 s**, RSS da árvore amostrado de
**4.03 GiB**, driver com heap de 8 GiB.
O pico de temporários mede apenas o diretório informado; RSS pode contar páginas
compartilhadas e perder picos curtos. O JSON contém todos os denominadores.

Manifesto: `data/gold/expansion-analysis/407b64011bf6d040484813e8/_analysis.json`.
SHA-256: `61facb00dd806d93ca066b9cc3debaace885cf1aa31245740c36f5fa68b353e6`.
Relatório: `data/gold/expansion-analysis/407b64011bf6d040484813e8/report/report.json`.
SHA-256: `4100d283a5152673692aa85658c1f1e5f96fdb528b4f92c5d2ee5b1cd2c92475`.
