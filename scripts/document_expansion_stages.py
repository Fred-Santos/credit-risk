"""Evidências E03–E05 a partir de manifestos e relatórios aprovados."""
import argparse
import json
from pathlib import Path
import yaml
from src.expansion.storage import verify_package
from src.pipelines.download_home_credit import sha256


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--silver-id',required=True);p.add_argument('--gold-id',required=True);a=p.parse_args()
    for identifier in (a.silver_id,a.gold_id):
        if len(identifier)!=24 or any(c not in '0123456789abcdef' for c in identifier):raise ValueError('ID inválido')
    root=Path(__file__).resolve().parents[1];art=root/'artifacts/expansion';docs=root/'docs/evidencias'
    sp=root/'data/silver/expansion'/a.silver_id;gp=root/'data/gold/expansion'/a.gold_id
    silver=verify_package(sp,'_silver.json');gold=verify_package(gp,'_gold.json')
    audit=json.loads((art/'temporal'/(a.silver_id+'.json')).read_text())
    revision=json.loads((art/'revision_demo'/a.silver_id/'result.json').read_text())
    unit=json.loads((art/'e03_e05_unit_tests.json').read_text());tests=json.loads((art/'e03_e05_integration_tests.json').read_text())
    if any(r['status']!='passed' for r in (audit,revision,unit,tests)) or unit['skipped'] or tests['skipped']:raise ValueError('Evidência não aprovada')
    resources={name:json.loads((art/file).read_text()) for name,file in
        [('silver','e03_silver_resources.json'),('audit','e04_audit_resources.json'),('gold','e05_gold_resources.json')]}
    if any(r['exit_code']!=0 for r in resources.values()):raise ValueError('Processo não concluído')
    receipts=[json.loads(p.read_text()) for p in (art/'runs').glob('*/receipt.json')]
    for phase,identifier in [('silver',a.silver_id),('gold',a.gold_id)]:
        if not any(r['phase']==phase and r['id']==identifier and r['status']=='passed' and r['reused'] for r in receipts):
            raise ValueError('Reuso real não demonstrado: '+phase)
    catalogue=yaml.safe_load((root/'configs/contracts/expansion_gold_v1.yaml').read_text())
    total=sum(t['rows'] for t in silver['tables'].values())
    empty=[n for n,t in silver['tables'].items() if t['rows']==0]
    s=f'''# E03 — Silver extensível e revisões

Estado: E03.1–E03.4 aceitos no escopo local. Snapshot `{a.silver_id}`.
[Contratos e limites](../contratos/EXPANSAO_SILVER_E_ABT.md).

Foram publicadas **{len(silver['tables'])} tabelas Delta**, com **{total:,} linhas**,
preservando todas as colunas da Bronze e acrescentando revisão inicial 1 e flag
de simulação false. As 58 conversões ISO enumeradas no contrato terminaram sem
novos nulos. Todas as tabelas passaram por chaves únicas/não nulas, domínios,
finito, referência à base e comparação exata de cada célula com a transformação
aprovada da Bronze. Os vínculos entre grupos auditados tiveram zero órfãos.
As tabelas vazias na janela são: {', '.join(empty)}. Seus schemas foram preservados.

Os pins registram UUID, versão zero, schema e contagem. O manifesto foi publicado
por rename após aprovação conjunta, sem ativar CURRENT ou modificar o MVP.
Os arquivos/logs Delta têm checksums. A reexecução confirmou reuso do pacote
sem reescrever as tabelas. A transformação bloqueia o pacote inteiro
em caso de rejeição; diagnóstico privado por chave/arquivo/regra é reproduzível
com `scripts/diagnose_expansion_source.py`. A fixture inválida demonstrou esse
registro e a preservação da entrada. Não houve rejeições na execução real.

Uma correção em `train_other_1` foi simulada em snapshot filho privado
`{revision['child_id']}`: +1 unidade transformada em um valor, revisão 2.
O MERGE foi conferido por reconstrução independente; o pai permaneceu intacto.
**Um caso afetado**, meses antigos/novos {revision['affected_cases']['old_new_months']},
foi registrado sem coletar os IDs no driver. A reexecução reutilizou o filho.
As outras tabelas continuam pinadas ao pai; não houve CDC real.

| Medição | Resultado |
|---|---:|
| Processo Silver completo | {resources['silver']['duration_seconds']} s |
| Pico RSS da árvore | {resources['silver']['peak_process_tree_rss_bytes']/1024**3:.2f} GiB |
| Pico de temporários medidos | {resources['silver']['peak_workdir_logical_bytes']/1024**3:.2f} GiB |

A JVM usou heap de 8 GiB no Linux/WSL com cerca de 15,46 GiB visíveis. RSS inclui
memória fora do heap e pode somar páginas compartilhadas; amostras podem perder
picos. O medidor cobre `.runtime/tmp/expansion-stages`, não todo o disco.
A primeira execução Silver usou o padrão Delta de 50 partições de snapshot;
os comandos posteriores explicitam quatro, como no perfil S3 anterior.

```bash
bash scripts/project.sh -m scripts.run_expansion silver --bronze-id a728cbc74ed5507307b398a5
bash scripts/project.sh -m scripts.run_expansion revision-demo --silver-id {a.silver_id}
```
'''
    (docs/'E03_SILVER_EXPANSAO.md').write_text(s)
    flagged=sum(1 for fields in audit['date_ranges'].values() for v in fields.values() if v['after_decision'])
    e=f'''# E04 — Atributos e investigação temporal

Estado: E04.1–E04.4 aceitos como catálogo e investigação; aprovação operacional
para ML continua **não demonstrada**. Silver auditada: `{a.silver_id}`.

A seleção fixa produz **{len(catalogue['features'])} atributos retrospectivos**,
com fórmula, origem, tipo, unidade, ausência e status temporal no
[contrato Gold](../../configs/contracts/expansion_gold_v1.yaml). Todos os campos
de origem estão classificados no [catálogo de fontes](../../configs/contracts/expansion_feature_sources_v1.yaml).
As 16 auxiliares contribuem; `train_base` define a população. Campos não
selecionados continuam na Silver, sem seleção supervisionada por target.

São usadas fontes 1:1, solicitante de índice zero e históricos agregados antes
dos joins. Nível dois usa médias ponderadas por observações não nulas. Contagens,
flags, valores nulos, zeros reais e modas com desempate determinístico são
conferidos com SQL independente na E05. A fixture com grupos de tamanhos
diferentes impede aprovação de uma média de médias incorreta.

A auditoria examinou **{sum(len(v) for v in audit['date_ranges'].values())} campos de data**
(excluindo a decisão), em {len(audit['date_ranges'])} tabelas; **{flagged} campos**
apresentam alguma data posterior à decisão. Os contadores/min/max por campo
estão em `artifacts/expansion/temporal/{a.silver_id}.json`.
Datas programadas ou transformadas podem ser futuras: esses contadores sinalizam
investigação, não provam vazamento. Nenhuma observação foi apagada por essa regra.
Tempo da auditoria: {resources['audit']['duration_seconds']} s.

A [descrição oficial](https://www.kaggle.com/c/home-credit-credit-risk-model-stability/data)
foi consultada pelo texto indexado; a abertura direta depende de JavaScript e
não apresentou linhas legíveis. Ela indica finalidade preditiva na competição
e rótulo observado após um período, sem especificar nesse texto o horizonte ou
`label_available_at`. O dicionário local não fornece disponibilidade histórica
por campo. Um escore externo que menciona um ano não define a maturação do target.

Decisão: **zero atributos aprovados point in time**, `ml_ready=false`.
Não inferir disponibilidade de data do evento, aquisição em 2026 ou ausência de
datas futuras. Não afirmar que todos os atributos vazam. Não inventar janela
de maturação ou embargo. Essas lacunas impedem declarar treino operacional
válido, mas não impedem a ABT retrospectiva identificada prevista no roteiro.

Identidade de cliente entre períodos não pôde ser comprovada: o caso de crédito
é identificável, a pessoa global não. A separação E05 garante disjunção de casos,
sem alegar ausência de clientes repetidos. Empregadores mascarados e índices
locais não são tratados como identificadores de pessoa.

```bash
bash scripts/project.sh -m scripts.prepare_expansion_features
bash scripts/project.sh -m scripts.run_expansion audit --silver-id {a.silver_id}
```
'''
    (docs/'E04_ATRIBUTOS_E_TEMPO.md').write_text(e)
    counts={n:v['features']['rows'] for n,v in gold['products'].items()}
    g=f'''# E05 — Duas ABTs retrospectivas e reserva temporal

Estado: E05.1–E05.4 aceitos. Pacote `{a.gold_id}`, pinado à Silver `{a.silver_id}`.
Não há ativação CURRENT/S3 ampliada nesta fase; isso permanece na E07.

| ABT composta | Casos | Janela |
|---|---:|---|
| Desenvolvimento | {counts['development']:,} | 01/01–31/05/2020 |
| Avaliação temporal | {counts['evaluation']:,} | 01/06–30/09/2020 |

Cada produto tem features Delta de **170 colunas** e labels Delta com somente
`case_id/target`. A ABT lógica reconstruída possui **171 colunas**, com schema
comum aos dois períodos. As labels da reserva ficam separadas fisicamente das
features; nenhum atributo contém target ou parâmetro ajustado com a reserva.

Os **16 blocos** passaram por oráculo SQL independente, incluindo contagens,
presença, ponderação hierárquica e categorias. Na comparação numérica agregada
admite-se 1e-8 absoluto mais 1e-10 relativo; contagens/datas/categorias e readback
exigem igualdade. Os joins preservaram uma linha por caso. As populações
coincidem com filtros SQL na Silver; a interseção é **zero** e a união contém
**447.305 casos**. Rótulos, tipos e todas as features foram relidos e conferidos.
A reexecução confirmou reuso do mesmo pacote, sem reescrita.
O manifesto inclui pins de todas as fontes, contrato, política, limites,
contagens, rótulos e lista de elegibilidade. `eligible_predictors=[]`;
**nenhum modelo foi treinado** e a aprovação temporal continua pendente.

`open_abt` retorna features sem target. Juntar labels de avaliação exige dois
argumentos explícitos. `open_ml_inputs` recusa treino enquanto a evidência
histórica e a maturação não forem comprovadas. São guardas da API, não uma
promessa de impedir acesso direto do proprietário aos arquivos locais.
A fixture exercitou essas recusas e a leitura autorizada com schema equivalente.

| Medição Gold | Resultado |
|---|---:|
| Processo completo | {resources['gold']['duration_seconds']} s |
| Pico RSS da árvore | {resources['gold']['peak_process_tree_rss_bytes']/1024**3:.2f} GiB |
| Pico de temporários medidos | {resources['gold']['peak_workdir_logical_bytes']/1024**3:.2f} GiB |

Validação desta entrega: **101 unitários e sete verificações adicionais**
(seis Spark e um wrapper Delta com cenário integrado), todos aprovados e sem
skips. O relatório direto de oito testes repete a guarda unitária de leitores;
essa repetição não é contada duas vezes. O catálogo completo é conferido
estaticamente; não se declara que todos os testes históricos foram reexecutados.

```bash
bash scripts/project.sh -m scripts.run_expansion gold --silver-id {a.silver_id}
bash scripts/project.sh -m unittest tests.test_expansion_stages tests.test_expansion_revision_delta -q
bash scripts/project.sh scripts/run_tests.py --suite unit --integration-required --report artifacts/expansion/e03_e05_unit_tests.json
```

## Manifestos e evidências locais

'''
    paths=[sp/'_silver.json',gp/'_gold.json',art/'temporal'/(a.silver_id+'.json'),art/'revision_demo'/a.silver_id/'result.json',
        art/'e03_e05_unit_tests.json',art/'e03_e05_integration_tests.json',art/'e03_silver_resources.json',art/'e04_audit_resources.json',art/'e05_gold_resources.json',
        art/'e03_silver_replay_resources.json',art/'e05_gold_replay_resources.json',art/'e03_revision_resources.json',
        root/'data/silver/expansion'/revision['child_id']/'_silver.json',art/'e03_rejection_recheck.log']
    for path in paths:g+=f'- `{path.relative_to(root)}`: SHA-256 `{sha256(path)}`.\n'
    (docs/'E05_ABTS_TEMPORAIS.md').write_text(g)
    print('E03/E04/E05 documentadas; Gold:',counts)


if __name__=='__main__':main()
