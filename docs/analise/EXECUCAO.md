# F07 — executar, conferir e reproduzir o relatório

O relatório consome três publicações Gold aprovadas, com IDs obrigatórios.
Não reconstrói ABT, não altera tabelas e não troca CURRENT. Perguntas e método
em [PERGUNTAS_E_METODO.md](PERGUNTAS_E_METODO.md); achados em
[RESULTADOS.md](RESULTADOS.md).

## Preparar gráficos

O ambiente principal continua usando `requirements.lock`, preservado desde
F05/F06. A camada de gráficos tem outro lock, restrito a wheels Linux x86_64
para Python 3.11. O pip do sistema precisa suportar `--python` (22.3 ou superior;
a execução local usou 25.1.1). Não instalar os gráficos globalmente.

```bash
bash scripts/bootstrap_analysis.sh
```

O script usa o Python 3.11 de `.venv` e instala os hashes de
[requirements.analysis.lock](../../requirements.analysis.lock) em
`.runtime/analysis`. O wrapper [analysis.sh](../../scripts/analysis.sh) acrescenta
esse diretório ao PYTHONPATH e usa o runtime Java/Spark principal. Matplotlib
3.10.9 e NumPy 2.4.6 foram fixados; dependências transitivas também têm versão
e hash. O instalador foi executado com o lock final antes da regressão.

Matplotlib usa o backend de arquivos Agg, sem servidor de notebook ou janela.
A [documentação oficial de backends](https://matplotlib.org/stable/users/explain/figure/backends.html)
explica seu uso sem interface gráfica; a versão adotada consta das
[releases oficiais](https://github.com/matplotlib/matplotlib/releases/tag/v3.10.9).

## Executar em processo novo

Na raiz do projeto, com as três publicações existentes:

```bash
bash scripts/analysis.sh -m src.pipelines.run_analysis \
  --sample 7d58bbdaa00cbabfbce54d26 \
  --publication 6f4406dd0180850e23d5283e \
  --baseline c711e23bdd5145ae78537a61 \
  --corrected e709bcefce9adab4b7d60562
```

Cada comando inicia e encerra sua própria sessão Spark. Nenhuma variável de
notebook ou view anterior é necessária. O retorno JSON informa relatório,
identidade da análise, run_id, status e duração. O código de saída é diferente
de zero em falha; o diagnóstico fica em `artifacts/f07/runs/<run_id>.json`.

Identidade da análise combina hashes dos três manifestos, código, configuração
e runtime. Tentativas têm run_id próprio e não sobrescrevem saídas antigas:

```text
artifacts/analysis/<selection_id>/<analysis_id>/<run_id>/
  report.html                 # relatório offline, imagens PNG embutidas
  report.md                   # respostas textuais e link para HTML
  semantic.json               # números estáveis para comparação
  metadata.json               # execução, hashes, UUIDs/versões e ambiente
  baseline_monthly.csv
  corrected_monthly.csv
  final_monthly.csv
  baseline_segments.csv
  corrected_segments.csv
  final_segments.csv
  figures/baseline/            # três gráficos em PNG e SVG
  figures/final/               # três gráficos em PNG e SVG
  blobs/                      # implementação/configuração arquivadas por hash
  _SUCCESS.json               # aceite e inventário final de arquivos
```

Consumir apenas bundles com `_SUCCESS.json` aprovado e arquivos correspondentes
a seus hashes. A tentativa pode deixar arquivos incompletos sem esse marcador;
não apagar nem aceitar esses arquivos como uma análise aprovada.
O HTML exibe gráficos sem conexão e sem carregar JavaScript externo. Para seus
links CSV/JSON, manter a pasta completa. Dados e derivados ficam locais e
ignorados pelo Git; divulgação externa segue a governança da fonte.

## O que conferir no código

1. [run_analysis.py](../../src/pipelines/run_analysis.py): `require_triplet`
   confere seleção, contrato e cadeia baseline → corrected → final. O contexto
   `open_publication` mantém as ações sob lock e fixa versões explicitamente.
2. [queries.py](../../src/analytics/queries.py): `population_summary`,
   `monthly_analysis` e `history_segments` coletam somente agregados.
   Indicadores mensais publicados são comparados com SQL independente da ABT.
3. `compare_publications` exige casos, datas e rótulos estáveis na correção.
   Coleta somente as diferenças individuais limitadas por política; atraso
   é outra comparação e não pode alterar os casos anteriores.
4. [report.py](../../src/analytics/report.py) recebe os números conferidos,
   sem recalcular a Gold. `semantic.json` omite run_id/horário; SVGs não incluem
   data variável e usam salt estável, permitindo comparação byte a byte.
5. O gerador confere novamente entradas, CURRENT e hashes de código/configuração
   antes de escrever o marcador final. Metadata não é uma nova publicação Gold.

## Reprodução e testes

Repetir o comando cria outro bundle. Comparar `semantic.json`, seis CSVs e
os gráficos da mesma publicação. `metadata.json` e HTML registram o run_id da
tentativa, portanto seus bytes podem diferir sem mudar os resultados.
Não comparar outputs de código/configuração diferentes como se fossem o mesmo
experimento. Para regenerar uma implementação antiga, restaurar seus arquivos
arquivados e dependências explicitamente; ler um relatório antigo não executa
automaticamente aquele código.

```bash
bash scripts/analysis.sh tests/analysis_integration.py
bash scripts/project.sh -m unittest discover -s tests -p test_analysis_policy.py
bash scripts/project.sh scripts/run_tests.py --integration-required
```

O runner global inclui um subprocesso F07, que chama o wrapper analítico; prepare
a camada gráfica antes do runner. A integração F07 usa fixtures sintéticas
Spark, sem credenciais ou dados Home Credit. Duas execuções reais independentes
com Delta complementam essa prova; resultados em
[F07_ANALISE.md](../evidencias/F07_ANALISE.md).
