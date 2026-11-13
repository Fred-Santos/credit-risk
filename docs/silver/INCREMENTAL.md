# Silver incremental local — F04

Entrypoint: [run_incremental_demo.py](../../src/pipelines/run_incremental_demo.py).
Política: [incremental_policy_v1.yaml](../../configs/incremental_policy_v1.yaml).
Transporte: [event_parquet.py](../../src/bronze/event_parquet.py).
Estado: [incremental.py](../../src/silver/incremental.py).

## Finalidade e namespaces

Esta etapa demonstra novos casos, correções de auxiliares, duplicatas e atraso
usando o recorte fixo Home Credit. Todos os eventos são simulados e identificados.
Não há CDC fornecido pela competição. Fixtures sintéticas pertencem aos testes;
a demonstração operacional usa linhas reais da Bronze aprovada.

O pacote Silver inicial F03 permanece imutável. O experimento F04 começa com
tabelas vazias e recebe somente o primeiro lote na primeira aplicação.

| Artefato | Caminho |
|---|---|
| Landing imutável | `data/events/<selection_id>/f04_<identity>/` |
| Estado incremental de trabalho | `data/silver/samples/<selection_id>/incremental/f04_<identity>/` |
| Relatório da tentativa | `artifacts/f04/runs/<run_id>.json` |
| Recibo de aplicação por lote | `<estado>/applied/<batch_id>.json` |

A identidade vincula recorte, gate/execução Bronze, contratos, políticas, código
e runtime. Mudança técnica cria outro experimento; não migra nem sobrescreve um
estado antigo. O mesmo código e entrada reutilizam a landing e o estado.

## Gerador e cenários

As três janelas vêm da política persistida no recorte: semanas 0–51, 52–77 e
78–91. Dois casos elegíveis do primeiro lote são escolhidos por menor `case_id`,
com valores que possam receber a alteração declarada nas duas auxiliares.

O primeiro será o caso de correção. O segundo é retido integralmente, com sua
estática e todo o histórico, para chegar depois dos lotes temporais. A seleção
do recorte não é refeita, nem condicionada ao target. A escolha desses dois casos
serve somente à demonstração técnica, sem finalidade estatística.

| Ordem | Pacote | Conteúdo |
|---|---|---|
| 1–3 | `b00_w000_051`, `b01_w052_077`, `b02_w078_091` | Casos reais e auxiliares, revisão 1; exceto o caso retido |
| 4 | `correction_r2` | Uma estática e uma observação histórica do primeiro caso, revisão 2 |
| 5 | `duplicate_r2` | Duas entregas de cada evento de correção, mesma revisão/payload |
| 6 | `old_revision_r1` | Valores originais das duas linhas corrigidas, revisão 1 |
| 7 | `late_case_r1` | Caso retido e todas as suas auxiliares, revisão 1 |
| Recusado | `reject_old_conflict` | Payload contraditório na revisão 1 já recebida |
| Reexecução | Primeiro pacote novamente | Mesmas entregas e nenhum novo efeito |

As únicas alterações artificiais de negócio são `+1.0` em
`train_static_0.annuity_780A` e em uma observação de
`train_applprev_1.credamount_590A`. Nenhuma chave é alterada. A origem é marcada
como `home_credit_with_simulated_change`; as demais linhas mantêm valores reais.

Antes de aceitar o gerador, os três lotes baseline mais o atraso são unidos e
comparados integralmente à Bronze nos dois sentidos, incluindo proveniência.
Isso verifica que os cenários não perderam, trocaram ou duplicaram a população.

## Transporte e contrato v1

Cada pacote contém uma pasta Parquet para cada uma das três tabelas, inclusive
quando a tabela não tem entregas naquele lote. Histórico vazio com schema é
válido. O pacote inteiro vazio é recusado.

As linhas achatam o payload completo, os quatro metadados Bronze e os campos
escalares do envelope de F02.4. A validação distribuída chama `make_event` e
`validate_event` nos executores, preservando `typed_python_json_v1` para hashes
de payload/evento/entrega. Não se substitui esse hash por Spark `to_json`.
O hash de proveniência adicional tem finalidade separada.

As posições são determinísticas por tabela/lote: ordenação distribuída das
chaves e `zipWithIndex`, que retorna ao driver somente contagens por partição.
Não há coleta integral de payloads. Duplicatas declaradas recebem posições
diferentes, mantendo a identidade de evento. Posição repetida é erro.

O publisher valida os envelopes e os conflitos, escreve em staging, confere a
leitura de volta, registra checksums e publica por rename local. Retry compara
conteúdo lógico nos dois sentidos, preservando arquivos e primeiro recibo.
O manifesto registra `receipt_index`, primeira execução e chegada UTC; esses
campos não definem precedência do negócio.

## Precedência e deduplicação

Maior `_source_revision` prevalece para a chave de negócio: `case_id` na base
e estática, `(case_id,num_group1)` no histórico. A data do negócio e o horário
de chegada não desempatarão revisões. Ausência de linha em pacote parcial
preserva o estado; não há delete ou patch parcial.

Antes de publicar ou aplicar, examinamos todas as revisões do histórico aceito,
inclusive as inferiores à atual. Mesma chave/revisão com payload diferente
rejeita o lote inteiro. No transporte F04, a proveniência da mesma revisão
também precisa concordar; não se escolhe arbitrariamente entre duas origens.

Depois dessa conferência, a janela Spark ordena por revisão decrescente e
`delivery_id` crescente. Esse desempate só escolhe entre entregas concordantes;
nunca resolve um conflito de valores. O resultado tem uma linha por chave.

As métricas satisfazem:

```text
entregas de entrada = duplicatas da mesma revisão
                   + revisões suplantadas dentro do lote
                   + chaves candidatas
```

As entregas continuam preservadas na landing. “Descartes” da deduplicação
descrevem candidatas que não vão ao merge, sem apagar a evidência recebida.

## Aplicação Delta e validação

O estado começa com três tabelas Delta vazias versão 0. O schema inclui os
campos Silver e Bronze mais sete campos de identidade/revisão do evento.
Metadados de entrega, como lote, posição e cenário, permanecem na landing:
reenvios do mesmo evento não tornam o estado dependente de qual entrega chegou.

Todos os candidatos são deduplicados e tratados com as guardas Silver antes
de começar os merges. O merge usa a chave correta, insere chaves novas e
atualiza somente quando `source_revision > target_revision`. Não executa merge
quando inserts/updates são zero, evitando commits vazios.

Inserts, updates, ignorados por igualdade e ignorados por revisão antiga são
classificados antes do merge e comparados às métricas efetivas do commit Delta.
Os commits registram identidade do experimento, lote, pacote e execução.
UUIDs, schemas e metadados dos commits são conferidos no consumo do estado.

Após cada pacote, os contratos Silver são aplicados à projeção de negócio e
metadados Bronze. Estática segue 1:1 com cobertura completa; histórico segue 0:N.
O resultado final também precisa coincidir com as contagens do recorte original.

Recibos de aplicação existentes não são reescritos. Reaplicar um lote ainda
confere o estado atual e registra as métricas da tentativa no relatório novo.

## Idempotência, atraso e reconstrução

Duplicatas, revisão antiga e retry do primeiro lote são comparados com snapshots
Delta fixados antes da operação, em todas as colunas e nos dois sentidos.
Contagens mensais de casos/target e cobertura histórica também devem permanecer
iguais, assim como as versões Delta. São diagnósticos F04, sem produzir Gold.

O caso atrasado deve entrar no período original e preservar todas as suas
relações. As duas correções afetam somente as linhas auxiliares declaradas.

A reconstrução usa todas as entregas aceitas, calcula a maior revisão por chave
com `groupBy/max`, une as revisões vencedoras e remove cópias concordantes do
estado. Não usa a janela de deduplicação nem o motor de merge incremental.
Os candidatos reconstruídos são comparados às três tabelas Delta em todos os
valores nos dois sentidos. Qualquer divergência bloqueia o aceite F04.

## Executar e medir

No ambiente preparado, a partir da raiz:

```bash
bash scripts/project.sh -m src.pipelines.run_incremental_demo \
  --sample 7d58bbdaa00cbabfbce54d26
```

O comando cria/reutiliza a landing, aplica a sequência, repete o primeiro lote,
reconstrói e valida. Não modifica o gate Bronze nem os pacotes Silver F03.
Erros retornam código não zero e relatório `failed` com etapa e causa.

Para medir a árvore de processos e o diretório do estado, usar o wrapper
`scripts/measure_resources.py`, com saída privada distinta por tentativa.
As limitações da amostragem e os resultados medidos ficam na evidência F04.
Mantemos `local[2]`, memória de driver 2g e o recorte atual; não ampliamos volume.

## Limites operacionais e próxima fase

A landing é imutável; o estado incremental é uma área de trabalho mutável,
protegida por um escritor cooperante. Os recibos registram versões aceitas por
lote, mas não há ponteiro de publicação para consumidores Gold.

Uma falha de I/O entre commits pode deixar parte do estado atualizada. A
precedência permite reconhecer linhas já aplicadas no retry, mas a prova
completa de falhas/retomada, evolução, publicação e retenção pertence a F05.
Não se oferece atomicidade global entre as três tabelas. F08 adaptará locks,
rename e I/O ao armazenamento de objetos escolhido.

As condições de F04 são geração fiel, precedência, deduplicação, merge,
idempotência/atraso e equivalência com reconstrução, com evidência real. Somente
após isso o roteiro pode avançar à F05.
