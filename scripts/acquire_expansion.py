"""Aquisição do catálogo de expansão com journal e preservação da RAW."""
import json
import re
from pathlib import Path, PurePosixPath
import yaml
from src.pipelines.download_home_credit import COMPETITION, download_selected
from src.utils.paths import load_paths


def load_files(root):
    catalog = yaml.safe_load((root / 'configs/home_credit_expansion_catalog.yaml').read_text())
    if catalog['competition'] != COMPETITION or catalog['scope'] != 'all_train_parquet':
        raise ValueError('Identidade do catálogo incompatível')
    if catalog.get('version') != 1 or catalog.get('dictionary') != 'feature_definitions.csv':
        raise ValueError('Versão ou dicionário incompatível')
    if not catalog.get('tables'):
        raise ValueError('Catálogo sem tabelas')
    files = [catalog['dictionary']]
    for logical, shards in catalog['tables'].items():
        if not shards:
            raise ValueError('Tabela sem arquivos')
        for item in shards:
            path = PurePosixPath(item['name'])
            if '..' in path.parts or not item['name'].startswith('parquet_files/train/') or path.suffix != '.parquet':
                raise ValueError('Arquivo fora do escopo de treino Parquet')
            if re.sub(r'(_[012])_\d+$', r'\1', path.stem) != logical:
                raise ValueError('Shard associado à tabela errada')
            if type(item['bytes']) is not int or item['bytes'] <= 0:
                raise ValueError('Tamanho remoto inválido')
            files.append(item['name'])
    if len(set(files)) != len(files):
        raise ValueError('Arquivos repetidos no catálogo')
    return catalog, files


def main():
    root = Path(__file__).resolve().parents[1]
    catalog, files = load_files(root)
    raw = load_paths(root)['raw_dir']
    records = []
    # Cada chamada mantém o lock e o protocolo prepared/complete do downloader.
    for remote in files:
        records.extend(download_selected(raw, files=[remote]))
        print(f'Verificado {len(records)}/{len(files)}: {remote}', flush=True)
    expected = {f['name']: f['bytes'] for shards in catalog['tables'].values() for f in shards}
    if any(r['bytes'] != expected[r['remote']] for r in records if r['remote'] in expected):
        raise ValueError('Tamanho adquirido diverge do catálogo remoto; arquivos preservados')
    out = root / 'artifacts/expansion/acquisition.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'files': records, 'bytes': sum(r['bytes'] for r in records)}, indent=2)+'\n')


if __name__ == '__main__':
    main()
