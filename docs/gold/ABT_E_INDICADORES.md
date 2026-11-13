# Gold — execução e consumo por publicação

O [contrato](../contratos/ABT.md) define população, 19 colunas da ABT e 11
colunas dos indicadores. A [evidência F06](../evidencias/F06_GOLD.md) registra a
execução medida. Este fluxo consome F05 aprovada; preserva RAW, Bronze, F03 e F04.

## Executar

Na raiz, com ambiente preparado e os relatórios indicados disponíveis:

```bash
bash scripts/project.sh -m src.pipelines.run_gold_demo \
  --sample 7d58bbdaa00cbabfbce54d26 \
  --f05-report artifacts/f05/runs/20261113T033217Z_04372370.json
```

O comando verifica as três publicações Silver do relatório F05: baseline,
corrected e late. Publica cada par ABT/indicadores em registry analítico próprio,
testa falha após MERGE privado, retoma, reproduz baseline, restaura late e verifica
retry. Retorna JSON com status, relatório, registry, IDs e quantidade da ABT.
É uma demonstração fechada dos cenários existentes, sem geração de novos eventos.

Registry: `artifacts/publications/<selection_id>/analytics/`.
Dados: `data/gold/samples/<selection_id>/published/<publication_id>/`.
Relatórios: `artifacts/f06/runs/<run_id>.json`.

## Acompanhar o código

| Etapa | Função/arquivo | Por que existe |
|---|---|---|
| Identificar as entradas | `run_gold_demo` em [pipeline](../../src/pipelines/run_gold_demo.py) | Relatório F05 aprovado e seleção explícita |
| Verificar publicações | `publish_analytics` em [publish.py](../../src/gold/publish.py) | Ler versões aprovadas e anexar suas três entradas Silver ao manifesto |
| Agregar e juntar | `build_abt` em [model.py](../../src/gold/model.py) | Evitar multiplicação 1:N e preservar ausência/nulos |
| Identificar mudanças | `affected_cases` no mesmo módulo | Diferenças em qualquer Silver, não somente na base |
| Atualizar | `prepare_gold` em publish.py | Cópia privada do pai, MERGE por caso, conferência de métricas |
| Validar | [quality.py](../../src/gold/quality.py) | Contrato, SQL independente e reconciliação integral |
| Materializar indicadores | `monthly_sql` / `build_monthly` | Recalcular numeradores e denominadores por período |
| Disponibilizar | [protocolo](../PUBLICACAO_E_RECUPERACAO.md) | Manifesto imutável e troca de CURRENT após aceite |

## Estratégia e custo

A ABT inicial é integral. As seguintes começam com uma cópia Delta da ABT pai;
o MERGE recalcula somente os casos afetados. Portanto o algoritmo de atualização
é incremental, mas existe custo de copiar a tabela para preservar a publicação
anterior imutável. Versão 0 é a cópia; versão 1 registra o MERGE, quando necessário.
Um retry após merge reconhece seu commit e não o repete. O relatório diferencia
alterações lógicas pai→saída dos commits executados na tentativa de retomada.

Os indicadores têm poucos períodos. Uma materialização SQL integral por
publicação é simples de validar, reflete correções antigas e elimina períodos
que ficaram sem casos. Não há alegação de MERGE incremental físico mensal.
Cada publicação tem seu próprio UUID e começa indicadores na versão 0.

Conferir toda a ABT contra recomputação e indicadores contra Silver custa mais
que atualizar uma chave. Essa medição representa o laboratório com validações,
não um benchmark isolado de MERGE. Não ampliamos o recorte ou paralelismo.

## Consumir com versões coerentes

Execute as ações Spark dentro do contexto; a sessão deve estar preparada com
Delta. Exemplo Python usando os utilitários do projeto:

```python
from pathlib import Path
from src.publication.protocol import open_publication
from src.utils.spark import create_spark_session

root = Path.cwd()
registry = root / 'artifacts/publications/7d58bbdaa00cbabfbce54d26/analytics'
spark = create_spark_session(root, app_name='consume-gold', delta=True)
try:
    with open_publication(root, registry, spark) as (manifest, frames):
        print(manifest['publication_id'])
        frames['gold.monthly_metrics'].orderBy('MONTH').show(30, truncate=False)
        frames['gold.abt'].select('case_id', 'previous_application_count').show(5)
finally:
    spark.stop()
```

`publication_id='<id>'` em `open_publication` seleciona uma publicação histórica
explicitamente. Sem ID, o contexto lê CURRENT uma vez sob lock e valida o conjunto.
Não consultar todas as pastas Parquet nem escolher o último Delta de cada pasta.
O manifesto fixa as três Silver e duas Gold, registra referência ao manifesto
F05 e ao pai analítico, além de código/configuração arquivados por hash.

Falha entre Silver/Gold, após commit privado ou após qualidade não avança CURRENT.
Rollback troca o conjunto selecionado depois de verificá-lo; não sobrescreve
tabelas. A retenção mantém publicações fixadas sem prazo de descarte, com janela
Delta configurada em 30 dias e sem VACUUM nos dados reais. Garantias são locais,
com um escritor cooperante; objetos e orquestração integrada seguem em F08/F09.
