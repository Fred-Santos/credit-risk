# Evidência F05 — evolução, publicação e recuperação

Data local: 13/11/2026. Python 3.11.14, Java 17, Spark 3.5.7 e Delta 3.3.2.
F05.1–F05.6 aceitas no filesystem local. A F06 consumiu essas publicações na sequência; [evidência Gold](F06_GOLD.md).

## Testes

`bash scripts/project.sh tests/publication_integration.py`: **nove cenários Delta
aprovados em 182,170 s**, sem ignorados. Duas verificações de política também
passaram. O runner global `bash scripts/project.sh scripts/run_tests.py --integration-required`
aprovou **123 verificações em 1050,522 s**, sem ignorados, incluindo as quatro
suítes Delta isoladas de 15, nove, nove e oito cenários. O total do runner
inclui os quatro verificadores de subprocesso; não somar os níveis. Registro
e log: `artifacts/f06/validation/full_suite.json` e `full_suite.log`.

Foram exercitados schema autorizado/incompatível, leitura sem publicação,
falhas antes/depois do commit e entre tabelas, qualidade reprovada, manifesto
antes do ponteiro, falha após troca do ponteiro, locks, rollback, corrupção,
diretório desconhecido e limpeza de resíduos privados sem commit. Retry
preservou as versões concluídas; destino sem vínculo não foi sobrescrito.

## Execução real

```bash
bash scripts/project.sh scripts/measure_resources.py \
  --output artifacts/f05/resources_real.json \
  --workdir data/silver/samples/7d58bbdaa00cbabfbce54d26/published \
  -- bash scripts/project.sh -m src.pipelines.run_publication_demo \
  --sample 7d58bbdaa00cbabfbce54d26 \
  --f04-report artifacts/f04/runs/20261113T020347Z_1609747b.json
```

Execução `20261113T033217Z_04372370`, status `passed`, saída 0. Relatório:
`artifacts/f05/runs/20261113T033217Z_04372370.json`.

| Snapshot | Publicação | Versões de entrada F04 | Linhas base/estática/histórico |
|---|---|---|---|
| baseline | b5e320496adccfe70f22542d | 3/3/3 | 49.999 / 49.999 / 215.382 |
| corrected | 54647e547afac85a7f72c6ca | 3/4/4 | 49.999 / 49.999 / 215.382 |
| late | 1d081af9769d86abc373f48f | 4/5/5 | 50.000 / 50.000 / 215.390 |

As três tabelas de cada publicação começam como cópias Delta versão 0 e
adicionam/preenchem `_silver_contract_version int = 2`, chegando à versão 2.
Os valores antigos foram comparados integralmente à origem nos dois sentidos.
As tabelas e os UUIDs são próprios de cada publicação, sem alterar a F04.

Coluna ausente, tipo incompatível e coluna inesperada foram recusados antes
de escrever. No snapshot corrigido, uma falha deliberada após o commit da
cópia estática preservou CURRENT no baseline. A retomada reconheceu os commits
privados e concluiu a migração, sem duplicação. Os contratos e referências
passaram antes de cada manifesto de aceite.

O rollback selecionou baseline e reproduziu todos os valores; depois CURRENT
foi restaurado para late. O registry é
`artifacts/publications/7d58bbdaa00cbabfbce54d26/silver/`, com manifestos,
intentos, ativações, tentativas e blobs de proveniência por hash.

## Retenção e limites

A auditoria leu todas as publicações e suas versões iniciais. As tabelas têm
retenção Delta de 30 dias; publicações ficam fixadas sem prazo de descarte.
Não há comando de VACUUM real neste protocolo.

Na fixture interna, 10 virou 11. VACUUM com 720 horas preservou a leitura
histórica 10; VACUUM 0, com proteção desabilitada somente nessa fixture, tornou
a versão antiga ilegível e preservou o valor atual 11. As mensagens de arquivo
histórico ausente no log são a falha esperada desse teste. A sessão foi
restaurada e nenhum dado real foi limpo. Não simulamos 30 dias transcorridos.

O protocolo tem um escritor cooperante, manifesto imutável e troca atômica
de CURRENT em filesystem POSIX. A prova não equivale a transação global Delta,
SCD tipo 2, teste de perda de energia ou garantia para objetos/S3.

## Recursos e rastreabilidade

Core: **220,981 s**; processo completo: **223,773 s**. Pico RSS somado da árvore:
3.501.973.504 bytes; o RSS inclui Java/Python/workers e pode contar páginas
compartilhadas. Pico de bytes lógicos no diretório medido: 338.231.738 bytes,
incluindo dados e logs preservados. Não mede temporários Spark ou blocos físicos.

O relatório e os manifestos vinculam RAW, coorte, relatório/lotes/recibos F04,
UUIDs e versões de entrada/saída, código e configuração. Os arquivos de
implementação e contratos usados foram arquivados por hash. Hashes atuais
não são exigidos para consultar o snapshot antigo; as versões e os blobs
publicados são verificados.

Logs: `artifacts/f05/validation/integration.log` e `artifacts/f05/validation/real.log`.
Operação em [PUBLICACAO_E_RECUPERACAO.md](../PUBLICACAO_E_RECUPERACAO.md);
schema em [SILVER_GERENCIADA.md](../contratos/SILVER_GERENCIADA.md).
