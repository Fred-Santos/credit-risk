# F09.5 — resumo operacional e alertas locais

Em 13/11/2026 foram acrescentados `src.operation.status` e o CLI
`src.pipelines.operational_status`, sem alterar os produtores ou suas regras.
[Operação, níveis de leitura e calibração](../operacao/RESUMO_OPERACIONAL.md).
O resumo salva JSON e Markdown, exibindo execução, publicação, falhas, qualidade,
relatórios sem estado final e limites locais. Não inicia serviços nem agenda
monitoramento. O Spark é usado somente quando a leitura Delta é solicitada.

## Validação real

O script `artifacts/f09/validation/f095/validate.py` verificou cinco casos:

| Caso | Publicação apresentada | Código |
|---|---|---:|
| online | online — `0b0bc75d0e35ade82fd750ee` | 0 |
| verified | online — `0b0bc75d0e35ade82fd750ee` | 0 |
| service_unavailable | cached — `0b0bc75d0e35ade82fd750ee` | 0 |
| offline | cached — `0b0bc75d0e35ade82fd750ee` | 0 |
| verification_unavailable | cached — `0b0bc75d0e35ade82fd750ee` | 1 |

Resumo com leitura Delta: `20261113T182235Z_e9d70572.json`.
Última execução conhecida: `20261113T174530Z_27471961`,
reprovada por fonte ausente na validação F09.3. A publicação
`0b0bc75d0e35ade82fd750ee` continuou aprovada. O resumo exibiu
attention e preservou a distinção entre falha da operação e qualidade dos dados.
Não houve nova falha de carga nesta etapa.


A leitura normal confirmou ponteiro/manifesto e suas aprovações. A opção
--verify-tables conferiu hashes, UUIDs, schemas, versões e contagens das cinco
tabelas com Spark/Delta. A qualidade permanece a aprovação armazenada, sem
alegar recomputação de SQL nesta consulta. Com o serviço parado, o resumo usou
cache sem declarar CURRENT atual. A verificação completa solicitada com S3
indisponível retornou 1, apesar de haver cache anteriormente verificado.

O comando não iniciou o servidor em nenhum dos modos. A validação iniciou/parou
o serviço externamente e comprovou os dois CURRENT S3 byte a byte iguais
(demonstração F08 e operação F09). Nenhuma carga, ativação ou MERGE foi executado.
Arquivos JSON/Markdown do resumo foram produzidos, e o servidor terminou parado.
Resultados: `results.json`, `online.log`, `verified.log`, `service_unavailable.log`,
`offline.log` e `verification_unavailable.log` no diretório de validação F09.5.

## Alertas calibrados

A política `configs/operational_alerts_v1.yaml` aponta duas operações F09.3
por path e SHA-256. Os limites são 2× a duração e 1,5× o RSS observado. Aplicam-se
somente ao mesmo modo/lote/coorte da última operação bem-sucedida. São margens
iniciais de investigação, não SLA ou inferência estatística. Sem perfil, não
inventa limite. Baseline ausente/alterada gera aviso e desabilita a comparação,
sem esconder a publicação e o histórico disponíveis.

- update/b00_w000_051: acima de 422.423 s ou 7549796352 bytes RSS; baseline `artifacts/f09/operations/20261113T173937Z_821632d2.json`.
- replay/b00_w000_051: acima de 281.367 s ou 5665751040 bytes RSS; baseline `artifacts/f09/operations/20261113T174309Z_698759ab.json`.

## Testes e preservação

Oito testes novos aprovados: falha recente com publicação válida; limites só em
operações comparáveis; cache não atual e corrupção; ordenação temporal e história
incompleta; relatório sem estado final sem alegar processo vivo; coorte/qualidade
inválida; baseline fixada e deriva detectada; métrica inválida sem quebrar a consulta.

A regressão direcionada aprovou 17 verificações no runner (oito do resumo, cinco
de lineage, três de métricas e o wrapper dos oito cenários do supervisor), além
dos três testes de seleção F09.1. Não somar wrapper e cenários internos como
se fossem do mesmo nível. Logs `unit.log`, `regression.log` e `selection.log`.
A regressão global F08 de 129 verificações é a linha de base anterior; não foi
reexecutada nesta alteração.

A auditoria `protected_inputs_check.json` verificou RAW/recorte/Bronze, recibos
F03, arquivos publicados F05/F06, ponteiros locais e bundles F07. Os produtores
F05/F06/F08 permaneceram iguais às referências, e os produtores F09 não foram
alterados por esta etapa. O resumo e a política ficam fora de suas identidades.

## Limites

O resumo usa artefatos locais e o registry operacional F09; não é catálogo global,
monitoramento de liveness ou consumidor alternativo dos dados. Cache não comprova
CURRENT. Quality=passed é a aprovação registrada, distinguida da leitura de
arquivos feita agora. O código 0 indica resumo gerado e não sucesso da última
carga. Alertas não reiniciam serviços nem alteram dados. Próxima: F09.6,
matriz ponta a ponta de sucesso e falhas operacionais.
