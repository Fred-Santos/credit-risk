"""Profiling de hipóteses do notebook; nenhuma transformação é publicada."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re

from src.bronze.inputs import bind_sample, verify_input
from src.pipelines.download_home_credit import sha256
from src.quality.contracts import load_contract, check_schema
from src.utils.run_context import RunContext
from src.utils.spark import create_spark_session

NUMERIC_PROBES = [99, 999, 9999, 99999, 999999, 9999999, -1]
STRING_PROBES = ['XNA', 'Unknown', 'unknown', 'N/A', 'na', '', 'a55475b1']


def notebook_inventory(path: Path) -> dict:
    notebook = json.loads(path.read_text())
    cells, table = [], None
    for index, cell in enumerate(notebook['cells']):
        source = ''.join(cell['source'])
        match = re.search(r'^## Dataset (train_\w+)', source, re.M)
        if match:
            table = match[1]
            if table == 'train_applprev_1_0':
                table = 'train_applprev_1'
        rows = []
        in_schema = False
        for line in source.splitlines():
            if line.startswith('|') and 'dtype Bronze' in line:
                in_schema = True
                continue
            if in_schema and line.startswith('|'):
                parts = [p.strip() for p in line.strip('|').split('|')]
                if len(parts) == 4 and not all(re.fullmatch('[-: ]*', p) for p in parts):
                    rows.append(dict(zip(['column', 'bronze_type', 'proposal', 'reason'], parts)))
            elif in_schema:
                in_schema = False
        blocks = re.findall(r'```python\s*\n(.*?)(?:```|\Z)', source, re.S)
        syntax_errors = []
        for block_number, block in enumerate(blocks):
            try:
                ast.parse(block)
            except SyntaxError as error:
                syntax_errors.append({'block': block_number, 'line': error.lineno, 'message': error.msg})
        cells.append({'index': index, 'id': cell.get('id'), 'type': cell['cell_type'],
                      'table': table, 'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                      'headings': re.findall(r'^#+ .+', source, re.M), 'schema_proposals': rows,
                      'action_headings': re.findall(r'^### Ações Silver.*', source, re.M),
                      'python_block_syntax_errors': syntax_errors})
    return {'notebook_sha256': sha256(path), 'cell_numbering': 'zero_based',
            'cell_count': len(cells), 'cells': cells}


def notebook_lists(path: Path) -> dict:
    cells = json.loads(path.read_text())['cells']
    source = ''.join(cells[178]['source'])
    result = {}
    for name in ['cols_to_drop', 'int_cols', 'date_cols', 'sentinel_minus1_cols', 'm_cols']:
        match = re.search(rf'^{name}\s*=\s*(\[.*?\])', source, re.M | re.S)
        if not match:
            raise ValueError(f'Lista do notebook ausente: {name}; revisar catálogo')
        result[name] = ast.literal_eval(match[1])
    return result


def profile_candidates(frame, schema: dict, key: list, drops: list) -> dict:
    from pyspark.sql import functions as F
    result = {'rows': frame.count(), 'columns': {}}
    # Blocos pequenos evitam um único plano agregado com milhares de expressões.
    names = list(schema)
    for start in range(0, len(names), 12):
        expressions, descriptors = [], []
        def add(column, metric, expression):
            alias = f'm{len(expressions)}'
            expressions.append(expression.alias(alias))
            descriptors.append((column, metric, alias))
        for column in names[start:start + 12]:
            c, dtype = F.col(column), schema[column]
            add(column, 'nulls', F.sum(c.isNull().cast('long')))
            if dtype in ('double', 'bigint'):
                add(column, 'min', F.min(c)); add(column, 'max', F.max(c))
                add(column, 'negative', F.sum((c < 0).cast('long')))
                add(column, 'fractional', F.sum((c != F.floor(c)).cast('long')))
                add(column, 'outside_int32', F.sum(((c < -(2**31)) | (c > 2**31 - 1)).cast('long')))
                if dtype == 'double':
                    add(column, 'nan', F.sum(F.isnan(c).cast('long')))
                if column not in key and column not in ['MONTH', 'WEEK_NUM', 'target']:
                    for value in NUMERIC_PROBES:
                        add(column, f'probe_{value}', F.sum((c == value).cast('long')))
            if dtype == 'string':
                for value in STRING_PROBES:
                    add(column, f'probe_{value or "empty"}', F.sum((c == value).cast('long')))
                if column.endswith('D') or column == 'date_decision':
                    parsed = F.try_to_timestamp(c, F.lit('yyyy-MM-dd')).cast('date')
                    add(column, 'invalid_date', F.sum((c.isNotNull() & parsed.isNull()).cast('long')))
                    add(column, 'non_iso', F.sum((c.isNotNull() & ~c.rlike(r'^\d{4}-\d{2}-\d{2}$')).cast('long')))
                if column.endswith('M'):
                    for label, pattern in [('p_format', r'^P\d+_\d+_\d+$'),
                                           ('q_format', r'^Q\d+_\d+_\w+$'), ('hex_format', r'^[0-9a-f]{8}$')]:
                        add(column, label, F.sum(c.rlike(pattern).cast('long')))
            if dtype == 'boolean':
                add(column, 'false', F.sum((c == F.lit(False)).cast('long')))
                add(column, 'true', F.sum((c == F.lit(True)).cast('long')))
            if column in drops:
                add(column, 'exact_distinct_non_null', F.countDistinct(c))
        values = frame.agg(*expressions).first().asDict()
        for column, metric, alias in descriptors:
            value = values[alias]
            result['columns'].setdefault(column, {})[metric] = value if value is not None else (None if metric in ('min', 'max') else 0)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', required=True)
    args = parser.parse_args()
    ctx = RunContext.create(Path(__file__).resolve().parents[2])
    bound = bind_sample(ctx, args.sample)
    ctx = bound.ctx
    gate_path = ctx.bronze_dir / '_READY.json'
    gate_hash = sha256(gate_path)
    gate = json.loads(gate_path.read_text())
    run = json.loads((ctx.repo_root / gate['run_report']).read_text())
    if gate['status'] != 'passed' or gate['input'] != bound.descriptor or run['status'] != 'passed':
        raise ValueError('Bronze sem aceite compatível com o recorte')
    for field, location in [('quality_report_sha256', run['quality']['json']),
                            ('reconciliation_report_sha256', run['reconciliation']['json'])]:
        if gate[field] != sha256(Path(location)):
            raise ValueError('Relatório do gate alterado')
    for relative, expected in gate['output_checksums'].items():
        if sha256(ctx.bronze_dir / relative) != expected:
            raise ValueError('Bronze aprovada foi alterada')
    contract = load_contract(ctx.repo_root / 'configs/contracts/home_credit_v1.yaml')
    notebook = ctx.repo_root / 'notebooks/analise_silver.ipynb'
    inventory, lists = notebook_inventory(notebook), notebook_lists(notebook)
    report = {'run_id': ctx.run_id, 'selection_id': args.sample, 'status': 'running',
              'scope': 'approved_bronze_sample_read_only', 'gate_sha256': gate_hash,
              'accepted_bronze_run': gate['verified_by_run_id'], 'notebook_inventory': inventory,
              'static_notebook_lists': lists, 'tables': {}}
    spark = create_spark_session(ctx.repo_root, app_name='silver-rule-review')
    try:
        for name, spec in contract['tables'].items():
            frame = spark.read.parquet(str(ctx.bronze_dir / name)).select(*spec['schema'])
            check_schema(frame, spec)
            report['tables'][name] = profile_candidates(frame, spec['schema'], spec['key'], lists['cols_to_drop'])
    finally:
        spark.stop()
    verify_input(bound)
    for relative, expected in gate['output_checksums'].items():
        if sha256(ctx.bronze_dir / relative) != expected:
            raise RuntimeError('Bronze mudou durante inspeção')
    if gate_hash != sha256(gate_path) or sha256(notebook) != inventory['notebook_sha256']:
        raise RuntimeError('Gate/notebook mudou durante inspeção')
    report['status'] = 'passed'
    report['code_sha256'] = sha256(Path(__file__))
    output = ctx.repo_root / 'artifacts/silver_rule_review' / f'{ctx.run_id}.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'passed', 'report': str(output)}))


if __name__ == '__main__':
    main()
