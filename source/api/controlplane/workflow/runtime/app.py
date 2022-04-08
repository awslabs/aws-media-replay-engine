#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import json
import urllib.parse
import boto3
from chalice import Chalice
from chalice import IAMAuthorizer
from chalice import ChaliceViewError
from boto3.dynamodb.types import TypeSerializer
from boto3.dynamodb.conditions import Key, Attr
from chalicelib import replace_decimals

app = Chalice(app_name='aws-mre-controlplane-workflow-api')

API_VERSION = '1.0.0'
authorizer = IAMAuthorizer()
serializer = TypeSerializer()

ddb_resource = boto3.resource("dynamodb")


WORKFLOW_EXECUTION_TABLE_NAME = os.environ['WORKFLOW_EXECUTION_TABLE_NAME']

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