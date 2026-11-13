# Contrato Silver gerenciada v2 — F05

Definição: [silver_managed_v2.yaml](../../configs/contracts/silver_managed_v2.yaml).
Implementação: [evolution.py](../../src/publication/evolution.py).

A v2 herda os campos de negócio/metadados Bronze do contrato Silver inicial e
os sete campos de evento do estado F04. A única coluna nova autorizada é
`_silver_contract_version`, do tipo `int`, preenchida com 2.

Essa coluna é técnica: identifica o contrato aplicado à linha. Não inventa
atributo financeiro, não altera as regras de negócio e não comprova SCD tipo 2.
Uma coluna de negócio futura exigirá contrato e migração próprios.

## Migração permitida

1. Validar exatamente o schema v1 da entrada versionada F04.
2. Criar uma cópia privada Delta, versão 0, e reconciliar todos os valores.
3. Executar `ALTER TABLE ... ADD COLUMNS` somente para a coluna aprovada.
4. Preencher os registros existentes com 2, sem casts ou mudança das demais colunas.
5. Comparar novamente todas as colunas antigas com a entrada e validar o estado v2.

Para tabelas não vazias, a sequência produz normalmente versões 0/1/2. Uma
tabela histórica vazia tem a coluna adicionada e pode dispensar o commit de
backfill. Versões Delta são locais à tabela e não são a versão do contrato.

Coluna obrigatória ausente, coluna inesperada ou tipo incompatível bloqueiam
antes da cópia. Uma alteração inesperada na área privada também bloqueia a
retomada. Não habilitamos evolução automática genérica nem overwriteSchema.

## Regras preservadas e aceite

Chaves, nulos, domínios, calendário e referências continuam nas definições
herdadas. Estática mantém cobertura 1:1; histórico mantém 0:N e pode estar vazio
com schema. Todos os marcadores existentes precisam estar preenchidos com 2.

Não se modifica o estado F04 para demonstrar migração. As cópias ficam em
`data/silver/samples/<selection_id>/published/<publication_id>/`.
O consumidor só as vê depois do manifesto aprovado e da troca de CURRENT,
conforme o [protocolo local](../PUBLICACAO_E_RECUPERACAO.md).
