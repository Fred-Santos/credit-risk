"""Traduz o contrato congelado de snapshot em checks Bronze, sem duplicar schemas."""
from pathlib import Path

from src.quality.contracts import load_contract

METADATA = {'_run_id': 'string', '_ingest_date': 'date', '_source_file': 'string',
            'ingest_batch': 'string'}  # Coluna descoberta nas pastas Hive-style da Bronze.


def contract_rules(repo_root: Path, relative: str):
    path = (repo_root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(repo_root.resolve()):
        raise ValueError('Contrato fora do repositório')
    contract = load_contract(path)
    generated = []
    for name, spec in contract['tables'].items():
        if set(spec['schema']) & set(METADATA):
            raise ValueError('Schema de negócio colide com metadados Bronze')
        checks = [
            {'type': 'exact_schema', 'types': {**spec['schema'], **METADATA}},
            {'type': 'minimum_rows', 'value': spec['minimum_rows']},
            {'type': 'unique', 'columns': spec['key']},
            {'type': 'not_null', 'columns': spec['required_non_null'] + list(METADATA)},
        ]
        if spec.get('reference'):
            ref = spec['reference']
            checks.append({'type': 'foreign_key', 'columns': ref['columns'], 'reference': ref['table']})
            if ref['full_coverage']:
                checks.append({'type': 'parent_coverage', 'columns': ref['columns'], 'reference': ref['table']})
        if name == 'train_base':
            checks.extend([{'type': 'base_calendar'},
                           {'type': 'allowed_values', 'column': 'target', 'values': [0, 1]}])
        generated.append({'pattern': name, 'checks': [{**c, 'severity': 'fail'} for c in checks]})
    return contract, generated
