#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

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

    MIN_DURATION = event['Plugin']['Configuration']['MIN_DURATION']
    results = []

    try:
        #get the dependent plugin name from plugin config
        #for this segmenter plugin, there is just one dependent plugin expected
        d_plugin_name = event["Plugin"]["DependentPlugins"][0]

        #calculate the start and end based on the original chunk time and provided ratio
        chunk_start = event['Input']['Metadata']['HLSSegment']['StartTime']

        #get all detector data since last start or end plus this current chunk
        state, segment, labels = mre_dataplane.get_segment_state()
        start_flag = True
        curr_dur = 0

        for label in labels[d_plugin_name]:
            print(label['Start'],label['Duration'])
            curr_dur += label['Duration']
            if start_flag:
                curr_start = label['Start']
                start_flag = False
            if curr_dur > MIN_DURATION:
                result = {}
                result["Start"] = curr_start
                result["End"] = label['Start'] + label['Duration']
                results.append(result)
                curr_dur = 0
                start_flag = True

        # check the last shot
        if start_flag == False and curr_dur > 1/2*MIN_DURATION:
            result = {}
            result["Start"] = curr_start
            result["End"] = curr_start + curr_dur
            results.append(result)
        print(results)

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
