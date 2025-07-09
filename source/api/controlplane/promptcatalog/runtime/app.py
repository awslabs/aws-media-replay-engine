#  Copyright 2024 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json
import os
import urllib.parse
from datetime import datetime

import boto3
from aws_lambda_powertools.utilities.validation import (SchemaValidationError,
                                                        validate)
from boto3.dynamodb.conditions import Attr, Key
from boto3.dynamodb.types import TypeSerializer
from botocore.client import ClientError
from chalice import (BadRequestError, Chalice, ChaliceViewError, IAMAuthorizer,
                     NotFoundError)
from chalicelib import load_api_schema, replace_decimals
from aws_lambda_powertools import Logger

app = Chalice(app_name="aws-mre-controlplane-prompt-catalog-api")
logger = Logger(service="aws-mre-controlplane-prompt-catalog-api")

API_VERSION = "1.0.0"
authorizer = IAMAuthorizer()
serializer = TypeSerializer()

ddb_resource = boto3.resource("dynamodb")
ddb_client = boto3.client("dynamodb")

CONTENT_GROUP_TABLE_NAME = os.environ["CONTENT_GROUP_TABLE_NAME"]
PROMPT_CATALOG_TABLE_NAME = os.environ["PROMPT_CATALOG_TABLE_NAME"]
PROMPT_CATALOG_VERSION_INDEX = os.environ["PROMPT_CATALOG_VERSION_INDEX"]
PROMPT_CATALOG_NAME_INDEX = os.environ["PROMPT_CATALOG_NAME_INDEX"]

API_SCHEMA = load_api_schema()

prompt_catalog_table = ddb_resource.Table(PROMPT_CATALOG_TABLE_NAME)

# Create middleware to inject request context
@app.middleware('all')
def inject_request_context(event, get_response):
    # event is a Chalice Request object
    request_id = event.context.get('requestId', 'N/A')
    
    # Add request ID to persistent logger context
    logger.append_keys(request_id=request_id)
    
    response = get_response(event)
    return response

@app.route("/prompt", cors=True, methods=["POST"], authorizer=authorizer)
def create_prompt():
    """
    Create a new prompt or publish a new version of an existing prompt.

    Body:

    .. code-block:: python

        {
            "Name": string,
            "Description": string,
            "ContentGroups": list,
            "Template": string
        }

    Parameters:

        - Name: Name of the prompt
        - Description: Description of the prompt
        - ContentGroups: List of Content Groups to be associated with the prompt
        - Template: Prompt Template (Text)

    Returns:

        A dict containing the Name and Version of the created prompt

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
        prompt = json.loads(app.current_request.raw_body.decode())

        validate(event=prompt, schema=API_SCHEMA["create_prompt"])

        logger.info("Got a valid prompt schema")

        logger.info(
            "Adding all the Content Group values passed in the request to the 'ContentGroup' DynamoDB table"
        )

        ddb_resource.batch_write_item(
            RequestItems={
                CONTENT_GROUP_TABLE_NAME: [
                    {"PutRequest": {"Item": {"Name": content_group}}}
                    for content_group in prompt["ContentGroups"]
                ]
            }
        )

        name = prompt["Name"]

        response = prompt_catalog_table.get_item(
            Key={"Name": name, "Version": "v0"}, ConsistentRead=True
        )

        if "Item" not in response:
            logger.info(f"Adding a new prompt '{name}'")
            latest_version = 0
            higher_version = 1

        else:
            logger.info(f"Publishing a new version of the prompt '{name}'")
            latest_version = response["Item"]["Latest"]
            higher_version = int(latest_version) + 1

        prompt["Created"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        prompt["Enabled"] = True

        # Serialize Python object to DynamoDB object
        serialized_prompt = {k: serializer.serialize(v) for k, v in prompt.items()}

        ddb_client.transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": PROMPT_CATALOG_TABLE_NAME,
                        "Key": {"Name": {"S": name}, "Version": {"S": "v0"}},
                        "ConditionExpression": "attribute_not_exists(#Latest) OR #Latest = :Latest",
                        "UpdateExpression": "SET #Latest = :Higher_version, #Description = :Description, #ContentGroups = :ContentGroups, #Template = :Template, #Created = :Created, #Enabled = :Enabled",
                        "ExpressionAttributeNames": {
                            "#Latest": "Latest",
                            "#Description": "Description",
                            "#ContentGroups": "ContentGroups",
                            "#Template": "Template",
                            "#Created": "Created",
                            "#Enabled": "Enabled",
                        },
                        "ExpressionAttributeValues": {
                            ":Latest": {"N": str(latest_version)},
                            ":Higher_version": {"N": str(higher_version)},
                            ":Description": (
                                serialized_prompt["Description"]
                                if "Description" in serialized_prompt
                                else {"S": ""}
                            ),
                            ":ContentGroups": serialized_prompt["ContentGroups"],
                            ":Template": serialized_prompt["Template"],
                            ":Created": serialized_prompt["Created"],
                            ":Enabled": serialized_prompt["Enabled"],
                        },
                    }
                },
                {
                    "Put": {
                        "TableName": PROMPT_CATALOG_TABLE_NAME,
                        "Item": {
                            "Name": {"S": name},
                            "Version": {"S": "v" + str(higher_version)},
                            "Description": (
                                serialized_prompt["Description"]
                                if "Description" in serialized_prompt
                                else {"S": ""}
                            ),
                            "ContentGroups": serialized_prompt["ContentGroups"],
                            "Template": serialized_prompt["Template"],
                            "Created": serialized_prompt["Created"],
                            "Enabled": serialized_prompt["Enabled"],
                        },
                    }
                },
            ]
        )

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")  

    except Exception as e:
        logger.info(f"Unable to add or publish a new version of the prompt: {str(e)}")
        raise ChaliceViewError(
            f"Unable to add or publish a new version of the prompt: {str(e)}"
        )

    else:
        logger.info(
            f"Successfully added or published a new version of the prompt: {json.dumps(prompt)}"
        )

        return {"Name": prompt["Name"], "Version": "v" + str(higher_version)}


@app.route("/prompt/all", cors=True, methods=["GET"], authorizer=authorizer)
def list_prompts():
    """
    List the latest version of all the available prompts.
    Each prompt has version "v0" which holds a copy of the latest prompt revision.

    By default, return only the prompts that are "Enabled" in the system. In order
    to also return the "Disabled" prompts, include the query parameter "include_disabled=true".

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string,
                    "Description": string,
                    "ContentGroups": list,
                    "Template": string,
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
        logger.info("Listing the latest version of all the prompts")

        query_params = app.current_request.query_params

        if query_params and query_params.get("include_disabled") == "true":
            filter_expression = Attr("Enabled").is_in([True, False])
        else:
            filter_expression = Attr("Enabled").eq(True)

        response = prompt_catalog_table.query(
            IndexName=PROMPT_CATALOG_VERSION_INDEX,
            KeyConditionExpression=Key("Version").eq("v0"),
            FilterExpression=filter_expression,
        )

        prompts = response["Items"]

        while "LastEvaluatedKey" in response:
            response = prompt_catalog_table.query(
                IndexName=PROMPT_CATALOG_VERSION_INDEX,
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("Version").eq("v0"),
                FilterExpression=filter_expression,
            )

            prompts.extend(response["Items"])

    except Exception as e:
        logger.info(f"Unable to list the latest version of all the prompts: {str(e)}")
        raise ChaliceViewError(
            f"Unable to list the latest version of all the prompts: {str(e)}"
        )

    else:
        return replace_decimals(prompts)


@app.route(
    "/prompt/contentgroup/{content_group}/all",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def list_prompts_by_contentgroup(content_group):
    """
    List the latest version of all the prompts by content group.
    Each prompt has version "v0" which holds a copy of the latest prompt revision.

    By default, return only the prompts that are "Enabled" in the system. In order
    to also return the "Disabled" prompts, include the query parameter "include_disabled=true".

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string,
                    "Description": string,
                    "ContentGroups": list,
                    "Template": string,
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

        validate_path_parameters({"ContentGroup": content_group})

        logger.info(
            f"Listing the latest version of all the prompts for content group '{content_group}'"
        )

        query_params = app.current_request.query_params

        if query_params and query_params.get("include_disabled") == "true":
            filter_expression = Attr("Enabled").is_in([True, False])
        else:
            filter_expression = Attr("Enabled").eq(True)

        response = prompt_catalog_table.query(
            IndexName=PROMPT_CATALOG_VERSION_INDEX,
            KeyConditionExpression=Key("Version").eq("v0"),
            FilterExpression=Attr("ContentGroups").contains(content_group)
            & filter_expression,
        )

        prompts = response["Items"]

        while "LastEvaluatedKey" in response:
            response = prompt_catalog_table.query(
                IndexName=PROMPT_CATALOG_VERSION_INDEX,
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("Version").eq("v0"),
                FilterExpression=Attr("ContentGroups").contains(content_group)
                & filter_expression,
            )

            prompts.extend(response["Items"])

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")  
    
    except Exception as e:
        logger.info(
            f"Unable to list the latest version of all the prompts for content group '{content_group}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to list the latest version of all the prompts for content group '{content_group}': {str(e)}"
        )

    else:
        return replace_decimals(prompts)


@app.route("/prompt/{name}", cors=True, methods=["GET"], authorizer=authorizer)
def get_prompt_by_name(name):
    """
    Get the latest version of a prompt by name.

    Returns:

        .. code-block:: python

            {
                "Name": string,
                "Description": string,
                "ContentGroups": list,
                "Template": string,
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

        validate_path_parameters({"Name": name})

        logger.info(f"Getting the latest version of the prompt '{name}'")

        response = prompt_catalog_table.get_item(
            Key={"Name": name, "Version": "v0"}, ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Prompt '{name}' not found")

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")  
    
    except NotFoundError as e:
        logger.info(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        logger.info(f"Unable to get the latest version of the prompt '{name}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to get the latest version of the prompt '{name}': {str(e)}"
        )

    else:
        return replace_decimals(response["Item"])


@app.route(
    "/prompt/{name}/version/{version}",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_prompt_by_name_and_version(name, version):
    """
    Get a prompt by name and version.

    Returns:

        .. code-block:: python

            {
                "Name": string,
                "Description": string,
                "ContentGroups": list,
                "Template": string,
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

        validate_path_parameters({"Name": name, "Version": version})

        logger.info(f"Getting the prompt '{name}' with version '{version}'")

        response = prompt_catalog_table.get_item(
            Key={"Name": name, "Version": version}, ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Prompt '{name}' with version '{version}' not found")

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")  
    
    except NotFoundError as e:
        logger.info(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        logger.info(f"Unable to get the prompt '{name}' with version '{version}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to get the prompt '{name}' with version '{version}': {str(e)}"
        )

    else:
        return replace_decimals(response["Item"])


@app.route(
    "/prompt/{name}/version/all", cors=True, methods=["GET"], authorizer=authorizer
)
def list_prompt_versions(name):
    """
    List all the versions of a prompt by name.

    Returns:

        .. code-block:: python

            [
                {
                    "Name": string,
                    "Description": string,
                    "ContentGroups": list,
                    "Template": string,
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

        validate_path_parameters({"Name": name})
        
        logger.info(f"Getting all the versions of the prompt '{name}'")

        response = prompt_catalog_table.query(
            IndexName=PROMPT_CATALOG_NAME_INDEX,
            KeyConditionExpression=Key("Name").eq(name),
        )

        if "Items" not in response or len(response["Items"]) < 1:
            raise NotFoundError(f"Prompt '{name}' not found")

        versions = response["Items"]

        while "LastEvaluatedKey" in response:
            response = prompt_catalog_table.query(
                IndexName=PROMPT_CATALOG_NAME_INDEX,
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("Name").eq(name),
            )

            versions.extend(response["Items"])

        # Remove version 'v0' from the query result
        for index, version in enumerate(versions):
            if version["Version"] == "v0":
                versions.pop(index)
                break

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")  
    
    except NotFoundError as e:
        logger.info(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        logger.info(f"Unable to list the versions of the prompt '{name}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to list the versions of the prompt '{name}': {str(e)}"
        )

    else:
        return replace_decimals(versions)


@app.route("/prompt/{name}/status", cors=True, methods=["PUT"], authorizer=authorizer)
def update_prompt_status(name):
    """
    Enable or Disable the latest version of a prompt by name.

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

        validate_path_parameters({"Name": name})

        status = json.loads(app.current_request.raw_body.decode())

        validate(event=status, schema=API_SCHEMA["update_status"])

        logger.info("Got a valid status schema")

        logger.info(f"Updating the status of the latest version of prompt '{name}'")

        response = prompt_catalog_table.get_item(
            Key={"Name": name, "Version": "v0"}, ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Prompt '{name}' not found")

        latest_version = "v" + str(response["Item"]["Latest"])

        # Update version v0
        prompt_catalog_table.update_item(
            Key={"Name": name, "Version": "v0"},
            UpdateExpression="SET #Enabled = :Status",
            ExpressionAttributeNames={"#Enabled": "Enabled"},
            ExpressionAttributeValues={":Status": status["Enabled"]},
        )

        # Update the latest version
        prompt_catalog_table.update_item(
            Key={"Name": name, "Version": latest_version},
            UpdateExpression="SET #Enabled = :Status",
            ConditionExpression="attribute_exists(#Name) AND attribute_exists(#Version)",
            ExpressionAttributeNames={
                "#Enabled": "Enabled",
                "#Name": "Name",
                "#Version": "Version",
            },
            ExpressionAttributeValues={":Status": status["Enabled"]},
        )

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")  

    except ClientError as e:
        logger.info(f"Got DynamoDB ClientError: {str(e)}")
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise NotFoundError(
                f"Prompt '{name}' with latest version '{latest_version}' not found"
            )
        else:
            raise

    except Exception as e:
        logger.info(
            f"Unable to update the status of the latest version of prompt '{name}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to update the status of the latest version of prompt '{name}': {str(e)}"
        )

    else:
        return {}


@app.route(
    "/prompt/{name}/version/{version}/status",
    cors=True,
    methods=["PUT"],
    authorizer=authorizer,
)
def update_prompt_version_status(name, version):
    """
    Enable or Disable a prompt by name and version.

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

        validate_path_parameters({"Name": name, "Version": version})

        status = json.loads(app.current_request.raw_body.decode())

        validate(event=status, schema=API_SCHEMA["update_status"])

        logger.info("Got a valid status schema")

        logger.info(f"Updating the status of the prompt '{name}' with version '{version}'")

        prompt_catalog_table.update_item(
            Key={"Name": name, "Version": version},
            UpdateExpression="SET #Enabled = :Status",
            ConditionExpression="attribute_exists(#Name) AND attribute_exists(#Version)",
            ExpressionAttributeNames={
                "#Enabled": "Enabled",
                "#Name": "Name",
                "#Version": "Version",
            },
            ExpressionAttributeValues={":Status": status["Enabled"]},
        )

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")  

    except ClientError as e:
        logger.info(f"Got DynamoDB ClientError: {str(e)}")
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise NotFoundError(f"Prompt '{name}' with version '{version}' not found")
        else:
            raise

    except Exception as e:
        logger.info(
            f"Unable to update the status of the prompt '{name}' with version '{version}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to update the status of the prompt '{name}' with version '{version}': {str(e)}"
        )

    else:
        return {}


@app.route("/prompt/{name}", cors=True, methods=["DELETE"], authorizer=authorizer)
def delete_prompt(name):
    """
    Delete all the versions of a prompt by name.

    Returns:

        None

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)

        validate_path_parameters({"Name": name})

        logger.info(f"Deleting the prompt '{name}' and all its versions")

        response = prompt_catalog_table.query(
            IndexName=PROMPT_CATALOG_NAME_INDEX,
            KeyConditionExpression=Key("Name").eq(name),
        )

        if "Items" not in response or len(response["Items"]) < 1:
            raise NotFoundError(f"Prompt '{name}' not found")

        versions = response["Items"]

        while "LastEvaluatedKey" in response:
            response = prompt_catalog_table.query(
                IndexName=PROMPT_CATALOG_NAME_INDEX,
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("Name").eq(name),
            )

            versions.extend(response["Items"])

        with prompt_catalog_table.batch_writer() as batch:
            for item in versions:
                batch.delete_item(
                    Key={"Name": item["Name"], "Version": item["Version"]}
                )
    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")  
    
    except NotFoundError as e:
        logger.info(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        logger.info(f"Unable to delete the prompt '{name}' and its versions: {str(e)}")
        raise ChaliceViewError(
            f"Unable to delete the prompt '{name}' and its versions: {str(e)}"
        )

    else:
        logger.info(f"Deletion of prompt '{name}' and its versions successful")
        return {}


@app.route(
    "/prompt/{name}/version/{version}",
    cors=True,
    methods=["DELETE"],
    authorizer=authorizer,
)
def delete_prompt_version(name, version):
    """
    Delete a specific version of a prompt by name and version.

    Deletion can be performed on all the prompt versions except "v0" and the latest prompt revision.
    If the latest prompt version needs to be deleted, publish a new version of the prompt and then
    delete the prior prompt version.

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

        validate_path_parameters({"Name": name, "Version": version})

        response = prompt_catalog_table.get_item(
            Key={"Name": name, "Version": "v0"}, ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Prompt '{name}' not found")

        latest_version = "v" + str(response["Item"]["Latest"])

        logger.info(f"Deleting version '{version}' of the prompt '{name}'")

        response = prompt_catalog_table.delete_item(
            Key={"Name": name, "Version": version},
            ConditionExpression="NOT (#Version IN (:Value1, :Value2))",
            ExpressionAttributeNames={"#Version": "Version"},
            ExpressionAttributeValues={":Value1": "v0", ":Value2": latest_version},
            ReturnValues="ALL_OLD",
        )

        if "Attributes" not in response:
            raise NotFoundError(f"Prompt '{name}' with version '{version}' not found")
        
    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")  
    
    except NotFoundError as e:
        logger.info(f"Got chalice NotFoundError: {str(e)}")
        raise

    except ClientError as e:
        logger.info(f"Got DynamoDB ClientError: {str(e)}")
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            if version == "v0":
                raise BadRequestError(
                    "Deletion of version 'v0' of the prompt is prohibited"
                )
            raise BadRequestError(
                f"Deletion of version '{version}' of the prompt is blocked as it is the latest prompt revision. Publish a new version to unblock the deletion of version '{version}'"
            )

        else:
            raise

    except Exception as e:
        logger.info(f"Unable to delete version '{version}' of the prompt '{name}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to delete version '{version}' of the prompt '{name}': {str(e)}"
        )

    else:
        logger.info(f"Deletion of version '{version}' of the prompt '{name}' successful")
        return {}
    
def validate_path_parameters(params: dict):
    validate(event=params, schema=API_SCHEMA["prompt_path_validation"])