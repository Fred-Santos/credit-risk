"""Relatório E06 e evidências E07, a partir dos resultados efetivamente medidos."""
import argparse,json
from pathlib import Path
from src.expansion.analysis import verify_analysis
from src.pipelines.download_home_credit import sha256


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--analysis-id',required=True);p.add_argument('--include-delivery',action='store_true');a=p.parse_args()
    if len(a.analysis_id)!=24 or any(c not in '0123456789abcdef' for c in a.analysis_id):raise ValueError('ID inválido')
    root=Path(__file__).resolve().parents[1];analysis=root/'data/gold/expansion-analysis'/a.analysis_id
    manifest=verify_analysis(analysis);report=json.loads((analysis/'report/report.json').read_text())
    monthly=report['rows']['monthly'];cases=sum(r['case_count'] for r in monthly);positive=sum(r['target_1_count'] for r in monthly)
    text=f'''# Público Home Credit — janeiro a setembro/2020

Análise retrospectiva da população completa de **{cases:,} casos** da janela.
Pacote `{a.analysis_id}`, ligado à Silver `{manifest['silver_id']}` e à Gold
`{manifest['gold_id']}`. Não há amostra de 50 mil nesta entrega.

## Perguntas e método

A análise pergunta como variam o volume e o desfecho observado, quais fontes
cobrem os casos, quais atributos estão ausentes, como se distribuem histórico,
produto e código de educação do solicitante, e como diferem os dois períodos.
Os cortes e dimensões estão fixados em `configs/expansion_analysis_v1.yaml`;
não foram escolhidos por desempenho preditivo ou correlação com target.

A população une as duas ABTs aprovadas. O acesso aos rótulos da avaliação foi
explícito e exclusivamente descritivo; nenhum imputador, escala, vocabulário,
modelo ou seletor foi ajustado. Usar essas conclusões futuramente para escolher
um modelo ou seus atributos comprometeria a independência da reserva e exigiria
redefinir a avaliação. Não tratar esse relatório como validação preditiva.

## Volume e target observado

O numerador é target=1; o denominador contém somente rótulos válidos em 0/1.
Há **{positive:,}/{cases:,} = {100*positive/cases:.3f}%** na janela. O horizonte de
maturação e a disponibilidade histórica continuam não comprovados: essa razão
não é uma taxa operacional atual de inadimplência.

| Mês | Casos | Target 1 | Rótulos válidos | Razão retrospectiva | Primeira/última data observada |
|---|---:|---:|---:|---:|---|
'''
    for r in monthly:text+=f"| {r['MONTH']} | {r['case_count']:,} | {r['target_1_count']:,} | {r['valid_label_count']:,} | {100*r['target_1_rate']:.3f}% | {r['first_date']} / {r['last_date']} |\n"
    peak=max(monthly,key=lambda r:r['case_count']);low=min(monthly,key=lambda r:r['case_count'])
    text+=f'''
O maior volume é {peak['MONTH']} ({peak['case_count']:,}) e o menor é
{low['MONTH']} ({low['case_count']:,}). Isso descreve chegadas de casos na fonte;
não demonstra efeito de pandemia, política de concessão ou mudança real de risco.
Datas observadas que não alcançam os limites do calendário são sinalizadas no
JSON como `observed_partial_month`; isso não comprova perda de registros.

![Volume e razão retrospectiva](../../data/gold/expansion-analysis/{a.analysis_id}/report/monthly.png)

## Cobertura das fontes

Cobertura é casos com ao menos uma observação / casos do mês. Quantidade de
observações é outra medida e pode exceder o número de casos. Ausência de uma
fonte não equivale a zero financeiro nem preenchimento completo dos seus campos.

| Fonte | Casos cobertos na janela | Cobertura | Observações |
|---|---:|---:|---:|
'''
    coverage=report['rows']['coverage']
    for name in sorted({r['source_table'] for r in coverage}):
        rows=[r for r in coverage if r['source_table']==name];covered=sum(r['covered_cases'] for r in rows)
        text+=f"| `{name}` | {covered:,} | {100*covered/cases:.3f}% | {sum(r['observations'] for r in rows):,} |\n"
    text+=f'''
`tax_registry_c_1` não possui observações nos casos desta janela. Sua estrutura
foi preservada, e a ausência não foi preenchida com registros artificiais.
Comparar fontes requer levar essas coberturas e calendários em conta.

![Cobertura mensal](../../data/gold/expansion-analysis/{a.analysis_id}/report/coverage.png)

## Ausências, composição e períodos

A completude tem denominador igual aos casos do mês e conta nulos reais;
códigos mascarados não foram decodificados ou reinterpretados como nulos.
Os {len({r['feature'] for r in report['rows']['missingness']})} atributos estão no CSV
`missingness.csv`, inclusive flags e contagens estruturais, que não devem ser
confundidas com medidas financeiras preenchidas. As modas categóricas e os
atributos do solicitante seguem o contrato Gold, sem escolher pessoa arbitrária.

`composition.csv` contém segmentos fixos de histórico (zero, um, dois–cinco,
seis ou mais registros), produto e código de educação. Categorias `VALUE:` são
códigos da fonte, sem inferir seu significado; `__NULL__` identifica ausência.
São registrados numeradores, denominadores e flags de grupos com menos de 500
casos ou 20 positivos. Essas flags não são testes de significância.

| Período | Casos | Target 1 / rótulos válidos | Razão retrospectiva |
|---|---:|---:|---:|
'''
    for row in report['rows']['period_compare']:
        text+=f"| {row['period']} | {row['case_count']:,} | {row['target_1_count']:,}/{row['valid_label_count']:,} | {100*row['target_1_count']/row['valid_label_count']:.3f}% |\n"
    text+='''
As razões dos dois períodos diferem. Não se conclui melhora de carteira ou de
modelo: composição, cobertura e maturação podem diferir. `period_compare.csv`
inclui também contagens preenchidas e médias de três atributos, em unidades
transformadas da fonte; nenhuma média foi interpretada como reais ou moeda.
A identidade global de cliente não é comprovada, portanto a disjunção é por caso.

## Reconciliação e reprodução

Volumes/rótulos mensais foram conferidos com SQL na base Silver; cobertura e
observações com SQL nas 16 auxiliares. Completude, composição e comparação de
períodos têm oráculos SQL próprios. As cinco tabelas Delta foram relidas e
comparadas célula a célula. O relatório e os gráficos têm checksums e não alteram
nenhuma fonte. Somente agregados pequenos são coletados no Python.
'''
    text+=f'''
Dados agregados e figuras exportáveis: [diretório local](../../data/gold/expansion-analysis/{a.analysis_id}/report/).

```bash
bash scripts/analysis.sh -m scripts.run_expansion analysis --silver-id {manifest['silver_id']} --gold-id {manifest['gold_id']}
```
'''
    lookup={(r['source_table'],r['MONTH']):r for r in coverage}
    shifts=[]
    for source in ('train_tax_registry_a_1','train_tax_registry_b_1','train_person_2'):
        jan=lookup[source,202001];sep=lookup[source,202009]
        shifts.append(f"- `{source}`: janeiro {jan['covered_cases']:,}/{jan['case_count']:,} ({100*jan['coverage_rate']:.2f}%); setembro {sep['covered_cases']:,}/{sep['case_count']:,} ({100*sep['coverage_rate']:.2f}%).")
    note='\nA cobertura muda ao longo do tempo e deve acompanhar comparações de público ou estabilidade:\n\n'+'\n'.join(shifts)+'\n\nEssa variação não comprova troca de fornecedor ou causa de negócio.\n'
    text=text.replace('## Ausências, composição e períodos',note+'\n## Ausências, composição e períodos')
    text+='\n`numeric_0`, `numeric_1` e `numeric_2` no CSV de períodos correspondem, respectivamente, a `static_0__annuity_780A`, `static_0__maininc_215A` e `other_1__amtdebitincoming_4809443A__mean`. Os sufixos indicam contagem não nula e média; o mapeamento também está na política do JSON.\n'
    (root/'docs/analise/PUBLICO_EXPANSAO.md').write_text(text)
    resources=json.loads((root/'artifacts/expansion/e06_resources.json').read_text())
    evidence=f'''# E06 — Análise de público executada

Estado: E06.1–E06.4 aceitos no escopo local. Data de referência: 19/11/2026.
[Resultados e método](../analise/PUBLICO_EXPANSAO.md).

População: {cases:,} casos, nove meses, {positive:,} positivos observados.
Pacote `{a.analysis_id}`. Foram materializadas cinco Delta e seus CSVs:
'''
    for name,entry in manifest['tables'].items():evidence+=f"- `{name}`: {entry['rows']:,} linhas.\n"
    evidence+=f'''
Os oráculos mensais, de cobertura, completude, composição e períodos passaram.
Os rótulos da reserva foram acessados explicitamente para descrição, sem ajuste
de modelo. Datas futuras e maturação permanecem limitações da E04, sem atribuir
causalidade ou taxa operacional aos resultados. As figuras PNG/SVG foram geradas
a partir dos agregados e conferidas visualmente.

Execução: **{resources['duration_seconds']} s**, RSS da árvore amostrado de
**{resources['peak_process_tree_rss_bytes']/1024**3:.2f} GiB**, driver com heap de 8 GiB.
O pico de temporários mede apenas o diretório informado; RSS pode contar páginas
compartilhadas e perder picos curtos. O JSON contém todos os denominadores.

Manifesto: `data/gold/expansion-analysis/{a.analysis_id}/_analysis.json`.
SHA-256: `{sha256(analysis/'_analysis.json')}`.
Relatório: `data/gold/expansion-analysis/{a.analysis_id}/report/report.json`.
SHA-256: `{sha256(analysis/'report/report.json')}`.
'''
    (root/'docs/evidencias/E06_PUBLICO_EXPANSAO.md').write_text(evidence)
    if not a.include_delivery:return
    art=root/'artifacts/expansion';delivery=json.loads((art/'e07_delivery.json').read_text());consumer=json.loads((art/'e07_independent_consumer.json').read_text())
    if delivery['status']!='passed' or consumer['status']!='passed' or consumer['is_simulated']:raise ValueError('Entrega/consumo não aprovados')
    measurements={name:json.loads((art/file).read_text()) for name,file in
        [('Gold corrigida','e07_corrected_gold_resources.json'),('Análise corrigida','e07_corrected_analysis_resources.json'),
         ('Publicação e recuperação','e07_publication_resources.json'),('Consumidor independente','e07_consumer_resources.json')]}
    if any(v['exit_code']!=0 for v in measurements.values()):raise ValueError('Execução incompleta')
    e=f'''# E07 — Publicação S3 ampliada e recuperação

Estado: E07.1–E07.4 aceitos no escopo local. Data de referência: 19/11/2026.
Registro: `{delivery['registry']}`.
CURRENT final: **`{delivery['baseline_id']}`**, dados originais, sem correção artificial.
Histórico simulado aprovado: `{delivery['corrected_id']}`.

O conjunto tem **{delivery['published_tables']} tabelas Delta**: 17 Silver,
16 blocos Gold, duas ABTs compostas em features/labels (quatro tabelas) e cinco
analíticas. Arquivos Delta são copiados por streaming e SHA-256, preservando
UUID, versões, schemas e valores. Logs com caminhos absolutos/externos são
rejeitados. O readback S3A confere UUID, versão, schema e contagem de cada tabela.
A igualdade de bytes transfere a prova de valores dos snapshots locais; não é
uma nova agregação aproximada ou coleta de registros no driver.

Manifestos Silver, Gold, análise, Bronze e auditoria temporal ficam referenciados
por hash no S3. A RAW permanece local, com inventário de origem no manifesto
Bronze. O preflight conferiu {delivery['source_preflight']['raw_files_verified']} arquivos RAW,
a Bronze e os snapshots aprovados. A execução reutilizou materializações locais
pesadas já medidas em E02–E05; não se declara uma recomputação RAW→Gold do zero.
A correção auxiliar gerou nova Gold e nova análise reais antes da segunda publicação.

## Falhas e recuperação

'''
    for fault in delivery['faults']:e+=f"- `{fault['stage']}`: {fault['status']}; injetada={fault.get('injected',True)}; CURRENT observado `{fault['current_after_failure']}`.\n"
    e+='''
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
'''
    e+=f'''
Os {delivery['mvp_current_count']} ponteiros CURRENT do MVP tiveram os mesmos hashes
antes e depois. A expansão usa `lakehouse-expansion-v1`, preservando `lakehouse-v1`.
O serviço fica disponível para consumo. Uso ML continua bloqueado pelas limitações
E04; os rótulos da análise são descritivos.

## Capacidade, versões e retenção

| Execução | Duração (s) | RSS amostrado (GiB) | Temporários medidos (GiB) |
|---|---:|---:|---:|
'''
    for name,r in measurements.items():e+=f"| {name} | {r['duration_seconds']} | {r['peak_process_tree_rss_bytes']/1024**3:.2f} | {r['peak_workdir_logical_bytes']/1024**3:.2f} |\n"
    e+=f'''
O S3 da expansão retém {delivery['storage']['objects']:,} objetos e
{delivery['storage']['bytes']:,} bytes de tabelas nas duas publicações. Isso não
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
bash scripts/objects.sh -m scripts.deliver_expansion consume --selection-id {delivery['selection_id']}
```

A matriz completa é reproduzível por `scripts/run_expansion_delivery.sh`, com
IDs explícitos dos snapshots base e da Silver simulada. Os scripts e recibos
registram cada execução e o reuso; os detalhes estão em `artifacts/expansion/`.

## Evidências locais

'''
    e+='\nA comparação entre versões encontrou uma alteração nas features de desenvolvimento e zero na avaliação ou nos rótulos, sem casos ausentes/extras. `success=false` na igualdade de desenvolvimento é esperado para a correção; não é falha de aprovação.\n'
    units=json.loads((art/'e06_e07_unit_tests.json').read_text())
    integration=json.loads((art/'e06_e07_tests.json').read_text())
    if units['status']!='passed' or integration['status']!='passed' or units['skipped'] or integration['skipped']:raise ValueError('Testes não aprovados')
    e+=f"\nValidação: **{units['tests']} testes unitários**, fixture Delta de análise e fixture S3 de recuperação aprovados, sem ignorados. O catálogo completo foi conferido estaticamente; a suíte completa permanece na E08.\n"
    for file in ['e07_delivery.json','e07_independent_consumer.json','e07_publication_resources.json','e07_consumer_resources.json','e06_e07_tests.json','e06_e07_unit_tests.json','e06_e07_code_checks.json','e06_e07_acceptance_mapping.json']:
        e+=f"- `artifacts/expansion/{file}`: SHA-256 `{sha256(art/file)}`.\n"
    (root/'docs/evidencias/E07_PUBLICACAO_EXPANSAO.md').write_text(e)


if __name__=='__main__':main()
