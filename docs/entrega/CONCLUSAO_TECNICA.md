# Nota de entrega técnica

Entrega: laboratório local de Engenharia e Análise de Dados, com Python, Spark,
Delta Lake e S3 local. A trilha real usa Home Credit sob acesso local; CI e pacote
de demonstração usam dados inventados. A revisão F11 é autorrevisão, sem avaliador
externo, publicação remota ou infraestrutura AWS.

## Critérios de conclusão

| Critério do roteiro | Evidência e limite |
|---|---|
| Problema e fonte | Escopo e SOURCE registram pergunta, acesso e restrições; não se concede redistribuição geral |
| Ambiente reproduzível | F10: instalação nova e 153 testes; F11: comandos de demo em cópia nova |
| Pipeline completo | E2e F10: RAW inventada → publicação S3; F09: operação sobre entradas reais aprovadas |
| Lakehouse | T09–T18: incremento, precedência, conflito, schema, falhas e histórico com Delta real |
| Gold | ABT por caso; indicadores com denominadores e nulos; oráculos independentes |
| Análise | F07: perguntas respondidas e reprodução de resultados; não equivale a consumo S3 |
| Objetos | F08–F10: API S3, S3A/Delta, reinício e falhas em host único |
| Qualidade/operação | Gates bloqueiam publicação; supervisor diagnostica/restringe retry; lineage e métricas disponíveis |
| Git/CI | Checks locais obrigatórios sem skips; workflow declarado; execução remota não realizada |
| Portfólio honesto | Demo inventada identificada, pacote sanitizado, autorrevisão explícita e limitações preservadas |

A evidência F11 registra o resultado observado da demonstração e reprodução;
essa tabela não substitui os relatórios executados.

## Versões e provas

Python 3.11.14, Java 17.0.21+9, Spark 3.5.7, Delta 3.3.2, Hadoop S3A 3.3.4,
SDK Java 1.12.262 e SeaweedFS 4.53. Dependências Python seguem lockfiles;
bootstrap verifica hashes das distribuições declaradas.

A regressão integral F10 passou com 153 testes, zero ignorados e 24 cenários.
Ela continua identificada como F10; F11 verifica suas novas ferramentas por
execução real da demonstração, reprodução, checks e inspeção do pacote.
Não foi alegada uma nova regressão integral após mudanças documentais.

## O que é entregue e o que permanece separado

O repositório local guarda código, contratos, guia em 12 capítulos, decisões,
procedimentos e evidências. Arquivos reais e credenciais permanecem ignorados.
O notebook histórico conserva outputs e hash original; não deve ser publicado
diretamente. O pacote de demonstração contém somente fonte sanitizada,
documentação selecionada e saídas de dados inventados, com inventário por hash.

Modelo preditivo, disponibilidade temporal para treino, multi-host, cluster,
CDC, alta disponibilidade, AWS e impacto financeiro medido não fazem parte da
entrega. Publicar o código ou resultados reais exige uma ação própria; as
restrições da fonte continuam aplicáveis. A revisão externa e o job remoto são
melhorias verificáveis futuras, não provas já realizadas.

Aprendizados, backlog e dependências de migração estão em EVOLUCAO_E_AWS.md.
A migração não provisionou recursos, escolheu região ou assumiu preços.
