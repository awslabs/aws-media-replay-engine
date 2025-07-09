#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import copy
import json
import math
import os
import uuid
from datetime import datetime

import boto3
import ffmpeg
import urllib3
from aws_lambda_powertools import Logger
from botocore.config import Config
from MediaReplayEnginePluginHelper import DataPlane

logger = Logger()

MAX_INPUTS_PER_JOB = int(os.environ['MediaConvertMaxInputJobs']) # This can be 150 as per the MediaConvert Quota
OUTPUT_BUCKET = os.environ['OutputBucket'] 
MEDIA_CONVERT_ROLE = os.environ['MediaConvertRole']
EB_EVENT_BUS_NAME = os.environ['EB_EVENT_BUS_NAME']
MEDIA_CONVERT_ENDPOINT = os.environ['MEDIA_CONVERT_ENDPOINT']

urllib3.disable_warnings()

ssm = boto3.client('ssm')
eb_client = boto3.client("events")



s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')
    
def generate_thumbnail_image(chunk_bucket, chunk_key):
   
    # Create the Temp Dir for Frame Grabs
    input_chunk_video_dir = "/tmp/video"
    output_dir = "/tmp/imgs"

    temp_image_file_name = f"{str(uuid.uuid4())}"
    logger.info(f"temp_image_file_name={temp_image_file_name}")

    if not os.path.exists(input_chunk_video_dir):
        os.makedirs(input_chunk_video_dir)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    logger.info(f"chunk_bucket={chunk_bucket}")
    logger.info(f"chunk_key={chunk_key}")

    try:
        s3_resource.Bucket(chunk_bucket).download_file(chunk_key, f"{input_chunk_video_dir}/{temp_image_file_name}.ts")
    except Exception as e:
        print("ERROR")
        raise
    
    for f in os.listdir(input_chunk_video_dir):
        logger.info(f"TS Downloaded file: {f}")

    # Get Video Duration
    probe = ffmpeg.probe(f"{input_chunk_video_dir}/{temp_image_file_name}.ts", select_streams="v:0")
    duration = float(probe['format']['duration'])

    logger.info(f"duration={duration}")
    
    # Calculate the timestamp for the center frame
    center_timestamp = duration / 2
    # Extract the center frame as a JPEG image
    (
        ffmpeg
        .input(f"{input_chunk_video_dir}/{temp_image_file_name}.ts", ss=math.floor(center_timestamp))
        .filter('scale', 1920, -1)
        .output(f"{output_dir}/{temp_image_file_name}.jpeg", vframes=1)
        .run()
    )

    for f in os.listdir(output_dir):
        logger.info(f"Image file created: {f}")

    # Upload Thumbnail image to S3
    thumbnail_key_prefix = f"thumbnail/{str(uuid.uuid4())}/{str(uuid.uuid4())}.jpeg"
    thumbnail_job_output_destination = f"s3://{OUTPUT_BUCKET}/{thumbnail_key_prefix}"
    
    s3_client.upload_file(f"{output_dir}/{temp_image_file_name}.jpeg", OUTPUT_BUCKET, thumbnail_key_prefix)
    
    return thumbnail_job_output_destination

def should_generate_original_clips(event) -> bool:
    return event['Event']['GenerateOrigClips']

def should_generate_original_thumbnails(event) -> bool:
    return event['Event']['GenerateOrigThumbNails']

def should_generate_optimized_thumbnails(event) -> bool:
    return event['Event']['GenerateOptoThumbNails']

def should_generate_optimized_clips(event) -> bool:
    return event['Event']['GenerateOptoClips']


def get_original_segment_dict(segment, audioTrack):
    return {
        "Start": segment['Start'],
        "End": segment['End'],
        "OriginalClipStatus": "Success",
        "OriginalClipLocation": "",
        "OriginalThumbnailLocation": "",
        "AudioTrack": audioTrack
    }

def get_all_original_optimized_segments(event):
    optimized_segments = []
    non_optimized_segments = []

    for segment in event['Segments']:
        if "OptoEnd" in segment and "OptoStart" in segment:
            #Ignore OptoStarts that have -1 in it
            if get_OptoStart(segment, event) != -1:
                optimized_segments.append(segment)
        
        # Original Clips should be generated when asked for.
        if event['GenerateOriginal']:
            if "End" in segment and "Start" in segment:
                #Ignore Starts that have -1 in it
                if segment['Start'] != -1:
                    non_optimized_segments.append(segment)
    
    return optimized_segments, non_optimized_segments

def build_opto_hls_settings(optimized_segments, dataplane, event):
    hls_input_settings_for_segments = []
    for optsegment in optimized_segments:
        opto_start, opto_end = get_OptoStart(optsegment, event), get_OptoEnd(optsegment, event)
        chunks = dataplane.get_chunks_for_segment(opto_start, opto_end)
        audioTrack = 1 if 'TrackNumber' not in event else event['TrackNumber']
        hls_input_setting = build_hls_input(dataplane, optsegment, event, chunks ,audioTrack)
        hls_input_settings_for_segments.extend(hls_input_setting)
    return hls_input_settings_for_segments


def build_orig_hls_settings(original_segments, dataplane, event):
    # A NonOpt Clip needs to be created for every segment
    hls_inputs = []
    for segment in original_segments:
        chunks = dataplane.get_chunks_for_segment(segment['Start'], segment['End'])
        audiotracks = event['Event']['AudioTracks']
        for track in audiotracks:
            hls_input = build_hls_input(dataplane, segment, event, chunks, track)
            hls_inputs.extend(hls_input)

    return hls_inputs


def process_optimized_segments(optimized_segments, dataplane, event):
    #hls_input_settings_for_segments = []
    media_convert_job_ids = []
    for optsegment in optimized_segments:

        logger.info("--- Processing Optimized segments -------------")
        logger.info(f"optsegment['Start'] = {optsegment['Start']}")

        opto_start, opto_end = get_OptoStart(optsegment, event), get_OptoEnd(optsegment, event)

        chunks = dataplane.get_chunks_for_segment(opto_start, opto_end)
        logger.info('Got Chunks from API based for Optimized Segment)')
        logger.info(f" optimized_segments chunks: {chunks}")
        logger.info(f"opto_start={opto_start}")
        logger.info(f"opto_end={opto_end}")

        job_ids  = create_optimized_MP4_clips(dataplane, optsegment, event, chunks)
        media_convert_job_ids.extend(job_ids)

       
    return media_convert_job_ids


def update_job_status(event, context):
    '''
        This Handler is Invoked by EventBridge when MediaConvert Job Status changes to either 'COMPLETE' or 'ERROR'
        A EventBridge rule configures this Lambda Handler as a Trigger. This Handler will update the Status of the 
        Job in the DDB Table JobTracker

        A Sample Payload passed to this handler is shown below

        {
            "version": "0",
            "id": "",
            "detail-type": "MediaConvert Job State Change",
            "source": "aws.mediaconvert",
            "account": "",
            "time": "",
            "region": "us-east-2",
            "resources": [
                "arn:aws:mediaconvert"
            ],
            "detail": {
                "timestamp": ,
                "accountId": "",
                "queue": "queue",
                "jobId": "1662660985490-XXXXXXXXXXXXXXX",
                "status": "COMPLETE",
                "userMetadata": {
                    "BatchId": "62119357-db53-4464-8e1d-0ad66370fbb5"
                },
                "outputGroupDetails": [
                    {
                        
                    },
                    {
                        
                    }
                ]
            }
        }

    '''
    dataplane = DataPlane({})
    job_id = event['detail']['jobId']

    logger.info(json.dumps(event))

    # Updates Job Status to either 'COMPLETE' or 'ERROR'
    dataplane.update_media_convert_job_status(job_id, event['detail']['status'])

    publish_to_MRE_bus_after_clip_job_complete(event['detail']['userMetadata'])

def are_jobs_complete(jobIds, dataplane) -> bool:
    all_jobs_complete = True
    for job_id in jobIds:
        job_detail = dataplane.get_media_convert_job_detail(job_id)
        if job_detail:
            job_status = job_detail[0]["Status"]
            if job_status == 'CREATED':
                all_jobs_complete = False
                break
        else:
            all_jobs_complete = True    # When No JobId is found in DDB, which should never happen, we set the state to True to avoid SFN loop to go on eternally.
            break
    return all_jobs_complete

def process_original_segments(nonoptimized_segments, dataplane, event):

    # A NonOpt Clip needs to be created for every segment
    nonoptimized_segments_with_tracks = []
    media_convert_job_ids = []
    for segment in nonoptimized_segments:

        logger.info("---  Processing Original segments -------------")
        logger.info(f"segment['Start'] = {segment['Start']}")
        chunks = dataplane.get_chunks_for_segment(segment['Start'], segment['End'])
        logger.info('Got Chunks from API based for Original Segments)')
        logger.info(f" Original_segments chunks: {chunks}")
        segs, job_ids = create_non_optimized_MP4_clip_per_audio_track(dataplane, segment, event, chunks)

        nonoptimized_segments_with_tracks.extend(segs)
        media_convert_job_ids.extend(job_ids)

       
       
    return nonoptimized_segments_with_tracks, media_convert_job_ids


def publish_to_MRE_bus_after_clip_job_complete(payload) -> None:

    detail = {
            "State": "CLIP_GEN_DONE_WITH_CLIPS",
            "Event": {
                "EventInfo": {
                    "EventName": payload['EventName'],
                    "ProgramName": payload['ProgramName']
                },
                "EventType": "EVENT_CLIP_GEN_WITH_CLIPS"
            }
        }
    detail['SegmentClipDetail'] = payload
    try:
        eb_client.put_events(
            Entries=[
                {
                    "Source": "awsmre",
                    "DetailType": "Clip Gen Clip Gen Done Status",
                    "Detail": json.dumps(detail),
                    "EventBusName": EB_EVENT_BUS_NAME
                }
            ]
        )
        logger.info(f"Published {detail['State']}")
    except Exception as e:
        logger.info(e)
        logger.info('Error while publishing CLIP_GEN_DONE_WITH_CLIPS event to EB')

def publish_to_MRE_bus(event, clipsGenerated=False, segments=None) -> None:

    detail = {
            "State": "CLIP_GEN_DONE",
            "Event": {
                "EventInfo": event,
                "EventType": "EVENT_CLIP_GEN"
            }
        }
    
    # Publish Clip location Info when available.
    if clipsGenerated and segments:
       detail['ClipInfo'] = segments

    logger.info(f"Publishing to EB - {detail['State']}")
    logger.info(f"Publishing to EB - {detail}")
    try:
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
        logger.info(f"Published {detail['State']}")
    except Exception as e:
        logger.info(e)
        logger.info('Error while publishing CLIP_GEN_DONE event to EB')

# Save Segment info whether Clips are generated or not
def save_original_segment_info(dataplane, event, nonoptimized_segments_with_tracks):
    if nonoptimized_segments_with_tracks:
        logger.info(f"Processed Non Opt Segments before saving into Plugin Results - {nonoptimized_segments_with_tracks}")
        dataplane.save_clip_results(nonoptimized_segments_with_tracks)

    publish_to_MRE_bus(event, clipsGenerated=should_generate_original_clips(event), segments=nonoptimized_segments_with_tracks)
    


def save_optimized_segment_info(event, audioTrack, dataplane):
    results = []

    optimizedClipStatus = "Not Attempted" if not should_generate_optimized_clips(event) else "Success"
    originalClipStatus = "Not Attempted" if not should_generate_original_clips(event) else "Success"

    for segment in event['Segments']:
        # We are dealing with an Optimized Segment
        if "OptimizedS3KeyPrefix" in segment:
            optimizedClipLocation = segment["OptimizedS3KeyPrefix"]
            optimizedThumbnailLocation = segment["OptimizedThumbnailS3KeyPrefix"]
            

            if "OriginalS3KeyPrefix" in segment:
                originalClipLocation = "" if not should_generate_original_clips(event) else segment["OriginalS3KeyPrefix"]

                results.append({
                    "Start": segment['Start'],
                    "End": segment['End'],
                    "OriginalClipStatus": originalClipStatus,
                    "OriginalClipLocation": originalClipLocation,
                    "OptoStart": get_OptoStart(segment, event),
                    "OptoEnd": get_OptoEnd(segment, event),
                    "OptimizedClipStatus": optimizedClipStatus,
                    "OptimizedClipLocation": optimizedClipLocation,
                    "OptimizedThumbnailLocation": optimizedThumbnailLocation,
                    "AudioTrack": audioTrack
                })
            else:
                results.append({
                    "Start": segment['Start'],
                    "End": segment['End'],
                    "OptoStart": get_OptoStart(segment, event),
                    "OptoEnd": get_OptoEnd(segment, event),
                    "OptimizedClipStatus": optimizedClipStatus,
                    "OptimizedClipLocation": optimizedClipLocation,
                    "OptimizedThumbnailLocation": optimizedThumbnailLocation,
                    "AudioTrack": audioTrack
                })

    if results:
        logger.info(f"Processed Optimized Segments before saving - {results}")
        dataplane.save_clip_results(results)
        publish_to_MRE_bus(event, clipsGenerated=should_generate_optimized_clips(event), segments=results)

    return results

def create_HLS_clips(event, inputSettings, index, batch_id, audioTrack):

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

        jobMetadata = {
                "EventName": event['Event']['Name'],
                "ProgramName": event['Event']['Program'],
                'BatchId': batch_id,
                "Source": "ClipGen"
        }

        return create_job(jobMetadata, jobSettings)

    except Exception as e:
        logger.info ('Exception: %s' % e)
        raise


def create_hls_output(hls_input_settings_for_segments, event, audioTrack, batch_id):

    all_hls_clip_job_ids = []

    # For HLS Clips, divide the Entire Segment List to Smaller Chunks to meet the MediaConvert Quota Limits of 150 Inputs per Job
    # We create a MediaConvert Job per segment group (which can have a Max of 150 Inputs configured
    
    groups_of_input_settings = [hls_input_settings_for_segments[x:x+MAX_INPUTS_PER_JOB] for x in range(0, len(hls_input_settings_for_segments), MAX_INPUTS_PER_JOB)]
    index = 1
    

    #----------- HLS Clips Gen ------------------------------------

    logger.info("---------------- ALL groups_of_input_settings")
    logger.info(groups_of_input_settings)

    # For Opto segments, AudioTrack would be passed to the Step function
    if 'Optimizer' in event['Profile']:
        logger.info("---- Creating Opto HLS -----------")
        # Launch a Media Convert Job with a Max of 150 Inputs
        for inputsettings in groups_of_input_settings:
            # Each Input setting will have the relevant AudioTrack embedded.
            job = create_HLS_clips(event, inputsettings, index, batch_id, audioTrack)

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
                    job = create_HLS_clips(event, final_input_settings, index, batch_id, track)

                    if job != None:
                        all_hls_clip_job_ids.append(job['Job']['Id'])
                    index += 1

    return all_hls_clip_job_ids, batch_id

@logger.inject_lambda_context
def GenerateClips(event, context):
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
    audioTrack = 1 if 'TrackNumber' not in event else event['TrackNumber']

    # Get all the Original and Optimized segments to be processed
    optimized_segments, nonoptimized_segments = get_all_original_optimized_segments(event)

    # Create a Optimized Clip for Optimized Segments
    hls_input_settings_for_segments = []
    nonoptimized_segments_with_tracks = []
    opto_results = []
    # Create Clips for Optimized Segments
    if optimized_segments:
        
        hls_input_settings_for_segments = build_opto_hls_settings(optimized_segments, dataplane, event)

        # Generate MP4 Clips for Optimized Segments only when asked for
        
        logger.info('Processing Optimized segments ...')
        job_ids = process_optimized_segments(optimized_segments, dataplane, event)
        
        logger.info(f'OPTO MEDIA CONVERT JOBS COUNT = {len(job_ids)}, segs = {len(optimized_segments)}')
        logger.info(f'OPTO MEDIA CONVERT JOBS  = {job_ids}')

        for job_id in job_ids:
            dataplane.save_media_convert_job_details(job_id)

        # Save all Optimized Segment info per audio track into Plugin Results
        opto_results = save_optimized_segment_info(event, audioTrack, dataplane)
        logger.info('Optimized segments Saved !!')

    # Create Clips for Original Segments
    if nonoptimized_segments:

        # Only when we have no Optimizer configured we generate HLS 
        # output from the HLS Settings corresponding to Orig segments
        if 'Optimizer' not in event['Profile']:
            hls_input_settings_for_segments = build_orig_hls_settings(nonoptimized_segments, dataplane, event)


        nonoptimized_segments_with_tracks, job_ids =  process_original_segments(nonoptimized_segments, dataplane, event)
        logger.info(f'NON_OPTO MEDIA CONVERT JOBS COUNT = {len(job_ids)}, segs = {len(nonoptimized_segments)}')
        logger.info(f'NON_OPTO MEDIA CONVERT JOBS  = {job_ids}')

        for job_id in job_ids:
            dataplane.save_media_convert_job_details(job_id)

        # Save all Original Segment info into Plugin Results
        save_original_segment_info(dataplane, event, nonoptimized_segments_with_tracks)
        logger.info('Original segments with ClipInfo Saved !!')

        
    # Generate HLS output from the HLS Settings corresponding to Orig or Opto segments.
    all_hls_clip_job_ids = []
    batch_id = str(uuid.uuid4())
    logger.info(f'Proceeding to create HLS output ... {hls_input_settings_for_segments}')
    all_hls_clip_job_ids, batch_id = create_hls_output(hls_input_settings_for_segments, event, audioTrack, batch_id)

    # For Opto segments, AudioTrack would be passed to the Step function
    if 'Optimizer' in event['Profile']:
        return {
            "MediaConvertJobs" : all_hls_clip_job_ids,
            "HLSOutputKeyPrefix": f"HLS/{batch_id}/{audioTrack}/",
            "OutputBucket": OUTPUT_BUCKET,
            "Result": opto_results,
            "Event": event['Event'],
            "Input": event['Input']
        }
    else:
        return {
            "MediaConvertJobs" : all_hls_clip_job_ids,
            "OutputBucket": OUTPUT_BUCKET,
            "HLSOutputKeyPrefix": f"HLS/{batch_id}/",
            "Result": opto_results,
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
def get_clip_timings(dataplane, segment, event, fallbackToDefault=False):

    if not fallbackToDefault:
        if "OptoEnd" in segment and "OptoStart" in segment:
            return dataplane.get_mediaconvert_clip_format(get_OptoEnd(segment, event)), dataplane.get_mediaconvert_clip_format(get_OptoStart(segment, event))
            
        elif "End" in segment and "Start" in segment:
            return dataplane.get_mediaconvert_clip_format(segment['End']), dataplane.get_mediaconvert_clip_format(segment['Start'])
    else:
            return "00:00:20:00", "00:00:00:00"

def get_start_clip_timings(dataplane, segment, event):

    if "OptoEnd" in segment and "OptoStart" in segment:
        return dataplane.get_mediaconvert_clip_format(get_OptoStart(segment, event))
    elif "End" in segment and "Start" in segment:
        return dataplane.get_mediaconvert_clip_format(segment['Start'])

            
def get_end_clip_timings(dataplane,segment, event):

    if "OptoEnd" in segment and "OptoStart" in segment:
        return dataplane.get_mediaconvert_clip_format(get_OptoEnd(segment, event))
    elif "End" in segment and "Start" in segment:
        return dataplane.get_mediaconvert_clip_format(segment['End'])




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

def build_hls_input(dataplane, segment, event, chunks ,audioTrack):
    
    inputs = []

    # Only chunk, so will have Start and End Clipping time
    if len(chunks) == 1:
        inputClippings = []
        inputClip = {}
        ic = {}

        endtime, starttime = get_clip_timings(dataplane,segment, event)
        ic['EndTimecode'] = str(endtime)
        ic['StartTimecode'] = str(starttime)

        #If we have a single Chunk we don't need the Endtime Configured if it is less than Start time. Remove it.
        if datetime.strptime(endtime, "%H:%M:%S:%f") < datetime.strptime(starttime, "%H:%M:%S:%f"):
            ic.pop('EndTimecode', None)

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
                ic['StartTimecode'] = get_start_clip_timings(dataplane, segment, event)
                inputClippings.append(ic)
                inputClip['InputClippings'] = inputClippings
            elif chunk_index == len(chunks)-1:  # Last Chunk
                ic['EndTimecode'] = get_end_clip_timings(dataplane, segment, event)
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

def create_optimized_MP4_clips(dataplane, segment, event, chunks):

    #hls_input_setting = []
    media_convert_job_ids = []

    if should_generate_optimized_clips(event): 
        try:
            job_settings_filename = os.path.join(os.path.dirname(__file__), 'job_settings_mp4.json')

            with open(job_settings_filename) as json_data:
                jobSettings = json.load(json_data)

            
            # Check if an AudioTrack has been sent in the event.
            # If yes, set the AudioTrack for extraction in MediaConvert
            # Also use the AudioTrack in the Output video key prefix
            audioTrack = 1 if 'TrackNumber' not in event else event['TrackNumber']

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
            if should_generate_optimized_thumbnails(event):
                thumbnail_keyprefix = f"thumbnail/{runid}/{str(get_OptoStart(segment, event)).replace('.',':')}-{str(get_OptoEnd(segment, event)).replace('.',':')}"
                thumbnail_job_output_destination = f"s3://{OUTPUT_BUCKET}/{thumbnail_keyprefix}"
                jobSettings["OutputGroups"][1]["OutputGroupSettings"]["FileGroupSettings"]["Destination"] = thumbnail_job_output_destination
            else:
                jobSettings["OutputGroups"].pop(1)  # Remove the Frame Settings if Thumbnails are not generated

            jobMetadata = {
                    "Start": str(segment.get['OptoStart'][audioTrack]) if type(segment['OptoStart']) is dict else str(segment['OptoStart']),
                    "End": str(segment.get['OptoEnd'][audioTrack]) if type(segment['OptoEnd']) is dict else str(segment['OptoEnd']),
                    "OptimizedClipStatus": "Success",
                    "AudioTrack": str(audioTrack),
                    #'OptimizedClipLocation': f"{job_output_destination}.mp4",
                    #'OptimizedThumbnailLocation': f"{thumbnail_job_output_destination}.0000000.jpg",
                    "EventName": event['Event']['Name'],
                    "ProgramName": event['Event']['Program'],
                    "Source": "ClipGen"
            }

            # Input should be based on the Number of chunks. A Segment timing can constitute multiple chunks
            # If only one Chunk found, then we create one Input for the MediaConvert Job 
            # If more than on Chunk, create as many Inputs and set the InputClippings Accordingly.
            # Inputclippings will be assigned as follows
            # When #Chunks > 1 , 1st Chunk - StartTime = Segment.OptoStart, EndTime = Empty
            # When #Chunks > 1 , 2nd Chunk - StartTime = Empty, EndTime = empty
            # When #Chunks > 1 , 3rd Chunk - StartTime = Empty, EndTime = Segment.OptoEnd
            logger.info(f"we got {len(chunks)} number of chunks")
            if len(chunks) == 1:
                # Update the job settings with the source video from the S3 event and destination 
                input_segment_location = f"s3://{chunks[0]['S3Bucket']}/{chunks[0]['S3Key']}"
                jobSettings['Inputs'][0]['FileInput'] = input_segment_location

                logger.info("Only one Chunk found .. Clip Timings is")
                if "OptoEnd" in segment and "OptoStart" in segment:
                
                    if type(segment['OptoEnd']) is dict:
                        logger.info(f"Segment OptoEnd is {segment['OptoEnd'][audioTrack]}")
                    else:
                        logger.info(f"Segment OptoEnd is {segment['OptoEnd']}")
                
                    if type(segment['OptoStart']) is dict:
                        logger.info(f"Segment OptoStart is {segment['OptoStart'][audioTrack]}")
                    else:
                        logger.info(f"Segment OptoStart is {segment['OptoStart']}")

                logger.info(f"Here are the modified Clip Timings when Total chunks = 1")
                logger.info(get_clip_timings(dataplane, segment, event))

                endtime, starttime = get_clip_timings(dataplane, segment, event)
                jobSettings['Inputs'][0]['InputClippings'][0]['EndTimecode'] = str(endtime)
                jobSettings['Inputs'][0]['InputClippings'][0]['StartTimecode'] = str(starttime)

                #If we have a single Chunk we don't need the Endtime Configured if it is less than Start time. Remove it.
                if datetime.strptime(endtime, "%H:%M:%S:%f") < datetime.strptime(starttime, "%H:%M:%S:%f"):
                    jobSettings['Inputs'][0]['InputClippings'][0].pop('EndTimecode', None)    


                logger.info("Single Chunk processed .. JobSettings is ...")
                logger.info(json.dumps(jobSettings))

                # We pass Metadata so subscribers to the Event Bridge event which is Triggered when 
                # the Job finishes, can do something useful 
                jobid = str(uuid.uuid4())
                jobMetadata['JobId'] = jobid
                job_response = create_job(jobMetadata, jobSettings)
                media_convert_job_ids.append(job_response['Job']['Id'])
                
            elif len(chunks) > 1:
                for chunk_index in range(len(chunks)):
                    
                    input_segment_location = f"s3://{chunks[chunk_index]['S3Bucket']}/{chunks[chunk_index]['S3Key']}"
                        
                    if chunk_index == 0:    # First Chunk
                        logger.info(f"Chunk index is {chunk_index}")
                        jobSettings['Inputs'][0]['FileInput'] = input_segment_location
                        jobSettings['Inputs'][0]['InputClippings'][0]['StartTimecode'] = get_start_clip_timings(dataplane, segment, event)
                        jobSettings['Inputs'][0]['InputClippings'][0].pop('EndTimecode', None)

                        logger.info(f"First chunk processing ... Job Setting is")
                        logger.info(json.dumps(jobSettings))
                    elif chunk_index == len(chunks)-1:  # Last Chunk

                        logger.info(f"Chunk index is {chunk_index}")
                        jobSettings['Inputs'].append(copy.deepcopy(jobSettings['Inputs'][0]))   #Clone the existing InputSettings and add it to the Inputs Key
                        jobSettings['Inputs'][chunk_index]['FileInput'] = input_segment_location
                        jobSettings['Inputs'][chunk_index]['InputClippings'][0].pop('StartTimecode', None)
                        jobSettings['Inputs'][chunk_index]['InputClippings'][0]['EndTimecode'] = get_end_clip_timings(dataplane, segment, event)

                        logger.info(f"Last chunk processing ... Job Setting is")
                        logger.info(json.dumps(jobSettings))
                    else:   #in between chunks
                        logger.info(f"Chunk index is {chunk_index}")
                        jobSettings['Inputs'].append(copy.deepcopy(jobSettings['Inputs'][0]))
                        jobSettings['Inputs'][chunk_index]['FileInput'] = input_segment_location
                        jobSettings['Inputs'][chunk_index]['InputClippings']= []   # No need to Clip for sandwitched Chunks
                        logger.info(f"Sandwitch chunk processing ... Job Setting is")
                        logger.info(json.dumps(jobSettings))

                # We pass Metadata so subscribers to the Event Bridge event which is Triggered when 
                # the Job finishes, can do something useful 
                jobid = str(uuid.uuid4())
                jobMetadata['JobId'] = jobid
                job_response = create_job(jobMetadata, jobSettings)
                media_convert_job_ids.append(job_response['Job']['Id'])

            # Update the Segment with the S3KeyPrefix
            segment['OptimizedS3KeyPrefix'] = f"{job_output_destination}.mp4"
            segment['OptimizedThumbnailS3KeyPrefix'] = f"{thumbnail_job_output_destination}.0000000.jpg" if should_generate_optimized_thumbnails(event) else ""

            #logger.info(json.dumps(jobSettings))

        except Exception as e:
            logger.info ('Exception: %s' % e)
            raise

    # Clip generation disabled, thumbnails enabled
    elif not should_generate_optimized_clips(event) and should_generate_optimized_thumbnails(event):
        logger.info('Generating Opto thumbnails only ...')
        segment["OptimizedS3KeyPrefix"] = ""

        # In order to generate a Thumbnail, we just hook into the 
        # first chunk and Grab the Frame at the center of the Chunk
        thumbnail_image_location = generate_thumbnail_image(chunks[0]['S3Bucket'], chunks[0]['S3Key'])
        segment["OptimizedClipStatus"] = "Thumbnail generated"
        segment["OptimizedThumbnailS3KeyPrefix"] = thumbnail_image_location # S3 Location of Thumbnail Image

    # Clip generation disabled, thumbnails disabled
    elif not should_generate_optimized_clips(event) and not should_generate_optimized_thumbnails(event):
        logger.info('Not generating both Opto  Clip and Thumbnails ...')
        segment["OptimizedClipStatus"] = "NA"
        segment["OptimizedS3KeyPrefix"] = ""
        segment["OptimizedThumbnailS3KeyPrefix"] = ""
    
    logger.info(f"OPTIMIZED SEGMENT STATE AFTER PROCESSING = {json.dumps(segment)}")
    return media_convert_job_ids

def create_job(jobMetadata, jobSettings):

    # Customizing Exponential back-off
    # Retries with additional client side throttling.
    boto_config = Config(
        retries = {
            'max_attempts': 3,
            'mode': 'adaptive'
        }
    )
    # add the account-specific endpoint to the client session 
    client = boto3.client('mediaconvert', config=boto_config, endpoint_url=MEDIA_CONVERT_ENDPOINT, verify=False)
    return client.create_job(Role=MEDIA_CONVERT_ROLE, UserMetadata=jobMetadata, Settings=jobSettings)


def create_non_optimized_MP4_clip_per_audio_track(dataplane, segment, event, chunks):
    audiotracks = event['Event']['AudioTracks']
    segments = []
    media_convert_job_ids = []
    for track in audiotracks:
        seg, job_ids = create_non_optimized_MP4_clips(dataplane, segment, event, chunks, int(track))
        segments.append(seg)
        media_convert_job_ids.extend(job_ids)
    
    return segments, media_convert_job_ids


def is_end_time_less_than_start_time(endtime, starttime):
    end = endtime.split(':')
    start = starttime.split(':')
    if int(end[0]) > int(start[0]) or int(end[1]) > int(start[1]) or int(end[2]) > int(start[2]) or int(end[3]) > int(start[3]):
        return False
    
    return True

def create_non_optimized_MP4_clips(dataplane, segment, event, chunks, audioTrack):
    #hls_input = []
    media_convert_job_ids = []

    # Get the State of the existing Original Segment
    orig_segment = get_original_segment_dict(segment, audioTrack)
    

    if should_generate_original_clips(event): 
        try:
        
        
            job_settings_filename = os.path.join(os.path.dirname(__file__), 'job_settings_mp4.json')
                    
            with open(job_settings_filename) as json_data:
                jobSettings = json.load(json_data)


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
            
            # Only when we generate clips, we set the job_output_destination for MP4 Clips
            jobSettings["OutputGroups"][0]["OutputGroupSettings"]["FileGroupSettings"]["Destination"] = job_output_destination

            
            if should_generate_original_thumbnails(event):
                thumbnail_keyprefix = f"thumbnail/{runid}/{str(segment['Start']).replace('.',':')}-{str(segment['End']).replace('.',':')}"
                thumbnail_job_output_destination = f"s3://{OUTPUT_BUCKET}/{thumbnail_keyprefix}"
                jobSettings["OutputGroups"][1]["OutputGroupSettings"]["FileGroupSettings"]["Destination"] = thumbnail_job_output_destination
            else:
                jobSettings["OutputGroups"].pop(1)  # Remove the Frame Settings if Thumbnails are not generated

            jobMetadata = {
                    "Start": str(segment['Start']),
                    "End": str(segment['End']),
                    "OriginalClipStatus": "Success",
                    "AudioTrack": str(audioTrack),
                    #"OriginalClipLocation": f"{job_output_destination}.mp4",
                    #"OriginalThumbnailLocation": f"{thumbnail_job_output_destination}.0000000.jpg",
                    "EventName": event['Event']['Name'],
                    "ProgramName": event['Event']['Program'],
                    "Source": "ClipGen"
            }

            # Input should be based on the Number of chunks. A Segment timming can constitute multiple chunks
            # If only one Chunk found, then we create one Input for the MediaConvert Job 
            # If more than on Chunk, create as many Inputs and set the InputClippings Accordingly.
            # Inputclippings will be assigned as follows
            # When #Chunks > 1 , 1st Chunk - StartTime = Segment.OptoStart, EndTime = Empty
            # When #Chunks > 1 , 2nd Chunk - StartTime = Empty, EndTime = empty
            # When #Chunks > 1 , 3rd Chunk - StartTime = Empty, EndTime = Segment.OptoEnd
            logger.info(f"we got {len(chunks)} number of chunks")
            if len(chunks) == 1:
                # Update the job settings with the source video from the S3 event and destination 
                input_segment_location = f"s3://{chunks[0]['S3Bucket']}/{chunks[0]['S3Key']}"
                jobSettings['Inputs'][0]['FileInput'] = input_segment_location

                endtime, starttime = get_clip_timings(dataplane, segment, event)
                jobSettings['Inputs'][0]['InputClippings'][0]['EndTimecode'] = str(endtime)
                jobSettings['Inputs'][0]['InputClippings'][0]['StartTimecode'] = str(starttime)

                #If we have a single Chunk we don't need the Endtime Configured if it is less than Start time. Remove it.
                if datetime.strptime(endtime, "%H:%M:%S:%f") < datetime.strptime(starttime, "%H:%M:%S:%f"):
                    jobSettings['Inputs'][0]['InputClippings'][0].pop('EndTimecode', None)
                
                # Convert the video using AWS Elemental MediaConvert
                # We pass Metadata so subscribers to the Event Bridge event which is Triggered when 
                # the Job finishes, can do something useful 
                jobid = str(uuid.uuid4())
                jobMetadata['JobId'] = jobid
                job_response = create_job(jobMetadata, jobSettings)
                media_convert_job_ids.append(job_response['Job']['Id'])

            elif len(chunks) > 1:
                for chunk_index in range(len(chunks)):
                    
                    input_segment_location = f"s3://{chunks[chunk_index]['S3Bucket']}/{chunks[chunk_index]['S3Key']}"
                        
                    if chunk_index == 0:    # First Chunk
                        jobSettings['Inputs'][0]['FileInput'] = input_segment_location
                        jobSettings['Inputs'][0]['InputClippings'][0]['StartTimecode'] = get_start_clip_timings(dataplane, segment, event)
                        jobSettings['Inputs'][0]['InputClippings'][0].pop('EndTimecode', None)
                    elif chunk_index == len(chunks)-1:  # Last Chunk
                        jobSettings['Inputs'].append(copy.deepcopy(jobSettings['Inputs'][0]))   #Clone the existing InputSettings and add it to the Inputs Key
                        jobSettings['Inputs'][chunk_index]['FileInput'] = input_segment_location
                        jobSettings['Inputs'][chunk_index]['InputClippings'][0].pop('StartTimecode', None)
                        jobSettings['Inputs'][chunk_index]['InputClippings'][0]['EndTimecode'] = get_end_clip_timings(dataplane,segment, event)
                    else:   #in between chunks
                        jobSettings['Inputs'].append(copy.deepcopy(jobSettings['Inputs'][0]))
                        jobSettings['Inputs'][chunk_index]['FileInput'] = input_segment_location
                        jobSettings['Inputs'][chunk_index]['InputClippings']= []   # No need to Clip for sandwitched Chunks
                        

                # Convert the video using AWS Elemental MediaConvert
                # We pass Metadata so subscribers to the Event Bridge event which is Triggered when 
                # the Job finishes, can do something useful 
                jobid = str(uuid.uuid4())
                jobMetadata['JobId'] = jobid
                job_response = create_job(jobMetadata, jobSettings)
                media_convert_job_ids.append(job_response['Job']['Id'])
            
        except Exception as e:
            logger.info ('Exception: %s' % e)
            raise

        #orig_segment["OriginalClipLocation"] = "NA" if thumbnails_only else f"{job_output_destination}.mp4"
        orig_segment["OriginalClipLocation"] = f"{job_output_destination}.mp4"
        orig_segment["OriginalThumbnailLocation"] = f"{thumbnail_job_output_destination}.0000000.jpg" if should_generate_original_thumbnails(event) else ""

    # Clip generation disabled, thumbnails enabled
    elif not should_generate_original_clips(event) and should_generate_original_thumbnails(event):
        logger.info('Generating thumbnails only ...')
        orig_segment["OriginalClipLocation"] = ""

        # In order to generate a Thumbnail, we just hook into the 
        # first chunk and Grab the Frame at the center of the Chunk
        thumbnail_image_location = generate_thumbnail_image(chunks[0]['S3Bucket'], chunks[0]['S3Key'])
        orig_segment["OriginalClipStatus"] = "Thumbnail generated"
        orig_segment["OriginalThumbnailLocation"] = thumbnail_image_location # S3 Location of Thumbnail Image

    # Clip generation disabled, thumbnails disabled
    elif not should_generate_original_clips(event) and not should_generate_original_thumbnails(event):
        logger.info('Not generating both Clip and Thumbnails ...')
        orig_segment["OriginalClipStatus"] = "NA"
        orig_segment["OriginalClipLocation"] = ""
        orig_segment["OriginalThumbnailLocation"] = ""
    
    logger.info(f"ORIGINAL SEGMENT STATE AFTER PROCESSING = {json.dumps(orig_segment)}")

    return orig_segment, media_convert_job_ids

