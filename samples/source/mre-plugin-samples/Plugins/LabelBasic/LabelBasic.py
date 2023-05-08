# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane

def your_function_to_format_a_label(segments, noun):
    results = []
    result = {}

    #loop through all the segments (0 to many) for this chunk
    for segment in segments:
        result = {}
        #your logic to format a string to be the Label for this segment
        result['Start'] = segment['Segment']['Start']
        result['End'] = segment['Segment']['End']
        result['Label'] = noun + ' in chunk ' + str(segment['Segment']['ChunkNumber']) + ' at ' + str(segment['Segment']['Start'])
        result['LabelCode'] = 'Succeeded'
        results.append(result)
    return results


def lambda_handler(event, context):
    print (event)

    results = []
    mre_dataplane = DataPlane(event)

    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)

    #What are we calling our detection. For example : 'Scene change in chunk 18 at 169.17'
    chunkNoun = event['Plugin']['Configuration']['chunk_noun']

    try:

        jsonResults = mre_dataplane.get_segment_state_for_labeling()
        print('jsonResults=',jsonResults)

        results = your_function_to_format_a_label(jsonResults, chunkNoun)
        print('results=',results)

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
