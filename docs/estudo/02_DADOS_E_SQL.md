# 2 — Dados, relacionamentos e SQL

[Percurso](../GUIA_ESTUDO_LAKEHOUSE.md) · Anterior: [Arquitetura](01_PRODUTO_E_ARQUITETURA.md)

Objetivo: interpretar tabelas e prever o efeito de uma consulta antes de
executá-la. Pré-requisito: conhecer o produto descrito no capítulo 1.

## Grão, chave e ausência de valor

**Grão** é o significado de uma linha. **Chave** é a coluna ou combinação de
colunas que identifica uma linha nesse grão. **Schema** é a definição das
colunas e de seus tipos. Um **nulo** representa ausência de valor; sua
interpretação depende do campo e da regra de negócio.

Na base Home Credit, uma linha representa um caso de crédito, identificado por
`case_id`. Esse identificador não comprova identidade de pessoa. No histórico,
um caso pode ter várias observações. A chave é composta por `case_id` e
`num_group1`, um índice de grupo.

| Origem | Nome na Silver | Chave | Relação com a base |
|---|---|---|---|
| `train_base` | `credit_cases` | `case_id` | Um registro por caso |
| `train_static_0` | `credit_static` | `case_id` | 1:1 no contrato atual |
| `train_applprev_1` | `previous_applications` | `case_id`, `num_group1` | 0:N observações por caso |

**Cardinalidade** descreve quantas linhas podem se relacionar. Um caso sem
observação histórica é permitido. A ausência da tabela inteira tem outro
significado e bloqueia a execução.

## Por que um join pode mudar uma análise

Exemplo sintético: a base tem `(101, target=1)` e `(102, target=0)`. O histórico
tem duas observações de 101 e nenhuma de 102.

Um `LEFT JOIN` preserva as linhas da esquerda e acrescenta cada correspondência
da direita. O resultado tem três linhas: 101 aparece duas vezes; 102 aparece
uma vez com campos históricos nulos. A proporção de `target=1` vira 2/3 se
calculada nessas linhas. Na base original, era 1/2.

O problema está no grão do cálculo. Para uma análise por caso, primeiro
agregamos o histórico por caso e depois fazemos o join.

## SQL para expressar a transformação

SQL descreve seleção, filtros, relacionamentos e agregações sobre tabelas.
`GROUP BY` define a unidade da agregação; `COUNT(*)` conta linhas; `COUNT(campo)`
conta valores não nulos. `WHERE` filtra registros e `HAVING` filtra grupos.

Exemplo didático do padrão de agregação usado na Gold; nomes da consulta abaixo
são ilustrativos. A implementação está em [model.py](../../src/gold/model.py):

```sql
WITH historico_por_caso AS (
    SELECT case_id, COUNT(*) AS quantidade
    FROM previous_applications
    GROUP BY case_id
)
SELECT b.case_id, b.target, COALESCE(h.quantidade, 0) AS quantidade_historica
FROM credit_cases b
LEFT JOIN historico_por_caso h ON b.case_id = h.case_id;
```

No exemplo, o resultado teria duas linhas e quantidades 2 e 0. O zero faz
sentido como contagem de observações ausentes, conforme a definição desse
indicador. Uma média monetária desconhecida não deve virar zero por essa razão.
Para executar SQL sobre DataFrames, é preciso registrá-los como views na sessão.

## Leitura guiada do projeto

Leia [TRAIN_BASE.md](../contratos/TRAIN_BASE.md) e
[TRAIN_APPLPREV_1.md](../contratos/TRAIN_APPLPREV_1.md), observando grão,
chaves e referência. Em seguida, abra
[silver_contracts.py](../../src/quality/silver_contracts.py), função
`validate_silver_frames`, no laço dos relacionamentos.

Observe os anti-joins que medem órfãos e casos sem correspondência. Um
`left_anti` devolve chaves da esquerda que não aparecem na direita. Depois,
compare `child_left_join_rows` e `base_left_join_rows`: o sentido do join muda
a pergunta e a contagem esperada.

## Evidência e ligação com a entrega

Os [contratos Silver](../evidencias/F03_CONTRATOS_SILVER.md) mediram zero órfãos,
estática com cobertura completa e 9.924 casos sem histórico. O left join direto
da base com o histórico gera 225.314 linhas para 50.000 casos. Essa expansão é
compatível com 0:N. A ABT de F06 controla essa multiplicação agregando antes do join.

## Atividade e conferência

Base: casos `{1,2,3}`. Histórico: observações `(1,0)`, `(1,1)`, `(2,0)`.
Preveja as linhas do left join direto, os casos sem histórico e as linhas após
agregar por caso e unir à base.

**Conferência:** quatro linhas no join direto; caso 3 sem histórico; três
linhas após agregar e unir. Repetir `case_id=1` no histórico é válido se a
chave composta continuar única.

Próximo: [3 — Python, ambiente e Git](03_PYTHON_AMBIENTE_E_GIT.md).
