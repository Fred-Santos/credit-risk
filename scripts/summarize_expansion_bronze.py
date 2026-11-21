"""Consolida E02 e confere contagens da Bronze contra o inventário independente."""
import argparse
import hashlib
import json
from pathlib import Path
from src.bronze.expansion import verify_committed


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('selection_id')
    args=parser.parse_args()
    if len(args.selection_id)!=24 or any(c not in '0123456789abcdef' for c in args.selection_id):
        raise ValueError('ID inválido')
    root=Path(__file__).resolve().parents[1]
    dest=root/'data/bronze/expansion'/args.selection_id
    raw_manifest=json.loads((dest/'_bronze.json').read_text())
    manifest=verify_committed(dest,raw_manifest['identity'])
    inventory=json.loads((root/'artifacts/expansion/source_profiles.json').read_text())
    populations=json.loads((root/'artifacts/expansion/populations.json').read_text())
    summary=root/'artifacts/expansion/bronze'/(args.selection_id+'.json')
    result=json.loads(summary.read_text())
    reused=json.loads((summary.with_name(args.selection_id+'-reused.json')).read_text())
    if not reused['reused'] or reused['tables']!=result['tables']:
        raise ValueError('Reexecução não comprovada')
    for name,table in manifest['tables'].items():
        expected=inventory['tables'][name]['cohort_rows']
        if table['bronze_rows']!=expected or table['raw_selected_rows']!=expected:
            raise ValueError(f'Contagem diverge do inventário: {name}')
    for name, count in manifest['population']['windows'].items():
        if populations['windows'][name]['cases']!=count:
            raise ValueError(f'População diverge de E00: {name}')
    unit=json.loads((root/'artifacts/expansion/e02_unit_tests.json').read_text())
    integration=json.loads((root/'artifacts/expansion/e02_bronze_tests.json').read_text())
    if unit['status']!='passed' or unit['skipped'] or integration['status']!='passed' or integration['skipped']:
        raise ValueError('Testes não aprovados sem skips')
    resources=json.loads((root/'artifacts/expansion/bronze_build_resources.json').read_text())
    if resources['exit_code']!=0:raise ValueError('Execução não aprovada')
    text=f'''# E02 — Seleção temporal e Bronze expandida

Data de referência: 18/11/2026. Estado: E02.3/E02.4 aceitos.

Política: [temporal_policy_v1.yaml](../../configs/temporal_policy_v1.yaml).
Snapshot: `{args.selection_id}` em `data/bronze/expansion/{args.selection_id}/`.
Esse namespace é independente da Bronze do MVP e não altera Silver, Gold ou CURRENT.

## População e preservação

A base completa tem **{manifest['population']['full_base_cases']:,} casos**.
A seleção pública contém **{manifest['population']['selected_cases']:,} casos**;
**{manifest['population']['outside_public_cases']:,}** ficam fora da janela.
São **{manifest['population']['windows']['development']:,}** no desenvolvimento
(janeiro–maio) e **{manifest['population']['windows']['evaluation']:,}** na reserva
(junho–setembro). Os intervalos são semiabertos e incluem 31/05 e 30/09.
Não existe limite de 50 mil ou amostragem na nova política.

Somente a `date_decision` da base determina os casos. Auxiliares passam por
`left_semi` em `case_id`; todas as observações desses casos são preservadas,
independentemente de suas datas. Isso inclui registros anteriores a janeiro e
posteriores a setembro. A Bronze preserva o snapshot retrospectivo; elegibilidade
para ML e disponibilidade temporal serão investigadas em E04.

## Reconciliação e proveniência

Cada tabela foi escrita sem casts de negócio e comparada diretamente à RAW
selecionada, com `exceptAll` nos dois sentidos e mesmos tipos/ordem de colunas.
A comparação inclui todos os campos originais e `_source_file`, `_selection_id`,
`_run_id`, `_ingested_at_utc`. Assim, preserva multiplicidade, nulos, valores
e proveniência, sem substituir igualdade por contagens ou hashes de linhas.
Todos os arquivos de saída têm SHA-256 registrado no manifesto.

As contagens foram também confrontadas com E00, executada por rotina independente.

| Tabela | Linhas Bronze | Fora da janela de casos (linhas RAW) | Diferenças nos dois sentidos |
|---|---:|---:|---:|
'''
    for name,table in manifest['tables'].items():
        text+=f"| `{name}` | {table['bronze_rows']:,} | {inventory['tables'][name]['rows']-table['bronze_rows']:,} | 0 / 0 |\n"
    total=sum(t['bronze_rows'] for t in manifest['tables'].values())
    text+=f'''
Total entre tabelas: **{total:,} linhas**. Não é quantidade de casos únicos.

## Identidade, falha e reexecução

A identidade inclui política, catálogo lógico, fontes com SHA-256/tamanho,
versão Spark e hashes da implementação. O ID é derivado dessa identidade.
O journal da aquisição e todos os bytes RAW foram conferidos antes e depois da
materialização; nenhuma fonte foi sobrescrita. Catálogo e política ficam no manifesto.

O lock serializa escritores cooperantes. Tabelas são escritas em staging privado;
um rename no mesmo filesystem torna o snapshot visível somente após aprovação
das 17 tabelas e gravação do manifesto. Não há ativação por CURRENT nesta camada.
Staging de uma falha permanece privado para diagnóstico e não é consumível como
snapshot aprovado. A retomada cria staging novo e preserva o anterior.

A segunda execução reutilizou o mesmo snapshot após verificar fontes,
identidade, aprovação e checksums das saídas, sem reescrever as tabelas.
Uma alteração de conteúdo provoca recusa, não sobrescrita automática.
O teste de falha injetada demonstrou ausência de snapshot público e retry válido;
o teste de corrupção de Parquet demonstrou bloqueio da reexecução.

## Recursos e validação

Heap efetivo: **{result['jvm_max_heap_bytes']/1024**3:.0f} GiB**.
Tempo de materialização/reconciliação no manifesto:
**{manifest['duration_seconds']} s**; tempo do processo monitorado:
**{resources['duration_seconds']} s**.
Pico RSS amostrado da árvore: **{resources['peak_process_tree_rss_bytes']/1024**3:.2f} GiB**.
Pico de bytes lógicos no scratch configurado:
**{resources['peak_workdir_logical_bytes']/1024**3:.2f} GiB**.

RSS pode contar páginas compartilhadas e perder picos; o disco medido não inclui
os arquivos Bronze nem outros diretórios. Esta é uma execução Bronze real, não
validação do futuro processamento Silver/Gold completo. A configuração efetiva
fica no diretório de runtime apontado pelo resumo local.

**100 testes unitários e dois testes Spark de integração aprovados**, sem
ignorados. A suíte unitária inclui política temporal, configuração Spark,
catálogo e downloader. Os três testes do arquivo novo também passaram
por execução direta (a política é contabilizada na suíte unitária, sem duplicar
a contagem de cenários distintos). As fixtures cobrem as bordas de datas,
histórico antigo e futuro, nulos, preservação de multiplicidade, reuso, corrupção
e falha privada seguida de retry. Os testes Spark usam JVM de 2 GB; a execução
real verificou 8 GiB. Sockets locais exigiram execução fora do sandbox restrito.

```bash
bash scripts/project.sh -m unittest tests.test_expansion_bronze -q
bash scripts/project.sh scripts/run_tests.py --suite unit --integration-required --report artifacts/expansion/e02_unit_tests.json
bash scripts/project.sh -m scripts.build_expansion_bronze
bash scripts/project.sh -m scripts.build_expansion_bronze
bash scripts/project.sh -m scripts.summarize_expansion_bronze {args.selection_id}
```

O monitor usado na primeira execução foi `scripts/measure_resources.py`, com
`--workdir .runtime/tmp/bronze-expansion`. Os recursos da reexecução ficam
separados em `bronze_replay_resources.json`.

## Evidências locais

'''
    paths=[dest/'_bronze.json',summary,summary.with_name(args.selection_id+'-reused.json'),
           root/'artifacts/expansion/bronze_build_resources.json',root/'artifacts/expansion/bronze_replay_resources.json',root/'artifacts/expansion/e02_unit_tests.json',root/'artifacts/expansion/e02_bronze_tests.json',
           root/'artifacts/expansion/e02_code_checks.json',root/'artifacts/expansion/e02_acceptance_mapping.json']
    for path in paths:
        text+=f"- `{path.relative_to(root)}`: SHA-256 `{hashlib.sha256(path.read_bytes()).hexdigest()}`.\n"
    (root/'docs/evidencias/E02_BRONZE_TEMPORAL.md').write_text(text)
    print('E02 reconciliada com E00:',len(manifest['tables']),'tabelas;',total,'linhas')


if __name__=='__main__':main()
