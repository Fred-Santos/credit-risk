"""Spark/Delta em S3A, com Hadoop/AWS SDK compatíveis com o runtime fixado."""
from src.object_store.config import load_config,credentials
from src.utils.spark import session_settings


def create_object_spark(repo,*,app_name='credit-risk-objects',config_path=None):
    from pyspark.sql import SparkSession
    from delta import configure_spark_with_delta_pip
    config=load_config(repo);secret=credentials(repo,config)
    settings=session_settings(repo,config_path)
    builder=SparkSession.builder.master(settings['master']).appName(app_name)
    for name,value in settings.get('config',{}).items():builder=builder.config(name,value)
    options={'spark.jars.ivy':str(repo/'.runtime/ivy'),
        'spark.jars.ivySettings':str(repo/'configs/ivysettings.xml'),
        'spark.sql.extensions':'io.delta.sql.DeltaSparkSessionExtension',
        'spark.sql.catalog.spark_catalog':'org.apache.spark.sql.delta.catalog.DeltaCatalog',
        'spark.delta.logStore.s3a.impl':config['delta_log_store'],
        'spark.hadoop.fs.s3a.impl':'org.apache.hadoop.fs.s3a.S3AFileSystem',
        'spark.hadoop.fs.s3a.endpoint':config['endpoint'],
        'spark.hadoop.fs.s3a.endpoint.region':config['region'],
        'spark.hadoop.fs.s3a.path.style.access':'true',
        'spark.hadoop.fs.s3a.connection.ssl.enabled':'false',
        'spark.hadoop.fs.s3a.aws.credentials.provider':'org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider',
        'spark.hadoop.fs.s3a.access.key':secret['access_key'],
        'spark.hadoop.fs.s3a.secret.key':secret['secret_key'],
        'spark.hadoop.fs.s3a.connection.maximum':'16',
        'spark.hadoop.fs.s3a.threads.max':'8',
        'spark.hadoop.fs.s3a.connection.establish.timeout':'2000',
        'spark.hadoop.fs.s3a.connection.timeout':'10000',
        'spark.hadoop.fs.s3a.attempts.maximum':'2',
        'spark.hadoop.fs.s3a.retry.limit':'1',
        'spark.hadoop.fs.s3a.retry.interval':'100ms',
        'spark.hadoop.fs.s3a.multipart.size':'8388608',
        'spark.hadoop.fs.s3a.multipart.threshold':'8388608',
        'spark.hadoop.fs.s3a.fast.upload':'true',
        'spark.hadoop.fs.s3a.fast.upload.buffer':'bytebuffer',
        'spark.databricks.delta.snapshotPartitions':settings['config']['spark.sql.shuffle.partitions']}
    for name,value in options.items():builder=builder.config(name,value)
    builder=configure_spark_with_delta_pip(builder,extra_packages=[
        'org.apache.hadoop:hadoop-aws:'+config['hadoop_aws'],
        'com.amazonaws:aws-java-sdk-bundle:'+config['aws_java_sdk_bundle']])
    spark=builder.getOrCreate();spark.sparkContext.setLogLevel('WARN')
    if spark.sparkContext._jvm.org.apache.hadoop.util.VersionInfo.getVersion()!=config['hadoop_aws']:
        spark.stop();raise ValueError('Hadoop do runtime diverge do conector fixado')
    return spark
