#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

##############################################################################
#
# PURPOSE:
# Probe the HLS video segment (.ts) file outputted to a S3 bucket to extract 
# metadata about the video segment and all the key frames in it.
#
##############################################################################

import os
import traceback
from datetime import date, datetime, time, timedelta
from dateutil import parser

import ffmpeg

from MediaReplayEnginePluginHelper import DataPlane
from MediaReplayEnginePluginHelper import MREExecutionError
from MediaReplayEngineWorkflowHelper import ControlPlane

controlplane = ControlPlane()


def get_first_pts(p_event, program, mre_event, frame_rate, first_key_frame):
    print(f"Getting the first pts timecode for event '{p_event}' in program '{program}'")

    if "FirstPts" in mre_event:
        first_pts = mre_event["FirstPts"]

    else:
        print(f"First pts timecode for event '{p_event}' in program '{program}' not found. Initializing from the first key frame.")
        first_pts = first_key_frame["pkt_pts_time"]

        print(f"Storing the first pts timecode and frame rate for event '{p_event}' in program '{program}' in DynamoDB")
        controlplane.store_first_pts(p_event, program, first_pts)
        controlplane.store_frame_rate(p_event, program, frame_rate)

    return float(first_pts)


def get_frame_time_from_timecode(frame_timecode, frame_rate):
    if not frame_timecode:
        return None

    bfr = frame_timecode.replace(';', ':').replace('.', ':').split(':')
    return (int(bfr[0]) * 60 * 60) + (int(bfr[1]) * 60) + int(bfr[2]) + (int(bfr[3]) * round(frame_rate / 1000, 3))


def get_frame_embedded_timecode(frame):
    is_timecode_embedded = False
    frame_timecode = None

    if "tags" in frame and "timecode" in frame["tags"]: # Look for embedded timecode in tags
        frame_timecode = frame["tags"]["timecode"]
        is_timecode_embedded = True

    elif "side_data_list" in frame: # Look for embedded timecode in sidedata
        for side_data in frame["side_data_list"]:
            if "timecodes" in side_data:
                frame_timecode = side_data["timecodes"][0]["value"]
                is_timecode_embedded = True
                break

    return is_timecode_embedded, frame_timecode


def get_first_frame_embedded_timecode(p_event, program, mre_event, timecode_source, first_key_frame):
    print(f"Getting the embedded timecode value of the first key frame for event '{p_event}' in program '{program}'")

    if "FirstEmbeddedTimecode" in mre_event:
        first_frame_embedded_timecode = mre_event["FirstEmbeddedTimecode"]

    else:
        print(f"Embedded timecode value of the first key frame for event '{p_event}' in program '{program}' not found. Initializing from the first key frame.")
        is_timecode_embedded, first_frame_embedded_timecode = get_frame_embedded_timecode(first_key_frame)

        if is_timecode_embedded:
            print("Embedded timecode found in the first key frame")
            print(f"Storing the embedded timecode of the first key frame in DynamoDB")
            controlplane.store_first_frame_embedded_timecode(p_event, program, first_frame_embedded_timecode)

        else:
            print(f"Embedded timecode not found in the first key frame even though TimecodeSource of the event is set to '{timecode_source}'")
            print("Falling back to ffmpeg probed relative frame time")

    return first_frame_embedded_timecode


def get_relative_frame_time_from_timecode(frame_timecode, frame_rate, event_start_dt):
    relative_seconds = get_frame_time_from_timecode(frame_timecode, frame_rate)

    now = datetime.utcnow()

    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_midnight = today_midnight - timedelta(days=1)

    utc_today = today_midnight + timedelta(seconds=relative_seconds)
    utc_yesterday = yesterday_midnight + timedelta(seconds=relative_seconds)

    if abs(utc_yesterday - now) < abs(utc_today - now):
        utc = utc_yesterday
    else:
        utc = utc_today

    print(f"Derived time: {utc}")

    event_start_epoch = event_start_dt.timestamp()
    utc_epoch = utc.timestamp()

    relative_frame_time = round(utc_epoch - event_start_epoch, 3)

    print(f"Frame time relative to event start: {relative_frame_time}")

    return relative_frame_time


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
    generate_orig_clips = event["Event"]["GenerateOrigClips"] if "GenerateOrigClips" in event["Event"] else True
    generate_opto_clips = event["Event"]["GenerateOptoClips"] if "GenerateOptoClips" in event["Event"] else True
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

        # Get all the required MRE event metadata
        mre_event = controlplane.get_event(p_event, program)
        first_pts = get_first_pts(p_event, program, mre_event, frame_rate, key_frames[0])
        timecode_source = mre_event["TimecodeSource"] if "TimecodeSource" in mre_event else "NOT_EMBEDDED"

        if timecode_source != "NOT_EMBEDDED":
            first_frame_embedded_timecode = get_first_frame_embedded_timecode(p_event, program, mre_event, timecode_source, key_frames[0])
            event_start_dt = parser.parse(p_event_start)

        offset = 0

        for index, frame in enumerate(key_frames):
            if timecode_source != "NOT_EMBEDDED" and first_frame_embedded_timecode: # Use embedded timecode if present
                _, frame_timecode = get_frame_embedded_timecode(frame)

                if timecode_source == "UTC_BASED":
                    frame_time = get_relative_frame_time_from_timecode(frame_timecode, frame_rate, event_start_dt)
                else:
                    frame_time = get_frame_time_from_timecode(frame_timecode, frame_rate)

                pkt_pts_time = round(frame_time + first_pts, 3)

                if index == 0:
                    start_pts_time = pkt_pts_time

            else: # Fallback to relative frame time
                pkt_pts_time = float(frame["pkt_pts_time"])
                frame_time = round(pkt_pts_time - first_pts, 3)

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
                "TimecodeSource": timecode_source,
                "GenerateOrigClips": generate_orig_clips,
                "GenerateOptoClips": generate_opto_clips,
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
