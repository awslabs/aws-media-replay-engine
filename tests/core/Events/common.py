# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0


import json
import sys
import time
import boto3
import os
import logging
from utils.api_client import call_api, ApiUrlType
from boto3.dynamodb.conditions import Key, Attr

def wait_for_event_completion(event_config):
    count = 1
        # We try for Event Completion in the next 2.5 mins (Event Bootstrap = 3 mins + Some Buffer)
    while count <= 5:
        mre_event = call_api(path=f"event/{event_config['Name']}/program/{event_config['Program']}", api_method="GET")
        mre_event = mre_event.json()
        if mre_event['Status'] == "Complete":
            return True
        count += 1
        time.sleep(30)
    return False


def get_event_recorder_data(event_config):

    ddb_resource = boto3.resource("dynamodb")
    EVENT_RECORDER_TABLE_NAME = get_recorder_table_name()
    event_recorder_table = ddb_resource.Table(EVENT_RECORDER_TABLE_NAME)

    response = event_recorder_table.query(
            KeyConditionExpression=Key("EventName").eq(f"{event_config['Name']}")
        )
    events = []
    events = response["Items"]

    while "LastEvaluatedKey" in response:
        response = event_recorder_table.query(
            ExclusiveStartKey=response["LastEvaluatedKey"],
            KeyConditionExpression=Key("EventName").eq(f"{event_config['Name']}")
        )
        events.extend(response["Items"])

    return events


def get_recorder_table_name() -> str:
    client = boto3.client('dynamodb')
    response = client.list_tables(
    )
    tables = response['TableNames']
    if 'LastEvaluatedTableName' in response:
        response = client.list_tables(
            ExclusiveStartTableName=response['LastEvaluatedTableName']
        )
        tables.extend(response['TableNames'])


    recorder_table = [table for table in tables if "EventStateRecorder" in table]
    if recorder_table:
        return recorder_table[0]
    else:
        raise Exception("Event State Recorder Table Not Found")




def get_segment_start_times(route) -> list:
    start_times = []
    response = call_api(path=route, api_method="GET",api_url=ApiUrlType.DATA_PLANE)
    segment_info = json.loads(response.content.decode("utf-8"))
    for segment in segment_info['Items']['Segments']:
        start_times.append(segment['StartTime'])
    start_times.sort(key=float)
    return start_times