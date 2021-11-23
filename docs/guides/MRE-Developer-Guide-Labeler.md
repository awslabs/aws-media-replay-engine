![mre-header](mre-header-1.png)

# Developers Guide - Labeler Plugin

The Labeler class plugin is responsible for generating a custom label for each segment. It is optional. Formatting a label can make use of the available segment data.

The particular MRE helper function for labeling is this:

```
  result = mre_dataplane.get_segment_state_for_labeling()
```

A starter Lambda function for labeling is shown below. Reminder to include the MRE plugin helper Lambda Layer called: MediaReplayEnginePluginHelper

```
from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane

def your_function_to_format_a_label(segments):
    results = []
    result = {}

    #loop through all the segments (0 to many) for this chunk   
    for segment in segments:
        #your logic to format a string to be the Label for this segment
        result['Label'] = 'TBD'
        results.append(result)        
    return results


def lambda_handler(event, context):
    print (event)

    results = []
    mre_dataplane = DataPlane(event)

    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)

    try:

        jsonResults = mre_dataplane.get_segment_state_for_labeling()
        print('jsonResults=',jsonResults)

        results = your_function_to_format_a_label(jsonResults)     
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

```
