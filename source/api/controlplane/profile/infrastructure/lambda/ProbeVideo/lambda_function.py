#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

##############################################################################
#
# PURPOSE:
# Probe the HLS video segment (.ts) file outputted by MediaLive to extract 
# metadata about the video segment and all the key frames in it
#
##############################################################################

import os
import traceback
from datetime import date, datetime, time, timedelta

import ffmpeg

from MediaReplayEnginePluginHelper import DataPlane
from MediaReplayEnginePluginHelper import MREExecutionError
from MediaReplayEngineWorkflowHelper import ControlPlane

controlplane = ControlPlane()


def get_first_pts(p_event, program, frame_rate, first_key_frame):
    print(f"Getting the first pts timecode for event '{p_event}' in program '{program}'")
    
    first_pts = controlplane.get_first_pts(p_event, program)
    
    if not first_pts:
        print(f"First pts timecode for event '{p_event}' in program '{program}' not found. Initializing from the first key frame.")
        first_pts = first_key_frame["pkt_pts_time"]
        
        print(f"Storing the first pts timecode and frame rate for event '{p_event}' in program '{program}' in DynamoDB")
        controlplane.store_first_pts(p_event, program, first_pts)
        controlplane.store_frame_rate(p_event, program, frame_rate)
    
    return float(first_pts)

def probe_video(media_path, select_streams, show_frames=False):
    if select_streams == "v:0":
        if show_frames:
            probe = ffmpeg.probe(media_path, select_streams=select_streams, show_frames=None, skip_frame="nokey")
            result = probe["frames"]
        
        else:
            probe = ffmpeg.probe(media_path, select_streams=select_streams)
            result = probe["streams"][0]
    
    elif select_streams == "a":
        probe = ffmpeg.probe(media_path, select_streams=select_streams)
        result = []
        
        if "streams" in probe:
            for stream in probe["streams"]:
                result.append(stream['index'])
    
    return result
    
def lambda_handler(event, context):
    print("Lambda got the following event:\n", event)
    
    program = event["Event"]["Program"]
    p_event = event["Event"]["Name"]
    p_event_start = event["Event"]["Start"]
    audio_tracks = event["Event"]["AudioTracks"] if "AudioTracks" in event["Event"] else []
    execution_id = event["Input"]["ExecutionId"]
    bucket = event["Input"]["Media"]["S3Bucket"]
    key = event["Input"]["Media"]["S3Key"]
    filename = os.path.split(key)[-1]
    
    print(f"Probing the HLS video segment '{key}' from S3 bucket '{bucket}'")
    
    try:
        # Record current workflow execution details in the Control Plane
        controlplane.record_execution_details(p_event, program, filename, execution_id)
        
        dataplane = DataPlane(event)
        
        # Download the HLS video segment from S3
        media_path = dataplane.download_media()
        
        # Get ffprobe video stream output
        video_stream = probe_video(media_path, select_streams="v:0")
        
        print("Getting start_time, duration, frame_rate from the video segment")
        
        # HLS video segment metadata
        start_pts_time = float(video_stream["start_time"])
        duration = round(float(video_stream["duration"]), 3)
        frame_rate = round(eval(video_stream["avg_frame_rate"]))
        
        if not audio_tracks:
            print("Getting the list of audio tracks present in the video segment")
            audio_tracks = probe_video(media_path, select_streams="a")
            
            # Store the audio tracks information in the Control Plane
            controlplane.store_audio_tracks(p_event, program, audio_tracks)
        
        print("Extracting all the key frames from the video segment")
        
        # Get ffprobe frame output
        key_frames = probe_video(media_path, select_streams="v:0", show_frames=True)
        
        # Get the pts timecode of the first frame of the first HLS video segment
        first_pts = get_first_pts(p_event, program, frame_rate, key_frames[0])
        
        offset = 0
        
        for index, frame in enumerate(key_frames):
            pkt_pts_time = float(frame["pkt_pts_time"])
            frame_time = round(pkt_pts_time - first_pts, 3) # Zero-based timecode
            
            if index == 0: # Calculate offset used in restarting the frame number for each new HLS video segment
                offset = frame_time
            
            key_frame = {
                "ExecutionId": execution_id,
                "Filename": filename,
                "FrameNumber": int((frame_time - offset) * frame_rate),
                "FramePtsTime": pkt_pts_time,
                "FrameTime": frame_time,
                "KeyFrame": frame["key_frame"],
                "PictType": frame["pict_type"],
                "DurationTime": float(frame["pkt_duration_time"])
            }
            
            # Replace existing key frame in the list
            key_frames[index] = key_frame
        
        print("Storing the extracted key frames in DynamoDB")
        dataplane.store_frames(key_frames)
        
        # Metadata to include about the HLS segment in the result
        start_time = round(start_pts_time - first_pts, 3)
        start_time_utc = (datetime.combine(date.today(), time(0, 0, 0)) + timedelta(seconds=start_time)).strftime("%H:%M:%S.%f")[:-3]
        start_pts_time_utc = (datetime.combine(date.today(), time(0, 0, 0)) + timedelta(seconds=start_pts_time)).strftime("%H:%M:%S.%f")[:-3]
        
        print("Storing the HLS Segment (Chunk) metadata in DynamoDB")
        dataplane.store_chunk_metadata(start_time, start_pts_time, duration, bucket, key)
        
        result = {
            "Event": {
                "Name": p_event,
                "Program": program,
                "Start": p_event_start,
                "AudioTracks": audio_tracks
            },
            "Input": {
                "ExecutionId": execution_id,
                "Media": {
                    "S3Bucket": bucket,
                    "S3Key": key
                },
                "Metadata": {
                    "HLSSegment": {
                        "StartTime": start_time,
                        "StartTimeUtc": start_time_utc,
                        "StartPtsTime": start_pts_time,
                        "StartPtsTimeUtc": start_pts_time_utc,
                        "Duration": duration,
                        "FrameRate": frame_rate
                    }
                }
            }
        }
        
        print(f"Done probing the HLS video segment '{bucket}/{key}'")
            
        return result
    
    except ffmpeg.Error as e:
        print(f"ffprobe: Encountered an error while probing the HLS segment file '{bucket}/{key}': {e.stderr}")
        raise MREExecutionError(e.stderr)
    
    except Exception as e:
        print(f"Encountered an exception while probing the HLS segment file '{bucket}/{key}': {str(e)}")
        print(traceback.format_exc())
        raise MREExecutionError(e)
        