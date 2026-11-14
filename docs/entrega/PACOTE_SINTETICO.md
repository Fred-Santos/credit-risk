# Credit Risk Lakehouse — demonstração sintética

Este pacote contém código, notebook sem outputs e uma demonstração executada
com dados inteiramente inventados. Não inclui Home Credit, resultados individuais
reais, credenciais, logs locais, ambientes instalados ou histórico Git.
A licença do código está em LICENSE; ela não concede direitos sobre o dataset.

O projeto demonstra contratos, Delta, revisões e publicação coerente de três
Silver e duas Gold. A demo começa em Silver tipada, com três casos e dois meses;
não representa toda a ingestão. O teste e2e separado cobre RAW inventada até S3/Gold.

## Preparar e executar

Em Linux x86_64 com Python 3 e acesso à rede:

```bash
bash scripts/bootstrap_environment.sh
bash scripts/bootstrap_analysis.sh
bash scripts/bootstrap_objects.sh
bash scripts/objects.sh scripts/demo_portfolio.py --output artifacts/nova-demo
bash scripts/analysis.sh scripts/render_demo.py --output artifacts/nova-demo
```

Use uma pasta de saída nova. Java fica em `.runtime/java/jdk-17.0.21+9-jre`;
remova JAVA_HOME herdado ou aponte-o para essa instalação. Não é necessário Kaggle.
O serviço S3 usa loopback e credenciais locais geradas. Objetos temporários da
demo são removidos ao final. Para o teste completo desde RAW:

```bash
bash scripts/project.sh scripts/run_tests.py --suite e2e --integration-required
```

## Conferir as saídas incluídas

`demo/report.json` registra a execução aprovada. Os seis CSVs mostram baseline,
correção e leitura histórica. A anuidade do caso inventado 1 muda de 10 para 11
e a soma histórica de 5 para 6; a população permanece em três casos. A falha
após commit privado preserva CURRENT; o retry não repete o MERGE e a leitura
histórica recupera os valores iniciais. `demo/correction.png` é derivado dos CSVs.

[Sequência de apresentação](DEMONSTRACAO.md),
[arquitetura e limites](ARQUITETURA.md),
[reprodução por instruções](REPRODUCAO.md).
`portfolio_manifest.json` permite conferir o inventário e hashes. O manifesto
atesta integridade dos arquivos do pacote, não é assinatura de autoria externa.

A ABT é retrospectiva, sem elegibilidade temporal comprovada para treino. Não há
ML, impacto financeiro medido, alta disponibilidade, multi-host ou AWS provisionada.
A preparação deste arquivo não é uma publicação remota; a disponibilização externa
é uma ação separada. A documentação completa e as evidências reais ficam na cópia
local do projeto e não acompanham esta distribuição sintética.
