# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import json
import urllib.parse
import boto3
from decimal import Decimal
from datetime import datetime
from chalice import Blueprint
from chalice import IAMAuthorizer
from chalice import ChaliceViewError
from boto3.dynamodb.conditions import Key, Attr
from chalicelib import load_api_schema
from chalicelib.common import populate_segment_data_matching, get_event_segment_metadata


PLUGIN_RESULT_TABLE_NAME = os.environ['PLUGIN_RESULT_TABLE_NAME']
REPLAY_RESULT_TABLE_NAME = os.environ['REPLAY_RESULT_TABLE_NAME']

authorizer = IAMAuthorizer()
ddb_resource = boto3.resource("dynamodb")
API_SCHEMA = load_api_schema()

replay_api = Blueprint(__name__)

@replay_api.route('/event/{name}/program/{program}/profileClassifier/{classifier}/track/{tracknumber}/replay/{replayId}/segments/v2',
    cors=True, methods=['GET'], authorizer=authorizer)
def get_matching_replay_segments_v2(name, program, classifier, tracknumber, replayId):
    """
    Gets the Replay Segments by matching the StartTime of each Replay Segment with the segments created so far for the event

    Query String Params:
    :param limit: Limits how many segments the API returns. Returns a LastEvaluatedKey if more segments exist.
    :param LastEvaluatedKey: Set the LastEvaluatedKey returned by the previous call to the API to fetch the next list of segments

    Returns:

        A list of Segments along with LastEvaluatedKey. Any empty LastEvaluatedKey indicates that no additional segments exist.

        .. code-block:: python

            {
                "LastEvaluatedKey": "",
                "Items": 
            }

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    name = urllib.parse.unquote(name)
    program = urllib.parse.unquote(program)
    classifier = urllib.parse.unquote(classifier)
    tracknumber = urllib.parse.unquote(tracknumber)
    limit = 100
    last_evaluated_key = 0
    replay_clips = []

    try:
        query_params = replay_api.current_app.current_request.query_params
        if query_params:
            if "limit" in query_params:
                limit = int(query_params.get("limit"))
            if "LastEvaluatedKey" in query_params and query_params["LastEvaluatedKey"]:
                last_evaluated_key = int(query_params.get("LastEvaluatedKey"))

        replay_results_table = ddb_resource.Table(REPLAY_RESULT_TABLE_NAME)

        replay_results_query = replay_results_table.query(
            KeyConditionExpression=Key("ProgramEventReplayId").eq(f"{program}#{name}#{replayId}")
        )

        if len(replay_results_query['Items']) > 0:
            try:
                replay_clips = match_replays_with_segments(replay_results_query['Items'][0]['ReplayResults'], program, name,
                                                        classifier, tracknumber, last_evaluated_key, limit)
            except KeyError:
                pass
        else:
            return {
                "LastEvaluatedKey": None,
                "Items": [],
            }
    except Exception as e:
        print(e)
        print(f"Unable to match replays for event '{name}' in Program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to match replays for event '{name}' in Program '{program}': {str(e)}")

    else:
        return {
            "LastEvaluatedKey": replay_clips["LastEvaluatedKey"],
            "Items": replay_clips["Items"],
        }


@replay_api.route('/event/{name}/program/{program}/profileClassifier/{classifier}/track/{tracknumber}/replay/{replayId}/segments',
    cors=True, methods=['GET'], authorizer=authorizer)
def get_matching_replay_segments(name, program, classifier, tracknumber, replayId):
    """
    Gets the Replay Segments by matching the StartTime of each Replay Segment with the segments created so far for the event.

    Returns:

        A list of replay Segments.

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """

    name = urllib.parse.unquote(name)
    program = urllib.parse.unquote(program)
    classifier = urllib.parse.unquote(classifier)

    segment_metadata = get_event_segment_metadata(name, program, classifier, tracknumber)

    replay_results_table = ddb_resource.Table(REPLAY_RESULT_TABLE_NAME)

    response = replay_results_table.query(
        KeyConditionExpression=Key("ProgramEventReplayId").eq(f"{program}#{name}#{replayId}")
    )

    replay_clips = []
    if 'Items' in response:
        replay_results_response = response['Items']

        while "LastEvaluatedKey" in response:
            response = replay_results_table.query(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("ProgramEventReplayId").eq(f"{program}#{name}#{replayId}")
            )
            replay_results_response.extend(response['Items'])

        for replay_result in replay_results_response:
            for result in replay_result['ReplayResults']:
                # print(f"Replay Start = {type(result['Start'])}")
                for segment in segment_metadata['Segments']:
                    # print(type(segment['StartTime']))
                    if Decimal(str(result['Start'])) == Decimal(str(segment['StartTime'])):
                        replay_clips.append(segment)
                        break

    return replay_clips


@replay_api.route('/event/{name}/program/{program}/replay/{replayId}/segments', cors=True, methods=['GET'],
           authorizer=authorizer)
def get_replay_segments(name, program, replayId):
    """
    Gets the Replay Segments for a ReplayId

    Returns:

        A list of replay Segments.

    """

    name = urllib.parse.unquote(name)
    program = urllib.parse.unquote(program)

    replay_results_table = ddb_resource.Table(REPLAY_RESULT_TABLE_NAME)
    response = replay_results_table.query(
        KeyConditionExpression=Key("ProgramEventReplayId").eq(f"{program}#{name}#{replayId}")
    )

    if 'Items' in response:
        replay_results_response = response['Items']
        while "LastEvaluatedKey" in response:
            response = replay_results_table.query(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("ProgramEventReplayId").eq(f"{program}#{name}#{replayId}")
            )
            replay_results_response.extend(response['Items'])

        if len(replay_results_response) > 0:
            return replay_results_response[0]['ReplayResults'] if 'ReplayResults' in replay_results_response[0] else []
        else:
            return []
    else:
        return []



@replay_api.route('/replay/result', cors=True, methods=['POST'], authorizer=authorizer)
def update_replay_results():
    """
    Store the result of a plugin in a DynamoDB table.

    Body:

    .. code-block:: python

        {
            "Program": string,
            "Event": string,
            "ReplayId": string,
            "Profile": string,
            "Classifier": string,
            "AdditionalInfo" : list,
            "ReplayResults: list
        }

    Returns:

        None
    """

    replay_result = json.loads(replay_api.current_app.current_request.raw_body.decode(), parse_float=Decimal)
    print(replay_result)

    program = replay_result["Program"]
    event = replay_result["Event"]
    replay_id = replay_result["ReplayId"]
    profile = replay_result["Profile"]
    classifier = replay_result["Classifier"]
    replay_results = replay_result["ReplayResults"]
    additional_info = replay_result["AdditionalInfo"]
    total_score = replay_result["TotalScore"]

    update_expression = []
    expression_attribute_names = {}
    expression_attribute_values = {}

    update_expression.append("#CreatedOn = :CreatedOn")
    expression_attribute_names["#CreatedOn"] = "CreatedOn"
    expression_attribute_values[":CreatedOn"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    update_expression.append("#ReplayId = :ReplayId")
    expression_attribute_names["#ReplayId"] = "ReplayId"
    expression_attribute_values[":ReplayId"] = replay_id

    update_expression.append("#Event = :Event")
    expression_attribute_names["#Event"] = "Event"
    expression_attribute_values[":Event"] = event

    update_expression.append("#Program = :Program")
    expression_attribute_names["#Program"] = "Program"
    expression_attribute_values[":Program"] = program

    update_expression.append("#Profile = :Profile")
    expression_attribute_names["#Profile"] = "Profile"
    expression_attribute_values[":Profile"] = profile

    update_expression.append("#Classifier = :Classifier")
    expression_attribute_names["#Classifier"] = "Classifier"
    expression_attribute_values[":Classifier"] = classifier

    update_expression.append("#TotalScore = :TotalScore")
    expression_attribute_names["#TotalScore"] = "TotalScore"
    expression_attribute_values[":TotalScore"] = total_score

    # Upsert will first Insert an Empty list and then append Debug Information if any found
    # This will serve as a Audit Trail on which segments were Included/Excluded for every Segment End event processing
    update_expression.append("#DebugInfo = list_append(if_not_exists(#DebugInfo, :initialDebugInfo), :DebugInfo)")
    expression_attribute_names["#DebugInfo"] = "DebugInfo"
    expression_attribute_values[":DebugInfo"] = []  # additional_info
    expression_attribute_values[":initialDebugInfo"] = []

    update_expression.append("#ReplayResults = :ReplayResults")
    expression_attribute_names["#ReplayResults"] = "ReplayResults"
    expression_attribute_values[
        ":ReplayResults"] = replay_results  # json.loads(json.dumps(replay_results), parse_float=Decimal)

    if len(replay_results) > 0:
        replay_results_table = ddb_resource.Table(REPLAY_RESULT_TABLE_NAME)

        replay_results_table.update_item(
            Key={"ProgramEventReplayId": f"{program}#{event}#{replay_id}"},
            UpdateExpression="SET " + ", ".join(update_expression),
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values
        )

        return "Replay results updated"

    return ""


def match_replays_with_segments(replay_items, program, event_name, classifier, tracknumber, last_evaluated_key_input, limit):
    plugin_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)
    result_items = []
    last_evaluated_key_result = ""

    for replay_index in range(last_evaluated_key_input, len(replay_items)):
        if len(result_items) < limit:
            replay_result = replay_items[replay_index]
            start_time = Decimal(str(replay_result['Start']))
            segment_response = plugin_table.query(
                IndexName='ProgramEvent_Start-index',
                KeyConditionExpression=Key("ProgramEvent").eq(f"{program}#{event_name}") &
                                       Key("Start").eq(start_time),
                FilterExpression=Attr('PK').eq(f"{program}#{event_name}#{classifier}")
            )
            if 'Items' in segment_response and len(segment_response['Items']) > 0:
                segment_response_data = segment_response['Items'][0]
                segment_data = populate_segment_data_matching(segment_response_data, tracknumber)
                if segment_data:
                    result_items.append(segment_data)
                    last_evaluated_key_result = replay_index

    if len(result_items) < limit:
        last_evaluated_key_result = ""

    result = {
        "Items": result_items,
        "LastEvaluatedKey": last_evaluated_key_result
    }

    return result


