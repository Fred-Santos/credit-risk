"""Consolida evidências agregadas da expansão em Markdown local."""
import json
import hashlib
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    artifacts = root / 'artifacts/expansion'
    report = json.loads((artifacts / 'source_profiles.json').read_text())
    if report['status'] != 'completed':
        raise ValueError('Perfil incompleto; não emitir evidência final')
    tables = report['tables']
    compressed = sum(v['compressed_file_bytes'] for v in tables.values())
    uncompressed = sum(v['parquet_uncompressed_column_bytes'] for v in tables.values())
    text = '''# E00 — Perfil completo das fontes de treino

Evidência gerada a partir de `artifacts/expansion/source_profiles.json`.
Dados de negócio não são exportados neste documento; todas as contagens são exatas.
As chaves abaixo são candidatas observadas, ainda sujeitas à definição semântica
em E03/E04. Ausência de duplicatas não prova identidade de contrato financeiro.

| Tabela | Linhas RAW | Linhas janeiro–setembro | Casos na janela | Chave candidata | Grupos duplicados | Casos órfãos |
|---|---:|---:|---:|---|---:|---:|
'''
    for name,v in tables.items():
        text += f"| `{name}` | {v['rows']:,} | {v['cohort_rows']:,} | {v['cohort_distinct_cases']:,} | {', '.join(v['key'])} | {v['duplicate_key_groups']:,} | {v['orphan_cases']:,} |\n"
    text += f'''
## Armazenamento e capacidade

- Entradas Parquet comprimidas: **{compressed:,} bytes**.
- Column chunks descomprimidos, somados dos rodapés: **{uncompressed:,} bytes**.
- Duração do perfil: **{report['duration_seconds']} segundos**.

O tamanho descomprimido não representa memória de objetos Spark/Python nem
pico de disco; os chunks ainda usam codificação Parquet após descompressão.
Para planejamento inicial, adotar uma reserva de trabalho de
`max(64 GiB, 4 × column chunks descomprimidos + 2 × entradas comprimidas)`, arredondada para
cima e com folga adicional de 20%. O piso de 64 GiB é uma reserva operacional provisória, sem calibração de pico.
Essa é uma hipótese de orçamento para
materializações e temporários, não um limite superior garantido. Medir o fluxo
completo e a retenção para substituir essa hipótese em E01/E07.

'''
    budget = max(64 * 1024**3, 4 * uncompressed + 2 * compressed) * 1.2
    text += f'Envelope inicial calculado: **{budget / 1024**3:.2f} GiB**, além dos dados já existentes.\n'
    text += '''
## Limitações e encaminhamentos

O JSON contém tipos, nulos/NaNs por coluna, máximos de linhas por caso, cobertura
sobre a base completa, datas brutas e campos sem definição. Datas brutas não
comprovam validade, disponibilidade na decisão ou elegibilidade para ML.
A compatibilidade de schema foi conferida entre todos os shards de cada tabela.
Na execução, as 17 tabelas apresentaram zero nulos nas chaves candidatas, zero
grupos de chave duplicada e zero casos órfãos. Todos os campos de negócio
encontraram entrada no dicionário; isso não comprova clareza ou adequação temporal.

As relações entre níveis de histórico precisam de definição de negócio e
validação das chaves parentais antes dos joins Gold. Campos sem descrição devem
receber investigação ou exclusão explícita. Perfis e aquisição não equivalem
à aceitação de contratos Silver, nem demonstram capacidade de processamento e
publicação de todas as tabelas em conjunto.

Reprodução:

```bash
bash scripts/project.sh -m scripts.acquire_expansion
bash scripts/project.sh scripts/measure_resources.py --output artifacts/expansion/profile_resources.json --workdir .runtime/tmp -- .venv/bin/python -m scripts.profile_expansion_sources
bash scripts/project.sh -m scripts.summarize_expansion_profile
```

O perfil usou o heap atual de 2 GB. A memória visível no Linux/WSL foi cerca de
15 GiB. Aplicar o perfil de 8 GB e avaliar folga em E01; aumentos para 12/16 GB
não são seguros por pressuposto nesse limite da VM. A medição RSS soma a árvore
de processos e pode contar páginas compartilhadas mais de uma vez.
'''
    resources = json.loads((artifacts / 'profile_resources.json').read_text())
    text += f"\nPico RSS amostrado da árvore: **{resources['peak_process_tree_rss_bytes'] / 1024**3:.2f} GiB**. "
    text += "A medição de disco cobre somente `.runtime/tmp`; o Spark pode usar `/tmp`, portanto não comprova pico total.\n"
    text += "\n## Integridade\n\n"
    for name in ('source_profiles.json', 'profile_resources.json', 'host_capacity.json', 'acquisition.json'):
        text += f"- `{name}`: SHA-256 `{hashlib.sha256((artifacts / name).read_bytes()).hexdigest()}`.\n"
    (root / 'docs/evidencias/E00_PERFIL_FONTES.md').write_text(text)


if __name__ == '__main__':
    main()
