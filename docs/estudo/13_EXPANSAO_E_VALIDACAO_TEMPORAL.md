# 13 — Expansão Home Credit e validação temporal

O MVP demonstrou o ciclo com três fontes e 50 mil casos. A expansão integrou
17 tabelas lógicas em 32 Parquets e selecionou 447.305 casos por data de decisão,
sem limite de amostra. A finalidade desta leitura é entender como essa mudança
altera contratos, processamento e evidências, preservando os limites do estudo.

## Uma fonte completa não tem um único grão

Leia `configs/contracts/expansion_silver_v1.yaml`. Nível zero usa `case_id`;
nível um acrescenta `num_group1`; nível dois acrescenta `num_group2`. Esses
índices são locais ao snapshot, não identificadores globais de pessoas ou
contratos financeiros. Os vínculos entre níveis são auditados; os históricos
não são ligados crus em uma cadeia que multiplicaria observações.

A Bronze filtra apenas os casos pela `date_decision` da base. Auxiliares entram
por semi-join em `case_id`, conservando datas antigas e futuras. A Silver faz
58 casts explícitos com roundtrip sem perda, audita chaves e compara cada célula
após a transformação. Uma linha rejeitada bloqueia o pacote e permanece na
entrada para diagnóstico; não há descarte silencioso.

## Uma janela curta não prova ausência de vazamento

O desenvolvimento contém janeiro–maio/2020 e a avaliação contém junho–setembro.
A separação é por caso, com interseção zero, e as duas ABTs usam o mesmo contrato.
Ela não demonstra que um atributo existia na decisão, que o target já havia
maturado em junho ou que uma pessoa não aparece nos dois períodos.

Abra `src/expansion/temporal.py` e a [evidência E04](../evidencias/E04_ATRIBUTOS_E_TEMPO.md).
A auditoria encontrou datas posteriores à decisão em 44 campos. Algumas podem
ser programadas ou transformadas; o número não comprova vazamento. Também não
é correto aprovar um atributo apenas porque sua data é anterior à decisão.
Disponibilidade histórica exige evidência própria. O horizonte de maturação
do target não foi especificado na descrição consultada.

Por isso, `eligible_predictors=[]` e `ml_ready=false`. As ABTs foram entregues
como produtos retrospectivos, e `open_ml_inputs` recusa treino. Isso preserva
uma pendência explícita sem inventar uma garantia que a fonte não permite provar.
Os preprocessadores futuros deverão ser ajustados somente no treino de cada
fold cronológico de desenvolvimento, com estados congelados para validação e
reserva. Folds e embargo dependem da maturação ainda desconhecida.

## Agregação por caso e por grupo

Em `src/expansion/features.py`, compare `aggregate_block` com `sql_oracle`.
No nível dois, a média final usa somas e quantidades não nulas por grupo. Não
é a média simples das médias de grupos com tamanhos diferentes. Pessoas usam
índice zero para os atributos do solicitante; uma pessoa relacionada não é
escolhida como substituta. A moda desempata pelo código em ordem lexical.

Ausência gera contagens zero e flags false; medidas sem valores observados
permanecem nulas. Zero observado permanece zero. As 166 features incluem todos
os tipos de fonte, mas não todas as colunas disponíveis. Os campos excluídos
continuam na Silver e estão classificados no catálogo de origens.

As features físicas têm 170 colunas, incluindo quatro metadados. Labels ficam
em outra Delta com `case_id/target`; a ABT lógica tem 171 colunas nos dois
períodos. Rótulos da reserva exigem opt-in na API. Essa guarda não impede o
proprietário de acessar diretamente seus arquivos locais.

## Fechar a publicação e demonstrar recuperação

O S3 local publica 42 Delta: 17 Silver, 16 blocos, quatro componentes das ABTs
e cinco tabelas analíticas. Leia `src/expansion/publication.py` e `delivery.py`.
A aplicação copia os bytes aprovados, confere hashes/UUIDs/versões e só então
ativa CURRENT. Uma falha antes da troca conserva a publicação vigente; uma
falha depois da troca exige consultar CURRENT antes de concluir o estado.

A E07 demonstrou uma correção auxiliar em um caso, retry, rollback, histórico,
reinício do serviço e consumo em outra JVM. CURRENT foi restaurado para os
valores originais; o histórico simulado continua disponível. Esses testes não
são prova de cluster, concorrência distribuída ou SLA.

## Estudar as evidências sem confundir suas finalidades

- As evidências reais E00–E07 comprovam o volume e os produtos executados neste host.
- As fixtures inventadas testam falhas, limites de datas, nulos, relações e bloqueios sem Kaggle.
- A matriz X01–X17 liga os requisitos da expansão aos testes; T01–T24 preserva o MVP.
- A suíte completa exige integração sem skips; os wrappers contam uma vez, mesmo com vários cenários internos.

O e2e da expansão percorre RAW inventada, Bronze temporal, Silver, ABTs,
auditoria, análise e S3, com fontes dos níveis zero, um e dois. Não usa os dados
reais como resultado esperado de testes nem credenciais Kaggle.

## Atividade com conferência

Desenhe um caso com dois grupos históricos: valores 10 e 20 no primeiro e 100
no segundo. A média correta é 130/3; a média das duas médias, 57,5, está errada.
Acrescente um caso com observação de valor nulo e outro sem observações. Explique
por que ambos têm média nula, mas contagens e flags diferentes.

Depois localize a fixture desse exemplo e a guarda que impede ler labels da
reserva sem opt-in. Termine explicando por que ambos os testes podem passar e,
ainda assim, a base continuar sem aprovação point in time para ML.
