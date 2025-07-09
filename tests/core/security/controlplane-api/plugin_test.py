# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import logging
import os

import pytest
import requests
from chalice import ChaliceViewError, BadRequestError
from utils.api_client import call_api

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logger = logging.getLogger()

CURRENT_PATH = os.path.dirname(__file__)
print(f"Current Path: {CURRENT_PATH}")


# Test invalid data types:
def test_invalid_data_types():
    """
    Test registering a plugin with invalid data types for various fields.
    For example, providing an integer where a string is expected.
    """
    payload = {
        "Name": 123,  # Should be a string
        "Description": True,
        "Class": "InvalidClass",  # Should be one of the allowed classes
        "ExecutionType": "Async",
        "SupportedMediaType": "Text",  # Should be either "Video" or "Audio"
        "ContentGroups": "NotAList",  # Should be a list
        "ExecuteLambdaQualifiedARN": 456,  # Should be a string ARN
        "ModelEndpoints": "NotAList",
        "Configuration": "NotADict",
        "OutputAttributes": "NotADict",
        "DependentPlugins": "NotAList",
    }

    with pytest.raises(BadRequestError) as excinfo:
        response = call_api(
            path="plugin", api_method="POST", api_body=json.dumps(payload)
        )
        assert response.status_code == 400

    # Verify the error message contains type errors
    error_message = str(excinfo.value)
    assert "is not of type" in error_message


def test_missing_required_fields():
    """
    Test registering a plugin with missing required fields.
    For example, omitting the 'Name' and 'ExecutionType' fields.
    """
    payload = {
        # "Name": "ExamplePlugin",  # Missing
        "Description": "A plugin without a name.",
        "Class": "Classifier",
        "ExecutionType": "Sync",
        "SupportedMediaType": "Video",
        "ContentGroups": ["Group1", "Group2"],
        "ExecuteLambdaQualifiedARN": "arn:aws:lambda:us-east-1:123456789012:function:ExampleFunction",
        # "ModelEndpoints": [],  # Required if ExecutionType is "SyncModel"
        "Configuration": {"setting1": "value1"},
        "OutputAttributes": {"attribute1": {"Description": "An output attribute."}},
        "DependentPlugins": ["DepPlugin1"],
    }

    with pytest.raises(BadRequestError) as excinfo:
        response = call_api(
            path="plugin", api_method="POST", api_body=json.dumps(payload)
        )
        assert response.status_code == 400

    # Verify the error message mentions missing 'Name'
    error_message = str(excinfo.value)
    assert "'Name' is a required property" in error_message


def test_malformed_json():
    """
    Test registering a plugin with malformed JSON.
    """
    invalid_json = """{
        "Name": "MalformedPlugin",
        "Description": "This JSON is not properly closed."
        "Class": "Optimizer",
    """  # Missing closing braces and commas

    with pytest.raises(ChaliceViewError) as excinfo:
        response = call_api(path="plugin", api_method="POST", api_body=invalid_json)
        assert response.status_code == 500

    # Verify the error message
    error_message = str(excinfo.value)
    assert "An internal server error occurred" in error_message


def test_api_call_with_expired_creds():
    """
    Test registering a plugin with expired IAM credentials.
    This should result in a 403 Forbidden error.
    """
    payload = {
        "Name": "ValidPlugin",
        "Description": "A plugin with expired credentials.",
        "Class": "Featurer",
        "ExecutionType": "Sync",
        "SupportedMediaType": "Audio",
        "ContentGroups": ["AudioGroup1"],
        "ExecuteLambdaQualifiedARN": "arn:aws:lambda:us-east-1:123456789012:function:ValidFunction",
        "Configuration": {"setting1": "value1"},
        "OutputAttributes": {"attribute1": {"Description": "An output attribute."}},
        "DependentPlugins": [],
    }

    with pytest.raises(requests.exceptions.HTTPError) as excinfo:
        response = call_api(
            path="plugin",
            api_method="POST",
            api_body=json.dumps(payload),
            valid_auth=False,
        )
        assert response.status_code == 403

    # Verify the error message mentions forbidden access
    error_message = str(excinfo.value)
    assert "Forbidden" in error_message or "403" in error_message


# TODO: Change the payload size to match API threshold - check WAF Rule
def test_oversized_payload_rejection():
    """
    Test registering a plugin with an oversized payload to trigger WAF rules.
    The payload size exceeds the 10MB limit.
    """
    # Create a payload that exceeds 10MB (10485760 bytes)
    large_content_groups = [
        f"Group{i}" for i in range(1000000)
    ]  # Adjust the number to exceed the limit
    large_data = {
        "Name": "OversizedPlugin",
        "Description": "A plugin with an oversized payload.",
        "Class": "Labeler",
        "ExecutionType": "Sync",
        "SupportedMediaType": "Video",
        "ContentGroups": large_content_groups,  # This list should make the payload exceed 10MB
        "ExecuteLambdaQualifiedARN": "arn:aws:lambda:us-east-1:123456789012:function:OversizedFunction",
        "Configuration": {"setting1": "value1"},
        "OutputAttributes": {"attribute1": {"Description": "An output attribute."}},
        "DependentPlugins": [],
    }

    with pytest.raises(requests.exceptions.HTTPError) as excinfo:
        response = call_api(
            path="plugin",
            api_method="POST",
            api_body=json.dumps(large_data),
            valid_auth=True,  # Assuming valid credentials
        )
        assert response.status_code == 413

    # Verify the error message mentions payload too large
    error_message = str(excinfo.value)
    assert "Payload Too Large" in error_message or "413" in error_message
