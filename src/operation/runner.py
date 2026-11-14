"""Supervisor: uma operação lógica, tentativas novas e retry restrito."""
from datetime import datetime, timezone
import time
import uuid
from pathlib import Path
from src.operation.metrics import StageClock, ResourceSampler

from src.publication.protocol import atomic_json
from src.utils.run_context import RunContext
from src.pipelines.download_home_credit import sha256


def now():
    return datetime.now(timezone.utc).isoformat()


def classify(error, stage):
    from botocore.exceptions import (EndpointConnectionError, ConnectionClosedError,
        ConnectTimeoutError, ReadTimeoutError, ClientError)
    from src.quality.silver_contracts import SilverContractError
    from src.gold.quality import GoldQualityError
    if isinstance(error,(SilverContractError,GoldQualityError)):return 'quality_rejected',False,3
    if isinstance(error, KeyboardInterrupt): return 'cancelled', False, 130
    if isinstance(error, BlockingIOError): return 'writer_conflict', False, 4
    if isinstance(error, (EndpointConnectionError, ConnectionClosedError, ConnectTimeoutError, ReadTimeoutError)):
        return 'temporary_access', True, 5
    if isinstance(error, ClientError):
        status = error.response.get('ResponseMetadata', {}).get('HTTPStatusCode')
        if status in (408, 429, 500, 502, 503, 504): return 'temporary_access', True, 5
        return 'access_rejected', False, 3
    if isinstance(error, TimeoutError) and stage == 'service_start': return 'service_timeout', True, 5
    # Java exceptions are classified by actual cause classes, never by a message match.
    java = getattr(error, 'java_exception', None)
    for _ in range(12):
        if java is None: break
        try:
            name = java.getClass().getName()
            if name in ('java.net.ConnectException', 'java.net.SocketTimeoutException',
                        'java.net.NoRouteToHostException', 'java.net.UnknownHostException'):
                return 'temporary_access', True, 5
            java = java.getCause()
        except Exception: break
    if isinstance(error, (ValueError, FileNotFoundError, PermissionError)):
        return 'invalid_input_or_configuration', False, 3
    return 'unexpected', False, 1


def supervise(repo, options, *, max_attempts=2, retry_delay=2, service_factory=None,
              spark_factory=None, executor=None, sleep=time.sleep, reports_directory=None):
    if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
        raise ValueError('max_attempts deve estar entre 1 e 3')
    if not 0 <= retry_delay <= 30: raise ValueError('retry_delay deve estar entre 0 e 30 s')
    from src.object_store.service import ObjectService
    from src.object_store.spark import create_object_spark
    from src.pipelines.run_lakehouse import execute
    service_factory = service_factory or ObjectService
    spark_factory = spark_factory or create_object_spark
    executor = executor or execute
    operation_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
    directory=Path(reports_directory or repo/'artifacts/f09/operations').resolve()
    if not directory.is_relative_to(repo.resolve()) or directory==repo.resolve():raise ValueError('Relatórios devem ficar dentro do repositório')
    path = directory/(operation_id+'.json')
    report = {'operation_id':operation_id, 'status':'running', 'stage':'initialization',
        'started_at_utc':now(), 'options':options, 'max_attempts':max_attempts,
        'retry_delay_seconds':retry_delay, 'attempts':[]}
    atomic_json(path, report)
    timer=StageClock();timer.enter('initialization')
    sampler=ResourceSampler().start()
    for number in range(1, max_attempts+1):
        attempt = {'number':number, 'run_id':None, 'status':'running',
                   'stage':'service_configuration', 'started_at_utc':now()}
        report['attempts'].append(attempt)
        attempt_timer=StageClock()
        ctx = None
        service = spark = None
        owned = False
        error = None
        def stage(name):
            timer.enter(name)
            attempt_timer.enter(name)
            attempt['stage'] = report['stage'] = name
            attempt.setdefault('stages', []).append({'stage':name, 'at_utc':now()})
            atomic_json(path, report)
        try:
            stage('context_configuration')
            ctx = RunContext.create(repo)
            attempt['run_id'] = ctx.run_id
            stage('service_configuration')
            service = service_factory(repo)
            stage('service_status')
            owned = service.status()['status'] != 'running'
            stage('service_start')
            service.start()
            stage('spark_start')
            spark = spark_factory(repo, app_name='lakehouse-operation')
            result = executor(ctx, spark, **options, operation_id=operation_id, on_stage=stage)
            attempt.update(status='passed', result=result)
        except (Exception, KeyboardInterrupt) as caught:
            error = caught
            category, retryable, code = classify(caught, attempt['stage'])
            attempt.update(status='cancelled' if code == 130 else 'failed', error_type=type(caught).__name__,
                error=str(caught), category=category, retryable=retryable, exit_code=code)
        finally:
            timer.enter('cleanup')
            attempt_timer.enter('cleanup')
            cleanup = []
            for name, action in [('spark_stop', spark.stop if spark is not None else None),
                                 ('service_stop', service.stop if service is not None and owned else None)]:
                if action is not None:
                    try: action()
                    except Exception as caught: cleanup.append({'stage':name,'error_type':type(caught).__name__,'error':str(caught)})
            if ctx is not None:
                run_report=repo/'artifacts/f09/runs'/(ctx.run_id+'.json')
                if run_report.is_file():
                    try:attempt['run_report']={'path':run_report.relative_to(repo).as_posix(),'sha256':sha256(run_report)}
                    except OSError as reference_error:attempt['run_report_reference_error']=str(reference_error)
            attempt['timing']=attempt_timer.snapshot()
            attempt['cleanup_errors'] = cleanup
            attempt['finished_at_utc'] = now()
        if cleanup:
            # An uncertain cleanup never starts another writer or hides the primary error.
            if error is None:
                attempt.update(status='failed', category='cleanup_failed', retryable=False, exit_code=1)
            else: attempt['retryable'] = False
        if attempt['status'] == 'passed':
            report.update(status='passed', stage='complete', exit_code=0, result=attempt['result'])
            break
        if attempt['retryable'] and number < max_attempts:
            timer.enter('retry_wait')
            report.update(status='retry_wait', stage=attempt['stage'])
            atomic_json(path, report)
            try: sleep(retry_delay)
            except KeyboardInterrupt:
                report.update(status='cancelled', exit_code=130)
                break
            report['status'] = 'running'
            continue
        report.update(status=attempt['status'], stage=attempt['stage'], exit_code=attempt['exit_code'])
        break
    report['resources']=sampler.stop()
    report['timing']=timer.snapshot()
    report['finished_at_utc'] = now()
    atomic_json(path, report)
    return {'status':report['status'], 'operation_id':operation_id,
            'report':str(path), 'exit_code':report['exit_code']}
