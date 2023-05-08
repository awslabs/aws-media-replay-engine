# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import ast
from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import PluginHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane


def remove_dups_in_list(aList):
    simplified_list = []
    labels_list = []
    if len(aList) > 0:
        last_label = aList[0]['Label'] #initialize to the first label value
    new_label = True

    #loop through all the frame level label results
    for i, label_dict in enumerate(aList):
        if new_label:
            new_label_dict = label_dict
            new_label_dict['orig_idx'] = i
            new_label_dict['orig_idx_end'] = i
            new_label = False
        else:
            new_label_dict['orig_idx_end'] = i

        #is there a change of value in the list?
        if label_dict["Label"] != last_label:
            simplified_list.append(new_label_dict)
            new_label = True
            labels_list.append(new_label_dict['Label'])
            last_label = label_dict['Label']

    #add last label
    if len(aList) > 0:
        simplified_list.append(new_label_dict)
        labels_list.append(new_label_dict['Label'])

    return simplified_list, labels_list


def find_sequence(aList, aDeduppedList, aSearchList, aListOfSearchSequences, start_end, aStartPos = 0):
    result = []
    i = 0
    
    #Get the list of labels from the labels object
    aList = aList[list(aList.keys())[0]]

    for i in range(aStartPos, len(aSearchList)):
        for aSearchSequence in aListOfSearchSequences:
            # print("using search sequence: " + str(aSearchSequence))
            # print("compared to: " + str(aSearchList[i:i+len(aSearchSequence)]) )
            if aSearchList[i:i+len(aSearchSequence)] == aSearchSequence:
                if start_end == 'Start':
                    result.append(aList[aDeduppedList[i+len(aSearchSequence)-1]['orig_idx']])
                else:
                    result.append(aList[aDeduppedList[i]['orig_idx_end']])
                break
        else:
            # Continue if the inner loop wasn't broken
            continue
        # Inner loop was broken, break the outer
        break

    return result, i


def lambda_handler(event, context):

    print (event)

    results = []
    mre_dataplane = DataPlane(event)

    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)

    try:

        # plugin params

        #get the dependent plugin name from plugin config
        #for this segmenter plugin, there is just one dependent plugin expected
        d_plugin_name = event["Plugin"]["DependentPlugins"][0]

        #get all detector data since last start or end plus this current chunk
        state, segment, labels = mre_dataplane.get_segment_state()
        print("state: " + str(state))
        print("segment:",segment)

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
                search_results, search_from_idx = find_sequence(labels, labels_dedupped, labels_list, start_seq, 'Start', search_from_idx)

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
                search_results, search_from_idx = find_sequence(labels, labels_dedupped, labels_list, end_seq, 'End', search_from_idx)
                #print(search_results)

                if len(search_results) > 0:
                    print("We have results!: " + str(search_results))
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
