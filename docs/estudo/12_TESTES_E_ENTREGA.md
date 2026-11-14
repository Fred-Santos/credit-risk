# 12 — Testes, CI, evidências e entrega do portfólio

[Percurso](../GUIA_ESTUDO_LAKEHOUSE.md) · Anterior: [Operação](11_OPERACAO_E_STORAGE.md)

Objetivo: avaliar o que cada teste comprova e como transformar implementação
em entrega reproduzível. Pré-requisito: fluxo completo dos capítulos anteriores.

Estado: F10 organiza as suítes e declara a CI com dados sintéticos. A evidência
identifica a execução em ambiente limpo e os limites da revisão de acesso.
F11 concluiu demonstração, autorrevisão e pacote sintético auditado.

## Testar uma afirmação específica

Um teste prepara um cenário, executa um comportamento e compara o resultado
com uma expectativa. A expectativa deve representar a regra que queremos
garantir. Um teste de contagem não prova preservação de todos os valores.

| Tipo | O que verifica | Exemplo do projeto |
|---|---|---|
| Unidade | Regra ou componente isolado | Configuração inválida e precedência |
| Integração | Componentes reais em conjunto | Spark gravando e lendo Delta |
| Ponta a ponta | Fluxo até sua saída de consumo | RAW inventada → Bronze → incremento → publicação Gold S3 |
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

Em [object_store_integration.py](../../tests/object_store_integration.py), os dez
cenários usam SeaweedFS e Spark/Delta reais. Leia a falha após commit privado,
a indisponibilidade do serviço e a reconstrução incremental. CURRENT precisa
continuar apontando ao conjunto aprovado durante falhas privadas. Um teste altera
bytes de Parquet e exige reprovação do inventário. A limpeza é restrita ao
prefixo aleatório criado pela fixture; a fixture de remoção cria seu próprio
servidor temporário. PUT condicional e exclusão local comprovam o protocolo de
um host/driver; não comprovam escritores distribuídos. A
[evidência F08](../evidencias/F08_OBJETOS.md) inclui também a execução real.

Por fim, leia [run_tests.py](../../scripts/run_tests.py). A opção abaixo exige
que a suíte não seja aceita com testes ignorados. O comando executa testes com
fixtures temporárias e inclui integrações reais; requer o ambiente principal
e as camadas analítica e S3 preparadas (`bash scripts/bootstrap_analysis.sh` e
`bash scripts/bootstrap_objects.sh`):

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

## Conferir o comportamento da operação completa

A matriz F09.6 em [operational_matrix_local.py](../../tests/operational_matrix_local.py)
usa entradas reais já aprovadas e destinos temporários. Primeiro estabelece uma
publicação válida. Depois injeta coluna extra, target inválido e indisponibilidade
física do serviço, além de testar entrada ausente. Os contratos e oráculos reais
precisam bloquear as saídas inválidas e conservar o ponteiro anterior.

No caso de qualidade, alterar o DataFrame privado representa um defeito do
produtor; não é uma regra fictícia que sempre retorna falha. Na indisponibilidade,
o serviço para depois de um commit privado. A retomada deve reconhecer o commit,
sem reinserir linhas, e só publicar após completar os checks. Cada tentativa tem
seu run_id e relatório; a operação lógica mantém o mesmo operation_id.

A [matriz documentada](../operacao/MATRIZ_OPERACIONAL.md) descreve os pontos de
injeção e seus limites. O script fica fora do discover e usa dados locais
restritos. A CI F10 usa fixtures sintéticas sem depender dessa fonte.
Separar esses contextos faz parte da reprodução: um teste local com dados reais
não pode ser apresentado como teste automaticamente executável por qualquer clone.

## CI e reprodução por outra pessoa

**Integração contínua (CI)** automatiza verificações quando o código muda.
O [workflow F10](../../.github/workflows/ci.yml) declara ambiente e testes
obrigatórios, usando fixtures sintéticas sem login Kaggle ou dados restritos. Uma dependência ausente deve impedir aprovação
da integração obrigatória, em vez de produzir uma execução aparentemente verde.

A reprodução com recorte real exige acesso autorizado aos dados e instruções
próprias. A evidência deve identificar comando, parâmetros, ambiente, código,
entrada, resultado esperado/obtido e localização dos artefatos.

## Ler a implementação da CI sem perder o sentido

Comece pelo [catálogo](../../tests/suites.json): cada classe tem um grupo.
Depois leia [run_tests.py](../../scripts/run_tests.py): ele descobre testes,
confere o catálogo, executa e grava resultado por ID. `--integration-required`
impede aprovação com testes ignorados. Isso responde uma pergunta concreta:
a integração Delta foi executada ou apenas estava escrita no repositório?

Agora abra [e2e_synthetic.py](../../tests/e2e_synthetic.py). Os quatro casos são
inventados. O caso 1 tem dois históricos e uma correção; o caso 3 tem histórico
com valor nulo; o caso 4 não tem histórico. Antes do Spark, escreva no papel:
quantas linhas a ABT deve ter e quando a soma deve continuar nula? Ao final,
o teste lê a publicação real por S3A e compara com valores calculados à mão.
Os detalhes de cobertura estão na [matriz T01–T24](../testes/MATRIZ_ACEITACAO.md).

Um ambiente limpo começa sem dados, credenciais ou sessão de notebook. Os
scripts instalam Python, Java e dependências declaradas; testes criam seus
dados temporários. Isso permite a outra pessoa verificar o comportamento sem
obter o dataset restrito. Os dados reais continuam importantes para semântica e
custo: o benchmark F10 usa o recorte aprovado, em namespace privado.

Nesse benchmark, o comando precisava de um lote, mas lia sete antes de escolher.
Selecionar os metadados primeiro elimina seis leituras tipadas. O ganho observado
foi de 259,7 s para 185,2 s, com igualdade completa das cinco tabelas. Uma medição
por variante indica oportunidade; não demonstra desempenho estatístico ou SLA.
O espelho completo continua verificado por hash. Aumentar volume não era necessário.

Por fim, leia [export_source.py](../../scripts/export_source.py): um notebook pode
conter dados nos outputs mesmo quando a pasta data está ignorada pelo Git. A
cópia de CI limpa esses outputs e atualiza seus próprios hashes. O original
permanece ligado às evidências históricas. Isso explica por que export limpo e
repositório pronto para publicação são avaliações distintas. Comandos e limites
em [Execução e CI](../testes/EXECUCAO_E_CI.md).

## O que caracteriza a entrega final

A entrega F11 permite explicar o problema, acompanhar a arquitetura, executar o
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

## A entrega F11 como exercício completo

Leia o [README](../../README.md) pelo problema e depois siga a
[demonstração](../entrega/DEMONSTRACAO.md). Ela usa Silver inventada já tipada para
mostrar publicação: três casos, duas observações no caso 1, correção das auxiliares,
falha após commit e leitura anterior. A [imagem](../entrega/imagens/correcao_sintetica.png)
foi gerada dos CSVs consultados. A soma muda e a população permanece igual.

Agora compare com `tests/e2e_synthetic.py`: esse teste começa em RAW, gera amostra,
Bronze e eventos antes de publicar. A demo curta e o e2e têm pontos de partida
diferentes; nenhum deve ser apresentado como se cobrisse sozinho todas as provas.

Na [reprodução](../entrega/REPRODUCAO.md), verifique os seis hashes de CSV entre
execuções. Um ID aleatório diferente não significa dado diferente, assim como
contagem igual não garante valores iguais. O executor declarou autorrevisão;
um avaliador externo e um job remoto seriam evidências adicionais.

Por fim, abra o manifesto do pacote sintético: ele lista cada arquivo, tamanho e
hash. O notebook da cópia tem zero outputs e os gráficos só contêm dados inventados.
O notebook original continua preservado. Isso permite entregar uma demonstração
sem carregar dados restritos junto com o código.

**Exercício:** depois de uma falha após MERGE, a ABT privada já tem 11 e 6.
Por que o leitor ainda deve ver 10 e 5? O retry precisa aplicar novamente o MERGE?

**Conferência:** o leitor escolhe o manifesto aprovado anterior pelo CURRENT.
Commit privado não aprova o conjunto. O retry reconhece o commit já efetuado,
confere seu resultado e completa a publicação; a demo exige zero novas linhas
inseridas/atualizadas por MERGE nessa retomada.
