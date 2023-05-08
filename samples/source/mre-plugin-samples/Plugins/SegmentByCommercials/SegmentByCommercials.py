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
    window_size = event['Plugin']['Configuration']['WINDOW_SIZE']
    threshold_val = event['Plugin']['Configuration']['THRESHOLD_VAL']
    threshold_len = event['Plugin']['Configuration']['THRESHOLD_LEN']
    try:
        #calculate the start and end based on the original chunk time and provided ratio
        chunk_start = event['Input']['Metadata']['HLSSegment']['StartTime']
        chunk_duration = event['Input']['Metadata']['HLSSegment']['Duration']
        chunk_size = event['Profile']['ChunkSize']
        
        #get all detector data since last start or end plus this current chunk
        state, segment, labels = mre_dataplane.get_segment_state()
        start_flag = True
        curr_dur = 0

        durs_sec = [label['Duration'] for label in labels]
        numbers = durs_sec

        
        # Go to next chunk is window size is too small
        if len(numbers) > window_size:
            moving_averages = []
            i = 0
            while i < len(numbers) - window_size + 1:
                this_window = numbers[i : i + window_size]
            
                window_average = sum(this_window) / window_size
                moving_averages.append(float("{:.2f}".format(window_average)))
                i += 1
            print(len(numbers),numbers)

            print(len(moving_averages), moving_averages)
            # # Go to next chunk is window size is too small
            
            if len(moving_averages) > threshold_len:
            #moving_averages = numbers
                idx = 0
                segment_payload = {} 
                have_partial = False
                keep_searching = True
                while keep_searching:
                    ## Looking for start
                    if state is None or state == "End":
                        print(f'----To find start from {idx} {segment_payload}')
                        counter = 0
                        averages = moving_averages[idx:]
                        for aver in averages:
                            idx += 1
                            ## duration > threshold, contents start
                            ## duration < threshold, commercials start
                            if aver > threshold_val:
                                counter += 1
                            else:
                                counter = 0 
                            if counter == threshold_len:
                                beg_idx = idx - threshold_len
                                segment_payload = {} 
                                segment_payload['Start'] = labels[beg_idx]['Start']+1
                                state = 'Start'
                                have_partial = True
                                print(f'Found Start at {idx-1} {aver}, start with {beg_idx} {labels[beg_idx]}')
                                break
                    ## Looking for end
                    elif state == "Start":
                        print(f'----To find end from {idx} {segment_payload}')
                        counter = 0
                        averages = moving_averages[idx:]
                        for aver in averages:
                            idx += 1
                            ## duration < threshold, contents end
                            ## duration > threshold, commercials end
                            if aver < threshold_val:
                                counter += 1
                            else:
                                counter = 0         
                            if counter == threshold_len:
                                beg_idx = idx - threshold_len
                                if 'Start' not in segment_payload:
                                    segment_payload['Start'] = segment[state]
                                segment_payload['End'] = labels[beg_idx]['Start'] + 1
                                results.append(segment_payload)
                                state = 'End'
                                have_partial = False
                                print(f'Found End at {idx-1} {aver}, End with {beg_idx} {labels[beg_idx]}')
                                break
                    
                    if idx == len(moving_averages):        
                        print(f'---Done searching {idx}{len(moving_averages)}')
                        keep_searching = False
                
                if(chunk_size > chunk_duration):
                    #This is the last chunk and end the segment anyways
                    if 'Start' not in segment_payload:
                        segment_payload['Start'] = segment[state]
                    segment_payload['End'] = chunk_start + chunk_duration
                    results.append(segment_payload)
                    state = 'End'
                    have_partial = False
                    
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

