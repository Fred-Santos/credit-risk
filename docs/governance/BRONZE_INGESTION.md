# Ingestão Bronze recuperável

Atualização F02.3: entrada explícita, namespace por seleção e marcador de conclusão
estão em [BRONZE_DO_RECORTE.md](../BRONZE_DO_RECORTE.md). Os conceitos abaixo
descrevem o builder local compartilhado; os caminhos são relativos ao namespace.

Cada arquivo RAW é uma unidade de publicação. Seu caminho relativo identifica
um lote estável; SHA-256 detecta alterações no conteúdo. A estrutura é:

```
<namespace_bronze>/<dataset>/ingest_batch=<id>/
    part-*.parquet
    _SUCCESS
    _ingestion.json
```

A leitura continua sendo `spark.read.parquet(caminho_do_dataset)`. Spark descobre
a coluna de partição técnica `ingest_batch`; ela não deve ser usada como feature.
O manifesto oculto contém caminho, checksum da origem e run_id da primeira carga.
Na versão 2 ele registra também checksums dos Parquets de saída. A reexecução
verifica origem e saída antes de pular um arquivo. Manifesto sem esses checksums
ou conteúdo modificado bloqueia a tentativa para revisão.
Metadados de linha `_run_id`, `_ingest_date` e `_source_file` são preservados.

A escrita ocorre em `<namespace_bronze>/.staging`, no mesmo filesystem. Um rename
publica dados e manifesto juntos. Falhas anteriores à publicação não tornam o
lote visível; a próxima tentativa retoma apenas arquivos não publicados.
Alterar o tamanho dos chunks não muda a identidade dos lotes. Cada leitura agora
processa um arquivo de origem por vez para manter a unidade de recuperação.
Um lock do sistema operacional impede builds concorrentes e é liberado quando
o processo termina. Isso se aplica ao armazenamento local deste projeto.

Reexecuções não acrescentam arquivos já publicados. Uma fonte cujo conteúdo
mudou é rejeitada, pois misturar versões quebraria o contrato append-only.
Para substituir uma versão, arquive o diretório do dataset e reconstrua-o com
uma RAW consistente. Arquivos removidos da RAW não apagam históricos da Bronze.

Bronze do formato antigo (Parquets diretamente no dataset) é rejeitada pelo
builder. O entrypoint exige `--sample <selection_id>` ou `--raw`; os modos
escrevem em namespaces separados. Diretórios legados na raiz da Bronze não são
migrados nem apagados automaticamente. Revisar/reconstruir em namespace separado
antes de adotar dados sem os manifestos exigidos.

A atomicidade é por arquivo de origem, não por execução inteira. Os consumidores
devem aguardar o sucesso do pipeline, incluindo qualidade e `_READY.json`. Dados
publicados antes de uma falha permanecem disponíveis para inspeção e retomada;
o marcador de conclusão fica ausente até a aprovação da execução.
