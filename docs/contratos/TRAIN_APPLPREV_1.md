# Contrato — train_applprev_1

Versão 1. [Políticas comuns](README.md) e
[schema completo dos 41 campos](../../configs/contracts/home_credit_v1.yaml).

| Item | Definição |
|---|---|
| Grão | Uma observação de aplicação anterior associada ao caso e ao índice `num_group1` |
| Shards RAW | `train_applprev_1_0.parquet` e `train_applprev_1_1.parquet`, na pasta de treino |
| Chave | `case_id`, `num_group1`, ambos bigint e não nulos |
| Unicidade | Global no dataset lógico após unir os shards |
| Referência | Todo `case_id` presente deve existir na base |
| Cobertura | Parcial permitida; não exigir histórico para todo caso |
| Mínimo de linhas | Zero, preservando schema e presença do dataset |
| Demais atributos | Podem ser nulos; preservar valores e tipos RAW |

`case_id` repetido é esperado em uma relação 1:N. `num_group1` é parte da chave
observada deste snapshot, não um identificador global cuja estabilidade foi
provada em sistemas operacionais ou extrações futuras.

O recorte seleciona casos na base e traz **todas** as linhas históricas desses
casos por semi-join. Não aplicar um limite independente de linhas na auxiliar,
pois isso poderia truncar o histórico dos casos selecionados.

Ausência de histórico, quantidade zero de registros e valor monetário desconhecido
são situações diferentes. A regra de agregação da ABT definirá cada representação;
este contrato não preenche atributos com zero.

As datas auxiliares permanecem strings e seu significado temporal ainda será
validado. Selecionar o histórico junto do lote do caso evita introduzir casos
de lotes futuros, mas não comprova disponibilidade de cada atributo na decisão.

Na Silver inicial, esta fonte é `previous_applications`: sete datas são date
nativas, com guardas de perda e preservação dos demais campos. O grão e a
cobertura parcial são mantidos. Contrato do estado persistido e diagnóstico
temporal em [SILVER_INICIAL.md](SILVER_INICIAL.md).
