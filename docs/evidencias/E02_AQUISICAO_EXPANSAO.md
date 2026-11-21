# E02 — Aquisição de apoio ao inventário da expansão

Data de referência: 18/11/2026. Aquisição concluída; seleção Bronze temporal pendente.

O catálogo versionado seleciona todas as 17 tabelas de treino, em 32 Parquets,
e `feature_definitions.csv`: **33 arquivos, 1.328.474.848 bytes**.
Os seis arquivos do MVP foram reaproveitados após conferir identidade e SHA-256;
os 27 ausentes foram adquiridos via API autenticada Kaggle. A consulta de rede
exigiu execução fora do sandbox restrito. Nenhum dado existente foi removido.

Foi reutilizado `download_selected`, com lock, journal prepared/complete,
publicação por hard link sem sobrescrita e SHA-256. O catálogo é validado antes
da aquisição: escopo, versão, dicionário, duplicação, relação shard/tabela,
caminhos de treino e tamanhos. Todos os tamanhos adquiridos coincidem com o
catálogo remoto. Os registros completos estão em `data/raw/_acquisition/` e
`artifacts/expansion/acquisition.json`.

Uma segunda execução terminou sem acesso à rede, reutilizando todos os 33
arquivos após conferir seus checksums. Isso demonstra retomada/idempotência da
aquisição nesse conjunto. Testes de catálogo e downloader: **10 testes aprovados**.

```bash
bash scripts/project.sh -m scripts.acquire_expansion
bash scripts/project.sh -m unittest tests.test_expansion_catalog tests.test_download_home_credit -q
```

A seleção continua no catálogo próprio da expansão; o comando original do MVP
mantém sua lista histórica. Nenhuma Silver, Gold, Bronze ou CURRENT foi alterada.
A aquisição foi antecipada como dependência do perfil E00.2, evitando repetir
trabalho em E02. Os itens E02.3/E02.4 ainda precisam da política temporal,
materialização Bronze e reconciliação.

SHA-256 do recibo local:

`ae0467e3e58c526b7de5c6d95533e4fa8792df1d2f5b2ad2d52b4cff9307533a`

## Continuação

A [Bronze temporal](E02_BRONZE_TEMPORAL.md) concluiu a seleção e reconciliação
das 17 tabelas. As pendências acima registram o estado no momento da aquisição.
