# Aprendizados, evolução e inventário para AWS

O escopo local fecha com ingestão, contratos, incremento, publicação, análise,
operação e provas de recuperação. Evoluções abaixo não contam como pendências
ocultas da entrega e não foram provisionadas.

| Aprendizado observado | Consequência |
|---|---|
| Join direto com histórico 1:N duplica casos | Agregar antes do join e conferir o grão da ABT |
| Contagens iguais podem esconder valores alterados | Reconciliar todas as colunas, nos dois sentidos |
| Commit Delta não publica cinco tabelas atomicamente | Manifesto aprovado e ponteiro de consumo da aplicação |
| Retry precisa reconhecer o que já foi commitado | Identidade lógica estável, tentativas separadas e verificação do estado |
| Notebook contém dados também nos outputs | Export sanitizado e hashes próprios sem destruir evidências históricas |
| Dependência ausente não valida integração | CI obrigatória sem skips e bootstrap reproduzido |
| Ler antes de selecionar custava trabalho dispensável | Selecionar metadados antes de ler pacotes tipados, mantendo validação |

| Backlog opcional | Condição e critério para iniciar |
|---|---|
| Revisão externa e GitHub Actions remoto | Autorizar disponibilização do código; registrar job e feedback reais |
| Divulgação de resultados Home Credit | Rever condições/autorização; não incluir dados individuais ou outputs por padrão |
| Mais tabelas/volume | Medir orçamento de recursos e reconciliar novo grão/contratos |
| Orquestrador/agenda | Necessidade operacional concreta e desenho de retomada |
| Dashboard | Pergunta de exploração que justifique manutenção adicional |
| Treino preditivo | Estudo de disponibilidade temporal, vazamento e avaliação fora deste escopo |
| Fonte aberta alternativa | Decisão explícita; inspecionar dados/licença e adaptar contratos |
| AWS | Plano próprio de custo, acesso, segurança, arquitetura e aceite aprovado |

## Dependências e mudanças necessárias na migração

| Dependência local | Versão/desenho atual | Candidato AWS e trabalho necessário |
|---|---|---|
| Python/Java | 3.11.14 / 17.0.21+9 | Empacotar imagem ou ambiente gerenciado compatível |
| Spark/Delta | 3.5.7 / 3.3.2 | Validar versões e extensões no runtime escolhido; não presumir compatibilidade |
| Hadoop S3A/SDK Java | 3.3.4 / 1.12.262 | Conferir classpath, autenticação IAM e semântica do armazenamento |
| SeaweedFS | 4.53, endpoint loopback | Avaliar S3 real; retirar endpoint/credenciais locais, preservar pré-condições |
| Controle de escritor | flock e um host/driver | Projetar coordenação multi-host antes de permitir concorrência |
| RAW/Bronze/artefatos | Filesystem local | Desenhar buckets/prefixos, catálogo, versionamento, IAM e chaves de criptografia |
| Manifesto/CURRENT | API S3 condicional, protocolo próprio | Validar consistência e falhas no S3 real; definir recuperação e observabilidade |
| Metadados Delta | Paths e UUID/versões | Avaliar catálogo e governança; migração não é só copiar arquivos |
| Supervisor | Processo Python e JSON locais | Avaliar serviço de jobs/agenda, estados e armazenamento de logs |
| Análise | Matplotlib e consultas locais | Empacotar consumidor e definir distribuição de relatórios |
| Segredos e rede | Arquivos 0600, loopback | IAM de menor privilégio, rede, rotação e trilha de acesso |
| Retenção | 30 dias, pins, sem VACUUM real | Rever custo e políticas com provas de histórico antes de habilitar limpeza |
| CI | Fixtures sintéticas, dependências fixadas | Identidade de CI sem chaves persistentes e testes de integração próprios |

Serviços, regiões e instâncias não foram escolhidos; não há estimativa de preço
validada nem infraestrutura criada. O inventário descreve dependências de migração,
não recomenda uma contratação ou afirma que o laboratório já roda na AWS.
