#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

##############################################################################
#
# PURPOSE:
# Handle the output of a plugin based on its execution status
#
##############################################################################

import os
import traceback

from MediaReplayEngineWorkflowHelper import ControlPlane
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import MREExecutionError


def lambda_handler(event, context):
    print("Lambda got the following event:\n", event)
    
    program = event["Event"]["Program"]
    p_event = event["Event"]["Name"]
    
    key = event["Input"]["Media"]["S3Key"]
    filename = os.path.split(key)[-1]
    
    output_plugin_name = event["Output"]["PluginName"]
    output_plugin_class = event["Output"]["PluginClass"]
    output_plugin_status = event["Output"]["Status"]
    
    print(f"Handling the output of plugin '{output_plugin_name}' of class '{output_plugin_class}' for program '{program}' and event '{p_event}'")
    
    try:
        controlplane = ControlPlane()
        
        controlplane.put_plugin_execution_status(p_event, program, filename, output_plugin_name, output_plugin_status)
        
        if output_plugin_status == Status.PLUGIN_ERROR:
            if output_plugin_class in ["Classifier", "Optimizer"]:
                # Stop the current step function invocation and set the status of the Event to Error
                pass
    
    except Exception as e:
        print(f"Encountered an exception while handling the output of plugin '{output_plugin_name}' of class '{output_plugin_class}' for program '{program}' and event '{p_event}': {str(e)}")
        print(traceback.format_exc())
        raise MREExecutionError(e)
    