# F09.6 — matriz operacional local

A matriz executa o supervisor e o executor F09 com Spark, Delta, S3A e SeaweedFS
reais. Consome o primeiro lote da seleção Home Credit já aprovada, incluindo
seus contratos, gates, espelho, incremento, reconstrução independente e publicação.
Os produtores e publicações reais permanecem preservados.

```bash
bash scripts/objects.sh tests/operational_matrix_local.py
```

Pré-requisitos: ambiente principal e objetos preparados, arquivos e relatórios
F00–F04 aprovados disponíveis, serviço local sem outra carga concorrente. O
script usa a seleção `7d58bbdaa00cbabfbce54d26`, relatório F04
`20261113T020347Z_1609747b` e lote `b00_w000_051` (35.045 casos, 35.045 estáticos,
136.679 observações históricas). É um ensaio local com dados autorizados; não
faz download nem exige credenciais Kaggle durante a execução.

## Cenários e expectativas

| Cenário | Intervenção | Resultado esperado |
|---|---|---|
| Sucesso | Entrada aprovada, processamento completo do lote | Código 0; cinco tabelas aprovadas; estabelece CURRENT da fixture |
| Fonte ausente | Relatório de entrada inexistente | Código 3; etapa inputs; uma tentativa; CURRENT anterior preservado |
| Schema inválido | Coluna extra no DataFrame entregue à publicação Silver | Código 3; etapa publication; validador real rejeita; uma tentativa; CURRENT preservado |
| Qualidade reprovada | target=7 no DataFrame privado entregue à publicação | Código 3, quality_rejected; relatório detalhado failed; sem retry; CURRENT preservado |
| Serviço indisponível | Parar SeaweedFS após commit privado de criação da ABT | Erro real de conexão; CURRENT anterior preservado antes da retomada; segunda tentativa conclui sem novos commits de negócio |

Nos casos de schema/qualidade, a mutação ocorre na saída privada entregue ao
publicador, representando um defeito do produtor. Os arquivos de entrada e o
estado incremental saudável não são corrompidos. Os validadores de schema,
contratos Silver, SQL Gold e comparações de dados são executados sem substituição.

A indisponibilidade é física: o processo do serviço é parado, e o SDK encontra
o endpoint indisponível. O callback de espera do teste reinicia o serviço apenas
para conferir o CURRENT anterior e volta a pará-lo; a tentativa seguinte executa
os mecanismos reais de inicialização e retomada. operation_id mantém o namespace
rebuild, enquanto cada tentativa tem outro run_id. O teste exige versões de
negócio iguais e inserts/updates zero na reaplicação, além de leitura final das
cinco tabelas por outro contexto Spark.

## Isolamento e rastreabilidade

`temporary_objects` cria um prefixo imprevisível e fechado. O teste redireciona
somente a fábrica do cliente S3 do executor para esse cliente real e envolve
o ponto de publicação com injeção de falhas. O publicador real continua sendo
chamado. Nenhum gate/validador é substituído por um resultado aprovado fictício.
O hash do harness é registrado junto aos resultados.

Cada cenário usa rebuild isolado. A fixture estabelece sua própria publicação
válida; os erros seguintes não podem avançar seu ponteiro. Os dois CURRENT reais
(F08 e F09) são capturados antes e conferidos depois da limpeza. O prefixo
criado internamente é removido por API ao finalizar; não recebe caminho externo
para apagar. Não há VACUUM ou remoção de dados reais. A limpeza lógica pode
conservar bytes internos no backend; não a confundir com liberação de disco.

O supervisor aceita `reports_directory` interno ao repositório para separar as
operações de validação da história operacional normal. O CLI mantém o diretório
padrão. Os runs do processamento continuam com seus run_id únicos em
`artifacts/f09/runs/`. Tentativas incluem referência ao run_report e SHA-256,
inclusive em falha. Reprovações Silver/Gold preservam quality_failure no run.

Relatórios da matriz ficam em `artifacts/f09/validation/f096/`: progress.json,
operations/, results.json e logs. As publicações da fixture são temporárias;
seus metadados/provas ficam nos resultados, sem prometer leitura histórica após
a limpeza. A fonte original e as publicações reais continuam disponíveis.

## Alcance do aceite

A matriz exercita o fluxo operacional sobre entradas já aprovadas e um lote
representativo. As execuções F04/F08 anteriores cobrem os sete pacotes simulados;
F09.1/F09.3 cobrem atualização, replay e reconstrução. A matriz é complementar.
Ela chama a API do supervisor para permitir injeções que não são flags do CLI.
O CLI já tem provas reais de sucesso, fonte ausente e código de saída em F09.2/F09.3.

Este script não entra no discover automático e depende de artefatos reais
privados. A organização dos testes e CI com fixtures sintéticas, sem Home Credit
ou Kaggle, continua em F10. Uma execução limpa desde aquisição/instalação e a
aceitação final também continuam nas etapas seguintes.
