# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import PluginHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane

def lambda_handler(event, context):

    print(event)
    duration = event['Input']['Metadata']['HLSSegment']['Duration']

    results = []
    mre_dataplane = DataPlane(event)

    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)
    mre_pluginhelper = PluginHelper(event)

    try :
        for seg_time in range(int(duration)):
            result = {}
            result['Start'] = mre_pluginhelper.get_segment_absolute_time(seg_time)
            result['End'] = result['Start']
            result['Label'] = 'TEST'
            for i in range(1,100):
                result['Attribute' + str(i)] = True

            results.append(result)

        print(results)

        #get all dependent detector data
        depResults = mre_dataplane.get_dependent_plugins_output()
        print(depResults)

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
