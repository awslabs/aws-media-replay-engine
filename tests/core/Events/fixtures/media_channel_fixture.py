# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

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

CURRENT_PATH = os.path.dirname(__file__)
print(f"Current Path: {CURRENT_PATH}")

client = boto3.client('medialive')
cloudformation_client = boto3.client('cloudformation')



def get_channel_info(source:str):
    response = client.list_channels(
        MaxResults=100
    )
    return [channel['Id'] for channel in response['Channels'] if str(channel['Name']).startswith('MRE_TESTSUITE' if source == "ML" else "MRE_BYOB_TESTSUITE") ]

# This fixture lets us run tests in parallel while retrieving the list of MediaLive Channels to be fetched only once per test session
# pytest-xdist provide workers and each worker recreates its own environment for tests. Any session fixtures by default will 
# run in each environment. To make sure the list of MediaLive Channels is fetched only once per test session,
# we need to use a session fixture with a workaround of using a Filelock to Synchronize multiple processes.
@pytest.fixture(scope="session")
def get_channel_ids(tmp_path_factory, worker_id, name="get_channel_info"):
                
    if not worker_id:
        # not executing in with multiple workers, just return the channel id list and let
        # pytest's fixture caching do its job
        return get_channel_info("ML")
    
    # get the temp directory shared by all workers
    root_tmp_dir = tmp_path_factory.getbasetemp().parent

    fn = root_tmp_dir / "channel_id_data.json"
    with FileLock(str(fn) + ".lock"):
        if fn.is_file():
            data = json.loads(fn.read_text())
        else:
            data = get_channel_info("ML")
            fn.write_text(json.dumps(data))
    return data


# This fixture lets us run tests in parallel while retrieving the list of MediaLive Channels for BYOB use cases to be fetched only once per test session
# pytest-xdist provide workers and each worker recreates its own environment for tests. Any session fixtures by default will 
# run in each environment. To make sure the list of MediaLive Channels is fetched only once per test session,
# we need to use a session fixture with a workaround of using a Filelock to Synchronize multiple processes.
@pytest.fixture(scope="session")
def get_byob_channel_ids(tmp_path_factory, worker_id, name="get_channel_info"):
                
    if not worker_id:
        # not executing in with multiple workers, just return the channel id list and let
        # pytest's fixture caching do its job
        return get_channel_info("BYOB")
    
    # get the temp directory shared by all workers
    root_tmp_dir = tmp_path_factory.getbasetemp().parent

    fn = root_tmp_dir / "byob_channel_ids_data.json"
    with FileLock(str(fn) + ".lock"):
        if fn.is_file():
            data = json.loads(fn.read_text())
        else:
            data = get_channel_info("BYOB")
            fn.write_text(json.dumps(data))
    return data

def get_byob_buckets():
    byob_bucket_names = []
    response = cloudformation_client.describe_stacks(StackName="aws-mre-test-suite")
    outputs = response["Stacks"][0]["Outputs"]
    for output in outputs:
        if output["OutputKey"].startswith("mreTestAutomationBYOB"):
            byob_bucket_names.append(output["OutputValue"])
    return byob_bucket_names


# This fixture lets us run tests in parallel while retrieving a list of BYOB buckets once per test session
# pytest-xdist provide workers and each worker recreates its own environment for tests. Any session fixtures by default will 
# run in each environment. To make sure the list of MediaLive Channels is fetched only once per test session,
# we need to use a session fixture with a workaround of using a Filelock to Synchronize multiple processes.
@pytest.fixture(scope="session")
def get_byob_bucket_names(tmp_path_factory, worker_id, name="get_byob_buckets"):
                
    if not worker_id:
        # not executing in with multiple workers, just return the channel id list and let
        # pytest's fixture caching do its job
        return get_byob_buckets()
    
    # get the temp directory shared by all workers
    root_tmp_dir = tmp_path_factory.getbasetemp().parent

    fn = root_tmp_dir / "byob_bucket_names_data.json"
    with FileLock(str(fn) + ".lock"):
        if fn.is_file():
            data = json.loads(fn.read_text())
        else:
            data = get_byob_buckets()
            fn.write_text(json.dumps(data))
    return data