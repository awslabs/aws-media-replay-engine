#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import urllib.parse

import boto3
from aws_lambda_powertools.utilities.validation import (SchemaValidationError,
                                                        validate)
from chalice import BadRequestError, Chalice, ChaliceViewError, IAMAuthorizer
from chalicelib import load_api_schema
from aws_lambda_powertools import Logger

app = Chalice(app_name="aws-mre-controlplane-program-api")
logger = Logger(service="aws-mre-controlplane-program-api")

API_VERSION = "1.0.0"
authorizer = IAMAuthorizer()

API_SCHEMA = load_api_schema()

ddb_resource = boto3.resource("dynamodb")

PROGRAM_TABLE_NAME = os.environ["PROGRAM_TABLE_NAME"]

# Create middleware to inject request context
@app.middleware('all')
def inject_request_context(event, get_response):
    # event is a Chalice Request object
    request_id = event.context.get('requestId', 'N/A')
    
    # Add request ID to persistent logger context
    logger.append_keys(request_id=request_id)
    
    response = get_response(event)
    return response

@app.route("/program/{program}", cors=True, methods=["PUT"], authorizer=authorizer)
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

        validate_path_parameters({"Program": program})

        logger.info(f"Creating a new program '{program}'")

        program_table = ddb_resource.Table(PROGRAM_TABLE_NAME)

        item = {"Name": program}

        program_table.put_item(Item=item)

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except Exception as e:
        logger.info(f"Unable to create a new program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to create a new program '{program}': {str(e)}")

    else:
        return {}


@app.route("/program/all", cors=True, methods=["GET"], authorizer=authorizer)
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
        logger.info(f"Listing all the programs")

        program_table = ddb_resource.Table(PROGRAM_TABLE_NAME)

        response = program_table.scan(ConsistentRead=True)

        programs = response["Items"]

        while "LastEvaluatedKey" in response:
            response = program_table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"], ConsistentRead=True
            )

            programs.extend(response["Items"])

    except Exception as e:
        logger.info(f"Unable to list all the programs stored in the system: {str(e)}")
        raise ChaliceViewError(
            f"Unable to list all the programs stored in the system: {str(e)}"
        )

    else:
        return programs


@app.route("/program/{program}", cors=True, methods=["DELETE"], authorizer=authorizer)
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

        validate_path_parameters({"Program": program})

        logger.info(f"Deleting the program '{program}'")

        program_table = ddb_resource.Table(PROGRAM_TABLE_NAME)

        program_table.delete_item(Key={"Name": program})

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except Exception as e:
        logger.info(f"Unable to delete the program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to delete the program '{program}': {str(e)}")

    else:
        return {}


def validate_path_parameters(params: dict):
    validate(event=params, schema=API_SCHEMA["program_path_validation"])
