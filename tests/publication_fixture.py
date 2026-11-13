"""Dados pequenos e schemas independentes para F05/F06; nenhuma origem Home Credit."""
from datetime import date

from src.quality.bronze_contract import METADATA
from src.quality.silver_contracts import DOMAINS, RELATIONSHIPS
from src.silver.incremental import EVENT_STATE


def fixture_frames(spark, *, corrected=False, late=False, history_only=False):
    from pyspark.sql import functions as F
    rows = {
        'credit_cases': ([(1, date(2020, 1, 1), 202001, 0, 0), (2, date(2020, 1, 2), 202001, 1, 1),
                          (3, date(2020, 2, 1), 202002, 60, 1)],
                         'case_id long, date_decision date, MONTH long, WEEK_NUM long, target long'),
        'credit_static': ([(1, 11.0 if corrected else 10.0), (2, None), (3, 30.0)],
                          'case_id long, annuity_780A double'),
        'previous_applications': ([(1, 0, 6.0 if corrected or history_only else 5.0, date(2019, 1, 1)),
                                   (1, 1, None, None), (2, 0, 7.0, date(2020, 1, 3))],
                                  'case_id long, num_group1 long, credamount_590A double, observedD date')}
    if late:
        rows['credit_cases'][0].append((4, date(2020, 1, 4), 202001, 2, 0))
        rows['credit_static'][0].append((4, 40.0))
        rows['previous_applications'][0].append((4, 0, 8.0, date(2019, 12, 31)))
    frames, plan = {}, {'domains': DOMAINS, 'tables': {}}
    for name, (values, schema) in rows.items():
        frame = spark.createDataFrame(values, schema)
        business = dict(frame.dtypes)
        key = ['case_id', 'num_group1'] if name == 'previous_applications' else ['case_id']
        dates = [c for c, t in business.items() if t == 'date']
        required = list(business) if name == 'credit_cases' else key
        plan['tables'][name] = {'schema': {**business, **METADATA}, 'key': key,
            'required_non_null': required + list(METADATA), 'grain': 'synthetic_fixture',
            'minimum_rows': 0 if name == 'previous_applications' else 1,
            'dates': dates, 'relationship': RELATIONSHIPS.get(name)}
        changed = (F.col('case_id') == 1) & F.lit((corrected and name == 'credit_static') or
            ((corrected or history_only) and name == 'previous_applications'))
        if name == 'previous_applications':
            changed = changed & (F.col('num_group1') == 0)
        frame = (frame.withColumn('_run_id', F.lit('fixture_bronze'))
            .withColumn('_ingest_date', F.lit(date(2026, 11, 13)))
            .withColumn('_source_file', F.lit('file:///synthetic_fixture.parquet'))
            .withColumn('ingest_batch', F.lit('fixture_batch'))
            .withColumn('_source_system', F.lit('synthetic_fixture_only'))
            .withColumn('_selection_id', F.lit('a' * 24))
            .withColumn('_stream_id', F.lit('fixture'))
            .withColumn('_source_revision', F.when(changed, 2).otherwise(1).cast('long'))
            .withColumn('_event_id', F.sha2(F.concat_ws(':', F.lit(name), *[F.col(c).cast('string') for c in key],
                                                        F.col('_source_revision').cast('string')), 256))
            .withColumn('_payload_sha256', F.sha2(F.to_json(F.struct(*[F.col(c) for c in business])), 256))
            .withColumn('_is_simulated', F.lit(True)))
        assert dict(frame.dtypes) == {**business, **METADATA, **EVENT_STATE}
        frames[name] = frame
    return frames, plan
