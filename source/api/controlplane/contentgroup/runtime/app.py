#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import urllib.parse
import boto3
from chalice import Chalice
from chalice import IAMAuthorizer
from chalice import ChaliceViewError

app = Chalice(app_name='aws-mre-controlplane-contentgroup-api')

API_VERSION = '1.0.0'
authorizer = IAMAuthorizer()

ddb_resource = boto3.resource("dynamodb")

CONTENT_GROUP_TABLE_NAME = os.environ['CONTENT_GROUP_TABLE_NAME']

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
