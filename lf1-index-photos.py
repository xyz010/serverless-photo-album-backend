import json
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from botocore.exceptions import ClientError
import requests


REGION = 'us-east-1'
INDEX = 'photos-cf'
BUCKET_NAME = 'bucketb2-cf'

def lambda_handler(event, context):
    s3client = boto3.client('s3')
    rekognition_client = boto3.client('rekognition')

    labels = []
    photo_name = event['Records'][0]['s3']['object']['key']
    metadata = s3client.head_object(Bucket=BUCKET_NAME, Key=photo_name)
    httpheaders = metadata['ResponseMetadata']['HTTPHeaders']
    if 'x-amz-meta-customlabels' in httpheaders.keys():
        customLabels = httpheaders['x-amz-meta-customlabels']
        for label in customLabels.split(","):
            labels.append(label.strip())

    detect_labels_response = rekognition_client.detect_labels(
        Image={'S3Object': {'Bucket': BUCKET_NAME, 'Name': photo_name}})
    for label in detect_labels_response['Labels']:
        labels.append(label['Name'])
    print(labels)
    object = {
        'objectKey': photo_name,
        'bucket': BUCKET_NAME,
        'createdTimestamp': str(metadata['LastModified']),
        'labels': labels
    }
    post(object, photo_name)
    return object


def post(document, key):
    awsauth = get_awsauth(REGION, 'es')
    client = boto3.client('opensearch')
    host = client.describe_domain(DomainName=INDEX)['DomainStatus']['Endpoint']

    es_client = OpenSearch(hosts=[{
        'host': host,
        'port': 443
    }],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection)

    index_name = INDEX
    index_body = {
        'settings': {
            'index': {
                'number_of_shards': 1
            }
        }
    }

    res = es_client.index(index=INDEX, id=key, body=document)
    print(res)
    print(es_client.get(index=INDEX, id=key))


def get_awsauth(region, service):
    cred = boto3.Session().get_credentials()
    return AWS4Auth(cred.access_key,
                    cred.secret_key,
                    region,
                    service,
                    session_token=cred.token)
