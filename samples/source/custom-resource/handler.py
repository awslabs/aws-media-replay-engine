# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import hashlib
import hmac
import json
import logging
import os
import requests
from requests_aws4auth import AWS4Auth

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig()
logger = logging.getLogger("mre_custom_resource")
logger.setLevel(LOG_LEVEL)

valid_types = ["plugin", "model", "prompt", "profile"]


def on_event(event, context):
    logger.info(f"Event -- {event}")
    props = event["ResourceProperties"]

    config = json.loads(props['config'])
    type_ = props["type"]

    if type_ not in valid_types:
        raise Exception(f"Type {type_} is not recognised")

    if type_ == "plugin":
        lambda_arn = props["ExecuteLambdaQualifiedARN"] + ":$LATEST"
        config = config["MRE"]["Plugin"]
        config.update({"ExecuteLambdaQualifiedARN": lambda_arn})

    request_type = event["RequestType"]
    if request_type == "Create":
        return create_update(config, type_)
    if request_type == "Update":
        return create_update(config, type_)
    if request_type == "Delete":
        return delete(config, type_)
    raise Exception(f"Invalid request type: {request_type}")


def create_update(config, resource):
    logger.info(f"Posting {resource}")
    physical_id = config["Name"]
    method = "POST"

    # If profile exists then update processing profile.
    if resource == "profile":
        name = config['Name']
        logger.info("profile")
        get_profile = call_api(f"profile/{name}", None, "GET")
        logger.info(f"GET profile --->{get_profile.json()}")
        if get_profile.status_code == 200:
            logger.info('Profile already exists, sending update')
            resource = f"{resource}/{name}"
            method = "PUT"
            config.pop('Name')
            print(config)
        else:
            logger.info('Profile does not exist, sending create')

    # Get the "Version" for the model endpoints for registering the plugin
    if resource == "plugin" and config["ExecutionType"] == "SyncModel":
        if "ModelEndpoints" in config and len(config["ModelEndpoints"]) > 0:
            for index, model_endpoint in enumerate(config["ModelEndpoints"]):
                if "Version" not in model_endpoint:
                    api_response = call_api(f"model/{model_endpoint['Name']}", None, "GET").json()
                    logger.info(f"GET api response -- {api_response}")
                    config["ModelEndpoints"][index]["Version"] = f"v{api_response['Latest']}"

    response = call_api(resource, json.dumps(config), method)
    logger.info(f"{method} api response -- {response.json()}")

    if response.status_code > 299:
        raise Exception(f"API Error: {response.text}")
    return {"PhysicalResourceId": physical_id}


def delete(config, resource):
    logger.info(f"Deleting {resource}")
    name = config["Name"]
    response = call_api(f"{resource}/{name}", None, "DELETE")
    if response.status_code > 299:
        raise Exception(f"API Error: {response.text}")


def get_iam_auth():
    return AWS4Auth(
        os.environ['AWS_ACCESS_KEY_ID'],
        os.environ['AWS_SECRET_ACCESS_KEY'],
        os.environ['AWS_REGION'],
        'execute-api',
        session_token=os.getenv('AWS_SESSION_TOKEN')
    )


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


def call_api(path, api_body, api_method, api_headers=None):
    global res
    try:
        url = os.environ["CONTROLPLANE_ENDPOINT"] + path

        if not url:
            raise Exception("No route found")

        if api_method in ['GET', 'DELETE']:

            res = requests.request(
                method=api_method,
                url=f"{url}",
                auth=get_iam_auth()
            )

            if api_headers:
                if 'accept' in api_headers:
                    if 'application/octet-stream' in api_headers['accept']:
                        blob_content = json.loads(res.text)
                        return {"body": bytes(blob_content['BlobContent'], 'utf-8'),
                                "status_code": 200,
                                "headers": {'Content-Type': 'application/octet-stream'}}

        elif api_method in ['PUT', 'POST']:
            api_headers = {"Content-Type": "application/json"}
            res = requests.request(
                method=api_method,
                url=f"{url}",
                headers=api_headers,
                data=api_body,
                auth=get_iam_auth()
            )

    except Exception as e:
        raise
    else:
        return res
