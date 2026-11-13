# Tratamentos Silver e controle de perdas — F03.3

Implementação: [transforms.py](../../src/silver/transforms.py).
Política executável: [silver_policy_v1.yaml](../../configs/silver_policy_v1.yaml).
Esta etapa executa transformações e valida a preservação dos dados. Não grava
tabelas Silver, não cria versões Delta e não aprova publicação Gold.

## Transformações permitidas

Atualização F03.4: estes tratamentos já alimentam a
[materialização Delta inicial](DELTA_INICIAL.md). Esta página descreve a API de
tratamento e sua conferência isolada, que continua sem gravar tabelas por si só.

Somente as 23 colunas de datas revisadas são convertidas de string para date:
uma na base, 15 na estática e sete no histórico. As listas são explícitas na
política. O loader confere versão, políticas suportadas, tabelas, chaves, listas
sem duplicatas e hashes do contrato/notebook revisados. Uma edição incompatível
exige revisão explícita; não inferimos tratamentos pelo sufixo de colunas novas.

As demais colunas mantêm nomes, tipos e valores: bigint, double, boolean,
strings codificadas e metadados. Não há estreitamento numérico, arredondamento,
imputação, substituição de sentinelas, remoção de colunas, deduplicação ou
enriquecimento por join. Um nulo booleano continua diferente de false. Os grãos
e o rótulo permanecem como na entrada aprovada.

## Guarda de conversão

O transformador exige a sessão Spark em UTC e não muda essa configuração.
Para cada coluna de data, aceita somente o formato completo `yyyy-MM-dd`.
Não remove espaços nem interpreta strings vazias como ausência já existente.
Cada valor preenchido deve:

1. Corresponder ao formato ISO de quatro dígitos de ano, dois de mês e dois de dia.
2. Ser interpretável por `try_to_timestamp(..., 'yyyy-MM-dd')`, convertido a date.
3. Voltar à mesma string por `date_format(..., 'yyyy-MM-dd')`.

A terceira condição impede aceitar uma data que um parser permissivo normalize
para outro dia. A regra foi testada com ANSI habilitado/parser CORRECTED e ANSI
desabilitado/parsers LEGACY e EXCEPTION. A função `try_` sozinha não basta: um parse que retorna
null silenciosamente também representa perda quando a entrada era preenchida.

Cada tabela é medida antes de liberar o DataFrame transformado. Se houver valor
preenchido que não possa ser convertido sem perda, `SilverTransformError` inclui
as métricas e bloqueia o snapshot inteiro. Nenhuma linha é descartada. Não há
quarentena nesta versão: a Bronze preservada permite investigar e revisar a causa.

## Métricas e significado

| Métrica por coluna | Significado |
|---|---|
| input_nulls | Nulos que já existiam na Bronze |
| invalid_shape | Valores preenchidos fora do formato aceito |
| parse_failed | Valores com formato canônico que o parser não conseguiu interpretar |
| roundtrip_mismatch | Valores interpretados cuja data formatada diverge da string original |
| new_nulls | Valores preenchidos que a conversão candidata tornaria nulos; qualquer ocorrência bloqueia |
| output_nulls | Nulos da conversão candidata; em sucesso, iguais aos nulos originais |
| converted_non_nulls | Células preenchidas convertidas com sucesso |

Por tabela, `invalid_rows` conta linhas com ao menos uma data inválida, e
`invalid_date_cells` soma células inválidas nas colunas. Uma linha com duas datas
inválidas conta uma vez na primeira métrica e duas na segunda. Não somar contagens
por coluna como se fossem necessariamente casos de crédito distintos.

Na falha, `output_nulls` descreve o candidato rejeitado, não uma saída publicada.
`accepted_rows=0` refere-se ao snapshot bloqueado e `discarded_rows=0` à ausência
de descarte de registros. A aprovação depende de todas as tabelas passarem.

## Provar que o restante foi preservado

`verify_transformation` exige exatamente o schema de origem mais quatro metadados,
trocando somente os tipos das datas para date. Depois, formata apenas as datas
de volta para strings ISO e compara **todos os campos** com a Bronze usando
`exceptAll` nas duas direções, sem casts nas demais colunas.

Essa prova detecta perda/adição de linhas, mudança de multiplicidade, alteração
de valor, nulo preenchido indevidamente e metadado modificado. Ela segue a
igualdade de valores do Spark SQL, não a identidade binária de arquivos/float.
Checksums físicos continuam cobertos pelo leitor Bronze aprovado.

O schema verificado é uma expectativa deste tratamento, não o contrato completo
do estado Silver materializado. Referências, domínios e operação das tabelas
Delta serão consolidados nas fases seguintes.

## API e execução

`load_silver_policy` carrega a política compatível. `transform_table` aplica a
guarda e retorna DataFrame + métricas. `transform_snapshot` coordena as tabelas,
executa a prova de preservação e só retorna frames quando todas passam.

```bash
bash scripts/project.sh -m src.pipelines.check_silver_transforms \
  --sample 7d58bbdaa00cbabfbce54d26
bash scripts/project.sh scripts/run_tests.py --integration-required
```

O CLI usa `open_bronze_snapshot`: todas as ações Spark, inclusive as provas,
ocorrem dentro do lock do leitor. O contexto revalida a publicação ao terminar;
o CLI também confere estabilidade da política, contrato e notebook. Escreve
relatório em `artifacts/silver_transforms/<run_id>.json` com hashes e métricas.
Falhas retornam código de saída diferente de zero e relatório `failed`.

O relatório não inclui valores individuais nem linhas descartadas. Se a falha
for de configuração/schema, o diagnóstico contém a causa; para perda de data,
contém também as métricas da tabela e o resultado parcial das tabelas já avaliadas.
O gate Bronze não é alterado por este consumidor.

## Limites e próxima entrega

Datas válidas não comprovam disponibilidade dos atributos na decisão de crédito.
O produto continua retrospectivo. Não deduzir significado de sentinelas ou
aplicar filtros temporais sem requisito e evidência.

A função produz planos e realiza ações de validação; nenhum DataFrame é devolvido
pelo CLI para consumo tardio fora do lock. A materialização de F03.4 escreve
dentro desse contexto; F03.5 valida os contratos persistidos. O
[comando de F03.6](EXECUCAO_INICIAL.md) reúne essas etapas e emite recibo de
aceite inicial somente após as conferências. Esta API de transformação isolada
continua sem escrever tabelas ou aprovar consumo por conta própria.
