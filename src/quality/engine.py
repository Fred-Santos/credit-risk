"""Regras comuns às camadas RAW e Bronze."""
from __future__ import annotations

import fnmatch
import json
from pathlib import Path

import yaml


CHECKS = {"non_empty", "nonempty", "require_columns", "not_null", "unique",
          "column_types", "allowed_values", "foreign_key", "exact_schema",
          "minimum_rows", "parent_coverage", "base_calendar"}


def load_rules(path: Path) -> dict:
    rules = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if (not isinstance(rules, dict) or not isinstance(rules.get("tables"), list)
            or set(rules) - {'version', 'defaults', 'tables', 'required_datasets', 'snapshot_contract'}):
        raise ValueError(f"Configuração de qualidade inválida: {path}")
    if not isinstance(rules.get('defaults', {}), dict):
        raise ValueError('defaults deve ser um objeto')
    if set(rules.get('defaults', {})) - {'action_on_fail'}:
        raise ValueError('Opção desconhecida em defaults')
    if 'version' in rules and (type(rules['version']) is not int or rules['version'] != 1):
        raise ValueError('Versão de qualidade não suportada')
    required = rules.get('required_datasets', [])
    if not isinstance(required, list) or any(not isinstance(n, str) or not n for n in required):
        raise ValueError('required_datasets deve ser uma lista de nomes')
    if 'snapshot_contract' in rules and not isinstance(rules['snapshot_contract'], str):
        raise ValueError('snapshot_contract deve ser caminho relativo')
    default = rules.get("defaults", {}).get("action_on_fail", "fail")
    if default not in {"fail", "warn"}:
        raise ValueError(f"Severidade padrão inválida: {default}")
    for table in rules["tables"]:
        if not isinstance(table, dict) or set(table) - {'pattern', 'patterns', 'checks'}:
            raise ValueError('Regra de tabela inválida')
        patterns = table.get('patterns', [table.get('pattern')])
        if (not isinstance(patterns, list) or not patterns
                or any(not isinstance(p, str) or not p for p in patterns)
                or ('pattern' in table and 'patterns' in table)):
            raise ValueError('Padrões de tabela inválidos')
        if not isinstance(table.get('checks'), list) or not table['checks']:
            raise ValueError('Tabela deve declarar checks não vazios')
        for check in table['checks']:
            if not isinstance(check, dict):
                raise ValueError('Check deve ser um objeto')
            if check.get("type") not in CHECKS:
                raise ValueError(f"Check desconhecido: {check.get('type')}")
            if check.get("severity", default) not in {"fail", "warn"}:
                raise ValueError("Severidade deve ser fail ou warn")
            kind = check['type']
            params = ({'columns'} if kind in {'require_columns', 'not_null', 'unique'} else
                      {'types'} if kind in {'column_types', 'exact_schema'} else
                      {'column', 'values'} if kind == 'allowed_values' else
                      {'columns', 'reference'} if kind in {'foreign_key', 'parent_coverage'} else
                      {'value'} if kind == 'minimum_rows' else set())
            if set(check) - ({'type', 'severity'} | params) or not params <= set(check):
                raise ValueError(f'Parâmetros inválidos para {kind}')
            if 'columns' in params:
                cols = check['columns']
                if (not isinstance(cols, list) or not cols
                        or any(not isinstance(c, str) or not c for c in cols) or len(cols) != len(set(cols))):
                    raise ValueError('columns deve conter nomes únicos')
            if 'types' in params:
                types = check['types']
                if (not isinstance(types, dict) or not types
                        or any(not isinstance(c, str) or not c or not isinstance(t, str) or not t
                               for c, t in types.items())):
                    raise ValueError('types deve mapear nomes para tipos')
            if 'reference' in params:
                ref = check['reference']
                if not isinstance(ref, str) or not ref or Path(ref).is_absolute() or '..' in Path(ref).parts:
                    raise ValueError('Referência deve permanecer dentro da camada')
            if kind == 'minimum_rows' and (type(check['value']) is not int or check['value'] < 0):
                raise ValueError('minimum_rows exige inteiro não negativo')
            if kind == 'allowed_values' and (not isinstance(check['column'], str)
                    or not check['column'] or not isinstance(check['values'], list) or not check['values']):
                raise ValueError('allowed_values exige column e values não vazios')
    return rules


def match_rules(rules: dict, name: str) -> list:
    return [check for table in rules["tables"]
            if any(fnmatch.fnmatchcase(name.replace("\\", "/"), pattern)
                   for pattern in table.get("patterns", [table.get("pattern", "")]))
            for check in table.get("checks", [])]


def evaluate(df, check: dict, spark, root: Path) -> dict:
    kind = check["type"]
    if kind == 'minimum_rows':
        return {'success': df.limit(check['value']).count() >= check['value']}
    if kind == 'exact_schema':
        actual, expected = dict(df.dtypes), check['types']
        return {'success': actual == expected, 'missing_columns': sorted(set(expected) - set(actual)),
                'extra_columns': sorted(set(actual) - set(expected)),
                'type_mismatches': {c: {'expected': expected[c], 'actual': actual[c]}
                                    for c in set(actual) & set(expected) if actual[c] != expected[c]}}
    if kind == 'base_calendar':
        from pyspark.sql import functions as F
        parsed = F.try_to_timestamp('date_decision', F.lit('yyyy-MM-dd')).cast('date')
        valid = (F.col('date_decision').rlike(r'^\d{4}-\d{2}-\d{2}$') & parsed.isNotNull()
                 & (F.col('MONTH') == F.date_format(parsed, 'yyyyMM').cast('long'))
                 & (F.col('WEEK_NUM') >= 0))
        return {'success': df.filter(~F.coalesce(valid, F.lit(False))).limit(1).count() == 0}
    if kind in {"non_empty", "nonempty"}:
        return {"success": df.limit(1).count() > 0}
    columns = check.get("columns", [])
    if kind == "column_types":
        columns = list(check["types"])
    if kind == "allowed_values":
        columns = [check["column"]]
    missing = [column for column in columns if column not in df.columns]
    if missing:
        return {"success": False, "missing_columns": missing}
    if kind == "require_columns":
        return {"success": True}
    if kind == "column_types":
        actual = dict(df.dtypes)
        mismatches = {c: {"expected": expected, "actual": actual[c]}
                      for c, expected in check["types"].items() if actual[c] != expected}
        return {"success": not mismatches, "type_mismatches": mismatches}
    if kind == "unique":
        if not columns:
            raise ValueError("unique exige columns")
        duplicate = df.groupBy(*columns).count().filter("count > 1").limit(1).count() > 0
        return {"success": not duplicate}
    from pyspark.sql import functions as F
    if kind == "not_null":
        if not columns:
            raise ValueError("not_null exige columns")
        from functools import reduce
        condition = reduce(lambda a, b: a | b, [F.col(c).isNull() for c in columns])
        return {"success": df.filter(condition).limit(1).count() == 0}
    if kind == "allowed_values":
        column = F.col(check["column"])
        invalid = column.isNull() | ~column.isin(check["values"])
        return {"success": df.filter(invalid).limit(1).count() == 0}
    if kind in {"foreign_key", "parent_coverage"}:
        if not columns:
            raise ValueError("foreign_key exige columns")
        reference = (root / check["reference"]).resolve()
        if not reference.is_relative_to(root.resolve()):
            raise ValueError("Referência fora da camada")
        if not reference.exists():
            return {"success": False, "error": "missing_reference"}
        parent = spark.read.parquet(str(reference)).select(*columns).distinct()
        child = df.select(*columns).distinct()
        orphans = (child.join(parent, on=columns, how="left_anti") if kind == 'foreign_key'
                   else parent.join(child, on=columns, how='left_anti'))
        return {"success": orphans.limit(1).count() == 0}
    raise ValueError(f"Check desconhecido: {kind}")


def run_checks(ctx, spark, *, layer: str):
    if layer not in {'raw', 'bronze'}:
        raise ValueError('Camada de qualidade desconhecida')
    root = ctx.raw_dir if layer == "raw" else ctx.bronze_dir
    config = "quality_rules.yaml" if layer == "raw" else "quality_rules_bronze.yaml"
    rules = load_rules(ctx.repo_root / "configs" / config)
    contract = None
    contract_hash = None
    if 'snapshot_contract' in rules:
        if layer != 'bronze':
            raise ValueError('snapshot_contract é exclusivo da Bronze de snapshot')
        from src.quality.bronze_contract import contract_rules
        from src.pipelines.download_home_credit import sha256
        contract_path = ctx.repo_root / rules['snapshot_contract']
        contract_hash = sha256(contract_path)
        contract, generated = contract_rules(ctx.repo_root, rules['snapshot_contract'])
        rules['tables'].extend(generated)
    default = rules.get("defaults", {}).get("action_on_fail", "fail")
    if layer == "raw":
        tables = [(p.relative_to(root).as_posix(), p) for p in sorted(root.rglob("*"))
                  if p.is_file() and p.suffix.lower() in {".parquet", ".csv"}]
    else:
        # Lê o dataset completo: unicidade deve abranger todos os lotes e arquivos.
        tables = [(p.name, p) for p in sorted(root.iterdir())
                  if p.is_dir() and not p.name.startswith((".", "_"))] if root.exists() else []
    results = []
    if not tables:
        results.append({"table": str(root), "check": "datasets_present",
                        "severity": "fail", "success": False})
    required = set(rules.get("required_datasets", [])) | (set(contract['tables']) if contract else set())
    names = {name for name, _ in tables}
    for name in required:
        if name not in names:
            results.append({"table": name, "check": "dataset_present",
                            "severity": "fail", "success": False})
    for name, path in tables:
        if contract and name not in contract['tables']:
            results.append({'table': name, 'check': 'dataset_in_contract', 'severity': 'fail', 'success': False})
            continue
        checks = match_rules(rules, name)
        if not checks and layer == "raw":
            continue
        if not checks:
            results.append({"table": name, "check": "rules_present",
                            "severity": "fail", "success": False})
            continue
        try:
            df = (spark.read.option("header", "true").option("inferSchema", "true").csv(str(path))
                  if path.suffix.lower() == ".csv" else spark.read.parquet(str(path)))
        except Exception as exc:
            results.append({"table": name, "check": "readable", "severity": "fail",
                            "success": False, "error": str(exc)})
            continue
        for check in checks:
            result = {"table": name, "check": check["type"],
                      "severity": check.get("severity", default)}
            try:
                result.update(evaluate(df, check, spark, root))
            except Exception as exc:
                # Erro de execução/configuração nunca deve virar aprovação silenciosa.
                result.update(success=False, severity="fail", error=str(exc))
            results.append(result)
    if contract is not None and sha256(contract_path) != contract_hash:
        results.append({'table': '*', 'check': 'contract_unchanged', 'severity': 'fail', 'success': False})
    failed = sum(not r["success"] and r["severity"] == "fail" for r in results)
    warnings = sum(not r["success"] and r["severity"] == "warn" for r in results)
    outdir = ctx.data_quality_dir / ("results" if layer == "raw" else "bronze_results")
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{ctx.run_id}_{layer}_checks.json"
    out.write_text(json.dumps({"run_id": ctx.run_id, "started_at_utc": ctx.started_at_utc,
                               "snapshot_contract_sha256": contract_hash,
                               "failed_checks": failed, "warning_checks": warnings,
                               "results": results}, indent=2), encoding="utf-8")
    if failed:
        raise RuntimeError(f"Data Quality ({layer.upper()}) falhou: {failed} checks; relatório: {out}")
    return {"json": str(out), "failed_checks": failed, "warning_checks": warnings,
            "snapshot_contract_sha256": contract_hash}
