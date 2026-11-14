# F09.6 — matriz operacional e fechamento de F09

Execução local em 13/11/2026. [Matriz e método](../operacao/MATRIZ_OPERACIONAL.md).
O fluxo foi executado com entradas Home Credit reais já aprovadas e destinos
S3 temporários, incluindo gates, espelho, incremento, reconstrução, publicação
Silver v2/Gold, contratos e oráculos. Foram preservados RAW, entradas e publicações
reais. A coorte usada é a seleção aprovada, com o primeiro lote de 35.045 casos,
35.045 estáticos e 136.679 históricos; as provas anteriores cobrem os sete lotes.

## Comando e resultados

```bash
bash scripts/objects.sh tests/operational_matrix_local.py
```

O teste usa a API do supervisor para permitir injeção de falhas não expostas
como flags do CLI. O publicador, validadores, Spark, Delta e S3 são reais.
O cliente real é redirecionado para um prefixo privado e o ponto de publicação
é envolvido por hooks de falha; nenhum validador é substituído por um mock.
O hash do harness e os hashes dos produtores estão em `results.json`.

| Cenário | Operação | Código | Tentativas | Etapa final |
|---|---|---:|---:|---|
| success | `20261113T184327Z_8fb1c3ee` | 0 | 1 | complete |
| source_missing | `20261113T184845Z_74986e44` | 3 | 1 | inputs |
| schema_invalid | `20261113T184859Z_c0e352cc` | 3 | 1 | publication |
| quality_rejected | `20261113T185158Z_7328b030` | 3 | 1 | publication |
| service_unavailable | `20261113T185551Z_9fda9d28` | 0 | 2 | complete |

Sucesso estabeleceu uma publicação válida da fixture. Fonte ausente falhou em
inputs; schema extra falhou em publication. Ambas encerraram sem retry e
preservaram CURRENT. A falha de qualidade foi identificada como quality_rejected,
código 3, com relatório detalhado fixado por hash no run_report da tentativa.
O check real reprovado foi:

```json
[
  {
    "table": "credit_cases",
    "check": "target_domain",
    "success": false
  }
]
```

O schema extra e target=7 foram introduzidos somente nos DataFrames privados
entregues ao publicador, simulando um defeito do produtor. A entrada aprovada e
o estado incremental saudável não foram editados.

## Recuperação após indisponibilidade

SeaweedFS foi parado depois do commit privado de criação da ABT. O SDK gerou
EndpointConnectionError real. Antes do retry, o teste reiniciou o serviço e
conferiu o CURRENT anterior byte a byte; voltou a pará-lo e deixou a tentativa
seguinte percorrer a inicialização e o processamento reais. O supervisor usou
duas tentativas e a mesma identidade lógica de rebuild, com run_id distintos.

A reaplicação conservou versões do estado incremental e teve zero inserts e
updates. A publicação retomada foi aprovada depois dos checks. Um novo contexto
Spark leu as cinco tabelas, confirmou ABT de 35.045 linhas, 12 meses e ABT versão
0, sem recriação como novo commit. Os dados privados só ficaram visíveis após
completar as validações. As falhas definitivas não avançaram a publicação anterior.

## Diagnóstico e mudanças implementadas

As exceções SilverContractError/GoldQualityError agora são classificadas como
quality_rejected, sem retry e com código 3. O executor preserva o relatório da
reprovação em quality_failure. As tentativas ligam o run_report por path e
SHA-256, quando ele existe; falha de criação do contexto não herda referência
de tentativa anterior. O supervisor permite diretório de relatórios confinado
ao repositório; a matriz usa operations/ sob seu diretório de validação,
sem contaminar o histórico operacional normal. O CLI conserva o padrão.

## Preservação, limpeza e verificações

O resultado registrou ambos CURRENT reais (F08 e F09) iguais antes/depois.
A fixture usou prefixo gerado internamente; todos os seus objetos foram removidos
por API ao finalizar. Nenhum caminho real foi recebido para remoção, e não houve
VACUUM. Os metadados/provas da fixture ficam em results.json e relatórios;
suas tabelas temporárias não ficam disponíveis para consumo depois da limpeza.
O backend pode reter bytes internos, portanto limpeza lógica não é liberação
física de disco. O serviço terminou no estado apropriado de encerramento.

Artefatos: `artifacts/f09/validation/f096/results.json`, `operations/`,
`matrix.log`, `supervisor.log`, `regression.log`, `selection.log`, e runs
referenciados em `artifacts/f09/runs/`. Oito cenários do supervisor passaram,
incluindo classificação Silver/Gold e confinamento do diretório de relatórios.
A regressão direcionada aprovou 17 verificações no runner (oito do resumo,
cinco de lineage, três de métricas e o wrapper dos oito cenários de supervisor),
além dos três testes de seleção. Não somar wrapper e cenários internos como
verificações do mesmo nível. A regressão global F08 de 129 verificações é a
linha de base anterior; não foi reexecutada nesta etapa. A consolidação de
suítes e CI obrigatória fica em F10.

Auditoria de preservação em protected_inputs_check.json confere RAW/recorte,
Bronze, recibos F03, publicações F05/F06 e bundles F07. Mudanças de código F09
criam identidades novas; as versões anteriores permanecem nos blobs históricos.

## Aceite e próximos passos

F09.1–F09.6 aceitas no escopo local: comando por lote, estados/erros e retry,
métricas, lineage/inventário, resumo e matriz de operação/recuperação.
Esta matriz depende dos artefatos privados e fica fora do discover automático.
CI sem Kaggle e com fixtures sintéticas, reprodução em ambiente limpo,
aceitação técnica consolidada e entrega do portfólio seguem em F10/F11.
Próxima: F10.1, organizar suítes por responsabilidade.
