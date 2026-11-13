# 12 — Testes, CI, evidências e entrega do portfólio

[Percurso](../GUIA_ESTUDO_LAKEHOUSE.md) · Anterior: [Operação](11_OPERACAO_E_STORAGE.md)

Objetivo: avaliar o que cada teste comprova e como transformar implementação
em entrega reproduzível. Pré-requisito: fluxo completo dos capítulos anteriores.

Estado: suíte local e evidências até F07 implementadas. CI, validação completa
da arquitetura final e demonstração do portfólio previstas em F10/F11.

## Testar uma afirmação específica

Um teste prepara um cenário, executa um comportamento e compara o resultado
com uma expectativa. A expectativa deve representar a regra que queremos
garantir. Um teste de contagem não prova preservação de todos os valores.

| Tipo | O que verifica | Exemplo do projeto |
|---|---|---|
| Unidade | Regra ou componente isolado | Configuração inválida e precedência |
| Integração | Componentes reais em conjunto | Spark gravando e lendo Delta |
| Ponta a ponta | Fluxo até sua saída de consumo | Futuro RAW → publicação Gold → análise |
| Reconciliação | Equivalência entre representações | Bronze versus origem; incremental versus reconstrução |

Uma **fixture** prepara dados e ambiente. Um **oráculo** é a referência que
permite decidir se o resultado está correto. Um **mock** substitui um componente
para isolar comportamento ou injetar falha. Mocks ajudam a testar decisões,
mas não demonstram compatibilidade real entre Java, Spark e Delta.

## Um oráculo que cabe no papel

Use base `{1,2,3}` e histórico `[(1,0),(1,1),(2,0)]`. Antes de executar, sabemos:
três casos, três observações, um caso sem histórico, máximo de duas observações
por caso coberto e quatro linhas no left join direto.

Esse cálculo independente ajuda a detectar erro no código. Gerar o resultado
esperado copiando a mesma lógica da implementação pode reproduzir o mesmo
defeito e deixar o teste passar.

## Testar falhas e repetir operações

Precisamos observar fonte ausente, schema inválido, duplicata, conflito de
revisão, data inválida, arquivo alterado e interrupção de escrita. Também
precisamos conferir o estado deixado pela falha: aceites anteriores preservados,
ausência de nova aprovação indevida e retry consistente.

Exemplo de F03.6: a materialização terminou, mas o contrato foi reprovado.
O teste verifica que não surgiu recibo e que o retry pode revalidar/reutilizar
o pacote técnico. Outro cenário falha entre relatório e recibo e confere
que o aceite anterior continua válido.

## Leitura guiada dos testes reais

Leia [test_silver_contracts.py](../../tests/test_silver_contracts.py), procurando
as expectativas de cardinalidade calculadas à parte. Depois, abra
[delta_initial_integration.py](../../tests/delta_initial_integration.py):
`InitialDeltaIntegrationTests` verifica persistência, enquanto
`SilverExecutionIntegrationTests` cobre o comando consolidado.

Em [incremental_integration.py](../../tests/incremental_integration.py),
acompanhe `IncrementalIntegrationTests`: gerador temporal, correção auxiliar,
chave composta, conflito antigo, atraso e reconstrução independente. A fixture
tem quatro casos, incluindo um sem histórico e outro com duas observações.
Compare os valores esperados escritos à mão com a projeção do estado Delta.

Em [publication_integration.py](../../tests/publication_integration.py), acompanhe
falhas de processo antes/depois de commit e nas janelas de manifesto/CURRENT,
migração de schema e a fixture de retenção destrutiva. A fixture é criada pelo
próprio teste; nenhum caminho de dados reais é aceito para limpeza.

Em [gold_integration.py](../../tests/gold_integration.py), siga primeiro o oráculo
de três casos. Depois leia a correção somente no histórico, a chegada tardia,
a mudança de mês e a falha após MERGE Gold. O teste de qualidade duplica linhas
no produtor, grava Delta e exige que o contrato/oráculo independente reprove;
o validador não é substituído por mock. O teste de retomada confere que não
ocorre segundo MERGE e que a publicação anterior continuou disponível.

Em [analysis_integration.py](../../tests/analysis_integration.py), compare os
oráculos de três casos com o relatório de consumo: duas observações de um caso
não aumentam a população. Um teste corrompe o numerador mensal e exige falha
contra SQL; outro tenta comparar correção com população/rótulo diferentes.
Rótulo nulo e grupo vazio preservam taxas não calculáveis, sem imputar zero.
Esse subprocesso usa Spark; as leituras Delta e os gráficos são exercitados
também pelas duas execuções reais registradas na [F07](../evidencias/F07_ANALISE.md).

Em [test_delta_initial.py](../../tests/test_delta_initial.py), observe o
subprocesso. Delta precisa de uma JVM iniciada com seus JARs; o isolamento evita
depender de uma sessão Spark simples criada por outro teste.

Por fim, leia [run_tests.py](../../scripts/run_tests.py). A opção abaixo exige
que a suíte não seja aceita com testes ignorados. O comando executa testes com
fixtures temporárias e inclui integrações reais; requer o ambiente principal
e a camada analítica preparados (`bash scripts/bootstrap_analysis.sh`):

```bash
bash scripts/project.sh scripts/run_tests.py --integration-required
```

A [evidência F04](../evidencias/F04_INCREMENTAL.md) registra 117 verificações
aprovadas, incluindo as verificações dos 15 cenários Delta anteriores e nove
novos da F04, em JVMs próprias, sem ignorados.
Essa é a linha de base de F04. As evidências [F05](../evidencias/F05_PUBLICACAO.md)
e [F06](../evidencias/F06_GOLD.md) registram as novas suítes e o resultado global
daquela entrega. A [F07](../evidencias/F07_ANALISE.md) atualiza as consultas,
gráficos e reprodução; cenários das fases ainda não construídas continuam pendentes.
A contagem do runner inclui as verificações que executam as suítes
isoladas, então os números não devem ser somados como testes do mesmo nível.

## CI e reprodução por outra pessoa

**Integração contínua (CI)** automatiza verificações quando o código muda.
F10 declarará o ambiente e testes obrigatórios, usando fixtures sintéticas sem
login Kaggle ou dados restritos. Uma dependência ausente deve impedir aprovação
da integração obrigatória, em vez de produzir uma execução aparentemente verde.

A reprodução com recorte real exige acesso autorizado aos dados e instruções
próprias. A evidência deve identificar comando, parâmetros, ambiente, código,
entrada, resultado esperado/obtido e localização dos artefatos.

## O que caracteriza a entrega final

F11 deve permitir explicar o problema, acompanhar a arquitetura, executar o
fluxo, consultar Gold, demonstrar uma correção e reproduzir uma análise anterior.
README, contratos, decisões e demonstração precisam corresponder ao código.
Simulações serão identificadas; resultados de portfólio não serão apresentados
como operação de produção ou impacto financeiro medido.

O conhecimento deste percurso deve permitir defender uma escolha e localizar
sua evidência. Uma ferramenta familiar, um teste verde e um gráfico correto
são partes de uma cadeia que precisa permanecer coerente.

## Atividade e conferência

Um runner mostra sucesso, mas ignorou todos os testes Delta porque faltavam JARs.
O que ele comprova? Como o projeto deve tratar isso?

**Conferência:** ele só comprova os testes efetivamente executados. A integração
Delta permanece sem validação; `--integration-required` deve bloquear o aceite.
Depois, precisamos preparar o ambiente e executar essa integração de fato.

Retorne ao [percurso](../GUIA_ESTUDO_LAKEHOUSE.md) e explique o caminho de uma
linha desde a aquisição até o indicador, indicando onde cada garantia é testada.
