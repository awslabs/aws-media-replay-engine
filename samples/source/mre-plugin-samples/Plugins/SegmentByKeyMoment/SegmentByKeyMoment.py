# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import PluginHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane
    
def DetectKeyMoment_check(labels, chunk_time):
    for item in labels: #'Label': 'score-change'
        if int(item['Start']) == chunk_time:
            return True
    return False

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
        chunk_to_segment_ratio = 1 #float(event['Plugin']['Configuration']['chunk_to_segment_ratio'])

        #calculate the start and end based on the original chunk time and provided ratio
        chunk_start = event['Input']['Metadata']['HLSSegment']['StartTime']
        duration = event['Input']['Metadata']['HLSSegment']['Duration']
        chunk_end = chunk_start + duration
        
        #get all detector data since last start or end plus this current chunk
        state, segment, labels = mre_dataplane.get_segment_state()
        print("state: ", str(state))
        print("segment: ", segment)
        print("labels: ", labels)

        segment_end = 0
        desired_clip_length = 30 #or make a parameter
        buffer_time = int((float(desired_clip_length)/2)) #assumes equal weighting before/after the key moment
        
        open_segment = False
        close_segment = False
        last_segment_end = None
        
        #payload for a se
        result = {}

        for chunk_time in range(int(chunk_start), int(chunk_start+duration)):
            print(chunk_time)
            found_keymoment = False
            
            for label in labels:
                if DetectKeyMoment_check(labels[label], chunk_time):
                    result[label] = True
                    found_keymoment = True
                    
            #optionally add other dependent detector data to consider for other key moments            
                
            #when a key moment is found (like a score change), start a new segment or add to an existing open one
            if found_keymoment:
                if not open_segment:
                    #start a new segment
                    print("start new segment")
                    
                    #the start of the segment will be padded
                    segment_start = max(chunk_time - buffer_time, 0)
                    
                    #overlaping segments are not preferred, adjust the start if needed
                    if last_segment_end:
                        if segment_start < last_segment_end:
                            segment_start = last_segment_end 
                        
                    #the end of the segment will be padded    
                    segment_end = min(chunk_end, chunk_time + buffer_time)
                    last_segment_end = segment_end
                    
                    #result = {} 
                    result["Start"] = float(segment_start)
                    result["End"] = float(segment_end)
                    #other output attributes are set above when the key moment was found
                    open_segment = True
                
                elif chunk_time > segment_end:
                    #close the segment, its length meets the desired duration
                    close_segment = True
                
            if close_segment:
                print(result)
                results.append(result)
                close_segment = False
                open_segment = False
                
                #reset for next key moment that may exist in this chunk
                result = {}
        
        #close any remaining segments and append to results
        if open_segment:
            print(result)
            results.append(result)
            close_segment = False
            open_segment = False
                
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
