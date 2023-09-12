#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import json
from decimal import Decimal
import urllib.parse
import boto3
from datetime import datetime
from botocore.client import ClientError
from chalice import Chalice
from chalice import IAMAuthorizer
from chalice import ChaliceViewError, BadRequestError, ConflictError, NotFoundError
from chalicelib import DecimalEncoder
from jsonschema import validate, ValidationError
from chalicelib import load_api_schema

app = Chalice(app_name='aws-mre-controlplane-custompriorities-api')

API_VERSION = '1.0.0'
authorizer = IAMAuthorizer()

API_SCHEMA = load_api_schema()

ddb_resource = boto3.resource("dynamodb")

CUSTOM_PRIORITIES_TABLE_NAME = os.environ['CUSTOM_PRIORITIES_TABLE_NAME']

@app.route('/custompriorities', cors=True, methods=['POST'], authorizer=authorizer)
def create_custom_priorities_engine():
    """
    Create a new Custom Priorities Engine configuration. A Custom Priorities Engine configuration is a collection of attributes
    that define's the required elements to integrate with an external API that provides segment level significance or weights 
    for replay generation
    
    Body:

    .. code-block:: python

        {
            "Name": string,
            "Description": string,
            "EndpointSsmParam": string,
            "SecretsManagerApiKeyArn": string
        }
    
    Parameters:

        - Name: Name of the Custom Priorities Engine configuration
        - Description: Description of the Custom Priorities Engine configuration
        - EndpointSsmParam: Name of the SSM Parameter that holds the API endpoint
        - SecretsManagerApiKeyArn: ARN of the Secret in Secrets manager that holds the API key to Access the Custom Priorities Engine API

    Returns:

        A dict containing the Name of the Custom Priorities Engine

        .. code-block:: python

            {
                "Name": string,
            }

    Raises:
        400 - BadRequestError
        500 - ChaliceViewError
    """
    try:
        custom_priorities_engine = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=custom_priorities_engine, schema=API_SCHEMA["create_custom_priorities_engine"])

        print("Got a valid profile schema")

        name = custom_priorities_engine["Name"]
        custom_priorities_engine["Created"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        custom_priorities_engine["LastModified"] = custom_priorities_engine["Created"]
        custom_priorities_engine["Enabled"] = True

        custom_priorities_table = ddb_resource.Table(CUSTOM_PRIORITIES_TABLE_NAME)

        custom_priorities_table.put_item(
            Item=custom_priorities_engine,
            ConditionExpression="attribute_not_exists(#Name)",
            ExpressionAttributeNames={
                "#Name": "Name"
            }
        )
    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise ValidationError(e.message)
    
    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ConflictError(f"Custom Priorities Engine '{name}' already exists")
        else:
            raise

    except Exception as e:
        print(f"Unable to create a new custom priorities engine '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to create a new custom priorities engine '{name}': {str(e)}")

    else:
        return {}

@app.route('/custompriorities/all', cors=True, methods=['GET'], authorizer=authorizer)
def list_custompriorities():
    """
    List all the custom priorities engine configurations.

    Returns:

        .. code-block:: python

        [
            {
                "Name": string,
                "Description": string,
                "EndpointSsmParam": string,
                "SecretsManagerApiKeyArn": string
                "Created": timestamp,
                "LastModified": timestamp
            }
        ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        print("Listing all the custom priorities engine")

        custom_priorities_table = ddb_resource.Table(CUSTOM_PRIORITIES_TABLE_NAME)

        response = custom_priorities_table.scan(
            ConsistentRead=True
        )

        custom_priorities_engine = response["Items"]

        while "LastEvaluatedKey" in response:
            response = custom_priorities_table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                ConsistentRead=True
            )

            custom_priorities_engine.extend(response["Items"])

    except Exception as e:
        print(f"Unable to list all the custom priorities engine: {str(e)}")
        raise ChaliceViewError(f"Unable to list all the custom priorities engine: {str(e)}")

    else:
        return custom_priorities_engine
    
@app.route('/custompriorities/{name}', cors=True, methods=['GET'], authorizer=authorizer)
def get_custompriorities(name):
    """
    Get a custom priorities engine configuration by name.

    Returns:

        .. code-block:: python

        {
            "Name": string,
            "Description": string,
            "EndpointSsmParam": string,
            "SecretsManagerApiKeyArn": string,
            "Enabled": boolean,
            "Created": timestamp,
            "LastModified": timestamp
        }

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)

        print(f"Getting the custom priorities engine '{name}'")

        custom_priorities_table = ddb_resource.Table(CUSTOM_PRIORITIES_TABLE_NAME)

        response = custom_priorities_table.get_item(
            Key={
                "Name": name
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Custom Priorities Engine '{name}' not found")

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to get the custom priorities engine '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to get the custom priorities engine '{name}': {str(e)}")

    else:
        return response["Item"]
    
@app.route('/custompriorities/{name}', cors=True, methods=['PUT'], authorizer=authorizer)
def update_custom_priorities_engine(name):
    """
    Update a custom priorities engine configuration by name.

    Body:

    .. code-block:: python

        {
            "Description": string,
            "EndpointSsmParam": string,
            "SecretsManagerApiKeyArn": string
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
        custom_priorities_engine = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=custom_priorities_engine, schema=API_SCHEMA["update_custom_priorities_engine"])

        print("Got a valid custom priorities engine schema")

        print(f"Updating the custom priorities engine '{name}'")

        custom_priorities_table = ddb_resource.Table(CUSTOM_PRIORITIES_TABLE_NAME)

        response = custom_priorities_table.get_item(
            Key={
                "Name": name
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Custom Priorities Engine '{name}' not found")
        
        custom_priorities_engine["Description"] = custom_priorities_engine["Description"] if "Description" in custom_priorities_engine else (
            response["Item"]["Description"] if "Description" in response["Item"] else "")
        
        custom_priorities_engine["EndpointSsmParam"] = custom_priorities_engine["EndpointSsmParam"] if "EndpointSsmParam" in custom_priorities_engine else (
            response["Item"]["EndpointSsmParam"] if "EndpointSsmParam" in response["Item"] else "")
        
        custom_priorities_engine["SecretsManagerApiKeyArn"] = custom_priorities_engine["SecretsManagerApiKeyArn"] if "SecretsManagerApiKeyArn" in custom_priorities_engine else (
            response["Item"]["SecretsManagerApiKeyArn"] if "SecretsManagerApiKeyArn" in response["Item"] else "")
        
        custom_priorities_table.update_item(
            Key={
                "Name": name
            },
            UpdateExpression="SET #Description = :Description, #EndpointSsmParam = :EndpointSsmParam, #SecretsManagerApiKeyArn = :SecretsManagerApiKeyArn, #LastModified = :LastModified",
            ExpressionAttributeNames={
                "#Description": "Description",
                "#EndpointSsmParam": "EndpointSsmParam",
                "#SecretsManagerApiKeyArn": "SecretsManagerApiKeyArn",
                "#LastModified": "LastModified"
            },
            ExpressionAttributeValues={
                ":Description": custom_priorities_engine["Description"],
                ":EndpointSsmParam": custom_priorities_engine["EndpointSsmParam"],
                ":SecretsManagerApiKeyArn": custom_priorities_engine["SecretsManagerApiKeyArn"],
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
        print(f"Unable to update the custom priorities engine '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to update the custom priorities engine '{name}': {str(e)}")

    else:
        print(f"Successfully updated the profile: {json.dumps(custom_priorities_engine, cls=DecimalEncoder)}")

        return {}
    
@app.route('/custompriorities/{name}/status', cors=True, methods=['PUT'], authorizer=authorizer)
def update_custom_priorities_engine_status(name):
    """
    Enable or Disable custom priorities engine by name.

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

        print(f"Updating the status of the custom priorities engine '{name}'")

        custom_priorities_table = ddb_resource.Table(CUSTOM_PRIORITIES_TABLE_NAME)

        custom_priorities_table.update_item(
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
            raise NotFoundError(f"Custom Priorities Engine '{name}' not found")
        else:
            raise

    except Exception as e:
        print(f"Unable to update the status of custom priorities engine '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to update the status of custom priorities engine '{name}': {str(e)}")

    else:
        return {}
    
@app.route('/custompriorities/{name}', cors=True, methods=['DELETE'], authorizer=authorizer)
def delete_custom_priorities_engine(name):
    """
    Delete a custom priorities engine configuration by name.

    Returns:

        None

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)

        print(f"Deleting the custom priorities engine '{name}'")

        custom_priorities_table = ddb_resource.Table(CUSTOM_PRIORITIES_TABLE_NAME)

        response = custom_priorities_table.delete_item(
            Key={
                "Name": name
            },
            ReturnValues="ALL_OLD"
        )

        if "Attributes" not in response:
            raise NotFoundError(f"Custom Priorities Engine '{name}' not found")

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to delete custom priorities engine '{name}': {str(e)}")
        raise ChaliceViewError(f"Unable to delete custom priorities engine '{name}': {str(e)}")

    else:
        print(f"Deletion of custom priorities engine '{name}' successful")
        return {}