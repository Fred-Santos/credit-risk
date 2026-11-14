# F09.4 — lineage e inventário por publicação

Em 13/11/2026 foi acrescentada uma auditoria de leitura sobre operações
aprovadas, sem modificar os produtores, dados ou ponteiros existentes.
Implementação: `src.operation.lineage` e CLI `src.pipelines.inspect_lineage`.
[Comando, dicionário de IDs e limites](../operacao/LINEAGE_E_INVENTARIO.md).

A auditoria liga operação/tentativa/run, manifesto, coorte, modos/limites,
versões de origem, lote/recibo, espelho, RAW, recorte, Bronze, landing, estado
incremental e as cinco tabelas publicadas. O mapa cobre as 19 colunas ABT e
11 dos indicadores; é revisado e vinculado ao hash conhecido do modelo Gold,
sem alegar inferência automática de SQL ou prova point-in-time.

## Validação real

```bash
bash scripts/objects.sh -m src.pipelines.inspect_lineage \
  --operation-report artifacts/f09/operations/20261113T173937Z_821632d2.json
```

O script `artifacts/f09/validation/f094/validate.py` auditou a atualização e seu
replay e repetiu a primeira auditoria no mesmo Spark. Todas as leituras fizeram
conferência de hashes, UUIDs, versões, schemas e contagens das cinco tabelas.
O espelho de 113 arquivos foi conferido por SHA-256, e os vínculos entre gates,
seleção e lotes foram verificados. Resultado `results.json`, status passed.

- Auditoria 1: `e7d8012d746f76196ed220c8`, arquivo `20261113T175622Z_19e6e9eb.json`.
- Auditoria 2: `48b0cc87499df5c0bbd1e993`, arquivo `20261113T175635Z_a2712876.json`.
- Auditoria 3: `e7d8012d746f76196ed220c8`, arquivo `20261113T175638Z_494b7ed6.json`.

A primeira e a terceira auditorias produziram o mesmo inventory_id com
outros audit_run_id. A atualização e o replay usam a publicação
`0b0bc75d0e35ade82fd750ee`, mas têm runs de consumo diferentes:
`20261113T173937Z_1a2c77a9` e `20261113T174309Z_55aac979`.
Os logs locais identificaram a mesma tentativa de criação nos dois inventários;
a origem dessa observação é declarada e os arquivos são fixados por hash.


O inventário contém **5 tabelas publicadas, 15 nós de origem/trabalho e 19
ligações entre tabelas**, além dos arquivos, colunas e consumidores conhecidos.
Os dois CURRENT S3 (demonstração F08 e operação F09) permaneceram byte a byte
iguais. O serviço terminou parado e os dados foram preservados. Nenhuma carga,
MERGE, ativação ou troca de publicação foi executada pela auditoria.

## Testes e preservação

Cinco testes novos aprovados: cobertura das colunas/constante, modelo desconhecido,
publicação reutilizada, vínculo operação/tentativa/coorte/limite e versões/código
incompatíveis. A regressão direcionada executou nove verificações no runner
(cinco de lineage, três de métricas e um wrapper dos oito cenários de supervisor)
e três testes de seleção F09.1. Não somar wrapper e cenários internos como
verificações do mesmo nível. Logs `unit.log`, `regression.log` e `selection.log`.
A regressão global F08 de 129 verificações é a linha de base anterior; não foi
reexecutada nesta alteração.

A auditoria de preservação `protected_inputs_check.json` conferiu seis RAW,
recorte/Bronze, dois recibos F03, 90 arquivos publicados F05 e 127 de F06,
blobs/referências, ambos CURRENT locais e os dois bundles F07. Os produtores
F05/F06/F08 permanecem iguais às suas referências. Os produtores F09 também
não foram alterados nesta etapa; somente o consumidor de auditoria foi criado.
Logs reais: `validation.log` no diretório de validação F09.4.

## Limites

Uma publicação explícita é auditada por vez; não é catálogo global de acessos.
As dependências Gold são declaradas pelo mapa suportado; a leitura deste auditor
é verificada com Delta. O relatório F07 continua consumidor das suas publicações
F06 no filesystem. Não inventar ligação dele ao S3. O estado de trabalho pode
avançar depois; as versões publicadas e recibos preservados são as referências
históricas. Logs de criação ausentes geram lista de tentativas observadas vazia,
sem atribuir o run de replay como produtor original. Logs locais não são
assinaturas criptográficas de autoria. Próxima: F09.5, resumo operacional.
