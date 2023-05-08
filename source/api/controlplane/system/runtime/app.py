#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import boto3
from chalice import Chalice
from chalice import IAMAuthorizer
from chalice import ChaliceViewError
import uuid
import urllib.parse
import json
from decimal import Decimal
from jsonschema import validate, ValidationError, FormatChecker
from chalice import ChaliceViewError, BadRequestError, ConflictError, NotFoundError
from chalicelib import DecimalEncoder
from chalicelib import load_api_schema, replace_decimals
    

app = Chalice(app_name='aws-mre-controlplane-system-api')

API_VERSION = '1.0.0'
authorizer = IAMAuthorizer()

ddb_resource = boto3.resource("dynamodb")
medialive_client = boto3.client("medialive")
mediatailor_client = boto3.client("mediatailor")
s3_client = boto3.client("s3")

FRAMEWORK_VERSION = os.environ['FRAMEWORK_VERSION']
SYSTEM_TABLE_NAME = os.environ['SYSTEM_TABLE_NAME']
REGION = os.getenv("AWS_REGION")

API_SCHEMA = load_api_schema()

@app.route('/system/version', cors=True, methods=['GET'], authorizer=authorizer)
def version():
    """
    Get the control plane api and framework version numbers

    Returns:

    .. code-block:: python
        
        {
            "api_version": "x.x.x",
            "framework_version": "x.x.x"
        }
    """
    return {
        "api_version": API_VERSION,
        "framework_version": FRAMEWORK_VERSION
    }


@app.route('/system/uuid', cors=True, methods=['GET'], authorizer=authorizer)
def generate_uuid():
    """
    Generate a random UUID string using the Python 'uuid' module

    Returns:

    .. code-block:: python

        UUID
    """
    return str(uuid.uuid4())


@app.route('/system/medialive/channels', cors=True, methods=['GET'], authorizer=authorizer)
def list_medialive_channels():
    """
    Get all Media Live Channels

    Returns:

        A list of Media Live Channels

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        print("Listing all the MediaLive channels")

        response = medialive_client.list_channels()

        channels = response["Channels"]

        while "NextToken" in response:
            response = medialive_client.list_channels(
                NextToken=response["NextToken"]
            )

            channels.extend(response["Channels"])

    except Exception as e:
        print(f"Unable to list all the MediaLive channels: {str(e)}")
        raise ChaliceViewError(f"Unable to list all the MediaLive channels: {str(e)}")

    else:
        return [
            {
                "Id": channel["Id"],
                "Name": channel["Name"]
            }
            for channel in channels
        ]


@app.route('/system/mediatailor/channels', cors=True, methods=['GET'], authorizer=authorizer)
def list_mediatailor_channels():
    """
    Get all Media Tailor Channels

    Returns:

        A list of Media Tailor Channels

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        print("Listing all the MediaTailor channels")

        response = mediatailor_client.list_channels()

        channels = response["Items"]

        while "NextToken" in response:
            response = mediatailor_client.list_channels(
                NextToken=response["NextToken"]
            )

            channels.extend(response["Items"])

    except Exception as e:
        print(f"Unable to list all the MediaTailor channels: {str(e)}")
        raise ChaliceViewError(f"Unable to list all the MediaTailor channels: {str(e)}")

    else:
        return [channel["ChannelName"] for channel in channels]


@app.route('/system/mediatailor/playbackconfigurations', cors=True, methods=['GET'], authorizer=authorizer)
def list_mediatailor_playback_configurations():
    """
    Get all Media Tailor Playback Configurations

    Returns:

        A list of Media Tailor Playback Configurations

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        print("Listing all the MediaTailor Playback Configurations")

        response = mediatailor_client.list_playback_configurations()

        configs = response["Items"]

        while "NextToken" in response:
            response = mediatailor_client.list_playback_configurations(
                NextToken=response["NextToken"]
            )

            configs.extend(response["Items"])

    except Exception as e:
        print(f"Unable to list all the MediaTailor Playback Configurations: {str(e)}")
        raise ChaliceViewError(f"Unable to list all the MediaTailor Playback Configurations: {str(e)}")

    else:
        return [config["Name"] for config in configs]


@app.route('/system/configuration', cors=True, methods=['PUT'], authorizer=authorizer)
def put_system_configuration():
    """
    Upsert a system configuration parameter

    Body:

    .. code-block:: python

        {
            "Name": "ParameterName",
            "Value": "ParameterValue"
        }

        MRE system parameters:

        - MaxConcurrentWorkflows
            The maximum number of replay generation workflows allowed to run concurrently. 
            Once MaxConcurrentWorkflows is reached, any new workflow added is held in a 
            queue until existing workflows complete. This configuration parameter helps 
            avoid throttling in AWS service API calls.

        - ReplayClipsRetentionPeriod
            The maximum number of days to retain the replay clips (generated by the MRE 
            workflows) and their related metadata. Clips past the retention period are 
            purged from the system.

    Returns:

        None

    Raises:
        400 - BadRequestError
        500 - ChaliceViewError
    """
    try:
        config = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=config, schema=API_SCHEMA["put_system_configuration"])

        print("Got a valid system configuration schema")

        print(f"Upserting the system configuration parameter: {config}")

        if config["Name"] in ["MaxConcurrentWorkflows", "ReplayClipsRetentionPeriod"]:
            if int(config["Value"]) < 1:
                raise BadRequestError(f"{config['Name']} must have a value greater than 0")

        system_table = ddb_resource.Table(SYSTEM_TABLE_NAME)

        system_table.put_item(Item=config)

    except BadRequestError as e:
        print(f"Got chalice BadRequestError: {str(e)}")
        raise

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except Exception as e:
        print(f"Unable to upsert the system configuration parameter: {str(e)}")
        raise ChaliceViewError(f"Unable to upsert the system configuration parameter: {str(e)}")

    else:
        return {}


@app.route('/system/configuration/{name}', cors=True, methods=['GET'], authorizer=authorizer)
def get_system_configuration(name):
    """
    Get a system configuration parameter value by name

    Returns:

        Value of the system configuration parameter

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)

        print(f"Getting the value of the system configuration parameter '{name}'")

        system_table = ddb_resource.Table(SYSTEM_TABLE_NAME)

        response = system_table.get_item(
            Key={
                "Name": name
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"System configuration parameter '{name}' not found")

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to get the value of the system configuration parameter '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to get the value of the system configuration parameter '{name}': {str(e)}")

    else:
        return replace_decimals(response["Item"]["Value"])


@app.route('/system/configuration/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_system_configurations():
    """
    List all the system configuration parameters

    Returns:

        .. code-block:: python

            [
                {
                    "ParameterName": "ParameterValue"
                },
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        print("Listing all the system configuration parameters")

        system_table = ddb_resource.Table(SYSTEM_TABLE_NAME)

        response = system_table.scan(
            ConsistentRead=True
        )

        configs = response["Items"]

        while "LastEvaluatedKey" in response:
            response = system_table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                ConsistentRead=True
            )

            configs.extend(response["Items"])

    except Exception as e:
        print(f"Unable to list the system configuration parameters: {str(e)}")
        raise ChaliceViewError(f"Unable to list the system configuration parameters: {str(e)}")

    else:
        return replace_decimals(configs)

@app.route('/system/s3/buckets', cors=True, methods=['GET'], authorizer=authorizer)
def list_s3_buckets():
    """
    Get all S3 Buckets in region

    Returns:

        A list of S3 Buckets in deployed region

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        print("Listing all the S3 buckets")

        response = s3_client.list_buckets()
        buckets = response["Buckets"]
        return [
            bucket["Name"]
            # Only get the buckets from your region
            # null location constraint means its us-east-1
            for bucket in buckets if (s3_client.get_bucket_location(Bucket=bucket["Name"]).get("LocationConstraint") or "us-east-1") == REGION
        ]

    except Exception as e:
        print(f"Unable to list all the S3 buckets: {str(e)}")
        raise ChaliceViewError(f"Unable to list all the S3 buckets: {str(e)}")