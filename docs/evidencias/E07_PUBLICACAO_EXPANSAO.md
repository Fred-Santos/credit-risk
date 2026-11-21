# E07 — Publicação S3 ampliada e recuperação

Estado: E07.1–E07.4 aceitos no escopo local. Data de referência: 19/11/2026.
Registro: `lakehouse-expansion-v1/publications/a728cbc74ed5507307b398a5`.
CURRENT final: **`58c3de42fe5b3c61ad3eeede`**, dados originais, sem correção artificial.
Histórico simulado aprovado: `269bbb84aca22e4e44d9289b`.

O conjunto tem **42 tabelas Delta**: 17 Silver,
16 blocos Gold, duas ABTs compostas em features/labels (quatro tabelas) e cinco
analíticas. Arquivos Delta são copiados por streaming e SHA-256, preservando
UUID, versões, schemas e valores. Logs com caminhos absolutos/externos são
rejeitados. O readback S3A confere UUID, versão, schema e contagem de cada tabela.
A igualdade de bytes transfere a prova de valores dos snapshots locais; não é
uma nova agregação aproximada ou coleta de registros no driver.

Manifestos Silver, Gold, análise, Bronze e auditoria temporal ficam referenciados
por hash no S3. A RAW permanece local, com inventário de origem no manifesto
Bronze. O preflight conferiu 33 arquivos RAW,
a Bronze e os snapshots aprovados. A execução reutilizou materializações locais
pesadas já medidas em E02–E05; não se declara uma recomputação RAW→Gold do zero.
A correção auxiliar gerou nova Gold e nova análise reais antes da segunda publicação.

## Falhas e recuperação

- `after_copy:silver.train_base`: passed; injetada=True; CURRENT observado `58c3de42fe5b3c61ad3eeede`.
- `before_pointer`: passed; injetada=True; CURRENT observado `58c3de42fe5b3c61ad3eeede`.
- `after_pointer`: passed; injetada=True; CURRENT observado `269bbb84aca22e4e44d9289b`.

A falha privada manteve a publicação aprovada anterior. Após criar o manifesto,
uma falha antes da troca também manteve CURRENT. A falha depois da troca deixou
a nova publicação vigente; o processo consultou CURRENT, retomou o mesmo ID e
confirmou reuso. O rollback selecionou novamente o manifesto original aprovado.
Uma correção auxiliar simulada foi rastreada até um caso Gold, sem mudar casos
ou rótulos; leituras históricas de ambas as publicações passaram. Nenhum byte de
publicação aprovada foi sobrescrito ou removido.

O serviço SeaweedFS foi reiniciado preservando seus diretórios. A leitura posterior
passou. Outro processo/JVM consumiu somente API S3/S3A e reconciliou os indicadores
com o relatório também obtido no S3, sem ler dados locais. O leitor padrão não
retorna labels individuais da avaliação nem o target da Silver base; essa guarda
é de API, sem promessa de ACL contra acesso direto pelo proprietário.

Os 2 ponteiros CURRENT do MVP tiveram os mesmos hashes
antes e depois. A expansão usa `lakehouse-expansion-v1`, preservando `lakehouse-v1`.
O serviço fica disponível para consumo. Uso ML continua bloqueado pelas limitações
E04; os rótulos da análise são descritivos.

## Capacidade, versões e retenção

| Execução | Duração (s) | RSS amostrado (GiB) | Temporários medidos (GiB) |
|---|---:|---:|---:|
| Gold corrigida | 228.9 | 6.09 | 0.20 |
| Análise corrigida | 110.073 | 3.55 | 0.02 |
| Publicação e recuperação | 243.273 | 4.91 | 0.53 |
| Consumidor independente | 55.964 | 1.91 | 0.53 |

O S3 da expansão retém 471 objetos e
1,291,030,660 bytes de tabelas nas duas publicações. Isso não
é o espaço físico total do SeaweedFS, que contém o MVP e histórico interno.
RSS não é heap nem memória de todo o host; a amostragem pode perder picos.
O disco temporário medido não inclui todos os dados persistentes.

Manter heap de 8 GiB e local[2]: a execução terminou sem exigir aumento de heap.
O host Linux/WSL vê cerca de 15,46 GiB. Não extrapolar este resultado para cluster,
escritores distribuídos ou SLA. As publicações são imutáveis e pinadas por prazo
indeterminado; o mínimo operacional é 30 dias e VACUUM real é proibido. As
propriedades Delta originais foram preservadas; não se afirma que seus defaults
foram reescritos para 30 dias. Não há rotina destrutiva de retenção nesta entrega.

## Consumo e reprodução

```bash
bash scripts/objects.sh -m scripts.deliver_expansion consume --selection-id a728cbc74ed5507307b398a5
```

A matriz completa é reproduzível por `scripts/run_expansion_delivery.sh`, com
IDs explícitos dos snapshots base e da Silver simulada. Os scripts e recibos
registram cada execução e o reuso; os detalhes estão em `artifacts/expansion/`.

## Evidências locais


A comparação entre versões encontrou uma alteração nas features de desenvolvimento e zero na avaliação ou nos rótulos, sem casos ausentes/extras. `success=false` na igualdade de desenvolvimento é esperado para a correção; não é falha de aprovação.

Validação: **103 testes unitários**, fixture Delta de análise e fixture S3 de recuperação aprovados, sem ignorados. O catálogo completo foi conferido estaticamente; a suíte completa permanece na E08.
- `artifacts/expansion/e07_delivery.json`: SHA-256 `2885c56923684f9bc91d2e99688e97f4816836c6ae23be1a980693e7cab292b7`.
- `artifacts/expansion/e07_independent_consumer.json`: SHA-256 `34c60901278e43107d2f35dbb47cc5f0a7858d26e0f7189a0edf59714e9adf35`.
- `artifacts/expansion/e07_publication_resources.json`: SHA-256 `d11c6ea65bf44130beef510fdc105c9a10af1c3fb0d95f061278c584973772d3`.
- `artifacts/expansion/e07_consumer_resources.json`: SHA-256 `ebf3bf455b179283743b94ef72f2a59482c1dc87b8cafb602726e7d331047b6b`.
- `artifacts/expansion/e06_e07_tests.json`: SHA-256 `49a3089e9b80dce6c1e1ea6316b0e4594cab5a89e0ab83b0ad42a9b2c8a94466`.
- `artifacts/expansion/e06_e07_unit_tests.json`: SHA-256 `64c7a368bbd6a1f6b4121e9132a36db64304a57f9fdb5cb29bf6d3194dffa88b`.
- `artifacts/expansion/e06_e07_code_checks.json`: SHA-256 `db5301548a9946802df1300764cf9d265f57fdaf4549bf1d947b9f4619c78c5c`.
- `artifacts/expansion/e06_e07_acceptance_mapping.json`: SHA-256 `a7520337e1bdb00893ce115ed17e38acc1f867ef6fcbbb633cbdcc04d95fcaff`.
