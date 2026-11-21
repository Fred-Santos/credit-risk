# Documentação do Credit Risk Lakehouse

O projeto entrega um pipeline local de crédito com PySpark, Delta Lake e S3
compatível via SeaweedFS. O MVP usa três fontes; a expansão integra as 17
fontes lógicas de treino. Os produtos são retrospectivos e não estão aprovados
para treino preditivo. Dados reais, credenciais e saídas individuais ficam locais.

## Caminho principal

| Documento | O que permite avaliar |
|---|---|
| [Arquitetura](entrega/ARQUITETURA.md) | Componentes, fluxo e garantias |
| [Escopo do produto](ESCOPO_PRODUTO.md) | Problema, entregas e limites |
| [Decisões técnicas](DECISOES.md) | Escolhas, justificativas e alternativas |
| [Reprodução](entrega/REPRODUCAO.md) e [README principal](../README.md) | Ambiente e comandos do MVP |
| [Demonstração sintética](entrega/DEMONSTRACAO.md) | Fluxo verificável sem credenciais Kaggle |
| [Resultados da expansão](analise/PUBLICO_EXPANSAO.md) | População, indicadores e limites de interpretação |
| [Fonte e condições de uso](governance/SOURCE.md) | Acesso e restrições dos dados |

## Contratos, operação e testes

- [Contratos do MVP](contratos/README.md) e [contrato da expansão](contratos/EXPANSAO_SILVER_E_ABT.md).
- [Publicação e recuperação](PUBLICACAO_E_RECUPERACAO.md).
- [Operação S3 local](objetos/OPERACAO.md) e [comando operacional](operacao/COMANDO_UNICO.md).
- [Lineage e inventário](operacao/LINEAGE_E_INVENTARIO.md).
- [Execução dos testes e CI](testes/EXECUCAO_E_CI.md).
- [Matriz T01–T24 do MVP](testes/MATRIZ_ACEITACAO.md) e [matriz X01–X17 da expansão](testes/MATRIZ_EXPANSAO.md).

## Evidências do MVP

Os identificadores F preservam a referência às execuções históricas. Os números
abaixo descrevem o MVP e não substituem os resultados posteriores da expansão.

| Evidência | Resultado documentado |
|---|---|
| [F02 — Bronze](evidencias/F02_RECONCILIACAO_BRONZE.md) | Igualdade dos valores e rastreabilidade |
| [F03 — Silver](evidencias/F03_EXECUCAO_SILVER.md) | Persistência Delta e contratos |
| [F04 — Incremental](evidencias/F04_INCREMENTAL.md) | Correções, reenvios, atrasos e reconstrução |
| [F05 — Publicação](evidencias/F05_PUBLICACAO.md) | Versões aprovadas, retry e histórico |
| [F06 — Gold](evidencias/F06_GOLD.md) | ABT e indicadores reconciliados |
| [F07 — Análise](evidencias/F07_ANALISE.md) | Resultados e reprodução analítica |
| [F08 — Objetos](evidencias/F08_OBJETOS.md) | Delta/S3A, recuperação e persistência |
| [F09 — Operação](evidencias/F09_MATRIZ_OPERACIONAL.md) | Cenários operacionais de sucesso e falha |
| [F10 — Aceitação](evidencias/F10_ACEITACAO.md) | 153 testes obrigatórios em ambiente novo |
| [F11 — Entrega](evidencias/F11_ENTREGA.md) | Demonstração, reprodução e pacote sintético |

## Expansão

As evidências E registram a execução com 17 fontes e 447.305 casos selecionados
por data de decisão. Os comandos estão nos respectivos documentos, separados
da reprodução do MVP.

| Evidência | Conteúdo |
|---|---|
| [E00 — Inventário](evidencias/E00_INVENTARIO_EXPANSAO.md) | Fontes e escopo |
| [E01 — Perfil de execução](evidencias/E01_PERFIL_EXECUCAO.md) | Configuração e capacidade medidas |
| [E02 — Aquisição](evidencias/E02_AQUISICAO_EXPANSAO.md) e [Bronze](evidencias/E02_BRONZE_TEMPORAL.md) | Origem e seleção temporal |
| [E03 — Silver](evidencias/E03_SILVER_EXPANSAO.md) | 17 tabelas Delta validadas |
| [E04 — Atributos e tempo](evidencias/E04_ATRIBUTOS_E_TEMPO.md) | Auditoria temporal e pendências para ML |
| [E05 — ABTs](evidencias/E05_ABTS_TEMPORAIS.md) | 166 atributos e separação de features e labels |
| [E06 — Público](evidencias/E06_PUBLICO_EXPANSAO.md) | Análise retrospectiva de nove meses |
| [E07 — Publicação](evidencias/E07_PUBLICACAO_EXPANSAO.md) | 42 Delta no S3 local e recuperação |
| [E08 — Aceitação](evidencias/E08_ACEITACAO_EXPANSAO.md) | 174 testes aprovados, zero ignorados, no ambiente local existente |

A CI está configurada; as evidências registram execução local, sem job remoto
comprovado. A aprovação point in time para ML continua pendente.

## Percurso didático opcional

O [guia da implementação](GUIA_ESTUDO_LAKEHOUSE.md) conecta conceitos,
ferramentas, código e exercícios em 13 capítulos. É material de aprofundamento;
a avaliação e a reprodução podem seguir apenas o caminho principal acima.
