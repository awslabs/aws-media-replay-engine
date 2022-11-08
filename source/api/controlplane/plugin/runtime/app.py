#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import json
import uuid
import urllib.parse
import boto3
from decimal import Decimal
from datetime import datetime
from chalice import Chalice
from chalice import IAMAuthorizer
from chalice import ChaliceViewError, BadRequestError, NotFoundError
from boto3.dynamodb.types import TypeSerializer
from boto3.dynamodb.conditions import Key, Attr
from botocore.client import ClientError
from jsonschema import validate, ValidationError
from chalicelib import DecimalEncoder
from chalicelib import load_api_schema, replace_decimals, generate_plugin_state_definition

app = Chalice(app_name='aws-mre-controlplane-plugin-api')

API_VERSION = '1.0.0'
authorizer = IAMAuthorizer()
serializer = TypeSerializer()

ddb_resource = boto3.resource("dynamodb")
ddb_client = boto3.client("dynamodb")

CONTENT_GROUP_TABLE_NAME = os.environ['CONTENT_GROUP_TABLE_NAME']
MODEL_TABLE_NAME = os.environ['MODEL_TABLE_NAME']
PLUGIN_TABLE_NAME = os.environ['PLUGIN_TABLE_NAME']
FRAMEWORK_VERSION = os.environ['FRAMEWORK_VERSION']
PLUGIN_VERSION_INDEX = os.environ['PLUGIN_VERSION_INDEX']
PLUGIN_NAME_INDEX = os.environ['PLUGIN_NAME_INDEX']

API_SCHEMA = load_api_schema()


# region local function
# return plugins that have circular dependency
# otherwise return None
def find_circular_dependency(plugin_name, dependent_plugins):
    response = None

    for dependent_plugin in dependent_plugins:
        # get full dependent plugins tree of each of the dependent plugins of the list
        all_dependencies = get_plugin_dependency_tree(dependent_plugin)

        if all_dependencies:
            all_dependent_plugin_names = [plugin["Name"] for plugin in all_dependencies]
            if plugin_name in all_dependent_plugin_names:
                print(f"Found circular plugin between '{plugin_name}' and '{dependent_plugin}")
                response = (dependent_plugin, plugin_name)

    return response


# endregion

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

            circular_dependency_plugin_names = find_circular_dependency(name, dependent_plugins)

            if circular_dependency_plugin_names:
                raise BadRequestError(
                    f"Found Circular Dependency between plugin: '{circular_dependency_plugin_names[0]}' and '{circular_dependency_plugin_names[1]}'")

        else:
            dependent_plugins = []

        output_attributes = plugin["OutputAttributes"] if "OutputAttributes" in plugin else {}

        print("Adding all the Content Group values passed in the request to the 'ContentGroup' DynamoDB table")

        ddb_resource.batch_write_item(
            RequestItems={
                CONTENT_GROUP_TABLE_NAME: [{"PutRequest": {"Item": {"Name": content_group}}} for content_group in plugin["ContentGroups"]]
            }
        )

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
        raise BadRequestError(str(e))

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to register or publish a new version of the plugin: {str(name)}")
        raise ChaliceViewError(f"Unable to register or publish a new version of the plugin: {str(name)}")

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


@app.route('/plugin/{name}/dependentplugins/all', cors=True, methods=['GET'], authorizer=authorizer)
def get_plugin_dependency_tree(name):
    """
    List multi level dependency plugins by traversing every dependency level until no more dependencies are found.
    Uses version "v0" of the given plugin and of every dependency.

    Returns:
        .. code-block:: python

            [
                {
                    "Name": string,
                    "PluginData": {
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
                    "DependentFor": ["pluginName1",...]
                },
                ...
            ]

        Raises:
            500 - ChaliceViewError
        """
    try:
        plugin_dependencies_result = []

        name = urllib.parse.unquote(name)

        print(f"Getting plugin dependencies of plugin '{name}'")

        plugin_table = ddb_resource.Table(PLUGIN_TABLE_NAME)

        # get the latest version of the plugin
        response = plugin_table.get_item(
            Key={
                "Name": name,
                "Version": "v0"
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Plugin '{name}' not found")

        # memoize dependencies until they are also searched for their dependencies - instead of recursive search
        memoized_dependent_plugins = {response["Item"]["Name"]: response["Item"]["DependentPlugins"]}
        plugins_searched = [response["Item"]["Name"]]

        while len(memoized_dependent_plugins) > 0:
            new_memoized_dependent_plugins = {}

            for parent_name, dependency_list in memoized_dependent_plugins.items():
                for dependent_plugin in dependency_list:
                    # find dependencies of discovered dependent plugin
                    if dependent_plugin not in plugins_searched:
                        response = plugin_table.get_item(
                            Key={
                                "Name": dependent_plugin,
                                "Version": "v0"
                            },
                            ConsistentRead=True
                        )

                        plugin_dependencies_result.append({
                            "Name": dependent_plugin,
                            "pluginData": response["Item"],
                            "DependentFor": [parent_name]
                        })

                        plugins_searched.append(response["Item"]["Name"])
                        # add new discovered dependencies
                        new_memoized_dependent_plugins[response["Item"]["Name"]] = response["Item"]["DependentPlugins"]

                    else:
                        # add dependent plugin to response or append required for if exists
                        name_index = next((
                            index for (index, d) in enumerate(plugin_dependencies_result) if d["Name"] ==
                                                                                             dependent_plugin), None
                        )
                        plugin_dependencies_result[name_index]["DependentFor"].append(parent_name)

            # done discovering level of dependencies, copy the next level discovered
            memoized_dependent_plugins = new_memoized_dependent_plugins

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to list the dependent plugins of the plugin '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to list the dependent plugins of the plugin '{name}': {str(e)}")

    else:
        return plugin_dependencies_result
