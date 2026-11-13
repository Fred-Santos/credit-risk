# Leitor lógico da Bronze aprovada — F03.2

Implementação: [read_bronze.py](../../src/silver/read_bronze.py).
O leitor disponibiliza as três tabelas do recorte com dados e metadados
preservados. Não converte datas, não une tabelas por join e não grava Silver.

## Executar a conferência

```bash
bash scripts/project.sh -m src.pipelines.check_silver_input \
  --sample 7d58bbdaa00cbabfbce54d26
bash scripts/project.sh scripts/run_tests.py --integration-required
```

O comando publica um relatório em `artifacts/silver_input/<run_id>.json`, com
status, seleção, execução Bronze aprovada, hashes e contagens consumidas. Uma
exceção gera relatório `failed` e código de saída diferente de zero. O CLI não
publica `_READY` nem tabelas Silver; o gate consultado pertence à Bronze.

## O que o gate precisa provar

`verify_approval` exige recorte explícito verificado por `bind_sample`, namespace
Bronze existente e `_READY.json` de formato conhecido com `status=passed`.
O vínculo de entrada e as contagens devem coincidir com o manifesto do recorte.
Também verifica:

- Inventário exato dos Parquets, manifestos de ingestão e `_input.json`, com
  checksums. Arquivos ausentes, alterados ou extras bloqueiam.
- Relatório de execução dentro do diretório de relatórios da seleção, com
  mesma execução, entrada, contagens e aprovação.
- Hash do YAML de qualidade atual, contrato do recorte e relatório de qualidade
  aprovado para a mesma execução. Mudança no YAML exige revalidar a Bronze.
- Relatório de reconciliação, hash, contrato, seleção, execução e checks aprovados.
- Lineage da publicação, com entrada, saída, seleção e checksums de dados e
  manifestos. Não basta encontrar um evento `COMPLETE` isolado.

Os paths são resolvidos e devem permanecer nos namespaces esperados, inclusive
quando o relatório usa paths absolutos. Os hashes detectam alterações acidentais
e incompatibilidades; não são assinatura contra adulteração coordenada de todas
as evidências. Não há promessa de aprovação criptográfica de um agente externo.

## Mapeamento físico e união

O contrato define exatamente os nomes `train_base`, `train_static_0` e
`train_applprev_1`. O leitor não procura nomes parecidos por prefixo. As entradas
imediatas vêm do recorte verificado; cada caminho de origem determina um batch
esperado, pela mesma função SHA-256 usada na ingestão Bronze.

Para cada batch, confere o manifesto v2, checksum de origem, conjunto de saídas
e seus checksums. Lê individualmente cada Parquet declarado, com `basePath`
apontando à tabela Bronze. Assim, o Spark reconhece `ingest_batch` nas pastas,
sem substituir a coluna `_source_file` já gravada pela ingestão.

Cada fragmento deve conter **schema completo de negócio + quatro metadados**,
com tipos exatos. Só então projeta a ordem comum e usa `unionByName`, sem
`allowMissingColumns=True`. Uma coluna ausente em um fragmento é erro, mesmo
que outro fragmento a contenha. O leitor não faz casts nem fabrica nulos para
conciliar schemas incompatíveis.

Depois da união, verifica contagens, mínimo de linhas, nulos obrigatórios,
unicidade global da chave e metadados de execução/batch. Tabelas ou batches
inesperados bloqueiam. Histórico vazio com schema e arquivos válidos continua
permitido, conforme contrato. Arquivo ilegível gera erro; nenhuma linha é
descartada silenciosamente.

As referências, calendário e domínios já fazem parte do aceite Bronze, vinculado
aos mesmos bytes pelo gate. O leitor repete schema/chaves/contagens defensivamente;
não substitui os contratos de saída Silver que serão criados após os tratamentos.

## Consumo protegido e avaliação preguiçosa

```python
with open_bronze_snapshot(bound, spark) as loaded:
    casos = loaded.frames['train_base']
    total = casos.count()  # A ação ocorre enquanto a publicação está protegida.
    receipt = loaded.receipt
# Persistir um relatório de sucesso somente depois de sair do contexto.
```

`bound` é um `BronzeInput` produzido por `bind_sample`. O contexto mantém o
mesmo `.pipeline.lock` exclusivo usado pela ingestão Bronze. Outro escritor
cooperante não pode iniciar a publicação enquanto o leitor consome seus arquivos.
Ao terminar normalmente, o leitor verifica de novo gate, relatórios, configuração,
entrada e arquivos, detectando mudanças externas ao protocolo.

DataFrames são planos preguiçosos: construir `casos` não equivale a ler todos
os seus valores. Não devolver esse plano para executar ações fora do `with`,
mesmo que Python permita reter a referência. O consumidor é responsável por
respeitar o escopo; uma futura materialização Silver deverá manter suas ações
nesse contexto e só aprovar sua própria saída após a conferência final.

O lock é local e não bloqueante: conflito gera erro para retry posterior, sem
espera ilimitada. Há serialização entre leitores e escritor, em vez de locks
compartilhados nesta implementação. Não usar isso como controle distribuído
para objetos/S3. Não protege contra programas que ignoram o lock; a conferência
final detecta alterações observáveis, sem tornar o filesystem transacional.

Uma falha do consumidor não remove o gate válido do produtor. O leitor não
publica uma nova aprovação Bronze nem sobrescreve dados; em uma materialização
posterior, o sucesso/falha da Silver terá seu próprio controle.

## Escopo e próximos passos

Atualização F03.6: leitura, [tratamentos com guardas](TRATAMENTOS.md), Delta
e contratos estão reunidos no [comando operacional](EXECUCAO_INICIAL.md).
As ações de escrita e validação também respeitam o contexto deste leitor.

O leitor inicial aceita apenas o snapshot de um recorte explícito. O modo RAW
legado e os pacotes de eventos não fazem parte dessa API. O recorte já consolidou
os shards originais `_0`/`_1`; a leitura atual reconhece os batches e fragmentos
efetivamente declarados no seu manifesto, preservando a relação com a origem.
Não adicionar tabelas para imitar toda a exploração antiga do notebook.

As etapas F03.3–F03.6 estão implementadas e validadas no recorte. A próxima
entrega é F04.1, gerador de lotes e cenários declarados. O consumo incremental
terá contrato próprio e não deve ser tratado como leitura de snapshot completo.
