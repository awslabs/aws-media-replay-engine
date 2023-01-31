#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

##############################################################################
#
# PURPOSE:
# Execute MRE StepFunction workflow for every HLS video segment (.ts) file 
# stored in S3
#
##############################################################################

import os
import json
import boto3
import uuid
import traceback
import urllib.parse

from MediaReplayEngineWorkflowHelper import ControlPlane

sfn = boto3.client('stepfunctions')


def lambda_handler(event, context):
    controlplane = ControlPlane()
    
    execution_id = str(uuid.uuid4())
    
    s3_bucket = event['Records'][0]['s3']['bucket']['name']
    s3_key = event['Records'][0]['s3']['object']['key']

    print(f"s3_key={s3_key}")
    print(f"s3_bucket={s3_bucket}")
    
    # UnquotePlus the URL encoded S3 Key
    s3_key = urllib.parse.unquote_plus(s3_key)
    
    if len(s3_key.split("/")) == 3: #BYOB
        # Get the program, event and profile from the S3 Key
        program = s3_key.split("/")[0]
        p_event = s3_key.split("/")[1]
        profile = s3_key.split("/")[2]
    else:
        # Get the program, event and profile from the S3 Key
        program = s3_key.split("/")[-4]
        p_event = s3_key.split("/")[-3]
        profile = s3_key.split("/")[-2]
    
    try:
        print(f"Getting the Event details and StepFunction ARN from the Control plane")
        mre_event = controlplane.get_event(p_event, program)
        event_start_time = mre_event["Start"]
        generate_orig_clips = mre_event["GenerateOrigClips"]
        generate_opto_clips = mre_event["GenerateOptoClips"]
        sfn_arn = controlplane.get_profile(profile)["StateMachineArn"]
        
        sfn_input = {
            "Event": {
                "Name": p_event,
                "Program": program,
                "Start": event_start_time,
                "GenerateOrigClips": generate_orig_clips,
                "GenerateOptoClips": generate_opto_clips
            },
            "Input": {
                "ExecutionId": execution_id,
                "Media": {
                    "S3Bucket": s3_bucket,
                    "S3Key": s3_key
                }
            }
        }
        
        print(f"Starting the StepFunction execution of '{sfn_arn}' for bucket '{s3_bucket}' and key '{s3_key}'")

        
        event_status = controlplane.get_event_status(p_event, program)

        if event_status == "Complete":
            print(f"Event status is Complete. Not starting StepFunction execution for arriving chunks event '{p_event}' in program '{program}'.")
            return
        
        sfn.start_execution(
            stateMachineArn=sfn_arn,
            name=execution_id,
            input=json.dumps(sfn_input),
        )
        
        print("Successfully started the StepFunction execution")
        
        
        # Update the status of event to "In Progress" if not done already
        if event_status != "In Progress":
            print(f"Updating the status of event '{p_event}' in program '{program}' to 'In Progress'")
            controlplane.put_event_status(p_event, program, "In Progress")
    
    except Exception as e:
        print(f"Encountered an exception while starting the step function execution: {str(e)}")
        print(traceback.format_exc())
        raise Exception(e)
        