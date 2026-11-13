# Evidência — aquisição e inspeção da Home Credit real

Data: 12/11/2026. Escopo aceito: F00.2 para desenvolvimento local, F00.3 e F02.1.
F00.4/F00.5 e as demais entregas de F02 continuam pendentes.

## 1. Origem e execução

O cliente oficial Kaggle autenticou e listou os arquivos de
`home-credit-credit-risk-model-stability`. O inventário remoto retornou 138
arquivos; seis foram selecionados e seus nomes/tamanhos conferidos contra a API.
Nenhum token ou conteúdo de credencial foi incluído nesta evidência.

Comandos executados na raiz:

```bash
bash scripts/project.sh -m kaggle competitions files home-credit-credit-risk-model-stability --page-size 200
bash scripts/project.sh -m src.pipelines.download_home_credit
bash scripts/project.sh -m src.profiling.inspect_home_credit
bash scripts/project.sh scripts/run_tests.py --integration-required
```

Após a primeira aquisição, o downloader foi executado novamente: verificou os
seis arquivos por checksum sem novo download. Não restaram diretórios temporários
`.download-*`. O journal registra os seis como `complete`.

## 2. Arquivos adquiridos

| Arquivo relativo à RAW | Bytes |
|---|---:|
| `feature_definitions.csv` | 34.047 |
| `parquet_files/train/train_base.parquet` | 7.048.047 |
| `parquet_files/train/train_static_0_0.parquet` | 113.858.592 |
| `parquet_files/train/train_static_0_1.parquet` | 74.691.173 |
| `parquet_files/train/train_applprev_1_0.parquet` | 106.951.598 |
| `parquet_files/train/train_applprev_1_1.parquet` | 72.860.971 |
| **Total** | **375.444.428** |

O total corresponde a aproximadamente 358,05 MiB/0,35 GiB de arquivos adquiridos.
Não representa o download completo da competição ou o disco total da solução.
São arquivos reais completos das tabelas selecionadas; ainda não é o recorte
de desenvolvimento de até 50 mil casos.

Os arquivos originais escolhidos foram preservados. Não foram baixados CSVs
duplicados nem todo o conjunto de teste; nenhum dado anterior foi removido.
Checksums SHA-256 completos ficam em `data/raw/_acquisition/`, fora do Git.
Os tamanhos de todos os arquivos coincidiram com os informados pela API.

## 3. Relatório de inspeção

Run ID: `20261112T181943Z_8cf3dbbd`.

Relatório local:
`artifacts/source_inspection/20261112T181943Z_8cf3dbbd.json`.
Inventário remoto selecionado:
`artifacts/source_inspection/api_selected_files.json`.

Resultado: `passed`. Tempo da função de inspeção: 51,869 s, excluindo download,
inicialização/encerramento da sessão Spark. As contagens são exatas e não
estimativas por amostragem ou contagem aproximada de distintos.

O script verifica esquemas dos shards antes da união e registra, para cada
campo, tipo, nulabilidade declarada, contagem de nulos e contagem de NaN quando
aplicável. Não exporta registros individuais nem exemplos de clientes/casos.

## 4. Grãos e chaves observados

| Tabela lógica | Linhas | Colunas | Casos distintos | Chave observada |
|---|---:|---:|---:|---|
| `train_base` | 1.526.659 | 5 | 1.526.659 | `case_id` |
| `train_static_0`, união de dois shards | 1.526.659 | 168 | 1.526.659 | `case_id` |
| `train_applprev_1`, união de dois shards | 6.525.979 | 41 | 1.221.522 | `case_id`, `num_group1` |

Nenhuma tabela lógica apresentou chave nula ou grupo de chave duplicada.
Os esquemas dos shards de cada tabela lógica coincidiram. A verificação de
unicidade foi feita após unir os arquivos, abrangendo duplicatas entre shards.

O significado de caso de crédito vem da descrição da fonte, e a unicidade foi
verificada nos arquivos atuais. Isso não identifica uma pessoa única. A chave
composta do histórico é válida neste snapshot; a estabilidade de um índice
ordinal em outras extrações não foi demonstrada e não deve ser presumida para CDC.

## 5. Referências e cobertura

| Auxiliar | Casos órfãos | Casos da base sem correspondência | Cobertura da base |
|---|---:|---:|---:|
| Estática | 0 | 0 | 100% |
| Aplicações anteriores | 0 | 305.137 | Aproximadamente 80,01% |

A cobertura usa casos distintos, não a quantidade de linhas auxiliares. Ausência
de correspondência no histórico não foi classificada automaticamente como erro.
O motivo de ausência não é determinado por esse anti-join.

Um left join direto entre base e histórico teria, pelas cardinalidades observadas,
6.525.979 + 305.137 = **6.831.116 linhas**, em vez de 1.526.659. Esse é um cálculo
derivado das contagens, não um join materializado. Para a ABT por caso, o histórico
precisará ser agregado antes do join; regras de ausência serão definidas no contrato.

## 6. Tempo e rótulo da base principal

| Verificação | Resultado |
|---|---|
| Menor `date_decision` | 2019-01-01 |
| Maior `date_decision` | 2020-10-05 |
| `MONTH` | 201901 a 202010, com 22 meses presentes |
| `WEEK_NUM` | 0 a 91, com 92 valores presentes |
| Datas não nulas que falharam na conversão | 0 |
| Divergências entre `MONTH` e mês da data | 0 |
| Rótulos fora de 0/1 ou nulos | 0 |
| `target=0` | 1.478.665 casos |
| `target=1` | 47.994 casos |

Os cinco campos da base não apresentaram nulos. A proporção retrospectiva de
`target=1` nesse conjunto é aproximadamente 3,14%; isso não é uma estimativa
de inadimplência de uma carteira atual, uma probabilidade individual ou aprovação
de crédito. Outubro de 2020 termina no dia 5 e não deve ser comparado como mês
completo. A data de aquisição de 2026 não transforma o período de negócio em 2026.

## 7. Nulos, NaN e definições

| Tabela lógica | Colunas com pelo menos um nulo | Colunas inteiramente nulas | NaN observados |
|---|---:|---:|---:|
| Base | 0 | 0 | 0 |
| Estática | 121 | 0 | 0 |
| Aplicações anteriores | 32 | 0 | 0 |

Nulabilidade declarada no schema e ausência observada são conceitos distintos.
Um campo marcado como nullable não necessariamente tem nulos; um campo sem
nulos neste snapshot não se torna obrigatório sem decisão de contrato.

O CSV de definições contém 465 linhas e as colunas `Variable` e `Description`.
Todas as features não estruturais das três tabelas selecionadas encontraram
definição pelo nome. Isso facilita a escolha da ABT, mas não comprova disponibilidade
no instante da decisão, unidade monetária ou regra de preenchimento.

Datas auxiliares, sentinelas, categorias especiais e políticas de imputação
ainda não foram validadas por esta inspeção. Não converter automaticamente nulos
em zero, valores negativos em erro ou códigos em ausências.

## 8. Testes e limites

Suíte obrigatória atual: **33 testes aprovados, nenhum ignorado**, em 17,672 s.
Os dois testes adicionados verificam contagens de duplicatas/nulos/NaN no grão
composto e diagnóstico de data, mês e rótulo inválidos. Fixtures são sintéticas;
os números deste documento vieram dos arquivos reais adquiridos e da inspeção
Spark executada separadamente.

Credenciais, arquivos reais e relatórios locais foram confirmados como ignorados
pelo Git. Nenhuma publicação externa ou submissão à competição foi realizada.
A revisão da divulgação externa permanece antes da publicação do portfólio.

## 9. Próxima entrega

Definir contratos das três tabelas e a política do recorte/lotes (F00.4/F00.5),
depois materializar o recorte e executar a validação RAW → Bronze. Não chamar
a RAW atual de Silver, ABT ou Lakehouse concluído.
