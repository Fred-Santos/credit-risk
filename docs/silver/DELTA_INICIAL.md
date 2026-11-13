# Tabelas Delta iniciais — F03.4

Materializador: [initial_delta.py](../../src/silver/initial_delta.py).
Comando: [materialize_silver_initial.py](../../src/pipelines/materialize_silver_initial.py).
Esta entrega persiste três tabelas tratadas e verifica sua leitura por Delta.
O aceite completo do estado Silver continua em F03.5/F03.6.

Atualização F03.6: o [comando operacional](EXECUCAO_INICIAL.md) reúne as etapas
e emite recibo separado após os contratos. As referências a aceite pendente
abaixo descrevem o manifesto técnico de F03.4, que permanece imutável.

## Nomes, paths e versões

| Origem lógica | Tabela Delta | Grão preservado |
|---|---|---|
| train_base | credit_cases | Um caso de crédito, chave case_id |
| train_static_0 | credit_static | Atributos estáticos por case_id |
| train_applprev_1 | previous_applications | Uma observação anterior por case_id/num_group1 |

Os nomes são explícitos em `TABLES`; não existe descoberta por prefixo.
São tabelas baseadas em paths, sem metastore externo ou necessidade de
`saveAsTable`. Cada tabela possui seu `_delta_log` e seus arquivos de dados.

Pacote: `data/silver/samples/<selection_id>/initial/<materialization_id>/`.
As três pastas acima e `_materialization.json` ficam dentro dele. Cada tabela
começa na **versão Delta 0**, operação `WRITE`. A versão é específica da tabela;
três tabelas na versão 0 não formam uma transação Delta global.

## Identidade e preservação

O identificador de 24 caracteres deriva do hash da seleção, gate/execução Bronze,
política, contrato, notebook, configurações, requirements, código, mapeamento e
versões Spark/Delta. O manifesto guarda a identidade completa e seu hash.
Execuções técnicas diferentes podem reutilizar o mesmo pacote; mudanças em
entrada, política ou implementação produzem outro identificador.

O namespace inicial é **imutável**. Não há overwrite, merge ou append nessa
entrega. Novas revisões e cargas incrementais terão desenho próprio em F04.
O pacote registra o primeiro run_id de materialização; os metadados de linha
continuam apontando para a ingestão Bronze original.

## Como a materialização ocorre

1. Conferir a Bronze aprovada e manter o lock durante todas as ações.
2. Carregar a política, executar as conversões das 23 datas e provar preservação.
3. Sob lock do namespace Silver, preparar uma pasta de staging no mesmo filesystem.
4. Escrever cada DataFrame com `format('delta')` e `mode('errorifexists')`.
5. Ler com Delta e `versionAsOf=0`, conferir schema e comparar todas as linhas
   nos dois sentidos contra o DataFrame tratado.
6. Registrar UUID Delta, versão, operação, schema, chave, contagens e prova de leitura.
7. Registrar checksums de Parquets e arquivos não ocultos dos logs Delta;
   publicar o pacote inteiro com rename local.
8. Abrir os paths finais com o leitor Delta, executar ações e revalidar os artefatos.

O log Delta registra caminhos relativos dos arquivos adicionados; a leitura
após mover o pacote foi exercitada. Não registrar essas tabelas temporárias em
um catálogo e depois presumir que a referência do catálogo acompanha o rename.

Uma falha anterior à publicação remove apenas o staging criado pela tentativa;
nenhum pacote parcial é anunciado no destino final. Não apagamos diretórios
existentes para “consertar” uma reexecução. Se a falha ocorrer depois do rename,
o pacote técnico pode existir mesmo com relatório de execução falho: deve ser
verificado no retry, sem presumir aceite global ou rollback automático.

## Reexecução

Se o destino já existe, o materializador exige manifesto íntegro, identidade
compatível, tabelas e versões esperadas, inventário/checksums e schemas corretos.
Compara novamente os dados armazenados com os candidatos tratados. Só então
retorna `reused=true`, sem criar outra versão ou modificar o primeiro recibo.

Um diretório sem vínculo, conteúdo diferente sob a mesma identidade, arquivo
faltando ou commit externo no pacote inicial bloqueia. Não recorrer a Parquet
ou a uma tabela “parecida” para contornar a falha. Uma nova versão de código ou
política cria outro pacote preservando o anterior, sem escolher automaticamente
qual geração será consumida pela Gold.

## Leitor Delta obrigatório

`open_initial_tables(root, spark)` mantém o lock local, verifica o pacote, lê
apenas com `spark.read.format('delta').option('versionAsOf', versão)` e confere
novamente os artefatos ao sair. Todas as ações devem ocorrer dentro do contexto.
O leitor recusa versões adicionais no namespace inicial imutável.

Arquivos Parquet antigos podem continuar fisicamente presentes depois de um
delete/update Delta. O `_delta_log` determina quais estão ativos. Ler a pasta
com `spark.read.parquet` ignora remoções lógicas e pode incluir linhas antigas
ou duplicadas. Um teste sintético comprova essa diferença; não houve delete nos
dados reais desta entrega.

## Manifesto técnico e aceite Silver

Os [contratos persistidos](../contratos/SILVER_INICIAL.md) foram validados em
F03.5. Em F03.6, o [comando operacional](EXECUCAO_INICIAL.md) passou a repeti-los
antes de emitir um recibo de aceite separado, mantendo o manifesto imutável.

`_materialization.json` usa status `materialized_pending_silver_acceptance`.
O pacote comprova persistência Delta e igualdade com os tratamentos aprovados;
o recibo de F03.6 aceita o estado Silver inicial, sem criar `_READY` dentro
do pacote. Incremento/reconciliação F04 e publicação/recuperação F05 continuam
como dependências antes da Gold em F06.

O rename é uma garantia local do protocolo, não uma transação entre tabelas
Delta ou uma solução equivalente em armazenamento de objetos. Há lock local
exclusivo e não bloqueante, que depende da cooperação dos programas. Não há
orquestração distribuída, coleta automática de pacotes antigos nem vacuum.

## Executar

```bash
bash scripts/project.sh -m src.pipelines.materialize_silver_initial \
  --sample 7d58bbdaa00cbabfbce54d26
bash scripts/project.sh scripts/run_tests.py --integration-required
```

Relatório: `artifacts/silver_materialization/<run_id>.json`, com hashes,
tratamentos, paths, versões e contagens lidas por Delta. Erros produzem relatório
`failed` e código de saída não zero. A identidade é impressa no relatório.

Spark é iniciado com os JARs/extensões Delta antes de criar a JVM. O paralelismo
de snapshots Delta deriva das partições configuradas para o laboratório.
Nos testes, Delta usa um subprocesso com JVM própria: adicionar JARs depois que
outras integrações iniciaram uma JVM Spark simples não é um isolamento confiável.
O runner principal inclui uma verificação que exige a suíte Delta isolada
aprovada, sem skips. Eram oito cenários em F03.4; F03.5 acrescentou o nono,
validando contratos sobre tabelas persistidas. Usam somente fixtures sintéticas.

Atualização F04: [lotes e merge](INCREMENTAL.md) validados em outro namespace,
preservando estes pacotes iniciais. Próximo item atual: F05.1, evolução controlada.
