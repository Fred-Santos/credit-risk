# Testes, ambiente limpo e CI

O catálogo [suites.json](../../tests/suites.json) atribui cada classe descoberta a
uma responsabilidade. O runner exige correspondência exata: classe nova sem grupo,
ID duplicado ou seleção vazia impedem a execução. As integrações em subprocessos
contam uma vez no relatório externo; seus cenários internos não são somados de novo.

| Grupo | Responsabilidade |
|---|---|
| unit | Configuração, políticas, seleção, métricas, supervisão e runner |
| spark | Ingestão, contratos, reconciliação e transformações com DataFrames |
| delta | Transações, incremento, publicação, recuperação e Gold em JVM isolada |
| objects | API S3, S3A/Delta, persistência, falhas e exclusão de escritor |
| analysis | Consumidor publicado e oráculos de indicadores |
| e2e | RAW inventada → amostra → Bronze → sete pacotes → supervisor → Silver/Gold S3 |

Preparar dependências fixadas e executar a mesma sequência adotada pela CI:

```bash
python3 scripts/export_source.py --output /tmp/credit-risk-source
cd /tmp/credit-risk-source
python3 scripts/audit_source.py --bundle . --report artifacts/tests/access_review.json
bash scripts/bootstrap_environment.sh
bash scripts/bootstrap_analysis.sh
bash scripts/bootstrap_objects.sh
bash scripts/project.sh scripts/check_code.py
bash scripts/project.sh scripts/run_tests.py --integration-required --report artifacts/tests/report.json
bash scripts/project.sh scripts/check_acceptance.py --report artifacts/tests/report.json --output artifacts/tests/acceptance_matrix.json
```

O destino do export deve ser novo. Para inspecionar ou selecionar um grupo:

```bash
bash scripts/project.sh scripts/run_tests.py --list
bash scripts/project.sh scripts/run_tests.py --suite unit --integration-required
```

A verificação de código compila Python sem executá-lo, usa `bash -n`, lê YAML e
confere catálogo/matriz. Não adota um formatador ou analisador de tipos. O runner
retorna erro se uma integração obrigatória for ignorada, se houver falha esperada,
erro ou falha de teste. Ausência de Java, Spark, Delta, S3A ou SeaweedFS deve ser
resolvida pelo bootstrap; não transforma integração obrigatória em aprovação.

O [workflow](../../.github/workflows/ci.yml) usa Ubuntu 24.04, Python 3.11.14,
Java 17.0.21+9, Spark 3.5.7, Delta 3.3.2 e SeaweedFS 4.53. As bibliotecas e JARs
seguem os manifestos e scripts existentes. Checkout v6.0.1 e upload-artifact v6.0.0
estão fixados por SHA, conferidos nas fontes oficiais de
[checkout](https://github.com/actions/checkout/releases) e
[upload-artifact](https://github.com/actions/upload-artifact/releases).
A permissão do job é leitura de conteúdo; credenciais Git não são persistidas.

O job não baixa Home Credit nem chama Kaggle. Executa em cópia sem data,
artifacts, runtime, credenciais, Git ou documentação. O notebook exportado tem
outputs, attachments e metadados removidos; somente a cópia recebe novos hashes
na cadeia de contratos. O notebook histórico e as publicações locais conservam
seus vínculos originais. O manifesto registra ambos os hashes de cada arquivo.

O teste e2e inventa quatro casos, três meses, quatro históricos, nulos e ausência
de histórico; calcula à mão somas, cobertura e rótulos. A correção conserva o
nome técnico `home_credit_with_simulated_change`, exigido pelo protocolo de
eventos, mas os valores da fixture são inventados. Somente a identificação da
origem no produtor é adaptada; os validadores, MERGEs, publicação e leitor são
reais. Cada teste usa temporários; o e2e gera credenciais próprias e limpa variáveis
AWS/Kaggle. Binário e cache de dependências podem ser compartilhados, dados não.
A matriz real F09.6 permanece explicitamente fora do discover e do pacote CI.

O upload usa lista fechada: relatórios de testes, matriz, código, auditoria,
e2e e manifesto de fonte. Não inclui logs, credenciais, dados ou backend S3.
Retenção: sete dias. A configuração foi reproduzida localmente em ambiente novo;
não há alegação de execução remota do GitHub Actions nesta etapa.

O export é um pacote de código para validação, não a entrega final do portfólio.
O notebook original ainda contém outputs históricos e não está liberado para
publicação direta. F11 deve preparar a entrega e revisar divulgação/direitos.
[Aceitação F10](../evidencias/F10_ACEITACAO.md).

## Ampliação E08

A suíte atual inclui a expansão e preserva a evidência histórica F10. Consulte
a [matriz X01–X17](MATRIZ_EXPANSAO.md) e a
[evidência E08](../evidencias/E08_ACEITACAO_EXPANSAO.md) para os novos números.
O wrapper e2e executa tanto o MVP quanto a expansão em JVMs separadas, com dados
inventados e sem Kaggle. O workflow também verifica o gate da expansão e inclui
os dois relatórios sintéticos entre os artefatos publicados. Não houve execução
remota da CI nesta etapa.
