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

def test_model_creation_deletion_and_get_with_valid_end_point():
    config = load_config(f"{CURRENT_PATH}/config/valid_end_point.json")
    response = call_api(path="model", api_method="POST", api_body=json.dumps(config))
    assert response.status_code == 200

    # Get this Model 
    response = call_api(path="model/TestSuite-ValidEndpointModel", api_method="GET")
    assert response.status_code == 200
    model= response.json()
    assert model['Name'] == config['Name']
    assert model['Description'] == config['Description']
    assert model['PluginClass'] == config['PluginClass']
    assert model['Endpoint'] == config['Endpoint']
    assert model['ContentGroups'][0] == config['ContentGroups'][0]

    # Delete the Model
    call_api(path="model/TestSuite-ValidEndpointModel", api_method="DELETE")

    # Get this Model 
    with pytest.raises(NotFoundError):
        response = call_api(path="model/TestSuite-ValidEndpointModel", api_method="GET")
    

def test_model_creation_with_invalid_endpoint():
    config = load_config(f"{CURRENT_PATH}/config/invalid_end_point.json")
    with pytest.raises(ChaliceViewError):
        call_api(path="model", api_method="POST", api_body=config)
        
    
def test_model_creation_with_no_endpoint():
    config = load_config(f"{CURRENT_PATH}/config/no_end_point.json")
    with pytest.raises(ChaliceViewError):
        call_api(path="model", api_method="POST", api_body=config)  
    
    
def test_model_creation_with_invalid_plugin_class():
    config = load_config(f"{CURRENT_PATH}/config/invalid_plugin_class.json")
    with pytest.raises(ChaliceViewError):
        call_api(path="model", api_method="POST", api_body=config)  


def test_latest_version_model_deletion_when_multiple_versions_exist():

    # Create new Model
    config = load_config(f"{CURRENT_PATH}/config/valid_end_point.json")
    config['Name'] = 'TestSuite-ValidEndpointModel1'

    response = call_api(path="model", api_method="POST", api_body=json.dumps(config))
    assert response.status_code == 200

    # Create new version of the model
    response = call_api(path="model", api_method="POST", api_body=json.dumps(config))
    assert response.status_code == 200

    # Delete the latest version of  this Model 
    with pytest.raises(ChaliceViewError):
        call_api(path="model/TestSuite-ValidEndpointModel1/version/V2", api_method="DELETE")
    
    # Delete the whole Model
    call_api(path="model/TestSuite-ValidEndpointModel1", api_method="DELETE")

    # Get this Model 
    with pytest.raises(NotFoundError):
        response = call_api(path="model/TestSuite-ValidEndpointModel", api_method="GET")


def test_older_version_model_deletion_when_multiple_versions_exist():

    # Create new Model
    config = load_config(f"{CURRENT_PATH}/config/valid_end_point.json")
    config['Name'] = 'TestSuite-ValidEndpointModel2'

    # Create new version of the model - v1
    response = call_api(path="model", api_method="POST", api_body=json.dumps(config))
    assert response.status_code == 200

    # Create new version of the model - v2
    response = call_api(path="model", api_method="POST", api_body=json.dumps(config))
    assert response.status_code == 200

    # Delete the Oldest version of this Model - v1
    call_api(path="model/TestSuite-ValidEndpointModel2/version/v1", api_method="DELETE")

    # Verify if v1 version is deleted
    with pytest.raises(NotFoundError):
        call_api(path="model/TestSuite-ValidEndpointModel2/version/v1", api_method="GET")


    # Verify that V2 version exists
    res = call_api(path="model/TestSuite-ValidEndpointModel2/version/v2", api_method="GET")
    assert res.status_code == 200
    model= res.json()
    assert model['Version'] == 'v2'
    
    # Delete the whole Model
    call_api(path="model/TestSuite-ValidEndpointModel2", api_method="DELETE")

    # Check if the Whole Model is deleted
    with pytest.raises(NotFoundError):
        call_api(path="model/TestSuite-ValidEndpointModel2", api_method="GET")
    




