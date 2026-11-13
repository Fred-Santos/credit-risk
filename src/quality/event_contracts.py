"""Referência v1 para eventos simulados; sem aplicar estado Silver ou merges."""
from __future__ import annotations

from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re

import yaml

from src.pipelines.download_home_credit import sha256
from src.quality.contracts import load_contract

FIELDS = {'_event_contract_version', '_source_system', '_selection_id', '_stream_id',
          '_batch_id', '_table', '_ordinal', '_source_revision', '_operation',
          '_is_simulated', '_scenario', '_payload_origin', '_event_id',
          '_delivery_id', '_payload_sha256', '_payload'}


class EventConflictError(ValueError):
    pass


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))


def digest(value) -> str:
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


def load_event_contract(path: Path, snapshot_path: Path) -> tuple[dict, dict]:
    contract = yaml.safe_load(path.read_text(encoding='utf-8'))
    if (not isinstance(contract, dict) or type(contract.get('version')) is not int
            or contract['version'] != 1 or contract.get('scope') != 'simulated_event_batches'):
        raise ValueError('Contrato de eventos v1 inválido')
    expected = {
        'source_system': 'home_credit_simulator_v1', 'operations': ['upsert'],
        'event_identity': 'event_v1_context_table_business_key_revision',
        'delivery_identity': 'delivery_v1_context_batch_table_ordinal',
        'payload_encoding': 'typed_python_json_v1',
    }
    if any(contract.get(key) != value for key, value in expected.items()):
        raise ValueError('Algoritmo ou operação de eventos não suportados')
    if set(contract.get('fields', {})) != FIELDS:
        raise ValueError('Campos de envelope diferentes da versão 1')
    if contract.get('snapshot_contract_sha256') != sha256(snapshot_path):
        raise ValueError('Contrato de snapshot incompatível com os eventos')
    if contract.get('scenarios') != ['baseline_replay', 'correction_simulation', 'late_arrival', 'duplicate_delivery']:
        raise ValueError('Cenários de eventos não suportados')
    if contract.get('payload_origins') != ['home_credit_snapshot', 'home_credit_with_simulated_change', 'synthetic_fixture']:
        raise ValueError('Origens de payload não suportadas')
    policies = contract.get('policies', {})
    expected_policies = {
        'payload_mode': 'full_row', 'all_arrivals_simulated': True,
        'duplicate_event_same_payload': 'preserve_deliveries',
        'same_revision_different_payload': 'reject_batch',
        'older_revision': 'accept_history_never_overwrite_newer_state',
        'batch_content_change': 'reject', 'delete_by_absence': 'forbidden',
    }
    if policies != expected_policies:
        raise ValueError('Políticas diferem do protocolo implementado')
    return contract, load_contract(snapshot_path)


def identifier(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,79}', value):
        raise ValueError(f'{label} deve usar letras minúsculas, números e underscore')


def normalize_payload(table: str, payload: dict, snapshot: dict) -> dict:
    if table not in snapshot['tables']:
        raise ValueError('Tabela fora do contrato de snapshot')
    spec = snapshot['tables'][table]
    if not isinstance(payload, dict) or set(payload) != set(spec['schema']):
        raise ValueError(f'Payload deve conter exatamente o schema de {table}')
    result = {}
    for column, dtype in spec['schema'].items():
        value = payload[column]
        if value is None:
            if column in spec['required_non_null']:
                raise ValueError(f'Campo obrigatório nulo: {column}')
        elif dtype == 'bigint':
            if type(value) is not int or not -(2**63) <= value < 2**63:
                raise ValueError(f'Inteiro bigint inválido: {column}')
        elif dtype == 'double':
            if type(value) not in (int, float):
                raise ValueError(f'Número double inválido: {column}')
            try:
                value = float(value)
            except OverflowError as error:
                raise ValueError(f'Número double inválido: {column}') from error
            if not math.isfinite(value):
                raise ValueError(f'NaN/Infinity não suportado pelo envelope JSON v1: {column}')
            if value == 0:
                value = 0.0  # Zero com sinal não distingue versões de negócio aqui.
        elif dtype == 'boolean':
            if type(value) is not bool:
                raise ValueError(f'Boolean inválido: {column}')
        elif dtype == 'string':
            if not isinstance(value, str):
                raise ValueError(f'String inválida: {column}')
        else:
            raise ValueError(f'Tipo de payload não suportado: {dtype}')
        result[column] = value
    if table == 'train_base':
        text = result['date_decision']
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', text):
            raise ValueError('Data de decisão deve ser ISO yyyy-MM-dd')
        decision = date.fromisoformat(text)
        if result['MONTH'] != decision.year * 100 + decision.month:
            raise ValueError('MONTH diverge da data de decisão')
        if result['WEEK_NUM'] < 0 or result['target'] not in (0, 1):
            raise ValueError('Semana ou target inválido')
    return result


def make_event(contract: dict, snapshot: dict, *, selection_id: str, stream_id: str,
               batch_id: str, table: str, ordinal: int, source_revision: int,
               payload: dict, scenario: str, payload_origin: str) -> dict:
    if not isinstance(selection_id, str) or not re.fullmatch(r'[0-9a-f]{24}', selection_id):
        raise ValueError('selection_id inválido')
    identifier(stream_id, 'stream_id')
    identifier(batch_id, 'batch_id')
    if type(ordinal) is not int or not 0 <= ordinal < 2**63:
        raise ValueError('ordinal deve ser inteiro não negativo')
    if type(source_revision) is not int or not 1 <= source_revision < 2**63:
        raise ValueError('source_revision deve ser inteiro positivo')
    if scenario not in contract['scenarios'] or payload_origin not in contract['payload_origins']:
        raise ValueError('Cenário/origem não permitido')
    if scenario == 'baseline_replay' and source_revision != 1:
        raise ValueError('Replay inicial usa revisão 1')
    if scenario == 'correction_simulation' and (source_revision < 2 or payload_origin != 'home_credit_with_simulated_change'):
        raise ValueError('Correção exige revisão >=2 e origem explicitamente simulada')
    normalized = normalize_payload(table, payload, snapshot)
    namespace = [contract['source_system'], selection_id, stream_id]
    key = [[name, normalized[name]] for name in snapshot['tables'][table]['key']]
    event_id = digest(['event_v1', *namespace, table, key, source_revision])
    return {
        '_event_contract_version': 1, '_source_system': contract['source_system'],
        '_selection_id': selection_id, '_stream_id': stream_id, '_batch_id': batch_id,
        '_table': table, '_ordinal': ordinal, '_source_revision': source_revision,
        '_operation': 'upsert', '_is_simulated': True, '_scenario': scenario,
        '_payload_origin': payload_origin, '_event_id': event_id,
        '_delivery_id': digest(['delivery_v1', *namespace, batch_id, table, ordinal]),
        '_payload_sha256': digest({'operation': 'upsert', 'payload': normalized}),
        '_payload': normalized,
    }


def validate_event(event: dict, contract: dict, snapshot: dict) -> dict:
    if not isinstance(event, dict) or set(event) != FIELDS:
        raise ValueError('Envelope com campos ausentes ou extras')
    if (type(event['_event_contract_version']) is not int or event['_event_contract_version'] != 1
            or event['_source_system'] != contract['source_system']
            or event['_operation'] != 'upsert' or event['_is_simulated'] is not True):
        raise ValueError('Versão, operação ou marcação de simulação inválida')
    expected = make_event(contract, snapshot, selection_id=event['_selection_id'],
                          stream_id=event['_stream_id'], batch_id=event['_batch_id'],
                          table=event['_table'], ordinal=event['_ordinal'],
                          source_revision=event['_source_revision'], payload=event['_payload'],
                          scenario=event['_scenario'], payload_origin=event['_payload_origin'])
    if event != expected:
        raise ValueError('Identidade/hash de evento ou entrega divergente do conteúdo')
    return expected


def check_revision_history(events: list[dict]) -> dict:
    """Recebe envelopes já validados; examina todas as revisões, inclusive antigas."""
    versions = {}
    for event in events:
        prior = versions.get(event['_event_id'])
        if prior is not None and prior != event['_payload_sha256']:
            raise EventConflictError(f'Payloads conflitantes para o mesmo evento/revisão: {event["_event_id"]}')
        versions[event['_event_id']] = event['_payload_sha256']
    return versions


def revision_action(current: dict | None, incoming: dict, snapshot: dict) -> str:
    """Classificador de referência; o chamador valida histórico antes de usá-lo."""
    if current is None:
        return 'insert'
    context = ('_source_system', '_selection_id', '_stream_id', '_table')
    if any(current[key] != incoming[key] for key in context):
        raise ValueError('Comparação entre contextos diferentes')
    columns = snapshot['tables'][incoming['_table']]['key']
    if any(current['_payload'][key] != incoming['_payload'][key] for key in columns):
        raise ValueError('Comparação entre chaves de negócio diferentes')
    a, b = current['_source_revision'], incoming['_source_revision']
    if b == a:
        if current['_payload_sha256'] != incoming['_payload_sha256']:
            raise EventConflictError('Mesma revisão com conteúdo diferente')
        return 'ignore_same_revision'
    return 'update' if b > a else 'ignore_older_revision'
