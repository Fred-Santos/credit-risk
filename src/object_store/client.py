"""Somente API S3 para dados e manifestos; ETag é precondição, SHA é integridade."""
import hashlib
import json
from pathlib import Path

from src.object_store.config import load_config,credentials,s3_key


class ObjectClient:
    def __init__(self,repo,*,wrong_credentials=False):
        import boto3
        from botocore.config import Config
        self.repo=Path(repo).resolve();self.config=load_config(self.repo)
        secret=credentials(self.repo,self.config)
        self.bucket=self.config['bucket']
        self.s3=boto3.client('s3',endpoint_url=self.config['endpoint'],region_name=self.config['region'],
            aws_access_key_id='invalid-access-key-000000' if wrong_credentials else secret['access_key'],
            aws_secret_access_key='invalid-secret-key-000000' if wrong_credentials else secret['secret_key'],
            config=Config(signature_version='s3v4',connect_timeout=2,read_timeout=10,
                retries={'max_attempts':0},s3={'addressing_style':'path'},
                request_checksum_calculation='when_required',response_checksum_validation='when_required'))

    def ensure_bucket(self):
        from botocore.exceptions import ClientError
        try:self.s3.head_bucket(Bucket=self.bucket)
        except ClientError as error:
            if error.response['ResponseMetadata']['HTTPStatusCode']!=404:raise
            self.s3.create_bucket(Bucket=self.bucket)

    def uri(self,key):return f's3a://{self.bucket}/'+s3_key(key)

    def get(self,key):
        result=self.s3.get_object(Bucket=self.bucket,Key=s3_key(key))
        try:data=result['Body'].read()
        finally:result['Body'].close()
        return data,result['ETag']

    def exists(self,key):
        from botocore.exceptions import ClientError
        try:self.s3.head_object(Bucket=self.bucket,Key=s3_key(key));return True
        except ClientError as error:
            if error.response['ResponseMetadata']['HTTPStatusCode']==404:return False
            raise

    def json(self,key):return json.loads(self.get(key)[0])

    def put_new(self,key,data):
        from botocore.exceptions import ClientError
        try:
            return self.s3.put_object(Bucket=self.bucket,Key=s3_key(key),Body=data,IfNoneMatch='*')['ETag']
        except ClientError as error:
            if error.response['ResponseMetadata']['HTTPStatusCode']!=412:raise
            previous,etag=self.get(key)
            if previous!=data:raise ValueError('Objeto imutável existente com outro conteúdo')
            return etag

    def put_json(self,key,value):
        return self.put_new(key,json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode())

    def replace(self,key,data,previous_etag):
        condition={'IfNoneMatch':'*'} if previous_etag is None else {'IfMatch':previous_etag}
        return self.s3.put_object(Bucket=self.bucket,Key=s3_key(key),Body=data,**condition)['ETag']

    def list(self,prefix):
        paginator=self.s3.get_paginator('list_objects_v2')
        return {item['Key']:item['Size'] for page in paginator.paginate(Bucket=self.bucket,Prefix=s3_key(prefix))
                for item in page.get('Contents',[])}

    def inventory(self,prefix):
        prefix=s3_key(prefix).rstrip('/')+'/'
        return {key[len(prefix):]:hashlib.sha256(self.get(key)[0]).hexdigest() for key in sorted(self.list(prefix))
                if not key.endswith('/') and (key.endswith('.parquet') or
                    ('/_delta_log/' in key and not key.rsplit('/',1)[1].startswith('.')))}

    def checksum(self,key):
        result=self.s3.get_object(Bucket=self.bucket,Key=s3_key(key))
        checksum=hashlib.sha256()
        try:
            for chunk in iter(lambda:result['Body'].read(1024*1024),b''):checksum.update(chunk)
        finally:result['Body'].close()
        return checksum.hexdigest()
