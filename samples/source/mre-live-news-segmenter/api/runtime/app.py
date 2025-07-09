# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os
import urllib.parse
from decimal import Decimal

import boto3
from aws_lambda_powertools.utilities.validation import (SchemaValidationError,
                                                        validate)
from boto3.dynamodb.conditions import Key
from botocore.client import ClientError
from chalice import BadRequestError, Chalice, ChaliceViewError, IAMAuthorizer
from chalicelib import common, load_api_schema
from chalicelib.common import create_presigned_url
from chalicelib.user_favorites import user_favorites_api

app = Chalice(app_name="mre-live-news-segmenter-api")

app.register_blueprint(user_favorites_api)

authorizer = IAMAuthorizer()

ddb_resource = boto3.resource("dynamodb")
ddb_client = boto3.client("dynamodb")

EVENT_TABLE_NAME = os.environ["EVENT_TABLE_NAME"]
PROFILE_TABLE_NAME = os.environ["PROFILE_TABLE_NAME"]
PLUGIN_RESULT_TABLE_NAME = os.environ["PLUGIN_RESULT_TABLE_NAME"]
event_table = ddb_resource.Table(EVENT_TABLE_NAME)
profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)
plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

API_SCHEMA = load_api_schema()


@app.route(
    "/samples/news/get-child-themes/{program}/{event}/{plugin}/{start}/{end}",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_child_themes(program, event, plugin, start, end):
    """
    Retrieve child themes for a specific program, event, and plugin within a given time range.

    This function handles GET requests to the specified route and queries a DynamoDB table
    to fetch items that match the provided program, event, plugin, start, and end parameters.
    The results are then processed to include presigned URLs for thumbnails.

    Parameters:
    - program (str): The program identifier.
    - event (str): The event identifier.
    - plugin (str): The plugin identifier.
    - start (str): The start time for the query.
    - end (str): The end time for the query.

    Request format: /samples/news/child-themes/{program}/{event}/{plugin}/{start}/{end}

    Returns:
    - list: A list of items that match the query criteria, each item includes a presigned URL for the thumbnail.

    Raises:
    - ChaliceViewError: If there is an error querying the DynamoDB table.
    """

    program = urllib.parse.unquote(program)
    event = urllib.parse.unquote(event)
    plugin = urllib.parse.unquote(plugin)

    try:
        validate_path_parameters(
            {
                "Program": program,
                "Event": event,
                "Plugin": plugin,
                "Start": start,
                "End": end,
            }
        )
        program_event_pluginName = f"{program}#{event}#{plugin}"
        start = Decimal(start)
        end = Decimal(end)

        response = plugin_result_table.query(
                KeyConditionExpression=Key('PK').eq(program_event_pluginName) & Key('Start').between(start,end)
        )

        body = {}
        items = []
        for item in response["Items"]:
            item = common.udf(item)
            item["OriginalThumbnailLocation"] = common.create_presigned_url(
                item["OriginalThumbnailLocation"]
            )
            items.append(item)

        body["Items"] = items
    except SchemaValidationError as e:
        print(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except ClientError as e:
        err_msg = f"Unable to get values from '{PLUGIN_RESULT_TABLE_NAME}' table usgin : {str(e)}"
        print(err_msg)
        raise ChaliceViewError(err_msg)

    else:
        return body["Items"]


@app.route(
    "/samples/news/refresh-event-themes/{program}/{event}",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def refresh_event_themes(program, event):
    """
    Refresh event themes for a specific program and event.

    This function handles GET requests to the specified route and queries a DynamoDB table
    to fetch items that match the provided program and event parameters. The results are then
    processed to include presigned URLs for thumbnails and to remove child themes, leaving only root themes.

    Parameters:
    - program (str): The program identifier.
    - event (str): The event identifier.

    Query Parameters:
    - start_from (int, optional): The starting point for pagination.
    - limit (int, optional): The maximum number of items to return. Default is 10.
    - order (str, optional): The order of the results. Can be 'asc' for ascending or 'desc' for descending. Default is ascending.

    Request format: /samples/news/refresh-event-themes/{program}/{event}

    Returns:
    - dict: A dictionary containing the list of items that match the query criteria, each item includes a presigned URL for the thumbnail.
            If pagination is used, the dictionary also includes the 'StartFrom' key for the next set of results.

    Raises:
    - ChaliceViewError: If there is an error querying the DynamoDB table.
    """

    program = urllib.parse.unquote(program)
    event = urllib.parse.unquote(event)

    limit = 10
    start_from = None
    ScanIndexForward = True
    if app.current_request.query_params is not None:
        if app.current_request.query_params.get("start_from") is not None:
            start_from = Decimal(
                str(app.current_request.query_params.get("start_from"))
            )

        if (
            app.current_request.query_params is not None
            and app.current_request.query_params.get("limit") is not None
        ):
            limit = int(app.current_request.query_params.get("limit"))

        order = app.current_request.query_params.get("order")
        if order is not None and order.lower() == "desc":
            ScanIndexForward = False

    # Get the profile name from the event table
    profile_name = event_table.get_item(Key={"Program": program, "Name": event})[
        "Item"
    ]["Profile"]
    # Get the segmenter plugin name from the profile table
    plugin_name = profile_table.get_item(Key={"Name": profile_name})["Item"][
        "Classifier"
    ]["Name"]
    program_event_pluginName = f"{program}#{event}#{plugin_name}"

    try:
        validate_path_parameters(
            {
                "Program": program,
                "Event": event,
                "StartFrom": start_from,
                "Limit": limit,
            }
        )

        # Get the profile name from the event table
        profile_name = event_table.get_item(Key={"Program": program, "Name": event})[
            "Item"
        ]["Profile"]
        # Get the segmenter plugin name from the profile table
        plugin_name = profile_table.get_item(Key={"Name": profile_name})["Item"][
            "Classifier"
        ]["Name"]
        program_event_pluginName = f"{program}#{event}#{plugin_name}"

        # Pagination
        if start_from is not None:
            response = plugin_result_table.query(
                IndexName="ProgramEventPluginName_Start-index",
                KeyConditionExpression=Key("ProgramEventPluginName").eq(
                    program_event_pluginName
                ),
                ExclusiveStartKey={
                    "ProgramEventPluginName": program_event_pluginName,
                    "PK": program_event_pluginName,
                    "Start": start_from,
                },
                ScanIndexForward=ScanIndexForward,
                Limit=limit,
            )
        else:
            response = plugin_result_table.query(
                IndexName="ProgramEventPluginName_Start-index",
                KeyConditionExpression=Key("ProgramEventPluginName").eq(
                    program_event_pluginName
                ),
                ScanIndexForward=ScanIndexForward,
                Limit=limit,
            )

        items = response["Items"]

        if ScanIndexForward:
            # Remove the children themes, letting only the roots
            size = len(items)
            x = 0
            y = 1

            while y < size:
                if (
                    items[y]["Start"] >= items[x]["Start"]
                    and items[y]["End"] <= items[x]["End"]
                ):
                    del items[y]
                    size = len(items)
                else:
                    x = y
                    y = y + 1
        else:
            # Remove the children themes, letting only the roots
            size = len(items)
            x = size - 1
            y = x - 1

            while y >= 0:
                if (
                    items[y]["Start"] >= items[x]["Start"]
                    and items[y]["End"] <= items[x]["End"]
                ):
                    del items[y]
                    y = y - 1
                    x = x - 1
                else:
                    x = y
                    y = y - 1

        # Generate the presigned url
        for item in items:
            if "OriginalThumbnailLocation" in item:
                item["OriginalThumbnailLocation"] = create_presigned_url(
                    item["OriginalThumbnailLocation"]
                )

        body = {}
        if "LastEvaluatedKey" in response:
            body["StartFrom"] = response["LastEvaluatedKey"]["Start"]

        body["Items"] = items
        return body

    except SchemaValidationError as e:
        print(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    
    except ClientError as err:
        err_msg = (
            f"Unable to get values from '{PLUGIN_RESULT_TABLE_NAME}' table: {str(err)}"
        )
        print(err_msg)
        raise ChaliceViewError(err_msg)

def validate_path_parameters(params: dict):
    validate(event=params, schema=API_SCHEMA["news_segmenter_path_validation"])