#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json
import os
import urllib.parse
import uuid
from decimal import Decimal

import boto3
from aws_lambda_powertools.utilities.validation import (SchemaValidationError,
                                                        validate)
from chalice import (BadRequestError, Chalice, ChaliceViewError, ConflictError,
                     IAMAuthorizer, NotFoundError)
from chalicelib import DecimalEncoder, load_api_schema, replace_decimals
from aws_lambda_powertools import Logger

app = Chalice(app_name='aws-mre-controlplane-system-api')
logger = Logger(service='aws-mre-controlplane-system-api')

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


# Create middleware to inject request context
@app.middleware('all')
def inject_request_context(event, get_response):
    # event is a Chalice Request object
    request_id = event.context.get('requestId', 'N/A')
    
    # Add request ID to persistent logger context
    logger.append_keys(request_id=request_id)
    
    response = get_response(event)
    return response


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
        logger.info("Listing all the MediaLive channels")

        response = medialive_client.list_channels()

        channels = response["Channels"]

        while "NextToken" in response:
            response = medialive_client.list_channels(
                NextToken=response["NextToken"]
            )

            channels.extend(response["Channels"])

    except Exception as e:
        logger.info(f"Unable to list all the MediaLive channels: {str(e)}")
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
        logger.info("Listing all the MediaTailor channels")

        response = mediatailor_client.list_channels()

        channels = response["Items"]

        while "NextToken" in response:
            response = mediatailor_client.list_channels(
                NextToken=response["NextToken"]
            )

            channels.extend(response["Items"])

    except Exception as e:
        logger.info(f"Unable to list all the MediaTailor channels: {str(e)}")
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
        logger.info("Listing all the MediaTailor Playback Configurations")

        response = mediatailor_client.list_playback_configurations()

        configs = response["Items"]

        while "NextToken" in response:
            response = mediatailor_client.list_playback_configurations(
                NextToken=response["NextToken"]
            )

            configs.extend(response["Items"])

    except Exception as e:
        logger.info(f"Unable to list all the MediaTailor Playback Configurations: {str(e)}")
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

        logger.info("Got a valid system configuration schema")

        logger.info(f"Upserting the system configuration parameter: {config}")

        if config["Name"] in ["MaxConcurrentWorkflows", "ReplayClipsRetentionPeriod"]:
            if int(config["Value"]) < 1:
                raise BadRequestError(f"{config['Name']} must have a value greater than 0")

        system_table = ddb_resource.Table(SYSTEM_TABLE_NAME)

        system_table.put_item(Item=config)

    except BadRequestError as e:
        logger.info(f"Got chalice BadRequestError: {str(e)}")
        raise

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")  

    except Exception as e:
        logger.info(f"Unable to upsert the system configuration parameter: {str(e)}")
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

        validate_path_parameters({"Name": name})

        logger.info(f"Getting the value of the system configuration parameter '{name}'")

        system_table = ddb_resource.Table(SYSTEM_TABLE_NAME)

        response = system_table.get_item(
            Key={
                "Name": name
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"System configuration parameter '{name}' not found")

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")  
    
    except NotFoundError as e:
        logger.info(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        logger.info(f"Unable to get the value of the system configuration parameter '{name}': {str(e)}")
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
        logger.info("Listing all the system configuration parameters")

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
        logger.info(f"Unable to list the system configuration parameters: {str(e)}")
        raise ChaliceViewError(f"Unable to list the system configuration parameters: {str(e)}")

    else:
        return replace_decimals(configs)

def get_bucket_region(bucket_name: str) -> bool:
    resp = s3_client.get_bucket_location(Bucket=bucket_name)
    if resp['LocationConstraint']:
        return resp['LocationConstraint'] == REGION
    else:
        return "us-east-1" == REGION

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
        logger.info("Listing all the S3 buckets")

        response = s3_client.list_buckets()
        buckets = response["Buckets"]
        bucket_list =  [
            bucket["Name"]
            # Only get the buckets from your region
            # null location constraint means its us-east-1
            for bucket in buckets if get_bucket_region(bucket['Name'])
        ]
        return bucket_list

    except Exception as e:
        logger.info(f"Unable to list all the S3 buckets: {str(e)}")
        raise ChaliceViewError(f"Unable to list all the S3 buckets: {str(e)}")
    
def validate_path_parameters(params: dict):
    validate(event=params, schema=API_SCHEMA["system_path_validation"])