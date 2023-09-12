
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0import pytest
import pytest
import json
import sys
from chalice import ChaliceViewError, BadRequestError, NotFoundError, ConflictError, Response
import os
from datetime import datetime, timedelta, timezone
from utils.config_mgr import load_config
from utils.api_client import call_api
import time
import boto3
from boto3.dynamodb.conditions import Key, Attr
import logging
from filelock import FileLock


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logger = logging.getLogger()

CURRENT_PATH = os.path.dirname((os.path.dirname(__file__)))
print(f"Current Path: {CURRENT_PATH}")

client = boto3.client('medialive')
AWS_ACCOUNT_ID = os.getenv('AWS_ACCOUNT_ID')
AWS_REGION = os.getenv('AWS_REGION')


# This fixture lets us run tests in parallel while enabling Plugins and Profiles to be registered only once per test session
# pytest-xdist provide workers and each worker recreates its own environment for tests. Any session fixtures by default will 
# run in each environment. To enforce execution on this only once,
# we need to use a session fixture with a workaround of using a Filelock to Synchronize multiple processes.
@pytest.fixture(scope="session")
def create_event_dependent_data(tmp_path_factory, worker_id, name="create_event_dependent_data"):
                
    if not worker_id:
        # not executing in with multiple workers, just return the channel id list and let
        # pytest's fixture caching do its job
        return create_event_dependent_data()
    
    # get the temp directory shared by all workers
    root_tmp_dir = tmp_path_factory.getbasetemp().parent

    fn = root_tmp_dir / "event-data.json"
    with FileLock(str(fn) + ".lock"):
        if fn.is_file():
            data = json.loads(fn.read_text())
        else:
            # Only one process gets to create the data, others wait for it to be created
            # This is to ensure that the data is created only once, even if multiple processes are running
            # in parallel.
            data = {"purpose": "Dummy data. Dont need this for any tests"}
            fn.write_text(json.dumps(data))
            create_event_dependency_data()
    return data



def register_DetectPassThrough100():
        config = load_config(f"{CURRENT_PATH}/config/DetectPassThrough100.json")
        config["ExecuteLambdaQualifiedARN"] = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT_ID}:function:DetectPassThrough100:$LATEST"
        call_api(path="plugin", api_method="POST", api_body=json.dumps(config))

def register_LabelPassthrough():
    config = load_config(f"{CURRENT_PATH}/config/LabelPassthrough.json")
    config["ExecuteLambdaQualifiedARN"] = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT_ID}:function:LabelPassThrough:$LATEST"
    call_api(path="plugin", api_method="POST", api_body=json.dumps(config))


def register_SegmentPassThrough100():
    config = load_config(f"{CURRENT_PATH}/config/SegmentPassThrough100.json")
    config["ExecuteLambdaQualifiedARN"] = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT_ID}:function:SegmentPassThrough100:$LATEST"
    call_api(path="plugin", api_method="POST", api_body=json.dumps(config))


def register_OptimizePassThrough():
    config = load_config(f"{CURRENT_PATH}/config/OptimizePassThrough.json")
    config["ExecuteLambdaQualifiedARN"] = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT_ID}:function:OptimizePassThrough:$LATEST"
    call_api(path="plugin", api_method="POST", api_body=json.dumps(config))



def register_profile():
    config = load_config(f"{CURRENT_PATH}/config/PassThroughProfile.json")
    call_api(path="profile", api_method="POST", api_body=json.dumps(config))
    time.sleep(30) # Lets give it sometime for the step functions def to be created
    return config


def create_event_dependency_data():
    # Check if the Dependency on Models, Profiles, Plugins is complete
    # If not, then register the models, profiles, and plugins

    #1. Check if DetectPassThrough100 is registered
    try:
        call_api(path="plugin/TestSuite-EventTest-DetectPassThrough100", api_method="GET")
    except NotFoundError as e:
        register_DetectPassThrough100()

    
    #2. Check if LabelPassthrough is registered
    try:
        call_api(path="plugin/TestSuite-EventTest-LabelPassThrough", api_method="GET")
    except NotFoundError as e:
        register_LabelPassthrough()

    
    
    #3. Check if SegmentPassThrough100 is registered
    try:
        call_api(path="plugin/TestSuite-EventTest-SegmentPassThrough100", api_method="GET")
    except NotFoundError as e:
        register_SegmentPassThrough100()
    


    #4. Check if OptimizePassThrough is regiGetting startedstered
    try:
        call_api(path="plugin/TestSuite-EventTest-OptimizePassThrough", api_method="GET")
    except NotFoundError as e:
        register_OptimizePassThrough()

    

    try:
        call_api(path="profile/TestSuite-EventTestPassThroughProfile", api_method="GET")
    except NotFoundError as e:
        register_profile()
    
    return {"purpose": "Dummy data. Dont need this for any tests"}



