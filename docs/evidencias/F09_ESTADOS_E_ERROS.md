# F09.2 — estados, erros e retry limitado

Em 13/11/2026 foi acrescentado o supervisor `src.operation.runner`, acessível
por `src.pipelines.operate_lakehouse`. O processamento permanece no executor
F09.1; sua identidade agora inclui os arquivos do supervisor para proveniência.
As versões anteriores permanecem arquivadas nas publicações históricas.

[Operação e códigos de saída](../operacao/ESTADOS_E_ERROS.md). A operação lógica
recebe operation_id, e cada tentativa recebe outro run_id. Rebuild conserva
operation_id durante retries. Relatórios de operação registram início/fim UTC,
etapas, tentativas, erro, classificação, decisão de retry e erros de encerramento.
A configuração inicial também está dentro do tratamento de falhas.

## Resultado executado

- Sucesso real Spark/Delta/S3: operação `20261113T164816Z_99afd0f9`, código 0.
- Entrada ausente pelo CLI real: operação `20261113T165244Z_93212e84`, código 3, uma tentativa.
- Interrupção real do endpoint: operação `20261113T165222Z_95901a63`, duas tentativas, código 0.

O teste de indisponibilidade usa o serviço e o SDK reais, com um substituto de
Spark para isolar o supervisor: para o servidor antes da primeira leitura,
observa EndpointConnectionError e permite que a segunda tentativa reinicie e
leia o mesmo CURRENT. O ponteiro permaneceu byte a byte igual. Não foi uma
reexecução completa do MERGE depois de indisponibilidade; a execução completa
aprovada acima e as provas anteriores de recuperação dos componentes completam
o escopo desta fase. O serviço terminou parado, conservando dados.

Oito testes direcionados do supervisor passaram, além do wrapper de subprocesso
e dos três testes de seleção F09.1. Cobrem falhas de contexto/configuração,
início do serviço/JVM, contratos, esgotamento, cancelamento, HTTP recuperável ou
rejeitado, manutenção do serviço pré-existente, identidade lógica estável e
erros no encerramento. Cleanup reprovado bloqueia outra tentativa e preserva
a causa original. Logs e resultados: `artifacts/f09/validation/f092/`.

A regressão global F08 de 129 verificações é a linha de base anterior; não foi
reexecutada nesta alteração. Não somar o wrapper aos oito testes internos como
se fossem verificações do mesmo nível. A validação desta mudança usou os testes
direcionados e os cenários reais descritos.

## Limites

Retry padrão de duas tentativas, máximo três; espera fixa configurável de 0–30 s.
Somente erros transitórios reconhecidos são repetidos. Esquema/contrato inválido,
fonte ausente, acesso negado, conflito de escritor e erro desconhecido encerram.
Classificação Java examina causas por classe; não interpreta palavras na mensagem.
Falha após ativação pode deixar nova publicação aprovada; não se presume rollback.
Não houve remoção de dados reais. O laboratório continua com um host/driver
cooperante, sem garantia para processo morto à força ou artefatos não graváveis.
Próxima: F09.3, consolidar métricas por etapa e por operação.
