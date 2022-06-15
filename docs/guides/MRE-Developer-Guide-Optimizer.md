[![Header](../assets/images/mre-header-1.png)](../../MRE-Developer-Guide.md)

# Developers Guide - Optimizer Plugin

Reasons you may want to optimize your segments are:

- Remove short duration scene changes (flicker frames) at the start or end of the segment
- Avoid interupting a person (announcer) speaking at the very beginning or ending of the segment
- Padding the segment by a set amount

The Lambda code sample below contains a general purpose optimizer plugin example that attempts to extend the segment length based on the dependent featurer plugin results. This can be used with a plugin that uses FFMPEG for example to detect silence or scene changes. You could also use Amazon Transcribe to detect speech and look for breaks in conversation. Whatever the data is that you want to use with this opto plugin, it should be gathered using one or more featurer plugins registered as dependencies.  

```
import json
import boto3
from botocore.exceptions import ClientError

from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import PluginHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane


def optimize_segment(segment_mark, segment_type, detectors, config, max_search_window_sec):
    opto_segment_mark = segment_mark
    status = False

    result = {}

    print (f'Segment {segment_type} at:', str(segment_mark))
    print('Dependent Plugin(s) config:', config)

    #loop through all dependent detectors
    for detector in detectors:
        print('Dependent detector:', detector)
        detector_name = detector['DependentDetector']
        bias = config[detector_name]['bias'] #'safe range', 'unsafe range'
        print('Detector bias: ' + bias)

        if segment_type in detector:
            #loop through all the data for the respective detector
            for detection in detector[segment_type]:
                print('Detection starting at ' + str(detection['Start']) + ' ending at ' + str(detection['End']))

                if bias == 'safe range':
                    if detection['Start'] <= segment_mark <= detection['End']:
                        print('already in safe range')
                        
                        if not status:
                            status = True

                    else: # not in a good range, attempt to move it
                        if status:
                            print("already optimized. exiting the loop")
                            break
                    
                        print('segment_mark: ' + str(segment_mark) + '  detection_start: ' + str(detection['Start']))
                        
                        if segment_type == 'Start':
                            if abs(detection['Start'] - segment_mark) > max_search_window_sec:
                                opto_segment_mark = segment_mark - max_search_window_sec
                                print('adjusted but limited by max window')
                                status = True
                            else:
                                opto_segment_mark = detection['Start']
                                print('adjusted to start edge of range')
                                status = True

                        else: #end processing
                            if abs(detection['End'] - segment_mark) > max_search_window_sec:
                                opto_segment_mark = segment_mark + max_search_window_sec
                                print('adjusted but limited by max window')
                                status = True
                            else:
                                opto_segment_mark = detection['End']
                                print('adjusted to end edge of range')
                                status = True
                        
                    print("Opto segment mark:", opto_segment_mark)

                elif bias == 'unsafe range': 
                    if detection['Start'] <= segment_mark <= detection['End']: # not in a good range, attempt to move it
                        if status:
                            print("already optimized. exiting the loop")
                            break
                        
                        if segment_type == 'Start':
                            if abs(detection['Start'] - segment_mark) > max_search_window_sec:
                                opto_segment_mark = segment_mark - max_search_window_sec
                                print('adjusted but limited by max window')
                                status = True
                            else:
                                opto_segment_mark = detection['Start']
                                print('adjusted to start edge of range')
                                status = True

                        else: #end processing
                            if abs(detection['End'] - segment_mark) > max_search_window_sec:
                                opto_segment_mark = segment_mark + max_search_window_sec
                                print('adjusted but limited by max window')
                                status = True
                            else:
                                opto_segment_mark = detection['End']
                                print('adjusted to end edge of range')
                                status = True
                    
                    else: # in a good range
                        print('already in safe range')
                        
                        if not status:
                            status = True
                            
                    print("Opto segment mark:", opto_segment_mark)

        else:
            print(f'No {segment_type} found in detector')

    result['Opto' + segment_type] = opto_segment_mark

    return result, status


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

        #this input parameter needs to be configured as part of the MRE plugin registration process
        optimization_search_window_sec = float(plugin_config['optimization_search_window_sec'])

        #Check if this plugin has dependencies and if so, get their respective configuration details
        dep_plugin_config = mre_pluginhelper.get_dependent_plugins_configuration()
        print('Dependent plugins config:\n', dep_plugin_config)

        #get all pending segments to be optimized and detector data within that time range plus the search window buffer time
        segments = mre_dataplane.get_segment_state_for_optimization(search_window_sec=optimization_search_window_sec)
        print('get_segment_state_for_optimization:\n', segments)

        for segment in segments:
            print('Next segment to optimize')
            new_result = {}
            
            #ignore incomplete segments that only have a start. We know that because the end is set temporarily to that of the start
            if 'End' in segment['Segment'] and segment['Segment']['Start'] != segment['Segment']['End']:
                #check opto status of the segment and only process those that have not been attempted
                if 'OptoStart' not in segment:
                    segment_type = 'Start'
                    print(segment_type + ' part of segment to optimize')
                    result, status = optimize_segment(segment['Segment'][segment_type], segment_type, segment['DependentDetectorsOutput'], dep_plugin_config, optimization_search_window_sec)
                    print(status)

                    new_result['Start'] = segment['Segment']['Start']
                    new_result['End'] = segment['Segment']['End']
                    new_result['OptoStart'] = result['OptoStart']

                    if status:
                        new_result['OptoStartCode'] = 'Opto succeeded'
                    else:
                        new_result['OptoStartCode'] = 'Unsuccessful'


                if 'OptoEnd' not in segment:
                    segment_type = 'End'
                    print(segment_type + ' part of segment to optimize')
                    result, status = optimize_segment(segment['Segment'][segment_type], segment_type, segment['DependentDetectorsOutput'], dep_plugin_config, optimization_search_window_sec)
                    print(status)

                    new_result['Start'] = segment['Segment']['Start']
                    new_result['End'] = segment['Segment']['End']
                    new_result['OptoEnd'] = result['OptoEnd']

                    if status:
                        new_result['OptoEndCode'] = 'Opto succeeded'
                    else:
                        new_result['OptoEndCode'] = 'Unsuccessful'

            if new_result:
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

```
