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
from chalicelib import load_api_schema, replace_decimals

app = Chalice(app_name='aws-mre-controlplane-model-api')

API_VERSION = '1.0.0'
authorizer = IAMAuthorizer()
serializer = TypeSerializer()

ddb_resource = boto3.resource("dynamodb")
ddb_client = boto3.client("dynamodb")

CONTENT_GROUP_TABLE_NAME = os.environ['CONTENT_GROUP_TABLE_NAME']
MODEL_TABLE_NAME = os.environ['MODEL_TABLE_NAME']
MODEL_VERSION_INDEX = os.environ['MODEL_VERSION_INDEX']
MODEL_NAME_INDEX = os.environ['MODEL_NAME_INDEX']

API_SCHEMA = load_api_schema()

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

        print("Adding all the Content Group values passed in the request to the 'ContentGroup' DynamoDB table")

        ddb_resource.batch_write_item(
            RequestItems={
                CONTENT_GROUP_TABLE_NAME: [{"PutRequest": {"Item": {"Name": content_group}}} for content_group in model["ContentGroups"]]
            }
        )

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
