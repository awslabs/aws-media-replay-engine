#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from timecode import Timecode
from boto3 import client
import uuid
import os
import boto3
import time

MEDIA_CONVERT_ENDPOINT = os.environ['MEDIA_CONVERT_ENDPOINT']

OUTPUT_BUCKET = os.environ['OutputBucket'] 
s3_client = boto3.client('s3')

'''
{
  "Input": {
    "ExecutionId": "27d2cbfd-4d77-490e-8ae6-711fa07c259d",
    "Media": {
      "S3Bucket": "aws-mre-ml-output",
      "S3Key": "Reeu1200927005_1-YS-3min_1_00002.mp4"
    },
    "Metadata": {
      "HLSSegment": {
        "StartTime": 20,
        "StartTimeUtc": "00:00:20.000",
        "StartPtsTime": 22.3,
        "StartPtsTimeUtc": "00:00:22.300",
        "Duration": 20,
        "FrameRate": 25
      }
    }
  },  
  "Event": {
    "Name": "Olympics",
    "Program": "Olympics",
    "FrameRate": 25,
    "Profile": "TestProfile"
  },
  "Segments": [
    {
            "Start": 1.6,
            "End": 4.5
        },
        {
            "Start": 6.1,
            "End": 12.3
        },
        {
            "Start": 13.1,
            "End": 29.9
        },
        {
            "Start": 33.4,
            "End": 100.9
        },
        {
            "Start": 112,
            "End": 179
        }
  ]
}
'''

'''
Generates CMX 3600 EDL formatted content from Segment Clip times. The following formatted content is generated

TITLE: llama-ad-llama
FCM: NON-DROP FRAME

001  AX      B     C        00:00:00:00 00:00:04:00 00:00:00:00 00:00:04:00
* FROM CLIP NAME: Reeu1200927005_1-YS-3min.mp4

002  AX      B     C        00:00:05:00 00:00:09:00 00:00:04:00 00:00:08:00
* FROM CLIP NAME: Reeu1200927005_1-YS-3min.mp4

003  AX      B     C        00:00:10:00 00:00:20:00 00:00:08:00 00:00:18:00
* FROM CLIP NAME: Reeu1200927005_1-YS-3min.mp4

004  AX      B     C        00:00:22:00 00:00:30:00 00:00:18:00 00:00:26:00
* FROM CLIP NAME: Reeu1200927005_1-YS-3min.mp4

005  AX      B     C        00:00:30:00 00:02:56:00 00:00:26:00 00:02:52:00
* FROM CLIP NAME: Reeu1200927005_1-YS-3min.mp4

'''
#@app.lambda_function()
def generate_edl(event, context):
    
    from MediaReplayEnginePluginHelper import DataPlane
    from MediaReplayEngineWorkflowHelper import ControlPlane
    dataPlaneHelper = DataPlane({})
    controlPlaneHelper = ControlPlane()

    edl_content = []
    prev_record_out_time = ""
    event_name = event['detail']['Segment']['Event']
    program_name = event['detail']['Segment']['Program']

    mre_event = controlPlaneHelper.get_event(event_name, program_name)
    frame_rate = mre_event['FrameRate']
    profile_name = mre_event['Profile']
    input_media_name = mre_event['LastKnownMediaLiveConfig']['InputAttachments'][0]['InputAttachmentName'] if 'LastKnownMediaLiveConfig' in mre_event else str(uuid.uuid4())
    input_media_name_without_extn = get_input_media_name(input_media_name)

    edl_content.append(f"TITLE: {input_media_name_without_extn}")
    edl_content.append("FCM: NON-DROP FRAME")
    edl_content.append("")


    profile = controlPlaneHelper.get_profile(profile_name)

    runid = str(uuid.uuid4())

    for track in mre_event['AudioTracks']:
      index = 1
      all_segments = dataPlaneHelper.get_all_segments_for_event_edl(program_name, event_name, profile['Classifier']['Name'], track)
  
      for segment in all_segments:
          try:
            if "OptoEnd" in segment and "OptoStart" in segment:

                # Ask helper to convert numbers into Clip Timings in the format "HH:mm:ss:SS"
                play_source_in_time_str  = time.strftime('%H:%M:%S:%s', time.gmtime(get_OptoStart(segment, track))) #dataPlaneHelper.get_mediaconvert_clip_format(get_OptoStart(segment, track), program_name, event_name, profile_name, frame_rate)
                play_source_in_time = Timecode(frame_rate, play_source_in_time_str)
                print(f"play_source_in_time = {play_source_in_time}")
                
                # Ask helper to convert numbers into Clip Timings
                play_source_out_time_str = time.strftime('%H:%M:%S:%s', time.gmtime(get_OptoEnd(segment, track))) #dataPlaneHelper.get_mediaconvert_clip_format(get_OptoEnd(segment, track), program_name, event_name, profile_name, frame_rate)
                play_source_out_time = Timecode(frame_rate, play_source_out_time_str)
                print(f"play_source_out_time = {play_source_out_time}")  

            else:# Consider the Non Opto timings

              # Ask helper to convert numbers into Clip Timings in the format "HH:mm:ss:SS"
              play_source_in_time_str  = time.strftime('%H:%M:%S:%s', time.gmtime(segment['Start'])) #dataPlaneHelper.get_mediaconvert_clip_format(segment['Start'], program_name, event_name, profile_name, frame_rate)
              play_source_in_time = Timecode(frame_rate, play_source_in_time_str)
              print(f"play_source_in_time = {play_source_in_time}")
              
              # Ask helper to convert numbers into Clip Timings
              play_source_out_time_str = time.strftime('%H:%M:%S:%s', time.gmtime(segment['End'])) #dataPlaneHelper.get_mediaconvert_clip_format(segment['End'], program_name, event_name, profile_name, frame_rate)
              play_source_out_time = Timecode(frame_rate, play_source_out_time_str)
              print(f"play_source_out_time = {play_source_out_time}")

            # If Start and End Times are the same, Skip as we get this error
            #ValueError: Timecode.frames should be a positive integer bigger than zero, not 0
            #if play_source_out_time_str == play_source_in_time_str:
            #  continue

            # Record in time always starts with all Zero's for the segment's first clip
            # For Subsequent Clips, the Record In Time would be the previous Clip's Record Out time.
            record_in_time = Timecode(frame_rate, "00:00:00:00") if index == 1 else prev_record_out_time

            # Add the Segment Clip duration to the start time. This becomes the Record Out time
            inctime = play_source_out_time - play_source_in_time
            record_out_time = record_in_time + inctime
            
            prev_record_out_time = record_out_time

            # Format as per the following
            # AX means source is AUX. We use this instead of reel numbers as we don't have the Reel Numbers in Input.
            # B - Channels involved in Edit - Audio 1 and Video
            # C -  Cut Information
            # 001  AX      B     C        00:00:00:00 00:00:04:00 00:00:00:00 00:00:04:00
            edl_line = f"{str(index).zfill(3)}  AX      B     C        {play_source_in_time_str} {play_source_out_time_str} {record_in_time} {record_out_time}"
            
            edl_content.append(edl_line)
            edl_content.append(f"* FROM CLIP NAME: {input_media_name}")
            edl_content.append("")

            index += 1
          except ValueError as e:
            print(e)

      if len(all_segments) > 0:
        create_edl_file(edl_content, input_media_name_without_extn)

        s3_key_prefix = f"EDL/{runid}/{str(track)}/{input_media_name_without_extn}.edl"

        # Upload final Manifest File to S3
        s3_client.upload_file(f"/tmp/{input_media_name_without_extn}.edl", OUTPUT_BUCKET, s3_key_prefix)
        controlPlaneHelper.update_event_edl_location(event_name, program_name, f"s3://{OUTPUT_BUCKET}/{s3_key_prefix}", str(track))

# Returns the name of the Input Media based on the S3 Key
def get_input_media_name(media_name):

    media_name_without_extn = media_name
    if media_name.find('.') != -1:
        media_name_without_extn = media_name[:media_name.find('.')]
    return media_name_without_extn


def create_edl_file(edl_content, filename):
    with open(f"/tmp/{filename}.edl", "w") as output:
        for row in edl_content:
            output.write(str(row) + '\n')



def get_OptoStart(segment, track):
    if 'OptoStart' in segment:
      if type(segment['OptoStart']) is dict:
          return segment['OptoStart'][track]
      else:
          return segment['OptoStart']



def get_OptoEnd(segment, track):
    if type(segment['OptoEnd']) is dict:
        return segment['OptoEnd'][track]
    else:
        return segment['OptoEnd']
