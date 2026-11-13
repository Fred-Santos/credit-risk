"""Relatório offline e gráficos científicos estáticos a partir de agregados conferidos."""
import base64
import csv
from html import escape
import json
from pathlib import Path

SEGMENTS={'no_history':'Sem histórico','one_observation':'1 observação',
          'two_to_five':'2 a 5 observações','six_or_more':'6 ou mais observações'}


def count(value):
    return f'{value:,}'.replace(',','.') if value is not None else '—'


def percent(value):
    return f'{value*100:.3f}%'.replace('.',',') if value is not None else 'não calculável'


def number(value):
    if value is None:
        return 'NULL'
    if isinstance(value,bool):
        return str(value).lower()
    return str(value)


def canonical_json(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n'


def write_csv(path,rows):
    if not rows:
        return
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def charts(view,publication_id,destination):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    matplotlib.rcParams.update({'font.family':'DejaVu Sans','font.size':10,
        'svg.hashsalt':'credit-risk-analysis-v1','axes.spines.top':False,'axes.spines.right':False})
    destination.mkdir(parents=True,exist_ok=True)
    months=view['monthly']
    labels=[f"{r['MONTH']//100}-{r['MONTH']%100:02d}" for r in months]
    x=list(range(len(months)))
    paths=[]

    def save(fig,name):
        fig.suptitle(name.replace('_',' ').capitalize(),fontsize=15,fontweight='bold',x=.06,ha='left')
        fig.text(.06,.015,f'Publicação {publication_id} · Recorte retrospectivo · Sem inferência causal',fontsize=8)
        fig.tight_layout(rect=(.02,.05,.98,.94))
        for extension in ('png','svg'):
            path=destination/(name+'.'+extension)
            metadata={'Date':None} if extension=='svg' else {'Software':'credit-risk-analysis-v1'}
            fig.savefig(path,dpi=150,metadata=metadata)
            paths.append(path)
        plt.close(fig)

    fig,axes=plt.subplots(2,1,figsize=(13,8),sharex=True)
    colors=['#bc621a' if r['small_case_count'] else '#286da8' for r in months]
    bars=axes[0].bar(x,[r['case_count'] for r in months],color=colors)
    for bar,row in zip(bars,months):
        if row['observed_partial_month']:
            bar.set_hatch('///')
        axes[0].annotate(count(row['case_count']),(bar.get_x()+bar.get_width()/2,bar.get_height()),
                         xytext=(0,4),textcoords='offset points',ha='center',fontsize=7)
    axes[0].set_ylabel('Casos (n)')
    axes[0].set_ylim(bottom=0,top=max([r['case_count'] for r in months]+[1])*1.2)
    axes[0].set_title('Laranja: n<500 · Hachura: datas observadas não cobrem o mês inteiro',loc='left',fontsize=10)
    rates=[r['target_1_rate'] if r['target_1_rate'] is not None else float('nan') for r in months]
    axes[1].plot(x,rates,color='#286da8',linewidth=1.4)
    for i,row in enumerate(months):
        if row['target_1_rate'] is not None:
            flagged=row['small_case_count'] or row['few_target_1']
            axes[1].scatter(i,row['target_1_rate'],color='#bc621a' if flagged else '#286da8',zorder=3)
            if flagged:
                axes[1].annotate(f"{row['target_1_count']}/{row['valid_label_count']}",
                    (i,row['target_1_rate']),xytext=(0,8),textcoords='offset points',ha='center',fontsize=8)
    axes[1].set_ylabel('target=1 / rótulos válidos')
    axes[1].set_ylim(bottom=0,top=max([v for v in rates if v==v]+[.01])*1.35)
    axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[1].set_title('Pontos laranja: n<500 ou menos de 20 target=1; flags de leitura, sem teste de significância',loc='left',fontsize=9)
    axes[1].set_xticks(x,labels,rotation=60,ha='right')
    axes[1].set_xlabel('Mês da decisão; tabela do relatório informa todos os numeradores e denominadores')
    save(fig,'volume_e_desfecho')

    fig,ax=plt.subplots(figsize=(13,5.5))
    ax.plot(x,[r['static_coverage_rate'] for r in months],marker='o',label='Cobertura estática / casos',color='#286da8')
    ax.plot(x,[r['history_coverage_rate'] for r in months],marker='s',label='Cobertura histórica / casos',color='#40815e')
    ax.set_ylim(0,1.08)
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_ylabel('Casos com correspondência / casos do mês')
    ax.set_xticks(x,labels,rotation=60,ha='right')
    ax.legend(loc='lower left')
    ax.set_title('Cobertura indica existência da linha; não significa preenchimento de todos os atributos',loc='left',fontsize=10)
    save(fig,'cobertura_por_mes')

    segments=view['segments']
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    positions=list(range(len(segments)))
    for ax in axes:
        ax.set_xticks(positions,[SEGMENTS[r['segment']] for r in segments],rotation=20,ha='right')
    axes[0].bar(positions,[r['case_count'] for r in segments],color='#286da8')
    axes[0].set_ylabel('Casos (n)')
    for i,row in enumerate(segments):
        axes[0].annotate(count(row['case_count']),(i,row['case_count']),xytext=(0,4),textcoords='offset points',ha='center')
        if row['target_1_rate'] is not None:
            axes[1].bar(i,row['target_1_rate'],color='#bc621a' if row['small_case_count'] or row['few_target_1'] else '#40815e')
            axes[1].annotate(f"{row['target_1_count']}/{row['valid_label_count']}",(i,row['target_1_rate']),
                             xytext=(0,4),textcoords='offset points',ha='center',fontsize=9)
    axes[1].set_ylim(0,max([r['target_1_rate'] or 0 for r in segments]+[.01])*1.3)
    axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[1].set_ylabel('target=1 / rótulos válidos')
    axes[1].set_title('Associação descritiva; composição e tempo podem diferir',fontsize=10)
    save(fig,'composicao_por_historico')
    return paths


def findings(payload):
    final=payload['views']['final']
    p=final['population']
    monthly=final['monthly']
    small=[str(r['MONTH']) for r in monthly if r['small_case_count']]
    partial=[f"{r['MONTH']} ({r['observed_first_date']} a {r['observed_last_date']})" for r in monthly if r['observed_partial_month']]
    correction=payload['comparisons']['correction']
    late=payload['comparisons']['late_arrival']
    return [
        ('P01 — Volume observado', f"A publicação final contém {count(p['case_count'])} casos, entre {p['first_date']} e {p['last_date']}, em {len(monthly)} meses. Meses com n<500: {', '.join(small) or 'nenhum'}. Janela observada parcial: {'; '.join(partial) or 'nenhuma'}. Essas flags descrevem o recorte; não estimam o volume operacional da fonte."),
        ('P02 — Desfecho rotulado', f"Foram observados {count(p['target_1_count'])} rótulos target=1 entre {count(p['valid_label_count'])} rótulos válidos: {percent(p['target_1_rate'])}. Ausentes: {count(p['missing_label_count'])}. Cada taxa mensal acompanha numerador e denominador. A maturação dos rótulos e sua disponibilidade na decisão não foram auditadas."),
        ('P03 — Cobertura e composição', f"A estática cobre {count(p['static_covered_count'])}/{count(p['case_count'])} casos ({percent(p['static_coverage_rate'])}), mas annuity está preenchida em {count(p['static_annuity_non_null_count'])}/{count(p['case_count'])} ({percent(p['static_annuity_completeness'])}). O histórico cobre {count(p['history_covered_count'])}/{count(p['case_count'])} casos ({percent(p['history_coverage_rate'])}). Há {count(p['history_row_count'])} observações históricas, com montante preenchido em {count(p['history_amount_non_null_count'])} ({percent(p['history_amount_completeness'])} das observações). Ausência de histórico não é automaticamente erro de qualidade."),
        ('P04 — Efeito da correção simulada', f"Baseline e corrected conservam os mesmos {count(correction['before_cases'])} casos, períodos e rótulos. Mudaram {count(correction['changed_common_cases'])} linhas ABT; os indicadores mensais {'permaneceram iguais' if correction['monthly_unchanged'] else 'mudaram nos períodos exibidos'}. A comparação registra valores anteriores e novos; a correção é simulada. A chegada tardia é comparada separadamente: {late['added_cases']} casos adicionados e {late['changed_common_cases']} casos anteriores alterados."),
        ('P05 — Reprodução', 'As três publicações são explícitas e fixam tabelas por UUID/versão. semantic.json contém os resultados sem horário ou run_id, para comparação entre execuções em processos novos. Os gráficos baseline preservam a população anterior; CURRENT não é alterado.'),
        ('P06 — Confiabilidade no escopo local', 'Os manifestos, arquivos, versões e proveniência foram verificados. O SQL de consumo reconciliou todos os indicadores mensais com a ABT; segmentos foram conferidos por SQL independente. A comparação de correção exige a mesma população e rótulos, evitando atribuir efeito a uma troca de casos.')]


def render_bundle(destination: Path,payload: dict,metadata: dict):
    destination.mkdir(parents=True,exist_ok=True)
    for label,view in payload['views'].items():
        write_csv(destination/(label+'_monthly.csv'),view['monthly'])
        write_csv(destination/(label+'_segments.csv'),view['segments'])
    image_paths=[]
    for label in ('baseline','final'):
        image_paths+=charts(payload['views'][label],metadata['publications'][label]['publication_id'],destination/'figures'/label)
    (destination/'semantic.json').write_text(canonical_json(payload))

    def table(headers,rows):
        return '<div class="table-scroll"><table><thead><tr>'+''.join('<th>'+escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join(
            '<tr>'+''.join('<td>'+escape(str(cell))+'</td>' for cell in row)+'</tr>' for row in rows)+'</tbody></table></div>'

    def image(path,alt):
        encoded=base64.b64encode(path.read_bytes()).decode('ascii')
        return f'<figure><img alt="{escape(alt)}" src="data:image/png;base64,{encoded}"><figcaption>{escape(alt)}</figcaption></figure>'

    body=['<h1>Credit Risk — análise retrospectiva</h1>',
        '<p>Publicação final: <code>'+escape(metadata['publications']['final']['publication_id'])+'</code>. Execução: '+escape(metadata['run_id'])+'.</p>',
        '<p class="notice">Recorte determinístico para laboratório. Não é taxa operacional de carteira, avaliação causal ou base de treino validada no tempo. As correções e chegadas são simulações identificadas.</p>']
    for title,text in findings(payload):
        body+=['<h2>'+escape(title)+'</h2>','<p>'+escape(text)+'</p>']
    body.append('<h2>Série mensal da publicação final</h2>')
    for name in ('volume_e_desfecho','cobertura_por_mes','composicao_por_historico'):
        body.append(image(destination/'figures/final'/(name+'.png'),name.replace('_',' ')))
    monthly=payload['views']['final']['monthly']
    body.append(table(['Mês','Datas observadas','Casos','target=1 / válidos','Proporção','Estática / casos','Histórico / casos','Sinais de leitura'],[
        [r['MONTH'],r['observed_first_date']+' a '+r['observed_last_date'],count(r['case_count']),
         f"{r['target_1_count']}/{r['valid_label_count']}",percent(r['target_1_rate']),
         f"{r['static_covered_count']}/{r['case_count']}",f"{r['history_covered_count']}/{r['case_count']}",
         '; '.join(label for flag,label in [('small_case_count','n<500'),('few_target_1','target=1<20'),('observed_partial_month','janela parcial')] if r[flag]) or '—']
        for r in monthly]))
    body.append('<h2>Composição por observações históricas</h2>')
    body.append(table(['Grupo','Casos','target=1 / válidos','Proporção','Grupo vazio'],[
        [SEGMENTS[r['segment']],count(r['case_count']),f"{r['target_1_count']}/{r['valid_label_count']}",percent(r['target_1_rate']),r['empty_group']]
        for r in payload['views']['final']['segments']]))
    body.append('<h2>Valores da correção simulada — mesma população</h2>')
    rows=[]
    for change in payload['comparisons']['correction']['changed_cases']:
        for column,values in change['columns'].items():
            rows.append([change['case_id'],change['MONTH'],column,number(values['before']),number(values['after'])])
    body.append(table(['Caso','Mês','Coluna ABT','Antes','Depois'],rows))
    body.append('<p>Montantes mantêm as unidades originais não confirmadas. Somar observações não mede dívida atual; contagem histórica não comprova empréstimos distintos.</p>')
    body.append('<h2>Chegada tardia — população diferente</h2>')
    body.append(table(['Caso inserido','Mês original','target','Observações históricas'],[
        [r['case_id'],r['MONTH'],r['target'],r['previous_application_count']] for r in payload['comparisons']['late_arrival']['inserted_cases']]))
    late_rows=[]
    for change in payload['comparisons']['late_arrival']['monthly_changes']:
        old,new=change['before'],change['after']
        late_rows.append([change['MONTH'],old['case_count'] if old else 0,new['case_count'] if new else 0,
            percent(old['target_1_rate']) if old else 'sem grupo',percent(new['target_1_rate']) if new else 'sem grupo'])
    body.append(table(['Mês','Casos antes','Casos depois','Proporção antes','Proporção depois'],late_rows))
    body.append('<details><summary>Gráficos da publicação baseline para reprodução histórica</summary>')
    for name in ('volume_e_desfecho','cobertura_por_mes','composicao_por_historico'):
        body.append(image(destination/'figures/baseline'/(name+'.png'),'baseline: '+name.replace('_',' ')))
    body.append('</details><h2>Interpretação e próximas investigações</h2><p>Achados: contagens, proporções, cobertura e diferenças descritas acima. Hipótese a investigar: a composição dos casos e das fontes ao longo dos meses pode explicar parte das diferenças descritivas. Investigar população original, regras de maturação do rótulo e disponibilidade temporal antes de testar essa hipótese. Não recomendamos decisões de concessão ou alegamos impacto financeiro.</p>')
    body.append('<p>Flags n&lt;500 e target=1&lt;20 são convenções de leitura definidas antes do relatório. Não são testes de significância nem justificam ocultar grupos. Datas observadas parciais não comprovam completude dos outros meses ou cobertura operacional. A seleção por hash não fornece plano de amostragem para inferência de carteira.</p>')
    body.append('<h2>Arquivos e rastreabilidade</h2><ul>')
    for name in ('semantic.json','metadata.json','baseline_monthly.csv','corrected_monthly.csv','final_monthly.csv','final_segments.csv'):
        body.append(f'<li><a href="{name}">{name}</a></li>')
    body.append('</ul><p>SVG e PNG independentes estão em figures/. A exportação completa é local; condições de divulgação seguem a governança da fonte.</p>')
    html='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Credit Risk — análise retrospectiva</title><style>
body{font:16px/1.6 system-ui,sans-serif;color:#233347;max-width:1240px;margin:36px auto;padding:0 24px;background:#fff}h1,h2{line-height:1.25;color:#133f63}h2{margin-top:2em}code{overflow-wrap:anywhere}.notice{border-left:5px solid #bc621a;background:#fff5e8;padding:16px}img{max-width:100%;height:auto}figure{margin:22px 0}figcaption{font-size:14px;color:#536376}.table-scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:9px 11px;border-bottom:1px solid #d9e0e7;text-align:left;white-space:nowrap}th{background:#edf3f8}a{color:#135e97}summary{cursor:pointer;font-weight:bold}
</style><body>'''+''.join(body)+'</body></html>'
    (destination/'report.html').write_text(html,encoding='utf-8')
    paragraphs=['# Credit Risk — relatório retrospectivo',
        'Publicação final: `'+metadata['publications']['final']['publication_id']+'`.']
    for title,text in findings(payload):
        paragraphs+=['\n## '+title+'\n',text]
    paragraphs+=['\n## Gráficos e dados\n','Abra [report.html](report.html) para gráficos, tabelas, comparação de valores e limitações. Dados verificáveis em [semantic.json](semantic.json).']
    (destination/'report.md').write_text('\n\n'.join(paragraphs)+'\n')
    return image_paths
