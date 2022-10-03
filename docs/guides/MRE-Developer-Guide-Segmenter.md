[![Header](../assets/images/mre-header-1.png)](../../MRE-Developer-Guide.md)

# Developers Guide - Segmenter Plugin

The segmentation plugin class is responsible for determining where the start and end of a clip is within the video chunks processed. The MRE helper library is required to persist the key data for each segment. This is done by specifying the **Start** and **End** using absolute time for the event. Absolute time starts with a value of 0 at the very first frame processed in the event. In situations where the beginning of a segment is found in a chunk but not the end, simply pass just the start back to the helper library in the payload. When the next chunk is processed, the existance of a incomplete segment will be made available via the helper library so state is known to the segmenter plugin.

Below is a partial example of a segmenter plugin that uses scene change (camera angles) in a specific sequence (i.e. near-far) as defined in the plugin configuration.  

```
def lambda_handler(event, context):

    print (event)

    results = []
    mre_dataplane = DataPlane(event) # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)

    try:
        # plugin params

        #get all detector data since last start or end plus this current chunk
        state, segment, labels = mre_dataplane.get_segment_state()
        print("state: ", str(state))
        print("segment:", segment)

        #get the dependent plugin name from plugin config
        #for this segmenter plugin, there is just one dependent plugin
        d_plugin_name = event["Plugin"]["DependentPlugins"][0]

        labels_scene = [label for label in labels[d_plugin_name]]

        labels_dedupped, labels_list = remove_dups_in_list(labels_scene)

        print('Dedupped label list to work with:')
        for i, label in enumerate(labels_dedupped):
            #print(label)
            print('Label ' + str(i) + ', ' + label['Label'] + ', Start: ' + str(label['Start']) + ', orig_idx: ' + str(label['orig_idx']) + ', orig_idx_end: ' + str(label['orig_idx_end']) )

        #expected labels: far, near, replay, scene, topview
        start_seq = ast.literal_eval(event['Plugin']['Configuration']['start_seq']) #[['near', 'far'], ['topview', 'far']]
        end_seq = ast.literal_eval(event['Plugin']['Configuration']['end_seq']) #[['far', 'near'], ['far', 'topview']]  

        padding_seconds = int(event['Plugin']['Configuration']['padding_seconds'])

        search_from_idx = 0
        keep_searching = True
        first_pass = True
        have_partial = False

        segment_payload = {}
        print('')            

        while keep_searching:

            if state is None or state == "End":
                #look for start sequence
                if first_pass:
                    print('first_pass looking for start')
                    search_from_idx = 0
                    first_pass = False
                else:
                    search_from_idx += len(end_seq)

                #print("tryin with search_from_idx: " + str(search_from_idx))
                search_results, search_from_idx = find_sequence(labels[d_plugin_name], labels_dedupped, labels_list, start_seq, 'Start', search_from_idx)

                if len(search_results) > 0:
                    print(search_results)
                    segment_payload = {} #reset payload
                    segment_payload['Start'] = search_results[0]['Start'] - padding_seconds
                    state = 'Start' #now look for end
                    have_partial = True
                    print('start found at ' + str(search_from_idx) + ' with: ' + str(search_results[0]['Start']))
                else:
                    keep_searching = False

            elif state == "Start":
                #look for “End”
                if first_pass:
                    print('first_pass looking for end')
                    search_from_idx = 0
                    first_pass = False
                else:
                    search_from_idx += 1 #len(start_seq) >> overlapping far segment sequences area needed to find the end, so try offsetting by 1

                #print("tryin with search_from_idx: " + str(search_from_idx))
                search_results, search_from_idx = find_sequence(labels[d_plugin_name], labels_dedupped, labels_list, end_seq, 'End', search_from_idx)
                #print(search_results)

                if len(search_results) > 0:
                    if 'Start' not in segment_payload:
                        segment_payload['Start'] = segment[state]
                    segment_payload['End'] = search_results[0]['Start'] + padding_seconds
                    results.append(segment_payload)
                    state = 'End' #now look for start
                    have_partial = False
                    print('end found at ' + str(search_from_idx) + ' with: ' + str(search_results[0]['Start']))
                else:
                    keep_searching = False

        if have_partial:
            results.append(segment_payload)  #adding the start without end... maybe next chunk will have it

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

**How does the Segmenter plugin know what to look for in the current chunk?**
```
state, last_segment, labels = mre_dataplane.get_segment_state()

if state is None or state == "End":
	look for "Start"

elif state == "Start":
	look for "End"
```
get_segment_state() outputs a list with 3 items: 
- The first item is one of: “Start” (if the last segment result is “Start”), “End” (if the last segment result is “End”), None (if there is no last segment result).
- The second item is a dictionary containing the last segment (if the last segment result is either “Start“ or “End“) or {}.
- Finally, the third item is a dictionary containing the dependent plugins of the Segmenter plugin as keys with values being the results outputted by those dependent plugins since the last segment start/end (spans across multiple chunks) or {} (if there are no results outputted by the dependent plugins of the Segmenter plugin since the last segment start/end).