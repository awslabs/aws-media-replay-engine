#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

##############################################################################
#
# PURPOSE:
# Check the completion status of a Classifier/Optimizer plugin in the prior 
# AWS Step Function workflow executions
#
##############################################################################

import os
import traceback

from MediaReplayEngineWorkflowHelper import ControlPlane
from MediaReplayEnginePluginHelper import MREExecutionError


def lambda_handler(event, context):
    print("Lambda got the following event:\n", event)
    
    program = event["Event"]["Program"]
    p_event = event["Event"]["Name"]
    
    chunk_size = int(event["Profile"]["ChunkSize"])
    
    key = event["Input"]["Media"]["S3Key"]
    filename = os.path.split(key)[-1]
    
    multi_chunk_plugin_class = event["MultiChunk"]["PluginClass"]
    multi_chunk_wait_factor = event["MultiChunk"]["WaitFactor"]
    
    if multi_chunk_plugin_class == "Classifier":
        multi_chunk_plugin_name = event["Profile"]["Classifier"]["Name"]
    elif multi_chunk_plugin_class == "Optimizer":
        multi_chunk_plugin_name = event["Profile"]["Optimizer"]["Name"]
    
    print(f"Checking the execution status of '{multi_chunk_plugin_name}' plugin in prior workflow executions for program '{program}' and event '{p_event}'")
    
    is_completed = False
    
    try:
        controlplane = ControlPlane()
        
        executions = controlplane.list_incomplete_executions(p_event, program, filename, multi_chunk_plugin_name)
        
        if len(executions) > 0:
            is_completed = False
            print(f"Found one or more incomplete prior workflow executions for '{multi_chunk_plugin_name}' plugin. Waiting for them to complete.")
            controlplane.put_plugin_execution_status(p_event, program, filename, multi_chunk_plugin_name, "Waiting")
            
        else:
            is_completed = True
            print(f"All the prior workflow executions for '{multi_chunk_plugin_name}' plugin are complete. Proceeding forward.")
            controlplane.put_plugin_execution_status(p_event, program, filename, multi_chunk_plugin_name, "In Progress")
        
        return {
            "Event": event["Event"],
            "Input": event["Input"],
            "Profile": event["Profile"],
            "MultiChunk": {
                "IsCompleted": is_completed,
                "WaitSeconds": chunk_size // multi_chunk_wait_factor
            }
        }
    
    except Exception as e:
        print(f"Encountered an exception while checking the execution status of '{multi_chunk_plugin_name}' plugin in prior workflow executions for program '{program}' and event '{p_event}': {str(e)}")
        print(traceback.format_exc())
        raise MREExecutionError(e)
    