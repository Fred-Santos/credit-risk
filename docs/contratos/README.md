# Contratos — snapshot Home Credit e recorte

O contrato do estado Silver persistido está em [SILVER_INICIAL.md](SILVER_INICIAL.md).
Este documento continua descrevendo o snapshot RAW/recorte, com schemas de origem.
A migração publicada está em [SILVER_GERENCIADA.md](SILVER_GERENCIADA.md), e o
contrato de consumo Gold em [ABT.md](ABT.md).

Versão 1, em 12/11/2026. Escopo: arquivos RAW selecionados e seu recorte de
desenvolvimento, ambos snapshots. Não é o contrato de eventos/revisões da Bronze
incremental, nem o contrato final Silver/Gold.

## Definição executável

[home_credit_v1.yaml](../../configs/contracts/home_credit_v1.yaml) contém:

- Identificação da competição e da inspeção de origem.
- SHA-256 e tamanho dos seis arquivos da edição adquirida.
- Relação explícita de shards por tabela lógica.
- Schema completo: **214 entradas de campos** entre as três tabelas.
- Chaves, campos obrigatórios, referências, cobertura e quantidade mínima de linhas.
- Escopo temporal e políticas de falha e preservação.

Leitura e validação estão em [contracts.py](../../src/quality/contracts.py).
Os esquemas de cada shard são conferidos antes da união por nome. Não usamos
`allowMissingColumns=True` para esconder uma divergência de origem.

| Tabela | Grão | Chave | Referência | Cobertura obrigatória da base |
|---|---|---|---|---|
| [train_base](TRAIN_BASE.md) | Caso de crédito | `case_id` | Não se aplica | Não se aplica |
| [train_static_0](TRAIN_STATIC_0.md) | Registro estático por caso | `case_id` | Base por `case_id` | Sim, no snapshot deste MVP |
| [train_applprev_1](TRAIN_APPLPREV_1.md) | Observação de aplicação anterior associada ao caso | `case_id`, `num_group1` | Base por `case_id` | Não; ausência é permitida |

## Políticas comuns

**Schema:** campos e tipos devem corresponder ao contrato. A ordem física pode
variar; colunas ausentes, extras ou de tipo diferente bloqueiam a etapa. O código
diagnostica o desvio antes de produzir uma saída aprovada. Evolução planejada
exigirá revisão do contrato em vez de aceitação automática.

**Nulabilidade:** as chaves são obrigatórias. Na base, também são obrigatórios
data, mês, semana e rótulo. Os outros atributos podem ser nulos neste contrato
inicial. Um campo não vira obrigatório apenas porque não teve nulos no snapshot.
Nulos e NaN são perfilados; valores opcionais não são imputados nesta etapa.

**Falhas:** schema inválido, chave duplicada/nula, referência órfã ou outra regra
obrigatória reprovada bloqueia a publicação do recorte. Não eliminar registros
inválidos silenciosamente. A RAW permanece preservada para investigação. Uma
quarentena com fluxo operacional ainda será desenvolvida, se necessária.

**Versão da fonte:** o contrato fixa a edição pelos checksums, além do schema.
Uma alteração em arquivo de origem exige revisão explícita da edição e do
contrato; não editar o checksum apenas para contornar uma falha desconhecida.
Fontes de correções simuladas são novas entradas sob o
[contrato separado de eventos](EVENTOS_REVISOES.md), implementado em F02.4.

**Tempo:** `date_decision` é data do negócio; download e execução têm timestamps
próprios. A disponibilidade dos atributos auxiliares no instante da decisão
ainda não está comprovada. A entrega inicial é retrospectiva; esse metadado não
constitui validação point-in-time ou autorização para treino preditivo.

**Preservação:** não converter tipos, arredondar valores, preencher nulos ou
tratar códigos/sentinelas neste recorte. Essas transformações pertencem à Silver
e precisam de evidência semântica. A conversão da data usada nos checks não
altera a coluna original do snapshot.

## O que foi validado

Os contratos foram exercitados na fonte real completa selecionada e no recorte
de 50 mil casos. O manifesto do recorte guarda os dois relatórios de validação.
Resultados e identificadores estão em
[evidência de contratos e recorte](../evidencias/F00_CONTRATOS_RECORTE.md).

O conjunto de regras tem 16 verificações agregadas, além da conferência exata
dos schemas e dos fingerprints. Testes sintéticos cobrem violação de chave
obrigatória, referência órfã, coluna extra, nulo opcional e histórico vazio.
Ter essas regras aprovadas não conclui todos os testes de Silver ou Lakehouse.

## Relação com as regras já existentes

Os YAMLs `quality_rules.yaml` e `quality_rules_bronze.yaml` continuam pertencendo
ao fluxo RAW anterior e à publicação Bronze, respectivamente. O YAML Bronze
referencia este contrato desde F02.5: o adaptador gera regras de schema completo,
chaves, nulos obrigatórios, volume e referências. Histórico opcional vazio com
schema válido é permitido. Detalhes em [qualidade Bronze](../QUALIDADE_BRONZE.md).

F02.4 separou unicidade do snapshot de identidade de revisão/evento.
Não aplicar uma chave única por caso a todo um histórico de revisões acumuladas.
