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
    Test registering a model with invalid data types for various fields.
    For example, providing an integer where a string is expected.
    """
    payload = {
        "Name": 123,  # Should be a string
        "Description": True,
        "ContentGroups": "NotAList",
        "Endpoint": 456,  # Should be a string ARN
        "PluginClass": "InvalidClass"
    }

    with pytest.raises(BadRequestError) as excinfo:
        response = call_api(
            path="model", api_method="POST", api_body=json.dumps(payload)
        )
        assert response.status_code == 400

    # Verify the error message contains type errors
    error_message = str(excinfo.value)
    assert "is not of type" in error_message


def test_missing_required_fields():
    """
    Test registering a model with missing required fields.
    For example, omitting the 'Name' and 'Endpoint' fields.
    """
    payload = {
        # "Name": "ExampleModel", # Missing
        "Description": "A model without a name.",
        "ContentGroups": ["Group1", "Group2"],
        "Endpoint": "arn:aws:sagemaker:us-east-1:123456789012:endpoint/ExampleEndpoint",
        "PluginClass": "Classifier"
    }

    with pytest.raises(BadRequestError) as excinfo:
        response = call_api(
            path="model", api_method="POST", api_body=json.dumps(payload)
        )
        assert response.status_code == 400

    # Verify the error message mentions missing 'Name'
    error_message = str(excinfo.value)
    assert "'Name' is a required property" in error_message


def test_malformed_json():
    """
    Test registering a model with malformed JSON.
    """
    invalid_json = """{
        "Name": "MalformedModel",
        "Description": "This JSON is not properly closed."
        "ContentGroups": ["Group1", "Group2"],
    """  # Missing closing braces and commas

    with pytest.raises(ChaliceViewError) as excinfo:
        response = call_api(path="model", api_method="POST", api_body=invalid_json)
        assert response.status_code == 500

    # Verify the error message
    error_message = str(excinfo.value)
    assert "Unable to register or publish a new version of the Machine Learning model endpoint: " in error_message


# Test API calls with expired IAM credentials
def test_api_call_with_expired_creds():
    """
    Test registering a model with expired IAM credentials.
    This should result in a 403 Forbidden error.
    """
    payload = {
        "Name": "ValidModel",
        "Description": "A model with expired credentials.",
        "ContentGroups": ["Group1"],
        "Endpoint": "arn:aws:sagemaker:us-east-1:123456789012:endpoint:ValidEndpoint",
        "PluginClass": "Optimizer"
    }

    with pytest.raises(requests.exceptions.HTTPError) as excinfo:
        response = call_api(
            path="model",
            api_method="POST",
            api_body=json.dumps(payload),
            valid_auth=False  # Simulate expired credentials
        )
        assert response.status_code == 403

    # Verify the error message mentions forbidden access
    error_message = str(excinfo.value)
    assert "Forbidden" in error_message or "403" in error_message


# TODO: Change the payload size to match API threshold - check WAF Rule
def test_oversized_payload_rejection():
    """
    Test registering a model with an oversized payload to trigger WAF rules.
    The payload size exceeds the 10MB limit.
    """
    # Create a payload that exceeds 10MB (10485760 bytes)
    large_content_groups = [f"Group{i}" for i in range(2000000)]  # Adjust the number to exceed the limit
    large_data = {
        "Name": "OversizedModel",
        "Description": "A model with an oversized payload.",
        "ContentGroups": large_content_groups,  # This list should make the payload exceed 10MB
        "Endpoint": "arn:aws:sagemaker:us-east-1:123456789012:endpoint:OversizedEndpoint",
        "PluginClass": "Labeler"
    }

    with pytest.raises(requests.exceptions.HTTPError) as excinfo:
        response = call_api(
            path="model",
            api_method="POST",
            api_body=json.dumps(large_data),
            valid_auth=True  # Assuming valid credentials
        )
        assert response.status_code == 413

    # Verify the error message mentions payload too large
    error_message = str(excinfo.value)
    assert "Payload Too Large" in error_message or "413" in error_message
