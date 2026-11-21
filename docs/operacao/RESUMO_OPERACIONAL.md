# F09.5 — resumo operacional pontual

```bash
bash scripts/objects.sh -m src.pipelines.operational_status \
  --sample 7d58bbdaa00cbabfbce54d26
```

O comando mostra a última execução conhecida, última operação bem-sucedida,
falhas/cancelamentos recentes, relatórios sem estado final, publicação aprovada
observada e sua qualidade registrada. Gera JSON completo e Markdown em
`artifacts/f09/status/<selection_id>/<status_run_id>.json` e `.md`.
`--json` imprime a versão estruturada. Não há daemon, agendador, alerta enviado
ou serviço de monitoramento permanente. Os produtores não são modificados.

## Consulta online e cache

A consulta padrão tenta ler CURRENT e o manifesto no registry **operacional F09**.
Ela não inicia nem encerra o serviço S3. Se o servidor estiver parado, pode mostrar
a última observação válida, identificada como **cached**, sem afirmar que continua
sendo CURRENT. Se nunca houve observação, a publicação aparece indisponível.
Não há substituição automática por uma publicação F08 ou por uma pasta mais nova.

```bash
# Somente relatórios locais e observação anterior; não conecta ao S3.
bash scripts/objects.sh -m src.pipelines.operational_status \
  --sample 7d58bbdaa00cbabfbce54d26 --offline

# Conferência completa das tabelas, com o serviço já disponível.
bash scripts/objects.sh -m src.object_store.service start
bash scripts/objects.sh -m src.pipelines.operational_status \
  --sample 7d58bbdaa00cbabfbce54d26 --verify-tables
bash scripts/objects.sh -m src.object_store.service stop
```

`--offline` e `--verify-tables` são mutuamente exclusivos. A consulta normal
verifica vínculo do ponteiro, hash do manifesto, identidade/coorte, metadados
e validações aprovadas. Não reconta linhas ou lê arquivos de dados.
`--verify-tables` também usa Spark/Delta para conferir arquivos, UUIDs, schemas,
versões e contagens das cinco tabelas. Encerra seu Spark, sem encerrar o S3.

A qualidade exibida é a aprovação armazenada no manifesto. Mesmo uma nova
conferência Delta não repete os oráculos SQL da transformação. A origem da
qualidade e o nível de verificação são explícitos. Se CURRENT mudar durante a
leitura, o resumo avisa e não declara a observação como confirmação atual.

O cache é `last_observed_publication.json`. Seu conteúdo precisa coincidir com
o hash do manifesto e ser uma publicação aprovada da coorte. Cache corrompido
é recusado. Horário e nível da observação anterior permanecem visíveis. Ele é
cache do resumo, não alternativa de leitura dos dados nem aceite de uma carga.

## Execução não é publicação

A última execução é selecionada por started_at_utc, com desempate por operation_id,
não por mtime ou nome do arquivo. Uma operação mais recente que falhou não apaga
a publicação anterior. O resumo mostra os dois estados separadamente. A lista
de falhas contém até dez entradas; failure_count_total informa o total conhecido.

Um relatório running/retry_wait não prova processo vivo: pode ter sido interrompido
à força. O resumo o lista como sem estado final, sem fabricar um diagnóstico de
liveness. Relatórios ilegíveis, métricas inválidas ou formato desconhecido geram
diagnósticos; nesse caso a história é incompleta e a última execução é a última
conhecida entre os documentos válidos. Erros de leitura S3 também são preservados.

No estado usado na validação F09.5, a última execução conhecida é o teste
intencional de fonte ausente da F09.3. Portanto attention é esperado, mesmo com
qualidade aprovada da publicação. Isso não representa nova falha dos dados.

## Alertas locais baseados nas medições

Política: [operational_alerts_v1.yaml](../../configs/operational_alerts_v1.yaml).
As referências são operações reais F09.3, fixadas por path e SHA-256. A política
deriva os limites, em vez de duplicar números sem origem:

| Modo/lote/coorte | Referência | Aviso acima de |
|---|---|---|
| update, primeiro lote, seleção atual | 211,212 s e 5.033.197.568 bytes RSS | 422,423 s ou 7.549.796.352 bytes RSS |
| replay, primeiro lote, seleção atual | 140,684 s e 3.777.167.360 bytes RSS | 281,367 s ou 5.665.751.040 bytes RSS |

Duração: 2× a observação; RSS: 1,5×. São margens iniciais de atenção, escolhidas
para investigação local, não SLA, teste estatístico ou limite de RAM garantido.
A comparação usa a última operação bem-sucedida e exige mesmo modo, lote e coorte.
Sem perfil correspondente, não inventa limite para outro lote ou reconstrução.
Não compara a falha rápida de inicialização com um processamento completo.

As medições são do ambiente local, com os limites descritos na
[F09.3](METRICAS.md). Mudanças de runtime, serviço pré-existente, volume ou
máquina exigem revisão da calibração com novas medições; não há aumento automático
dos limites. Baseline ausente/alterada desabilita a comparação e gera aviso,
sem impedir a exibição dos demais fatos.

Alertas também incluem última operação reprovada/cancelada, documentos sem estado
final, história incompleta e publicação não confirmada nesta consulta. Nenhum
alerta muda CURRENT, apaga histórico, reinicia serviços ou retenta uma pipeline.

`health=ok` significa que este resumo não produziu avisos; não é aceite global
da solução. `attention` indica itens para conferir. Consultas geradas retornam 0,
inclusive com avisos ou cache. Uso inválido retorna 2. Quando --verify-tables é
solicitado e a verificação nova não está disponível/aprovada, o CLI retorna 1,
mesmo que exista cache anteriormente verificado. Não interpretar o código 0 do
resumo como código de sucesso da última carga.

A [matriz operacional F09.6](MATRIZ_OPERACIONAL.md) documenta
os cenários ponta a ponta executados. Fonte, limites de acesso e retenção continuam vigentes.
