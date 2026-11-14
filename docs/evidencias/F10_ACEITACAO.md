# F10 — CI e aceitação técnica

Data: 13/11/2026. Escopo: laboratório local com testes sintéticos reproduzíveis,
recorte real aprovado sob acesso local e configuração de GitHub Actions. Nenhum
push, publicação externa ou job remoto foi executado nesta sessão.

## F10.1 — Organização e oráculos

[Catálogo](../../tests/suites.json), [runner](../../scripts/run_tests.py) e
[instruções](../testes/EXECUCAO_E_CI.md) separam unidade, Spark, Delta, objetos,
análise e ponta a ponta. Catálogo e descoberta devem corresponder exatamente.
As integrações Delta usam subprocessos para iniciar suas JVMs com os JARs certos.
O relatório externo conta cada wrapper uma vez e não soma seus cenários internos.

Fixtures pequenas e oráculos manuais cobrem cardinalidade, valores, datas,
revisões, nulos e denominadores. O novo e2e inventa quatro casos e quatro
históricos, prepara RAW e executa amostragem, Bronze, sete pacotes F04, operação
supervisionada S3 e leitor da publicação. Espera quatro linhas na ABT e três
meses; verifica correção 10→11 na anuidade, soma histórica 6, atraso, valor nulo
e caso sem histórico. O adapter de origem conserva a enumeração exigida pelo
protocolo de correção; nenhum dado Home Credit compõe essa fixture.

Os temporários, credenciais e prefixos são próprios dos testes. O e2e compartilha
somente binário instalado e cache de JARs, remove variáveis AWS/Kaggle e encerra
seu serviço. A matriz real F09.6 fica fora da descoberta e do export CI.
Três testes do runner conferem que skips obrigatórios, falhas esperadas e catálogo
incompleto impedem aceite. A suíte de unidade local passou com 93 testes.

## F10.2 — CI declarada

[Workflow](../../.github/workflows/ci.yml): Ubuntu 24.04, bootstrap fixado de
Python/Java/Spark/Delta/SeaweedFS e dependências dos lockfiles; sintaxe Python,
`bash -n`, YAML, catálogo, suíte integral obrigatória e matriz T01–T24.
Checkout v6.0.1 e upload-artifact v6.0.0 usam SHA integral, verificado nos
repositórios oficiais de [checkout](https://github.com/actions/checkout/releases)
e [upload-artifact](https://github.com/actions/upload-artifact/releases).
A permissão é contents:read; checkout não persiste credenciais. Timeout: 90 min.

Não há download Kaggle/dados restritos. O job trabalha em export sanitizado e
publica somente os relatórios sintéticos explicitamente listados, por sete dias.
Integração ignorada impede aprovação. Não foi acrescentado formatador ou checker
de tipos; o escopo do check de código está declarado no próprio relatório.
A execução remota continua dependente de disponibilizar o código no GitHub;
o aceite local usa a sequência reproduzida abaixo, sem alegar um job remoto verde.

## F10.3 — Matriz obrigatória

A [matriz legível](../testes/MATRIZ_ACEITACAO.md) e o
[mapa executável](../../tests/acceptance_matrix.json) cobrem T01–T24.
`check_acceptance.py` exige IDs completos, métodos existentes e aprovação dos
testes vinculados em relatório integral obrigatório sem ignorados. Os wrappers
executam suas suítes internas completas e recusam cenários ignorados.

Resultado executado: **24/24 cenários aprovados**, vinculados à suíte integral
de **153 testes, zero ignorados**, com `--integration-required`.
Relatórios locais: `artifacts/f10/validation/report.json` e
`artifacts/f10/validation/acceptance_matrix.json`.
Duração integral: 2.181,696 s (36 min 22 s). Grupos: 93 unidade, 53 Spark,
quatro wrappers Delta, um objetos, um análise e um e2e. Os cenários internos
dos subprocessos já estão representados por esses wrappers.

## F10.4 — Reprodução limpa e recorte real

Foi criado `/tmp/credit-risk-f10-clean` por export, sem data, artifacts, runtime,
venv, credenciais ou Git herdados. Python 3.11.14, Java 17.0.21+9, Spark 3.5.7,
Delta 3.3.2, Hadoop 3.3.4, SDK Java 1.12.262 e SeaweedFS 4.53 foram instalados
pelos três bootstraps. O cache Ivy começou vazio. As dependências não foram
substituídas por symlinks para o runtime do projeto original.

O processo externo removeu variáveis AWS/Kaggle/PySpark, PYTHONPATH e JAVA_HOME;
o projeto configurou seu próprio ambiente novo. Comandos do job reproduzidos:

```bash
python3 scripts/export_source.py --output /tmp/credit-risk-f10-clean
cd /tmp/credit-risk-f10-clean
bash scripts/bootstrap_environment.sh
bash scripts/bootstrap_analysis.sh
bash scripts/bootstrap_objects.sh
bash scripts/project.sh scripts/check_code.py
bash scripts/project.sh scripts/run_tests.py --integration-required --report artifacts/tests/report.json
bash scripts/project.sh scripts/check_acceptance.py --report artifacts/tests/report.json --output artifacts/tests/acceptance_matrix.json
```

A cópia sanitizada recalcula apenas os hashes de sua cadeia notebook→política→
contratos Silver/Gold. Original e export constam de `source_manifest.json`.
O helper sintético recebeu ajuste de identificação antes de ser executado;
checker/matriz e manifesto final foram conferidos após a suíte. Não foi
necessário estado de notebook. O bootstrap e as execuções ficam nos artefatos
locais de validação F10; seu conteúdo não entra no upload CI.
`validation/clean_environment.json` registra versões observadas e o hash do
manifesto de fonte; `bootstrap_{environment,analysis,objects}.log` preservam
a instalação.

Com dados reais, dois processos novos executaram rebuild até o primeiro lote,
usando o catálogo F04 aprovado e o espelho real somente para leitura, em
namespace descartável. Conferiram contratos, hashes da entrada, reconstrução e
publicação de cinco tabelas. Isso valida a execução atual sobre o recorte local;
não é um novo download do dataset em máquina sem autorização. A matriz de falhas
real F09.6 complementa esse ensaio e permanece preservada.

## F10.5 — Gargalo medido e igualdade

O executor lia tipadamente sete pacotes (três tabelas por pacote) antes de
selecionar um. A alteração em [run_lakehouse.py](../../src/pipelines/run_lakehouse.py)
seleciona metadados por modo/lote antes da leitura S3A. O catálogo aprovado e o
espelho completo continuam validados por hash. Nada mudou em volume, cache,
paralelismo, partições, precedência ou critérios de publicação.

| Medida | Antes | Depois |
|---|---:|---:|
| Pacotes disponíveis | 7 | 7 |
| Pacotes lidos tipadamente | 7 | 1 |
| Tabelas de entrada lidas/contadas | 21 | 3 |
| Duração da operação | 259,673 s | 185,228 s |

Uma execução por variante observou redução de 28,7%. Não é benchmark estatístico,
SLA ou isolamento causal do tempo de leitura. Cada variante iniciou processo/JVM
novo, com o mesmo serviço já iniciado; RSS desse serviço preexistente não integra
o processo medido. Entradas imutáveis e ambiente foram compartilhados. O relatório
separa duração da operação das durações internas, que incluem suas validações.

A comparação bidirecional de todas as colunas aprovou `silver.credit_cases`,
`silver.credit_static`, `silver.previous_applications`, `gold.abt` e
`gold.monthly_metrics`, sem linhas ausentes ou extras. Os CURRENT reais F08/F09
foram preservados e o prefixo temporário removido. O ensaio não ampliou a coorte.
Fontes, versões, fingerprints, contadores, recursos e provas:
`artifacts/f10/benchmark/{before,after,results}.json`, `variant.py`, `compare.py`.

## F10.6 — Acesso, dados e preservação

O export usa lista de extensões/diretórios permitidos. Exclui dados, artefatos,
logs, runtime, ambientes, credenciais, Git e documentação; sanitiza outputs,
attachments e metadados de notebook. É pacote de fonte para validar fixtures,
não o pacote final de portfólio. A auditoria exige inventário exato e hashes,
confere extensões/caminhos, outputs e correspondência com três segredos locais
conhecidos, sem imprimir seus valores.

O pacote `artifacts/f10/credit-risk-ci-source.tar.gz` contém 174 arquivos regulares;
todos os hashes foram novamente conferidos dentro do arquivo comprimido. Relatórios
`validation/package.json`, `access_review.json`, `source_manifest.json` e
`local_access.json` registram seu inventário, SHA e limites. Nenhum dado ou
credencial foi encontrado no pacote ou nos arquivos rastreados examinados.
Data, artifacts, runtime, venv e credenciais estão ignorados; os dois arquivos
locais de credenciais conferidos têm modo 0600.

**O notebook original conserva 164 outputs e não está liberado para publicação
direta.** Seu SHA é
`350aa226f0fbed8851d1f86cf13d23b41a2ab66c5afc953922b4f8dbcf35111e`,
ligado às evidências históricas. O export tem zero outputs e referências próprias.
F11 deverá revisar entrega/divulgação e condições da fonte antes da publicação.
A auditoria por segredos conhecidos não é prova universal de ausência de todo
segredo possível ou autorização de redistribuição dos dados.

A auditoria de preservação passou: seis RAW, amostra/Bronze íntegros, dois recibos
F03, 90 arquivos de publicações Silver, 127 de publicações analíticas, dois bundles
F07 e os dois CURRENT filesystem preservados. Fingerprints F05/F06/F08 continuam
iguais. Resultado: `artifacts/f10/protected_inputs_check.json`.

## Fechamento

Após copiar relatórios, logs, manifesto e pacote para `artifacts/f10`, o serviço
do ambiente limpo foi confirmado parado e os diretórios descartáveis do ensaio
foram removidos. O runtime e os dados do projeto original foram preservados.
Registro: `artifacts/f10/validation/cleanup.json`. O aceite consolidado está em
`artifacts/f10/acceptance.json`, com hashes das evidências.

**F10.1–F10.6 aceitos no escopo descrito.** Roteiro: **66/72**, F00–F10
concluídas. Próxima: **F11.1**, reescrever README e alinhar a entrega.
F11 conserva a revisão de divulgação e o preparo do pacote final.
