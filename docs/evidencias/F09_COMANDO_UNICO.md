# F09.1 — comando operacional

Em 13/11/2026, foi acrescentado `src.pipelines.run_lakehouse`, separado das
demonstrações anteriores e sem alterar seus produtores. O código/configuração
executados estão fixados pelos hashes dos relatórios F09. A interface coordena
as dependências já aprovadas RAW/recorte/Bronze/landing, o espelho por hash,
Silver incremental, reconstrução independente e publicação Silver v2 + Gold S3.
Aquisição e preparação dos aceites de entrada continuam nos comandos existentes.

[Comando e modos](../operacao/COMANDO_UNICO.md). Update exige limite de lote;
replay reaplica pacotes no mesmo estado; rebuild usa outro namespace por run_id.
O catálogo é o conjunto finito de eventos simulados aprovado em F04. O registry
operacional é separado do registry F08. A Gold usa materialização integral nesta
interface, mantendo os contratos e validadores; otimização não foi presumida.

## Evidência executada

O CLI update do primeiro lote passou: run `20261113T152046Z_5dadaa13`, 35.045
casos, 35.045 estáticos, 136.679 históricos, versões 1/1/1. Houve antes um erro
no mapeamento transporte/Silver, corrigido antes de gravar o estado incremental;
o relatório reprovado foi preservado. Não houve aceite daquela tentativa.

- update: `20261113T152423Z_541644e2`, publicação `74e3ff681cee04bc3ad915a9`, versões `{'credit_cases': 2, 'credit_static': 2, 'previous_applications': 2}`.
- replay: `20261113T152801Z_85deefa9`, publicação `74e3ff681cee04bc3ad915a9`, versões `{'credit_cases': 2, 'credit_static': 2, 'previous_applications': 2}`.
- rebuild: `20261113T163139Z_59b92851`, publicação `42b2530aa696de3cf28e1512`, versões `{'credit_cases': 2, 'credit_static': 2, 'previous_applications': 2}`.

A validação real avançou ao segundo lote, reaplicou os dois lotes sem novas
versões ou publicação, recusou um limite anterior ao já consumido e reconstruiu
em estado separado. Todas as cinco tabelas reconstruídas coincidiram integralmente
com a atualização. CURRENT F08 foi conferido antes/depois e permaneceu igual.
O serviço criado pela validação foi parado; dados reais foram preservados.
Resultado: `artifacts/f09/validation/modes.json`; logs `modes.log` e `update.log`.
Os relatórios completos ficam em `artifacts/f09/runs/`.

Três testes unitários de seleção passaram (dependências/ordem, modos e limites,
entradas inválidas). Log `artifacts/f09/validation/unit.log`. A regressão global
F08 de 129 verificações continua como linha de base; ela não foi reexecutada para
esta adição. A validação desta mudança inclui testes direcionados e os modos
reais acima, usando os componentes S3A/Delta já aprovados.

## Limites e próximo passo

F09.1 é aceita para execução sobre entradas locais aprovadas. Não é um comando
de download autenticado nem ingestão de uma fonte CDC. Uma instalação sem dados
precisa preparar as entradas conforme README. F09.2 ainda precisa consolidar
inicialização, estados, classificação de falhas e retry limitado. F09.3–F09.6
continuam pendentes para métricas/lineage/resumo operacional e matriz completa
de falhas. A arquitetura continua limitada a um host/driver cooperante.
