#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

##############################################################################
#
# PURPOSE:
# Update the status of an MRE event to Complete based on the configured CloudWatch EventBridge rules. 
# 
##############################################################################

import boto3
import traceback
import json
import os
from datetime import datetime, timedelta
from MediaReplayEngineWorkflowHelper import ControlPlane

controlplane = ControlPlane()

EB_EVENT_BUS_NAME = os.environ['EB_EVENT_BUS_NAME']
medialive_client = boto3.client("medialive")
eb_client = boto3.client("events")

def get_program_event_from_medialive(channel_id):
    response = medialive_client.describe_channel(
        ChannelId=channel_id
    )
    destinations = response["Destinations"]
    program = ""
    p_event = ""
    for destination in destinations:
        if destination["Id"] == "awsmre":
            url = destination["Settings"][0]["Url"]
            if len(url.split("/")) == 7: #BYOB Testing via MediaLive
                program = url.split("/")[3]
                p_event = url.split("/")[4]
                break
            else:
                program = url.split("/")[4]
                p_event = url.split("/")[5]
                break
        
    return (program, p_event, response["State"])

def lambda_handler(event, context):
    print(f"Lambda got the following event:\n{event}")
    
    try:
        channel_id = ""
        channel_state = ""
        is_vod_event = False
        
        # If the Lambda was triggered when MediaLive channel is Stopped manually by the user
        if event["source"] == "aws.medialive":
            channel_arn = event["detail"]["channel_arn"]
            channel_id = channel_arn.split(":")[-1]
            program, p_event, channel_state = get_program_event_from_medialive(channel_id)
            print(f"program={program}")
            print(f"p_event={p_event}")

            # Check if this is a LIVE event
            event = controlplane.get_event(p_event, program)

            event_creation_time_utc = datetime.strptime(event["Created"], "%Y-%m-%dT%H:%M:%SZ")
            event_start_time_utc = datetime.strptime(event["Start"], "%Y-%m-%dT%H:%M:%SZ")

            # Event Start time is more than Event Create time. This is a LIVE event
            is_vod_event = True if event_start_time_utc < event_creation_time_utc else False
        
        # If this Lambda gets triggered from EventBridge Schedule via VOD_EVENT_END or LIVE_EVENT_END
        elif event["source"] == "awsmre":
            p_event = event["detail"]["Event"]
            program = event["detail"]["Program"]
            is_vod_event = event["detail"]["IsVODEvent"] if "IsVODEvent" in event["detail"] else False

            if "ChunkSourceDetail" in event["detail"]:
                if "ChannelId" in event["detail"]["ChunkSourceDetail"]:
                    channel_id = event["detail"]["ChunkSourceDetail"]["ChannelId"]
                    program, p_event, channel_state = get_program_event_from_medialive(channel_id)
            else:
                raise Exception("ChunkSourceDetail was not found. THIS IS A PROBLEM. Check the EventBridge event Payload")
           
        print(f"program={program}-p_event={p_event}")
        if program and p_event:
            # Update the status of the MRE event to "Complete" if not done already
            # Event Status needs to be Updated no matter the Input Chunk Source (ML, BYOB etc)
            event_status = controlplane.get_event_status(p_event, program)
            print(f"Current event_status = {event_status}")

            if event_status == "In Progress":
                controlplane.put_event_status(p_event, program, "Complete")
                print(f"Updated the status of event '{p_event}' in program '{program}' to 'Complete'")

            # Send VOD_EVENT_COMPLETE / LIVE_EVENT_COMPLETE to Event Bridge 
            # We send this every time the Lambda gets triggered to let schedules be deleted in the
            # Subscriber Lambda
            put_event_start_to_event_bus(is_vod_event, p_event, program, event, channel_id)
            print("Published VOD_EVENT_COMPLETE / LIVE_EVENT_COMPLETE to Event Bridge")
            
    except Exception as e:
        print(f"Encountered an exception while updating the status of an MRE event to Complete: {str(e)}")
        print(traceback.format_exc())
        raise

def put_event_start_to_event_bus(is_vod, event_name, program_name, event, channel_id):
    
    event_payload = controlplane.get_event(event_name, program_name)
    payload_detail = {
                "State": "VOD_EVENT_COMPLETE" if is_vod else "LIVE_EVENT_COMPLETE",
                "Event": event_name,
                "Program": program_name,
                "IsVodEvent": is_vod,
                "ChannelId": channel_id
                
            }

    if 'vod_schedule_id' in event_payload:
        payload_detail['vod_schedule_name'] = event_payload['vod_schedule_id']

    if 'live_start_schedule_id'in event_payload:
        payload_detail['live_start_schedule_id'] = event_payload['live_start_schedule_id']

    if 'live_end_schedule_id'in event_payload:
        payload_detail['live_end_schedule_id'] = event_payload['live_end_schedule_id']

    eb_client.put_events(
        Entries=[
            {
                "Source": "awsmre",
                "DetailType": "VOD/LIVE event has been completed.",
                "Detail": json.dumps(payload_detail),
                "EventBusName": EB_EVENT_BUS_NAME
            }
        ]
    )

