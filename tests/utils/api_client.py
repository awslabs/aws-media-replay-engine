# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
import boto3
import datetime
import hashlib
import hmac
import json
import logging
import os
from urllib.parse import urlparse
from urllib.parse import unquote
import requests
from requests_aws4auth import AWS4Auth
from chalice import ChaliceViewError, BadRequestError, NotFoundError, ConflictError
from chalice import Response
from enum import Enum
import time

# from aws_requests_auth.aws_auth import AWSRequestsAuth
class ApiUrlType(Enum):
    CONTROL_PLANE = 1
    DATA_PLANE = 2

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig()
logger = logging.getLogger("api_client")
logger.setLevel(LOG_LEVEL)

AWS_ACCOUNT_ID = os.getenv('AWS_ACCOUNT_ID')
AWS_REGION = os.getenv('AWS_REGION')

ssm_client = boto3.client('ssm')
_PARAM_CACHE = {}

def get_controlplane_url():
     return _PARAM_CACHE.get("/MRE/ControlPlane/EndpointURL")

def get_dataplane_url():
     return _PARAM_CACHE.get("/MRE/DataPlane/EndpointURL")

def get_endpoint_urls_from_ssm():
    response = ssm_client.get_parameters(
        Names=['/MRE/DataPlane/EndpointURL','/MRE/ControlPlane/EndpointURL'],
        WithDecryption=True
    )
    for parameter in response["Parameters"]:
        endpoint_name = parameter["Name"]
        endpoint_url = parameter["Value"]
        _PARAM_CACHE[endpoint_name] = endpoint_url


get_endpoint_urls_from_ssm()


CONTROLPLANE_ENDPOINT = get_controlplane_url()
DATAPLANE_ENDPOINT = get_dataplane_url()

def get_iam_auth(valid_auth: bool):
    if valid_auth:
        return AWS4Auth(
            os.environ['AWS_ACCESS_KEY_ID'],
            os.environ['AWS_SECRET_ACCESS_KEY'],
            os.environ['AWS_REGION'],
            'execute-api',
            session_token=os.getenv('AWS_SESSION_TOKEN')
        ) 
    else:
        return AWS4Auth(
            os.environ['AWS_ACCESS_KEY_ID'][:-1],
            os.environ['AWS_SECRET_ACCESS_KEY'],
            os.environ['AWS_REGION'],
            'execute-api',
            session_token=os.getenv('AWS_SESSION_TOKEN')[:-1]
        )
    
# The following functions derive keys for the request. For more information, see
# http://docs.aws.amazon.com/general/latest/gr/signature-v4-examples.html#signature-v4-examples-python.
def sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def getSignatureKey(key, date_stamp, regionName, serviceName):
    kDate = sign(('AWS4' + key).encode('utf-8'), date_stamp)
    kRegion = sign(kDate, regionName)
    kService = sign(kRegion, serviceName)
    kSigning = sign(kService, 'aws4_request')
    return kSigning

def get_error_message(error_response):
    try:
        res_json = json.loads(error_response)
        if 'message' in res_json:
            return res_json['message']
        elif 'Message' in res_json:
            return res_json['Message']
    except Exception as e:
        print(e)
    else:
        return error_response

def call_api(path, api_method, api_body=None, api_headers=None, uri_params=None, api_url=ApiUrlType.CONTROL_PLANE, valid_auth=True):
    try:
        url = CONTROLPLANE_ENDPOINT + path if api_url == ApiUrlType.CONTROL_PLANE else DATAPLANE_ENDPOINT + path

        if not url:
            raise Exception("No route found")

        if api_method in ['GET', 'DELETE']:

            res = requests.request(
                method=api_method,
                url=f"{url}",
                auth=get_iam_auth(valid_auth)
            )

            if api_headers:
                if 'accept' in api_headers:
                    if 'application/octet-stream' in api_headers['accept']:
                        blob_content = json.loads(res.text)
                        return Response(body=bytes(blob_content['BlobContent'], 'utf-8'),
                                        status_code=200,
                                        headers={'Content-Type': 'application/octet-stream'})

        elif api_method in ['PUT', 'POST']:
            api_headers = {"Content-Type": "application/json"}
            res = requests.request(
                method=api_method,
                url=f"{url}",
                headers=api_headers,
                data=api_body,
                auth=get_iam_auth(valid_auth)
            )

        res.raise_for_status()

    except requests.HTTPError as e:
        error_msg = get_error_message(e.response.text)
        
        if res.status_code == 404:
            raise NotFoundError(error_msg)
        elif res.status_code == 400:
            raise BadRequestError(error_msg)
        elif res.status_code == 409:
            raise ConflictError(error_msg)
        elif res.status_code >= 500:
            raise ChaliceViewError(error_msg)
        else:
            raise
    
    except requests.exceptions.RequestException as e:
        error_msg = get_error_message(e.response.text)

        if res.status_code == 404:
            raise NotFoundError(error_msg)
        elif res.status_code == 400:
            raise BadRequestError(error_msg)
        elif res.status_code == 409:
            raise ConflictError(error_msg)
        elif res.status_code >= 500:
            raise ChaliceViewError(error_msg)
        else:
            raise
    
    except Exception as e:
        print(e)
        raise
    else:
        return res