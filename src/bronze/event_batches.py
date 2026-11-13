"""Landing imutável de pequenos lotes de referência; não atualiza tabelas Silver.

JSONL e leitura integral do histórico são deliberados neste laboratório de contrato.
O gerador distribuído e o transporte Parquet pertencem à etapa F04.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile

from src.bronze.build_bronze import _ingestion_lock
from src.pipelines.download_home_credit import sha256
from src.quality.event_contracts import (canonical_json, check_revision_history,
                                         digest, identifier, validate_event)


def _packet(events, contract, snapshot, binding, stream_id, batch_id):
    normalized = [validate_event(e, contract, snapshot) for e in events]
    if not normalized:
        raise ValueError('Lote vazio não representa uma entrega')
    deliveries = set()
    for event in normalized:
        if (event['_selection_id'] != binding['selection_id']
                or event['_stream_id'] != stream_id or event['_batch_id'] != batch_id):
            raise ValueError('Evento pertence a outro contexto/lote')
        if event['_delivery_id'] in deliveries:
            raise ValueError('Posição de entrega repetida no lote')
        deliveries.add(event['_delivery_id'])
    return sorted(normalized, key=lambda e: (e['_table'], e['_ordinal']))


def read_history(root: Path, contract: dict, snapshot: dict, binding: dict) -> list[dict]:
    """Verifica recibos e conteúdo antes de admitir novos eventos."""
    history, receipts = [], []
    for directory in sorted(root.iterdir()):
        if directory.name.startswith('.') or directory.name == '_stream.json':
            continue
        if not directory.is_dir():
            raise ValueError('Arquivo inesperado no stream')
        identifier(directory.name, 'batch_id')
        manifest = json.loads((directory / '_batch.json').read_text())
        path = directory / 'events.jsonl'
        if sha256(path) != manifest['events_sha256']:
            raise ValueError('Conteúdo de lote publicado foi alterado')
        events = [json.loads(line) for line in path.read_text().splitlines()]
        events = _packet(events, contract, snapshot, binding, root.name, directory.name)
        if (manifest['binding'] != binding or manifest['batch_id'] != directory.name
                or manifest['stream_id'] != root.name or manifest['event_count'] != len(events)
                or manifest['packet_sha256'] != digest(events)):
            raise ValueError('Manifesto de lote incompatível com conteúdo/contexto')
        receipt = manifest['receipt_index']
        if type(receipt) is not int or receipt < 1:
            raise ValueError('Índice de recebimento inválido')
        receipts.append(receipt)
        history.extend(events)
    if sorted(receipts) != list(range(1, len(receipts) + 1)):
        raise ValueError('Sequência de recebimentos inválida')
    check_revision_history(history)
    return history


def publish_batch(root: Path, *, binding: dict, stream_id: str, batch_id: str,
                  events: list[dict], contract: dict, snapshot: dict,
                  run_id: str, started_at_utc: str) -> dict:
    """Publica em staging + rename no mesmo filesystem, sob lock de stream.

    binding deve ser produzido a partir de um recorte verificado pelo chamador.
    run_id/horário auditam a primeira publicação; não definem revisão de negócio.
    """
    identifier(stream_id, 'stream_id')
    identifier(batch_id, 'batch_id')
    if root.name != stream_id or root.parent.name != binding['selection_id']:
        raise ValueError('Namespace do stream divergente do vínculo')
    packet = _packet(events, contract, snapshot, binding, stream_id, batch_id)
    packet_hash = digest(packet)
    root.mkdir(parents=True, exist_ok=True)
    with _ingestion_lock(root, '.stream.lock'):
        stream = root / '_stream.json'
        if stream.exists():
            if json.loads(stream.read_text()) != binding:
                raise ValueError('Stream já vinculado a outro contrato/recorte')
        else:
            if any(p.is_dir() and not p.name.startswith('.') for p in root.iterdir()):
                raise ValueError('Stream com lotes sem vínculo')
            temporary = root / '._stream.tmp'
            temporary.write_text(canonical_json(binding) + '\n', encoding='utf-8')
            temporary.replace(stream)
        history = read_history(root, contract, snapshot, binding)
        check_revision_history(history + packet)
        target = root / batch_id
        if target.exists():
            manifest = json.loads((target / '_batch.json').read_text())
            if manifest['packet_sha256'] != packet_hash:
                raise ValueError('batch_id existente com conteúdo diferente')
            return {**manifest, 'reused': True}
        stage = Path(tempfile.mkdtemp(prefix='.stage_', dir=root))
        try:
            path = stage / 'events.jsonl'
            path.write_text(''.join(canonical_json(e) + '\n' for e in packet), encoding='utf-8')
            manifest = {
                'version': 1, 'binding': binding, 'stream_id': stream_id, 'batch_id': batch_id,
                'receipt_index': len({e['_batch_id'] for e in history}) + 1,
                'event_count': len(packet), 'packet_sha256': packet_hash,
                'events_sha256': sha256(path), 'first_run_id': run_id,
                'first_received_at_utc': started_at_utc,
            }
            (stage / '_batch.json').write_text(canonical_json(manifest) + '\n', encoding='utf-8')
            stage.rename(target)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
        return {**manifest, 'reused': False}
