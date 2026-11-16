import hashlib
import os
import uuid
import boto3
from botocore.config import Config

def client():
    return boto3.client('s3', endpoint_url=os.environ['R2_ENDPOINT'], region_name='auto',
        aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],
        config=Config(connect_timeout=3, read_timeout=12, retries={'total_max_attempts':1},
                      s3={'addressing_style':'path'}))

def put_document(account_id, filename, data, key=None):
    key = key or f'{account_id}/{uuid.uuid4()}'
    client().put_object(Bucket=os.environ['R2_BUCKET'], Key=key, Body=data,
                        ContentType='application/octet-stream')
    return (account_id, key, filename, hashlib.sha256(data).hexdigest(), len(data))

def get_document(row):
    response=client().get_object(Bucket=os.environ['R2_BUCKET'], Key=row['object_key'])
    with response['Body'] as body:
        data=body.read(8*1024*1024+1)
    if len(data)!=row['byte_count'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
        raise ValueError('Document integrity check failed')
    return data
