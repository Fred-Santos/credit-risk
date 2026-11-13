# Catálogo de decisões Silver — F03.1

Revisado em 12/11/2026. Esta entrega cataloga e mede hipóteses; **ainda não
materializa Silver**. Política planejada em
[silver_policy_v1.yaml](../../configs/silver_policy_v1.yaml). A implementação
será feita em F03.2–F03.6, com contratos e testes próprios.

## Como localizar a proposta original

Atualização F03.2/F03.3: o [leitor lógico](LEITURA_BRONZE.md) e os
[tratamentos com guardas](TRATAMENTOS.md) foram implementados e validados.
As 23 datas foram convertidas no recorte, com demais valores preservados.
Atualização F03.4: as três tabelas já foram [persistidas em Delta](DELTA_INICIAL.md),
com aceite Silver completo ainda pendente. O restante desta página preserva a
revisão de decisões feita em F03.1.

Fonte: [analise_silver.ipynb](../../notebooks/analise_silver.ipynb), preservado.
[INVENTARIO_NOTEBOOK.json](INVENTARIO_NOTEBOOK.json) indexa todas as **236 células**,
com índice a partir de zero, ID, hash do source, seção e proposta por campo.
Há **554 linhas de propostas de schema**, sendo **223 no MVP**: 214 campos de
negócio e os três metadados descritos em cada tabela no notebook. O metadado
`ingest_batch` é adicional no layout atual e também deverá ser preservado.

O inventário registra decisões por campo. Não replica outputs antigos nem usa
execution_count como identificação: células podem ser executadas fora de ordem.
Os 17 grupos lógicos do notebook foram catalogados; apenas três entram no MVP.

## Decisões aplicáveis às três tabelas

| ID | Proposta / localização no notebook | Evidência atual | Decisão e destino |
|---|---|---|---|
| S01 | Spark local[1]/3g e path Windows, células 2–3/22 | Configuração atual centralizada e namespaces por seleção | Substituir por RunContext/configuração compartilhada e gate; F03.2/F03.6 |
| S02 | Prefix glob e unionByName com allowMissingColumns, célula 5 | Contrato fixa tabelas/shards e schemas completos | Não migrar essa função. Carregamento explícito, sem preencher coluna ausente; F03.2 |
| S03 | date_decision → date, célula 19 | 50.000 linhas, zero datas não ISO/ilegíveis | Aprovar conversão planejada com contagem de perda e falha se >0; F03.3 |
| S04 | 7 datas do histórico e 15 da estática → date, células 34/178 | Zero inválidas/não ISO no recorte nas 22 colunas | Aprovar com mesma guarda; preservar nulos originais; F03.3 |
| S05 | MONTH/WEEK_NUM/target/num_group1 → int, células 19/34 | Tipos bigint corretos; reduzir largura não é necessário ao produto | Manter bigint na Silver inicial; casts de estreitamento adiados |
| S06 | Quatro contagens double → int no histórico; 64 na estática, células 34/178 | Zero frações e valores fora de int32 nessas candidatas no recorte | Manter double por ora. Perfil amostral não garante valores futuros nem justifica migração em massa |
| S07 | Substituir 99/999/9999/.../-1 por null, células 11/27/168 e análises 34/178 | Valores ocorrem, mas ocorrência não prova ausência ou erro | Não aplicar mapa genérico nem imputação. Preservar valores; evidência semântica por campo exigida para revisão |
| S08 | -1 → null em dez métricas, célula 178 | A mesma análise reconhece negativos; definição local menciona pagamento antes/depois do vencimento | Rejeitar a inferência de sentinela. Preservar -1 e outros negativos; registrar hipóteses sem afirmar causa de cada registro |
| S09 | a55475b1 → null em códigos *M, células 34/178 | Código frequente e hexadecimal; dicionário local descreve o atributo, sem regra explícita de nulificação | Preservar token, códigos P*, Q*, outros formatos e strings de sondagem. Regex é descrição, não validade de negócio |
| S10 | Drop de dez constantes na estática, célula 178 | Todas têm 1 valor distinto não nulo; nove também têm nulos | Não remover campos na Silver. Nulabilidade pode variar e a fonte pode mudar; seleção para análise será específica em Gold |
| S11 | Preservar null, inclusive boolean, células 34/178 | isdebitcard_527L distingue true/false/null no recorte | Aprovar preservação. Não preencher false, zero ou média; F03.3 |
| S12 | Unicidade, chaves compostas e ausência de deduplicação, células 13/29/170 e análises | Bronze reconciliada, sem chaves duplicadas/nulas | Validar novamente após leitura/tratamento; falhar em violação. Eventos têm grão próprio; F03.2/F03.5 |
| S13 | Left join de histórico com base por case_id, célula 34 | Histórico tem várias linhas por caso e cobertura parcial | Manter tabelas Silver separadas. Agregar histórico ao grão do caso antes do join da ABT em F06 |
| S14 | Métricas, approx_count_distinct e show | Diagnósticos exploratórios; cardinalidade aproximada não prova unicidade/constância | Manter como observabilidade/profiling, sem decisões destrutivas automáticas |
| S15 | Target desbalanceado/SMOTE/modelagem, célula 19 | Produto é análise retrospectiva, ML fora do MVP | Preservar target e distribuição; não reamostrar nem usar target para seleção de linhas |
| S16 | Inferir significado pelo sufixo *L/*P/*A/*M, células 34/178 | Há categorias *L, saldos fracionários e códigos ofuscados | Dicionário e perfil por coluna precedem regra. Manter doubles monetários; conversão para decimal exige projeto específico de precisão |

As listas completas de datas estão no YAML; as listas de int/drop/-1/*M da
estática foram extraídas para o inventário. As propostas por campo das células
19, 34 e 178 estão todas classificadas. Famílias S07–S09 prevalecem sobre qualquer
exemplo legado que proponha nulificação automática, inclusive linhas cujo texto
da tabela diz apenas “manter”. As famílias S11–S16 completam as regras que não
cabem em um mapeamento de tipos.

## O que o recorte real mostrou

Execução de leitura sobre a Bronze aprovada, sem tocar nos arquivos de dados.
Os números abaixo se referem ao recorte de 50 mil casos, não à fonte inteira.

| Observação | Resultado |
|---|---|
| Datas candidatas | 23 colunas; nenhuma data preenchida inválida/não ISO |
| avgdbddpdlast24m_3658932P | 24.272 negativos, incluindo 2.411 valores -1; não presumir erro |
| avgoutstandbalancel6m_4187114A | 433 negativos e 18.520 fracionários; não converter em contagem ou truncar |
| annuity_853A | 9 valores iguais a 999 e 1 igual a 9999; frequência não comprova sentinela |
| profession_152M | 212.967 linhas com a55475b1, 2.417 com formato P e 6 com formato Q |
| bankacctype_710L | 1 valor distinto preenchido e 36.170 nulos |
| isdebitcard_729L | 6.350 false, nenhum true e 43.650 nulos; não é uma constante se a ausência importa |
| isdebitcard_527L | 3.472 true, 11.916 false e 200.002 nulos |

`countDistinct` ignora null. Por isso, “1 distinto” não significa “a mesma
informação em todas as linhas”. Aproximações também não devem comprovar chave.
O notebook usa `.distinct().count()` na inspeção de formatos: ali a contagem é
de **valores distintos**, embora a análise textual às vezes diga ocorrências.
No novo relatório, as sondagens contam linhas. Não comparar essas unidades como
se fossem a mesma métrica.

Não atribuímos um significado de ausência ao token a55475b1 só porque ele é
frequente. Seu uso futuro como categoria analítica, “desconhecido” ou ausência
requer evidência adicional e política explícita. Preservá-lo mantém a decisão
reversível e evita aumentar artificialmente os nulos.

## Evidência semântica e limitações

`data/raw/feature_definitions.csv` é a referência local adquirida com a fonte.
Para `avgdbddpdlast24m_3658932P`, descreve dias antes/depois do vencimento; o
notebook dizer que DPD nunca é negativo não sustenta remover -1 nesse campo.
Para `avgoutstandbalancel6m_4187114A`, descreve saldo médio, sem proibir negativos.
Para `profession_152M`, descreve profissão na aplicação anterior, sem oferecer
decodificação dos tokens. Essas descrições justificam preservar, não inventar
o significado de cada valor.

A inspeção não comprova disponibilidade dos auxiliares no instante da decisão.
Converter uma string para date não resolve vazamento temporal. A análise inicial
continua retrospectiva; checagens temporais entre tabelas pertencem ao desenho
analítico e aos contratos posteriores. “Data válida” também não é “data plausível
para qualquer finalidade”.

Os ranges dos candidatos a int foram observados apenas no recorte. Conservar
os tipos evita uma redução desnecessária. Se futuramente houver estreitamento,
medir frações, overflow, NaN e perdas, com falha explícita em cada nova carga.

## Tabelas catalogadas fora do MVP

Todos os campos e propostas originais destas tabelas estão no inventário com
`deferred_outside_mvp`. Não baixar dados adicionais nem habilitar transformações
destas fontes nesta entrega.

| Tabela | Célula de análise | Propostas registradas / condição para retomar |
|---|---|---|
| train_applprev_2 | 44 | Cast de grupos, a55475b1 → null, chave tripla; revisar schema/semântica se entrar no escopo |
| train_credit_bureau_a_1 | 60 | Datas, int, sentinelas numéricas/datas 1900/2098 e códigos, preservar pares; exigir contrato e evidência |
| train_credit_bureau_a_2 | 71 | Grupos/mês/ano, sentinelas, chave tripla e anos futuros; revalidar sem inferir erro por calendário |
| train_credit_bureau_b_1 | 85 | Datas/int, mapas incompletos de sentinelas e pares de periodicidade; sem consolidação automática |
| train_credit_bureau_b_2 | 96 | Data de pagamento, grupos, sentinelas, chave tripla |
| train_debitcard_1 | 111 | Data/int, 999/9999 em movimentação; ocorrência exige evidência semântica |
| train_deposit_1 | 126 | Datas/int e nulos de encerramento; não inferir conta aberta apenas pelo null |
| train_other_1 | 139 | Grupos e sondagens monetárias 9999/99; não reduzir chave porque grupo observado é constante |
| train_person_1 | 151 | Datas/int, códigos, candidatos a drop/filtro por idade; não filtrar pessoas sem requisito de negócio |
| train_person_2 | 163 | Emprego, grupos e códigos, chave tripla |
| train_static_cb_0 | 192 | Drop de constantes, datas/int, datas sentinela, valores e regex de códigos; revalidar todas as hipóteses |
| train_tax_registry_a_1 | 206 | Data/grupo, valores monetários e formatos de empregador |
| train_tax_registry_b_1 | 221 | Data/grupo, valores monetários, hex/P; não inferir autoridades distintas só pela baixa sobreposição |
| train_tax_registry_c_1 | 234 | Data/grupo, valores monetários e Q → null; não declarar token inútil por formato |

As sugestões de join por case_id dessas fontes ficam para projeto analítico
específico, respeitando grão e cardinalidade. A existência de grupos diferentes
ou baixa sobreposição não prova sua causa operacional. Hipóteses sobre sistemas,
autoridades fiscais ou janelas de reporte permanecem hipóteses.

## Problemas de execução do notebook

Nove células markdown contêm blocos Python com erro sintático: 34, 60, 71, 85,
96, 192, 206, 221 e 234. Há mapas sem valores e `for val in :`. Não são código
pronto para migrar. Path Windows, variáveis reutilizadas (`total`, `df`) e estado
de sessão também impedem usá-lo como orquestrador. O inventário registra erros
por bloco, sem executar o notebook ou suas transformações.

## Critérios para as próximas implementações

F03.2: leitor deve conferir gate e hashes, mapear tabelas explicitamente e
validar schema/chaves sem completar colunas ausentes. F03.3: converter só as
datas aprovadas, contar preenchidos que viram null, preservar demais valores,
tipos, colunas e metadados. Falha bloqueia publicação; não há descarte silencioso.
F03.4: materializar três tabelas Delta preservando seus grãos. F03.5: validar
chaves, referências, domínios e perdas. F03.6: executar sem depender do notebook.

Nenhuma dessas implementações posteriores é marcada concluída por este catálogo.
