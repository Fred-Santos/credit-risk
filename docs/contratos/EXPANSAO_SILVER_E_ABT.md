# Contratos da expansão Home Credit — E03, E04 e E05

Escopo: todas as 17 tabelas de treino e casos decididos em janeiro–setembro/2020.
Os produtos ficam em namespaces `expansion`, sem substituir os contratos e
publicações de três tabelas do MVP. A ativação S3/CURRENT ampliada pertence à E07.

## Silver

Norma executável: [expansion_silver_v1.yaml](../../configs/contracts/expansion_silver_v1.yaml).
Cada tabela conserva o grão original: caso para nível zero, caso/num_group1
para nível um e caso/num_group1/num_group2 para nível dois. Esses índices são
chaves do snapshot; não são identidade financeira de empréstimo nem identidade
global de pessoa. O mapeamento entre tabelas é explícito, sem inferência de
schema ou união permissiva de shards.

As 58 datas enumeradas no contrato são convertidas de ISO para `date` apenas
com roundtrip sem perda. Outros tipos, nulos, códigos e valores são preservados.
Não há imputação, substituição de sentinelas ou deduplicação silenciosa.
Chaves nulas/negativas/duplicadas, casos órfãos, números não finitos e rótulos
fora de 0/1 bloqueiam o pacote inteiro. A estática principal exige cobertura
completa; as demais auxiliares podem faltar para um caso.

A entrada Bronze e os bytes de saída são conferidos por SHA-256. Após auditar
unicidade em ambas as entradas, a reconciliação faz full outer join pelas chaves
e compara cada célula com igualdade null-safe, incluindo proveniência. Assim,
não depende de hashes de linha para aprovar igualdade. Não há tolerância
numérica nesta transformação sem agregações. Os pins guardam UUID, versão,
schema e contagem de cada Delta. O pacote só aparece após a aprovação conjunta.

Rejeições não são descartadas: a entrada permanece na Bronze. O comando
`scripts/diagnose_expansion_source.py --bronze-id ID --table TABELA` registra
chave, arquivo original e regras infringidas em artefato privado, com registros
rejeitados em Parquet. Ele não corrige nem aprova uma Silver automaticamente.

## Revisões e dependências

O protocolo de `src/expansion/revisions.py` aceita full-row upserts tipados em
qualquer tabela contratada, com revisão positiva e simulação declarada. Reenvios
idênticos são idempotentes; payloads divergentes na mesma chave/revisão do lote
ou da revisão vigente bloqueiam a escrita. A maior revisão vence; eventos
ultrapassados não modificam o estado. A v1 não implementa exclusões nem entrada
de casos fora da coorte fixada; novas observações auxiliares de casos existentes
podem ser inseridas. Não há alegação de CDC real ou estabilidade de índices
entre extrações externas independentes.

O pai é imutável. Tabelas alteradas são copiadas para namespace privado e
recebem MERGE; tabelas inalteradas mantêm pins do pai. A cadeia de manifestos
é verificada. Uma reconstrução por anti-join + union confere o resultado do
MERGE. Casos afetados ficam em Parquet; os períodos antigos e novos são
registrados, inclusive quando apenas uma auxiliar muda. Alteração de data da
base recalcula a composição das janelas. Não há cópia tácita sobre o MVP.

## Atributos e temporalidade

Seleção fixa: [expansion_features_v1.yaml](../../configs/expansion_features_v1.yaml).
Contrato de saída: [expansion_gold_v1.yaml](../../configs/contracts/expansion_gold_v1.yaml).
O [catálogo de campos de origem](../../configs/contracts/expansion_feature_sources_v1.yaml)
classifica todos os campos como chave, metadado, rótulo, selecionado retrospectivo
ou preservado apenas na Silver, com justificativa. Seleção por significado e
engenharia precede qualquer modelagem e não usa correlação com rótulos da reserva.

As 16 auxiliares contribuem com 166 atributos: presença, observações, grupos,
valores diretos selecionados, atributos do solicitante, estatísticas numéricas,
intervalos de datas e moda categórica. Nenhuma tabela histórica é ligada crua
à base. Nível dois é agregado por caso/grupo e depois por caso; médias são
ponderadas por quantidades não nulas. Um SQL independente calcula AVG e
COUNT(DISTINCT grupo) diretamente na fonte para conferir essa ponderação.

Em pessoas, atributos do solicitante usam somente índice zero; registros de
outras pessoas não substituem esse valor. A moda ignora nulos e desempata pela
ordem lexical do código. Ausência gera contagens zero e flags false; medidas
sem observações preenchidas permanecem nulas. Zero observado permanece zero.
Montantes transformados não são declarados moeda, dívida atual ou exposição.
As médias double admitem tolerância absoluta 1e-8 mais relativa 1e-10 no oráculo;
contagens, categorias, datas e readback dos produtos exigem igualdade.

A [descrição oficial da competição](https://www.kaggle.com/c/home-credit-credit-risk-model-stability/data)
identifica `case_id` como caso de crédito, distingue os níveis dos índices e
informa que o rótulo é determinado após um período. Os campos são destinados
à predição na competição, mas essa descrição não fornece a duração de maturação
nem um timestamp histórico de disponibilidade por atributo. O dicionário também
identifica transformações de datas/valores; datas futuras podem ser programadas
ou transformadas, e não constituem sozinhas prova de vazamento.

A auditoria E04 conta datas anteriores/posteriores à decisão por campo e conserva
os dados. Ela não transforma data de evento, data de aquisição ou ausência de
data futura em prova de `available_at`. O status v1 é **retrospectivo**:
`eligible_predictors=[]` e `ml_ready=false`. Nenhum campo recebe aprovação
point in time sem evidência. Tampouco se afirma que todos os campos vazam.
Os escores externos `riskassesment_*` permanecem na Silver, fora desta ABT,
pois treinamento, vintage e disponibilidade não foram demonstrados.

A data de corte seleciona casos, não fixa a data em que um modelo poderia ser
treinado. O horizonte e o instante de disponibilidade do target ainda precisam
ser conhecidos para simular esse treinamento e definir eventual embargo.
`case_id`, índices de pessoas e códigos de empregadores não comprovam identidade
global de cliente; a independência entre pessoas dos dois períodos não é alegada.

## ABTs e acesso aos rótulos

As duas ABTs são compostas por tabelas Delta de features e labels vinculadas
por `case_id`, cada uma com uma linha por caso. O mesmo contrato produz:

| Produto | Intervalo de decisão |
|---|---|
| Desenvolvimento | `[2020-01-01, 2020-06-01)` |
| Avaliação temporal | `[2020-06-01, 2020-10-01)` |

As features têm 170 colunas: quatro metadados de caso/tempo e 166 atributos.
As labels têm somente `case_id` e `target`. A ABT lógica reconstruída tem 171
colunas e o mesmo schema nos dois períodos. Não há target nas features.
Ambas são retrospectivas; não são denominadas bases aprovadas para treino.

`scripts/run_expansion.py gold` escreve blocos conferidos com SQL, valida os
joins, os limites, a disjunção e a união das populações, confere todas as
features após releitura e publica um manifesto com pins das fontes, contratos,
contagens e disponibilidade. Há zero ajuste de imputação, escala, vocabulário,
seleção supervisionada ou hiperparâmetros usando a reserva.

`open_abt` abre features por padrão. Para juntar labels de avaliação, exige
`include_labels=True, allow_evaluation_labels=True`. Essa guarda evita uso
acidental pela API; não é uma ACL que impede o proprietário local de ler os
arquivos diretamente. `open_ml_inputs` bloqueia treino enquanto o contrato não
for aprovado temporalmente. A análise de público da E06 une features
dos dois períodos sem acessar automaticamente os rótulos individuais da reserva.

## Política para a modelagem futura

Imputadores, normalizadores, codificadores e seletores deverão ser ajustados
apenas no treino de cada fold cronológico interno do desenvolvimento. O estado
será congelado para validar o restante do fold e, ao final, a reserva. As datas
dos folds, o instante simulado de treinamento e eventual embargo dependem da
maturação do target e serão definidos sem escolher pelo desempenho da reserva.
Até resolver essas dependências, nenhuma receita de treino é declarada válida.

## Aceitação dos contratos

A [matriz E08](../testes/MATRIZ_EXPANSAO.md) testa schemas equivalentes,
disjunção/reconciliação, nulos versus ausência, relações entre níveis, seleção
do solicitante e bloqueios de acesso/ML. A fixture e2e mantém propositalmente
uma data posterior à decisão e verifica que o leitor ML permanece bloqueado.
Preservar esse dado para análise retrospectiva não o aprova como preditor.
