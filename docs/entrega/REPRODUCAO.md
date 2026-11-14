# Reprodução por instruções e autorrevisão

Esta revisão é feita pelo próprio executor, seguindo comandos em outra cópia.
Não houve avaliador externo. O ambiente do autor e o kernel do notebook não são
requisitos para a trilha sintética. Os dados Home Credit não acompanham a cópia.

Use destinos novos, sem espaços nos exemplos, em Linux x86_64:

```bash
python3 scripts/export_source.py --output /tmp/credit-risk-f11-repro
cd /tmp/credit-risk-f11-repro
bash scripts/bootstrap_environment.sh
bash scripts/bootstrap_analysis.sh
bash scripts/bootstrap_objects.sh
bash scripts/project.sh scripts/check_code.py
bash scripts/objects.sh scripts/demo_portfolio.py --output artifacts/demo
bash scripts/analysis.sh scripts/render_demo.py --output artifacts/demo
```

O export remove outputs de notebook e recalcula os hashes somente da cópia. Os
três bootstraps instalam os runtimes e dependências nessa cópia. Para não herdar
outra instalação Java, remova `JAVA_HOME` do ambiente antes dos comandos ou
aponte-o ao `.runtime/java/jdk-17.0.21+9-jre` dessa cópia. A execução registrada
remove também variáveis AWS/Kaggle/PySpark e PYTHONPATH e não usa credenciais locais.

Confira `report.json`: status passed, quatro etapas aprovadas, CURRENT preservado
na falha, zero linhas de novo MERGE no retry, histórico igual ao baseline e prefixo
removido. Compare os seis CSVs entre execução inicial e reprodução: os hashes
devem coincidir. IDs de publicação, prefixos, horários e duração podem mudar.
Os gráficos devem vir dos CSVs aprovados, não de expectativas desenhadas à mão.

A regressão global limpa F10 já executou 153 testes e T01–T24 sem ignorados.
F11 adiciona comandos de demonstração/entrega e verifica seu comportamento real;
não apresenta a regressão F10 como se tivesse sido executada outra vez sobre F11.
Checks de sintaxe/catálogo e revisão de links acompanham a entrega final.

Resultados e hashes da reprodução estão registrados na evidência F11 local.
No ensaio aprovado, a execução inicial levou 129,069 s e a repetição 136,816 s;
os seis CSVs e os dois gráficos coincidiram por hash. A revisão corrigiu o hook
de falha e os links relativos do pacote antes do aceite. Sem um resultado registrado, este roteiro sozinho não comprova
reprodução. A etapa real usa acesso próprio e as instruções específicas de aquisição;
a trilha acima não baixa dados restritos.
