# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json 
import boto3
import os
from decimal import Decimal

ddb_resource = boto3.resource("dynamodb")
EVENT_RECORDER_TABLE_NAME = os.environ["EVENT_RECORDER_TABLE_NAME"]

def handler(event, context):
    """
    This Lambda hooks onto the MRE Event Bus and listens to the  SEGMENT_END, OPTIMIZE_SEGMENT_END events emitted by MRE.
    In the process it records the Segments info into DDB. This is used for asserting if the Segments created by MRE are being emitted 
    reliably via the Event Bus for consumers.

    Args:
        event (_type_): _description_
        context (_type_): _description_
    """
    print(json.dumps(event))
    segment = event['detail']['Segment']
    segment_event_type = event['detail']['State'] #SEGMENT_END, OPTIMIZE_SEGMENT_END
    event_name = segment['Event']
    program_name = segment['Program']

    segment_start = segment['Start'] if segment_event_type == "SEGMENT_END" else segment['OptoStart']
    segment_end = segment['End'] if segment_event_type == "SEGMENT_END" else segment['OptoEnd']

    pk = f"{event_name}"

    '''
        #SEGMENT_END#10.11
        #OPTIMIZED_SEGMENT_END#10.11
    '''
    sk = f"{segment_event_type}#{segment_start}"  
    item = {}
    item['EventName'] = pk
    item['SegmentTypeStartTime'] = sk
    item['Start'] = segment_start
    item['End'] = segment_end
    item['SegmentEventType'] = segment_event_type

    # When dealing with Opto Segments, Capture OptoStart and OptoEnd
    if segment_event_type != "SEGMENT_END":
        item['OptoStart'] = segment_start
        item['OptoEnd'] = segment_end

    recorder_table = ddb_resource.Table(EVENT_RECORDER_TABLE_NAME)
    recorder_table.put_item(Item=json.loads(json.dumps(item), parse_float=Decimal))