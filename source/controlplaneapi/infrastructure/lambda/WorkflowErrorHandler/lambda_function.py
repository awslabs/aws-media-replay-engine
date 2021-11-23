#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

##############################################################################
#
# PURPOSE:
# Handle exceptions caught by the AWS Step Function workflow 
# and optionally update the execution status of the Classifier plugin
#
##############################################################################

import os
import json
import traceback

import boto3

from MediaReplayEngineWorkflowHelper import ControlPlane
from MediaReplayEnginePluginHelper import MREExecutionError

eb_client = boto3.client("events")


def lambda_handler(event, context):
    print("Lambda got the following event:\n", event)
    
    program = event["Event"]["Program"]
    p_event = event["Event"]["Name"]
    
    key = event["Input"]["Media"]["S3Key"]
    filename = os.path.split(key)[-1]
    
    classifier_plugin_name = event["Profile"]["Classifier"]["Name"]
    
    try:
        print(f"Checking the execution status of '{classifier_plugin_name}' plugin in the current workflow execution for program '{program}' and event '{p_event}'")
        
        controlplane = ControlPlane()
        
        status = controlplane.get_plugin_execution_status(p_event, program, filename, classifier_plugin_name)
        
        if not status or status in ["Waiting", "In Progress"]:
            print(f"Updating the execution status of '{classifier_plugin_name}' from '{status}' to 'Error' to unblock upcoming workflow executions")
            controlplane.put_plugin_execution_status(p_event, program, filename, classifier_plugin_name, "Error")
            
        else:
            print(f"No update is needed as the execution status of '{classifier_plugin_name}' is already '{status}'")
        
        print(f"Notifying the workflow failure to MRE Event Bus with the caught exception message")
        
        detail = {
            "State": "WORKFLOW_FAILED",
            "Payload": event
        }
        
        eb_client.put_events(
            Entries=[
                {
                    "Source": "awsmre",
                    "DetailType": "Workflow Status",
                    "Detail": json.dumps(detail),
                    "EventBusName": os.environ["EB_EVENT_BUS_NAME"]
                }
            ]
        )
        
        print("Raising an exception back to the Step Function with the caught exception message to mark it as failed")
        raise MREExecutionError(event["Error"])
        
    except MREExecutionError:
        raise
    
    except Exception as e:
        print(traceback.format_exc())
        raise
    