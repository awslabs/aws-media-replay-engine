# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import os
from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import PluginHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane

def lambda_handler(event, context):

    print(event)

    results = []
    mre_dataplane = DataPlane(event)

    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)

    mre_pluginhelper = PluginHelper(event)

    results = []

    try:
        # process chunk with ffmpeg using options provided
        chunk_to_segment_ratio = float(event['Plugin']['Configuration']['chunk_to_segment_ratio'])

        #calculate the start and end based on the original chunk time and provided ratio
        chunk_start = event['Input']['Metadata']['HLSSegment']['StartTime']
        duration = event['Input']['Metadata']['HLSSegment']['Duration']
        segment_start = chunk_start + ((duration * chunk_to_segment_ratio) / 2)
        segment_end = segment_start + duration - ((duration * chunk_to_segment_ratio) / 2)

        #get all detector data since last start or end plus this current chunk
        state, segment, labels = mre_dataplane.get_segment_state()
        print("state: ", str(state))
        print("segment: ", segment)
        print("labels: ", labels)

        #assemble the payload to submit to MRE with the single segment for this chunk
        result = {}
        result["Start"] = segment_start
        result["End"] = segment_end
        results.append(result)

        # Add the results of the plugin to the payload (required if the plugin status is "complete"; Optional if the plugin has any errors)
        mre_outputhelper.add_results_to_output(results)

        # Persist plugin results for later use
        mre_dataplane.save_plugin_results(results)

        # Update the processing status of the plugin (required)
        mre_outputhelper.update_plugin_status(Status.PLUGIN_COMPLETE)

        # Returns expected payload built by MRE helper library
        return mre_outputhelper.get_output_object()

    except Exception as e:
        print(e)

        # Update the processing status of the plugin (required)
        mre_outputhelper.update_plugin_status(Status.PLUGIN_ERROR)

        # Re-raise the exception to MRE processing where it will be handled
        raise
