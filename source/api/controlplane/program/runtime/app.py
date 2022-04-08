#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import urllib.parse
import boto3
from chalice import Chalice
from chalice import IAMAuthorizer
from chalice import ChaliceViewError

app = Chalice(app_name='aws-mre-controlplane-program-api')

API_VERSION = '1.0.0'
authorizer = IAMAuthorizer()

ddb_resource = boto3.resource("dynamodb")

PROGRAM_TABLE_NAME = os.environ['PROGRAM_TABLE_NAME']

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
