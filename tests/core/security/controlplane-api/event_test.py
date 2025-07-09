# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import logging
import os

import boto3
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
    payload = {
        "Name": "Football Match Highlights",
        "Program": "Sports Coverage",
        "Description": "Premier League match highlights",
        "Channel": "sports-channel-1",
        "ProgramId": "SP123",
        "SourceVideoAuth": {"apiKey": "abc123"},
        "SourceVideoMetadata": {"resolution": "1080p", "format": "MP4"},
        "BootstrapTimeInMinutes": "15",
        "Profile": "sports-profile",
        "ContentGroup": "football-matches",
        "Start": "2024-01-20T14:00:00Z",
        "DurationMinutes": 120,
        "Archive": True,
        "GenerateOrigClips": True,
        "GenerateOptoClips": True,
        "GenerateOrigThumbNails": True,
        "GenerateOptoThumbNails": False,
        "TimecodeSource": "UTC_BASED",
        "Variables": {"League": "Premier", "Season": "2023-24"},
    }

    with pytest.raises(BadRequestError) as excinfo:
        response = call_api(
            path="event", api_method="POST", api_body=json.dumps(payload)
        )
        assert response.status_code == 400

    # Verify the error message
    assert "'15' is not of type 'integer'" in str(excinfo.value)


# Test missing required fields
def test_missing_required_fields():
    payload = {
        "Program": "Sports Coverage",
        "Description": "Premier League match highlights",
        "Channel": "sports-channel-1",
        "ProgramId": "SP123",
        "SourceVideoAuth": {"apiKey": "abc123"},
        "SourceVideoMetadata": {"resolution": "1080p", "format": "MP4"},
        "BootstrapTimeInMinutes": 15,
        "Profile": "sports-profile",
        "ContentGroup": "football-matches",
        "Start": "2024-01-20T14:00:00Z",
        "DurationMinutes": 120,
        "Archive": True,
        "GenerateOrigClips": True,
        "GenerateOptoClips": True,
        "GenerateOrigThumbNails": True,
        "GenerateOptoThumbNails": False,
        "TimecodeSource": "UTC_BASED",
        "Variables": {"League": "Premier", "Season": "2023-24"},
    }
    with pytest.raises(BadRequestError) as excinfo:
        response = call_api(
            path="event", api_method="POST", api_body=json.dumps(payload)
        )
        assert response.status_code == 400

    # Verify the error message
    assert "'Name' is a required property" in str(excinfo.value)


# Test malformed JSON
def test_malformed_json():
    invalid_json = """{
        "Program": 'Sports Coverage',   # Mixed quote types
        "SourceVideoAuth": {
            apiKey: abc123              # Missing quotes
        }
        "Variables": {                  # Missing comma
            "League": "Premier",,       # Double comma
            "Season": "2023-24"
        }
    }"""
    with pytest.raises(ChaliceViewError) as excinfo:
        response = call_api(path="event", api_method="POST", api_body=invalid_json)
        assert response.status_code == 500

    # Verify the error message
    assert "An internal server error occurred" in str(excinfo.value)


# Test API calls with expired IAM credentials
def test_api_call_with_expired_creds():
    payload = {
        "Name": "Football Match Highlights",
        "Program": "Sports Coverage",
        "Description": "Premier League match highlights",
        "Channel": "sports-channel-1",
        "ProgramId": "SP123",
        "SourceVideoAuth": {"apiKey": "abc123"},
        "SourceVideoMetadata": {"resolution": "1080p", "format": "MP4"},
        "BootstrapTimeInMinutes": 15,
        "Profile": "sports-profile",
        "ContentGroup": "football-matches",
        "Start": "2024-01-20T14:00:00Z",
        "DurationMinutes": 120,
        "Archive": True,
        "GenerateOrigClips": True,
        "GenerateOptoClips": True,
        "GenerateOrigThumbNails": True,
        "GenerateOptoThumbNails": False,
        "TimecodeSource": "UTC_BASED",
        "Variables": {"League": "Premier", "Season": "2023-24"},
    }

    with pytest.raises(requests.exceptions.HTTPError) as excinfo:
        response = call_api(
            path="event",
            api_method="POST",
            api_body=json.dumps(payload),
            valid_auth=False,
        )
        assert response.status_code == 403


# TODO: Change the payload size to match API threshold - check WAF Rule
def test_oversized_payload_rejection():
    # Create a payload that exceeds 10MB (10485760 bytes)
    large_data = {"data": "x" * 11000000}  # Slightly over 10MB of data

    with pytest.raises(requests.exceptions.HTTPError) as excinfo:
        response = call_api(
            path="event",
            api_method="POST",
            api_body=json.dumps(large_data),
            valid_auth=False,
        )
        assert response.status_code == 413
