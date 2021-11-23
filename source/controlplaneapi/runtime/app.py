#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import json
import uuid
import urllib.parse
import copy
import boto3
import jwt
import functools
import rsa

from decimal import Decimal
from datetime import datetime, timedelta
from chalice import Chalice, Response, AuthResponse
from chalice import IAMAuthorizer, Rate
from chalice import ChaliceViewError, BadRequestError, ConflictError, NotFoundError
from boto3.dynamodb.types import TypeSerializer
from boto3.dynamodb.conditions import Key, Attr
from botocore.client import ClientError
from jsonschema import validate, ValidationError, FormatChecker
from botocore.signers import CloudFrontSigner
from chalicelib import DecimalEncoder
from chalicelib import generate_plugin_state_definition, generate_profile_state_definition, load_api_schema, \
    replace_decimals

app = Chalice(app_name='aws-mre-controlplane-api')

API_VERSION = '1.0.0'

# Environment variables defined in the CDK stack
FRAMEWORK_VERSION = os.environ['FRAMEWORK_VERSION']
SYSTEM_TABLE_NAME = os.environ['SYSTEM_TABLE_NAME']
CONTENT_GROUP_TABLE_NAME = os.environ['CONTENT_GROUP_TABLE_NAME']
PROGRAM_TABLE_NAME = os.environ['PROGRAM_TABLE_NAME']
PLUGIN_TABLE_NAME = os.environ['PLUGIN_TABLE_NAME']
PLUGIN_NAME_INDEX = os.environ['PLUGIN_NAME_INDEX']
PLUGIN_VERSION_INDEX = os.environ['PLUGIN_VERSION_INDEX']
PROFILE_TABLE_NAME = os.environ['PROFILE_TABLE_NAME']
MODEL_TABLE_NAME = os.environ['MODEL_TABLE_NAME']
MODEL_NAME_INDEX = os.environ['MODEL_NAME_INDEX']
MODEL_VERSION_INDEX = os.environ['MODEL_VERSION_INDEX']
EVENT_TABLE_NAME = os.environ['EVENT_TABLE_NAME']
EVENT_CHANNEL_INDEX = os.environ['EVENT_CHANNEL_INDEX']
EVENT_PROGRAMID_INDEX = os.environ['EVENT_PROGRAMID_INDEX']
EVENT_CONTENT_GROUP_INDEX = os.environ['EVENT_CONTENT_GROUP_INDEX']
EVENT_PAGINATION_INDEX = os.environ['EVENT_PAGINATION_INDEX']
WORKFLOW_EXECUTION_TABLE_NAME = os.environ['WORKFLOW_EXECUTION_TABLE_NAME']
REPLAY_REQUEST_TABLE_NAME = os.environ['REPLAY_REQUEST_TABLE_NAME']
MEDIALIVE_S3_BUCKET = os.environ['MEDIALIVE_S3_BUCKET']
PROBE_VIDEO_LAMBDA_ARN = os.environ['PROBE_VIDEO_LAMBDA_ARN']
MULTI_CHUNK_HELPER_LAMBDA_ARN = os.environ['MULTI_CHUNK_HELPER_LAMBDA_ARN']
PLUGIN_OUTPUT_HANDLER_LAMBDA_ARN = os.environ['PLUGIN_OUTPUT_HANDLER_LAMBDA_ARN']
WORKFLOW_ERROR_HANDLER_LAMBDA_ARN = os.environ['WORKFLOW_ERROR_HANDLER_LAMBDA_ARN']
SFN_ROLE_ARN = os.environ['SFN_ROLE_ARN']
EB_EVENT_BUS_NAME = os.environ['EB_EVENT_BUS_NAME']
SQS_QUEUE_URL = os.environ['SQS_QUEUE_URL']
HLS_HS256_API_AUTH_SECRET_KEY_NAME = os.environ['HLS_HS256_API_AUTH_SECRET_KEY_NAME']
CLOUDFRONT_COOKIE_PRIVATE_KEY_FROM_SECRET_MGR = os.environ['CLOUDFRONT_COOKIE_PRIVATE_KEY_NAME']
CLOUDFRONT_COOKIE_KEY_PAIR_ID_FROM_SECRET_MGR = os.environ['CLOUDFRONT_COOKIE_KEY_PAIR_ID_NAME']
HLS_STREAM_CLOUDFRONT_DISTRO = os.environ['HLS_STREAM_CLOUDFRONT_DISTRO']
CURRENT_EVENTS_TABLE_NAME = os.environ['CURRENT_EVENTS_TABLE_NAME']

authorizer = IAMAuthorizer()
serializer = TypeSerializer()

ddb_resource = boto3.resource("dynamodb")
ddb_client = boto3.client("dynamodb")
sfn_client = boto3.client("stepfunctions")
medialive_client = boto3.client("medialive")
mediatailor_client = boto3.client("mediatailor")
cw_client = boto3.client("cloudwatch")
eb_client = boto3.client("events")
sqs_client = boto3.client("sqs")
s3_client = boto3.client("s3")
s3_resource = boto3.resource("s3")
sm_client = boto3.client("secretsmanager")
API_SCHEMA = load_api_schema()


@app.route('/version', cors=True, methods=['GET'], authorizer=authorizer)
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


@app.route('/uuid', cors=True, methods=['GET'], authorizer=authorizer)
def generate_uuid():
    """
    Generate a random UUID string using the Python 'uuid' module

    Returns:

    .. code-block:: python

        UUID
    """
    return str(uuid.uuid4())


#############################################################
#                                                           #
#             SYSTEM CONFIGURATION PARAMETERS               #
#                                                           #
#############################################################

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


#############################################################
#                                                           #
#                        PLUGINS                            #
#                                                           #
#############################################################

@app.route('/plugin', cors=True, methods=['POST'], authorizer=authorizer)
def register_plugin():
    """
    Register a new plugin or publish a new version of an existing plugin with updated 
    attribute values.
    
    Plugins can be one of the following types:
        - Sync: Contains all the required processing logic within the plugin to achieve the end result
        - SyncModel: Depends on a Machine Learning model to help with achieving the end result

    Body:

    .. code-block:: python

        {
            "Name": string,
            "Description": string,
            "Class": ["Classifier"|"Optimizer"|"Featurer"|"Labeler"]
            "ExecutionType": ["Sync"|"SyncModel"],
            "SupportedMediaType": ["Video"|"Audio"],
            "ContentGroups": list,
            "ExecuteLambdaQualifiedARN": arn,
            "ModelEndpoints": [
                {
                    "Name": string,
                    "Version": string
                },
                ...
            ],
            "Configuration" : {
                    "configuration1": "value1",
                    ...
            },
            "OutputAttributes" : {
                    "attribute1": {
                        "Description": string
                    },
                    ...
            },
            "DependentPlugins": list
        }

    Parameters:

        - Name: Name of the Plugin
        - Description: Description of the Plugin
        - Class: One of "Classifier"|"Optimizer"|"Featurer"|"Labeler"
        - ExecutionType: One of "Sync"|"SyncModel". SyncModel indicates that the Plugin has a ML Model dependency.
        - SupportedMediaType: One of "Video"|"Audio". Whether Plugin operates on Video or Audio source
        - ContentGroups: List of Content Group supported by the Plugin
        - ExecuteLambdaQualifiedARN: ARN of the Lambda function that encapsulates the Plugin implementation
        - ModelEndpoints:  List of Dicts which contains the MRE Models used by the Plugin. Required only when the ExecutionType is SyncModel.
        - Configuration: Configuration values which impact the Plugin behavior. For example, MlModelConfidenceScore: 60
        - OutputAttributes: List of dict that have the name of the attributes the Plugin Outputs. These attributes can be configured to create Replays within MRE.
        - DependentPlugins: A list of Plugin names on which this Plugin depends on. MRE executes the dependent plugins before executing this plugin.

    Returns:

        A dict containing the Id and Version of the registered plugin

        .. code-block:: python

            {
                "Id": string,
                "Version": string
            }

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        plugin = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=plugin, schema=API_SCHEMA["register_plugin"])

        print("Got a valid plugin schema")

        name = plugin["Name"]
        execution_type = plugin["ExecutionType"]

        if execution_type == "SyncModel":
            if "ModelEndpoints" not in plugin:
                raise BadRequestError("Missing required key 'ModelEndpoints' in the input")

            else:
                model_table = ddb_resource.Table(MODEL_TABLE_NAME)

                for model_endpoint in plugin["ModelEndpoints"]:
                    model_name = model_endpoint["Name"]
                    model_version = model_endpoint["Version"]

                    response = model_table.get_item(
                        Key={
                            "Name": model_name,
                            "Version": model_version
                        },
                        ConsistentRead=True
                    )

                    if "Item" not in response:
                        raise NotFoundError(f"Model endpoint '{model_name}' with version '{model_version}' not found")

                    elif not response["Item"]["Enabled"]:
                        raise BadRequestError(
                            f"Model endpoint '{model_name}' with version '{model_version}' is disabled in the system")

        plugin_table = ddb_resource.Table(PLUGIN_TABLE_NAME)

        # Check if all the DependentPlugins are already registered and enabled in the system
        if "DependentPlugins" in plugin:
            dependent_plugins = plugin["DependentPlugins"]

            for d_plugin in dependent_plugins:
                if d_plugin == name:
                    raise BadRequestError(f"Plugin '{d_plugin}' cannot be a dependent of itself")

                response = plugin_table.get_item(
                    Key={
                        "Name": d_plugin,
                        "Version": "v0"
                    },
                    ConsistentRead=True
                )

                if "Item" not in response:
                    raise NotFoundError(f"Dependent plugin '{d_plugin}' not found")

                elif not response["Item"]["Enabled"]:
                    raise BadRequestError(f"Dependent plugin '{d_plugin}' is disabled in the system")

        else:
            dependent_plugins = []

        output_attributes = plugin["OutputAttributes"] if "OutputAttributes" in plugin else {}

        response = plugin_table.get_item(
            Key={
                "Name": name,
                "Version": "v0"
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            print(f"Registering a new plugin '{name}'")
            plugin["Id"] = str(uuid.uuid4())
            latest_version = 0
            higher_version = 1

        else:
            print(f"Publishing a new version of the plugin '{name}'")
            plugin["Id"] = response["Item"]["Id"]
            latest_version = response["Item"]["Latest"]
            higher_version = int(latest_version) + 1

        plugin["Created"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        plugin["Enabled"] = True
        plugin["FrameworkVersion"] = FRAMEWORK_VERSION

        state_definition = generate_plugin_state_definition(execution_type)

        state_definition_str = json.dumps(state_definition)
        state_definition_str = state_definition_str.replace("%%PLUGIN_NAME%%", name)
        state_definition_str = state_definition_str.replace("%%PLUGIN_CLASS%%", plugin["Class"])
        state_definition_str = state_definition_str.replace("%%PLUGIN_EXECUTION_TYPE%%", execution_type)
        state_definition_str = state_definition_str.replace("%%PLUGIN_EXECUTE_LAMBDA_ARN%%",
                                                            plugin["ExecuteLambdaQualifiedARN"])
        state_definition_str = state_definition_str.replace("\"%%PLUGIN_DEPENDENT_PLUGINS%%\"",
                                                            json.dumps(dependent_plugins))
        state_definition_str = state_definition_str.replace("\"%%PLUGIN_OUTPUT_ATTRIBUTES%%\"",
                                                            json.dumps(output_attributes))

        plugin["StateDefinition"] = state_definition_str

        print(f"Plugin State Definition: {state_definition_str}")

        # Serialize Python object to DynamoDB object
        serialized_plugin = {k: serializer.serialize(v) for k, v in plugin.items()}

        ddb_client.transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": PLUGIN_TABLE_NAME,
                        "Key": {
                            "Name": {"S": name},
                            "Version": {"S": "v0"}
                        },
                        "ConditionExpression": "attribute_not_exists(#Latest) OR #Latest = :Latest",
                        "UpdateExpression": "SET #Latest = :Higher_version, #Id = :Id, #Class = :Class, #Description = :Description, #ContentGroups = :ContentGroups, #ExecutionType = :ExecutionType, #SupportedMediaType = :SupportedMediaType, #ExecuteLambda = :ExecuteLambda, #StateDefinition = :StateDefinition, #ModelEndpoints = :ModelEndpoints, #Configuration = :Configuration, #OutputAttributes = :OutputAttributes, #DependentPlugins = :DependentPlugins, #Created = :Created, #Enabled = :Enabled, #FrameworkVersion = :FrameworkVersion",
                        "ExpressionAttributeNames": {
                            "#Latest": "Latest",
                            "#Id": "Id",
                            "#Class": "Class",
                            "#Description": "Description",
                            "#ContentGroups": "ContentGroups",
                            "#ExecutionType": "ExecutionType",
                            "#SupportedMediaType": "SupportedMediaType",
                            "#ExecuteLambda": "ExecuteLambdaQualifiedARN",
                            "#StateDefinition": "StateDefinition",
                            "#ModelEndpoints": "ModelEndpoints",
                            "#Configuration": "Configuration",
                            "#OutputAttributes": "OutputAttributes",
                            "#DependentPlugins": "DependentPlugins",
                            "#Created": "Created",
                            "#Enabled": "Enabled",
                            "#FrameworkVersion": "FrameworkVersion"
                        },
                        "ExpressionAttributeValues": {
                            ":Latest": {"N": str(latest_version)},
                            ":Higher_version": {"N": str(higher_version)},
                            ":Id": serialized_plugin["Id"],
                            ":Class": serialized_plugin["Class"],
                            ":Description": serialized_plugin[
                                "Description"] if "Description" in serialized_plugin else {"S": ""},
                            ":ContentGroups": serialized_plugin["ContentGroups"],
                            ":ExecutionType": serialized_plugin["ExecutionType"],
                            ":SupportedMediaType": serialized_plugin["SupportedMediaType"],
                            ":ExecuteLambda": serialized_plugin["ExecuteLambdaQualifiedARN"],
                            ":StateDefinition": serialized_plugin["StateDefinition"],
                            ":ModelEndpoints": serialized_plugin[
                                "ModelEndpoints"] if execution_type == "SyncModel" else {"L": []},
                            ":Configuration": serialized_plugin[
                                "Configuration"] if "Configuration" in serialized_plugin else {"M": {}},
                            ":OutputAttributes": serialized_plugin[
                                "OutputAttributes"] if "OutputAttributes" in serialized_plugin else {"M": {}},
                            ":DependentPlugins": serialized_plugin[
                                "DependentPlugins"] if "DependentPlugins" in serialized_plugin else {"L": []},
                            ":Created": serialized_plugin["Created"],
                            ":Enabled": serialized_plugin["Enabled"],
                            ":FrameworkVersion": serialized_plugin["FrameworkVersion"]
                        }
                    }
                },
                {
                    "Put": {
                        "TableName": PLUGIN_TABLE_NAME,
                        "Item": {
                            "Name": {"S": name},
                            "Version": {"S": "v" + str(higher_version)},
                            "Id": serialized_plugin["Id"],
                            "Class": serialized_plugin["Class"],
                            "Description": serialized_plugin["Description"] if "Description" in serialized_plugin else {
                                "S": ""},
                            "ContentGroups": serialized_plugin["ContentGroups"],
                            "ExecutionType": serialized_plugin["ExecutionType"],
                            "SupportedMediaType": serialized_plugin["SupportedMediaType"],
                            "ExecuteLambdaQualifiedARN": serialized_plugin["ExecuteLambdaQualifiedARN"],
                            "StateDefinition": serialized_plugin["StateDefinition"],
                            "ModelEndpoints": serialized_plugin[
                                "ModelEndpoints"] if execution_type == "SyncModel" else {"L": []},
                            "Configuration": serialized_plugin[
                                "Configuration"] if "Configuration" in serialized_plugin else {"M": {}},
                            "OutputAttributes": serialized_plugin[
                                "OutputAttributes"] if "OutputAttributes" in serialized_plugin else {"M": {}},
                            "Created": serialized_plugin["Created"],
                            "Enabled": serialized_plugin["Enabled"],
                            "DependentPlugins": serialized_plugin[
                                "DependentPlugins"] if "DependentPlugins" in serialized_plugin else {"L": []},
                            "FrameworkVersion": serialized_plugin["FrameworkVersion"]
                        }
                    }
                }
            ]
        )

    except BadRequestError as e:
        print(f"Got chalice BadRequestError: {str(e)}")
        raise

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to register or publish a new version of the plugin: {str(e)}")
        raise ChaliceViewError(f"Unable to register or publish a new version of the plugin: {str(e)}")

    else:
        print(
            f"Successfully registered or published a new version of the plugin: {json.dumps(plugin, cls=DecimalEncoder)}")

        return {
            "Id": plugin["Id"],
            "Version": "v" + str(higher_version)
        }


@app.route('/plugin/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_plugins():
    """
    List the latest version of all the registered plugins.
    Each plugin has version "v0" which holds a copy of the latest plugin revision.

    By default, return only the plugins that are "Enabled" in the system. In order 
    to also return the "Disabled" plugins, include the query parameter "include_disabled=true".

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string,
                    "Id": string,
                    "Class": ["Classifier"|"Optimizer"|"Featurer"|"Labeler"],
                    "Description": string,
                    "ContentGroups": list,
                    "ExecutionType": ["Sync"|"SyncModel"],
                    "SupportedMediaType": ["Video"|"Audio"],
                    "ExecuteLambdaQualifiedARN": arn,
                    "StateDefinition": string,
                    "ModelEndpoints": [
                        {
                            "Name": string,
                            "Version": string
                        },
                        ...
                    ],
                    "Configuration" : {
                        "configuration1": "value1",
                        ...
                    },
                    "OutputAttributes" : {
                        "attribute1": {
                            "Description": string
                        },
                        ...
                    },
                    "DependentPlugins": list,
                    "Version": string,
                    "Created": timestamp,
                    "Latest": number,
                    "Enabled": boolean,
                    "FrameworkVersion": "x.x.x"
                },
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        print("Listing the latest version of all the registered plugins")

        query_params = app.current_request.query_params

        if query_params and query_params.get("include_disabled") == "true":
            filter_expression = Attr("Enabled").is_in([True, False])
        else:
            filter_expression = Attr("Enabled").eq(True)

        plugin_table = ddb_resource.Table(PLUGIN_TABLE_NAME)

        response = plugin_table.query(
            IndexName=PLUGIN_VERSION_INDEX,
            KeyConditionExpression=Key("Version").eq("v0"),
            FilterExpression=filter_expression
        )

        plugins = response["Items"]

        while "LastEvaluatedKey" in response:
            response = plugin_table.query(
                IndexName=PLUGIN_VERSION_INDEX,
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("Version").eq("v0"),
                FilterExpression=filter_expression
            )

            plugins.extend(response["Items"])

    except Exception as e:
        print(f"Unable to list the latest version of all the registered plugins: {str(e)}")
        raise ChaliceViewError(f"Unable to list the latest version of all the registered plugins: {str(e)}")

    else:
        return replace_decimals(plugins)


@app.route('/plugin/class/{plugin_class}/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_plugins_by_class(plugin_class):
    """
    List the latest version of all the registered plugins by class.
    Each plugin has version "v0" which holds a copy of the latest plugin revision.

    By default, return only the plugins that are "Enabled" in the system. In order 
    to also return the "Disabled" plugins, include the query parameter "include_disabled=true".

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string,
                    "Id": string,
                    "Class": ["Classifier"|"Optimizer"|"Featurer"|"Labeler"],
                    "Description": string,
                    "ContentGroups": list,
                    "ExecutionType": ["Sync"|"SyncModel"],
                    "SupportedMediaType": ["Video"|"Audio"],
                    "ExecuteLambdaQualifiedARN": arn,
                    "StateDefinition": string,
                    "ModelEndpoints": [
                        {
                            "Name": string,
                            "Version": string
                        },
                        ...
                    ],
                    "Configuration" : {
                        "configuration1": "value1",
                        ...
                    },
                    "OutputAttributes" : {
                        "attribute1": {
                            "Description": string
                        },
                        ...
                    },
                    "DependentPlugins": list,
                    "Version": string,
                    "Created": timestamp,
                    "Latest": number,
                    "Enabled": boolean,
                    "FrameworkVersion": "x.x.x"
                },
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        plugin_class = urllib.parse.unquote(plugin_class)

        print(f"Listing the latest version of all the registered plugins for class '{plugin_class}'")

        query_params = app.current_request.query_params

        if query_params and query_params.get("include_disabled") == "true":
            filter_expression = Attr("Enabled").is_in([True, False])
        else:
            filter_expression = Attr("Enabled").eq(True)

        plugin_table = ddb_resource.Table(PLUGIN_TABLE_NAME)

        response = plugin_table.query(
            IndexName=PLUGIN_VERSION_INDEX,
            KeyConditionExpression=Key("Version").eq("v0"),
            FilterExpression=Attr("Class").eq(plugin_class) & filter_expression
        )

        plugins = response["Items"]

        while "LastEvaluatedKey" in response:
            response = plugin_table.query(
                IndexName=PLUGIN_VERSION_INDEX,
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("Version").eq("v0"),
                FilterExpression=Attr("Class").eq(plugin_class) & filter_expression
            )

            plugins.extend(response["Items"])

    except Exception as e:
        print(f"Unable to list the latest version of all the registered plugins for class '{plugin_class}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to list the latest version of all the registered plugins for class '{plugin_class}': {str(e)}")

    else:
        return replace_decimals(plugins)


@app.route('/plugin/contentgroup/{content_group}/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_plugins_by_contentgroup(content_group):
    """
    List the latest version of all the registered plugins by content group.
    Each plugin has version "v0" which holds a copy of the latest plugin revision.

    By default, return only the plugins that are "Enabled" in the system. In order 
    to also return the "Disabled" plugins, include the query parameter "include_disabled=true".

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string,
                    "Id": string,
                    "Class": ["Classifier"|"Optimizer"|"Featurer"|"Labeler"],
                    "Description": string,
                    "ContentGroups": list,
                    "ExecutionType": ["Sync"|"SyncModel"],
                    "SupportedMediaType": ["Video"|"Audio"],
                    "ExecuteLambdaQualifiedARN": arn,
                    "StateDefinition": string,
                    "ModelEndpoints": [
                        {
                            "Name": string,
                            "Version": string
                        },
                        ...
                    ],
                    "Configuration" : {
                        "configuration1": "value1",
                        ...
                    },
                    "OutputAttributes" : {
                        "attribute1": {
                            "Description": string
                        },
                        ...
                    },
                    "DependentPlugins": list,
                    "Version": string,
                    "Created": timestamp,
                    "Latest": number,
                    "Enabled": boolean,
                    "FrameworkVersion": "x.x.x"
                },
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        content_group = urllib.parse.unquote(content_group)

        print(f"Listing the latest version of all the registered plugins for content group '{content_group}'")

        query_params = app.current_request.query_params

        if query_params and query_params.get("include_disabled") == "true":
            filter_expression = Attr("Enabled").is_in([True, False])
        else:
            filter_expression = Attr("Enabled").eq(True)

        plugin_table = ddb_resource.Table(PLUGIN_TABLE_NAME)

        response = plugin_table.query(
            IndexName=PLUGIN_VERSION_INDEX,
            KeyConditionExpression=Key("Version").eq("v0"),
            FilterExpression=Attr("ContentGroups").contains(content_group) & filter_expression
        )

        plugins = response["Items"]

        while "LastEvaluatedKey" in response:
            response = plugin_table.query(
                IndexName=PLUGIN_VERSION_INDEX,
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("Version").eq("v0"),
                FilterExpression=Attr("ContentGroups").contains(content_group) & filter_expression
            )

            plugins.extend(response["Items"])

    except Exception as e:
        print(
            f"Unable to list the latest version of all the registered plugins for content group '{content_group}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to list the latest version of all the registered plugins for content group '{content_group}': {str(e)}")

    else:
        return replace_decimals(plugins)


@app.route('/plugin/class/{plugin_class}/contentgroup/{content_group}/all', cors=True, methods=['GET'],
           authorizer=authorizer)
def list_plugins_by_class_and_contentgroup(plugin_class, content_group):
    """
    List the latest version of all the registered plugins by class and content group.
    Each plugin has version "v0" which holds a copy of the latest plugin revision.

    By default, return only the plugins that are "Enabled" in the system. In order 
    to also return the "Disabled" plugins, include the query parameter "include_disabled=true".

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string,
                    "Id": string,
                    "Class": ["Classifier"|"Optimizer"|"Featurer"|"Labeler"],
                    "Description": string,
                    "ContentGroups": list,
                    "ExecutionType": ["Sync"|"SyncModel"],
                    "SupportedMediaType": ["Video"|"Audio"],
                    "ExecuteLambdaQualifiedARN": arn,
                    "StateDefinition": string,
                    "ModelEndpoints": [
                        {
                            "Name": string,
                            "Version": string
                        },
                        ...
                    ],
                    "Configuration" : {
                        "configuration1": "value1",
                        ...
                    },
                    "OutputAttributes" : {
                        "attribute1": {
                            "Description": string
                        },
                        ...
                    },
                    "DependentPlugins": list,
                    "Version": string,
                    "Created": timestamp,
                    "Latest": number,
                    "Enabled": boolean,
                    "FrameworkVersion": "x.x.x"
                },
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        plugin_class = urllib.parse.unquote(plugin_class)
        content_group = urllib.parse.unquote(content_group)

        print(
            f"Listing the latest version of all the registered plugins for class '{plugin_class}' and content group '{content_group}'")

        query_params = app.current_request.query_params

        if query_params and query_params.get("include_disabled") == "true":
            filter_expression = Attr("Enabled").is_in([True, False])
        else:
            filter_expression = Attr("Enabled").eq(True)

        plugin_table = ddb_resource.Table(PLUGIN_TABLE_NAME)

        response = plugin_table.query(
            IndexName=PLUGIN_VERSION_INDEX,
            KeyConditionExpression=Key("Version").eq("v0"),
            FilterExpression=Attr("Class").eq(plugin_class) & Attr("ContentGroups").contains(
                content_group) & filter_expression
        )

        plugins = response["Items"]

        while "LastEvaluatedKey" in response:
            response = plugin_table.query(
                IndexName=PLUGIN_VERSION_INDEX,
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("Version").eq("v0"),
                FilterExpression=Attr("Class").eq(plugin_class) & Attr("ContentGroups").contains(
                    content_group) & filter_expression
            )

            plugins.extend(response["Items"])

    except Exception as e:
        print(
            f"Unable to list the latest version of all the registered plugins for class '{plugin_class}' and content group '{content_group}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to list the latest version of all the registered plugins for class '{plugin_class}' and content group '{content_group}': {str(e)}")

    else:
        return replace_decimals(plugins)


@app.route('/plugin/{name}', cors=True, methods=['GET'], authorizer=authorizer)
def get_plugin_by_name(name):
    """
    Get the latest version of a plugin by name.

    Each plugin has version "v0" which holds a copy of the latest plugin revision.

    Returns:

        .. code-block:: python

            {
                "Name": string,
                "Id": string,
                "Class": ["Classifier"|"Optimizer"|"Featurer"|"Labeler"],
                "Description": string,
                "ContentGroups": list,
                "ExecutionType": ["Sync"|"SyncModel"],
                "SupportedMediaType": ["Video"|"Audio"],
                "ExecuteLambdaQualifiedARN": arn,
                "StateDefinition": string,
                "ModelEndpoints": [
                    {
                        "Name": string,
                        "Version": string
                    },
                    ...
                ],
                "Configuration" : {
                    "configuration1": "value1",
                    ...
                },
                "OutputAttributes" : {
                    "attribute1": {
                        "Description": string
                    },
                    ...
                },
                "DependentPlugins": list,
                "Version": string,
                "Created": timestamp,
                "Latest": number,
                "Enabled": boolean,
                "FrameworkVersion": "x.x.x"
            }

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)

        print(f"Getting the latest version of the plugin '{name}'")

        plugin_table = ddb_resource.Table(PLUGIN_TABLE_NAME)

        response = plugin_table.get_item(
            Key={
                "Name": name,
                "Version": "v0"
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Plugin '{name}' not found")

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to get the latest version of the plugin '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to get the latest version of the plugin '{name}': {str(e)}")

    else:
        return replace_decimals(response["Item"])


@app.route('/plugin/{name}/version/{version}', cors=True, methods=['GET'], authorizer=authorizer)
def get_plugin_by_name_and_version(name, version):
    """
    Get a plugin by name and version.

    Returns:

        .. code-block:: python

            {
                "Name": string,
                "Id": string,
                "Class": ["Classifier"|"Optimizer"|"Featurer"|"Labeler"],
                "Description": string,
                "ContentGroups": list,
                "ExecutionType": ["Sync"|"SyncModel"],
                "SupportedMediaType": ["Video"|"Audio"],
                "ExecuteLambdaQualifiedARN": arn,
                "StateDefinition": string,
                "ModelEndpoints": [
                    {
                        "Name": string,
                        "Version": string
                    },
                    ...
                ],
                "Configuration" : {
                    "configuration1": "value1",
                    ...
                },
                "OutputAttributes" : {
                    "attribute1": {
                        "Description": string
                    },
                    ...
                },
                "DependentPlugins": list,
                "Version": string,
                "Created": timestamp,
                ["Latest": number],
                ["Enabled": boolean],
                "FrameworkVersion": "x.x.x"
            }

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        version = urllib.parse.unquote(version)

        print(f"Getting the plugin '{name}' with version '{version}'")

        plugin_table = ddb_resource.Table(PLUGIN_TABLE_NAME)

        response = plugin_table.get_item(
            Key={
                "Name": name,
                "Version": version
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Plugin '{name}' with version '{version}' not found")

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to get the plugin '{name}' with version '{version}': {str(e)}")
        raise ChaliceViewError(f"Unable to get the plugin '{name}' with version '{version}': {str(e)}")

    else:
        return replace_decimals(response["Item"])


@app.route('/plugin/{name}/version/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_plugin_versions(name):
    """
    List all the versions of a plugin by name.

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string,
                    "Id": string,
                    "Class": ["Classifier"|"Optimizer"|"Featurer"|"Labeler"],
                    "Description": string,
                    "ContentGroups": list,
                    "ExecutionType": ["Sync"|"SyncModel"],
                    "SupportedMediaType": ["Video"|"Audio"],
                    "ExecuteLambdaQualifiedARN": arn,
                    "StateDefinition": string,
                    "ModelEndpoints": [
                        {
                            "Name": string,
                            "Version": string
                        },
                        ...
                    ],
                    "Configuration" : {
                        "configuration1": "value1",
                        ...
                    },
                    "OutputAttributes" : {
                        "attribute1": {
                            "Description": string
                        },
                        ...
                    },
                    "DependentPlugins": list,
                    "Version": string,
                    "Created": timestamp,
                    ["Latest": number],
                    ["Enabled": boolean],
                    "FrameworkVersion": "x.x.x"
                },
                ...
            ]

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)

        print(f"Getting all the versions of the plugin '{name}'")

        plugin_table = ddb_resource.Table(PLUGIN_TABLE_NAME)

        response = plugin_table.query(
            IndexName=PLUGIN_NAME_INDEX,
            KeyConditionExpression=Key("Name").eq(name)
        )

        if "Items" not in response or len(response["Items"]) < 1:
            raise NotFoundError(f"Plugin '{name}' not found")

        versions = response["Items"]

        while "LastEvaluatedKey" in response:
            response = plugin_table.query(
                IndexName=PLUGIN_NAME_INDEX,
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("Name").eq(name)
            )

            versions.extend(response["Items"])

        # Remove version 'v0' from the query result
        for index, version in enumerate(versions):
            if version["Version"] == "v0":
                versions.pop(index)
                break

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to list the versions of the plugin '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to list the versions of the plugin '{name}': {str(e)}")

    else:
        return replace_decimals(versions)


@app.route('/plugin/{name}', cors=True, methods=['DELETE'], authorizer=authorizer)
def delete_plugin(name):
    """
    Delete all the versions of a plugin by name.

    Returns:

        None

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)

        print(f"Deleting plugin '{name}' and all its versions")

        plugin_table = ddb_resource.Table(PLUGIN_TABLE_NAME)

        response = plugin_table.query(
            IndexName=PLUGIN_NAME_INDEX,
            KeyConditionExpression=Key("Name").eq(name)
        )

        if "Items" not in response or len(response["Items"]) < 1:
            raise NotFoundError(f"Plugin '{name}' not found")

        versions = response["Items"]

        while "LastEvaluatedKey" in response:
            response = plugin_table.query(
                IndexName=PLUGIN_NAME_INDEX,
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("Name").eq(name)
            )

            versions.extend(response["Items"])

        with plugin_table.batch_writer() as batch:
            for item in versions:
                batch.delete_item(
                    Key={
                        "Name": item["Name"],
                        "Version": item["Version"]
                    }
                )

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to delete the plugin '{name}' and its versions: {str(e)}")
        raise ChaliceViewError(f"Unable to delete the plugin '{name}' and its versions: {str(e)}")

    else:
        print(f"Deletion of plugin '{name}' and its versions successful")
        return {}


@app.route('/plugin/{name}/version/{version}', cors=True, methods=['DELETE'], authorizer=authorizer)
def delete_plugin_version(name, version):
    """
    Delete a specific version of a plugin by name and version.

    Deletion can be performed on all the plugin versions except "v0" and the latest plugin revision. 
    If the latest plugin version needs to be deleted, publish a new version of the plugin and then 
    delete the prior plugin version.

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        version = urllib.parse.unquote(version)

        plugin_table = ddb_resource.Table(PLUGIN_TABLE_NAME)

        response = plugin_table.get_item(
            Key={
                "Name": name,
                "Version": "v0"
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Plugin '{name}' not found")

        latest_version = "v" + str(response["Item"]["Latest"])

        print(f"Deleting version '{version}' of the plugin '{name}'")

        response = plugin_table.delete_item(
            Key={
                "Name": name,
                "Version": version
            },
            ConditionExpression="NOT (#Version IN (:Value1, :Value2))",
            ExpressionAttributeNames={
                "#Version": "Version"
            },
            ExpressionAttributeValues={
                ":Value1": "v0",
                ":Value2": latest_version
            },
            ReturnValues="ALL_OLD"
        )

        if "Attributes" not in response:
            raise NotFoundError(f"Plugin '{name}' with version '{version}' not found")

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            if version == "v0":
                raise BadRequestError("Deletion of version 'v0' of the plugin is prohibited")
            raise BadRequestError(
                f"Deletion of version '{version}' of the plugin is blocked as it is the latest plugin revision. Publish a new version to unblock the deletion of version '{version}'")

        else:
            raise

    except Exception as e:
        print(f"Unable to delete version '{version}' of the plugin '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to delete version '{version}' of the plugin '{name}': {str(e)}")

    else:
        print(f"Deletion of version '{version}' of the plugin '{name}' successful")
        return {}


@app.route('/plugin/{name}/status', cors=True, methods=['PUT'], authorizer=authorizer)
def update_plugin_status(name):
    """
    Enable or Disable the latest version of a plugin by name.

    Body:

    .. code-block:: python

        {
            "Enabled": boolean
        }

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        status = json.loads(app.current_request.raw_body.decode())

        validate(instance=status, schema=API_SCHEMA["update_status"])

        print("Got a valid status schema")

        print(f"Updating the status of the latest version of plugin '{name}'")

        plugin_table = ddb_resource.Table(PLUGIN_TABLE_NAME)

        response = plugin_table.get_item(
            Key={
                "Name": name,
                "Version": "v0"
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Plugin '{name}' not found")

        latest_version = "v" + str(response["Item"]["Latest"])

        # Update version v0
        plugin_table.update_item(
            Key={
                "Name": name,
                "Version": "v0"
            },
            UpdateExpression="SET #Enabled = :Status",
            ExpressionAttributeNames={
                "#Enabled": "Enabled"
            },
            ExpressionAttributeValues={
                ":Status": status["Enabled"]
            }
        )

        # Update the latest version
        plugin_table.update_item(
            Key={
                "Name": name,
                "Version": latest_version
            },
            UpdateExpression="SET #Enabled = :Status",
            ConditionExpression="attribute_exists(#Name) AND attribute_exists(#Version)",
            ExpressionAttributeNames={
                "#Enabled": "Enabled",
                "#Name": "Name",
                "#Version": "Version"
            },
            ExpressionAttributeValues={
                ":Status": status["Enabled"]
            }
        )

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise NotFoundError(f"Plugin '{name}' with latest version '{latest_version}' not found")
        else:
            raise

    except Exception as e:
        print(f"Unable to update the status of the latest version of plugin '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to update the status of the latest version of plugin '{name}': {str(e)}")

    else:
        return {}


@app.route('/plugin/{name}/version/{version}/status', cors=True, methods=['PUT'], authorizer=authorizer)
def update_plugin_version_status(name, version):
    """
    Enable or Disable a plugin by name and version.

    Body:

    .. code-block:: python

        {
            "Enabled": boolean
        }

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        version = urllib.parse.unquote(version)
        status = json.loads(app.current_request.raw_body.decode())

        validate(instance=status, schema=API_SCHEMA["update_status"])

        print("Got a valid status schema")

        print(f"Updating the status of the plugin '{name}' with version '{version}'")

        plugin_table = ddb_resource.Table(PLUGIN_TABLE_NAME)

        plugin_table.update_item(
            Key={
                "Name": name,
                "Version": version
            },
            UpdateExpression="SET #Enabled = :Status",
            ConditionExpression="attribute_exists(#Name) AND attribute_exists(#Version)",
            ExpressionAttributeNames={
                "#Enabled": "Enabled",
                "#Name": "Name",
                "#Version": "Version"
            },
            ExpressionAttributeValues={
                ":Status": status["Enabled"]
            }
        )

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise NotFoundError(f"Plugin '{name}' with version '{version}' not found")
        else:
            raise

    except Exception as e:
        print(f"Unable to update the status of the plugin '{name}' with version '{version}': {str(e)}")
        raise ChaliceViewError(f"Unable to update the status of the plugin '{name}' with version '{version}': {str(e)}")

    else:
        return {}


#############################################################
#                                                           #
#                        PROFILES                           #
#                                                           #
#############################################################

def get_model_endpoint_from_ddb(model):
    model_name = model["Name"]
    model_version = model["Version"]

    model_table = ddb_resource.Table(MODEL_TABLE_NAME)

    response = model_table.get_item(
        Key={
            "Name": model_name,
            "Version": model_version
        },
        ConsistentRead=True
    )

    if "Item" not in response:
        raise NotFoundError(f"Model endpoint '{model_name}' with version '{model_version}' not found")

    elif not response["Item"]["Enabled"]:
        raise BadRequestError(f"Model endpoint '{model_name}' with version '{model_version}' is disabled in the system")

    return response["Item"]["Endpoint"]


def profile_state_definition_helper(name, profile):
    plugins_list = []
    d_plugins_list = []
    batch_get_keys = []

    internal_lambda_arns = {
        "ProbeVideo": PROBE_VIDEO_LAMBDA_ARN,
        "MultiChunkHelper": MULTI_CHUNK_HELPER_LAMBDA_ARN,
        "PluginOutputHandler": PLUGIN_OUTPUT_HANDLER_LAMBDA_ARN,
        "WorkflowErrorHandler": WORKFLOW_ERROR_HANDLER_LAMBDA_ARN
    }

    shortened_profile = {
        "Name": name,
        "ChunkSize": profile["ChunkSize"],
        "MaxSegmentLengthSeconds": profile["MaxSegmentLengthSeconds"],
        "ProcessingFrameRate": profile["ProcessingFrameRate"]
    }

    # Classifier
    classifier = profile["Classifier"]

    if "ModelEndpoint" in classifier and isinstance(classifier["ModelEndpoint"], dict):
        classifier["ModelEndpoint"] = get_model_endpoint_from_ddb(classifier["ModelEndpoint"])

    shortened_classifier = {
        "Name": classifier["Name"],
        "Configuration": classifier["Configuration"] if "Configuration" in classifier else {},
        "DependentPlugins": []
    }
    plugins_list.append(classifier["Name"])
    batch_get_keys.append({"Name": classifier["Name"], "Version": "v0"})

    if "DependentPlugins" in classifier:
        for index, d_plugin in enumerate(classifier["DependentPlugins"]):
            if "ModelEndpoint" in d_plugin and isinstance(d_plugin["ModelEndpoint"], dict):
                classifier["DependentPlugins"][index]["ModelEndpoint"] = get_model_endpoint_from_ddb(
                    d_plugin["ModelEndpoint"])

            shortened_classifier["DependentPlugins"].append(
                {
                    "Name": d_plugin["Name"],
                    "Configuration": d_plugin["Configuration"] if "Configuration" in d_plugin else {},
                }
            )

            if d_plugin["Name"] not in d_plugins_list:
                d_plugins_list.append(d_plugin["Name"])
                batch_get_keys.append({"Name": d_plugin["Name"], "Version": "v0"})

    shortened_profile["Classifier"] = shortened_classifier

    # Optimizer
    optimizer = {}
    if "Optimizer" in profile and profile["Optimizer"]:
        optimizer = profile["Optimizer"]

        if "ModelEndpoint" in optimizer and isinstance(optimizer["ModelEndpoint"], dict):
            optimizer["ModelEndpoint"] = get_model_endpoint_from_ddb(optimizer["ModelEndpoint"])

        shortened_optimizer = {
            "Name": optimizer["Name"],
            "Configuration": optimizer["Configuration"] if "Configuration" in optimizer else {},
            "DependentPlugins": []
        }
        plugins_list.append(optimizer["Name"])
        batch_get_keys.append({"Name": optimizer["Name"], "Version": "v0"})

        if "DependentPlugins" in optimizer:
            for index, d_plugin in enumerate(optimizer["DependentPlugins"]):
                if "ModelEndpoint" in d_plugin and isinstance(d_plugin["ModelEndpoint"], dict):
                    optimizer["DependentPlugins"][index]["ModelEndpoint"] = get_model_endpoint_from_ddb(
                        d_plugin["ModelEndpoint"])

                shortened_optimizer["DependentPlugins"].append(
                    {
                        "Name": d_plugin["Name"],
                        "Configuration": d_plugin["Configuration"] if "Configuration" in d_plugin else {},
                    }
                )

                if d_plugin["Name"] not in d_plugins_list:
                    d_plugins_list.append(d_plugin["Name"])
                    batch_get_keys.append({"Name": d_plugin["Name"], "Version": "v0"})

        shortened_profile["Optimizer"] = shortened_optimizer

    # Labeler
    labeler = {}
    if "Labeler" in profile and profile["Labeler"]:
        labeler = profile["Labeler"]

        if "ModelEndpoint" in labeler and isinstance(labeler["ModelEndpoint"], dict):
            labeler["ModelEndpoint"] = get_model_endpoint_from_ddb(labeler["ModelEndpoint"])

        shortened_labeler = {
            "Name": labeler["Name"],
            "Configuration": labeler["Configuration"] if "Configuration" in labeler else {},
            "DependentPlugins": []
        }
        plugins_list.append(labeler["Name"])
        batch_get_keys.append({"Name": labeler["Name"], "Version": "v0"})

        if "DependentPlugins" in labeler:
            for index, d_plugin in enumerate(labeler["DependentPlugins"]):
                if "ModelEndpoint" in d_plugin and isinstance(d_plugin["ModelEndpoint"], dict):
                    labeler["DependentPlugins"][index]["ModelEndpoint"] = get_model_endpoint_from_ddb(
                        d_plugin["ModelEndpoint"])

                shortened_labeler["DependentPlugins"].append(
                    {
                        "Name": d_plugin["Name"],
                        "Configuration": d_plugin["Configuration"] if "Configuration" in d_plugin else {},
                    }
                )

                if d_plugin["Name"] not in d_plugins_list:
                    d_plugins_list.append(d_plugin["Name"])
                    batch_get_keys.append({"Name": d_plugin["Name"], "Version": "v0"})

        shortened_profile["Labeler"] = shortened_labeler

    # Featurers
    featurers = []
    if "Featurers" in profile and profile["Featurers"]:
        shortened_profile["Featurers"] = []

        featurers = profile["Featurers"]

        for index, featurer in enumerate(featurers):
            if featurer["Name"] in plugins_list:
                raise ConflictError(
                    f"Unable to create profile '{name}': Provided list of Featurers contains duplicates")

            if "ModelEndpoint" in featurer and isinstance(featurer["ModelEndpoint"], dict):
                featurers[index]["ModelEndpoint"] = get_model_endpoint_from_ddb(featurer["ModelEndpoint"])

            shortened_featurer = {
                "Name": featurer["Name"],
                "Configuration": featurer["Configuration"] if "Configuration" in featurer else {},
                "DependentPlugins": []
            }
            plugins_list.append(featurer["Name"])

            if featurer["Name"] not in d_plugins_list:
                batch_get_keys.append({"Name": featurer["Name"], "Version": "v0"})

            if "DependentPlugins" in featurer:
                for d_index, d_plugin in enumerate(featurer["DependentPlugins"]):
                    if "ModelEndpoint" in d_plugin and isinstance(d_plugin["ModelEndpoint"], dict):
                        featurers[index]["DependentPlugins"][d_index]["ModelEndpoint"] = get_model_endpoint_from_ddb(
                            d_plugin["ModelEndpoint"])

                    shortened_featurer["DependentPlugins"].append(
                        {
                            "Name": d_plugin["Name"],
                            "Configuration": d_plugin["Configuration"] if "Configuration" in d_plugin else {},
                        }
                    )

                    if d_plugin["Name"] not in d_plugins_list:
                        d_plugins_list.append(d_plugin["Name"])

                        if d_plugin["Name"] not in plugins_list:
                            batch_get_keys.append({"Name": d_plugin["Name"], "Version": "v0"})

            shortened_profile["Featurers"].append(shortened_featurer)

    # Retrieve the state machine definition of all the plugins present in the request
    response = ddb_resource.batch_get_item(
        RequestItems={
            PLUGIN_TABLE_NAME: {
                "Keys": batch_get_keys,
                "ConsistentRead": True,
                "ProjectionExpression": "#Name, #Class, #ExecutionType, #SupportedMediaType, #StateDefinition, #DependentPlugins, #Enabled, #Latest",
                "ExpressionAttributeNames": {
                    "#Name": "Name",
                    "#Class": "Class",
                    "#ExecutionType": "ExecutionType",
                    "#SupportedMediaType": "SupportedMediaType",
                    "#StateDefinition": "StateDefinition",
                    "#DependentPlugins": "DependentPlugins",
                    "#Enabled": "Enabled",
                    "#Latest": "Latest"
                }
            }
        }
    )

    responses = response["Responses"][PLUGIN_TABLE_NAME]

    while "UnprocessedKeys" in responses:
        response = ddb_resource.batch_get_item(
            RequestItems=responses["UnprocessedKeys"]
        )

        responses.extend(response["Responses"][PLUGIN_TABLE_NAME])

    plugin_definitions = {}

    for item in responses:
        plugin_definitions[item["Name"]] = {
            "Class": item["Class"],
            "ExecutionType": item["ExecutionType"],
            "SupportedMediaType": item["SupportedMediaType"],
            "StateDefinition": item["StateDefinition"],
            "DependentPlugins": item["DependentPlugins"] if "DependentPlugins" in item else [],
            "Enabled": item["Enabled"],
            "Latest": f"v{item['Latest']}"
        }

    # Check if any of the plugins present in the request does not exist or is disabled in the system
    for plugin in plugins_list:
        if plugin not in plugin_definitions:
            raise NotFoundError(f"Unable to create profile '{name}': Plugin '{plugin}' not found in the system")

        elif not plugin_definitions[plugin]["Enabled"]:
            raise BadRequestError(f"Unable to create profile '{name}': Plugin '{plugin}' is disabled in the system")

        else:
            for d_plugin in plugin_definitions[plugin]["DependentPlugins"]:
                if d_plugin not in d_plugins_list:
                    raise BadRequestError(
                        f"Unable to create profile '{name}': Required Dependent plugin '{d_plugin}' for plugin '{plugin}' not present in the request")

                elif d_plugin not in plugin_definitions:
                    raise NotFoundError(
                        f"Unable to create profile '{name}': Dependent plugin '{d_plugin}' for plugin '{plugin}' not found in the system")

                elif not plugin_definitions[d_plugin]["Enabled"]:
                    raise BadRequestError(
                        f"Unable to create profile '{name}': Dependent plugin '{d_plugin}' for plugin '{plugin}' is disabled in the system")

    # Add SupportedMediaType to all the DependentPlugins in the shortened_profile
    for index, d_plugin in enumerate(shortened_profile["Classifier"]["DependentPlugins"]):
        shortened_profile["Classifier"]["DependentPlugins"][index]["SupportedMediaType"] = \
            plugin_definitions[d_plugin["Name"]]["SupportedMediaType"]

    if "Optimizer" in shortened_profile:
        for index, d_plugin in enumerate(shortened_profile["Optimizer"]["DependentPlugins"]):
            shortened_profile["Optimizer"]["DependentPlugins"][index]["SupportedMediaType"] = \
                plugin_definitions[d_plugin["Name"]]["SupportedMediaType"]

    if "Labeler" in shortened_profile:
        for index, d_plugin in enumerate(shortened_profile["Labeler"]["DependentPlugins"]):
            shortened_profile["Labeler"]["DependentPlugins"][index]["SupportedMediaType"] = \
                plugin_definitions[d_plugin["Name"]]["SupportedMediaType"]

    if "Featurers" in shortened_profile:
        for p_index in range(len(shortened_profile["Featurers"])):
            for c_index, d_plugin in enumerate(shortened_profile["Featurers"][p_index]["DependentPlugins"]):
                shortened_profile["Featurers"][p_index]["DependentPlugins"][c_index]["SupportedMediaType"] = \
                    plugin_definitions[d_plugin["Name"]]["SupportedMediaType"]

    return (json.dumps(
        generate_profile_state_definition(name, classifier, optimizer, labeler, featurers, plugin_definitions,
                                          shortened_profile, internal_lambda_arns)), plugin_definitions)


@app.route('/profile', cors=True, methods=['POST'], authorizer=authorizer)
def create_profile():
    """
    Create a new processing profile. A processing profile is a logical grouping of:

        - One Classifier plugin
        - Zero or One Optimizer plugin
        - Zero or One Labeler plugin
        - Zero or More Featurer plugins

    Additionally, each of these plugins can optionally have one or more dependent plugins.

    Body:

    .. code-block:: python

        {
            "Name": string,
            "Description": string,
            "ContentGroups": list,
            "ChunkSize": number,
            "MaxSegmentLengthSeconds": number,
            "ProcessingFrameRate": number,
            "Classifier": {
                "Name": string,
                "ModelEndpoint": {
                    "Name": string,
                    "Version": string
                },
                "Configuration" : {
                    "configuration1": "value1",
                    ...
                },
                "DependentPlugins": [
                    {
                        "Name": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        }   
                    },
                    ...
                ]
            },
            "Optimizer": {
                "Name": string,
                "ModelEndpoint": {
                    "Name": string,
                    "Version": string
                },
                "Configuration" : {
                    "configuration1": "value1",
                    ...
                },
                "DependentPlugins": [
                    {
                        "Name": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        }   
                    },
                    ...
                ]
            },
            "Labeler": {
                "Name": string,
                "ModelEndpoint": {
                    "Name": string,
                    "Version": string
                },
                "Configuration" : {
                    "configuration1": "value1",
                    ...
                },
                "DependentPlugins": [
                    {
                        "Name": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        }   
                    },
                    ...
                ]
            },
            "Featurers": [
                {
                    "Name": string,
                    "ModelEndpoint": {
                        "Name": string,
                        "Version": string
                    },
                    "Configuration" : {
                        "configuration1": "value1",
                        ...
                    },
                    "DependentPlugins": [
                        {
                            "Name": string,
                            "ModelEndpoint": {
                                "Name": string,
                                "Version": string
                            },
                            "Configuration" : {
                                "configuration1": "value1",
                                ...
                            }   
                        },
                        ...
                    ]
                },
                ...
            ]
        }

    Parameters:

        - Name: Name of the Profile,
        - Description: Profile description
        - ContentGroups: List of Content Groups
        - ChunkSize: The size of the Video Chunk size represented by number of Frames in a Video Segment. 
        - MaxSegmentLengthSeconds: Length of a video segment in Seconds
        - ProcessingFrameRate: The video Frames/Sec used by MRE to perform analysis
        - Classifier: The Dict which represents a Classifier Plugin. Refer to the Plugin API for details on Plugin Parameters.
        - Featurers: A List of Featurer plugins. Each Dict which represents a Featurer Plugin. Refer to the Plugin API for details on Plugin Parameters.
        - Optimizer:The Dict which represents a Optimizer Plugin. Refer to the Plugin API for details on Plugin Parameters.
        - Labeler:The Dict which represents a Labeler Plugin. Refer to the Plugin API for details on Plugin Parameters.

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        409 - ConflictError
        500 - ChaliceViewError
    """
    try:
        profile = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=profile, schema=API_SCHEMA["create_profile"])

        print("Got a valid profile schema")

        name = profile["Name"]

        print(f"Creating the processing profile '{name}'")

        profile_copy = copy.deepcopy(profile)
        state_definition, plugin_definitions = profile_state_definition_helper(name, profile_copy)
        profile["StateDefinition"] = state_definition
        profile["Id"] = str(uuid.uuid4())
        profile["Created"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        profile["LastModified"] = profile["Created"]
        profile["Enabled"] = True

        sfn_name = f"aws-mre-{''.join(name.split())}-state-machine"

        print(f"Creating the StepFunction State Machine '{sfn_name}'")

        response = sfn_client.create_state_machine(
            name=sfn_name,
            definition=profile["StateDefinition"],
            roleArn=SFN_ROLE_ARN,
            type="STANDARD",
            tags=[
                {
                    "key": "Project",
                    "value": "MRE"
                },
                {
                    "key": "Profile",
                    "value": name
                }
            ],
            tracingConfiguration={
                "enabled": True
            }
        )

        profile["StateMachineArn"] = response["stateMachineArn"]

        # === Enrich profile by adding the latest version number of all the plugins provided in the profile ===
        # Classifier and its DependentPlugins
        profile["Classifier"]["Version"] = plugin_definitions[profile["Classifier"]["Name"]]["Latest"]

        if "DependentPlugins" in profile["Classifier"]:
            for index, d_plugin in enumerate(profile["Classifier"]["DependentPlugins"]):
                profile["Classifier"]["DependentPlugins"][index]["Version"] = plugin_definitions[d_plugin["Name"]]["Latest"]

        # Optimizer and its DependentPlugins
        if "Optimizer" in profile:
            profile["Optimizer"]["Version"] = plugin_definitions[profile["Optimizer"]["Name"]]["Latest"]

            if "DependentPlugins" in profile["Optimizer"]:
                for index, d_plugin in enumerate(profile["Optimizer"]["DependentPlugins"]):
                    profile["Optimizer"]["DependentPlugins"][index]["Version"] = plugin_definitions[d_plugin["Name"]]["Latest"]

        # Labeler and its DependentPlugins
        if "Labeler" in profile:
            profile["Labeler"]["Version"] = plugin_definitions[profile["Labeler"]["Name"]]["Latest"]

            if "DependentPlugins" in profile["Labeler"]:
                for index, d_plugin in enumerate(profile["Labeler"]["DependentPlugins"]):
                    profile["Labeler"]["DependentPlugins"][index]["Version"] = plugin_definitions[d_plugin["Name"]]["Latest"]

        # Featurers and their DependentPlugins
        if "Featurers" in profile:
            for p_index, featurer in enumerate(profile["Featurers"]):
                profile["Featurers"][p_index]["Version"] = plugin_definitions[featurer["Name"]]["Latest"]

                if "DependentPlugins" in featurer:
                    for c_index, d_plugin in enumerate(featurer["DependentPlugins"]):
                        profile["Featurers"][p_index]["DependentPlugins"][c_index]["Version"] = plugin_definitions[d_plugin["Name"]]["Latest"]
        # === End of enrichment ===

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)

        profile_table.put_item(
            Item=profile,
            ConditionExpression="attribute_not_exists(#Name)",
            ExpressionAttributeNames={
                "#Name": "Name"
            }
        )

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except BadRequestError as e:
        print(f"Got chalice BadRequestError: {str(e)}")
        raise

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except ConflictError as e:
        print(f"Got chalice ConflictError: {str(e)}")
        raise

    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ConflictError(f"Profile '{name}' already exists")
        else:
            raise

    except Exception as e:
        if "StateMachineArn" in profile:
            sfn_client.delete_state_machine(
                stateMachineArn=profile["StateMachineArn"]
            )

        print(f"Unable to create the processing profile: {str(e)}")
        raise ChaliceViewError(f"Unable to create the processing profile: {str(e)}")

    else:
        print(f"Successfully created the processing profile: {json.dumps(profile, cls=DecimalEncoder)}")

        return {}


@app.route('/profile/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_profiles():
    """
    List all the processing profiles.

    By default, return only the processing profiles that are "Enabled" in the system. In order 
    to also return the "Disabled" processing profiles, include the query parameter "include_disabled=true".

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string,
                    "Description": string,
                    "ContentGroups": list,
                    "ChunkSize": number,
                    "MaxSegmentLengthSeconds": number,
                    "ProcessingFrameRate": number,
                    "Classifier": {
                        "Name": string,
                        "Version": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentPlugins": [
                            {
                                "Name": string,
                                "Version": string,
                                "ModelEndpoint": {
                                    "Name": string,
                                    "Version": string
                                },
                                "Configuration" : {
                                    "configuration1": "value1",
                                    ...
                                }   
                            },
                            ...
                        ]
                    },
                    "Optimizer": {
                        "Name": string,
                        "Version": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentPlugins": [
                            {
                                "Name": string,
                                "Version": string,
                                "ModelEndpoint": {
                                    "Name": string,
                                    "Version": string
                                },
                                "Configuration" : {
                                    "configuration1": "value1",
                                    ...
                                }   
                            },
                            ...
                        ]
                    },
                    "Labeler": {
                        "Name": string,
                        "Version": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentPlugins": [
                            {
                                "Name": string,
                                "Version": string,
                                "ModelEndpoint": {
                                    "Name": string,
                                    "Version": string
                                },
                                "Configuration" : {
                                    "configuration1": "value1",
                                    ...
                                }   
                            },
                            ...
                        ]
                    },
                    "Featurers": [
                        {
                            "Name": string,
                            "Version": string,
                            "ModelEndpoint": {
                                "Name": string,
                                "Version": string
                            },
                            "Configuration" : {
                                "configuration1": "value1",
                                ...
                            },
                            "DependentPlugins": [
                                {
                                    "Name": string,
                                    "Version": string,
                                    "ModelEndpoint": {
                                        "Name": string,
                                        "Version": string
                                    },
                                    "Configuration" : {
                                        "configuration1": "value1",
                                        ...
                                    }   
                                },
                                ...
                            ]
                        },
                        ...
                    ],
                    "StateDefinition": string,
                    "Enabled": boolean,
                    "Id": uuid,
                    "Created": timestamp,
                    "LastModified": timestamp
                },
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        print("Listing all the processing profiles")

        query_params = app.current_request.query_params

        if query_params and query_params.get("include_disabled") == "true":
            filter_expression = Attr("Enabled").is_in([True, False])
        else:
            filter_expression = Attr("Enabled").eq(True)

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)

        response = profile_table.scan(
            FilterExpression=filter_expression,
            ConsistentRead=True
        )

        profiles = response["Items"]

        while "LastEvaluatedKey" in response:
            response = profile_table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                FilterExpression=filter_expression,
                ConsistentRead=True
            )

            profiles.extend(response["Items"])

    except Exception as e:
        print(f"Unable to list all the processing profiles: {str(e)}")
        raise ChaliceViewError(f"Unable to list all the processing profiles: {str(e)}")

    else:
        return replace_decimals(profiles)


@app.route('/profile/contentgroup/{content_group}/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_profiles_by_contentgroup(content_group):
    """
    List all the processing profiles by content group.

    By default, return only the processing profiles that are "Enabled" in the system. In order 
    to also return the "Disabled" processing profiles, include the query parameter "include_disabled=true".

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string,
                    "Description": string,
                    "ContentGroups": list,
                    "ChunkSize": number,
                    "MaxSegmentLengthSeconds": number,
                    "ProcessingFrameRate": number,
                    "Classifier": {
                        "Name": string,
                        "Version": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentPlugins": [
                            {
                                "Name": string,
                                "Version": string,
                                "ModelEndpoint": {
                                    "Name": string,
                                    "Version": string
                                },
                                "Configuration" : {
                                    "configuration1": "value1",
                                    ...
                                }   
                            },
                            ...
                        ]
                    },
                    "Optimizer": {
                        "Name": string,
                        "Version": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentPlugins": [
                            {
                                "Name": string,
                                "Version": string,
                                "ModelEndpoint": {
                                    "Name": string,
                                    "Version": string
                                },
                                "Configuration" : {
                                    "configuration1": "value1",
                                    ...
                                }   
                            },
                            ...
                        ]
                    },
                    "Labeler": {
                        "Name": string,
                        "Version": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentPlugins": [
                            {
                                "Name": string,
                                "Version": string,
                                "ModelEndpoint": {
                                    "Name": string,
                                    "Version": string
                                },
                                "Configuration" : {
                                    "configuration1": "value1",
                                    ...
                                }   
                            },
                            ...
                        ]
                    },
                    "Featurers": [
                        {
                            "Name": string,
                            "Version": string,
                            "ModelEndpoint": {
                                "Name": string,
                                "Version": string
                            },
                            "Configuration" : {
                                "configuration1": "value1",
                                ...
                            },
                            "DependentPlugins": [
                                {
                                    "Name": string,
                                    "Version": string,
                                    "ModelEndpoint": {
                                        "Name": string,
                                        "Version": string
                                    },
                                    "Configuration" : {
                                        "configuration1": "value1",
                                        ...
                                    }   
                                },
                                ...
                            ]
                        },
                        ...
                    ],
                    "StateDefinition": string,
                    "Enabled": boolean,
                    "Id": uuid,
                    "Created": timestamp,
                    "LastModified": timestamp
                },
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        content_group = urllib.parse.unquote(content_group)

        print(f"Listing all the processing profiles for content group '{content_group}'")

        query_params = app.current_request.query_params

        if query_params and query_params.get("include_disabled") == "true":
            filter_expression = Attr("Enabled").is_in([True, False])
        else:
            filter_expression = Attr("Enabled").eq(True)

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)

        response = profile_table.scan(
            FilterExpression=Attr("ContentGroups").contains(content_group) & filter_expression,
            ConsistentRead=True
        )

        profiles = response["Items"]

        while "LastEvaluatedKey" in response:
            response = profile_table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                FilterExpression=Attr("ContentGroups").contains(content_group) & filter_expression,
                ConsistentRead=True
            )

            profiles.extend(response["Items"])

    except Exception as e:
        print(f"Unable to list all the processing profiles for content group '{content_group}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to list all the processing profiles for content group '{content_group}': {str(e)}")

    else:
        return replace_decimals(profiles)


@app.route('/profile/{name}', cors=True, methods=['GET'], authorizer=authorizer)
def get_profile(name):
    """
    Get a processing profile by name.

    Returns:

        .. code-block:: python

            {
                "Name": string,
                "Description": string,
                "ContentGroups": list,
                "ChunkSize": number,
                "MaxSegmentLengthSeconds": number,
                "ProcessingFrameRate": number,
                "Classifier": {
                    "Name": string,
                    "Version": string,
                    "ModelEndpoint": {
                        "Name": string,
                        "Version": string
                    },
                    "Configuration" : {
                        "configuration1": "value1",
                        ...
                    },
                    "DependentPlugins": [
                        {
                            "Name": string,
                            "Version": string,
                            "ModelEndpoint": {
                                "Name": string,
                                "Version": string
                            },
                            "Configuration" : {
                                "configuration1": "value1",
                                ...
                            }   
                        },
                        ...
                    ]
                },
                "Optimizer": {
                    "Name": string,
                    "Version": string,
                    "ModelEndpoint": {
                        "Name": string,
                        "Version": string
                    },
                    "Configuration" : {
                        "configuration1": "value1",
                        ...
                    },
                    "DependentPlugins": [
                        {
                            "Name": string,
                            "Version": string,
                            "ModelEndpoint": {
                                "Name": string,
                                "Version": string
                            },
                            "Configuration" : {
                                "configuration1": "value1",
                                ...
                            }   
                        },
                        ...
                    ]
                },
                "Labeler": {
                    "Name": string,
                    "Version": string,
                    "ModelEndpoint": {
                        "Name": string,
                        "Version": string
                    },
                    "Configuration" : {
                        "configuration1": "value1",
                        ...
                    },
                    "DependentPlugins": [
                        {
                            "Name": string,
                            "Version": string,
                            "ModelEndpoint": {
                                "Name": string,
                                "Version": string
                            },
                            "Configuration" : {
                                "configuration1": "value1",
                                ...
                            }   
                        },
                        ...
                    ]
                },
                "Featurers": [
                    {
                        "Name": string,
                        "Version": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        },
                        "DependentPlugins": [
                            {
                                "Name": string,
                                "Version": string,
                                "ModelEndpoint": {
                                    "Name": string,
                                    "Version": string
                                },
                                "Configuration" : {
                                    "configuration1": "value1",
                                    ...
                                }   
                            },
                            ...
                        ]
                    },
                    ...
                ],
                "StateDefinition": string,
                "Enabled": boolean,
                "Id": uuid,
                "Created": timestamp,
                "LastModified": timestamp
            }

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)

        print(f"Getting the processing profile '{name}'")

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)

        response = profile_table.get_item(
            Key={
                "Name": name
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Profile '{name}' not found")

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to get the processing profile '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to get the processing profile '{name}': {str(e)}")

    else:
        return replace_decimals(response["Item"])


@app.route('/profile/{name}', cors=True, methods=['PUT'], authorizer=authorizer)
def update_profile(name):
    """
    Update a processing profile by name.

    Body:

    .. code-block:: python

        {
            "Description": string,
            "ContentGroups": list,
            "ChunkSize": number,
            "MaxSegmentLengthSeconds": number,
            "ProcessingFrameRate": number,
            "Classifier": {
                "Name": string,
                "ModelEndpoint": {
                    "Name": string,
                    "Version": string
                },
                "Configuration" : {
                    "configuration1": "value1",
                    ...
                },
                "DependentPlugins": [
                    {
                        "Name": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        }   
                    },
                    ...
                ]
            },
            "Optimizer": {
                "Name": string,
                "ModelEndpoint": {
                    "Name": string,
                    "Version": string
                },
                "Configuration" : {
                    "configuration1": "value1",
                    ...
                },
                "DependentPlugins": [
                    {
                        "Name": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        }   
                    },
                    ...
                ]
            },
            "Labeler": {
                "Name": string,
                "ModelEndpoint": {
                    "Name": string,
                    "Version": string
                },
                "Configuration" : {
                    "configuration1": "value1",
                    ...
                },
                "DependentPlugins": [
                    {
                        "Name": string,
                        "ModelEndpoint": {
                            "Name": string,
                            "Version": string
                        },
                        "Configuration" : {
                            "configuration1": "value1",
                            ...
                        }   
                    },
                    ...
                ]
            },
            "Featurers": [
                {
                    "Name": string,
                    "ModelEndpoint": {
                        "Name": string,
                        "Version": string
                    },
                    "Configuration" : {
                        "configuration1": "value1",
                        ...
                    },
                    "DependentPlugins": [
                        {
                            "Name": string,
                            "ModelEndpoint": {
                                "Name": string,
                                "Version": string
                            },
                            "Configuration" : {
                                "configuration1": "value1",
                                ...
                            }   
                        },
                        ...
                    ]
                },
                ...
            ]
        }

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        profile = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=profile, schema=API_SCHEMA["update_profile"])

        print("Got a valid profile schema")

        print(f"Updating the profile '{name}'")

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)

        response = profile_table.get_item(
            Key={
                "Name": name
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Profile '{name}' not found")

        profile["Description"] = profile["Description"] if "Description" in profile else (
            response["Item"]["Description"] if "Description" in response["Item"] else "")
        profile["ContentGroups"] = profile["ContentGroups"] if "ContentGroups" in profile else response["Item"][
            "ContentGroups"]
        profile["ChunkSize"] = profile["ChunkSize"] if "ChunkSize" in profile else response["Item"]["ChunkSize"]
        profile["MaxSegmentLengthSeconds"] = profile[
            "MaxSegmentLengthSeconds"] if "MaxSegmentLengthSeconds" in profile else response["Item"][
            "MaxSegmentLengthSeconds"]
        profile["ProcessingFrameRate"] = profile["ProcessingFrameRate"] if "ProcessingFrameRate" in profile else \
            response["Item"]["ProcessingFrameRate"]
        profile["Classifier"] = profile["Classifier"] if "Classifier" in profile else response["Item"]["Classifier"]
        profile["Optimizer"] = profile["Optimizer"] if "Optimizer" in profile else (
            response["Item"]["Optimizer"] if "Optimizer" in response["Item"] else {})
        profile["Featurers"] = profile["Featurers"] if "Featurers" in profile else (
            response["Item"]["Featurers"] if "Featurers" in response["Item"] else [])
        profile["Labeler"] = profile["Labeler"] if "Labeler" in profile else (
            response["Item"]["Labeler"] if "Labeler" in response["Item"] else {})

        state_definition, plugin_definitions = profile_state_definition_helper(name, replace_decimals(profile))
        profile["StateDefinition"] = state_definition

        # === Enrich profile by adding the latest version number of all the plugins provided in the profile ===
        # Classifier and its DependentPlugins
        profile["Classifier"]["Version"] = plugin_definitions[profile["Classifier"]["Name"]]["Latest"]

        if "DependentPlugins" in profile["Classifier"]:
            for index, d_plugin in enumerate(profile["Classifier"]["DependentPlugins"]):
                profile["Classifier"]["DependentPlugins"][index]["Version"] = plugin_definitions[d_plugin["Name"]]["Latest"]

        # Optimizer and its DependentPlugins
        if "Optimizer" in profile and profile["Optimizer"]:
            profile["Optimizer"]["Version"] = plugin_definitions[profile["Optimizer"]["Name"]]["Latest"]

            if "DependentPlugins" in profile["Optimizer"]:
                for index, d_plugin in enumerate(profile["Optimizer"]["DependentPlugins"]):
                    profile["Optimizer"]["DependentPlugins"][index]["Version"] = plugin_definitions[d_plugin["Name"]]["Latest"]

        # Labeler and its DependentPlugins
        if "Labeler" in profile and profile["Labeler"]:
            profile["Labeler"]["Version"] = plugin_definitions[profile["Labeler"]["Name"]]["Latest"]

            if "DependentPlugins" in profile["Labeler"]:
                for index, d_plugin in enumerate(profile["Labeler"]["DependentPlugins"]):
                    profile["Labeler"]["DependentPlugins"][index]["Version"] = plugin_definitions[d_plugin["Name"]]["Latest"]

        # Featurers and their DependentPlugins
        if "Featurers" in profile and profile["Featurers"]:
            for p_index, featurer in enumerate(profile["Featurers"]):
                profile["Featurers"][p_index]["Version"] = plugin_definitions[featurer["Name"]]["Latest"]

                if "DependentPlugins" in featurer:
                    for c_index, d_plugin in enumerate(featurer["DependentPlugins"]):
                        profile["Featurers"][p_index]["DependentPlugins"][c_index]["Version"] = plugin_definitions[d_plugin["Name"]]["Latest"]
        # === End of enrichment ===

        # Update the Step Function State Machine
        state_machine_arn = response["Item"]["StateMachineArn"]

        print(f"Updating the StepFunction State Machine '{state_machine_arn}'")

        sfn_client.update_state_machine(
            stateMachineArn=state_machine_arn,
            definition=profile["StateDefinition"]
        )

        profile_table.update_item(
            Key={
                "Name": name
            },
            UpdateExpression="SET #Description = :Description, #ContentGroups = :ContentGroups, #ChunkSize = :ChunkSize, #MaxSegmentLengthSeconds = :MaxSegmentLengthSeconds, #ProcessingFrameRate = :ProcessingFrameRate, #Classifier = :Classifier, #Optimizer = :Optimizer, #Featurers = :Featurers, #Labeler = :Labeler, #StateDefinition = :StateDefinition, #LastModified = :LastModified",
            ExpressionAttributeNames={
                "#Description": "Description",
                "#ContentGroups": "ContentGroups",
                "#ChunkSize": "ChunkSize",
                "#MaxSegmentLengthSeconds": "MaxSegmentLengthSeconds",
                "#ProcessingFrameRate": "ProcessingFrameRate",
                "#Classifier": "Classifier",
                "#Optimizer": "Optimizer",
                "#Featurers": "Featurers",
                "#Labeler": "Labeler",
                "#StateDefinition": "StateDefinition",
                "#LastModified": "LastModified"
            },
            ExpressionAttributeValues={
                ":Description": profile["Description"],
                ":ContentGroups": profile["ContentGroups"],
                ":ChunkSize": profile["ChunkSize"],
                ":MaxSegmentLengthSeconds": profile["MaxSegmentLengthSeconds"],
                ":ProcessingFrameRate": profile["ProcessingFrameRate"],
                ":Classifier": profile["Classifier"],
                ":Optimizer": profile["Optimizer"],
                ":Featurers": profile["Featurers"],
                ":Labeler": profile["Labeler"],
                ":StateDefinition": profile["StateDefinition"],
                ":LastModified": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            }
        )

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to update the profile '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to update the profile '{name}': {str(e)}")

    else:
        print(f"Successfully updated the profile: {json.dumps(profile, cls=DecimalEncoder)}")

        return {}


@app.route('/profile/{name}/status', cors=True, methods=['PUT'], authorizer=authorizer)
def update_profile_status(name):
    """
    Enable or Disable a processing profile by name.

    Body:

    .. code-block:: python

        {
            "Enabled": boolean
        }

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        status = json.loads(app.current_request.raw_body.decode())

        validate(instance=status, schema=API_SCHEMA["update_status"])

        print("Got a valid status schema")

        print(f"Updating the status of the profile '{name}'")

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)

        profile_table.update_item(
            Key={
                "Name": name
            },
            UpdateExpression="SET #Enabled = :Status",
            ConditionExpression="attribute_exists(#Name)",
            ExpressionAttributeNames={
                "#Enabled": "Enabled",
                "#Name": "Name"
            },
            ExpressionAttributeValues={
                ":Status": status["Enabled"]
            }
        )

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise NotFoundError(f"Profile '{name}' not found")
        else:
            raise

    except Exception as e:
        print(f"Unable to update the status of the profile '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to update the status of the profile '{name}': {str(e)}")

    else:
        return {}


@app.route('/profile/{name}', cors=True, methods=['DELETE'], authorizer=authorizer)
def delete_profile(name):
    """
    Delete a processing profile by name.

    Returns:

        None

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)

        print(f"Deleting the profile '{name}'")

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)

        response = profile_table.delete_item(
            Key={
                "Name": name
            },
            ReturnValues="ALL_OLD"
        )

        if "Attributes" not in response:
            raise NotFoundError(f"Profile '{name}' not found")

        # Delete the Step Function State Machine
        state_machine_arn = response["Attributes"]["StateMachineArn"]

        print(f"Deleting the StepFunction State Machine '{state_machine_arn}'")

        sfn_client.delete_state_machine(
            stateMachineArn=state_machine_arn
        )

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to delete the profile '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to delete the profile '{name}': {str(e)}")

    else:
        print(f"Deletion of profile '{name}' successful")
        return {}


#############################################################
#                                                           #
#                         MODELS                            #
#                                                           #
#############################################################

@app.route('/model', cors=True, methods=['POST'], authorizer=authorizer)
def register_model():
    """
    Register a new Machine Learning (ML) model endpoint or publish a new version of an 
    existing model endpoint.
    
    Body:

    .. code-block:: python

        {
            "Name": string,
            "Description": string,
            "ContentGroups": list,
            "Endpoint": string,
            "PluginClass": ["Classifier"|"Optimizer"|"Featurer"|"Labeler"]
        }
    
    Parameters:

        - Name: Name of the Machine Learning (ML) Model
        - Description: Description of the Machine Learning (ML) Model
        - ContentGroups: List of Content Groups this Machine Learning (ML) Model is used for
        - Endpoint: ARN of the Machine Learning (ML) model endpoint. For example ARN of rekognition custom label project endpoint or Sagemaker Endpoint
        - PluginClass: One of "Classifier"|"Optimizer"|"Featurer"|"Labeler"

    Returns:

        A dict containing the Name and Version of the registered model

        .. code-block:: python

            {
                "Name": string,
                "Version": string
            }

    Raises:
        400 - BadRequestError
        500 - ChaliceViewError
    """
    try:
        model = json.loads(app.current_request.raw_body.decode())

        validate(instance=model, schema=API_SCHEMA["register_model"])

        print("Got a valid model schema")

        name = model["Name"]

        model_table = ddb_resource.Table(MODEL_TABLE_NAME)

        response = model_table.get_item(
            Key={
                "Name": name,
                "Version": "v0"
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            print(f"Registering a new model endpoint '{name}'")
            latest_version = 0
            higher_version = 1

        else:
            print(f"Publishing a new version of the model endpoint '{name}'")
            latest_version = response["Item"]["Latest"]
            higher_version = int(latest_version) + 1

        model["Created"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        model["Enabled"] = True

        # Serialize Python object to DynamoDB object
        serialized_model = {k: serializer.serialize(v) for k, v in model.items()}

        ddb_client.transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": MODEL_TABLE_NAME,
                        "Key": {
                            "Name": {"S": name},
                            "Version": {"S": "v0"}
                        },
                        "ConditionExpression": "attribute_not_exists(#Latest) OR #Latest = :Latest",
                        "UpdateExpression": "SET #Latest = :Higher_version, #Description = :Description, #ContentGroups = :ContentGroups, #Endpoint = :Endpoint, #PluginClass = :PluginClass, #Created = :Created, #Enabled = :Enabled",
                        "ExpressionAttributeNames": {
                            "#Latest": "Latest",
                            "#Description": "Description",
                            "#ContentGroups": "ContentGroups",
                            "#Endpoint": "Endpoint",
                            "#PluginClass": "PluginClass",
                            "#Created": "Created",
                            "#Enabled": "Enabled"
                        },
                        "ExpressionAttributeValues": {
                            ":Latest": {"N": str(latest_version)},
                            ":Higher_version": {"N": str(higher_version)},
                            ":Description": serialized_model["Description"] if "Description" in serialized_model else {
                                "S": ""},
                            ":ContentGroups": serialized_model["ContentGroups"],
                            ":Endpoint": serialized_model["Endpoint"],
                            ":PluginClass": serialized_model["PluginClass"],
                            ":Created": serialized_model["Created"],
                            ":Enabled": serialized_model["Enabled"]
                        }
                    }
                },
                {
                    "Put": {
                        "TableName": MODEL_TABLE_NAME,
                        "Item": {
                            "Name": {"S": name},
                            "Version": {"S": "v" + str(higher_version)},
                            "Description": serialized_model["Description"] if "Description" in serialized_model else {
                                "S": ""},
                            "ContentGroups": serialized_model["ContentGroups"],
                            "Endpoint": serialized_model["Endpoint"],
                            "PluginClass": serialized_model["PluginClass"],
                            "Created": serialized_model["Created"],
                            "Enabled": serialized_model["Enabled"]
                        }
                    }
                }
            ]
        )

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except Exception as e:
        print(f"Unable to register or publish a new version of the Machine Learning model endpoint: {str(e)}")
        raise ChaliceViewError(
            f"Unable to register or publish a new version of the Machine Learning model endpoint: {str(e)}")

    else:
        print(
            f"Successfully registered or published a new version of the Machine Learning model endpoint: {json.dumps(model)}")

        return {
            "Name": model["Name"],
            "Version": "v" + str(higher_version)
        }


@app.route('/model/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_models():
    """
    List the latest version of all the registered Machine Learning models.
    Each model has version "v0" which holds a copy of the latest model revision.

    By default, return only the model endpoints that are "Enabled" in the system. In order 
    to also return the "Disabled" model endpoints, include the query parameter "include_disabled=true".

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string,
                    "Description": string,
                    "ContentGroups": list,
                    "Endpoint": string,
                    "PluginClass": ["Classifier"|"Optimizer"|"Featurer"|"Labeler"],
                    "Version": string,
                    "Created": timestamp,
                    "Latest": number,
                    "Enabled": boolean
                },
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        print("Listing the latest version of all the Machine Learning model endpoints")

        query_params = app.current_request.query_params

        if query_params and query_params.get("include_disabled") == "true":
            filter_expression = Attr("Enabled").is_in([True, False])
        else:
            filter_expression = Attr("Enabled").eq(True)

        model_table = ddb_resource.Table(MODEL_TABLE_NAME)

        response = model_table.query(
            IndexName=MODEL_VERSION_INDEX,
            KeyConditionExpression=Key("Version").eq("v0"),
            FilterExpression=filter_expression
        )

        models = response["Items"]

        while "LastEvaluatedKey" in response:
            response = model_table.query(
                IndexName=MODEL_VERSION_INDEX,
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("Version").eq("v0"),
                FilterExpression=filter_expression
            )

            models.extend(response["Items"])

    except Exception as e:
        print(f"Unable to list the latest version of all the Machine Learning model endpoints: {str(e)}")
        raise ChaliceViewError(
            f"Unable to list the latest version of all the Machine Learning model endpoints: {str(e)}")

    else:
        return replace_decimals(models)


@app.route('/model/pluginclass/{plugin_class}/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_models_by_pluginclass(plugin_class):
    """
    List the latest version of all the registered Machine Learning models by plugin class.
    Each model has version "v0" which holds a copy of the latest model revision.

    By default, return only the model endpoints that are "Enabled" in the system. In order 
    to also return the "Disabled" model endpoints, include the query parameter "include_disabled=true".

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string,
                    "Description": string,
                    "ContentGroups": list,
                    "Endpoint": string,
                    "PluginClass": ["Classifier"|"Optimizer"|"Featurer"|"Labeler"],
                    "Version": string,
                    "Created": timestamp,
                    "Latest": number,
                    "Enabled": boolean
                },
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        plugin_class = urllib.parse.unquote(plugin_class)

        print(
            f"Listing the latest version of all the Machine Learning model endpoints for plugin class '{plugin_class}'")

        query_params = app.current_request.query_params

        if query_params and query_params.get("include_disabled") == "true":
            filter_expression = Attr("Enabled").is_in([True, False])
        else:
            filter_expression = Attr("Enabled").eq(True)

        model_table = ddb_resource.Table(MODEL_TABLE_NAME)

        response = model_table.query(
            IndexName=MODEL_VERSION_INDEX,
            KeyConditionExpression=Key("Version").eq("v0"),
            FilterExpression=Attr("PluginClass").eq(plugin_class) & filter_expression
        )

        models = response["Items"]

        while "LastEvaluatedKey" in response:
            response = model_table.query(
                IndexName=MODEL_VERSION_INDEX,
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("Version").eq("v0"),
                FilterExpression=Attr("PluginClass").eq(plugin_class) & filter_expression
            )

            models.extend(response["Items"])

    except Exception as e:
        print(
            f"Unable to list the latest version of all the Machine Learning model endpoints for plugin class '{plugin_class}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to list the latest version of all the Machine Learning model endpoints for plugin class '{plugin_class}': {str(e)}")

    else:
        return replace_decimals(models)


@app.route('/model/contentgroup/{content_group}/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_models_by_contentgroup(content_group):
    """
    List the latest version of all the registered Machine Learning models by content group.
    Each model has version "v0" which holds a copy of the latest model revision.

    By default, return only the model endpoints that are "Enabled" in the system. In order 
    to also return the "Disabled" model endpoints, include the query parameter "include_disabled=true".

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string,
                    "Description": string,
                    "ContentGroups": list,
                    "Endpoint": string,
                    "PluginClass": ["Classifier"|"Optimizer"|"Featurer"|"Labeler"],
                    "Version": string,
                    "Created": timestamp,
                    "Latest": number,
                    "Enabled": boolean
                },
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        content_group = urllib.parse.unquote(content_group)

        print(
            f"Listing the latest version of all the Machine Learning model endpoints for content group '{content_group}'")

        query_params = app.current_request.query_params

        if query_params and query_params.get("include_disabled") == "true":
            filter_expression = Attr("Enabled").is_in([True, False])
        else:
            filter_expression = Attr("Enabled").eq(True)

        model_table = ddb_resource.Table(MODEL_TABLE_NAME)

        response = model_table.query(
            IndexName=MODEL_VERSION_INDEX,
            KeyConditionExpression=Key("Version").eq("v0"),
            FilterExpression=Attr("ContentGroups").contains(content_group) & filter_expression
        )

        models = response["Items"]

        while "LastEvaluatedKey" in response:
            response = model_table.query(
                IndexName=MODEL_VERSION_INDEX,
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("Version").eq("v0"),
                FilterExpression=Attr("ContentGroups").contains(content_group) & filter_expression
            )

            models.extend(response["Items"])

    except Exception as e:
        print(
            f"Unable to list the latest version of all the Machine Learning model endpoints for content group '{content_group}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to list the latest version of all the Machine Learning model endpoints for content group '{content_group}': {str(e)}")

    else:
        return replace_decimals(models)


@app.route('/model/pluginclass/{plugin_class}/contentgroup/{content_group}/all', cors=True, methods=['GET'],
           authorizer=authorizer)
def list_models_by_pluginclass_and_contentgroup(plugin_class, content_group):
    """
    List the latest version of all the registered Machine Learning models by plugin class and content group.
    Each model has version "v0" which holds a copy of the latest model revision.

    By default, return only the model endpoints that are "Enabled" in the system. In order 
    to also return the "Disabled" model endpoints, include the query parameter "include_disabled=true".

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string,
                    "Description": string,
                    "ContentGroups": list,
                    "Endpoint": string,
                    "PluginClass": ["Classifier"|"Optimizer"|"Featurer"|"Labeler"],
                    "Version": string,
                    "Created": timestamp,
                    "Latest": number,
                    "Enabled": boolean
                },
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        plugin_class = urllib.parse.unquote(plugin_class)
        content_group = urllib.parse.unquote(content_group)

        print(
            f"Listing all the Machine Learning model endpoints for plugin class '{plugin_class}' and content group '{content_group}'")

        query_params = app.current_request.query_params

        if query_params and query_params.get("include_disabled") == "true":
            filter_expression = Attr("Enabled").is_in([True, False])
        else:
            filter_expression = Attr("Enabled").eq(True)

        model_table = ddb_resource.Table(MODEL_TABLE_NAME)

        response = model_table.query(
            IndexName=MODEL_VERSION_INDEX,
            KeyConditionExpression=Key("Version").eq("v0"),
            FilterExpression=Attr("PluginClass").eq(plugin_class) & Attr("ContentGroups").contains(
                content_group) & filter_expression
        )

        models = response["Items"]

        while "LastEvaluatedKey" in response:
            response = model_table.query(
                IndexName=MODEL_VERSION_INDEX,
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("Version").eq("v0"),
                FilterExpression=Attr("PluginClass").eq(plugin_class) & Attr("ContentGroups").contains(
                    content_group) & filter_expression
            )

            models.extend(response["Items"])

    except Exception as e:
        print(
            f"Unable to list the latest version of all the Machine Learning model endpoints for plugin class '{plugin_class}' and content group '{content_group}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to list the latest version of all the Machine Learning model endpoints for plugin class '{plugin_class}' and content group '{content_group}': {str(e)}")

    else:
        return replace_decimals(models)


@app.route('/model/{name}', cors=True, methods=['GET'], authorizer=authorizer)
def get_model_by_name(name):
    """
    Get the latest version of a Machine Learning model endpoint by name.

    Returns:

        .. code-block:: python

            {
                "Name": string,
                "Description": string,
                "ContentGroups": list,
                "Endpoint": string,
                "PluginClass": ["Classifier"|"Optimizer"|"Featurer"|"Labeler"],
                "Version": string,
                "Created": timestamp,
                "Latest": number,
                "Enabled": boolean
            }

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)

        print(f"Getting the latest version of the Machine Learning model endpoint '{name}'")

        model_table = ddb_resource.Table(MODEL_TABLE_NAME)

        response = model_table.get_item(
            Key={
                "Name": name,
                "Version": "v0"
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Machine Learning model endpoint '{name}' not found")

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to get the latest version of the Machine Learning model endpoint '{name}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to get the latest version of the Machine Learning model endpoint '{name}': {str(e)}")

    else:
        return replace_decimals(response["Item"])


@app.route('/model/{name}/version/{version}', cors=True, methods=['GET'], authorizer=authorizer)
def get_model_by_name_and_version(name, version):
    """
    Get a Machine Learning model endpoint by name and version.

    Returns:

        .. code-block:: python

            {
                "Name": string,
                "Description": string,
                "ContentGroups": list,
                "Endpoint": string,
                "PluginClass": ["Classifier"|"Optimizer"|"Featurer"|"Labeler"],
                "Version": string,
                "Created": timestamp,
                "Latest": number,
                "Enabled": boolean
            }

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        version = urllib.parse.unquote(version)

        print(f"Getting the Machine Learning model endpoint '{name}' with version '{version}'")

        model_table = ddb_resource.Table(MODEL_TABLE_NAME)

        response = model_table.get_item(
            Key={
                "Name": name,
                "Version": version
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Machine Learning model endpoint '{name}' with version '{version}' not found")

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to get the Machine Learning model endpoint '{name}' with version '{version}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to get the Machine Learning model endpoint '{name}' with version '{version}': {str(e)}")

    else:
        return replace_decimals(response["Item"])


@app.route('/model/{name}/version/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_model_versions(name):
    """
    List all the versions of a Machine Learning model endpoint by name.

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string,
                    "Description": string,
                    "ContentGroups": list,
                    "Endpoint": string,
                    "PluginClass": ["Classifier"|"Optimizer"|"Featurer"|"Labeler"],
                    "Version": string,
                    "Created": timestamp,
                    "Latest": number,
                    "Enabled": boolean
                },
                ...
            ]

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)

        print(f"Getting all the versions of the model '{name}'")

        model_table = ddb_resource.Table(MODEL_TABLE_NAME)

        response = model_table.query(
            IndexName=MODEL_NAME_INDEX,
            KeyConditionExpression=Key("Name").eq(name)
        )

        if "Items" not in response or len(response["Items"]) < 1:
            raise NotFoundError(f"Machine Learning model '{name}' not found")

        versions = response["Items"]

        while "LastEvaluatedKey" in response:
            response = model_table.query(
                IndexName=MODEL_NAME_INDEX,
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("Name").eq(name)
            )

            versions.extend(response["Items"])

        # Remove version 'v0' from the query result
        for index, version in enumerate(versions):
            if version["Version"] == "v0":
                versions.pop(index)
                break

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to list the versions of the Machine Learning model '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to list the versions of the Machine Learning model '{name}': {str(e)}")

    else:
        return replace_decimals(versions)


@app.route('/model/{name}/status', cors=True, methods=['PUT'], authorizer=authorizer)
def update_model_status(name):
    """
    Enable or Disable the latest version of a Machine Learning model endpoint by name.

    Body:

    .. code-block:: python

        {
            "Enabled": boolean
        }

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        status = json.loads(app.current_request.raw_body.decode())

        validate(instance=status, schema=API_SCHEMA["update_status"])

        print("Got a valid status schema")

        print(f"Updating the status of the latest version of Machine Learning model endpoint '{name}'")

        model_table = ddb_resource.Table(MODEL_TABLE_NAME)

        response = model_table.get_item(
            Key={
                "Name": name,
                "Version": "v0"
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Model endpoint '{name}' not found")

        latest_version = "v" + str(response["Item"]["Latest"])

        # Update version v0
        model_table.update_item(
            Key={
                "Name": name,
                "Version": "v0"
            },
            UpdateExpression="SET #Enabled = :Status",
            ExpressionAttributeNames={
                "#Enabled": "Enabled"
            },
            ExpressionAttributeValues={
                ":Status": status["Enabled"]
            }
        )

        # Update the latest version
        model_table.update_item(
            Key={
                "Name": name,
                "Version": latest_version
            },
            UpdateExpression="SET #Enabled = :Status",
            ConditionExpression="attribute_exists(#Name) AND attribute_exists(#Version)",
            ExpressionAttributeNames={
                "#Enabled": "Enabled",
                "#Name": "Name",
                "#Version": "Version"
            },
            ExpressionAttributeValues={
                ":Status": status["Enabled"]
            }
        )

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise NotFoundError(
                f"Machine Learning model endpoint '{name}' with latest version '{latest_version}' not found")
        else:
            raise

    except Exception as e:
        print(
            f"Unable to update the status of the latest version of Machine Learning model endpoint '{name}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to update the status of the latest version of Machine Learning model endpoint '{name}': {str(e)}")

    else:
        return {}


@app.route('/model/{name}/version/{version}/status', cors=True, methods=['PUT'], authorizer=authorizer)
def update_model_version_status(name, version):
    """
    Enable or Disable a Machine Learning model endpoint by name and version.

    Body:

    .. code-block:: python

        {
            "Enabled": boolean
        }

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        version = urllib.parse.unquote(version)
        status = json.loads(app.current_request.raw_body.decode())

        validate(instance=status, schema=API_SCHEMA["update_status"])

        print("Got a valid status schema")

        print(f"Updating the status of the Machine Learning model endpoint '{name}' with version '{version}'")

        model_table = ddb_resource.Table(MODEL_TABLE_NAME)

        model_table.update_item(
            Key={
                "Name": name,
                "Version": version
            },
            UpdateExpression="SET #Enabled = :Status",
            ConditionExpression="attribute_exists(#Name) AND attribute_exists(#Version)",
            ExpressionAttributeNames={
                "#Enabled": "Enabled",
                "#Name": "Name",
                "#Version": "Version"
            },
            ExpressionAttributeValues={
                ":Status": status["Enabled"]
            }
        )

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise NotFoundError(f"Machine Learning model endpoint '{name}' with version '{version}' not found")
        else:
            raise

    except Exception as e:
        print(
            f"Unable to update the status of the Machine Learning model endpoint '{name}' with version '{version}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to update the status of the Machine Learning model endpoint '{name}' with version '{version}': {str(e)}")

    else:
        return {}


@app.route('/model/{name}', cors=True, methods=['DELETE'], authorizer=authorizer)
def delete_model(name):
    """
    Delete all the versions of a Machine Learning model endpoint by name.

    Returns:

        None

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)

        print(f"Deleting the Machine Learning model endpoint '{name}' and all its versions")

        model_table = ddb_resource.Table(MODEL_TABLE_NAME)

        response = model_table.query(
            IndexName=MODEL_NAME_INDEX,
            KeyConditionExpression=Key("Name").eq(name)
        )

        if "Items" not in response or len(response["Items"]) < 1:
            raise NotFoundError(f"Machine Learning model endpoint '{name}' not found")

        versions = response["Items"]

        while "LastEvaluatedKey" in response:
            response = model_table.query(
                IndexName=MODEL_NAME_INDEX,
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("Name").eq(name)
            )

            versions.extend(response["Items"])

        with model_table.batch_writer() as batch:
            for item in versions:
                batch.delete_item(
                    Key={
                        "Name": item["Name"],
                        "Version": item["Version"]
                    }
                )

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to delete the Machine Learning model endpoint '{name}' and its versions: {str(e)}")
        raise ChaliceViewError(
            f"Unable to delete the Machine Learning model endpoint '{name}' and its versions: {str(e)}")

    else:
        print(f"Deletion of Machine Learning model endpoint '{name}' and its versions successful")
        return {}


@app.route('/model/{name}/version/{version}', cors=True, methods=['DELETE'], authorizer=authorizer)
def delete_model_version(name, version):
    """
    Delete a specific version of a Machine Learning model endpoint by name and version.

    Deletion can be performed on all the model versions except "v0" and the latest model revision.
    If the latest model version needs to be deleted, publish a new version of the model and then
    delete the prior model version.

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        version = urllib.parse.unquote(version)

        model_table = ddb_resource.Table(MODEL_TABLE_NAME)

        response = model_table.get_item(
            Key={
                "Name": name,
                "Version": "v0"
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Machine Learning model '{name}' not found")

        latest_version = "v" + str(response["Item"]["Latest"])

        print(f"Deleting version '{version}' of the model '{name}'")

        response = model_table.delete_item(
            Key={
                "Name": name,
                "Version": version
            },
            ConditionExpression="NOT (#Version IN (:Value1, :Value2))",
            ExpressionAttributeNames={
                "#Version": "Version"
            },
            ExpressionAttributeValues={
                ":Value1": "v0",
                ":Value2": latest_version
            },
            ReturnValues="ALL_OLD"
        )

        if "Attributes" not in response:
            raise NotFoundError(f"Machine Learning model '{name}' with version '{version}' not found")

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            if version == "v0":
                raise BadRequestError("Deletion of version 'v0' of the model is prohibited")
            raise BadRequestError(
                f"Deletion of version '{version}' of the model is blocked as it is the latest model revision. Publish a new version to unblock the deletion of version '{version}'")

        else:
            raise

    except Exception as e:
        print(f"Unable to delete version '{version}' of the Machine Learning model '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to delete version '{version}' of the Machine Learning model '{name}': {str(e)}")

    else:
        print(f"Deletion of version '{version}' of the Machine Learning model '{name}' successful")
        return {}


#############################################################
#                                                           #
#                         EVENTS                            #
#                                                           #
#############################################################

def add_or_update_medialive_output_group(name, program, profile, channel_id):
    print(
        f"Describing the MediaLive channel '{channel_id}' to get existing InputAttachments, Destinations, and EncoderSettings")

    try:
        response = medialive_client.describe_channel(
            ChannelId=channel_id
        )

        if response["State"] != "IDLE":
            raise BadRequestError(f"MediaLive channel '{channel_id}' is not in 'IDLE' state")

        last_known_medialive_config = response
        input_attachments = response["InputAttachments"]
        destinations = response["Destinations"]
        encoder_settings = response["EncoderSettings"]

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)

        response = profile_table.get_item(
            Key={
                "Name": profile
            },
            ProjectionExpression="#Name, #ChunkSize",
            ExpressionAttributeNames={
                "#Name": "Name",
                "#ChunkSize": "ChunkSize"
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Profile '{profile}' not found")

        chunk_size = response["Item"]["ChunkSize"]

        is_destination_create = True

        for index, destination in enumerate(destinations):
            if destination["Id"] == "awsmre":
                print(f"Updating the existing MRE destination present in the MediaLive channel '{channel_id}'")
                destinations[index]["Settings"][0][
                    "Url"] = f"s3ssl://{MEDIALIVE_S3_BUCKET}/{channel_id}/{program}/{name}/{profile}/{program}_{name}"
                is_destination_create = False
                break

        if is_destination_create:
            print(f"Creating a new destination for MRE in the MediaLive channel '{channel_id}'")

            mre_destination = {
                "Id": "awsmre",
                "Settings": [
                    {
                        "Url": f"s3ssl://{MEDIALIVE_S3_BUCKET}/{channel_id}/{program}/{name}/{profile}/{program}_{name}"
                    }
                ]
            }

            # Append MRE destination to the existing channel destinations
            destinations.append(mre_destination)

        audio_descriptions = encoder_settings["AudioDescriptions"] if "AudioDescriptions" in encoder_settings else []

        if not audio_descriptions:
            # At this time, MRE automatically picks the first input attached to the MediaLive channel 
            # to get the AudioSelectors information. In a future update, this input picking could be user driven
            audio_selectors = input_attachments[0]["InputSettings"]["AudioSelectors"] if "AudioSelectors" in \
                                                                                         input_attachments[0][
                                                                                             "InputSettings"] else []
            audio_selectors_name_list = [audio_selector["Name"] for audio_selector in audio_selectors]

            for audio_selector_name in audio_selectors_name_list:
                audio_descriptions.append(
                    {
                        "AudioSelectorName": audio_selector_name,
                        "AudioTypeControl": "FOLLOW_INPUT",
                        "LanguageCodeControl": "FOLLOW_INPUT",
                        "Name": f"audio_{uuid.uuid4().hex}"
                    }
                )

            # Include AudioDescriptions in the EncoderSettings
            encoder_settings["AudioDescriptions"] = audio_descriptions

        audio_description_name_list = [audio_description["Name"] for audio_description in audio_descriptions]

        output_groups = encoder_settings["OutputGroups"]
        is_new_output_group = True

        for index, output_group in enumerate(output_groups):
            if "HlsGroupSettings" in output_group["OutputGroupSettings"] and \
                    output_group["OutputGroupSettings"]["HlsGroupSettings"]["Destination"][
                        "DestinationRefId"] == "awsmre":
                print(f"Updating the existing OutputGroup for MRE in the MediaLive channel '{channel_id}'")

                output_groups[index]["OutputGroupSettings"]["HlsGroupSettings"]["SegmentLength"] = int(chunk_size)
                output_groups[index]["OutputGroupSettings"]["HlsGroupSettings"]["ProgramDateTimePeriod"] = int(
                    chunk_size)

                output_groups[index]["Outputs"][0]["AudioDescriptionNames"] = audio_description_name_list

                is_new_output_group = False
                break

        if is_new_output_group:
            mre_output_group = {
                "OutputGroupSettings": {
                    "HlsGroupSettings": {
                        "AdMarkers": [],
                        "CaptionLanguageMappings": [],
                        "CaptionLanguageSetting": "OMIT",
                        "ClientCache": "ENABLED",
                        "CodecSpecification": "RFC_4281",
                        "Destination": {
                            "DestinationRefId": "awsmre"
                        },
                        "DirectoryStructure": "SINGLE_DIRECTORY",
                        "DiscontinuityTags": "INSERT",
                        "HlsId3SegmentTagging": "DISABLED",
                        "IFrameOnlyPlaylists": "DISABLED",
                        "IncompleteSegmentBehavior": "AUTO",
                        "IndexNSegments": 10,
                        "InputLossAction": "PAUSE_OUTPUT",
                        "IvInManifest": "INCLUDE",
                        "IvSource": "FOLLOWS_SEGMENT_NUMBER",
                        "KeepSegments": 21,
                        "ManifestCompression": "NONE",
                        "ManifestDurationFormat": "FLOATING_POINT",
                        "Mode": "VOD",
                        "OutputSelection": "VARIANT_MANIFESTS_AND_SEGMENTS",
                        "ProgramDateTime": "INCLUDE",
                        "ProgramDateTimePeriod": int(chunk_size),
                        "RedundantManifest": "DISABLED",
                        "SegmentLength": int(chunk_size),
                        "SegmentationMode": "USE_SEGMENT_DURATION",
                        "SegmentsPerSubdirectory": 10000,
                        "StreamInfResolution": "INCLUDE",
                        "TimedMetadataId3Frame": "PRIV",
                        "TimedMetadataId3Period": 10,
                        "TsFileMode": "SEGMENTED_FILES"
                    }
                },
                "Outputs": [
                    {
                        "AudioDescriptionNames": audio_description_name_list,
                        "CaptionDescriptionNames": [],
                        "OutputName": "awsmre",
                        "OutputSettings": {
                            "HlsOutputSettings": {
                                "H265PackagingType": "HVC1",
                                "HlsSettings": {
                                    "StandardHlsSettings": {
                                        "AudioRenditionSets": "program_audio",
                                        "M3u8Settings": {
                                            "AudioFramesPerPes": 4,
                                            "AudioPids": "492-498",
                                            "NielsenId3Behavior": "NO_PASSTHROUGH",
                                            "PcrControl": "PCR_EVERY_PES_PACKET",
                                            "PmtPid": "480",
                                            "ProgramNum": 1,
                                            "Scte35Behavior": "NO_PASSTHROUGH",
                                            "Scte35Pid": "500",
                                            "TimedMetadataBehavior": "NO_PASSTHROUGH",
                                            "TimedMetadataPid": "502",
                                            "VideoPid": "481"
                                        }
                                    }
                                },
                                "NameModifier": "_1"
                            }
                        },
                        "VideoDescriptionName": "video_awsmre"
                    }
                ]
            }

            # Append MRE output group to the existing channel output groups
            output_groups.append(mre_output_group)

        encoder_settings["OutputGroups"] = output_groups

        video_descriptions = encoder_settings["VideoDescriptions"]
        is_new_video_description = True

        for index, video_description in enumerate(video_descriptions):
            if video_description["Name"] == "video_awsmre":
                print(
                    f"Skipping the addition of new video description for MRE as it already exists in the MediaLive channel '{channel_id}'")
                is_new_video_description = False
                break

        if is_new_video_description:
            mre_video_description = {
                "CodecSettings": {
                    "H264Settings": {
                        "AdaptiveQuantization": "AUTO",
                        "AfdSignaling": "NONE",
                        "Bitrate": 5000000,
                        "BufSize": 5000000,
                        "ColorMetadata": "INSERT",
                        "EntropyEncoding": "CABAC",
                        "FlickerAq": "ENABLED",
                        "ForceFieldPictures": "DISABLED",
                        "FramerateControl": "INITIALIZE_FROM_SOURCE",
                        "GopBReference": "DISABLED",
                        "GopClosedCadence": 1,
                        "GopNumBFrames": 2,
                        "GopSize": 1,
                        "GopSizeUnits": "SECONDS",
                        "Level": "H264_LEVEL_AUTO",
                        "LookAheadRateControl": "MEDIUM",
                        "MaxBitrate": 5000000,
                        "NumRefFrames": 1,
                        "ParControl": "INITIALIZE_FROM_SOURCE",
                        "Profile": "HIGH",
                        "QvbrQualityLevel": 8,
                        "RateControlMode": "QVBR",
                        "ScanType": "PROGRESSIVE",
                        "SceneChangeDetect": "DISABLED",
                        "SpatialAq": "ENABLED",
                        "SubgopLength": "FIXED",
                        "Syntax": "DEFAULT",
                        "TemporalAq": "ENABLED",
                        "TimecodeInsertion": "DISABLED"
                    }
                },
                "Name": "video_awsmre",
                "RespondToAfd": "NONE",
                "ScalingBehavior": "DEFAULT",
                "Sharpness": 50
            }

            # Append MRE video description to the existing channel video descriptions
            video_descriptions.append(mre_video_description)

        encoder_settings["VideoDescriptions"] = video_descriptions

        # Update the MediaLive channel with modified Destinations and EncoderSettings
        print(f"Updating the MediaLive channel '{channel_id}' with modified Destinations and EncoderSettings")
        medialive_client.update_channel(
            ChannelId=channel_id,
            Destinations=destinations,
            EncoderSettings=encoder_settings
        )

    except medialive_client.exceptions.NotFoundException as e:
        print(f"MediaLive channel '{channel_id}' not found")
        raise Exception(e)

    except Exception as e:
        print(
            f"Unable to add a new or update an existing OutputGroup for MRE in the MediaLive channel '{channel_id}': {str(e)}")
        raise Exception(e)

    else:
        return last_known_medialive_config


def create_cloudwatch_alarm_for_channel(channel_id):
    print(
        f"Adding/Updating the CloudWatch Alarm for 'InputVideoFrameRate' metric for the MediaLive channel '{channel_id}'")

    try:
        cw_client.put_metric_alarm(
            AlarmName=f"AWS_MRE_MediaLive_{channel_id}_InputVideoFrameRate_Alarm",
            AlarmDescription=f"Alarm created by AWS MRE for the MediaLive channel {channel_id} to monitor input video frame rate and update the status of an Event to Complete",
            ComparisonOperator="LessThanOrEqualToThreshold",
            MetricName="InputVideoFrameRate",
            Period=10,
            EvaluationPeriods=1,
            DatapointsToAlarm=1,
            Threshold=0.0,
            TreatMissingData="breaching",
            Namespace="MediaLive",
            Statistic="Minimum",
            Dimensions=[
                {
                    "Name": "ChannelId",
                    "Value": channel_id
                },
                {
                    "Name": "Pipeline",
                    "Value": "0"
                }
            ],
            ActionsEnabled=False,
            Tags=[
                {
                    "Key": "Project",
                    "Value": "MRE"
                }
            ]
        )

    except Exception as e:
        print(
            f"Unable to add or update the CloudWatch Alarm for 'InputVideoFrameRate' metric for the MediaLive channel '{channel_id}': {str(e)}")
        raise Exception(e)


@app.route('/event', cors=True, methods=['POST'], authorizer=authorizer)
def create_event():
    """
    Creates a new event in MRE.

    Body:

    .. code-block:: python

        {
            "Name": string,
            "Program": string,
            "Description": string,
            "Channel": string,
            "ProgramId": string,
            "SourceVideoUrl": string,
            "SourceVideoAuth": object,
            "SourceVideoMetadata": object,
            "BootstrapTimeInMinutes": integer,
            "Profile": string,
            "ContentGroup": string,
            "Start": timestamp,
            "DurationMinutes": integer,
            "Archive": boolean
        }

    Parameters:

        - Name: Name of the Event
        - Program: Name of the Program
        - Description: Event Description 
        - Channel: Identifier of the AWS Elemental MediaLive Channel used for the Event
        - ProgramId: A Unique Identifier for the event being broadcasted.
        - SourceVideoUrl: VOD or Live Urls to help MRE to harvest the streams
        - SourceVideoAuth: A Dict which contains API Authorization payload to help MRE harvest VOD/Live streams
        - SourceVideoMetadata: A Dict of additional Event Metadata for reporting purposes.
        - BootstrapTimeInMinutes: Duration in Minutes which indicates the time it takes for the VOD/Live stream harvester to be initialized
        - Profile: Name of the MRE Profile to make use of for processing the event
        - ContentGroup: Name of the Content Group
        - Start: The Actual start DateTime of the event
        - DurationMinutes: The Total Event Duration
        - Archive: Backup the Source Video if true.

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        409 - ConflictError
        500 - ChaliceViewError
    """
    try:
        event = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=event, schema=API_SCHEMA["create_event"], format_checker=FormatChecker())

        print("Got a valid event schema")

        name = event["Name"]
        program = event["Program"]

        is_vod_event = False

        start_utc_time = datetime.strptime(event["Start"], "%Y-%m-%dT%H:%M:%SZ")
        cur_utc_time = datetime.utcnow()

        event["BootstrapTimeInMinutes"] = event["BootstrapTimeInMinutes"] if "BootstrapTimeInMinutes" in event else 5
        event["Id"] = str(uuid.uuid4())
        event["Status"] = "Queued"
        event["Created"] = cur_utc_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        event["HlsMasterManifest"] = {}
        event["EdlLocation"] = {}
        event["PaginationPartition"] = "PAGINATION_PARTITION"
        event["StartFilter"] = event["Start"]

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        if "Channel" in event and event["Channel"]:
            # Check if the event start time is in the past
            if cur_utc_time >= start_utc_time:
                is_vod_event = True

            event["LastKnownMediaLiveConfig"] = add_or_update_medialive_output_group(name, program, event["Profile"],
                                                                                     event["Channel"])

            # Add or Update the CW Alarm for the MediaLive channel
            create_cloudwatch_alarm_for_channel(event["Channel"])

        if "SourceVideoAuth" in event:
            response = sm_client.create_secret(
                Name=f"/MRE/Event/{event['Id']}/SourceVideoAuth",
                SecretString=json.dumps(event["SourceVideoAuth"]),
                Tags=[
                    {
                        "Key": "Project",
                        "Value": "MRE"
                    },
                    {
                        "Key": "Program",
                        "Value": program
                    },
                    {
                        "Key": "Event",
                        "Value": name
                    }
                ]
            )

            event["SourceVideoAuthSecretARN"] = response["ARN"]
            event.pop("SourceVideoAuth", None)

        print(f"Creating the event '{name}' in program '{program}'")

        event_table.put_item(
            Item=event,
            ConditionExpression="attribute_not_exists(#Name) AND attribute_not_exists(#Program)",
            ExpressionAttributeNames={
                "#Name": "Name",
                "#Program": "Program"
            }
        )

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except ConflictError as e:
        print(f"Got chalice ConflictError: {str(e)}")
        raise

    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")

        if "LastKnownMediaLiveConfig" in event:
            medialive_client.update_channel(
                ChannelId=event["Channel"],
                Destinations=event["LastKnownMediaLiveConfig"]["Destinations"],
                EncoderSettings=event["LastKnownMediaLiveConfig"]["EncoderSettings"]
            )

        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ConflictError(f"Event '{name}' in program '{program}' already exists")
        else:
            raise

    except Exception as e:
        print(f"Unable to create the event '{name}' in program '{program}': {str(e)}")

        if "LastKnownMediaLiveConfig" in event:
            medialive_client.update_channel(
                ChannelId=event["Channel"],
                Destinations=event["LastKnownMediaLiveConfig"]["Destinations"],
                EncoderSettings=event["LastKnownMediaLiveConfig"]["EncoderSettings"]
            )

        raise ChaliceViewError(f"Unable to create the event '{name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully created the event: {json.dumps(event)}")

        if is_vod_event:
            channel_id = event["Channel"]
            print(f"Starting the MediaLive channel '{channel_id}' as the event is based on a VOD asset")

            try:
                medialive_client.start_channel(
                    ChannelId=channel_id
                )

            except Exception as e:
                print(
                    f"Creation of event '{name}' in program '{program}' is successful but unable to start the MediaLive channel '{channel_id}': {str(e)}")
                raise ChaliceViewError(
                    f"Creation of event '{name}' in program '{program}' is successful but unable to start the MediaLive channel '{channel_id}': {str(e)}")

        return {}


# List events
def list_events(path_params):
    """
    List all events filtered by content_group with pagination and more filters

    Returns:
    .. code-block:: python
        {
        "Items":
            [
                {
                    "Name": string,
                    "Program": string,
                    "Description": string,
                    "Channel": string,
                    "ProgramId": string,
                    "SourceVideoUrl": string,
                    "SourceVideoAuth": object,
                    "SourceVideoMetadata": object,
                    "BootstrapTimeInMinutes": integer,
                    "Profile": string,
                    "ContentGroup": string,
                    "Start": timestamp,
                    "DurationMinutes": integer,
                    "Archive": boolean,
                    "FirstPts": number,
                    "FrameRate": number,
                    "AudioTracks": list,
                    "Status": string,
                    "Id": uuid,
                    "Created": timestamp,
                    "ContentGroup: string
                },
                ...
            ]
        "LastEvaluatedKey":
            {
                Obj
            }
        }

    Raises:
        500 - ChaliceViewError
    """
    try:
        query_params = app.current_request.query_params
        # query_params = event["queryStringParameters"]
        limit = 100
        filter_expression = None
        last_evaluated_key = None
        projection_expression = None

        if query_params:
            if "limit" in query_params:
                limit = int(query_params.get("limit"))
            if "hasReplays" in query_params and query_params.get("hasReplays") == "true":
                filter_expression = Attr("hasReplays").eq(True)
            if "LastEvaluatedKey" in query_params:
                last_evaluated_key = query_params.get("LastEvaluatedKey")
            if "ProjectionExpression" in query_params:
                projection_expression = query_params.get("ProjectionExpression")
            if "fromFilter" in query_params:
                start = query_params.get("fromFilter")
                filter_expression = Attr("StartFilter").gte(start) if \
                    not filter_expression else filter_expression & Attr("StartFilter").gte(start)
            if "toFilter" in query_params:
                end = query_params.get("toFilter")
                filter_expression = Attr("StartFilter").lte(end) if \
                    not filter_expression else filter_expression & Attr("StartFilter").lte(end)
            if "ContentGroup" in query_params:
                content_group = query_params["ContentGroup"]
                filter_expression = Attr("ContentGroup").eq(content_group) if \
                    not filter_expression else filter_expression & Attr("ContentGroup").eq(content_group)
        if path_params:
            if list(path_params.keys())[0] == "ContentGroup":
                content_group = list(path_params.values())[0]
                filter_expression = Attr("ContentGroup").eq(content_group) if \
                    not filter_expression else filter_expression & Attr("ContentGroup").eq(content_group)

        print(f"Getting '{limit}' Events'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        query = {
            'IndexName': EVENT_PAGINATION_INDEX,
            'Limit': limit,
            'ScanIndexForward': False,  # descending
            'KeyConditionExpression': Key("PaginationPartition").eq("PAGINATION_PARTITION")
        }

        if filter_expression:
            query["FilterExpression"] = filter_expression
        if last_evaluated_key:
            query["ExclusiveStartKey"] = json.loads(last_evaluated_key)
        if projection_expression:
            query["ProjectionExpression"] = ", ".join(["#" + name for name in projection_expression.split(', ')])
            expression_attribute_names = {}
            for item in query["ProjectionExpression"].split(', '):
                expression_attribute_names[item] = item[1:]
            query["ExpressionAttributeNames"] = expression_attribute_names

        response = event_table.query(**query)
        events = response["Items"]

        while "LastEvaluatedKey" in response and (limit - len(events) > 0):
            query["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            query["Limit"] = limit - len(events)
            response = event_table.query(**query)
            events.extend(response["Items"])

    except Exception as e:
        print(f"Unable to get the Events")
        raise ChaliceViewError(f"Unable to get Events")

    else:
        ret_val = {
            "LastEvaluatedKey": response["LastEvaluatedKey"] if "LastEvaluatedKey" in response else "",
            "Items": replace_decimals(events)
        }

        return ret_val


@app.route('/event/contentgroup/{content_group}/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_events_by_content_group(content_group):
    """
    List all events filtered by content_group with pagination and more filters

    Returns:

        .. code-block:: python

            {
            "Items":
                [
                    {
                        "Name": string,
                        "Program": string,
                        "Description": string,
                        "Channel": string,
                        "ProgramId": string,
                        "SourceVideoUrl": string,
                        "SourceVideoAuth": object,
                        "SourceVideoMetadata": object,
                        "BootstrapTimeInMinutes": integer,
                        "Profile": string,
                        "ContentGroup": string,
                        "Start": timestamp,
                        "DurationMinutes": integer,
                        "Archive": boolean,
                        "FirstPts": number,
                        "FrameRate": number,
                        "AudioTracks": list,
                        "Status": string,
                        "Id": uuid,
                        "Created": timestamp,
                        "ContentGroup: string
                    },
                    ...
                ]
            "LastEvaluatedKey":
                {
                    Obj
                }
            }

    Raises:
        500 - ChaliceViewError
    """
    content_group = urllib.parse.unquote(content_group)
    return list_events({"ContentGroup": content_group})


@app.route('/event/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_events_all():
    """
    List all events in MRE. Supports pagination and filters.

    Returns:

        .. code-block:: python

            {
            "Items":
                [
                    {
                        "Name": string,
                        "Program": string,
                        "Description": string,
                        "Channel": string,
                        "ProgramId": string,
                        "SourceVideoUrl": string,
                        "SourceVideoAuth": object,
                        "SourceVideoMetadata": object,
                        "BootstrapTimeInMinutes": integer,
                        "Profile": string,
                        "ContentGroup": string,
                        "Start": timestamp,
                        "DurationMinutes": integer,
                        "Archive": boolean,
                        "FirstPts": number,
                        "FrameRate": number,
                        "AudioTracks": list,
                        "Status": string,
                        "Id": uuid,
                        "Created": timestamp,
                        "ContentGroup: string
                    },
                    ...
                ]
            "LastEvaluatedKey":
                {
                    Obj
                }
            }

    Raises:
        500 - ChaliceViewError
    """
    return list_events(None)


@app.route('/event/{name}/program/{program}', cors=True, methods=['GET'], authorizer=authorizer)
def get_event(name, program):
    """
    Get an event by name and program.

    Returns:

        .. code-block:: python

            {
                "Name": string,
                "Program": string,
                "Description": string,
                "Channel": string,
                "ProgramId": string,
                "SourceVideoUrl": string,
                "SourceVideoAuth": object,
                "SourceVideoMetadata": object,
                "BootstrapTimeInMinutes": integer,
                "Profile": string,
                "ContentGroup": string,
                "Start": timestamp,
                "DurationMinutes": integer,
                "Archive": boolean,
                "FirstPts": number,
                "FrameRate": number,
                "AudioTracks": list,
                "Status": string,
                "Id": uuid,
                "Created": timestamp
            }

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)

        print(f"Getting the Event '{name}' in Program '{program}'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={
                "Name": name,
                "Program": program
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Event '{name}' in Program '{program}' not found")

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to get the Event '{name}' in Program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to get the Event '{name}' in Program '{program}': {str(e)}")

    else:
        return replace_decimals(response["Item"])


@app.route('/event/{name}/program/{program}', cors=True, methods=['PUT'], authorizer=authorizer)
def update_event(name, program):
    """
    Update an event by name and program.

    Body:

    .. code-block:: python

        {
            "Description": string,
            "ProgramId": string,
            "SourceVideoUrl": string,
            "SourceVideoAuth": object,
            "SourceVideoMetadata": object,
            "BootstrapTimeInMinutes": integer,
            "Profile": string,
            "ContentGroup": string,
            "Start": timestamp,
            "DurationMinutes": integer,
            "Archive": boolean
        }

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        409 - ConflictError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)

        event = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=event, schema=API_SCHEMA["update_event"])

        print("Got a valid event schema")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={
                "Name": name,
                "Program": program
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Event '{name}' in Program '{program}' not found")

        print(f"Updating the event '{name}' in program '{program}'")

        if "ProgramId" in event and event["ProgramId"]:
            program_id = event["ProgramId"]
            existing_program_id = response["Item"]["ProgramId"] if "ProgramId" in response["Item"] else ""

            if program_id != existing_program_id:
                response = event_table.query(
                    IndexName=EVENT_PROGRAMID_INDEX,
                    KeyConditionExpression=Key("ProgramId").eq(program_id)
                )

                events = response["Items"]

                while "LastEvaluatedKey" in response:
                    response = event_table.query(
                        ExclusiveStartKey=response["LastEvaluatedKey"],
                        IndexName=EVENT_PROGRAMID_INDEX,
                        KeyConditionExpression=Key("ProgramId").eq(program_id)
                    )

                    events.extend(response["Items"])

                if len(events) > 0:
                    raise ConflictError(f"ProgramId '{program_id}' already exists in another event")

        if "SourceVideoAuth" in event:
            existing_auth_arn = response["Item"]["SourceVideoAuthSecretARN"] if "SourceVideoAuthSecretARN" in response[
                "Item"] else ""

            if existing_auth_arn:
                sm_client.update_secret(
                    SecretId=existing_auth_arn,
                    SecretString=json.dumps(event["SourceVideoAuth"])
                )

                event["SourceVideoAuthSecretARN"] = existing_auth_arn
                event.pop("SourceVideoAuth", None)

            else:
                response = sm_client.create_secret(
                    Name=f"/MRE/Event/{response['Item']['Id']}/SourceVideoAuth",
                    SecretString=json.dumps(event["SourceVideoAuth"]),
                    Tags=[
                        {
                            "Key": "Project",
                            "Value": "MRE"
                        },
                        {
                            "Key": "Program",
                            "Value": program
                        },
                        {
                            "Key": "Event",
                            "Value": name
                        }
                    ]
                )

                event["SourceVideoAuthSecretARN"] = response["ARN"]
                event.pop("SourceVideoAuth", None)

        update_expression = "SET #Description = :Description, #ProgramId = :ProgramId, #Profile = :Profile, #ContentGroup = :ContentGroup, #Start = :Start, #DurationMinutes = :DurationMinutes, #Archive = :Archive"

        expression_attribute_names = {
            "#Description": "Description",
            "#ProgramId": "ProgramId",
            "#Profile": "Profile",
            "#ContentGroup": "ContentGroup",
            "#Start": "Start",
            "#DurationMinutes": "DurationMinutes",
            "#Archive": "Archive"
        }

        expression_attribute_values = {
            ":Description": event["Description"] if "Description" in event else (
                response["Item"]["Description"] if "Description" in response["Item"] else ""),
            ":ProgramId": event["ProgramId"] if "ProgramId" in event else (
                response["Item"]["ProgramId"] if "ProgramId" in response["Item"] else ""),
            ":Profile": event["Profile"] if "Profile" in event else response["Item"]["Profile"],
            ":ContentGroup": event["ContentGroup"] if "ContentGroup" in event else response["Item"]["ContentGroup"],
            ":Start": event["Start"] if "Start" in event else response["Item"]["Start"],
            ":DurationMinutes": event["DurationMinutes"] if "DurationMinutes" in event else response["Item"][
                "DurationMinutes"],
            ":Archive": event["Archive"] if "Archive" in event else response["Item"]["Archive"]
        }

        if "Channel" not in response["Item"]:
            update_expression += ", #SourceVideoUrl = :SourceVideoUrl, #SourceVideoAuthSecretARN = :SourceVideoAuthSecretARN, #SourceVideoMetadata = :SourceVideoMetadata, #BootstrapTimeInMinutes = :BootstrapTimeInMinutes"

            expression_attribute_names["#SourceVideoUrl"] = "SourceVideoUrl"
            expression_attribute_names["#SourceVideoAuthSecretARN"] = "SourceVideoAuthSecretARN"
            expression_attribute_names["#SourceVideoMetadata"] = "SourceVideoMetadata"
            expression_attribute_names["#BootstrapTimeInMinutes"] = "BootstrapTimeInMinutes"

            expression_attribute_values[":SourceVideoUrl"] = event["SourceVideoUrl"] if "SourceVideoUrl" in event else \
                response["Item"]["SourceVideoUrl"]
            expression_attribute_values[":SourceVideoAuthSecretARN"] = event[
                "SourceVideoAuthSecretARN"] if "SourceVideoAuthSecretARN" in event else (
                response["Item"]["SourceVideoAuthSecretARN"] if "SourceVideoAuthSecretARN" in response["Item"] else "")
            expression_attribute_values[":SourceVideoMetadata"] = event[
                "SourceVideoMetadata"] if "SourceVideoMetadata" in event else (
                response["Item"]["SourceVideoMetadata"] if "SourceVideoMetadata" in response["Item"] else {})
            expression_attribute_values[":BootstrapTimeInMinutes"] = event[
                "BootstrapTimeInMinutes"] if "BootstrapTimeInMinutes" in event else response["Item"][
                "BootstrapTimeInMinutes"]

        event_table.update_item(
            Key={
                "Name": name,
                "Program": program
            },
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values
        )

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to update the event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to update the event '{name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully updated the event: {json.dumps(event, cls=DecimalEncoder)}")

        return {}


def delete_medialive_output_group(name, program, profile, channel_id):
    print(f"Describing the MediaLive channel '{channel_id}' to get existing Destinations and EncoderSettings")

    try:
        response = medialive_client.describe_channel(
            ChannelId=channel_id
        )

        if response["State"] != "IDLE":
            print(
                f"Skipping deletion of MRE Destination and OutputGroup as the MediaLive channel '{channel_id}' is not in 'IDLE' state")
            return

        destinations = response["Destinations"]
        encoder_settings = response["EncoderSettings"]

        delete_output_group = False

        for index, destination in enumerate(destinations):
            if destination["Id"] == "awsmre" and destination["Settings"][0][
                "Url"] == f"s3ssl://{MEDIALIVE_S3_BUCKET}/{channel_id}/{program}/{name}/{profile}/{program}_{name}":
                print(f"Deleting the MRE destination present in the MediaLive channel '{channel_id}'")
                destinations.pop(index)
                delete_output_group = True
                break

        if delete_output_group:
            output_groups = encoder_settings["OutputGroups"]

            for index, output_group in enumerate(output_groups):
                if "HlsGroupSettings" in output_group["OutputGroupSettings"] and \
                        output_group["OutputGroupSettings"]["HlsGroupSettings"]["Destination"][
                            "DestinationRefId"] == "awsmre":
                    print(f"Deleting the OutputGroup for MRE in the MediaLive channel '{channel_id}'")
                    output_groups.pop(index)
                    break

            encoder_settings["OutputGroups"] = output_groups

            video_descriptions = encoder_settings["VideoDescriptions"]

            for index, video_description in enumerate(video_descriptions):
                if video_description["Name"] == "video_awsmre":
                    print(f"Deleting the VideoDescription for MRE in the MediaLive channel '{channel_id}'")
                    video_descriptions.pop(index)
                    break

            encoder_settings["VideoDescriptions"] = video_descriptions

            # Update the MediaLive channel with modified Destinations and EncoderSettings
            print(f"Updating the MediaLive channel '{channel_id}' with modified Destinations and EncoderSettings")
            medialive_client.update_channel(
                ChannelId=channel_id,
                Destinations=destinations,
                EncoderSettings=encoder_settings
            )

        else:
            print(
                f"No deletion required as the Destination and OutputGroup for MRE are not found in the MediaLive channel '{channel_id}'")

    except medialive_client.exceptions.NotFoundException as e:
        print(f"Unable to delete the Destination and OutputGroup for MRE: MediaLive channel '{channel_id}' not found")

    except Exception as e:
        print(
            f"Unable to delete the Destination and OutputGroup for MRE in the MediaLive channel '{channel_id}': {str(e)}")


def delete_cloudwatch_alarm_for_channel(channel_id):
    print(f"Deleting the CloudWatch Alarm for 'InputVideoFrameRate' metric for the MediaLive channel '{channel_id}'")

    try:
        cw_client.delete_alarms(
            AlarmNames=[f"AWS_MRE_MediaLive_{channel_id}_InputVideoFrameRate_Alarm"]
        )

    except Exception as e:
        print(
            f"Unable to delete the CloudWatch Alarm for 'InputVideoFrameRate' metric for the MediaLive channel '{channel_id}': {str(e)}")


def notify_event_deletion_queue(name, program, profile):
    print(
        f"Sending a message to the SQS queue '{SQS_QUEUE_URL}' to notify the deletion of event '{name}' in program '{program}'")

    try:
        message = {
            "Event": name,
            "Program": program,
            "Profile": profile
        }

        sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(message),
        )

    except Exception as e:
        print(
            f"Unable to send a message to the SQS queue '{SQS_QUEUE_URL}' to notify the deletion of event '{name}' in program '{program}': {str(e)}")


@app.route('/event/{name}/program/{program}', cors=True, methods=['DELETE'], authorizer=authorizer)
def delete_event(name, program):
    """
    Delete an event by name and program.

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)

        query_params = app.current_request.query_params

        if query_params and query_params.get("force") == "true":
            force_delete = True
        else:
            force_delete = False

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={
                "Name": name,
                "Program": program
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Event '{name}' in Program '{program}' not found")
        elif response["Item"]["Status"] == "In Progress":
            raise BadRequestError(f"Cannot delete Event '{name}' in Program '{program}' as it is currently in progress")

        channel_id = response["Item"]["Channel"] if "Channel" in response["Item"] else None
        profile = response["Item"]["Profile"]
        source_auth_secret_arn = response["Item"]["SourceVideoAuthSecretARN"] if "SourceVideoAuthSecretARN" in response[
            "Item"] else None

        if channel_id:
            print(
                f"Checking if MRE Destination and OutputGroup need to be deleted in the MediaLive channel '{channel_id}'")
            delete_medialive_output_group(name, program, profile, channel_id)

            print(
                f"Checking if the CloudWatch Alarm for 'InputVideoFrameRate' metric needs to be deleted for the MediaLive channel '{channel_id}'")

            response = event_table.query(
                IndexName=EVENT_CHANNEL_INDEX,
                KeyConditionExpression=Key("Channel").eq(channel_id)
            )

            events = response["Items"]

            while "LastEvaluatedKey" in response:
                response = event_table.query(
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                    IndexName=EVENT_CHANNEL_INDEX,
                    KeyConditionExpression=Key("Channel").eq(channel_id)
                )

                events.extend(response["Items"])

            if len(events) < 2:
                delete_cloudwatch_alarm_for_channel(channel_id)

        if source_auth_secret_arn:
            if force_delete:
                print(f"Deleting the secret '{source_auth_secret_arn}' immediately")

                sm_client.delete_secret(
                    SecretId=source_auth_secret_arn,
                    ForceDeleteWithoutRecovery=True
                )

            else:
                print(f"Deleting the secret '{source_auth_secret_arn}' with a recovery window of 7 days")

                sm_client.delete_secret(
                    SecretId=source_auth_secret_arn,
                    RecoveryWindowInDays=7
                )

        print(f"Deleting the Event '{name}' in Program '{program}'")

        response = event_table.delete_item(
            Key={
                "Name": name,
                "Program": program
            }
        )

        # Send a message to the Event Deletion SQS Queue to trigger the deletion of processing data in DynamoDB for the Event
        notify_event_deletion_queue(name, program, profile)

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except BadRequestError as e:
        print(f"Got chalice BadRequestError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to delete the Event '{name}' in Program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to delete the Event '{name}' in Program '{program}': {str(e)}")

    else:
        print(f"Deletion of Event '{name}' in Program '{program}' successful")
        return {}


@app.route('/event/{name}/program/{program}/timecode/firstpts/{first_pts}', cors=True, methods=['PUT'],
           authorizer=authorizer)
def store_first_pts(name, program, first_pts):
    """
    Store the pts timecode of the first frame of the first HLS video segment.

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)
        first_pts = urllib.parse.unquote(first_pts)

        print(
            f"Storing the first pts timecode '{first_pts}' of event '{name}' in program '{program}' in the DynamoDB table '{EVENT_TABLE_NAME}'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={
                "Name": name,
                "Program": program
            },
            UpdateExpression="SET #FirstPts = :FirstPts",
            ExpressionAttributeNames={
                "#FirstPts": "FirstPts"
            },
            ExpressionAttributeValues={
                ":FirstPts": Decimal(first_pts)
            }
        )

    except Exception as e:
        print(
            f"Unable to store the first pts timecode '{first_pts}' of event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to store the first pts timecode '{first_pts}' of event '{name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully stored the first pts timecode '{first_pts}' of event '{name}' in program '{program}'")

        return {}


@app.route('/event/{name}/program/{program}/timecode/firstpts', cors=True, methods=['GET'], authorizer=authorizer)
def get_first_pts(name, program):
    """
    Retrieve the pts timecode of the first frame of the first HLS video segment.

    Returns:

        The pts timecode of the first frame of the first HLS video segment if it exists. Else, None.

    Raises:
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)

        print(f"Retrieving the first pts timecode of event '{name}' in program '{program}'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={
                "Name": name,
                "Program": program
            },
            ProjectionExpression="FirstPts"
        )

        if "Item" not in response or len(response["Item"]) < 1:
            print(f"First pts timecode of event '{name}' in program '{program}' not found")
            return None

    except Exception as e:
        print(f"Unable to retrieve the first pts timecode of event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to retrieve the first pts timecode of event '{name}' in program '{program}': {str(e)}")

    else:
        return replace_decimals(response["Item"]["FirstPts"])


@app.route('/event/{name}/program/{program}/framerate/{frame_rate}', cors=True, methods=['PUT'], authorizer=authorizer)
def store_frame_rate(name, program, frame_rate):
    """
    Store the frame rate identified after probing the first HLS video segment.

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)
        frame_rate = urllib.parse.unquote(frame_rate)

        print(
            f"Storing the frame rate '{frame_rate}' of event '{name}' in program '{program}' in the DynamoDB table '{EVENT_TABLE_NAME}'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={
                "Name": name,
                "Program": program
            },
            UpdateExpression="SET #FrameRate = :FrameRate",
            ExpressionAttributeNames={
                "#FrameRate": "FrameRate"
            },
            ExpressionAttributeValues={
                ":FrameRate": frame_rate
            }
        )

    except Exception as e:
        print(f"Unable to store the frame rate '{frame_rate}' of event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to store the frame rate '{frame_rate}' of event '{name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully stored the frame rate '{frame_rate}' of event '{name}' in program '{program}'")

        return {}


@app.route('/event/metadata/track/audio', cors=True, methods=['POST'], authorizer=authorizer)
def store_audio_tracks():
    """
    Store the audio tracks of an event identified after probing the first HLS video segment.

    Body:

    .. code-block:: python

        {
            "Name": string,
            "Program": string,
            "AudioTracks": list
        }

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        event = json.loads(app.current_request.raw_body.decode())

        name = event["Name"]
        program = event["Program"]
        audio_tracks = event["AudioTracks"]

        print(
            f"Storing the audio tracks '{audio_tracks}' of event '{name}' in program '{program}' in the DynamoDB table '{EVENT_TABLE_NAME}'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={
                "Name": name,
                "Program": program
            },
            UpdateExpression="SET #AudioTracks = :AudioTracks",
            ExpressionAttributeNames={
                "#AudioTracks": "AudioTracks"
            },
            ExpressionAttributeValues={
                ":AudioTracks": audio_tracks
            }
        )

    except Exception as e:
        print(f"Unable to store the audio tracks '{audio_tracks}' of event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to store the audio tracks '{audio_tracks}' of event '{name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully stored the audio tracks '{audio_tracks}' of event '{name}' in program '{program}'")

        return {}


def put_events_to_event_bridge(name, program, status):
    try:
        print(f"Sending the event status to EventBridge for event '{name}' in program '{program}'")

        if status == "In Progress":
            state = "EVENT_START"
        elif status == "Complete":
            state = "EVENT_END"

        detail = {
            "State": state,
            "Event": {
                "Name": name,
                "Program": program
            }
        }

        response = eb_client.put_events(
            Entries=[
                {
                    "Source": "awsmre",
                    "DetailType": "Event Status",
                    "Detail": json.dumps(detail),
                    "EventBusName": EB_EVENT_BUS_NAME
                }
            ]
        )

        if response["FailedEntryCount"] > 0:
            print(
                f"Failed to send the event status to EventBridge for event '{name}' in program '{program}'. More details below:")
            print(response["Entries"])

    except Exception as e:
        print(f"Unable to send the event status to EventBridge for event '{name}' in program '{program}': {str(e)}")


@app.route('/event/{name}/program/{program}/status/{status}', cors=True, methods=['PUT'], authorizer=authorizer)
def put_event_status(name, program, status):
    """
    Update the status of an event.

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)
        status = urllib.parse.unquote(status)

        print(f"Setting the status of event '{name}' in program '{program}' to '{status}'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={
                "Name": name,
                "Program": program
            },
            UpdateExpression="SET #Status = :Status",
            ExpressionAttributeNames={
                "#Status": "Status"
            },
            ExpressionAttributeValues={
                ":Status": status
            }
        )

        # Notify EventBridge of the Event status
        if status in ["In Progress", "Complete"]:
            put_events_to_event_bridge(name, program, status)

    except Exception as e:
        print(f"Unable to set the status of event '{name}' in program '{program}' to '{status}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to set the status of event '{name}' in program '{program}' to '{status}': {str(e)}")

    else:
        print(f"Successfully set the status of event '{name}' in program '{program}' to '{status}'")

        return {}


@app.route('/event/{name}/program/{program}/status', cors=True, methods=['GET'], authorizer=authorizer)
def get_event_status(name, program):
    """
    Get the status of an event.

    Returns:

        Status of the event

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)

        print(f"Getting the status of event '{name}' in program '{program}'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={
                "Name": name,
                "Program": program
            },
            ProjectionExpression="#Status",
            ExpressionAttributeNames={
                "#Status": "Status"
            }
        )

        if "Item" not in response or len(response["Item"]) < 1:
            raise NotFoundError(f"Event '{name}' in program '{program}' not found")

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to get the status of event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to get the status of event '{name}' in program '{program}': {str(e)}")

    else:
        return response["Item"]["Status"]


#############################################################
#                                                           #
#                     CONTENT GROUP                         #
#                                                           #
#############################################################

@app.route('/contentgroup/{content_group}', cors=True, methods=['PUT'], authorizer=authorizer)
def put_content_group(content_group):
    """
    Create a new content group in the system.

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        content_group = urllib.parse.unquote(content_group)

        print(f"Creating a new content group '{content_group}'")

        content_group_table = ddb_resource.Table(CONTENT_GROUP_TABLE_NAME)

        item = {
            "Name": content_group
        }

        content_group_table.put_item(
            Item=item
        )

    except Exception as e:
        print(f"Unable to create a new content group '{content_group}': {str(e)}")
        raise ChaliceViewError(f"Unable to create a new content group '{content_group}': {str(e)}")

    else:
        return {}


@app.route('/contentgroup/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_content_groups():
    """
    List all the content groups stored in the system.

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string
                },
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        print(f"Listing all the content groups")

        content_group_table = ddb_resource.Table(CONTENT_GROUP_TABLE_NAME)

        response = content_group_table.scan(
            ConsistentRead=True
        )

        content_groups = response["Items"]

        while "LastEvaluatedKey" in response:
            response = content_group_table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                ConsistentRead=True
            )

            content_groups.extend(response["Items"])

    except Exception as e:
        print(f"Unable to list all the content groups stored in the system: {str(e)}")
        raise ChaliceViewError(f"Unable to list all the content groups stored in the system: {str(e)}")

    else:
        return content_groups


@app.route('/contentgroup/{content_group}', cors=True, methods=['DELETE'], authorizer=authorizer)
def delete_content_group(content_group):
    """
    Delete a content group in the system.

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        content_group = urllib.parse.unquote(content_group)

        print(f"Deleting the content group '{content_group}'")

        content_group_table = ddb_resource.Table(CONTENT_GROUP_TABLE_NAME)

        content_group_table.delete_item(
            Key={
                "Name": content_group
            }
        )

    except Exception as e:
        print(f"Unable to delete the content group '{content_group}': {str(e)}")
        raise ChaliceViewError(f"Unable to delete the content group '{content_group}': {str(e)}")

    else:
        return {}


#############################################################
#                                                           #
#                        PROGRAM                            #
#                                                           #
#############################################################

@app.route('/program/{program}', cors=True, methods=['PUT'], authorizer=authorizer)
def create_program(program):
    """
    Create a new program in the system.

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        program = urllib.parse.unquote(program)

        print(f"Creating a new program '{program}'")

        program_table = ddb_resource.Table(PROGRAM_TABLE_NAME)

        item = {
            "Name": program
        }

        program_table.put_item(
            Item=item
        )

    except Exception as e:
        print(f"Unable to create a new program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to create a new program '{program}': {str(e)}")

    else:
        return {}


@app.route('/program/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_programs():
    """
    List all the programs stored in the system.

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string
                },
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        print(f"Listing all the programs")

        program_table = ddb_resource.Table(PROGRAM_TABLE_NAME)

        response = program_table.scan(
            ConsistentRead=True
        )

        programs = response["Items"]

        while "LastEvaluatedKey" in response:
            response = program_table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                ConsistentRead=True
            )

            programs.extend(response["Items"])

    except Exception as e:
        print(f"Unable to list all the programs stored in the system: {str(e)}")
        raise ChaliceViewError(f"Unable to list all the programs stored in the system: {str(e)}")

    else:
        return programs


@app.route('/program/{program}', cors=True, methods=['DELETE'], authorizer=authorizer)
def delete_program(program):
    """
    Delete a program in the system.

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        program = urllib.parse.unquote(program)

        print(f"Deleting the program '{program}'")

        program_table = ddb_resource.Table(PROGRAM_TABLE_NAME)

        program_table.delete_item(
            Key={
                "Name": program
            }
        )

    except Exception as e:
        print(f"Unable to delete the program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to delete the program '{program}': {str(e)}")

    else:
        return {}


#############################################################
#                                                           #
#                   WORKFLOW EXECUTION                      #
#                                                           #
#############################################################

@app.route('/workflow/execution', cors=True, methods=['POST'], authorizer=authorizer)
def record_execution_details():
    """
    Record the details of an AWS Step Function workflow execution in the system.

    Body:

    .. code-block:: python

        {
            "Program": string,
            "Event": string,
            "ExecutionId": string,
            "ChunkNumber": integer,
            "Filename": string
        }

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        execution = json.loads(app.current_request.raw_body.decode())

        program = execution["Program"]
        event = execution["Event"]
        chunk_num = execution["ChunkNumber"]

        print(
            f"Recording the AWS Step Function workflow execution details for chunk '{chunk_num}' in program '{program}' and event '{event}'")

        workflow_exec_table_name = ddb_resource.Table(WORKFLOW_EXECUTION_TABLE_NAME)

        item = {
            "PK": f"{program}#{event}",
            "ChunkNumber": chunk_num,
            "ExecutionId": execution["ExecutionId"],
            "Filename": execution["Filename"]
        }

        workflow_exec_table_name.put_item(
            Item=item
        )

    except Exception as e:
        print(
            f"Unable to record the AWS Step Function workflow execution details for chunk '{chunk_num}' in program '{program}' and event '{event}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to record the AWS Step Function workflow execution details for chunk '{chunk_num}' in program '{program}' and event '{event}': {str(e)}")

    else:
        print(f"Successfully recorded the AWS Step Function workflow execution details: {json.dumps(execution)}")

        return {}


@app.route('/workflow/execution/program/{program}/event/{event}/chunk/{chunk_num}/plugin/{plugin_name}/status/{status}',
           cors=True, methods=['PUT'], authorizer=authorizer)
def put_plugin_execution_status(program, event, chunk_num, plugin_name, status):
    """
    Update the execution status of a plugin included as a part of an AWS Step Function workflow.

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """

    try:
        program = urllib.parse.unquote(program)
        event = urllib.parse.unquote(event)
        chunk_num = urllib.parse.unquote(chunk_num)
        plugin_name = urllib.parse.unquote(plugin_name)
        status = urllib.parse.unquote(status)

        print(
            f"Updating the execution status of '{plugin_name}' plugin for chunk '{chunk_num}' in program '{program}' and event '{event}'")

        workflow_exec_table_name = ddb_resource.Table(WORKFLOW_EXECUTION_TABLE_NAME)

        workflow_exec_table_name.update_item(
            Key={
                "PK": f"{program}#{event}",
                "ChunkNumber": int(chunk_num)
            },
            UpdateExpression=f"SET #Plugin = :Status",
            ExpressionAttributeNames={
                "#Plugin": plugin_name
            },
            ExpressionAttributeValues={
                ":Status": status
            }
        )

    except Exception as e:
        print(
            f"Unable to update the status of '{plugin_name}' plugin for chunk '{chunk_num}' in program '{program}' and event '{event}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to update the status of '{plugin_name}' plugin for chunk '{chunk_num}' in program '{program}' and event '{event}': {str(e)}")

    else:
        print(
            f"Successfully updated the status of '{plugin_name}' plugin for chunk '{chunk_num}' in program '{program}' and event '{event}'")

        return {}


@app.route('/workflow/execution/program/{program}/event/{event}/chunk/{chunk_num}/plugin/{plugin_name}/status',
           cors=True, methods=['GET'], authorizer=authorizer)
def get_plugin_execution_status(program, event, chunk_num, plugin_name):
    """
    Retrieve the execution status of a plugin included as a part of an AWS Step Function workflow.

    Returns:

        Execution status of the plugin, None if it doesn't exist

    Raises:
        500 - ChaliceViewError
    """

    try:
        program = urllib.parse.unquote(program)
        event = urllib.parse.unquote(event)
        chunk_num = urllib.parse.unquote(chunk_num)
        plugin_name = urllib.parse.unquote(plugin_name)

        print(
            f"Getting the execution status of '{plugin_name}' plugin for chunk '{chunk_num}' in program '{program}' and event '{event}'")

        workflow_exec_table_name = ddb_resource.Table(WORKFLOW_EXECUTION_TABLE_NAME)

        response = workflow_exec_table_name.get_item(
            Key={
                "PK": f"{program}#{event}",
                "ChunkNumber": int(chunk_num)
            },
            ProjectionExpression="#Plugin",
            ExpressionAttributeNames={
                "#Plugin": plugin_name
            }
        )

        if "Item" not in response or len(response["Item"]) < 1:
            status = None
        else:
            status = response["Item"][plugin_name]

    except Exception as e:
        print(
            f"Unable to get the execution status of '{plugin_name}' plugin for chunk '{chunk_num}' in program '{program}' and event '{event}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to get the execution status of '{plugin_name}' plugin for chunk '{chunk_num}' in program '{program}' and event '{event}': {str(e)}")

    else:
        return status


@app.route(
    '/workflow/execution/program/{program}/event/{event}/chunk/{chunk_num}/plugin/{plugin_name}/status/incomplete',
    cors=True, methods=['GET'], authorizer=authorizer)
def list_incomplete_plugin_executions(program, event, chunk_num, plugin_name):
    """
    List all the plugin executions that are either yet to start or currently in progress in any workflow 
    execution prior to the given chunk number for a given program and event.

    Returns:

        .. code-block:: python

            [
                {
                    "PK": string,
                    "ChunkNumber": integer
                },
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """

    try:
        program = urllib.parse.unquote(program)
        event = urllib.parse.unquote(event)
        chunk_num = urllib.parse.unquote(chunk_num)
        plugin_name = urllib.parse.unquote(plugin_name)

        print(
            f"Getting all the incomplete '{plugin_name}' plugin executions prior to the chunk '{chunk_num}' in program '{program}' and event '{event}'")

        workflow_exec_table_name = ddb_resource.Table(WORKFLOW_EXECUTION_TABLE_NAME)

        response = workflow_exec_table_name.query(
            KeyConditionExpression=Key("PK").eq(f"{program}#{event}") & Key("ChunkNumber").lt(int(chunk_num)),
            FilterExpression=Attr(plugin_name).not_exists() | Attr(plugin_name).is_in(["Waiting", "In Progress"]),
            ProjectionExpression="PK, ChunkNumber",
            ConsistentRead=True
        )

        executions = response["Items"]

        while "LastEvaluatedKey" in response:
            response = workflow_exec_table_name.query(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("PK").eq(f"{program}#{event}") & Key("ChunkNumber").lt(int(chunk_num)),
                FilterExpression=Attr(plugin_name).not_exists() | Attr(plugin_name).is_in(["Waiting", "In Progress"]),
                ProjectionExpression="PK, ChunkNumber",
                ConsistentRead=True
            )

            executions.extend(response["Items"])

    except Exception as e:
        print(
            f"Unable to get all the incomplete '{plugin_name}' plugin executions prior to the chunk '{chunk_num}' in program '{program}' and event '{event}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to get all the incomplete '{plugin_name}' plugin executions prior to the chunk '{chunk_num}' in program '{program}' and event '{event}': {str(e)}")

    else:
        return replace_decimals(executions)


@app.route('/replay', cors=True, methods=['POST'], authorizer=authorizer)
def add_replay():
    """
    Add a new Replay Summarization to the system.
    
    Body:

    .. code-block:: python

        {
            "Program": string,
            "Event": string,
            "AudioTrack": string,
            "Description": string,
            "Requester": string,
            "UxLabel": "",
            "DurationbasedSummarization": {
                "Duration": number,
                "FillToExact": boolean,
                "EqualDistribution": boolean
            },
            "Priorities":{
                "Clips": [
                    {
                        "Name": string,
                        "Weight": number,
                        "Include": boolean,
                        "Duration": string,
                        "AttribValue": string,
                        "AttribName": string,
                        "PluginName": string
                    }
                ]
            }
            "ClipfeaturebasedSummarization": boolean,
            "Catchup": boolean,
            "Resolutions": list,
            "CreateHls": boolean,
            "CreateMp4": boolean
        }

    Parameters:

        - Program: Name of the Program
        - Event: Name of the Event
        - AudioTrack: AudioTrack number which helps MRE support regional audience needs
        - Description: Description of the Replay being created
        - Requester: Requester of the Replay
        - DurationbasedSummarization:  A Dict capturing the Duration of the Replay to be created
        - Priorities: A List of dict. Each Dict represents the Weight of the Output Attribute which needs to be included in the Replay
        - ClipfeaturebasedSummarization: Set to True if a Duration based replay is not reqd. False, otherwise.
        - Catchup: True if a CatchUp replay is to be created, False otherwise.
        - CreateHls: True if HLS replay output is to be created
        - Resolutions: List of replay Resolutions to be created. Supported values ["4K (3840 x 2160)","2K (2560 x 1440)","16:9 (1920 x 1080)","16:9 (1920 x 1080)","16:9 (1920 x 1080)","1:1 (1080 x 1080)","4:5 (864 x 1080)","9:16 (608 x 1080)","720p (1280 x 720)","480p (854 x 480)","360p (640 x 360)"]
        - CreateMp4:True if MP4 replay output is to be created

    Returns:
    
        None

    Raises:
        400 - BadRequestError
        409 - ConflictError
        500 - ChaliceViewError
    """
    try:
        model = json.loads(app.current_request.raw_body.decode())

        validate(instance=model, schema=API_SCHEMA["add_replay"])

        model["PK"] = f"{model['Program']}#{model['Event']}"
        model["ReplayId"] = str(uuid.uuid4())

        model["Created"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        model["LastModified"] = model["Created"]
        model["Status"] = "Queued"
        model["Enabled"] = True
        model["HlsLocation"] = '-'
        model["EdlLocation"] = '-'
        model["HlsThumbnailLoc"] = '-'
        model["Mp4Location"] = {}
        model["Mp4ThumbnailLocation"] = {}

        print(f"Adding the Replay Request '{model['Program']}#{model['Event']}'")

        replay_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        replay_table.put_item(
            Item=model
        )

        # Publish to event bridge that a new Replay was Created
        detail = {
            "State": "REPLAY_CREATED",
            "Event": {
                "Name": model['Event'],
                "Program": model['Program']
            }
        }

        eb_client.put_events(
            Entries=[
                {
                    "Source": "awsmre",
                    "DetailType": "Replay Created Status",
                    "Detail": json.dumps(detail),
                    "EventBusName": EB_EVENT_BUS_NAME
                }
            ]
        )

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to add a new Replay Request: {str(e)}")
        raise ChaliceViewError(f"Unable to add a new Replay Request: {str(e)}")

    else:
        print(f"Successfully added a new new Replay Request: {json.dumps(model)}")

        return {}


@app.route('/replay/all', cors=True, methods=['GET'], authorizer=authorizer)
def get_all_replays():
    """
    Gets all the replay requests

    Returns:

        All Replay requests

    Raises:
        500 - ChaliceViewError
    """
    replays = []
    event_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

    response = event_table.scan()
    replayInfo = response["Items"]

    while "NextToken" in response:
        response = event_table.scan(
            NextToken=response["NextToken"]
        )
        replayInfo.extend(response["Items"])

    sorted_replayInfo = sorted(replayInfo, key=lambda x: x['Created'], reverse=True)

    for item in sorted_replayInfo:
        replays.append({
            "Program": item['PK'].split('#')[0],
            "Event": item['PK'].split('#')[1],
            "Requester": item['Requester'],
            "Duration": item['DurationbasedSummarization'][
                'Duration'] if 'DurationbasedSummarization' in item else 'N/A',
            "AudioTrack": item['AudioTrack'] if 'AudioTrack' in item else '',
            "CatchUp": item['Catchup'],
            "Status": item['Status'],
            "DTC": True if 'MediaTailorChannel' in item else False,
            "ReplayId": item['ReplayId'],
            "Description": item['Description'],
            "EdlLocation": item['EdlLocation'] if 'EdlLocation' in item else '-',
            "HlsLocation": item['HlsLocation'] if 'HlsLocation' in item else '-',
            "UxLabel": item['UxLabel'] if 'UxLabel' in item else ''
        })

    return {
        "Items": replace_decimals(replays)
    }


@app.route('/replay/program/{program}/event/{event}/all', cors=True, methods=['GET'], authorizer=authorizer)
def listreplay_by_program_event(program, event):
    """
    Gets all the replay requests based on Program and Event

    Returns:

        Replay requests based on Program and Event

    Raises:
        500 - ChaliceViewError
    """
    replays = []
    try:
        program = urllib.parse.unquote(program)
        event = urllib.parse.unquote(event)

        event_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        response = event_table.query(
            KeyConditionExpression=Key("PK").eq(f"{program}#{event}"),
            ConsistentRead=True
        )

        sorted_replayInfo = sorted(response['Items'], key=lambda x: x['Created'], reverse=True)

        for item in sorted_replayInfo:
            replays.append({
                "Program": program,
                "Event": event,
                "Duration": "TBD",
                "Requester": item['Requester'],
                "AudioTrack": item['AudioTrack'] if 'AudioTrack' in item else '',
                "CatchUp": item['Catchup'],
                "Status": item['Status'],
                "DTC": True if 'MediaTailorChannel' in item else False,
                "ReplayId": item['ReplayId'],
                "EdlLocation": item['EdlLocation'] if 'EdlLocation' in item else '-',
                "HlsLocation": item['HlsLocation'] if 'HlsLocation' in item else '-',
            })

    except Exception as e:
        print(f"Unable to get replays for Program and Event: {str(e)}")
        raise ChaliceViewError(f"Unable to get replays for Program and Event: {str(e)}")

    return replace_decimals(replays)


@app.route('/replay/all/contentgroup/{contentGrp}', cors=True, methods=['GET'], authorizer=authorizer)
def listreplay_by_content_group(contentGrp):
    """
    Get all the replay requests based on Content Group

    Returns:

        Replay requests based on Content Group

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    replays = []
    try:

        contentGroup = urllib.parse.unquote(contentGrp)

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)
        event_response = event_table.scan()

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)
        profileresponse = profile_table.scan()

        for event in event_response['Items']:
            profile = event['Profile']

            profile_obj = None
            for profileItem in profileresponse['Items']:
                if profileItem['Name'] == profile:
                    profile_obj = profileItem
                    break

            if profile_obj is None:
                continue

            if 'ContentGroups' in profile_obj:

                # If the Profile has the Content Group, return the replays associated with the 
                # Program and Event
                if contentGroup in profile_obj['ContentGroups']:

                    replay_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)
                    replayresponse = replay_table.query(
                        KeyConditionExpression=Key("PK").eq(f"{event['Program']}#{event['Name']}"),
                        ConsistentRead=True
                    )

                    for item in replayresponse['Items']:
                        replays.append({
                            "Program": event['Program'],
                            "Event": event['Name'],
                            "Duration": "TBD",
                            "Requester": item['Requester'],
                            "AudioTrack": item['AudioTrack'] if 'AudioTrack' in item else '',
                            "CatchUp": item['Catchup'],
                            "Status": item['Status'],
                            "DTC": True if 'MediaTailorChannel' in item else False,
                            "ReplayId": item['ReplayId'],
                            'Created': item['Created'],
                            "EdlLocation": item['EdlLocation'] if 'EdlLocation' in item else '-',
                            "HlsLocation": item['HlsLocation'] if 'HlsLocation' in item else '-',
                        })

        sorted_replayInfo = sorted(replays, key=lambda x: x['Created'], reverse=True)

    except Exception as e:
        print(f"Unable to get replays for Program and Event: {str(e)}")
        raise ChaliceViewError(f"Unable to get replays for Program and Event: {str(e)}")

    return replace_decimals(sorted_replayInfo)


@app.route('/replay/program/{program}/event/{event}/replayid/{id}', cors=True, methods=['GET'], authorizer=authorizer)
def get_replay_by_program_event_id(program, event, id):
    """
    Gets the replay request based on event, program and replayId

    Returns:

        Replay Request

    Raises:
        404 - NotFoundError
    """
    eventname = urllib.parse.unquote(event)
    program = urllib.parse.unquote(program)

    replay_request_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

    response = replay_request_table.get_item(
        Key={
            "PK": f"{program}#{eventname}",
            "ReplayId": id
        },
        ConsistentRead=True
    )

    if "Item" not in response:
        raise NotFoundError(f"Replay settings not found")

    return response['Item']


########################## Replay Changes Starts ######################
@app.route('/replay/program/{program}/event/{event}/replayid/{id}/status/update/{replaystatus}', cors=True,
           methods=['PUT'], authorizer=authorizer)
def update_replay_request_status(program, event, id, replaystatus):
    """
    Updates the status of a Replay

    Returns:

        None
    """
    eventname = urllib.parse.unquote(event)
    program = urllib.parse.unquote(program)
    replay_id = urllib.parse.unquote(id)
    replaystatus = urllib.parse.unquote(replaystatus)

    replay_request_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

    replay_request_table.update_item(
        Key={
            "PK": f"{program}#{eventname}",
            "ReplayId": replay_id
        },
        UpdateExpression="SET #Status = :status",
        ExpressionAttributeNames={"#Status": "Status"},
        ExpressionAttributeValues={':status': replaystatus}
    )

    return {
        "Status": "Replay request status updated"
    }


@app.route('/replayrequests/completed/events/track/{audioTrack}/program/{program}/event/{event}', cors=True,
           methods=['GET'], authorizer=authorizer)
def get_all_replay_requests_for_completed_event(event, program, audioTrack):
    """
    Returns all Complete Replay Requests for the Program/Event and Audio Track

    Returns:

        Replay Request based on Event, Program and AudioTrack

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    eventname = urllib.parse.unquote(event)
    program = urllib.parse.unquote(program)
    audioTrack = urllib.parse.unquote(audioTrack)

    # Check if Event is Complete
    event_obj = get_event(eventname, program)
    if event_obj['Status'] == 'Complete':
        replay_request_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)
        response = replay_request_table.query(
            KeyConditionExpression=Key("PK").eq(f"{program}#{eventname}"),
            FilterExpression=Attr('Status').ne('Complete') & Attr('AudioTrack').eq(int(audioTrack)),
            ConsistentRead=True
        )

        if "Items" not in response:
            raise NotFoundError(f"No Replay Requests found for program '{program}' and {eventname}")

        return replace_decimals(response['Items'])

    return []


@app.route('/replayrequests/track/{audioTrack}/program/{program}/event/{event}', cors=True, methods=['GET'],
           authorizer=authorizer)
def get_all_replay_requests_for_event_optosegment_end(event, program, audioTrack):
    """
    Returns all Queued Replay Requests for the Program/Event and Audio Track

    Returns:

        Replay Request based on Event, Program and AudioTrack

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    eventname = urllib.parse.unquote(event)
    program = urllib.parse.unquote(program)
    audioTrack = urllib.parse.unquote(audioTrack)

    replay_request_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

    response = replay_request_table.query(
        KeyConditionExpression=Key("PK").eq(f"{program}#{eventname}"),
        FilterExpression=Attr('Status').ne('Complete') & Attr('AudioTrack').eq(int(audioTrack)),
        ConsistentRead=True
    )

    if "Items" not in response:
        raise NotFoundError(f"No Replay Requests found for program '{program}' and {eventname}")

    return replace_decimals(response['Items'])


@app.route('/replayrequests/program/{program}/event/{event}/segmentend', cors=True, methods=['GET'],
           authorizer=authorizer)
def get_all_replays_for_segment_end(event, program):
    """
    Get all Queued,InProgress Replay Requests for the Program/Event

    Returns:

        Replay Request based on Event and Program

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    eventname = urllib.parse.unquote(event)
    program = urllib.parse.unquote(program)

    replay_request_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

    response = replay_request_table.query(
        KeyConditionExpression=Key("PK").eq(f"{program}#{eventname}"),
        FilterExpression=Attr('Status').ne('Complete'),
        ConsistentRead=True
    )

    if "Items" not in response:
        raise NotFoundError(f"No Replay Requests found for program '{program}' and {eventname}")

    return replace_decimals(response['Items'])


########################## Replay Changes Ends ######################


#############################################################
#                                                           #
#                  AWS SDK HELPER APIS                      #
#                                                           #
#############################################################
@app.route('/medialive/channels', cors=True, methods=['GET'], authorizer=authorizer)
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


@app.route('/mediatailor/channels', cors=True, methods=['GET'], authorizer=authorizer)
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


@app.route('/mediatailor/playbackconfigurations', cors=True, methods=['GET'], authorizer=authorizer)
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


@app.route('/replay/program/{program}/event/{event}/features', cors=True, methods=['GET'], authorizer=authorizer)
def getfeatures_by_program_event(program, event):
    """
    Get all the Features (as defined in plugin output attributes) based on Program and Event

    Returns:

        A list of Feature Names

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    features = []
    try:
        program = urllib.parse.unquote(program)
        event = urllib.parse.unquote(event)

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={
                "Name": event,
                "Program": program
            },
            ConsistentRead=True
        )
        if "Item" not in response:
            raise NotFoundError(f"Event '{event}' in Program '{program}' not found")

        profile = response['Item']['Profile']

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)
        profile_response = profile_table.get_item(
            Key={
                "Name": profile
            },
            ConsistentRead=True
        )

        if "Item" not in profile_response:
            raise NotFoundError(f"Profile '{profile}' not found")

        plugin_table = ddb_resource.Table(PLUGIN_TABLE_NAME)

        if 'Featurers' in profile_response['Item']:
            for feature in profile_response['Item']['Featurers']:
                response = plugin_table.get_item(
                    Key={
                        "Name": feature['Name'],
                        "Version": "v0"
                    },
                    ConsistentRead=True
                )

                # if "Item" not in response:
                #    raise NotFoundError(f"Plugin '{feature['Name']}' not found")
                if "Item" in response:
                    if "OutputAttributes" in response['Item']:
                        for key in response['Item']['OutputAttributes'].keys():
                            features.append(f"{feature['Name']} | {key}")

                dependent_plugin_features = get_features_from_dependent_plugins(feature)
                features.extend(dependent_plugin_features)

        if 'Classifier' in profile_response['Item']:
            # for feature in profile_response['Item']['Classifier']:
            response = plugin_table.get_item(
                Key={
                    "Name": profile_response['Item']['Classifier']['Name'],
                    "Version": "v0"
                },
                ConsistentRead=True
            )
            if "Item" in response:
                if "OutputAttributes" in response['Item']:
                    for key in response['Item']['OutputAttributes'].keys():
                        features.append(f"{profile_response['Item']['Classifier']['Name']} | {key}")

                dependent_plugin_features = get_features_from_dependent_plugins(profile_response['Item']['Classifier'])
                features.extend(dependent_plugin_features)

        if 'Labeler' in profile_response['Item']:
            # for feature in profile_response['Item']['Classifier']:
            response = plugin_table.get_item(
                Key={
                    "Name": profile_response['Item']['Labeler']['Name'],
                    "Version": "v0"
                },
                ConsistentRead=True
            )
            if "Item" in response:
                if "OutputAttributes" in response['Item']:
                    for key in response['Item']['OutputAttributes'].keys():
                        features.append(f"{profile_response['Item']['Labeler']['Name']} | {key}")

                dependent_plugin_features = get_features_from_dependent_plugins(profile_response['Item']['Labeler'])
                features.extend(dependent_plugin_features)


    except Exception as e:
        print(f"Unable to get replays for Program and Event: {str(e)}")
        raise ChaliceViewError(f"Unable to get replays for Program and Event: {str(e)}")

    return replace_decimals(features)

def get_features_from_dependent_plugins(pluginType):
    plugin_table = ddb_resource.Table(PLUGIN_TABLE_NAME)
    features = []

    if 'DependentPlugins' in pluginType:
        for dependent_plugin in pluginType['DependentPlugins']:
            response = plugin_table.get_item(
                Key={
                    "Name": dependent_plugin['Name'],
                    "Version": dependent_plugin['Version']
                },
                ConsistentRead=True
            )
            if "Item" in response:
                if "OutputAttributes" in response['Item']:
                    for key in response['Item']['OutputAttributes'].keys():
                        features.append(f"{dependent_plugin['Name']} | {key}")

    return features
    
@app.route('/event/program/hlslocation/update', cors=True, methods=['POST'], authorizer=authorizer)
def update_hls_manifest_for_event():
    """
    Updates HLS Manifest S3 location with the event

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        event = json.loads(app.current_request.raw_body.decode())

        name = event["Name"]
        program = event["Program"]
        hls_location = event["HlsLocation"]
        audiotrack = event["AudioTrack"]

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={
                "Name": name,
                "Program": program
            },
            UpdateExpression="SET #HlsMasterManifest.#AudioTrack = :Manifest",
            ExpressionAttributeNames={
                "#HlsMasterManifest": "HlsMasterManifest",
                "#AudioTrack": audiotrack
            },
            ExpressionAttributeValues={
                ":Manifest": hls_location
            }
        )

    except Exception as e:
        print(f"Unable to update HLS Master Manifest for event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to update HLS Master Manifest for event '{name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully stored the HLS Master Manifest for event '{name}' in program '{program}'")

        return {}


@app.route('/event/program/edllocation/update', cors=True, methods=['POST'], authorizer=authorizer)
def update_edl_for_event():
    """
    Updates EDL S3 location with the event

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        event = json.loads(app.current_request.raw_body.decode())

        name = event["Name"]
        program = event["Program"]
        edl_location = event["EdlLocation"]
        audiotrack = event["AudioTrack"]

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={
                "Name": name,
                "Program": program
            },
            UpdateExpression="SET #EdlLocation.#AudioTrack = :Manifest",
            ExpressionAttributeNames={
                "#EdlLocation": "EdlLocation",
                "#AudioTrack": audiotrack
            },
            ExpressionAttributeValues={
                ":Manifest": edl_location
            }
        )

    except Exception as e:
        print(f"Unable to update HLS Master Manifest for event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to update HLS Master Manifest for event '{name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully stored the HLS Master Manifest for event '{name}' in program '{program}'")

        return {}


def split_s3_path(s3_path):
    path_parts = s3_path.replace("s3://", "").split("/")
    bucket = path_parts.pop(0)
    key = "/".join(path_parts)
    return bucket, key


def create_signed_url(s3_path):
    bucket, objkey = split_s3_path(s3_path)
    try:
        expires = 86400
        url = s3_client.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': bucket,
                'Key': objkey
            }, ExpiresIn=expires)
        return url
    except Exception as e:
        print(e)
        raise e


@app.route('/program/{program}/event/{event}/hls/eventmanifest/track/{audiotrack}', cors=True, methods=['GET'],
           authorizer=authorizer)
def get_hls_manifest_by_event(program, event, audiotrack):
    """
    Returns the HLS format of an MRE Event as a octet-stream

    Returns:

       HLS format of an MRE Event as a octet-stream

    Raises:
        404 - NotFoundError
    """
    program = urllib.parse.unquote(program)
    event = urllib.parse.unquote(event)
    audiotrack = urllib.parse.unquote(audiotrack)

    event_table = ddb_resource.Table(EVENT_TABLE_NAME)

    response = event_table.get_item(
        Key={
            "Name": event,
            "Program": program
        },
        ConsistentRead=True
    )
    if "Item" not in response:
        raise NotFoundError(f"Event '{event}' in Program '{program}' not found")

    if 'HlsMasterManifest' not in response['Item']:
        return {
            "HlsMasterManifest": "No Content found"
        }

    master_manifest = response['Item']['HlsMasterManifest']

    if str(audiotrack) in master_manifest.keys():
        # url = create_signed_url(master_manifest[str(audiotrack)])
        s3_location = master_manifest[str(audiotrack)]
        parts = s3_location.split('/')
        bucket = parts[2]
        key = '/'.join(parts[-4:])

        hlsfilecontent = ""
        file_content = s3_resource.Object(bucket, key).get()['Body'].read().decode('utf-8').splitlines()
        for line in file_content:
            hlsfilecontent += str(line) + "\n"

        return Response(body=bytes(hlsfilecontent, 'utf-8'),
                        status_code=200,
                        headers={'Content-Type': 'application/octet-stream'})

    return {
        "HlsMasterManifest": "No Content found"
    }


@app.route('/program/{program}/event/{event}/hls/replaymanifest/replayid/{replayid}', cors=True, methods=['GET'],
           authorizer=authorizer)
def get_hls_manifest_by_replayid(program, event, replayid):
    """
    Returns the HLS format of an MRE Replay as a octet-stream

    Returns:

       HLS format of an MRE Replay as a octet-stream

    Raises:
        404 - NotFoundError
    """

    program = urllib.parse.unquote(program)
    event = urllib.parse.unquote(event)
    replayid = urllib.parse.unquote(replayid)

    replay_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

    response = replay_table.get_item(
        Key={
            "PK": f"{program}#{event}",
            "ReplayId": replayid
        },
        ConsistentRead=True
    )
    if "Item" not in response:
        raise NotFoundError(f"Event '{event}' in Program '{program}' not found")

    if 'HlsLocation' not in response['Item']:
        return {
            "HlsMasterManifest": "No Content found"
        }

    master_manifest = response['Item']['HlsLocation']

    # Every Replay request has this Attribute with a default value of '-'
    # If this has been updated with a s3 location, create the master manifest content to be sent back
    if master_manifest != '-':

        parts = master_manifest.replace(':', '').split('/')
        print(parts)
        bucket = parts[2]
        key = '/'.join(parts[-3:])

        hlsfilecontent = ""
        file_content = s3_resource.Object(bucket, key).get()['Body'].read().decode('utf-8').splitlines()
        for line in file_content:
            hlsfilecontent += str(line) + "\n"

        return Response(body=bytes(hlsfilecontent, 'utf-8'),
                        status_code=200,
                        headers={'Content-Type': 'application/octet-stream'})
    else:
        return {
            "HlsMasterManifest": "No Content found"
        }


@app.route('/program/{program}/event/{event}/edl/track/{audiotrack}', cors=True, methods=['GET'], authorizer=authorizer)
def get_edl_by_event(program, event, audiotrack):
    """
    Returns the EDL format of an MRE Event as a octet-stream

    Returns:

       EDL format of an MRE Event as a octet-stream

    Raises:
        404 - NotFoundError
    """
    program = urllib.parse.unquote(program)
    event = urllib.parse.unquote(event)
    audiotrack = urllib.parse.unquote(audiotrack)

    event_table = ddb_resource.Table(EVENT_TABLE_NAME)

    response = event_table.get_item(
        Key={
            "Name": event,
            "Program": program
        },
        ConsistentRead=True
    )
    if "Item" not in response:
        raise NotFoundError(f"Event '{event}' in Program '{program}' not found")

    if 'EdlLocation' not in response['Item']:
        return {"EdlLocation": "No Content found"}

    edl = response['Item']['EdlLocation']
    if str(audiotrack) in edl.keys():

        s3_location = edl[str(audiotrack)]
        parts = s3_location.split('/')
        bucket = parts[2]
        key = '/'.join(parts[-4:])

        edlfilecontent = ""
        file_content = s3_resource.Object(bucket, key).get()['Body'].read().decode('utf-8').splitlines()
        for line in file_content:
            edlfilecontent += str(line) + "\n"

        return Response(body=bytes(edlfilecontent, 'utf-8'),
                        status_code=200,
                        headers={'Content-Type': 'application/octet-stream'})

    return {
        "EdlLocation": "No Content found"
    }


@app.route('/replayrequest/mp4location/update', cors=True, methods=['POST'], authorizer=authorizer)
def update_mp4_for_replay_request():
    """
    Updates MP4 file location with the Replay Request

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        event = json.loads(app.current_request.raw_body.decode())

        event_name = event["Name"]
        program_name = event["Program"]
        replay_request_id = event["ReplayRequestId"]
        mp4_location = event["Mp4Location"]
        thumbnail_location = event["Thumbnail"]

        event_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        event_table.update_item(
            Key={
                "PK": f"{program_name}#{event_name}",
                "ReplayId": replay_request_id
            },
            UpdateExpression="SET #mp4Location = :location, #Mp4ThumbnailLoc = :thumbnail",
            ExpressionAttributeNames={
                "#mp4Location": "Mp4Location",
                "#Mp4ThumbnailLoc": "Mp4ThumbnailLocation"
            },
            ExpressionAttributeValues={
                ":location": mp4_location,
                ":thumbnail": thumbnail_location
            }
        )

    except Exception as e:
        print(
            f"Unable to update MP4 location for replay request {replay_request_id} and event '{event_name}' in program '{program_name}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to update MP4 location  for replay request {replay_request_id} and event '{event_name}' in program '{program_name}': {str(e)}")

    else:
        print(
            f"Successfully stored the MP4 location for replay request {replay_request_id} and event '{event_name}' in program '{program_name}'")

        return {}


@app.route('/replayrequest/update/hls/manifest', cors=True, methods=['POST'], authorizer=authorizer)
def update_hls_for_replay_request():
    """
    Updates HLS S3 manifest file location with the Replay Request

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        event = json.loads(app.current_request.raw_body.decode())

        event_name = event["Event"]
        program_name = event["Program"]
        replay_request_id = event["ReplayRequestId"]
        hls_location = event["HlsLocation"]
        thumbnail_location = event["Thumbnail"]

        event_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        event_table.update_item(
            Key={
                "PK": f"{program_name}#{event_name}",
                "ReplayId": replay_request_id
            },
            UpdateExpression="SET #HlsLocation = :location, #HlsThumbnailLoc = :thumbnail",
            ExpressionAttributeNames={
                "#HlsLocation": "HlsLocation",
                "#HlsThumbnailLoc": "HlsThumbnailLoc"
            },
            ExpressionAttributeValues={
                ":location": hls_location,
                ":thumbnail": thumbnail_location
            }
        )

    except Exception as e:
        print(
            f"Unable to update HLS Master Manifest for replay request {replay_request_id} and event '{event_name}' in program '{program_name}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to update HLS Master Manifest for replay request {replay_request_id} and event '{event_name}' in program '{program_name}': {str(e)}")

    else:
        print(
            f"Successfully stored the HLS Master Manifest for replay request {replay_request_id} and event '{event_name}' in program '{program_name}'")

        return {}


# //////////////////////////////////////////////////////// API using SHA512 Hash (HMAC) based Auth /////////////////////////////////////////////////////////////

@app.authorizer()
def jwt_auth(auth_request):
    '''
        Provides API Auth using HS512 (HMAC) based Authentication using a Shared Secret Key and an expiring JWT Token
        Clients invoke the API by sending the Bearer JWT Token.
    '''

    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager'
    )
    get_secret_value_response = client.get_secret_value(
        SecretId=HLS_HS256_API_AUTH_SECRET_KEY_NAME
    )

    try:
        decoded_payload = jwt.decode(auth_request.token.replace("Bearer", '').strip(),
                                     get_secret_value_response['SecretString'], algorithms=["HS512"])
    except Exception as e:
        print(e)
        return AuthResponse(routes=[''], principal_id='user')

    return AuthResponse(routes=[
        '/mre/streaming/auth',
        '/program/*/gameid/*/hls/stream/locations',
        '/event/all/external'
    ], principal_id='user')


def get_cloudfront_security_credentials():
    '''
        Generates Cloudfront Signed Cookie creds which are valid for 1 day.
    '''

    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager'
    )

    private_key_secret = client.get_secret_value(
        SecretId=CLOUDFRONT_COOKIE_PRIVATE_KEY_FROM_SECRET_MGR
    )
    privateKey = private_key_secret['SecretString']
    privateKey = rsa.PrivateKey.load_pkcs1(privateKey)

    key_pair_id_secret = client.get_secret_value(
        SecretId=CLOUDFRONT_COOKIE_KEY_PAIR_ID_FROM_SECRET_MGR
    )
    key_pair_id = key_pair_id_secret['SecretString']

    expiry = datetime.now() + timedelta(days=1)

    rsa_signer = functools.partial(
        rsa.sign, priv_key=privateKey, hash_method='SHA-1'
    )
    cf_signer = CloudFrontSigner(key_pair_id, rsa_signer)
    policy = cf_signer.build_policy(f"https://{HLS_STREAM_CLOUDFRONT_DISTRO}/*", expiry).encode('utf8')
    policy_64 = cf_signer._url_b64encode(policy).decode('utf8')
    signature = rsa_signer(policy)
    signature_64 = cf_signer._url_b64encode(signature).decode('utf8')

    return ({
        "CloudFront-Policy": policy_64,
        "CloudFront-Signature": signature_64,
        "CloudFront-Key-Pair-Id": key_pair_id,
    })


@app.route('/mre/streaming/auth', cors=True, methods=['GET'], authorizer=jwt_auth)
def get_mre_stream_auth():
    '''
    Returns Cloudfront Signed Cookie creds which are valid for 1 day.
    Clients can use these creds to cache locally and make subsequent calls to 
    Cloudfront URLs (for HLS Streaming and rendering thumbnails)

    Returns:

        .. code-block:: python

            {
                "CloudFront-Policy": "",
                "CloudFront-Signature": "",
                "CloudFront-Key-Pair-Id": ""
            }
    '''
    return get_cloudfront_security_credentials()


@app.route('/program/{program}/gameid/{event}/hls/stream/locations', cors=True, methods=['GET'], authorizer=jwt_auth)
def get_replay_hls_locations(program, event):
    '''
    Returns Cloudfront links for Replay HLS streams, thumbnails along with Cloudfront Signed Cookie Creds.
    Clients first Authorize with this API using JWT tokens and use the Cloudfront Signed Cookie Creds
    to make calls to the Cloudfront URLs to stream HLS

    Returns:

        .. code-block:: python

            {
                "Replays": ",
                "AuthInfo": {
                    "Policy": "",
                    "Signature": "",
                    "KeyPaidId": ""
                }
            }
    '''

    program = urllib.parse.unquote(program)
    event = urllib.parse.unquote(event)

    cfn_credentials = get_cloudfront_security_credentials()

    replay_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

    replays = replay_table.query(
        KeyConditionExpression=Key("PK").eq(f"{program}#{event}")
    )
    print('--------replays--------')
    print(replays)

    all_replays = []

    if 'Items' in replays:
        for replay in replays['Items']:
            temp_replay = {}
            if 'DurationbasedSummarization' in replay:
                temp_replay['DurationMinutes'] = replay['DurationbasedSummarization']['Duration']

            if 'HlsLocation' in replay:
                s3_hls_location = replay['HlsLocation']

                if s3_hls_location != '-':
                    s3_hls_location = s3_hls_location.replace(':', '').split('/')

                    # ['s3', '', 'aws-mre-clip-gen-output', 'HLS', 'ak555-testprogram', '4K', '']
                    keyprefix = f"{s3_hls_location[3]}/{s3_hls_location[4]}/{s3_hls_location[5]}"
                    temp_replay['HLSLocation'] = f"https://{HLS_STREAM_CLOUDFRONT_DISTRO}/{keyprefix}"
                else:
                    temp_replay['HLSLocation'] = s3_hls_location
            else:
                temp_replay['HLSLocation'] = ''

            if 'HlsThumbnailLoc' in replay:
                hls_thumbnail_location = replay['HlsThumbnailLoc']
                if hls_thumbnail_location != '-':
                    tmp_loc = hls_thumbnail_location.replace(':', '').split('/')

                    # ['s3', '', 'bucket_name', 'HLS', 'UUID', 'thumbnails', '4K', '']
                    key_prefix = f"{tmp_loc[3]}/{tmp_loc[4]}/{tmp_loc[5]}/{tmp_loc[6]}/{tmp_loc[7]}"
                    temp_replay['ThumbnailLocation'] = f"https://{HLS_STREAM_CLOUDFRONT_DISTRO}/{key_prefix}"
                else:
                    temp_replay['ThumbnailLocation'] = hls_thumbnail_location
            else:
                temp_replay['ThumbnailLocation'] = ''

            # Only include replays that have HLS clips generated
            if 'HlsLocation' in replay:
                s3_hls_location = replay['HlsLocation']
                if s3_hls_location != '-':
                    all_replays.append(temp_replay)

    return {
        "Replays": all_replays,
        "AuthInfo": {
            "Policy": cfn_credentials["CloudFront-Policy"],
            "Signature": cfn_credentials["CloudFront-Signature"],
            "KeyPaidId": cfn_credentials["CloudFront-Key-Pair-Id"]
        }
    }


@app.route('/event/all/external', cors=True, methods=['GET'], authorizer=jwt_auth)
def list_events_external():
    """
    List all the events for integrating with external systems.
    API Auth using HS256 (HMAC) based Authentication using a Shared Secret Key and an expiring JWT Token
    Clients invoke the API by sending a Bearer Token.

    Returns:

        .. code-block:: python

            [
                {
                    Event
                }
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        print("Listing all the events")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.scan(
            ConsistentRead=True
        )

        events = response["Items"]

        while "LastEvaluatedKey" in response:
            response = event_table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                ConsistentRead=True
            )

            events.extend(response["Items"])

        all_events = []
        for event in events:
            if 'LastKnownMediaLiveConfig' in event:
                event.pop('LastKnownMediaLiveConfig')
                all_events.append(event)


    except Exception as e:
        print(f"Unable to list all the events: {str(e)}")
        raise ChaliceViewError(f"Unable to list all the events: {str(e)}")

    else:
        return replace_decimals(all_events)


@app.route('/event/future/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_future_events():
    """
    List all the events scheduled in the future in the next 1 Hr.

    Returns:

        .. code-block:: python

            [
                {
                    Event
                }
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)
        cur_utc_time = datetime.utcnow()

        # Look for Events scheduled in the next 1 Hr
        future_time_one_hr_away = cur_utc_time + timedelta(hours=1)

        filter_expression = Attr("Start").between(cur_utc_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                  future_time_one_hr_away.strftime("%Y-%m-%dT%H:%M:%SZ"))

        response = event_table.scan(
            FilterExpression=filter_expression,
            ConsistentRead=True,
            ProjectionExpression="Profile, #status, #program, #created, FrameRate, #eventId, #start, #eventname",
            ExpressionAttributeNames={'#status': 'Status', '#created': 'Created', '#program': 'Program',
                                      '#eventId': 'Id', '#start': 'Start', '#eventname': 'Name'}
        )

        future_events = response["Items"]
    except Exception as e:
        print(f"Unable to list future events: {str(e)}")
        raise ChaliceViewError(f"Unable to list future events: {str(e)}")

    else:
        return replace_decimals(future_events)


@app.route('/event/range/{fromDate}/{toDate}', cors=True, methods=['GET'], authorizer=authorizer)
def list_range_based_events(fromDate, toDate):
    """
    List all the events based on Date Range which is in UTC format

    Returns:

        .. code-block:: python

            [
                {
                    Event
                }
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)
        filter_expression = Attr("Start").between(fromDate, toDate)

        response = event_table.scan(
            FilterExpression=filter_expression,
            ConsistentRead=True,
            ProjectionExpression="Profile, #status, #program, #created, FrameRate, #eventId, #start, #eventname",
            ExpressionAttributeNames={'#status': 'Status', '#created': 'Created', '#program': 'Program',
                                      '#eventId': 'Id', '#start': 'Start', '#eventname': 'Name'}
        )
        future_events = response["Items"]

    except Exception as e:
        print(f"Unable to list range based events: {str(e)}")
        raise ChaliceViewError(f"Unable to list range based events: {str(e)}")

    else:
        return replace_decimals(future_events)


@app.route('/event/queued/all/limit/{limit}/closestEventFirst/{closestEventFirst}', cors=True, methods=['GET'], authorizer=authorizer)
def get_all_queued_events(limit,closestEventFirst='Y'):
    """
    Gets all Queued Events for processing.

    Returns:

        .. code-block:: python

            [
                {
                    Event
                }
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        limit = urllib.parse.unquote(limit)
        closestEventFirst = urllib.parse.unquote(closestEventFirst)

        if closestEventFirst.lower() not in ['y','n']:
            raise Exception(f"Invalid closestEventFirst parameter value specified. Valid values are Y/N")

        events_table = ddb_resource.Table(EVENT_TABLE_NAME)

        query = {
            'IndexName': EVENT_PAGINATION_INDEX,
            'Limit': limit,
            'ScanIndexForward': True if closestEventFirst == 'Y' else False,  # Get the closest events first by default
            'KeyConditionExpression': Key("PaginationPartition").eq("PAGINATION_PARTITION"),
            'FilterExpression': Attr("Status").eq('Queued'),
            'ProjectionExpression': "Profile, #status, #program, #created, FrameRate, #eventId, #start, #eventname, #programid, #srcvideoAuth, #srcvideoUrl, #bootstrapTimeInMinutes",
            'ExpressionAttributeNames': {'#status': 'Status', '#created': 'Created', '#program' : 'Program', '#eventId' : 'Id', '#start': 'Start', '#eventname' : 'Name',
                "#programid": "ProgramId", "#srcvideoAuth": "SourceVideoAuth", "#srcvideoUrl": "SourceVideoUrl", "#bootstrapTimeInMinutes" : "BootstrapTimeInMinutes"
            }
        }

        response = events_table.query(**query)
        queued_events = response["Items"]

        while "LastEvaluatedKey" in response and (limit - len(queued_events) > 0):
            query["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            query["Limit"] = limit - len(queued_events)
            response = events_table.query(**query)
            queued_events.extend(response["Items"])

    except Exception as e:
        print(f"Unable to get all Queued events: {str(e)}")
        raise ChaliceViewError(f"Unable to get count of current events: {str(e)}")

    else:
        return replace_decimals(queued_events)

@app.route('/event/processed/{id}', cors=True, methods=['DELETE'], authorizer=authorizer)
def delete_processed_events_from_control(id):
    """
    Deletes Events from the Control table used to track Event processing status

    Returns:

        None
    """

    event_id = urllib.parse.unquote(id)

    try:

        current_events_table = ddb_resource.Table(CURRENT_EVENTS_TABLE_NAME)

        current_events_table.delete_item(
                    Key={
                        "EventId": event_id
                    }
                )

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to delete the event '{event_id}': {str(e)}")
        raise ChaliceViewError(f"Unable to delete the event '{event_id}': {str(e)}")

    else:
        print(f"Deletion of event '{event_id}' successful")
        return {}

    

@app.route('/replay/event/{name}/program/{program}/id/{replayid}', cors=True, methods=['DELETE'], authorizer=authorizer)
def delete_replay(name, program, replayid):
    """
    Deletes an event by name, program and ReplayId.

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)
        replayid = urllib.parse.unquote(replayid)

        replay_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        response = replay_table.get_item(
            Key={
                "PK": program + "#" + name,
                "ReplayId": replayid
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Event '{name}' in Program '{program}' not found")
        elif response["Item"]["Status"] == "In Progress":
            raise BadRequestError(f"Cannot delete Replay as it is currently in progress")

        print(f"Deleting the Replay")

        response = replay_table.delete_item(
            Key={
                "PK": program + "#" + name,
                "ReplayId": replayid
            }
        )

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except BadRequestError as e:
        print(f"Got chalice BadRequestError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to delete the Replay: {str(e)}")
        raise ChaliceViewError(f"Unable to delete the Replay: {str(e)}")

    else:
        print(f"Deletion of Replay successful")
        return {}


@app.route('/event/{name}/program/{program}/hasreplays', cors=True, methods=['PUT'], authorizer=authorizer)
def update_event_with_replay(name, program):
    """
    Updates an event with a flag to indicate Replay creation.

    Returns:

        None
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={
                "Name": name,
                "Program": program
            },
            UpdateExpression="SET #hasreplays = :hasreplays",
            ExpressionAttributeNames={"#hasreplays": "hasReplays"},
            ExpressionAttributeValues={":hasreplays": True}
        )

    except Exception as e:
        print(f"Unable to update the event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to update the event '{name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully updated the event")

        return {}


@app.route('/event/program/export_data', cors=True, methods=['PUT'],
           authorizer=authorizer)
def store_event_export_data():
    """
    Store the Export data generated for the Event as a S3 Location

    Returns:

        None

    Raises:
        500 - ChaliceViewError
        
    """
    try:
        payload = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)
        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_name = payload['Name']
        program = payload['Program']
        
        if 'IsBaseEvent' not in payload:
            raise Exception(f"Unable to determine the event type")

        if payload['IsBaseEvent'] not in ['Y', 'N']:
            raise Exception(f"Invalid base event type")

        if payload['IsBaseEvent'] == 'Y':
            updateExpression="SET #EventDataExportLocation = :EventDataExportLocation"
            expressionAttributeNames= { "#EventDataExportLocation": "EventDataExportLocation" }
            expressionAttributeValues= { ":EventDataExportLocation": payload['ExportDataLocation'] }
        else:
            updateExpression="SET #FinalEventDataExportLocation = :FinalEventDataExportLocation"
            expressionAttributeNames= { "#FinalEventDataExportLocation": "FinalEventDataExportLocation" }
            expressionAttributeValues= { ":FinalEventDataExportLocation": payload['ExportDataLocation'] }

        event_table.update_item(
            Key={
                "Name": event_name,
                "Program": program,
            },
            UpdateExpression=updateExpression,
            ExpressionAttributeNames=expressionAttributeNames,
            ExpressionAttributeValues=expressionAttributeValues
        )

    except Exception as e:
        print(
            f"Unable to store the Event data export of event '{event_name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to store the Event data export of event '{event_name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully stored the Event data export of event '{event_name}' in program '{program}'")

        return {}


@app.route('/export/data/event/{event}/program/{program}', cors=True, methods=['GET'],
           authorizer=authorizer)
def get_event_export_data(program, event):
    """
    Returns the export data for an event as a octet-stream

    Returns:

        Event export data as octet-stream

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        500 - ChaliceViewError
    """
    program = urllib.parse.unquote(program)
    event = urllib.parse.unquote(event)
    

    event_table = ddb_resource.Table(EVENT_TABLE_NAME)

    response = event_table.get_item(
        Key={
            "Name": event,
            "Program": program
        },
        ConsistentRead=True
    )
    if "Item" not in response:
        raise NotFoundError(f"Event '{event}' in Program '{program}' not found")

    if 'EventDataExportLocation' not in response['Item']:
        return {
            "EventDataExportLocation": "NA"
        }

    export_location = response['Item']['EventDataExportLocation']
    
    parts = export_location.split('/')
    bucket = parts[2]
    key = '/'.join(parts[-3:])

    export_filecontent = ""
    file_content = s3_resource.Object(bucket, key).get()['Body'].read().decode('utf-8').splitlines()
    for line in file_content:
        export_filecontent += str(line) + "\n"

    return Response(body=bytes(export_filecontent, 'utf-8'),
                    status_code=200,
                    headers={'Content-Type': 'application/octet-stream'})

@app.route('/replay/event/program/export_data', cors=True, methods=['PUT'],authorizer=authorizer)
def store_replay_export_data():
    """
    Store the Export data generated for the Replay

    Returns:

        None

    Raises:
        500 - ChaliceViewError
        
    """
    try:
        payload = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)
        event_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        event_name = payload['Name']
        program = payload['Program']
        
        if 'IsBaseEvent' not in payload:
            raise Exception(f"Unable to determine the event type")

        if payload['IsBaseEvent'] not in ['Y', 'N']:
            raise Exception(f"Invalid base event type")

        if payload['IsBaseEvent'] == 'Y':
            updateExpression="SET #ReplayDataExportLocation = :ReplayDataExportLocation"
            expressionAttributeNames= { "#ReplayDataExportLocation": "ReplayDataExportLocation" }
            expressionAttributeValues= { ":ReplayDataExportLocation": payload['ExportDataLocation'] }
        else:
            updateExpression="SET #FinalReplayDataExportLocation = :FinalReplayDataExportLocation"
            expressionAttributeNames= { "#FinalReplayDataExportLocation": "FinalReplayDataExportLocation" }
            expressionAttributeValues= { ":FinalReplayDataExportLocation": payload['ExportDataLocation'] }

        event_table.update_item(
            Key={
                "PK": f"{program}#{event_name}",
                "ReplayId": payload['ReplayId']
            },
            UpdateExpression=updateExpression,
            ExpressionAttributeNames=expressionAttributeNames,
            ExpressionAttributeValues=expressionAttributeValues
        )

    except Exception as e:
        print(
            f"Unable to store the Replay data export of event '{event_name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to store the Replay data export of event '{event_name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully stored the Replay data export of event '{event_name}' in program '{program}'")

        return {}


@app.route('/export/data/replay/{id}/event/{event}/program/{program}', cors=True, methods=['GET'],
           authorizer=authorizer)
def get_replay_export_data(program, event, id):
    """
    Returns the Replay Export Data as octet-stream

    Returns:

        Replay Export Data as octet-stream

    Raises:
        400 - BadRequestError
        404 - NotFoundError
    """
    program = urllib.parse.unquote(program)
    event = urllib.parse.unquote(event)
    replay_id = urllib.parse.unquote(id)
    

    replay_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

    response = replay_table.get_item(
        Key={
            "PK": f"{program}#{event}",
            "ReplayId": replay_id
        },
        ConsistentRead=True
    )
    if "Item" not in response:
        raise NotFoundError(f"Event '{event}' in Program '{program}' not found")

    if 'ReplayDataExportLocation' not in response['Item']:
        return {
            "ReplayDataExportLocation": "NA"
        }

    export_location = response['Item']['ReplayDataExportLocation']
    
    parts = export_location.split('/')
    bucket = parts[2]
    key = '/'.join(parts[-3:])

    export_filecontent = ""
    file_content = s3_resource.Object(bucket, key).get()['Body'].read().decode('utf-8').splitlines()
    for line in file_content:
        export_filecontent += str(line) + "\n"

    return Response(body=bytes(export_filecontent, 'utf-8'),
                    status_code=200,
                    headers={'Content-Type': 'application/octet-stream'})