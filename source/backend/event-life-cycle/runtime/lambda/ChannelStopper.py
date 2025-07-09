#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

##############################################################################
#
# PURPOSE:
# Stops a Media Live Channel
#
##############################################################################

import json
import traceback

import boto3

medialive_client = boto3.client("medialive")


def get_program_event_from_medialive(channel_id):
    
    response = medialive_client.describe_channel(ChannelId=channel_id)
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
    '''
        Stops a Medialive channel
    '''
    print(f"Lambda got the following event:\n{event}")
    
    try:
        channel_id = ""
        channel_state = ""
        
        # If this Lambda gets triggered from EventBridge Rule
        if event["source"] == "awsmre":
            p_event = event["detail"]["Event"]
            program = event["detail"]["Program"]

            # Check if the event has been configured to Stop the Channel
            # If not, do not Stop the Channel
            if not event["detail"]["StopChannel"]:
                print(f"Triggered for LIVE event {p_event} but StopChannel was Disabled. Not Stopping the Channel.")
                return

            if "ChunkSourceDetail" in event["detail"]:
                if "ChannelId" in event["detail"]["ChunkSourceDetail"]:
                    channel_id = event["detail"]["ChunkSourceDetail"]["ChannelId"]
            else:
                raise Exception("ChunkSourceDetail was not found. THIS IS A PROBLEM. Check the EventBridge event Payload")
            
            # Only if we have a Channel Id we Try to Stop it as long as its in a RUNNING state
            if program and p_event and channel_id != "":
                program, p_event, channel_state = get_program_event_from_medialive(channel_id)

                # Stop the MediaLive channel if its Running
                if channel_state == "RUNNING":
                    print(f"Stopping the MediaLive channel '{channel_id}' as '{p_event}' in program '{program}'")

                    medialive_client.stop_channel(
                        ChannelId=channel_id
                    )
    
    except Exception as e:
        print(f"Encountered an exception while stopping the channel: {str(e)}, event passed = {json.dumps(event)}")
        print(traceback.format_exc())
        raise
    