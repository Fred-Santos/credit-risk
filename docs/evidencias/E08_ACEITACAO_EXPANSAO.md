# E08 — Aceitação e documentação da expansão Home Credit

Execução local em 19/11/2026. Os quatro itens da E08 foram concluídos.
O roteiro de expansão termina na E08; não há uma E09 definida nesse documento.
A conclusão é do produto retrospectivo e dos controles implementados; a aprovação
point in time para ML continua pendente.

## Resultado executado

**174 testes aprovados, zero ignorados**, com integrações obrigatórias,
em 44.8 minutos. A contagem é por testes descobertos;
cada wrapper de integração conta uma vez, mesmo executando vários cenários
internos em JVM própria. As matrizes **T01–T24** e **X01–X17** foram aprovadas
contra esse relatório completo, não apenas conferidas estaticamente.

| Grupo | Testes no relatório |
|---|---|
| analysis | 1 |
| unit | 103 |
| spark | 61 |
| delta | 6 |
| e2e | 1 |
| objects | 2 |

A execução usa os runtimes já instalados neste host. Não foi uma instalação
nova nem execução remota de CI. A evidência histórica F10 de 153 testes em
ambiente novo permanece em `artifacts/f10/validation/`; ela não foi reutilizada
como aprovação automática da expansão.

## Cobertura nova e controles temporais

O wrapper e2e executa o MVP e, em outra JVM, o novo
`tests/expansion_e2e_synthetic.py`. A expansão percorre aquisição RAW com fetch
injetado, Bronze temporal, Silver Delta, auditoria, duas ABTs, análise e
publicação/consumo S3. Os cinco formatos de fonte inventados representam
níveis 0/1/2. Dos seis casos, quatro estão na janela pública e dois em cada ABT.
As datas de fronteira, históricos de 2018 e 2021, zero observado, valor nulo,
ausência de histórico e solicitante diferente de pessoa relacionada têm
conferências explícitas. O consumo S3 confirma 18 Delta no manifesto, nove
meses analíticos, features de ambos os períodos e ausência dos rótulos da
reserva no leitor padrão. O laboratório temporário foi removido.

A suíte também aprova reconciliação por chave/célula, schemas iguais, ABTs
disjuntas, média ponderada entre grupos, moda determinística, revisões/conflitos,
rejeições rastreáveis, falhas antes/depois da ativação, retry, rollback e
histórico imutável. A [matriz X01–X17](../testes/MATRIZ_EXPANSAO.md) identifica
os testes e cenários internos; não conta esses cenários como testes adicionais.

O teste preserva propositalmente uma data posterior à decisão para o produto
retrospectivo e confirma que `open_ml_inputs` rejeita treino. Os controles
previnem usos indevidos conhecidos, mas não comprovam disponibilidade histórica,
maturação do target ou identidade global do cliente. `ml_ready=false` e
`eligible_predictors=[]` permanecem. Um futuro modelo depende dessas evidências
e de preprocessamento ajustado apenas no treino de cada fold de desenvolvimento.

## Isolamento e documentação

A suíte foi iniciada sem `KAGGLE_API_TOKEN`, `KAGGLE_USERNAME` e `KAGGLE_KEY`,
com `KAGGLE_CONFIG_DIR` apontando para uma pasta vazia. O e2e remove variáveis
Kaggle/AWS do processo e utiliza apenas dados inventados; o S3 local usa suas
próprias credenciais locais. Não há aquisição autenticada da competição nos testes.
A fixture nova usa `fixtures/expansion-e2e/<uuid>` e limpa apenas esse prefixo.
Se o serviço real já estiver ativo, a fixture o mantém ativo.

A conferência final por leitura no S3 confirma CURRENT da expansão em
`58c3de42fe5b3c61ad3eeede` (dados originais), serviço ativo e dois ponteiros MVP
presentes. Os hashes desses dois ponteiros foram conferidos antes e depois das
integrações finais. Não houve republicação dos dados reais na E08.

O export sanitizado contém 226 fontes e um manifesto, sem dados reais,
credenciais ou outputs de notebooks. A auditoria aprovou o pacote e não encontrou
correspondências de credenciais nos arquivos rastreados. Os notebooks históricos
originais foram preservados; isso não declara a árvore original pronta para
publicação externa. Não houve push ou publicação externa nesta etapa.

README, arquitetura, contratos, operação S3 e guia de estudo foram atualizados,
com o [capítulo 13](../estudo/13_EXPANSAO_E_VALIDACAO_TEMPORAL.md) dedicado à expansão.
A CI passa a exigir também o gate X01–X17 e a guardar o relatório do e2e ampliado.
As evidências de volume real das 17 fontes e das 42 Delta permanecem em E02–E07;
a fixture de cinco fontes testa comportamento, não substitui essas evidências.

## Reprodução

Após os três bootstraps:

```bash
bash scripts/project.sh scripts/check_code.py --report artifacts/expansion/e08/code_checks.json
env -u KAGGLE_API_TOKEN -u KAGGLE_USERNAME -u KAGGLE_KEY KAGGLE_CONFIG_DIR=/tmp/credit-risk-e08-no-kaggle bash scripts/project.sh scripts/run_tests.py --integration-required --report artifacts/expansion/e08/full_suite.json
bash scripts/project.sh scripts/check_acceptance.py --report artifacts/expansion/e08/full_suite.json --output artifacts/expansion/e08/mvp_acceptance.json
bash scripts/project.sh scripts/check_expansion_acceptance.py --report artifacts/expansion/e08/full_suite.json --output artifacts/expansion/e08/expansion_acceptance.json
```

Use uma pasta vazia para `KAGGLE_CONFIG_DIR`. O gate da expansão sem `--report`
atesta apenas o mapeamento estático. Para a auditoria de fonte, exportar para uma
pasta nova com `scripts/export_source.py` e verificar com `scripts/audit_source.py`.

## Relatórios locais e hashes

Os relatórios são locais e ignorados pelo Git; os hashes permitem identificar
os resultados desta execução. Reexecutar os comandos gera novos relatórios.

- `artifacts/expansion/e08/full_suite.json`: SHA-256 `650572edc005a1988a18b3ad82573fc162106441cac547f7aa080a7b3498c6c3`.
- `artifacts/expansion/e08/mvp_acceptance.json`: SHA-256 `a77ae4e0ae4fe5794443ad0490ab5ed727de60ab146e498b92752a8005cdddda`.
- `artifacts/expansion/e08/expansion_acceptance.json`: SHA-256 `08104576d512896d08a55814565e46e1a81b39f60b769661e164e0562c8621f0`.
- `artifacts/expansion/e08/mvp_e2e.json`: SHA-256 `1292fe68cdb61bb85cf2602a18bdd76eb88261ea92cd0ddd313a58b47c0c40ab`.
- `artifacts/expansion/e08/expansion_e2e.json`: SHA-256 `01876f9d21476e85ad0c9f6566f02b611f6a6a7103e10f9fda5b6099b3c86779`.
- `artifacts/expansion/e08/code_checks.json`: SHA-256 `7b6fe462887a439d1866e92f03a8130b927006c750f1154e384108e7b09a330b`.
- `artifacts/expansion/e08/source_audit.json`: SHA-256 `5abd1a06655fc894c58ee8cad588ce588d99c73f8d35c98a2384e3ac21914be4`.
- `artifacts/expansion/e08/active_publications.json`: SHA-256 `9d1f7de1a50e9a545acfab8293b5cfc0c2b2e42d5c10ced561d70c8bedbb7852`.
