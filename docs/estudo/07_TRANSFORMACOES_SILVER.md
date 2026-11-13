# 7 — Transformar dados e controlar perdas na Silver

[Percurso](../GUIA_ESTUDO_LAKEHOUSE.md) · Anterior: [Qualidade](06_QUALIDADE_E_GOVERNANCA.md)

Objetivo: entender como uma hipótese de limpeza vira uma transformação
verificável. Pré-requisito: tipos, nulos, DataFrames e reconciliação.

## Transformar exige uma justificativa

Um notebook permite explorar campos e testar hipóteses. Para transformar uma
hipótese em regra da pipeline, precisamos decidir onde ela se aplica, o que
preserva e como detectar resultados inválidos.

No notebook original havia propostas de conversão, tratamento de sentinelas e
remoção de colunas. O catálogo de F03.1 revisou essas propostas contra a origem
e o recorte. A política adotada preserva números, códigos, colunas e nulos,
convertendo somente as 23 datas explicitamente aprovadas.

Uma string codificada continua sendo um valor, mesmo se sua aparência parecer
aleatória. Um negativo pode ter significado. Uma coluna constante no recorte
pode variar em outra seleção. Nenhuma dessas observações autoriza alteração
semântica automática.

## Tipo e representação de uma data

Texto `"2020-02-29"` e uma data nativa podem aparecer da mesma forma na tela,
mas suportam operações e validações diferentes. Converter o tipo, ou fazer um
**cast**, tenta interpretar o valor sob uma regra.

Exemplo sintético:

| Entrada | Resultado pretendido | Condição |
|---|---|---|
| `2020-02-29` | Data de 29/02/2020 | Válida |
| nulo | nulo | Ausência original preservada |
| `2019-02-29` | Bloquear aceite | Dia inexistente |
| `2020-2-29` | Bloquear aceite | Fora do formato aprovado |

Um parser pode lançar erro ou produzir nulo. Apenas contar nulos na saída não
identifica a causa: precisamos medir entradas preenchidas que perderiam o valor.

## Como a guarda foi implementada

O tratamento exige formato ISO `yyyy-MM-dd`, tenta interpretar a data e formata
o resultado de volta para comparar com o texto original. A ida e volta evita
aceitar uma normalização silenciosa para outro dia.

`new_nulls` conta entradas preenchidas que se tornariam nulas; qualquer perda
bloqueia o snapshot inteiro. `input_nulls` mede ausências originais.
`invalid_date_cells` soma células inválidas, enquanto `invalid_rows` conta linhas
afetadas. Uma linha com duas datas ruins conta duas células e uma linha.

Não há descarte nem quarentena automática nesta política. O tratamento também
prova a preservação das demais colunas: formata somente as datas de volta e
compara todas as linhas com a Bronze nos dois sentidos.

## Leitura guiada do projeto

1. Abra [silver_policy_v1.yaml](../../configs/silver_policy_v1.yaml) e localize
   as listas `cast_to_date` por tabela. São decisões explícitas.
2. Em [transforms.py](../../src/silver/transforms.py), leia `load_silver_policy`:
   o vínculo com contrato e notebook revisados é validado por hash.
3. Em `transform_table`, acompanhe formato, parse, ida e volta e agregações de
   métricas. Observe onde `SilverTransformError` impede continuidade.
4. Em `verify_transformation`, veja a representação restaurada e a comparação.
   Em `transform_snapshot`, veja como a aprovação depende de todas as tabelas.

Essas funções descrevem tratamentos e executam verificações. A gravação Delta
tem responsabilidade própria, estudada no próximo capítulo. O notebook é
proveniência da revisão; suas células não executam no comando operacional.

## Evidência e ligação com a entrega

A [evidência dos tratamentos](../evidencias/F03_TRATAMENTOS_SILVER.md) mostra
23 colunas de datas convertidas e 315.390 linhas preservadas, sem novas perdas.
As datas auxiliares posteriores à decisão são medidas como diagnóstico; não
provam disponibilidade do atributo naquele instante. A análise seguirá
retrospectiva, sem promessa de base válida para treino preditivo.

## Atividade e conferência

Uma coluna tem dois nulos originais, uma data inválida e sete datas válidas.
Qual seria o total de nulos de uma conversão permissiva? A pipeline deve aceitá-la?

**Conferência:** três nulos candidatos, sendo um novo. Nossa política bloqueia
o aceite, preserva a origem e registra a perda. Preencher todos com uma data
padrão mudaria o significado dos dados e exigiria outra regra justificada.

Próximo: [8 — Delta e execução Silver](08_DELTA_E_EXECUCAO.md).
