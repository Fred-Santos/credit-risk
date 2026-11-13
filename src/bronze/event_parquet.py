"""Transporte distribuído de envelopes v1, com payload tipado e proveniência.

Cada linha Parquet contém o payload completo, os quatro metadados Bronze e
os campos escalares do envelope v1. Os hashes usam make_event/validate_event,
inclusive nos executores: não substituímos a codificação por Spark to_json.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import reduce
import json
from pathlib import Path
import shutil
import tempfile

from src.bronze.build_bronze import _ingestion_lock
from src.pipelines.download_home_credit import sha256
from src.quality.bronze_contract import METADATA
from src.quality.contracts import check_schema
from src.quality.event_contracts import EventConflictError, digest, identifier, make_event, validate_event
from src.quality.reconcile_bronze import compare_rows

ENVELOPE = {
    '_event_contract_version': 'int', '_source_system': 'string', '_selection_id': 'string',
    '_stream_id': 'string', '_batch_id': 'string', '_table': 'string', '_ordinal': 'bigint',
    '_source_revision': 'bigint', '_operation': 'string', '_is_simulated': 'boolean',
    '_scenario': 'string', '_payload_origin': 'string', '_event_id': 'string',
    '_delivery_id': 'string', '_payload_sha256': 'string',
}
FORMAT = 'typed_parquet_with_event_v1_and_bronze_metadata'


def transport_schema(snapshot: dict, table: str):
    from pyspark.sql.types import StructType, StructField, _parse_datatype_string
    types = {**snapshot['tables'][table]['schema'], **METADATA, **ENVELOPE}
    if len(types) != len(snapshot['tables'][table]['schema']) + len(METADATA) + len(ENVELOPE):
        raise ValueError('Colisão de campos no transporte de eventos')
    return StructType([StructField(n, _parse_datatype_string(t), True) for n, t in types.items()])


def encode_events(frame, contract: dict, snapshot: dict, *, selection_id: str,
                  stream_id: str, batch_id: str, table: str, revision: int = 1,
                  scenario: str = 'baseline_replay', origin: str = 'home_credit_snapshot'):
    """Entrada contém payload, metadados Bronze e _ordinal determinístico."""
    schema = transport_schema(snapshot, table)
    business = list(snapshot['tables'][table]['schema'])
    columns = schema.fieldNames()

    def encode(partition):
        for row in partition:
            values = row.asDict()
            event = make_event(contract, snapshot, selection_id=selection_id, stream_id=stream_id,
                batch_id=batch_id, table=table, ordinal=values['_ordinal'], source_revision=revision,
                payload={c: values[c] for c in business}, scenario=scenario, payload_origin=origin)
            result = {**event['_payload'], **{c: values[c] for c in METADATA},
                      **{c: event[c] for c in ENVELOPE}}
            yield tuple(result[c] for c in columns)

    return frame.sparkSession.createDataFrame(frame.rdd.mapPartitions(encode), schema)


def validate_transport(frame, contract: dict, snapshot: dict, *, selection_id: str,
                       stream_id: str, batch_id: str, table: str) -> int:
    schema = transport_schema(snapshot, table)
    check_schema(frame, {'schema': {f.name: f.dataType.simpleString() for f in schema.fields}})
    business = list(snapshot['tables'][table]['schema'])

    def validate(partition):
        count = 0
        for row in partition:
            values = row.asDict()
            if (values['_selection_id'] != selection_id or values['_stream_id'] != stream_id
                    or values['_batch_id'] != batch_id or values['_table'] != table):
                raise ValueError('Envelope fora do contexto do lote')
            event = {c: values[c] for c in ENVELOPE}
            event['_payload'] = {c: values[c] for c in business}
            validate_event(event, contract, snapshot)
            if (any(values[c] is None for c in METADATA)
                    or any(not values[c].strip() for c in ('_run_id', '_source_file', 'ingest_batch'))):
                raise ValueError('Proveniência Bronze ausente ou vazia')
            count += 1
        yield count

    count = int(frame.rdd.mapPartitions(validate).sum())
    if frame.groupBy('_ordinal').count().filter('count > 1').limit(1).count():
        raise ValueError('Posição de entrega repetida no lote/tabela')
    return count


def revision_index(frame):
    from pyspark.sql import functions as F
    provenance = F.sha2(F.to_json(F.struct(*[F.col(c) for c in METADATA]),
                                {'ignoreNullFields': 'false'}), 256)
    return frame.select('_event_id', '_payload_sha256', provenance.alias('_provenance_sha256'))


def check_conflicts(indices: list):
    """Examinar todas as revisões aceitas, inclusive antigas, sem collect de payloads."""
    from pyspark.sql import functions as F
    if not indices:
        return
    index = reduce(lambda a, b: a.unionByName(b), indices)
    conflicting = (index.groupBy('_event_id')
        .agg(F.countDistinct(F.struct('_payload_sha256', '_provenance_sha256')).alias('contents'))
        .filter('contents > 1').limit(1).count())
    if conflicting:
        raise EventConflictError('Mesma chave/revisão com payload ou proveniência conflitante')


def parquet_checksums(root: Path) -> dict:
    result = {}
    for path in sorted(root.rglob('*.parquet')):
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Arquivo de evento fora do namespace')
        result[path.relative_to(root).as_posix()] = sha256(path)
    return result


def read_packets(root: Path, spark, snapshot: dict, binding: dict) -> list[tuple[dict, dict]]:
    if not root.exists():
        return []
    if json.loads((root / '_stream.json').read_text()) != binding:
        raise ValueError('Stream vinculado a outra entrada/implementação')
    result = []
    for path in sorted(root.iterdir()):
        if path.name.startswith('.') or path.name == '_stream.json':
            continue
        if not path.is_dir():
            raise ValueError('Arquivo inesperado no stream Parquet')
        identifier(path.name, 'batch_id')
        manifest = json.loads((path / '_batch.json').read_text())
        if (manifest.get('format') != FORMAT or manifest.get('binding') != binding
                or manifest.get('batch_id') != path.name or manifest.get('stream_id') != root.name
                or manifest.get('output_checksums') != parquet_checksums(path)
                or set(manifest['counts']) != set(snapshot['tables'])
                or {p.name for p in path.iterdir() if p.is_dir()} != set(snapshot['tables'])):
            raise ValueError('Pacote Parquet ausente, alterado ou incompatível')
        if (type(manifest.get('receipt_index')) is not int or manifest['receipt_index'] < 1
                or any(type(c) is not int or c < 0 for c in manifest['counts'].values())
                or not sum(manifest['counts'].values()) or not manifest['output_checksums']):
            raise ValueError('Contagens/recibo de lote Parquet inválidos')
        signature = {k: manifest[k] for k in ('binding', 'batch_id', 'counts', 'output_checksums')}
        if digest(signature) != manifest['packet_sha256']:
            raise ValueError('Identidade do pacote Parquet divergente')
        frames = {}
        for name in snapshot['tables']:
            frame = spark.read.parquet(str(path / name))
            schema = transport_schema(snapshot, name)
            check_schema(frame, {'schema': {f.name: f.dataType.simpleString() for f in schema.fields}})
            if frame.count() != manifest['counts'][name]:
                raise ValueError('Contagem Parquet divergente do manifesto')
            frames[name] = frame
        result.append((manifest, frames))
    if sorted(p[0]['receipt_index'] for p in result) != list(range(1, len(result) + 1)):
        raise ValueError('Sequência de recibos Parquet inválida')
    return sorted(result, key=lambda p: p[0]['receipt_index'])


def publish_packet(root: Path, spark, *, frames: dict, contract: dict, snapshot: dict,
                   binding: dict, batch_id: str, run_id: str) -> dict:
    """Valida distribuído, detecta conflitos históricos e publica sem overwrite."""
    from pyspark import StorageLevel
    identifier(root.name, 'stream_id')
    identifier(batch_id, 'batch_id')
    if root.parent.name != binding['selection_id'] or set(frames) != set(snapshot['tables']):
        raise ValueError('Namespace/conjunto de tabelas de eventos inválido')
    root.mkdir(parents=True, exist_ok=True)
    with _ingestion_lock(root, '.parquet_stream.lock'):
        header = root / '_stream.json'
        if not header.exists():
            if any(p.is_dir() and not p.name.startswith('.') for p in root.iterdir()):
                raise ValueError('Stream com pacotes sem vínculo')
            temporary_header = root / '._stream.tmp'
            temporary_header.write_text(json.dumps(binding, indent=2) + '\n')
            temporary_header.replace(header)
        packets = read_packets(root, spark, snapshot, binding)
        cached = {n: f.persist(StorageLevel.MEMORY_AND_DISK) for n, f in frames.items()}
        stage = None
        try:
            counts = {name: validate_transport(frame, contract, snapshot,
                selection_id=binding['selection_id'], stream_id=root.name, batch_id=batch_id, table=name)
                for name, frame in cached.items()}
            if sum(counts.values()) == 0:
                raise ValueError('Lote inteiro vazio não representa uma entrega')
            indices = [revision_index(f) for _, group in packets for f in group.values()]
            check_conflicts(indices + [revision_index(f) for f in cached.values()])
            target = root / batch_id
            if target.exists():
                manifest, stored = next(p for p in packets if p[0]['batch_id'] == batch_id)
                if counts != manifest['counts'] or any(not compare_rows(cached[n], stored[n], cached[n].columns)['success']
                                                     for n in cached):
                    raise ValueError('batch_id existente com conteúdo diferente')
                return {**manifest, 'reused': True}
            stage = Path(tempfile.mkdtemp(prefix='.packet_stage_', dir=root))
            for name, frame in cached.items():
                frame.write.mode('errorifexists').parquet(str(stage / name))
                stored = spark.read.parquet(str(stage / name))
                if not compare_rows(frame, stored, frame.columns)['success']:
                    raise ValueError('Leitura Parquet difere do envelope produzido')
            signature = {'binding': binding, 'batch_id': batch_id, 'counts': counts,
                         'output_checksums': parquet_checksums(stage)}
            manifest = {**signature, 'format': FORMAT, 'stream_id': root.name,
                        'packet_sha256': digest(signature), 'receipt_index': len(packets) + 1,
                        'first_run_id': run_id, 'first_received_at_utc': datetime.now(timezone.utc).isoformat(),
                        'all_arrivals_simulated': True}
            (stage / '_batch.json').write_text(json.dumps(manifest, indent=2) + '\n')
            stage.rename(target)
            return {**manifest, 'reused': False}
        finally:
            for frame in cached.values():
                frame.unpersist()
            if stage is not None and stage.exists():
                shutil.rmtree(stage)
