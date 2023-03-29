import json
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from botocore.exceptions import ClientError
import requests

REGION = 'us-east-1'
# HOST = 'search-photos-cf.us-east-1.es.amazonaws.com'
INDEX = 'photos-cf'
# hey this is a test, second test


def lambda_handler(event, context):
    s3client = boto3.client('s3')
    rekognition_client = boto3.client('rekognition')

    labels = []
    photo_name = event['Records'][0]['s3']['object']['key']
    bucket_name = 'bucketb2'
    metadata = s3client.head_object(Bucket=bucket_name, Key=photo_name)
    httpheaders = metadata['ResponseMetadata']['HTTPHeaders']
    if 'x-amz-meta-customLabels' in httpheaders.keys():
        labels.extend(httpheaders['x-amz-meta-customLabels'])

    detect_labels_response = rekognition_client.detect_labels(
        Image={'S3Object': {'Bucket': bucket_name, 'Name': photo_name}})
    for label in detect_labels_response['Labels']:
        labels.append(label['Name'])

    object = {
        'objectKey': photo_name,
        'bucket': bucket_name,
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