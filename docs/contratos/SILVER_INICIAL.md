# Contrato Silver inicial — F03.5

Definição executável: [silver_initial_v1.yaml](../../configs/contracts/silver_initial_v1.yaml).
Compilação e validação: [silver_contracts.py](../../src/quality/silver_contracts.py).
Escopo: estado persistido das três tabelas do pacote Delta inicial, versão 0.
Este contrato não é o de eventos nem o contrato futuro da ABT.

Atualização F03.6: o [comando operacional](../silver/EXECUCAO_INICIAL.md)
executa este contrato sobre o pacote persistido antes de emitir recibo de aceite
separado. O CLI isolado descrito nesta página continua apenas validando.

## Derivação e independência do writer

O contrato fixa os hashes do snapshot e da política Silver. O compilador deriva
os schemas a partir dessas definições revisadas: mantém os 214 campos de negócio,
converte somente as 23 datas e acrescenta os quatro metadados por tabela.
São **226 entradas de campos**, incluindo 26 do tipo date: 23 de negócio e três
ocorrências de `_ingest_date`.

Chaves, obrigatoriedade de campos e mínimos de linhas são herdados do snapshot
fixado. A política de datas também exige o vínculo com o notebook revisado.
O schema declarado pelo manifesto de materialização não é a fonte normativa:
ele já foi conferido pelo leitor técnico, mas o novo contrato verifica o estado
contra uma expectativa definida separadamente.

O loader rejeita versão, mapeamento, regras ou hashes incompatíveis. Não aceitar
um campo novo apenas porque apareceu num Parquet, nem alterar o contrato para
contornar uma falha sem investigar sua causa.

## Grãos e relacionamentos

| Tabela | Chave/grão | Obrigatoriedade | Relação com credit_cases |
|---|---|---|---|
| credit_cases | Um caso; case_id único | Tabela presente e não vazia; data, mês, semana e target não nulos | Base |
| credit_static | Um registro por case_id | Tabela presente e não vazia | 1:1, sem órfãos e com cobertura completa da base |
| previous_applications | Uma observação por case_id/num_group1 | Tabela presente com schema, podendo ter zero linhas | N:1 em relação à base; nenhum órfão, cobertura parcial permitida |

Unicidade é conferida no conjunto completo, não por arquivo. Campos opcionais
podem ser nulos. Atributo desconhecido, ausência de observação e ausência do
dataset continuam sendo situações diferentes.

O contrato também compara contagens com o manifesto do recorte quando executado
pelo CLI real. A quantidade histórica não é fixada globalmente em 215.390:
esse número pertence à seleção atual. Fixtures e outras seleções compatíveis
usam suas próprias contagens esperadas.

## Regras obrigatórias

- Conjunto exato de tabelas e schema completo, sem colunas extras, ausentes ou
  tipos diferentes. As datas precisam ser date, sem casts defensivos no validador.
- Mínimo de linhas, chaves únicas e campos obrigatórios não nulos.
- `_run_id`, `_source_file` e `ingest_batch` preenchidos e não vazios/em branco;
  `_ingest_date` presente e do tipo date. Não sobrescrever metadados do produtor.
- Target 0/1, semana não negativa e MONTH igual ao ano/mês de date_decision.
- `num_group1` não negativo, pois é um índice estrutural. Não impor um teto
  de 19 ou máximo de 20 observações apenas pelo perfil observado.
- Referências sem órfãos; cobertura completa somente na estática.
- Cardinalidade dos joins de controle: o filho unido à base não pode multiplicar
  linhas; o left join base/estática também deve preservar o número de casos.

Os joins desta validação são temporários e servem à medição. Não modificam as
tabelas e não produzem uma ABT. Para o histórico, o left join direto da base
pode aumentar linhas legitimamente: medimos essa contagem, sem exigir igualdade
com a base. Agregar antes de montar a ABT continua sendo trabalho de F06.

Não há regras de nulificação por aparência, filtro regex de categorias, proibição
genérica de negativos monetários ou preenchimento de booleano null com false.

## Datas: tipo, intervalo e disponibilidade

O validador exige schemas nativos date e perfila nulos e intervalos. Um date
nativo não guarda uma string com dia impossível; a perda silenciosa durante
o cast é tratada pelas guardas de F03.3 e pela reconciliação de F03.4. A presença
de null numa data opcional, isoladamente, não informa se houve erro de conversão:
por isso, contrato e prova de preservação têm funções distintas.

Medimos, por coluna auxiliar, quantas datas são posteriores a date_decision.
O resultado é **diagnóstico, sem falha automática nem descarte**. Datas de
pagamento, validade ou outros eventos podem ter significados diferentes; uma
comparação cronológica não prova quando o atributo estava disponível no sistema.
O produto continua retrospectivo, sem garantia point-in-time para modelagem.

Intervalos observados e max_rows_per_covered_case não viram limites automáticos
de domínio. Novas restrições precisam de justificativa semântica e revisão.

## Como executar

```bash
bash scripts/project.sh -m src.pipelines.validate_silver_initial \
  --sample 7d58bbdaa00cbabfbce54d26 \
  --materialization 41dabc26e228d2527ee553e8
bash scripts/project.sh scripts/run_tests.py --integration-required
```

Não há busca por `latest`: seleção e materialização são explícitas. O comando
confere o vínculo do pacote com seleção/contrato/política, abre somente pelo
leitor Delta com versões fixadas e mantém o lock durante as verificações.
Na saída normal, o leitor revalida os artefatos. O CLI também confere estabilidade
das definições e da entrada antes de registrar sucesso.

O relatório fica em `artifacts/silver_contract_validation/<run_id>.json`, com
contrato compilado, hashes, versões, UUIDs, checks, nulos, intervalos e métricas
dos relacionamentos. Não inclui valores individuais de clientes. Erros retornam
código não zero; falhas de regras trazem o relatório detalhado no diagnóstico.

Uma divergência bloqueia a validação inteira; não há eliminação de linhas.
`accepted_rows=0` na falha e `discarded_rows=0` em qualquer resultado. Schemas
inválidos impedem checks dependentes, que são reprovados explicitamente.

## Resultado e aceite

O contrato é avaliado sobre as versões persistidas sem atualizar o pacote,
seu manifesto, logs Delta ou gate Bronze. O relatório de contrato aprovado
complementa a prova técnica de materialização; não cria `_READY` Silver.
O comando de F03.6 consolida execução repetível e aceite operacional em recibo
separado, sem mudar o comportamento deste validador isolado.

Testes usam oráculos pequenos calculáveis à mão e uma suíte isolada com tabelas
Delta reais. Evidência atual em [F03_CONTRATOS_SILVER.md](../evidencias/F03_CONTRATOS_SILVER.md).
