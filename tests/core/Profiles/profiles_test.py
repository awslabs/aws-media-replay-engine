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


def register_plugin(plugin_name):
    config = load_config(f"{CURRENT_PATH}/config/{plugin_name}.json")
    config["ExecuteLambdaQualifiedARN"] = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT_ID}:function:{plugin_name}:$LATEST"
    call_api(path="plugin", api_method="POST", api_body=json.dumps(config))

def register_DetectPassThrough100():
    register_plugin("DetectPassThrough100")

def register_LabelPassthrough():
    register_plugin("LabelPassthrough")
    
def register_SegmentPassThrough100():
    register_plugin("SegmentPassThrough100")
    
def register_OptimizePassThrough():
    register_plugin("OptimizePassThrough")

def register_required_plugins():
    register_DetectPassThrough100()
    register_LabelPassthrough()
    register_SegmentPassThrough100()
    register_OptimizePassThrough()
    
def test_profile_creation_load_deletion_featurer_dep_replay():

    register_required_plugins()

    config = load_config(f"{CURRENT_PATH}/config/PassThroughProfile.json")
    response = call_api(path="profile", api_method="POST", api_body=json.dumps(config))
    assert response.status_code == 200

    # Load this profile
    response = call_api(path="profile/TestSuite-ProfileTest-PassThroughPlugins", api_method="GET")
    assert response.status_code == 200
    
    # Delete the profile
    call_api(path="profile/TestSuite-ProfileTest-PassThroughPlugins", api_method="DELETE")

    # Get this Profile. Ensure that the Profile has been deleted
    with pytest.raises(NotFoundError):
        response = call_api(path="profile/TestSuite-ProfileTest-PassThroughPlugins", api_method="GET")

    assert_plugins_dont_exist_after_deletion()


def test_profile_creation_load_deletion_featurer_not_dep_replay():
    register_required_plugins()

    config = load_config(f"{CURRENT_PATH}/config/PassThroughProfile.json")

    # Ensure to change the profile name since the previous test method could have deleted the profile 
    # which is a time consuming operation(as it involves deletion of state machine)
    profile_name = f"{config['Name']}-1"

    config['Name'] = profile_name
    config['Featurers'][0]['IsPriorityForReplay'] = False
    response = call_api(path="profile", api_method="POST", api_body=json.dumps(config))
    assert response.status_code == 200

    # Load this profile
    response = call_api(path=f"profile/{profile_name}", api_method="GET")
    assert response.status_code == 200
    
    # Delete the profile
    call_api(path=f"profile/{profile_name}", api_method="DELETE")

    # Get this Profile. Ensure that the Profile has been deleted
    with pytest.raises(NotFoundError):
        response = call_api(path=f"profile/{profile_name}", api_method="GET")

    assert_plugins_dont_exist_after_deletion()



def test_profile_creation_failure_invalid_chunkSize():
    register_required_plugins()

    config = load_config(f"{CURRENT_PATH}/config/PassThroughProfile.json")

    # Ensure to change the profile name since the previous test method could have deleted the profile 
    # which is a time consuming operation(as it involves deletion of state machine)
    profile_name = f"{config['Name']}-2"
    
    config['Name'] = profile_name
    config['ChunkSize'] = -1

    with pytest.raises(NotFoundError):
        response = call_api(path=f"profile/{profile_name}", api_method="GET")

    assert_plugins_dont_exist_after_deletion()

def test_profile_creation_failure_invalid_MaxSegmentLengthSeconds():
    register_required_plugins()

    config = load_config(f"{CURRENT_PATH}/config/PassThroughProfile.json")

    # Ensure to change the profile name since the previous test method could have deleted the profile 
    # which is a time consuming operation(as it involves deletion of state machine)
    profile_name = f"{config['Name']}-3"
    
    config['Name'] = profile_name
    config['MaxSegmentLengthSeconds'] = -1

    with pytest.raises(NotFoundError):
        response = call_api(path=f"profile/{profile_name}", api_method="GET")

    assert_plugins_dont_exist_after_deletion()


def test_profile_creation_failure_invalid_ProcessingFrameRate():
    register_required_plugins()

    config = load_config(f"{CURRENT_PATH}/config/PassThroughProfile.json")

    # Ensure to change the profile name since the previous test method could have deleted the profile 
    # which is a time consuming operation(as it involves deletion of state machine)
    profile_name = f"{config['Name']}-4"
    
    config['Name'] = profile_name
    config['ProcessingFrameRate'] = -1

    with pytest.raises(NotFoundError):
        response = call_api(path=f"profile/{profile_name}", api_method="GET")

    assert_plugins_dont_exist_after_deletion()

def assert_plugins_dont_exist_after_deletion():
    # Delete the Plugins used
    call_api(path="plugin/TestSuite-ProfileTest-DetectPassThrough100", api_method="DELETE")
    with pytest.raises(NotFoundError):
        call_api(path="plugin/TestSuite-ProfileTest-DetectPassThrough100", api_method="GET")
    call_api(path="plugin/TestSuite-ProfileTest-LabelPassThrough", api_method="DELETE")
    with pytest.raises(NotFoundError):
        call_api(path="plugin/TestSuite-ProfileTest-LabelPassThrough", api_method="GET")
    call_api(path="plugin/TestSuite-ProfileTest-OptimizePassThrough", api_method="DELETE")
    with pytest.raises(NotFoundError):
        call_api(path="plugin/TestSuite-ProfileTest-OptimizePassThrough", api_method="GET")
    call_api(path="plugin/TestSuite-ProfileTest-SegmentPassThrough100", api_method="DELETE")
    with pytest.raises(NotFoundError):
        call_api(path="plugin/TestSuite-ProfileTest-SegmentPassThrough100", api_method="GET")