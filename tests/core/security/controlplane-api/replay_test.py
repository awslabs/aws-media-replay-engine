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
    # Invalid payload with wrong data types
    payload = {
        "Program": 123,  # Should be string
        "Event": ["invalid"],
        "AudioTrack": 1,
        "Description": True,
        "DurationbasedSummarization": {
            "Duration": "300",  # Should be number
            "FillToExact": "true",
            "ToleranceMaxLimitInSecs": "30",
        },
    }

    with pytest.raises(BadRequestError) as excinfo:
        response = call_api(
            path="replay", api_method="POST", api_body=json.dumps(payload)
        )
        assert response.status_code == 400


def test_missing_required_fields():
    # Payload missing required fields
    payload = {
        "Program": "Sports",
        # Missing "Event"
        # Missing "AudioTrack"
        "Description": "Test replay",
        "Requester": "TestUser"
        # Missing other required fields
    }

    with pytest.raises(BadRequestError) as excinfo:
        response = call_api(
            path="replay", api_method="POST", api_body=json.dumps(payload)
        )
        assert response.status_code == 400


def test_malformed_json():
    # Malformed JSON string
    invalid_json = """{
        "Program": "Sports",
        "Event": "Game1"
        "AudioTrack": "en" # Missing comma
        "Description": "Test replay"
    }"""

    with pytest.raises(ChaliceViewError) as excinfo:
        response = call_api(path="replay", api_method="POST", api_body=invalid_json)
        assert response.status_code == 500


def test_api_call_with_expired_creds():
    # Valid payload structure but with expired credentials
    payload = {
        "Program": "Sports",
        "Event": "Game1",
        "AudioTrack": "en",
        "Description": "Test replay",
        "Requester": "TestUser",
        "DurationbasedSummarization": {
            "Duration": 300,
            "FillToExact": True,
            "EqualDistribution": True,
            "ToleranceMaxLimitInSecs": 30,
        },
        "CreateHls": True,
        "CreateMp4": True,
        "Resolutions": ["16:9 (1920 x 1080)"],
    }

    with pytest.raises(requests.exceptions.HTTPError) as excinfo:
        response = call_api(
            path="replay",
            api_method="POST",
            api_body=json.dumps(payload),
            valid_auth=False,
        )
        assert response.status_code == 403


def test_oversized_payload_rejection():
    # Creating an oversized payload
    large_payload = {
        "Program": "Sports",
        "Event": "Game1",
        "AudioTrack": "en",
        "Description": "Test replay",
        "Requester": "TestUser",
        "SpecifiedTimestamps": "x" * 11000000,  # Creating oversized content
        "Priorities": {
            "Clips": [
                {
                    "Name": "Clip1",
                    "Weight": 1,
                    "Include": True,
                    "Duration": "300",
                    "StartTime": 0,
                    "EndTime": 300,
                }
            ]
        },
    }

    with pytest.raises(requests.exceptions.HTTPError) as excinfo:
        response = call_api(
            path="replay",
            api_method="POST",
            api_body=json.dumps(large_payload),
            valid_auth=False,
        )
        assert response.status_code == 413
