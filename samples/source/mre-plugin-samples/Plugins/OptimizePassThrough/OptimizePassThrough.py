# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import PluginHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane

def lambda_handler(event, context):
    print("Lambda got the following event:\n", event)

    mre_dataplane = DataPlane(event)
    mre_outputhelper = OutputHelper(event)
    mre_pluginhelper = PluginHelper(event)

    results = []

    try:
        # plugin config
        plugin_config = mre_pluginhelper.get_plugin_configuration()
        print('Plugin config:\n', plugin_config)

        #Check if this plugin has dependencies and if so, get their respective configuration details
        dep_plugin_config = mre_pluginhelper.get_dependent_plugins_configuration()
        print('Dependent plugins config:\n', dep_plugin_config)

        #get all pending segments to be optimized and detector data within that time range plus the search window buffer time
        segments = mre_dataplane.get_segment_state_for_optimization(2)
        print('get_segment_state_for_optimization:\n', segments)

        for segment in segments:
            print('Next segment to optimize')
            new_result = {}

            new_result['Start'] = segment['Segment']['Start']
            new_result['End'] = segment['Segment']['End']
            new_result['OptoStart'] = segment['Segment']['Start']
            new_result['OptoEnd'] = segment['Segment']['End']
            new_result['OptoStartCode'] = 'Opto succeeded'
            new_result['OptoEndCode'] = 'Opto succeeded'

            results.append(new_result)

        print("Results:", results)

        # Persist plugin results for later use
        mre_dataplane.save_plugin_results(results)

        # Add the results of the plugin to the payload (required if the plugin status is "complete"; Optional if the plugin has any errors)
        mre_outputhelper.add_results_to_output(results)

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
