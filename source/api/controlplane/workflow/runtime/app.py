#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json
import os
import urllib.parse

import boto3
from aws_lambda_powertools.utilities.validation import (SchemaValidationError,
                                                        validate)
from boto3.dynamodb.conditions import Attr, Key
from boto3.dynamodb.types import TypeSerializer
from chalice import BadRequestError, Chalice, ChaliceViewError, IAMAuthorizer
from chalicelib import load_api_schema, replace_decimals
from aws_lambda_powertools import Logger

app = Chalice(app_name="aws-mre-controlplane-workflow-api")
logger = Logger(service="aws-mre-controlplane-workflow-api")

API_VERSION = "1.0.0"
authorizer = IAMAuthorizer()
serializer = TypeSerializer()

ddb_resource = boto3.resource("dynamodb")

API_SCHEMA = load_api_schema()


WORKFLOW_EXECUTION_TABLE_NAME = os.environ["WORKFLOW_EXECUTION_TABLE_NAME"]

# Create middleware to inject request context
@app.middleware('all')
def inject_request_context(event, get_response):
    # event is a Chalice Request object
    request_id = event.context.get('requestId', 'N/A')
    
    # Add request ID to persistent logger context
    logger.append_keys(request_id=request_id)
    
    response = get_response(event)
    return response

@app.route("/workflow/execution", cors=True, methods=["POST"], authorizer=authorizer)
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

        validate(event=execution, schema=API_SCHEMA["workflow_execution"])

        program = execution["Program"]
        event = execution["Event"]
        chunk_num = execution["ChunkNumber"]

        logger.info(
            f"Recording the AWS Step Function workflow execution details for chunk '{chunk_num}' in program '{program}' and event '{event}'"
        )

        workflow_exec_table_name = ddb_resource.Table(WORKFLOW_EXECUTION_TABLE_NAME)

        item = {
            "PK": f"{program}#{event}",
            "ChunkNumber": chunk_num,
            "ExecutionId": execution["ExecutionId"],
            "Filename": execution["Filename"],
        }

        workflow_exec_table_name.put_item(Item=item)

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except Exception as e:
        logger.info(
            f"Unable to record the AWS Step Function workflow execution details for chunk '{chunk_num}' in program '{program}' and event '{event}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to record the AWS Step Function workflow execution details for chunk '{chunk_num}' in program '{program}' and event '{event}': {str(e)}"
        )

    else:
        logger.info(
            f"Successfully recorded the AWS Step Function workflow execution details: {json.dumps(execution)}"
        )

        return {}


@app.route(
    "/workflow/execution/program/{program}/event/{event}/chunk/{chunk_num}/plugin/{plugin_name}/status/{status}",
    cors=True,
    methods=["PUT"],
    authorizer=authorizer,
)
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
        chunk_num = int(urllib.parse.unquote(chunk_num))
        plugin_name = urllib.parse.unquote(plugin_name)
        status = urllib.parse.unquote(status)

        validate_path_parameters(
            {
                "Program": program,
                "Event": event,
                "ChunkNumber": chunk_num,
                "PluginName": plugin_name,
                "Status": status,
            }
        )

        logger.info(
            f"Updating the execution status of '{plugin_name}' plugin for chunk '{chunk_num}' in program '{program}' and event '{event}'"
        )

        workflow_exec_table_name = ddb_resource.Table(WORKFLOW_EXECUTION_TABLE_NAME)

        workflow_exec_table_name.update_item(
            Key={
                "PK": f"{program}#{event}",
                "ChunkNumber": chunk_num,
            },
            UpdateExpression=f"SET #Plugin = :Status",
            ExpressionAttributeNames={"#Plugin": plugin_name},
            ExpressionAttributeValues={":Status": status},
        )

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except Exception as e:
        logger.info(
            f"Unable to update the status of '{plugin_name}' plugin for chunk '{chunk_num}' in program '{program}' and event '{event}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to update the status of '{plugin_name}' plugin for chunk '{chunk_num}' in program '{program}' and event '{event}': {str(e)}"
        )

    else:
        logger.info(
            f"Successfully updated the status of '{plugin_name}' plugin for chunk '{chunk_num}' in program '{program}' and event '{event}'"
        )

        return {}


@app.route(
    "/workflow/execution/program/{program}/event/{event}/chunk/{chunk_num}/plugin/{plugin_name}/status",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
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
        chunk_num = int(urllib.parse.unquote(chunk_num))
        plugin_name = urllib.parse.unquote(plugin_name)

        validate_path_parameters(
            {
                "Program": program,
                "Event": event,
                "ChunkNumber": chunk_num,
                "PluginName": plugin_name,
            }
        )

        logger.info(
            f"Getting the execution status of '{plugin_name}' plugin for chunk '{chunk_num}' in program '{program}' and event '{event}'"
        )

        workflow_exec_table_name = ddb_resource.Table(WORKFLOW_EXECUTION_TABLE_NAME)

        response = workflow_exec_table_name.get_item(
            Key={"PK": f"{program}#{event}", "ChunkNumber": chunk_num},
            ProjectionExpression="#Plugin",
            ExpressionAttributeNames={"#Plugin": plugin_name},
        )

        if "Item" not in response or len(response["Item"]) < 1:
            status = None
        else:
            status = response["Item"][plugin_name]

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except Exception as e:
        logger.info(
            f"Unable to get the execution status of '{plugin_name}' plugin for chunk '{chunk_num}' in program '{program}' and event '{event}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to get the execution status of '{plugin_name}' plugin for chunk '{chunk_num}' in program '{program}' and event '{event}': {str(e)}"
        )

    else:
        return status


@app.route(
    "/workflow/execution/program/{program}/event/{event}/chunk/{chunk_num}/plugin/{plugin_name}/status/incomplete",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
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
        chunk_num = int(urllib.parse.unquote(chunk_num))
        plugin_name = urllib.parse.unquote(plugin_name)

        validate_path_parameters(
            {
                "Program": program,
                "Event": event,
                "ChunkNumber": chunk_num,
                "PluginName": plugin_name,
            }
        )

        logger.info(
            f"Getting all the incomplete '{plugin_name}' plugin executions prior to the chunk '{chunk_num}' in program '{program}' and event '{event}'"
        )

        workflow_exec_table_name = ddb_resource.Table(WORKFLOW_EXECUTION_TABLE_NAME)

        response = workflow_exec_table_name.query(
            KeyConditionExpression=Key("PK").eq(f"{program}#{event}")
            & Key("ChunkNumber").lt(chunk_num),
            FilterExpression=Attr(plugin_name).not_exists()
            | Attr(plugin_name).is_in(["Waiting", "In Progress"]),
            ProjectionExpression="PK, ChunkNumber",
            ConsistentRead=True,
        )

        executions = response["Items"]

        while "LastEvaluatedKey" in response:
            response = workflow_exec_table_name.query(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("PK").eq(f"{program}#{event}")
                & Key("ChunkNumber").lt(chunk_num),
                FilterExpression=Attr(plugin_name).not_exists()
                | Attr(plugin_name).is_in(["Waiting", "In Progress"]),
                ProjectionExpression="PK, ChunkNumber",
                ConsistentRead=True,
            )

            executions.extend(response["Items"])

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except Exception as e:
        logger.info(
            f"Unable to get all the incomplete '{plugin_name}' plugin executions prior to the chunk '{chunk_num}' in program '{program}' and event '{event}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to get all the incomplete '{plugin_name}' plugin executions prior to the chunk '{chunk_num}' in program '{program}' and event '{event}': {str(e)}"
        )

    else:
        return replace_decimals(executions)


def validate_path_parameters(params: dict):
    validate(event=params, schema=API_SCHEMA["workflow_path_validation"])
