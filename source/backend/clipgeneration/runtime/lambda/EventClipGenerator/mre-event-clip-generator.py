#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import copy
import json
import os
import uuid
import boto3
import urllib3
from datetime import datetime
from botocore.config import Config


MAX_INPUTS_PER_JOB = int(os.environ['MediaConvertMaxInputJobs']) # This can be 150 as per the MediaConvert Quota
OUTPUT_BUCKET = os.environ['OutputBucket'] 
MEDIA_CONVERT_ROLE = os.environ['MediaConvertRole']
EB_EVENT_BUS_NAME = os.environ['EB_EVENT_BUS_NAME']

urllib3.disable_warnings()

ssm = boto3.client('ssm')
eb_client = boto3.client("events")

'''
    Indicates whether a Segment has Optimization Metadata within
'''

#@app.lambda_function()
def GenerateClips(event, context):

    from MediaReplayEnginePluginHelper import DataPlane
    dataplane = DataPlane(event)

    # Contains Job IDs for all the HLS Jobs. We will need to 
    # check if all Jobs have completed before creating the Aggregated
    # m3u8 file
    all_hls_clip_job_ids = []

    # If Segments key not present (In case of Batch Processing), call API to get Segments.
    # For now, we will process every Segment as they are created in Near Real time
    #input_segments = event['Segments']

    optimized_segments = []
    nonoptimized_segments = []
    hls_input_settings_for_segments = []

    audioTrack = 1 if 'TrackNumber' not in event else event['TrackNumber']
    
    input_segments = event
    for segment in input_segments['Segments']:

        # Track Segments which have Optimized Start and End Times
        #if "OptoEnd" in segment and "OptoStart" in segment:
        #    if len(segment['OptoEnd']) > 0 and len(segment['OptoStart']) > 0 :
        #Ignore Starts that have -1 in it
        if "OptoEnd" in segment and "OptoStart" in segment:
            if get_OptoStart(segment, event) != -1:
                optimized_segments.append(segment)
        
        # Original Clips should be generated when asked for.
        if event['GenerateOriginal']:
            if "End" in segment and "Start" in segment:
                #Ignore Starts that have -1 in it
                if segment['Start'] != -1:
                    nonoptimized_segments.append(segment)

    # Create a Optimized Clip for Optimized Segments
    for optsegment in optimized_segments:

        print("--- OPTO SEGMENT PROCESSED-------------")
        print(optsegment['Start'])

        
        chunks = dataplane.get_chunks_for_segment(get_OptoStart(optsegment, event), get_OptoEnd(optsegment, event))
        print('Got Chunks from API based for Optimized Segments)')
        print(f" optimized_segments chunks: {chunks}")
        keyprefix, hls_input_settings = create_optimized_MP4_clips(optsegment, event, chunks)

        # Only if we are dealing with Optimization, we will consider HLS Inputs for Opto Segments.
        if 'Optimizer' in event['Profile']:
            hls_input_settings_for_segments.extend(hls_input_settings)
        

    # A NonOpt Clip needs to be created for every segment
    nonoptimized_segments_with_tracks = []
    for segment in nonoptimized_segments:

        print("--- NON OPTO SEGMENT PROCESSED-------------")
        print(segment['Start'])

        chunks = dataplane.get_chunks_for_segment(segment['Start'], segment['End'])
        print('Got Chunks from API based for NonOptimized Segments)')
        print(f" nonoptimized_segments chunks: {chunks}")
        segs, hls_inputs = create_non_optimized_MP4_clip_per_audio_track(segment, event, chunks)
        nonoptimized_segments_with_tracks.extend(segs)

        # If we are dealing with Optimization, we don't have to consider HLS Inputs for Original Segments.
        # Only when we have no Optimizer configured, we consider HLS Inputs from Original Segments to generate HLS for Original Segs.
        if 'Optimizer' not in event['Profile']:
            hls_input_settings_for_segments.extend(hls_inputs)

    # SAVE ALL NON OPT SEGMENTS PER AUDIO TRACK
    if len(nonoptimized_segments_with_tracks) > 0:  
        print(f"Processed Non Opt Segments before saving - {nonoptimized_segments_with_tracks}")
        dataplane.save_clip_results(nonoptimized_segments_with_tracks)

        detail = {
            "State": "CLIP_GEN_DONE",
            "Event": {
                "EventInfo": event,
                "EventType": "EVENT_CLIP_GEN"
            }
        }
        eb_client.put_events(
            Entries=[
                {
                    "Source": "awsmre",
                    "DetailType": "Clip Gen Status",
                    "Detail": json.dumps(detail),
                    "EventBusName": EB_EVENT_BUS_NAME
                }
            ]
        )


    # For HLS Clips, divide the Entire Segment List to Smaller Chunks to meet the MediaConvert Quota Limits of 150 Inputs per Job
    # We create a MediaConvert Job per segment group (which can have a Max of 150 Inputs configured - build_input_settings)
    
    groups_of_input_settings = [hls_input_settings_for_segments[x:x+MAX_INPUTS_PER_JOB] for x in range(0, len(hls_input_settings_for_segments), MAX_INPUTS_PER_JOB)]
    index = 1
    #batch_id = f"{str(event['Event']['Name']).lower()}-{str(event['Event']['Program']).lower()}"
    batch_id = str(uuid.uuid4())

    #----------- HLS Clips Gen ------------------------------------
    #if audioTrack > 0:

    print("---------------- ALL groups_of_input_settings")
    print(groups_of_input_settings)

    # For Opto segments, AudioTrack would be passed to the Step function
    if 'Optimizer' in event['Profile']:
        print("---- CReating Opto HLS -----------")
        # Launch a Media Convert Job with a Max of 150 Inputs
        for inputsettings in groups_of_input_settings:
            # Each Input setting will have the relevant AudioTrack embedded.
            job = create_HLS_clips(inputsettings, index, batch_id, audioTrack)

            if job != None:
                all_hls_clip_job_ids.append(job['Job']['Id'])
            index += 1
    else:
        # Launch a Media Convert Job with a Max of 150 Inputs
        for inputsettings in groups_of_input_settings:

            # inputsettings for Orig Segments can have multiple audio tracks in it.
            # We need to create a Job per audiotrack to save the HLS Manifests 
            # in S3 at AudioTrack level.
            for track in event['Event']['AudioTracks']:

                final_input_settings = []

                for inputsetting in inputsettings:
                    if int(inputsetting['AudioSelectors']['Audio Selector 1']['Tracks'][0]) == int(track):
                        final_input_settings.append(inputsetting)

                # We have Track specific Input Setting, create the Job
                if len(final_input_settings) > 0:
                    # Each Input setting will have the relevant AudioTrack embedded.
                    job = create_HLS_clips(final_input_settings, index, batch_id, track)

                    if job != None:
                        all_hls_clip_job_ids.append(job['Job']['Id'])
                    index += 1

    #----------- HLS Clips Gen Ends ------------------------------------

    # Persist Output Artifacts generated from MediaConvert Jobs into DDB
    results = []

    for segment in input_segments['Segments']:

        # We are dealing with an Optimized Segment
        if "OptimizedS3KeyPrefix" in segment:
            if "OriginalS3KeyPrefix" in segment:
                results.append({
                    "Start": segment['Start'],
                    "End": segment['End'],
                    "OriginalClipStatus": "Success",
                    "OriginalClipLocation": segment["OriginalS3KeyPrefix"],
                    "OptoStart": get_OptoStart(segment, event),
                    "OptoEnd": get_OptoEnd(segment, event),
                    "OptimizedClipStatus": "Success",
                    "OptimizedClipLocation": segment["OptimizedS3KeyPrefix"],
                    "OptimizedThumbnailLocation": segment["OptimizedThumbnailS3KeyPrefix"],
                    "AudioTrack": audioTrack
                })
            else:
                results.append({
                    "Start": segment['Start'],
                    "End": segment['End'],
                    "OptoStart": get_OptoStart(segment, event),
                    "OptoEnd": get_OptoEnd(segment, event),
                    "OptimizedClipStatus": "Success",
                    "OptimizedClipLocation": segment["OptimizedS3KeyPrefix"],
                    "OptimizedThumbnailLocation": segment["OptimizedThumbnailS3KeyPrefix"],
                    "AudioTrack": audioTrack
                })

        #elif "OriginalS3KeyPrefix" in segment: # We are dealing with an Original Segment

        #     results.append({
        #         "Start": segment['Start'],
        #         "End": segment['End'],
        #         "OriginalClipStatus": "Success" if "OriginalS3KeyPrefix" in segment else "Failure",
        #         "OriginalClipLocation": segment["OriginalS3KeyPrefix"],
        #         "OriginalThumbnailLocation": segment["OriginalThumbnailS3KeyPrefix"]
        #     })

    if len(results) > 0:
        print(f"Processed Segments before saving - {results}")
        dataplane.save_clip_results(results)

        detail = {
            "State": "CLIP_GEN_DONE",
            "Event": {
                "EventInfo": event,
                "EventType": "EVENT_CLIP_GEN"
            }
        }
        eb_client.put_events(
            Entries=[
                {
                    "Source": "awsmre",
                    "DetailType": "Clip Gen Status",
                    "Detail": json.dumps(detail),
                    "EventBusName": EB_EVENT_BUS_NAME
                }
            ]
        )

    # For Opto segments, AudioTrack would be passed to the Step function
    if 'Optimizer' in event['Profile']:
        return {
            "MediaConvertJobs" : all_hls_clip_job_ids,
            "HLSOutputKeyPrefix": f"HLS/{batch_id}/{audioTrack}/",
            "OutputBucket": OUTPUT_BUCKET,
            "Result": results,
            "Event": event['Event'],
            "Input": event['Input']
        }
    else:
        return {
            "MediaConvertJobs" : all_hls_clip_job_ids,
            "OutputBucket": OUTPUT_BUCKET,
            "HLSOutputKeyPrefix": f"HLS/{batch_id}/",
            "Result": results,
            "Event": event['Event'],
            "Input": event['Input']
        }

def get_OptoStart(segment, event):
    audioTrack = 1 if 'TrackNumber' not in event else event['TrackNumber']
    if type(segment['OptoStart']) is dict:
        return segment['OptoStart'][audioTrack]
    else:
        return segment['OptoStart']


def get_OptoEnd(segment, event):
    audioTrack = 1 if 'TrackNumber' not in event else event['TrackNumber']
    if type(segment['OptoEnd']) is dict:
        return segment['OptoEnd'][audioTrack]
    else:
        return segment['OptoEnd']

'''
    Returns the Clip Timings in HH:MM:SS:FF format required for MediaConvert
'''
def get_clip_timings(segment, event, fallbackToDefault=False):

    from MediaReplayEnginePluginHelper import DataPlane
    mre_pluginhelper = DataPlane(event)
    
    
    if not fallbackToDefault:
        if "OptoEnd" in segment and "OptoStart" in segment:
        #if len(segment['OptoEnd']) > 0 and len(segment['OptoStart']) > 0 :
        #if does_segment_have_optimized_times(segment):
            return mre_pluginhelper.get_mediaconvert_clip_format(get_OptoEnd(segment, event)), mre_pluginhelper.get_mediaconvert_clip_format(get_OptoStart(segment, event))
            
        elif "End" in segment and "Start" in segment:
            return mre_pluginhelper.get_mediaconvert_clip_format(segment['End']), mre_pluginhelper.get_mediaconvert_clip_format(segment['Start'])
    else:
            return "00:00:20:00", "00:00:00:00"

def get_start_clip_timings(segment, event):

    from MediaReplayEnginePluginHelper import DataPlane
    mre_pluginhelper = DataPlane(event)

    if "OptoEnd" in segment and "OptoStart" in segment:
    #if len(segment['OptoEnd']) > 0 and len(segment['OptoStart']) > 0 :
    #if does_segment_have_optimized_times(segment):
        return mre_pluginhelper.get_mediaconvert_clip_format(get_OptoStart(segment, event))
        
    elif "End" in segment and "Start" in segment:
        return mre_pluginhelper.get_mediaconvert_clip_format(segment['Start'])

            
def get_end_clip_timings(segment, event):

    from MediaReplayEnginePluginHelper import DataPlane
    mre_pluginhelper = DataPlane(event)

    if "OptoEnd" in segment and "OptoStart" in segment:
    #if len(segment['OptoEnd']) > 0 and len(segment['OptoStart']) > 0 :
    #if does_segment_have_optimized_times(segment):
        return mre_pluginhelper.get_mediaconvert_clip_format(get_OptoEnd(segment, event))
        
    elif "End" in segment and "Start" in segment:
        return mre_pluginhelper.get_mediaconvert_clip_format(segment['End'])



def build_input_settings_for_orig_segment(dataplane, inputs, segment, event):
    
    
    chunks = dataplane.get_chunks_for_segment(segment['Start'], segment['End'])

    # Only chunk , so will have Start and End Clipping time
    if len(chunks) == 1:
        inputClippings = []
        inputClip = {}
        ic = {}

        endtime, starttime = get_clip_timings(segment, event)
        ic['EndTimecode'] = str(endtime)
        ic['StartTimecode'] = str(starttime)

        #If we have a single Chunk we don't need the Endtime Configured if it is less than Start time. Remove it.
        if datetime.strptime(endtime, "%H:%M:%S:%f") < datetime.strptime(starttime, "%H:%M:%S:%f"):
            ic.pop('EndTimecode', None)    

        #ic['EndTimecode'], ic['StartTimecode'] = get_clip_timings(segment, event)
        inputClippings.append(ic)

        inputClip['InputClippings'] = inputClippings
        inputClip['AudioSelectors'] = {
                "Audio Selector 1": {
                    "DefaultSelection": "DEFAULT"
                } 
            }
        inputClip['VideoSelector'] = {}
        inputClip['TimecodeSource'] = "ZEROBASED"
        inputClip['FileInput'] = f"s3://{chunks[0]['S3Bucket']}/{chunks[0]['S3Key']}"
        inputs.append(inputClip)
    elif len(chunks) > 1:
        for chunk_index in range(len(chunks)):
            inputClippings = []
            inputClip = {}
            ic = {}
            if chunk_index == 0:    # First Chunk
                ic['StartTimecode'] = get_start_clip_timings(segment, event)
                inputClippings.append(ic)
                inputClip['InputClippings'] = inputClippings
            elif chunk_index == len(chunks)-1:  # Last Chunk
                ic['EndTimecode'] = get_end_clip_timings(segment, event)
                inputClippings.append(ic)
                inputClip['InputClippings'] = inputClippings
            else:   # Sandwitch Chunks have no clippings
                inputClip['InputClippings'] = []

            
            inputClip['AudioSelectors'] = {
                "Audio Selector 1": {
                    "DefaultSelection": "DEFAULT"
                } 
            }
            inputClip['VideoSelector'] = {}
            inputClip['TimecodeSource'] = "ZEROBASED"
            inputClip['FileInput'] = f"s3://{chunks[chunk_index]['S3Bucket']}/{chunks[chunk_index]['S3Key']}"
            inputs.append(inputClip)


'''
    Sets Inputs for a MediaConvert Job when generating HLS Clips
#   [{
#       "InputClippings": [
#         {
#           "EndTimecode": "00:00:20:00",
#           "StartTimecode": "00:00:00:00"
#         }
#       ],
#       "AudioSelectors": {
#         "Audio Selector 1": {
#           "DefaultSelection": "DEFAULT"
#         }
#       },
#       "VideoSelector": {},
#       "TimecodeSource": "ZEROBASED",
#       "FileInput": "s3://aws-mre-ml-output/MediaLiveOutput/1/Reeu1200927005_1-YS-3min_1_00001.ts"
#   }]
'''

def build_hls_input(segment, event, chunks ,audioTrack):
    
    inputs = []

    # Only chunk, so will have Start and End Clipping time
    if len(chunks) == 1:
        inputClippings = []
        inputClip = {}
        ic = {}

        endtime, starttime = get_clip_timings(segment, event)
        ic['EndTimecode'] = str(endtime)
        ic['StartTimecode'] = str(starttime)

        #If we have a single Chunk we don't need the Endtime Configured if it is less than Start time. Remove it.
        if datetime.strptime(endtime, "%H:%M:%S:%f") < datetime.strptime(starttime, "%H:%M:%S:%f"):
            ic.pop('EndTimecode', None)

        #ic['EndTimecode'], ic['StartTimecode'] = get_clip_timings(segment, event)
        inputClippings.append(ic)
        inputClip['InputClippings'] = inputClippings
       
        #------------- Update MediaConvert AudioSelectors Input -------------

        # Leave the default Input AudioSelectors as is if we are dealing with default Track or only one.
        # If we have multiple AudioTracks, this lambda will be provided with one.
        if int(audioTrack) > 0:
            inputClip['AudioSelectors'] =   {
                                            "Audio Selector 1": {
                                                "Tracks": [
                                                    int(audioTrack)
                                                ],
                                                "DefaultSelection": "NOT_DEFAULT",
                                                "SelectorType": "TRACK"
                                            }
                                        }
        else:
            inputClip['AudioSelectors'] =   {
                                            "Audio Selector 1": {
                                                "DefaultSelection": "DEFAULT"
                                            }
                                        }

        inputClip['AudioSelectorGroups'] =  {
                                                "Audio Selector Group 1": {
                                                    "AudioSelectorNames": [
                                                    "Audio Selector 1"
                                                    ]
                                                }
                                            }
                                            
        #------------- Update MediaConvert AudioSelectors Input Ends -------------
        
        inputClip['VideoSelector'] = {}
        inputClip['TimecodeSource'] = "ZEROBASED"
        inputClip['FileInput'] = f"s3://{chunks[0]['S3Bucket']}/{chunks[0]['S3Key']}"
        inputs.append(inputClip)
    elif len(chunks) > 1:
        for chunk_index in range(len(chunks)):
            ic = {}
            inputClippings = []
            inputClip = {}
            if chunk_index == 0:    # First Chunk
                ic['StartTimecode'] = get_start_clip_timings(segment, event)
                inputClippings.append(ic)
                inputClip['InputClippings'] = inputClippings
            elif chunk_index == len(chunks)-1:  # Last Chunk
                ic['EndTimecode'] = get_end_clip_timings(segment, event)
                inputClippings.append(ic)
                inputClip['InputClippings'] = inputClippings
            else:   # Sandwitch Chunks have no clippings
                inputClip['InputClippings'] = []

            
            #------------- Update MediaConvert AudioSelectors Input -------------

            # Leave the default Input AudioSelectors as is if we are dealing with default Track or only one.
            # If we have multiple AudioTracks, this lambda will be provided with one.
            if int(audioTrack) > 0:
                inputClip['AudioSelectors'] =   {
                                                "Audio Selector 1": {
                                                    "Tracks": [
                                                        int(audioTrack)
                                                    ],
                                                    "DefaultSelection": "NOT_DEFAULT",
                                                    "SelectorType": "TRACK"
                                                }
                                            }
            else:
                inputClip['AudioSelectors'] =   {
                                            "Audio Selector 1": {
                                                "DefaultSelection": "DEFAULT"
                                            }
                                        }
            inputClip['AudioSelectorGroups'] =  {
                                                    "Audio Selector Group 1": {
                                                        "AudioSelectorNames": [
                                                        "Audio Selector 1"
                                                        ]
                                                    }
                                                }
                                                
        #------------- Update MediaConvert AudioSelectors Input Ends -------------
            inputClip['VideoSelector'] = {}
            inputClip['TimecodeSource'] = "ZEROBASED"
            inputClip['FileInput'] = f"s3://{chunks[chunk_index]['S3Bucket']}/{chunks[chunk_index]['S3Key']}"
            inputs.append(inputClip)

    return inputs

def build_input_settings(dataplane, segment_group, event):

    # Check if an AudioTrack has been sent in the event.
    # If yes, set the AudioTrack for extraction in MediaConvert
    # Also use the AudioTrack in the Output video key prefix
    audioTrack = 1 if 'TrackNumber' not in event else event['TrackNumber']

    

    inputs = []
    for segment in segment_group:

        # If a Segment has been Optimized, use the Opt clip timings. If not, fall on back on the Original Clip timings
        # Commenting these Temporarily until the usecase if finalized.

        if "OptoEnd" in segment and "OptoStart" in segment:
            # Check if the Maps have content, if not fall back on Original Segment
            #if len(segment['OptoEnd']) > 0 and len(segment['OptoStart']) > 0 :
        
            #Ignore Starts that have -1 in it
            if get_OptoStart(segment, event) == -1:
                continue

            chunks = dataplane.get_chunks_for_segment(get_OptoStart(segment, event), get_OptoEnd(segment, event))

            # Only chunk, so will have Start and End Clipping time
            if len(chunks) == 1:
                inputClippings = []
                inputClip = {}
                ic = {}

                endtime, starttime = get_clip_timings(segment, event)
                ic['EndTimecode'] = str(endtime)
                ic['StartTimecode'] = str(starttime)

                #If we have a single Chunk we don't need the Endtime Configured if it is less than Start time. Remove it.
                if datetime.strptime(endtime, "%H:%M:%S:%f") < datetime.strptime(starttime, "%H:%M:%S:%f"):
                    ic.pop('EndTimecode', None)

                #ic['EndTimecode'], ic['StartTimecode'] = get_clip_timings(segment, event)
                inputClippings.append(ic)
                inputClip['InputClippings'] = inputClippings
                # inputClip['AudioSelectors'] = {
                #         "Audio Selector 1": {
                #             "DefaultSelection": "DEFAULT"
                #         } 
                #     }

                #------------- Update MediaConvert AudioSelectors Input -------------

                # Leave the default Input AudioSelectors as is if we are dealing with default Track or only one.
                # If we have multiple AudioTracks, this lambda will be provided with one.
                if int(audioTrack) > 0:
                    inputClip['AudioSelectors'] =   {
                                                    "Audio Selector 1": {
                                                        "Tracks": [
                                                            int(audioTrack)
                                                        ],
                                                        "DefaultSelection": "NOT_DEFAULT",
                                                        "SelectorType": "TRACK"
                                                    }
                                                }
                else:
                    inputClip['AudioSelectors'] =   {
                                            "Audio Selector 1": {
                                                "DefaultSelection": "DEFAULT"
                                            }
                                        }
                inputClip['AudioSelectorGroups'] =  {
                                                        "Audio Selector Group 1": {
                                                            "AudioSelectorNames": [
                                                            "Audio Selector 1"
                                                            ]
                                                        }
                                                    }
                                                    
                #------------- Update MediaConvert AudioSelectors Input Ends -------------
                
                inputClip['VideoSelector'] = {}
                inputClip['TimecodeSource'] = "ZEROBASED"
                inputClip['FileInput'] = f"s3://{chunks[0]['S3Bucket']}/{chunks[0]['S3Key']}"
                inputs.append(inputClip)
            elif len(chunks) > 1:
                for chunk_index in range(len(chunks)):
                    ic = {}
                    inputClippings = []
                    inputClip = {}
                    if chunk_index == 0:    # First Chunk
                        ic['StartTimecode'] = get_start_clip_timings(segment, event)
                        inputClippings.append(ic)
                        inputClip['InputClippings'] = inputClippings
                    elif chunk_index == len(chunks)-1:  # Last Chunk
                        ic['EndTimecode'] = get_end_clip_timings(segment, event)
                        inputClippings.append(ic)
                        inputClip['InputClippings'] = inputClippings
                    else:   # Sandwitch Chunks have no clippings
                        inputClip['InputClippings'] = []

                    
                    #------------- Update MediaConvert AudioSelectors Input -------------

                    # Leave the default Input AudioSelectors as is if we are dealing with default Track or only one.
                    # If we have multiple AudioTracks, this lambda will be provided with one.
                    if int(audioTrack) > 0:
                        inputClip['AudioSelectors'] =   {
                                                        "Audio Selector 1": {
                                                            "Tracks": [
                                                                int(audioTrack)
                                                            ],
                                                            "DefaultSelection": "NOT_DEFAULT",
                                                            "SelectorType": "TRACK"
                                                        }
                                                    }
                    else:
                        inputClip['AudioSelectors'] =   {
                                            "Audio Selector 1": {
                                                "DefaultSelection": "DEFAULT"
                                            }
                                        }
                    inputClip['AudioSelectorGroups'] =  {
                                                            "Audio Selector Group 1": {
                                                                "AudioSelectorNames": [
                                                                "Audio Selector 1"
                                                                ]
                                                            }
                                                        }
                                                        
                #------------- Update MediaConvert AudioSelectors Input Ends -------------
                    inputClip['VideoSelector'] = {}
                    inputClip['TimecodeSource'] = "ZEROBASED"
                    inputClip['FileInput'] = f"s3://{chunks[chunk_index]['S3Bucket']}/{chunks[chunk_index]['S3Key']}"
                    inputs.append(inputClip)
    

        
        # elif "End" in segment and "Start" in segment and event['GenerateOriginal']:
        
        #         #Ignore Starts that have -1 in it
        #         if segment['Start'] == -1:
        #             continue
                
        #         build_input_settings_for_orig_segment(dataplane, inputs, segment, event)
                

            
    return inputs

def create_optimized_MP4_clips(segment, event, chunks):

    hls_input_setting = []

    try:
        job_settings_filename = os.path.join(os.path.dirname(__file__), 'job_settings_mp4.json')

        with open(job_settings_filename) as json_data:
            jobSettings = json.load(json_data)

        
        # Check if an AudioTrack has been sent in the event.
        # If yes, set the AudioTrack for extraction in MediaConvert
        # Also use the AudioTrack in the Output video key prefix
        audioTrack = 1 if 'TrackNumber' not in event else event['TrackNumber']

        hls_input_setting = build_hls_input(segment, event, chunks ,audioTrack)

        #------------- Update MediaConvert AudioSelectors Input -------------

        # Leave the default Input AudioSelectors as is if we are dealing with default Track or only one.
        # If we have multiple AudioTracks, this lambda will be provided with one.
        if int(audioTrack) > 0:
            jobSettings['Inputs'][0]['AudioSelectors'] = {
                                                            "Audio Selector 1": {
                                                                "Tracks": [
                                                                    int(audioTrack)
                                                                ],
                                                                "DefaultSelection": "NOT_DEFAULT",
                                                                "SelectorType": "TRACK"
                                                            }
                                                        }
        else:
            jobSettings['Inputs'][0]['AudioSelectors'] =   {
                                "Audio Selector 1": {
                                    "DefaultSelection": "DEFAULT"
                                }
                            }

            jobSettings['Inputs'][0]['AudioSelectorGroups'] =   {
                                                                    "Audio Selector Group 1": {
                                                                        "AudioSelectorNames": [
                                                                        "Audio Selector 1"
                                                                        ]
                                                                    }
                                                                }
        #------------- Update MediaConvert AudioSelectors Input Ends -------------

        runid = str(uuid.uuid4())

        # Get the Corresponding OptoStart and OptoEnd timings based on audio track in the Map
        keyprefix = f"optimized_assets/{runid}/MP4/{str(audioTrack)}/{str(get_OptoStart(segment, event)).replace('.',':')}-{str(get_OptoEnd(segment, event)).replace('.',':')}"
        job_output_destination = f"s3://{OUTPUT_BUCKET}/{keyprefix}"

        jobSettings["OutputGroups"][0]["OutputGroupSettings"]["FileGroupSettings"]["Destination"] = job_output_destination

        # We use the first index in the Map of OptoStart and OptoEnd for Thumbnail since we only need one thumbnail and is not depending on number of audio tracks
        thumbnail_keyprefix = f"thumbnail/{runid}/{str(get_OptoStart(segment, event)).replace('.',':')}-{str(get_OptoEnd(segment, event)).replace('.',':')}"
        thumbnail_job_output_destination = f"s3://{OUTPUT_BUCKET}/{thumbnail_keyprefix}"
        jobSettings["OutputGroups"][1]["OutputGroupSettings"]["FileGroupSettings"]["Destination"] = thumbnail_job_output_destination

        # Input should be based on the Number of chunks. A Segment timing can constitute multiple chunks
        # If only one Chunk found, then we create one Input for the MediaConvert Job 
        # If more than on Chunk, create as many Inputs and set the InputClippings Accordingly.
        # Inputclippings will be assigned as follows
        # When #Chunks > 1 , 1st Chunk - StartTime = Segment.OptoStart, EndTime = Empty
        # When #Chunks > 1 , 2nd Chunk - StartTime = Empty, EndTime = empty
        # When #Chunks > 1 , 3rd Chunk - StartTime = Empty, EndTime = Segment.OptoEnd
        print(f"we got {len(chunks)} number of chunks")
        if len(chunks) == 1:
            # Update the job settings with the source video from the S3 event and destination 
            input_segment_location = f"s3://{chunks[0]['S3Bucket']}/{chunks[0]['S3Key']}"
            jobSettings['Inputs'][0]['FileInput'] = input_segment_location

            print("Only one Chunk found .. Clip Timings is")
            if "OptoEnd" in segment and "OptoStart" in segment:
            #if len(segment['OptoEnd']) > 0 and len(segment['OptoStart']) > 0 :
            #if does_segment_have_optimized_times(segment):
                if type(segment['OptoEnd']) is dict:
                    print(f"Segment OptoEnd is {segment['OptoEnd'][audioTrack]}")
                else:
                    print(f"Segment OptoEnd is {segment['OptoEnd']}")
            
                if type(segment['OptoStart']) is dict:
                    print(f"Segment OptoStart is {segment['OptoStart'][audioTrack]}")
                else:
                    print(f"Segment OptoStart is {segment['OptoStart']}")

            print(f"Here are the modified Clip Timings when Total chunks = 1")
            print(get_clip_timings(segment, event))

            endtime, starttime = get_clip_timings(segment, event)
            jobSettings['Inputs'][0]['InputClippings'][0]['EndTimecode'] = str(endtime)
            jobSettings['Inputs'][0]['InputClippings'][0]['StartTimecode'] = str(starttime)

            #If we have a single Chunk we don't need the Endtime Configured if it is less than Start time. Remove it.
            if datetime.strptime(endtime, "%H:%M:%S:%f") < datetime.strptime(starttime, "%H:%M:%S:%f"):
                jobSettings['Inputs'][0]['InputClippings'][0].pop('EndTimecode', None)    

            #jobSettings['Inputs'][0]['InputClippings'][0]['EndTimecode'], jobSettings['Inputs'][0]['InputClippings'][0]['StartTimecode'] = get_clip_timings(segment, event)

            #If we have a single Chunk we don't need the Endtime Configured. Remove it.
            #jobSettings['Inputs'][0]['InputClippings'][0].pop('EndTimecode', None)

            print("Single Chunk processed .. JobSettings is ...")
            print(json.dumps(jobSettings))

            # Convert the video using AWS Elemental MediaConvert
            jobid = str(uuid.uuid4())
            jobMetadata = {'JobId': jobid}
            create_job(jobMetadata, jobSettings)
            
        elif len(chunks) > 1:
            for chunk_index in range(len(chunks)):
                
                input_segment_location = f"s3://{chunks[chunk_index]['S3Bucket']}/{chunks[chunk_index]['S3Key']}"
                    
                if chunk_index == 0:    # First Chunk
                    print(f"Chunk index is {chunk_index}")
                    jobSettings['Inputs'][0]['FileInput'] = input_segment_location
                    jobSettings['Inputs'][0]['InputClippings'][0]['StartTimecode'] = get_start_clip_timings(segment, event)
                    jobSettings['Inputs'][0]['InputClippings'][0].pop('EndTimecode', None)

                    print(f"First chunk processing ... Job Setting is")
                    print(json.dumps(jobSettings))
                elif chunk_index == len(chunks)-1:  # Last Chunk

                    print(f"Chunk index is {chunk_index}")
                    jobSettings['Inputs'].append(copy.deepcopy(jobSettings['Inputs'][0]))   #Clone the existing InputSettings and add it to the Inputs Key
                    jobSettings['Inputs'][chunk_index]['FileInput'] = input_segment_location
                    jobSettings['Inputs'][chunk_index]['InputClippings'][0].pop('StartTimecode', None)
                    jobSettings['Inputs'][chunk_index]['InputClippings'][0]['EndTimecode'] = get_end_clip_timings(segment, event)

                    print(f"Last chunk processing ... Job Setting is")
                    print(json.dumps(jobSettings))
                else:   #in between chunks
                    print(f"Chunk index is {chunk_index}")
                    jobSettings['Inputs'].append(copy.deepcopy(jobSettings['Inputs'][0]))
                    jobSettings['Inputs'][chunk_index]['FileInput'] = input_segment_location
                    jobSettings['Inputs'][chunk_index]['InputClippings']= []   # No need to Clip for sandwitched Chunks
                    print(f"Sandwitch chunk processing ... Job Setting is")
                    print(json.dumps(jobSettings))

            # Convert the video using AWS Elemental MediaConvert
            jobid = str(uuid.uuid4())
            jobMetadata = { 'JobId': jobid }
            create_job(jobMetadata, jobSettings)

        # Update the Segment with the S3KeyPrefix
        segment['OptimizedS3KeyPrefix'] = f"{job_output_destination}.mp4"
        segment['OptimizedThumbnailS3KeyPrefix'] = f"{thumbnail_job_output_destination}.0000000.jpg"

        #print(json.dumps(jobSettings))

    except Exception as e:
        print ('Exception: %s' % e)
        raise
    
    return keyprefix, hls_input_setting

def create_job(jobMetadata, jobSettings):

    # get the account-specific mediaconvert endpoint for this region
    endpoint = ssm.get_parameter(Name='/MRE/ClipGen/MediaConvertEndpoint', WithDecryption=False)['Parameter']['Value'] 

    # Customizing Exponential backoff
    # Retries with additional client side throttling.
    boto_config = Config(
        retries = {
            'max_attempts': 10,
            'mode': 'adaptive'
        }
    )
    # add the account-specific endpoint to the client session 
    client = boto3.client('mediaconvert', config=boto_config, endpoint_url=endpoint, verify=False)
    
    return client.create_job(Role=MEDIA_CONVERT_ROLE, UserMetadata=jobMetadata, Settings=jobSettings)


def create_non_optimized_MP4_clip_per_audio_track(segment, event, chunks):
    audiotracks = event['Event']['AudioTracks']
    segments = []
    hls_inputs = []
    for track in audiotracks:
        seg, hls_input = create_non_optimized_MP4_clips(segment, event, chunks, int(track))
        segments.append(seg)
        hls_inputs.extend(hls_input)
    
    return segments, hls_inputs


def is_end_time_less_than_start_time(endtime, starttime):
    end = endtime.split(':')
    start = starttime.split(':')
    if int(end[0]) > int(start[0]) or int(end[1]) > int(start[1]) or int(end[2]) > int(start[2]) or int(end[3]) > int(start[3]):
        return False
    
    return True

def create_non_optimized_MP4_clips(segment, event, chunks, audioTrack):
    hls_input = []

    try:
        
        job_settings_filename = os.path.join(os.path.dirname(__file__), 'job_settings_mp4.json')
                
        with open(job_settings_filename) as json_data:
            jobSettings = json.load(json_data)

        hls_input = build_hls_input(segment, event, chunks ,audioTrack)
        
        #------------- Update MediaConvert AudioSelectors Input -------------

        # Leave the default Input AudioSelectors as is if we are dealing with default Track or only one.
        # If we have multiple AudioTracks, this lambda will be provided with one.

        jobSettings['Inputs'][0]['AudioSelectors'] = {
                                                        "Audio Selector 1": {
                                                            "Tracks": [
                                                                audioTrack
                                                            ],
                                                            "DefaultSelection": "NOT_DEFAULT",
                                                            "SelectorType": "TRACK"
                                                        }
                                                    }

        jobSettings['Inputs'][0]['AudioSelectorGroups'] =   {
                                                                "Audio Selector Group 1": {
                                                                    "AudioSelectorNames": [
                                                                    "Audio Selector 1"
                                                                    ]
                                                                }
                                                            }
        #------------- Update MediaConvert AudioSelectors Input Ends -------------    

        # Overrides to Job settings
        runid = str(uuid.uuid4())
        keyprefix = f"nonoptimized_assets/{runid}/MP4/{str(audioTrack)}/{str(segment['Start']).replace('.',':')}-{str(segment['End']).replace('.',':')}"

        job_output_destination = f"s3://{OUTPUT_BUCKET}/{keyprefix}"
        
        jobSettings["OutputGroups"][0]["OutputGroupSettings"]["FileGroupSettings"]["Destination"] = job_output_destination

        thumbnail_keyprefix = f"thumbnail/{runid}/{str(segment['Start']).replace('.',':')}-{str(segment['End']).replace('.',':')}"
        thumbnail_job_output_destination = f"s3://{OUTPUT_BUCKET}/{thumbnail_keyprefix}"
        jobSettings["OutputGroups"][1]["OutputGroupSettings"]["FileGroupSettings"]["Destination"] = thumbnail_job_output_destination

        # Input should be based on the Number of chunks. A Segment timming can constitute multiple chunks
        # If only one Chunk found, then we create one Input for the MediaConvert Job 
        # If more than on Chunk, create as many Inputs and set the InputClippings Accordingly.
        # Inputclippings will be assigned as follows
        # When #Chunks > 1 , 1st Chunk - StartTime = Segment.OptoStart, EndTime = Empty
        # When #Chunks > 1 , 2nd Chunk - StartTime = Empty, EndTime = empty
        # When #Chunks > 1 , 3rd Chunk - StartTime = Empty, EndTime = Segment.OptoEnd
        print(f"we got {len(chunks)} number of chunks")
        if len(chunks) == 1:
            # Update the job settings with the source video from the S3 event and destination 
            input_segment_location = f"s3://{chunks[0]['S3Bucket']}/{chunks[0]['S3Key']}"
            jobSettings['Inputs'][0]['FileInput'] = input_segment_location

            endtime, starttime = get_clip_timings(segment, event)
            jobSettings['Inputs'][0]['InputClippings'][0]['EndTimecode'] = str(endtime)
            jobSettings['Inputs'][0]['InputClippings'][0]['StartTimecode'] = str(starttime)

            #If we have a single Chunk we don't need the Endtime Configured if it is less than Start time. Remove it.
            if datetime.strptime(endtime, "%H:%M:%S:%f") < datetime.strptime(starttime, "%H:%M:%S:%f"):
                jobSettings['Inputs'][0]['InputClippings'][0].pop('EndTimecode', None)
            
            #jobSettings['Inputs'][0]['InputClippings'][0]['EndTimecode'], jobSettings['Inputs'][0]['InputClippings'][0]['StartTimecode'] = get_clip_timings(segment, event)

            #print(f"IGNORED EndTime from helper function = {jobSettings['Inputs'][0]['InputClippings'][0]['EndTimecode']}")
            #print(f"StartTime from helper function = {jobSettings['Inputs'][0]['InputClippings'][0]['StartTimecode']}")

            

            # Convert the video using AWS Elemental MediaConvert
            jobid = str(uuid.uuid4())
            jobMetadata = {'JobId': jobid}
            create_job(jobMetadata, jobSettings)
            
        elif len(chunks) > 1:
            for chunk_index in range(len(chunks)):
                
                input_segment_location = f"s3://{chunks[chunk_index]['S3Bucket']}/{chunks[chunk_index]['S3Key']}"
                    
                if chunk_index == 0:    # First Chunk
                    jobSettings['Inputs'][0]['FileInput'] = input_segment_location
                    jobSettings['Inputs'][0]['InputClippings'][0]['StartTimecode'] = get_start_clip_timings(segment, event)
                    jobSettings['Inputs'][0]['InputClippings'][0].pop('EndTimecode', None)
                elif chunk_index == len(chunks)-1:  # Last Chunk
                    jobSettings['Inputs'].append(copy.deepcopy(jobSettings['Inputs'][0]))   #Clone the existing InputSettings and add it to the Inputs Key
                    jobSettings['Inputs'][chunk_index]['FileInput'] = input_segment_location
                    jobSettings['Inputs'][chunk_index]['InputClippings'][0].pop('StartTimecode', None)
                    jobSettings['Inputs'][chunk_index]['InputClippings'][0]['EndTimecode'] = get_end_clip_timings(segment, event)
                else:   #in between chunks
                    jobSettings['Inputs'].append(copy.deepcopy(jobSettings['Inputs'][0]))
                    jobSettings['Inputs'][chunk_index]['FileInput'] = input_segment_location
                    jobSettings['Inputs'][chunk_index]['InputClippings']= []   # No need to Clip for sandwitched Chunks
                    

            # Convert the video using AWS Elemental MediaConvert
            jobid = str(uuid.uuid4())
            jobMetadata = { 'JobId': jobid }
            create_job(jobMetadata, jobSettings)
        
    except Exception as e:
        print ('Exception: %s' % e)
        raise

    return {
            "Start": segment['Start'],
            "End": segment['End'],
            "OriginalClipStatus": "Success",
            "OriginalClipLocation": f"{job_output_destination}.mp4",
            "OriginalThumbnailLocation": f"{thumbnail_job_output_destination}.0000000.jpg",
            "AudioTrack": audioTrack
        }, hls_input

def create_HLS_clips(inputSettings, index, batch_id, audioTrack):

    if len(inputSettings) == 0:
        return None
    unqid = str(uuid.uuid4())
    try:
        
        job_settings_filename = os.path.join(os.path.dirname(__file__), 'job_settings_hls.json')
                
        with open(job_settings_filename) as json_data:
            jobSettings = json.load(json_data)
            
        job_output_destination = f"s3://{OUTPUT_BUCKET}/HLS/{batch_id}/{audioTrack}/"
        
        jobSettings["OutputGroups"][0]["OutputGroupSettings"]["HlsGroupSettings"]["Destination"] = job_output_destination
        
        jobSettings["OutputGroups"][0]['Outputs'][0]["NameModifier"] = f"Part-{unqid}"

        jobSettings["OutputGroups"][0]["OutputGroupSettings"]["HlsGroupSettings"]["AdditionalManifests"] =  [{
                                                                                                                "ManifestNameModifier": f"Batch-{unqid}",
                                                                                                                "SelectedOutputs": [
                                                                                                                        f"Part-{unqid}"
                                                                                                                    ]
                                                                                                            }]
        
        jobSettings['Inputs'] = inputSettings

        # Convert the video using AWS Elemental MediaConvert
        jobMetadata = { 'BatchId': batch_id }

        return create_job(jobMetadata, jobSettings)

    except Exception as e:
        print ('Exception: %s' % e)
        raise
