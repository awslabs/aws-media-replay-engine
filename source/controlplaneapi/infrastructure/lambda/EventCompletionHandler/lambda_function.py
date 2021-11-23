#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

##############################################################################
#
# PURPOSE:
# Update the status of an MRE event to Complete based on the 
# configured CloudWatch EventBridge triggers. Optionally, stop
# the MediaLive channel for VOD events.
#
##############################################################################

import boto3
import traceback

from datetime import datetime, timedelta
from MediaReplayEngineWorkflowHelper import ControlPlane

medialive_client = boto3.client("medialive")


def get_program_event_from_medialive(channel_id):
    print(f"Describing the MediaLive channel '{channel_id}'")
    
    response = medialive_client.describe_channel(
        ChannelId=channel_id
    )
    
    print("Getting the MRE program and event information from 'awsmre' MediaLive Destination")
    
    destinations = response["Destinations"]
    
    program = ""
    p_event = ""
    
    for destination in destinations:
        if destination["Id"] == "awsmre":
            url = destination["Settings"][0]["Url"]
            program = url.split("/")[4]
            p_event = url.split("/")[5]
            break
        
    return (program, p_event, response["State"])

def lambda_handler(event, context):
    print(f"Lambda got the following event:\n{event}")
    
    controlplane = ControlPlane()
    
    try:
        # If the trigger is MediaLive Stopped State Change EventBridge Rule
        if event["source"] == "aws.medialive":
            channel_arn = event["detail"]["channel_arn"]
            channel_id = channel_arn.split(":")[-1]
        
        # If the trigger is MediaLive CloudWatch Metric Alarm EventBridge Rule
        elif event["source"] == "aws.cloudwatch":
            channel_id = event["detail"]["configuration"]["metrics"][0]["metricStat"]["metric"]["dimensions"]["ChannelId"]
            
        program, p_event, channel_state = get_program_event_from_medialive(channel_id)
            
        if program and p_event:
            # Update the status of the MRE event to "Complete" if not done already
            if controlplane.get_event_status(p_event, program) == "In Progress":
                print(f"Updating the status of event '{p_event}' in program '{program}' to 'Complete'")
                controlplane.put_event_status(p_event, program, "Complete")

            # Stop the MediaLive channel for VOD events
            if event["source"] == "aws.cloudwatch" and channel_state == "RUNNING":
                mre_event = controlplane.get_event(p_event, program)

                event_start_utc = datetime.strptime(mre_event["Start"], "%Y-%m-%dT%H:%M:%SZ")
                event_duration = int(mre_event["DurationMinutes"])
                cur_utc_time = datetime.utcnow()

                if cur_utc_time > (event_start_utc + timedelta(minutes=event_duration)):
                    print(f"Stopping the MediaLive channel '{channel_id}' as '{p_event}' in program '{program}' is a VOD event")

                    medialive_client.stop_channel(
                        ChannelId=channel_id
                    )
    
    except Exception as e:
        print(f"Encountered an exception while updating the status of an MRE event to Complete: {str(e)}")
        print(traceback.format_exc())
        raise
