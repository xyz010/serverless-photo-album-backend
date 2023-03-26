import json
import time
import os
import logging
import boto3
import requests
from requests_aws4auth import AWS4Auth
from opensearchpy import OpenSearch, RequestsHttpConnection

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

HOST = 'search-photos-eaer4juf2onevj7sztagvxxoqi.us-east-1.es.amazonaws.com'
INDEX = 'photos'

def lambda_handler(event, context):
    # By default, treat the user request as coming from the America/New_York time zone.
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    # q = "Show me photos of dogs and oranges"
    print("event is " + str(event))
    # print('dispatch is', dispatch(event))
    query = event['queryStringParameters']
    # return dispatch(query)
    return photos_suggestions(query)

def dispatch(intent_request):
    logger.debug(intent_request)
    # intent_name = intent_request['sessionState']['intent']['name']
    if intent_name == 'SearchIntent':
        logger.debug('dispatch sessionId={}, intentName={}'.format(
            intent_request['sessionId'], intent_request['sessionState']['intent']['name']
        )
        )
        return photos_suggestions(intent_request)
    else:
        raise Exception('Intent with name {} is not supported'.format(intent_name))
    return photos_suggestions(intent_request)

def photos_suggestions(intent_request):
    """
    Performs image retrieval based on keywords
    TODO: should I use a try?
    """
    # q = intent_request['queryStringParameters']['q']
    q = intent_request['q']
    url_list = []
    if type(q) == str:
        client = boto3.client('lexv2-runtime', region_name='us-east-1')
        response = client.recognize_text(
            botId='D3UIIZYO9M',
            botAliasId='TSTALIASID',  # MODIFY HERE
            localeId='en_US',
            sessionId='testuser',
            text=q
        )
        print("Bot Response: {}".format(json.dumps(response)))
        slots = [response['sessionState']['intent']['slots']['query1']['value']['resolvedValues'][0]]
        if response['sessionState']['intent']['slots']['query2']:
            slots.append(response['sessionState']['intent']['slots']['query2']['value']['resolvedValues'][0])
        print("Incoming Slots from Lex are {}".format(slots))

        for query_word in slots:
            # for every query word get url from elastic search
            # append the url_list
            url_list += retrieve_url_from_opensearch(query_word)

    # now return the images
    if url_list:
        return {
            'statusCode': 200,
            'headers': {
                "Access-Control-Allow-Origin": "*",
                'Content-Type': 'application/json'
            },
            'body': json.dumps(url_list)
        }
    else:
        return {
            'statusCode': 200,
            'headers': {
                "Access-Control-Allow-Origin": "*",
                'Content-Type': 'application/json'
            },
            'body': json.dumps("There were no keyword hits in our database")
        }


def retrieve_url_from_opensearch(query_word):
    region = 'us-east-1'
    service = 'es'
    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)
    query = {
        "query": {
            "query_string": {
                "default_field": "labels",
                "query": query_word
            }
        }
    }
    
    client = OpenSearch(hosts=[{
        'host': HOST,
        'port': 443
    }],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection)

    res = client.search(index=INDEX, body=query)
    
    hits = res['hits']['hits']
    print("OpenSearch Hits are {}".format(hits))
    url_photo_list = []
    for hit in hits:
        hit_labels = [w.lower() for w in hit['_source']['labels']]
        if query_word in hit_labels:
            url_photo_list.append('https://bucketb2.s3.amazonaws.com/' + hit['_source']['objectKey'])

    return url_photo_list

