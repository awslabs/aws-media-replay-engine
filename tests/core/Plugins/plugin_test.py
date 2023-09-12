# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import pytest
import json
import sys
from chalice import ChaliceViewError, BadRequestError, NotFoundError, ConflictError, Response
import os

from utils.config_mgr import load_config
from utils.api_client import call_api

CURRENT_PATH = os.path.dirname(__file__)
print(f"Current Path: {CURRENT_PATH}")

AWS_ACCOUNT_ID = os.getenv('AWS_ACCOUNT_ID')
AWS_REGION = os.getenv('AWS_REGION')


def test_detect_passthrough_plugin_creation_deletion_get():
    config = load_config(f"{CURRENT_PATH}/config/DetectPassThrough100.json")
    config["ExecuteLambdaQualifiedARN"] = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT_ID}:function:DetectPassThrough100:$LATEST"
    response = call_api(path="plugin", api_method="POST", api_body=json.dumps(config))
    assert response.status_code == 200

    # Get this Plugin
    response = call_api(path="plugin/TestSuite-ModelTest-DetectPassThrough100", api_method="GET")
    assert response.status_code == 200
    model= response.json()
    assert model['Name'] == config['Name']
    assert model['Class'] == config['Class']
    assert model['ExecutionType'] == config['ExecutionType']

    # Delete the Plugin
    call_api(path="plugin/TestSuite-ModelTest-DetectPassThrough100", api_method="DELETE")

    # Get this Plugin 
    with pytest.raises(NotFoundError):
        response = call_api(path="plugin/TestSuite-ModelTest-DetectPassThrough100", api_method="GET")
    
def test_plugin_creation_failure_when_using_invalid_class():
    config = load_config(f"{CURRENT_PATH}/config/DetectPassThrough100.json")
    config["ExecuteLambdaQualifiedARN"] = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT_ID}:function:DetectPassThrough100:$LATEST"
    config['Class'] = "NON_EXISTENT"

    with pytest.raises(BadRequestError):
        response = call_api(path="plugin", api_method="POST", api_body=json.dumps(config))
    
def test_plugin_creation_failure_when_using_invalid_execution_type():
    config = load_config(f"{CURRENT_PATH}/config/DetectPassThrough100.json")
    config["ExecuteLambdaQualifiedARN"] = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT_ID}:function:DetectPassThrough100:$LATEST"
    config['ExecutionType'] = "NON_EXISTENT"

    with pytest.raises(BadRequestError):
        response = call_api(path="plugin", api_method="POST", api_body=json.dumps(config))
    
def test_plugin_creation_failure_when_using_invalid_lambda_arn():
    config = load_config(f"{CURRENT_PATH}/config/DetectPassThrough100.json")
    with pytest.raises(BadRequestError):
        response = call_api(path="plugin", api_method="POST", api_body=json.dumps(config))

def test_plugin_creation_failure_missing_model_endpoint():
    config = load_config(f"{CURRENT_PATH}/config/DetectPassThrough100.json")
    config["ExecutionType"] = "SyncModel"
    with pytest.raises(BadRequestError):
        response = call_api(path="plugin", api_method="POST", api_body=json.dumps(config))

