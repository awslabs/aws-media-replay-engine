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

medialive_client = boto3.client("medialive")


# Test invalid data types:
def test_invalid_data_types():
    payload = {
        "Name": "TestProfile",
        "Description": "Test Profile Description",
        "ContentGroups": ["Group1", "Group2"],
        "ChunkSize": "120",  # Invalid: should be a number
        "MaxSegmentLengthSeconds": 300,
        "ProcessingFrameRate": 30,
        "Classifier": {
            "Name": "TestClassifier",
            "ModelEndpoint": {"Name": "ClassifierEndpoint", "Version": "1.0"},
            "Configuration": {"threshold": "0.8"},
            "DependentPlugins": [],
        },
        "Optimizer": {
            "Name": "TestOptimizer",
            "ModelEndpoint": {"Name": "OptimizerEndpoint", "Version": "1.0"},
            "Configuration": {"parameter1": "value1"},
            "DependentPlugins": [],
        },
        "Labeler": {
            "Name": "TestLabeler",
            "ModelEndpoint": {"Name": "LabelerEndpoint", "Version": "1.0"},
            "Configuration": {"setting1": "value1"},
            "DependentPlugins": [],
        },
        "Featurers": [
            {
                "Name": "TestFeaturer",
                "ModelEndpoint": {"Name": "FeaturerEndpoint", "Version": "1.0"},
                "Configuration": {"param1": "value1"},
                "IsPriorityForReplay": True,
                "DependentPlugins": [],
            }
        ],
        "Variables": {"key1": "value1"},
    }

    with pytest.raises(BadRequestError) as excinfo:
        response = call_api(
            path="profile", api_method="POST", api_body=json.dumps(payload)
        )
        assert response.status_code == 400

    # Verify the error message
    assert "'120' is not of type 'integer'" in str(excinfo.value)


def test_missing_required_fields():
    payload = {
        # "Name": "VideoProcessingProfile1", # This required field is missing
        "Description": "Profile for processing sports videos with classification and feature extraction.",
        "ContentGroups": ["Sports", "Highlights"],
        "ChunkSize": 300,
        "MaxSegmentLengthSeconds": 60,
        "ProcessingFrameRate": 30,
        "Classifier": {
            "Name": "SportsClassifier",
            "ModelEndpoint": {"Name": "SportsModelEndpoint", "Version": "v1.2"},
            "Configuration": {"threshold": "0.75", "mode": "fast"},
            "DependentPlugins": [],
        },
        "Featurers": [
            {
                "Name": "MotionFeaturer",
                "ModelEndpoint": {"Name": "MotionFeatureEndpoint", "Version": "v1.1"},
                "Configuration": {"sensitivity": "high"},
                "IsPriorityForReplay": True,
                "DependentPlugins": [],
            }
        ],
        "Variables": {"resolution": "1080p", "language": "en-US"},
    }

    with pytest.raises(BadRequestError) as excinfo:
        response = call_api(
            path="event", api_method="POST", api_body=json.dumps(payload)
        )
        assert response.status_code == 400

    # Verify the error message
    assert "'Name' is a required property" in str(excinfo.value)


def test_malformed_json():
    invalid_json = """{
          "Name": "VideoProcessingProfile1",
          "Description": "Profile for processing sports videos with classification and feature extraction."
          "ContentGroups": ["Sports", "Highlights"],  // Missing comma after the Description field
          "ChunkSize": 300,
          "MaxSegmentLengthSeconds": 60,
          "ProcessingFrameRate": 30,
          "Classifier": {
            "Name": "SportsClassifier",
            "ModelEndpoint": {
              "Name": "SportsModelEndpoint",
              "Version": "v1.2"
            },
            "Configuration": {
              "threshold": "0.75",
              "mode": "fast",
            },  // Trailing comma after the "mode" field
            "DependentPlugins": [
              {
                "Name": "PreProcessor",
                "ModelEndpoint": {
                  "Name": "PreProcessingEndpoint",
                  "Version": "v3.1"
                },
                "Configuration": {
                  "resize": "1920x1080",
                  "format": "mp4"
                },
                "DependentFor": ["SportsClassifier"]
              }
            ]
          },
          "Optimizer": {
            "Name": "VideoOptimizer",
            "ModelEndpoint": {
              "Name": "OptimizerEndpoint",
              "Version": "v2.0"
            },
            "Configuration": {
              "bitrate": "4500k",
              "codec": "H.264"
            },
            "DependentPlugins": []
          },
          "Labeler": {
            "Name": "SceneLabeler",
            "ModelEndpoint": {
              "Name": "LabelerEndpoint",
              "Version": "v1.0"
            },
            "Configuration": {
              "labelTypes": ["scene", "action"]
            },
            "DependentPlugins": []
          },
          "Featurers": [
            {
              "Name": "MotionFeaturer",
              "ModelEndpoint": {
                "Name": "MotionFeatureEndpoint",
                "Version": "v1.1"
              },
              "Configuration": {
                "sensitivity": "high"
              },
              "IsPriorityForReplay": true,
              "DependentPlugins": []
            },
            {
              "Name": "AudioFeaturer",
              "ModelEndpoint": {
                "Name": "AudioFeatureEndpoint",
                "Version": "v1.0"
              },
              "Configuration": {
                "sampleRate": "44100Hz"
              },
              "IsPriorityForReplay": false,
              "DependentPlugins": []
            }
          ],
          "Variables": {
            "resolution": "1080p",
            "language": "en-US"
          }
        }  // Extra closing brace or missing elements can also cause errors
        """
    with pytest.raises(ChaliceViewError) as excinfo:
        response = call_api(path="event", api_method="POST", api_body=invalid_json)
        assert response.status_code == 500

    # Verify the error message
    assert "An internal server error occurred" in str(excinfo.value)


# Test API calls with expired IAM credentials
def test_api_call_with_expired_creds():
    payload = {
        "Name": "TestProfile",
        "Description": "Test Profile Description",
        "ContentGroups": ["Group1", "Group2"],
        "ChunkSize": "120",  # Invalid: should be a number
        "MaxSegmentLengthSeconds": 300,
        "ProcessingFrameRate": 30,
        "Classifier": {
            "Name": "TestClassifier",
            "ModelEndpoint": {"Name": "ClassifierEndpoint", "Version": "1.0"},
            "Configuration": {"threshold": "0.8"},
            "DependentPlugins": [],
        },
        "Optimizer": {
            "Name": "TestOptimizer",
            "ModelEndpoint": {"Name": "OptimizerEndpoint", "Version": "1.0"},
            "Configuration": {"parameter1": "value1"},
            "DependentPlugins": [],
        },
        "Labeler": {
            "Name": "TestLabeler",
            "ModelEndpoint": {"Name": "LabelerEndpoint", "Version": "1.0"},
            "Configuration": {"setting1": "value1"},
            "DependentPlugins": [],
        },
        "Featurers": [
            {
                "Name": "TestFeaturer",
                "ModelEndpoint": {"Name": "FeaturerEndpoint", "Version": "1.0"},
                "Configuration": {"param1": "value1"},
                "IsPriorityForReplay": True,
                "DependentPlugins": [],
            }
        ],
        "Variables": {"key1": "value1"},
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
