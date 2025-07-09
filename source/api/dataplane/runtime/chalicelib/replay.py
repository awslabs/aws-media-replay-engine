# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import gzip
import json
import os
import time
import urllib.parse
from datetime import datetime
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr, Key
from chalice import Blueprint, ChaliceViewError, IAMAuthorizer
from chalicelib import load_api_schema
from chalicelib.common import (get_event_segment_metadata,
                               populate_segment_data_matching)
from aws_lambda_powertools import Logger

PLUGIN_RESULT_TABLE_NAME = os.environ['PLUGIN_RESULT_TABLE_NAME']
REPLAY_RESULT_TABLE_NAME = os.environ['REPLAY_RESULT_TABLE_NAME']
JOB_TRACKER_TABLE_NAME = os.environ['JOB_TRACKER_TABLE_NAME']

authorizer = IAMAuthorizer()
ddb_resource = boto3.resource("dynamodb")
API_SCHEMA = load_api_schema()

replay_api = Blueprint(__name__)
logger = Logger(service="aws-mre-dataplane-api")

class DecimalEncoder(json.JSONEncoder):
  def default(self, obj):
    if isinstance(obj, Decimal):
      return float(obj)
    return json.JSONEncoder.default(self, obj)


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
                replay_results = json.loads(gzip.decompress(bytes(replay_results_query['Items'][0]['ReplayResults'])).decode('utf-8'))
                replay_clips = match_replays_with_segments(replay_results, program, name,
                                                        classifier, tracknumber, last_evaluated_key, limit)
            except KeyError:
                pass
        else:
            return {
                "LastEvaluatedKey": None,
                "Items": [],
            }
    except Exception as e:
        logger.info(e)
        logger.info(f"Unable to match replays for event '{name}' in Program '{program}': {str(e)}")
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

            tmp_replay_results = json.loads(gzip.decompress(bytes(replay_result['ReplayResults'])).decode('utf-8'))
            for result in tmp_replay_results:
                # logger.info(f"Replay Start = {type(result['Start'])}")
                for segment in segment_metadata['Segments']:
                    # logger.info(type(segment['StartTime']))
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
            if 'ReplayResults' in replay_results_response[0]:
                tmp_replay_results = json.loads(gzip.decompress(bytes(replay_results_response[0]['ReplayResults'])).decode('utf-8'))
                return tmp_replay_results
            else:
                return []
        else:
            return []
    else:
        return []

def create_replay_result(replay_results_table, replay_result):
    program = replay_result["Program"]
    event = replay_result["Event"]
    replay_id = replay_result["ReplayId"]
    profile = replay_result["Profile"]
    classifier = replay_result["Classifier"]
    
    additional_info = []
    total_score = replay_result["TotalScore"]
    lastSegmentStartTime = replay_result["LastSegmentStartTime"]


    json_data = json.dumps(replay_result['ReplayResults'], indent=2, cls=DecimalEncoder)
    # Convert to bytes
    encoded = json_data.encode('utf-8')
    compressed_replay_results = gzip.compress(encoded)

    replay_results = compressed_replay_results

    try:
        replay_results_table.put_item(
            Item={
                "CreatedOn": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "UpdatedOn": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ReplayId": replay_id,
                "ProgramEventReplayId": f"{program}#{event}#{replay_id}",
                "Event": event,
                "Program": program,
                "Profile": profile,
                "Classifier": classifier,
                "TotalScore": total_score,
                "LastSegmentStartTime": lastSegmentStartTime,
                "DebugInfo": [],
                "ReplayResults": replay_results
            },
            ConditionExpression="attribute_not_exists(ProgramEventReplayId)",
        )
    except ddb_resource.meta.client.exceptions.ConditionalCheckFailedException as e: 
        #Ignore this since we issue an update later
        pass


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
    logger.info(replay_result)

    program = replay_result["Program"]
    event = replay_result["Event"]
    replay_id = replay_result["ReplayId"]
    profile = replay_result["Profile"]
    classifier = replay_result["Classifier"]

    init_replay_results = replay_result["ReplayResults"]
    json_data = json.dumps(init_replay_results, indent=2, cls=DecimalEncoder)
    # Convert to bytes
    encoded = json_data.encode('utf-8')
    replay_results = gzip.compress(encoded) # Replay Results can be rather large. Compressing it to be below 400KB

    #replay_results = replay_result["ReplayResults"]
    additional_info = replay_result["AdditionalInfo"]
    total_score = replay_result["TotalScore"]
    lastSegmentStartTime = replay_result["LastSegmentStartTime"]
    has_clip_feedback = replay_result['HasFeedback']

    update_expression = []
    expression_attribute_names = {}
    expression_attribute_values = {}

    update_expression.append("#UpdatedOn = :UpdatedOn")
    expression_attribute_names["#UpdatedOn"] = "UpdatedOn"
    expression_attribute_values[":UpdatedOn"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

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

    # When a Segment gets added or deleted manually (via Feedback), do not Update the LastSegmentStartTime since this will be a Old
    # Segment Start time. For ex, if current ReplayResults was when a Segment with StartTime of 3400.54 secs,
    # and a older Segment (Start time of 1390.23) was Forcibly added, we dont want to change the LastSegmentStartTime to be 1390.23
    if not has_clip_feedback:
        update_expression.append("#LastSegmentStartTime = :LastSegmentStartTime")
        expression_attribute_names["#LastSegmentStartTime"] = "LastSegmentStartTime"
        expression_attribute_values[":LastSegmentStartTime"] = lastSegmentStartTime

    

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

        create_replay_result(replay_results_table, replay_result)

        # Handle Race conditions - Based on the LastSegmentStartTime which should be less than the 
        # new value. If the value is more, we are trying to update an older 
        # replay result.
        try:
            if not has_clip_feedback:
                replay_results_table.update_item(
                    Key={"ProgramEventReplayId": f"{program}#{event}#{replay_id}"},
                    UpdateExpression="SET " + ", ".join(update_expression),
                    ConditionExpression="attribute_exists(LastSegmentStartTime) and LastSegmentStartTime <= :LastSegmentStartTime",
                    ExpressionAttributeNames=expression_attribute_names,
                    ExpressionAttributeValues=expression_attribute_values
                )
            else:
                replay_results_table.update_item(
                    Key={"ProgramEventReplayId": f"{program}#{event}#{replay_id}"},
                    UpdateExpression="SET " + ", ".join(update_expression),
                    ExpressionAttributeNames=expression_attribute_names,
                    ExpressionAttributeValues=expression_attribute_values
                )
        except ddb_resource.meta.client.exceptions.ConditionalCheckFailedException as e: 
            logger.info(f'POSSIBLE RACE CONDITION!! Got lastSegmentStartTime={str(lastSegmentStartTime)} ')
            return False

    return True


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


@replay_api.route('/job/status/{job_id}',cors=True, methods=['GET'], authorizer=authorizer)
def get_job_status(job_id):
    jobid = urllib.parse.unquote(job_id)

    job_tracker_table = ddb_resource.Table(JOB_TRACKER_TABLE_NAME)
    response = job_tracker_table.query(
        KeyConditionExpression=Key("JobId").eq(jobid)
    )

    if 'Items' in response:
        return response['Items']
    else:
        return []

@replay_api.route('/job/create/{job_id}',cors=True, methods=['POST'], authorizer=authorizer)
def create_job(job_id):
    jobid = urllib.parse.unquote(job_id)
    job_tracker_table = ddb_resource.Table(JOB_TRACKER_TABLE_NAME)

    job_details = {}
    job_details["JobId"] = jobid
    job_details["Status"] = "CREATED"
    job_details["ttl"] = int(time.time()) + 18000 # 5 hrs * 3600 = 18000 secs // TTL of 5 Hrs
    job_tracker_table.put_item(Item=job_details)
    


@replay_api.route('/job/update/{job_id}/{status}',cors=True, methods=['POST'], authorizer=authorizer)
def update_job_status(job_id, status):
    jobid = urllib.parse.unquote(job_id)
    status = urllib.parse.unquote(status)

    job_tracker_table = ddb_resource.Table(JOB_TRACKER_TABLE_NAME)

    update_expression = []
    expression_attribute_names = {}
    expression_attribute_values = {}

    update_expression.append("#Status = :Status")
    expression_attribute_names["#Status"] = "Status"
    expression_attribute_values[":Status"] = status

    update_expression.append("#ttl = :ttl")
    expression_attribute_names["#ttl"] = "ttl"
    expression_attribute_values[":ttl"] = int(time.time()) + 18000 # 5 hrs * 3600 = 18000 secs // TTL of 5 Hrs

    job_tracker_table.update_item(
        Key={"JobId": jobid},
        UpdateExpression="SET " + ", ".join(update_expression),
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values
    )
