#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

##############################################################################
#
# PURPOSE:
# Deletes Event Bridge Schedule created for VOD, LIVE events
#
##############################################################################

import boto3
import traceback
import json
from datetime import datetime, timedelta
from botocore.config import Config


boto_config = Config(
                retries = {
                    'max_attempts': 10,
                    'mode': 'adaptive'
                }
            )

scheduler_client = boto3.client('scheduler', config=boto_config)
medialive_client = boto3.client("medialive")

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
    print(f"Event payload = {json.dumps(event)}")

    # Lets Try deleting both VOD and LIVE Schedules for this Event
    # since we dont really know if this Channel was running LIVE or VOD events
    if 'vod_schedule_name' in event["detail"]:
        delete_schedule(event["detail"]['vod_schedule_name'])

    if 'live_start_schedule_id' in event["detail"]:
        delete_schedule(event["detail"]['live_start_schedule_id'])

    if 'live_end_schedule_id' in event["detail"]:
        delete_schedule(event["detail"]['live_end_schedule_id'])
            

def delete_schedule(schedule_name):
    try:
        scheduler_client.delete_schedule(Name=schedule_name)
        print(f"Deleted schedule_name = {schedule_name}")
    except Exception as e:
        print(f"Encountered an exception while deleting a Schedule {schedule_name} {str(e)}.")
        print(traceback.format_exc())