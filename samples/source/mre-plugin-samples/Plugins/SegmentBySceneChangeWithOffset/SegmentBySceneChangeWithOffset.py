# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import logging
import os
from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane
import ast

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig()
logger = logging.getLogger('segmentation_with_offset')
logger.setLevel(LOG_LEVEL)

def remove_dups_in_list_ml(aList, min_len):
    simplified_list = []
    labels_list = []

    #Key for label that will be used for matching
    labelkey = 'Label'
    new_label = True
    if len(aList) > 0:
        first_label = aList[0][labelkey] ###initialize to the first label value

    # counter for consective changes
    n_change = 0
    saved_start = 0
    saved_label = aList[0]

    #loop through all the frame level label results
    for i, curr_label in enumerate(aList):
        # Find a new segment, start saving the previous one
        if new_label:
            new_label_dict = saved_label
            new_label_dict['orig_idx'] = saved_start
            new_label = False

        #is there a change of value in the list?
        if curr_label[labelkey] != first_label:
            if n_change == 0:
                saved_start = i
                saved_label = curr_label
                # print('saved start:',saved_start)
            n_change += 1
        else:
            n_change = 0
        #if the change is larger then min_len, end the previous segment
        if n_change >= min_len:
            new_label_dict['orig_idx_end'] = saved_start-1
            simplified_list.append(new_label_dict)
            labels_list.append(new_label_dict[labelkey])

            new_label = True
            first_label = curr_label[labelkey]
            n_change = 0

    #add last label
    if len(aList) > 0 :
        # For edge case that new label only shows up min_len times at the end
        if new_label:
            new_label_dict = saved_label
            new_label_dict['orig_idx'] = saved_start
        new_label_dict['orig_idx_end'] = i
        simplified_list.append(new_label_dict)
        labels_list.append(new_label_dict[labelkey])

    return simplified_list, labels_list

def find_sequence(aList, aDeduppedList, aSearchList, aListOfSearchSequences, start_end, aStartPos = 0):
    result = []
    i = 0

    #Get the list of labels from the labels object
    aList = aList[list(aList.keys())[0]]

    for i in range(aStartPos, len(aSearchList)):
        for aSearchSequence in aListOfSearchSequences:
            #print("using search sequence: " + str(aSearchSequence))
            #print("compared to: " + str(aSearchList[i:i+len(aSearchSequence)]) )
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

    return result, i, aSearchSequence

def find_pattern(aList, aDeduppedList, aSearchList, aListOfSearchPatterns, pidx, start_end, aStartPos = 0):
    # Pattern index pidx less than 0, search all the patterns
    if pidx < 0:
        aListOfSearchSequences = [seq for aSearchPattern in aListOfSearchPatterns for seq in aSearchPattern['pattern'] ]
        result, i , match = find_sequence(aList, aDeduppedList, aSearchList, aListOfSearchSequences, start_end, aStartPos)
        if len(result):
            matchList = [1 if match in aSearchPattern['pattern'] else 0 for aSearchPattern in aListOfSearchPatterns]
            pidx = matchList.index(1)
            print('----ALL SEARCH, pattern',aListOfSearchSequences, ',match=', match, matchList,pidx)
            return result, i, pidx
        else:
            result = []
            i = -1
            pidx = -1
    # Search Pattern pidx ONLY
    else:
        aListOfSearchSequences = aListOfSearchPatterns[pidx]['pattern']
        result, i, _= find_sequence(aList, aDeduppedList, aSearchList, aListOfSearchSequences, start_end, aStartPos)
    return result, i , pidx


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
        state, last_dic, labels = mre_dataplane.get_segment_state()
        if last_dic == {} or state == None :
            state_time = '0.0'
            pidx = -1
        else:
            state_time = last_dic[state]
            pidx = last_dic['Pidx']
        print("state: ", state, state_time, pidx)

        # Remove duplications in the label list
        labels_dedupped, labels_list = remove_dups_in_list_ml(labels[d_plugin_name], 5)


        print('Dedupped label list to work with:')
        for i, label in enumerate(labels_dedupped):
            print('Label ' + str(i) + ', ' + label['Label'] + ', Start: ' + str(label['Start']) + ', orig_idx: ' + str(label['orig_idx']) + ', orig_idx_end: ' + str(label['orig_idx_end']) )

        start_seq = event['Plugin']['Configuration']['start_seq']
        start_seq = ast.literal_eval(start_seq.strip())
        end_seq = event['Plugin']['Configuration']['end_seq']
        end_seq = ast.literal_eval(end_seq.strip())

        padding_seconds = int(event['Plugin']['Configuration']['padding_seconds'])
        print(start_seq,end_seq,padding_seconds)
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
                    search_from_idx += offset

                print("1 tryin with search_from_idx: " + str(search_from_idx))
                search_results, search_from_idx, pidx =  find_pattern(labels[d_plugin_name], labels_dedupped, labels_list, start_seq, pidx, 'Start', search_from_idx)
                offset = start_seq[pidx]['offset']
                print('1 search_results=',search_results, search_from_idx, pidx)

                if len(search_results) > 0:
                    segment_payload = {} #reset payload
                    segment_payload['Start'] = search_results[0]['Start'] - padding_seconds
                    segment_payload['Pidx'] = pidx
                    state = 'Start' #now look for end
                    have_partial = True
                    print('Start found at ' + str(search_from_idx) + ' with: ' + str(search_results[0]['Start']))
                else:
                    keep_searching = False

            elif state == "Start":
                #look for “End”
                if first_pass:
                    print('first_pass looking for end')
                    offset = end_seq[pidx]['offset']
                    search_from_idx = offset # Move by offset
                    first_pass = False
                else:
                    search_from_idx += offset # Move by offset

                print("2 tryin with search_from_idx: " + str(search_from_idx))
                search_results, search_from_idx, pidx = find_pattern(labels[d_plugin_name], labels_dedupped, labels_list, end_seq, pidx, 'End', search_from_idx)
                offset = end_seq[pidx]['offset']
                print('2 search_results=',search_results, search_from_idx, pidx)

                if len(search_results) > 0:
                    if 'Start' not in segment_payload:
                        segment_payload['Start'] = state_time
                    segment_payload['End'] = search_results[0]['Start'] + padding_seconds
                    segment_payload['Pidx'] = -1
                    results.append(segment_payload)
                    state = 'End' #now look for start
                    have_partial = False
                    pidx = -1 #will search for all patterns in next round
                    print('End found at ' + str(search_from_idx) + ' with: ' + str(search_results[0]['Start']))
                else:
                    keep_searching = False

        if have_partial:
            results.append(segment_payload)  #adding the start without end... maybe next chunk will have it

        logger.info(f'results:{results}')

        if len(results) > 0:
            # Add the results of the plugin to the payload (required if the plugin status is "complete"; Optional if the plugin has any errors)
            mre_outputhelper.add_results_to_output(results)

            # Persist plugin results for later use
            mre_dataplane.save_plugin_results(results)

        # Update the processing status of the plugin (required)
        mre_outputhelper.update_plugin_status(Status.PLUGIN_COMPLETE)


    except Exception as e:
        print(e)

        # Update the processing status of the plugin (required)
        mre_outputhelper.update_plugin_status(Status.PLUGIN_ERROR)

    return mre_outputhelper.get_output_object()
