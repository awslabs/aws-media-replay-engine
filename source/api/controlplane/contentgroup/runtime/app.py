#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import urllib.parse
import boto3
from aws_lambda_powertools.utilities.validation import (SchemaValidationError,validate)
from chalice import BadRequestError, Chalice, ChaliceViewError, IAMAuthorizer
from chalicelib import load_api_schema
from aws_lambda_powertools import Logger

app = Chalice(app_name='aws-mre-controlplane-contentgroup-api')
logger = Logger(service="aws-mre-controlplane-contentgroup-api")

API_VERSION = '1.0.0'
authorizer = IAMAuthorizer()
ddb_resource = boto3.resource("dynamodb")
CONTENT_GROUP_TABLE_NAME = os.environ['CONTENT_GROUP_TABLE_NAME']
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

        validate_path_parameters({"ContentGroup": content_group})

        logger.info(f"Creating a new content group '{content_group}'")

        content_group_table = ddb_resource.Table(CONTENT_GROUP_TABLE_NAME)

        item = {
            "Name": content_group
        }

        content_group_table.put_item(
            Item=item
        )
    
    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except Exception as e:
        logger.info(f"Unable to create a new content group '{content_group}': {str(e)}")
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
        logger.info(f"Listing all the content groups")

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
        logger.info(f"Unable to list all the content groups stored in the system: {str(e)}")
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

        validate_path_parameters({"ContentGroup": content_group})

        logger.info(f"Deleting the content group '{content_group}'")

        content_group_table = ddb_resource.Table(CONTENT_GROUP_TABLE_NAME)

        content_group_table.delete_item(
            Key={
                "Name": content_group
            }
        )
        
    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    
    except Exception as e:
        logger.info(f"Unable to delete the content group '{content_group}': {str(e)}")
        raise ChaliceViewError(f"Unable to delete the content group '{content_group}': {str(e)}")

    else:
        return {}

def validate_path_parameters(params: dict):
    validate(event=params, schema=API_SCHEMA["content_group_path_validation"])
