# Registro de decisões — Credit Risk Lakehouse

Atualizado em 12/11/2026. Projeto afetado em todas as entradas: `credit-risk`.
Status da decisão não equivale a implementação ou validação.

| ID | Decisão | Status | Motivo e alternativas | Pendência / próximo passo |
|---|---|---|---|---|
| D01 | Priorizar engenharia e análise retrospectiva de crédito | Aprovada pelo usuário | Portfólio de Engenharia e Análise; alternativa seria manter ML como centro | Executar o escopo funcional |
| D02 | Gold com ABT, indicadores e análises de consumo | Aprovada pelo usuário | Entregar detalhe e interpretação; alternativa seria encerrar na Silver | Confirmar grão e campos da fonte adotada |
| D03 | Usar Spark/PySpark e Delta como formato inicial único | Aprovada pelo usuário | Aproveitar código e demonstrar transações; Iceberg seria alternativa por requisito específico | Validar versões e ambiente |
| D04 | Preservar trabalho RAW/Bronze e adaptar incrementalmente | Aprovada pelo usuário | Evitar reescrita sem necessidade; converter tudo de início ampliaria risco | Adaptar aquisição/contratos se houver nova fonte |
| D05 | Identificar replay, correções e atrasos simulados | Aprovada pelo usuário | Arquivos estáticos não são CDC; alternativa seria buscar fonte com mudanças reais | Definir lotes e precedência |
| D06 | Provar Delta no filesystem e depois integrar objetos locais | Aprovada pelo usuário | Validar em etapas; alternativa seria iniciar toda a infraestrutura junta | Selecionar serviço e garantir commit/publicação no destino |
| D07 | Adiar ML, feature store, retreinamento e AWS | Aprovada pelo usuário | Foco e conclusão da entrega local; alternativas ficam no backlog | Revisar após aceite do MVP |
| D08 | Revisar alcance da divulgação externa Home Credit | Atualizada por D10 | A redação anterior impedia todo processamento; foi corrigida após esclarecer participação na competição | Revisar antes de publicar dados ou derivados |
| D09 | Manter Home Credit; não adotar substituta | Atualizada por D10 | Preservar fonte e trabalho existente | Seguir o escopo de D10 |
| D10 | Usar dados reais Home Credit na ABT/análises e fixtures somente nos testes | Aprovada pelo usuário; aquisição e inspeção inicial executadas | Inscrição informada e acesso autenticado confirmado | Fechar contratos e recorte; revisar divulgação externa antes de publicar |
| D11 | Ambiente nativo isolado Linux/WSL: Python 3.11.14, Java 17, Spark 3.5.7 e Delta 3.3.2 | Implementada e validada na prova inicial | Matriz compatível e aproveitamento do código; alternativa Docker adicionaria serviço sem necessidade nesta fase | Revalidar com recorte real e armazenamento de objetos nas etapas seguintes |
| D12 | Contrato v1 para snapshot RAW/recorte, com edição fixada e schema completo | Definida e implementada na execução autorizada | Bloquear mudanças silenciosas; alternativa de aceitar colunas ausentes/novas automaticamente foi descartada | Contratos de eventos/revisões e Silver continuam posteriores |
| D13 | Até 50 mil casos por SHA-256 de seed fixa e case_id; preservar relacionados | Definida e implementada na execução autorizada | Repetibilidade e limite de recursos; primeiras linhas ou amostragem por fração não atendem ao mesmo controle | Reavaliar volume após medir o fluxo completo; manter coorte fixa no experimento |
| D14 | Três lotes simulados por WEEK_NUM: 0–51, 52–77 e 78–91 | Definida e validada na atribuição | Calendário contíguo e explícito; não pressupor chegadas reais | Implementar entrega dos lotes e revisões em F04 |
| D15 | Recorte imutável em pasta separada, publicado após checks e reconciliação | Implementada e validada no filesystem local | Preservar RAW e detectar alteração de saídas; alternativa de sobrescrever o recorte foi descartada | Entrada Bronze adaptada; rever garantias para objetos em F08 |
| D16 | Entrada Bronze explícita por seleção ou modo RAW, com namespaces e relatórios separados | Implementada e validada na execução autorizada | Preservar origem/configuração e evitar mistura de coortes; alternativa de trocar globalmente data.raw foi descartada | Usar o namespace aprovado no consumo Silver |
| D17 | Manifesto de arquivo v2 com checksums de saída e gate local _READY após validações | Implementada e validada no filesystem local | Reconhecer commits no retry e impedir aprovação da execução parcial | Contrato de revisões, regras e reconciliação completa seguem em F02.4–F02.6; publicação entre tabelas Delta em F05 |
| D18 | Contrato de eventos separado, com chave de negócio, evento por revisão e entrega por lote/posição | Implementada e validada em F02.4 | Manter repetições auditáveis; conflito na mesma revisão rejeita o lote, inclusive em versões antigas | Gerador completo e merge Silver seguem em F04; não há CDC real na fonte |
| D19 | Landing local imutável JSONL para pequenos pacotes de referência, isolada por seleção/stream | Implementada e validada com linhas reais e correção declarada | Testar o protocolo sem reescrever RAW/snapshot ou ocupar os IDs dos lotes completos | Leitura integral em memória não atende ao replay completo; adaptar transporte/validação distribuída em F04 e storage em F08 |
| D20 | Derivar qualidade Bronze do contrato congelado, somando metadados técnicos; histórico vazio permitido com schema | Implementada e validada em F02.5 | Evitar schemas divergentes e distinguir ausência legítima de observações de carga ausente; eventos mantêm grão próprio | Qualidade não prova igualdade de valores: reconciliação completa em F02.6 |
| D21 | Reconciliar multiconjuntos por exceptAll nos dois sentidos, sem casts, e auditar proveniência antes do gate | Implementada e validada em F02.6 | Detectar mudanças de valor/multiplicidade que qualidade e contagens não detectam; RAW selecionada e recorte comparados à Bronze | Igualdade de valores Spark e checksums físicos têm funções distintas; merge Silver e ABT seguem posteriores |

D10 atualiza D08/D09 após a informação sobre inscrição: mantém Home Credit e
separa desenvolvimento da revisão de divulgação externa. Não houve troca de
dataset nem envio da solicitação. D01–D07 permanecem válidas; as alternativas
UCI ficam apenas como referência histórica.

D22 — F03.1: a Silver inicial preservará todos os campos, valores e tipos
numéricos do snapshot, incluindo códigos, nulos e negativos. Não aplicar
sentinelas por aparência nem remover colunas por cardinalidade. Planejar somente
conversões das 23 datas com guarda de perda. Decisão registrada em
[catálogo Silver](silver/CATALOGO_REGRAS_SILVER.md) e no YAML da política;
perfil real validado, implementação ainda em F03.2–F03.6. Uma futura mudança
semântica exigirá evidência e revisão explícita da política.

Detalhamento funcional: [ESCOPO_PRODUTO.md](ESCOPO_PRODUTO.md).

D23 — F03.2: consumir a Bronze aprovada por gerenciador de contexto, mantendo o
lock local do produtor durante as ações Spark e revalidando artefatos ao sair.
Leitura explícita de cada fragmento, schema completo antes da união e chave
global depois; sem união permissiva. Implementada e validada com dados reais
e testes negativos. O lock exige cooperação local e não fornece isolamento
distribuído; o consumidor deve executar dentro do `with`.

Controle de execução: [ROTEIRO_EXECUCAO_LAKEHOUSE.md](ROTEIRO_EXECUCAO_LAKEHOUSE.md).

D24 — F03.3: executar apenas as 23 conversões de datas aprovadas, exigindo formato
ISO, parse válido e equivalência de ida e volta. Qualquer perda de preenchido
bloqueia o snapshot inteiro, com métricas e sem descarte/quarentena automática.
Comparar todas as colunas com a Bronze após restaurar a representação das datas,
preservando valores, tipos restantes, nulos, grãos e metadados. Implementada e
validada no recorte real; gravação Delta continua em F03.4.

D25 — F03.4: materializar um pacote inicial imutável por identidade de entrada,
política, código e runtime. Gravar três tabelas Delta independentes, registrar
UUIDs/versões e reconciliar a leitura antes de publicar por rename local. Retry
verifica e reutiliza, sem overwrite ou novo commit. O manifesto é técnico,
com status de aceite Silver pendente; não equivale a transação Delta global
nem a autorização para iniciar Gold. Implementada e validada com o recorte real.

D26 — F03.5: compilar o contrato Silver a partir do snapshot e política fixados,
sem aceitar o manifesto do writer como única definição de schema. Validar o
estado persistido por Delta, com grãos, chaves, nulos, domínios e referências.
Estática exige cobertura completa e 1:1; histórico admite ausência e 0:N linhas
por caso. Índice num_group1 não negativo, sem teto derivado da amostra. Datas
auxiliares posteriores à decisão são diagnóstico, sem exclusão automática ou
promessa point-in-time. Implementada e validada com 29 checks reais aprovados;
aceite operacional segue em F03.6.

D27 — F03.6: consolidar leitura, transformação, criação/reutilização e contratos
em `run_silver_initial`, com `--sample` obrigatório e `--existing reuse|error`.
Registrar um recibo imutável por execução aprovada, separado do pacote técnico e
vinculado ao relatório por hash. Conferir estabilidade de código/configuração
antes do aceite. Falha preserva pacotes e aceites anteriores; retry revalida os
dados antes de reutilizar. Não há ponteiro `latest`: publicação histórica entre
gerações e camadas continua em F05. Implementação e operação em
[EXECUCAO_INICIAL.md](silver/EXECUCAO_INICIAL.md); resultados em
[F03_EXECUCAO_SILVER.md](evidencias/F03_EXECUCAO_SILVER.md).

D28 — F04: transportar o replay completo em Parquet tipado, com envelope v1
achatado e metadados Bronze preservados. Executores usam o mesmo
`make_event`/`validate_event` da referência para os hashes canônicos; não há
troca silenciosa por JSON Spark. Ordenar somente as chaves e usar `zipWithIndex`
evita coletar payloads ou concentrar a tabela larga numa janela global.

D29 — F04: isolar o experimento por identidade de seleção, gate Bronze, código,
política e runtime. O estado incremental começa vazio e não altera os pacotes
F03. Um caso do primeiro lote é retido com suas auxiliares para chegada tardia;
outro recebe duas correções declaradas de +1.0, uma em cada auxiliar.

D30 — F04: maior revisão vence, independentemente de chegada. Conflito na mesma
chave/revisão rejeita o lote inteiro, inclusive em revisão antiga já suplantada.
Entregas da mesma revisão também precisam concordar na proveniência Bronze.
Somente após essa concordância, `delivery_id` crescente desempata duplicatas.
Ausência em pacote parcial preserva linhas; não há exclusão inferida.

D31 — F04: estado Delta guarda negócio, proveniência Bronze e identidade/revisão
do evento; contexto de entrega permanece na landing. Merge insere chaves novas
e atualiza apenas revisão maior. Candidatos são tratados antes das escritas;
sem inserts/updates, nem o commit vazio é executado. Métricas planejadas são
conferidas com o commit real e os contratos persistidos após cada lote.

D32 — F04: reconstruir pelo máximo de revisão agrupado por chave, join e distinct
do estado, sem reutilizar a janela ou o merge incremental. Comparar todas as
colunas nos dois sentidos. Diagnósticos mensais e de cobertura só verificam
idempotência nesta fase; indicadores Gold continuam em F06. Publicação global,
evolução e prova completa de recuperação continuam em F05.

Detalhamento de F04: [Silver incremental](silver/INCREMENTAL.md).

D33 — F05: evoluir cópias gerenciadas para Silver v2 mediante contrato fixado
por hash. Adicionar somente `_silver_contract_version int`, preencher 2 e provar
preservação das colunas anteriores. Schema ausente, incompatível ou extra falha;
nenhuma mudança automática no estado F04 ou na Silver inicial F03.

D34 — F05/F06: publicar manifestos imutáveis de versões Delta aprovadas e trocar
CURRENT atomicamente no filesystem POSIX. Lock exclusivo local, intentos e
metadados de commit permitem retomar escritas privadas. Consumidor verifica o
conjunto e faz ações sob contexto; blobs de código/configuração preservam
proveniência histórica mesmo após mudanças no código de trabalho. Não é uma
transação global entre tabelas ou garantia para objetos. [Protocolo](PUBLICACAO_E_RECUPERACAO.md).

D35 — F05: retenção Delta de 30 dias e pins indefinidos de publicações e entradas.
Sem VACUUM real enquanto houver versões publicadas; qualquer retirada futura
exige procedimento explícito. A prova de perda histórica usa somente uma
fixture temporária criada internamente, sem aceitar caminho externo.

D36 — F06: ABT retrospectiva com uma linha por caso, histórico completo agregado
antes de joins, valores opcionais preservados e flags de cobertura distintas
da completude. Não há janela point-in-time comprovada. Soma double em ordem
estável por num_group1 evita depender da ordem física, sem arredondamento.
Oráculo SQL independente admite pequena tolerância aritmética; comparação
incremental/integral exige igualdade exata. [Contrato](contratos/ABT.md).

D37 — F06: comparar as três Silver para selecionar casos afetados, copiar ABT
pai para saída privada e aplicar MERGE apenas às derivações diferentes. A cópia
tem custo físico explícito e preserva versões anteriores. Indicadores mensais
têm poucos grupos e são materializados integralmente por SQL após cada merge;
assim períodos antigos são recalculados e grupos vazios deixam a saída. Validar
numeradores e denominadores diretamente na Silver. A manifestação analítica
fixa três Silver e duas Gold; falha privada não altera a publicação aprovada.
Operação: [ABT e indicadores](gold/ABT_E_INDICADORES.md).

D38 — F07: separar consumo de transformação. O relatório exige três publicações
analíticas explícitas, verifica seleção/contrato/cadeia de pais e lê versões
aprovadas sem alterar tabelas ou CURRENT. SQL independente reconcilia os
indicadores e segmentos; só agregados e diferenças limitadas chegam ao driver.

D39 — F07: comparar correção com os mesmos IDs, datas, semanas e rótulos. Chegada
tardia muda a população e é apresentada em outra comparação. Os indicadores
mensais v1 podem permanecer iguais quando a correção altera somente montantes;
a prova de propagação também compara as colunas da ABT por caso.

D40 — F07: relatório offline HTML/Markdown, CSVs e PNG/SVG com Matplotlib,
dependências isoladas e fixadas em requirements.analysis.lock. Não mudar o lock
Spark já aprovado para acrescentar gráficos. Bundles por execução registram
proveniência/aceite; semantic.json e gráficos estáveis permitem verificar
reprodução em processos novos. Não é necessário dashboard para aceitar a fase.

D41 — F07: sinais n<500 e target=1<20 orientam a leitura, sem ocultar grupos ou
alegar significância. Limites observados de datas sinalizam janela parcial,
sem inferir perda na origem. Cobertura, completude, maturação não auditada,
recorte e disponibilidade temporal são explicitados antes da interpretação.
Método e conclusões em [análise](analise/RESULTADOS.md).

D42 — F08: SeaweedFS 4.53 Apache 2.0 nativo em loopback, com binário verificado
por SHA-256, autenticação privada e estado persistente ignorado pelo Git.
Garage foi considerado; MinIO Community estava arquivado na consulta. A escolha
prioriza a operação local e as provas executadas, sem alegar teste dos demais.
[Alternativas e fontes](objetos/DECISAO_E_ARQUITETURA.md).

D43 — F08: fábrica Spark separada, Hadoop S3A 3.3.4 e AWS SDK 1.12.262 fixados;
S3SingleDriverLogStore, um host/driver escritor cooperante. Controle de exclusão
fica local; objetos de dados e publicação usam API/chaves, sem rename POSIX.
Manifestos imutáveis, hashes e PUT condicional de CURRENT preservam a publicação
anterior durante falhas privadas. ETag controla a precondição; SHA-256 confere bytes.
Não estender essa prova a múltiplos hosts/JVMs ou equivalência completa AWS.

D44 — F08: conservar filesystem como referência e espelhar entradas por SHA;
executar replay/MERGE/reconstrução nativamente em Delta S3A e depois derivar
Silver v2/Gold em prefixos privados. Comparar todas as tabelas com F04/F06.
Manter o relatório F07 ligado às publicações locais originais; consumo S3 usa
seu leitor explícito. Parada preserva backend; remoção validada só em fixture
internamente criada. Retenção 30 dias/pins indefinidos, sem VACUUM real.
[Provas e recursos](evidencias/F08_OBJETOS.md), [operação](objetos/OPERACAO.md).

D45 — F09.1: separar execução operacional das demonstrações que injetam falhas.
Usar update até lote explícito, replay idempotente e rebuild isolado por run_id,
com entradas locais aprovadas e registry operacional separado de F08. Validar
reconstrução antes de publicar; neste comando a Gold é materializada integralmente.
Recusar limite anterior ao estado consumido. A preparação de entradas permanece
nos comandos existentes; não há ingestão CDC. [Operação](operacao/COMANDO_UNICO.md)
e [evidência F09.1](evidencias/F09_COMANDO_UNICO.md).

D46 — F09.2: supervisionar a operação inteira, incluindo configuração e
inicialização, com operation_id estável e run_id por tentativa de processamento.
Retentar somente falhas temporárias reconhecidas, até três tentativas; não
repetir contrato inválido, fonte ausente, acesso negado, conflito ou erro desconhecido.
Preservar o erro primário e bloquear retry quando o encerramento falhar.
Um código não zero após ativação não significa rollback automático.
[Estados/erros](operacao/ESTADOS_E_ERROS.md) e
[evidência](evidencias/F09_ESTADOS_E_ERROS.md).

D47 — F09.3: medir durações com relógio monotônico, preservando horários UTC
para rastreio. Separar operação, tentativa e executor; somar intervalos exclusivos
e registrar esperas/cleanup. Reutilizar contadores conferidos com commits, sem
novos counts Spark para a consolidação. Distinguir entregas de linhas finais,
objetos de arquivos e marcadores S3A, bytes retidos de tráfego/escrita nova.
Amostragem RSS Linux inclui processo/descendentes, com custo e limites declarados.
Janela de coleta inclui guarda final da entrada; etapas dos componentes mantêm
validações embutidas, sem alegar tempo puro de transformação ou overhead isolado.
[Métricas](operacao/METRICAS.md), [evidência](evidencias/F09_METRICAS.md).

D48 — F09.4: auditar uma operação/publicação explícita por leitura, conferindo
relatórios, coorte, lotes/recibos, espelho e tabelas Delta. Separar run de consumo,
audit_run_id e tentativas aprovadas de criação observadas nos logs locais.
Mapear colunas Gold explicitamente, fixando a implementação conhecida e
rejeitando modelo desconhecido; não alegar parser SQL, autoria assinada ou catálogo
global de acessos. F07 continua ligado ao filesystem F06. Inventário estável por
identidade, com arquivo novo por auditoria. [Operação](operacao/LINEAGE_E_INVENTARIO.md)
e [evidência](evidencias/F09_LINEAGE.md).

D49 — F09.5: resumo pontual independente dos produtores, separando última
execução conhecida de publicação aprovada observada. Não iniciar S3 nem usar
cache como comprovação de CURRENT. Diferenciar metadados de leitura Delta e
aprovação de qualidade armazenada de nova computação SQL. Limites iniciais de
2× duração e 1,5× RSS derivam de baselines F09.3 fixadas por hash, somente para
modo/lote/coorte comparáveis; não são SLA nem bloqueiam cargas. Consultas sem
verificação nova geram relatório inclusive com avisos; verificação requerida
e indisponível retorna 1. [Operação](operacao/RESUMO_OPERACIONAL.md) e
[evidência](evidencias/F09_RESUMO_OPERACIONAL.md).

D50 — F09.6: testar fluxo completo em namespace S3 descartável com entradas
locais aprovadas. Injetar defeitos na saída privada do produtor e interrupção
real após commit, mantendo validadores/oráculos reais. Classificar exceções
Silver/Gold como quality_rejected (3, sem retry), preservar seu relatório e
ligar tentativa ao run_report por hash. Isolar relatórios da matriz do histórico
normal, confinados ao repositório. Rebuild mantém operação lógica no retry.
Não exigir Home Credit na CI: o ensaio local é separado e F10 usará fixtures
sintéticas. [Matriz](operacao/MATRIZ_OPERACIONAL.md),
[evidência](evidencias/F09_MATRIZ_OPERACIONAL.md).

D51 — F10: catalogar responsabilidades sem renomear testes vinculados às
evidências. Exigir integração sem skips, matriz T01–T24 completa e e2e sintético
com oráculo manual. CI usa fonte exportada, dependências fixadas e upload por
lista fechada, sem Kaggle. Preservar notebook histórico; limpar outputs e
recalcular referências somente na cópia, com manifesto dos dois hashes.
A configuração remota não equivale a uma execução no GitHub.
[Execução e CI](testes/EXECUCAO_E_CI.md).

D52 — F10.5: selecionar metadados do lote antes da leitura tipada S3A. Manter
verificação do espelho completo, contratos e reconstrução; conferir igualdade
das cinco tabelas em namespace temporário. Uma medição por variante, sem
aumentar recorte, cache, paralelismo ou partições; ganho observado não é SLA.
[Aceitação F10](evidencias/F10_ACEITACAO.md).

D53 — F11: apresentar o produto por problema, contratos, execução e limites,
com demo curta de Silver tipada inventada e prova RAW→S3 separada no e2e F10.
Executar publicação, commit privado, retomada e leitura histórica com S3/Delta
reais; gráficos derivados dos CSVs consultados. Não confundir mock de falha com
substituição de validador. Preservar outputs históricos e seus hashes originais.

D54 — F11: distribuir um pacote local de código sanitizado, documentação
selecionada e resultados inventados, com inventário por hash. Não incluir dados
Home Credit, relatórios reais individuais, logs, runtime ou credenciais. Declarar
autorrevisão por comandos, sem avaliador externo ou job remoto. Encerrar escopo
local sem pressupor commit/tag, push, divulgação externa ou recursos AWS.
