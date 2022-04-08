# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import json
import urllib.parse
import boto3
from decimal import Decimal
from chalice import Blueprint
from chalice import IAMAuthorizer
from chalice import ChaliceViewError, NotFoundError
from botocore.client import ClientError
from boto3.dynamodb.conditions import Key, Attr, In
from jsonschema import validate
from chalicelib import load_api_schema, replace_decimals

metadata_api = Blueprint(__name__)

# Environment variables defined in the CDK stack
FRAME_TABLE_NAME = os.environ['FRAME_TABLE_NAME']
CHUNK_TABLE_NAME = os.environ['CHUNK_TABLE_NAME']
CHUNK_STARTPTS_INDEX = os.environ['CHUNK_STARTPTS_INDEX']
authorizer = IAMAuthorizer()

ddb_resource = boto3.resource("dynamodb")
API_SCHEMA = load_api_schema()

@metadata_api.route('/metadata/frame', cors=True, methods=['POST'], authorizer=authorizer)
def store_frame():
    """
    Store one or more frames in the datastore.

    Body:

    .. code-block:: python

        {
            "Program": string,
            "Event": string,
            "Filename": string,
            "Frames": list
        }

    Returns:

        None
    
    Raises:
        500 - ChaliceViewError
    """
    try:
        
        frame = json.loads(metadata_api.current_app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=frame, schema=API_SCHEMA["store_frame"])

        print("Got a valid frame schema")

        program = frame["Program"]
        event = frame["Event"]
        filename = frame["Filename"]
        frames = frame["Frames"]

        print(
            f"Storing '{len(frames)}' frames of file '{filename}' for program '{program}' and event '{event}' in the DynamoDB table '{FRAME_TABLE_NAME}'")

        frame_table = ddb_resource.Table(FRAME_TABLE_NAME)

        with frame_table.batch_writer() as batch:
            for frame in frames:
                frame["Id"] = f"{program}#{event}#{filename}"
                frame["ProgramEvent"] = f"{program}#{event}"

                batch.put_item(
                    Item=frame
                )

    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")
        error = e.response['Error']['Message']
        print(
            f"Unable to store one or more frames of file '{filename}' for program '{program}' and event '{event}': {str(error)}")
        raise ChaliceViewError(
            f"Unable to store one or more frames of file '{filename}' for program '{program}' and event '{event}': {str(error)}")

    except Exception as e:
        print(
            f"Unable to store one or more frames of file '{filename}' for program '{program}' and event '{event}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to store one or more frames of file '{filename}' for program '{program}' and event '{event}': {str(e)}")

    else:
        return {}


@metadata_api.route('/metadata/chunk', cors=True, methods=['POST'], authorizer=authorizer)
def store_chunk_metadata():
    """
    Store the HLS Segment (Chunk) metadata in the datastore

    Body:

    .. code-block:: python

        {
            "Program": string,
            "Event": string,
            "Profile": string,
            "Filename": string,
            "Start": number,
            "StartPts": number,
            "Duration": number,
            "S3Bucket": string,
            "S3Key": string
        }

    Returns:

        None
    
    Raises:
        500 - ChaliceViewError
    """
    try:
        chunk = json.loads(metadata_api.current_app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=chunk, schema=API_SCHEMA["store_chunk_metadata"])

        print("Got a valid chunk schema")

        program = chunk["Program"]
        event = chunk["Event"]
        filename = chunk["Filename"]

        print(
            f"Storing the metadata of the HLS Segment (Chunk) '{filename}' for program '{program}' and event '{event}' in the DynamoDB table '{CHUNK_TABLE_NAME}'")

        chunk_table = ddb_resource.Table(CHUNK_TABLE_NAME)

        chunk["PK"] = f"{program}#{event}"

        chunk_table.put_item(
            Item=chunk
        )

    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")
        error = e.response['Error']['Message']
        print(
            f"Unable to store the metadata of the HLS Segment (Chunk) '{filename}' for program '{program}' and event '{event}': {str(error)}")
        raise ChaliceViewError(
            f"Unable to store the metadata of the HLS Segment (Chunk) '{filename}' for program '{program}' and event '{event}': {str(error)}")

    except Exception as e:
        print(
            f"Unable to store the metadata of the HLS Segment (Chunk) '{filename}' for program '{program}' and event '{event}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to store the metadata of the HLS Segment (Chunk) '{filename}' for program '{program}' and event '{event}': {str(e)}")

    else:
        return {}

@metadata_api.route('/metadata/chunk/start/{program}/{event}/{profile}/{reference_time}', cors=True, methods=['GET'],
           authorizer=authorizer)
def get_chunk_start_time(program, event, profile, reference_time):
    """
    Get the HLS Segment (Chunk) start time based on the given reference time.
    By default, return the presentation (PTS) start timecode of the chunk as identified from the MPEG transport stream.

    The PTS timecode is usually not zero-based, i.e., the PTS timecode of the first frame in a video doesn't necessarily start at 00:00.
    PTS timecodes are ideal for accurately clipping a video given the start and end timecodes using tools such as ffmpeg. 
    
    For certain use-cases, a zero-based start timecode may be needed and can be retrieved by including the query parameter "pts=false".

    Returns:

        The HLS Segment (Chunk) start time that is less than the given reference time. Returns None if no chunk is found with 
        start time less than the given reference time.
    
    Raises:
        500 - ChaliceViewError
    """
    try:
        program = urllib.parse.unquote(program)
        event = urllib.parse.unquote(event)
        profile = urllib.parse.unquote(profile)
        reference_time = urllib.parse.unquote(reference_time)

        print(
            f"Getting the chunk start time for program '{program}' and event '{event}' based on the reference time '{reference_time}'")

        chunk_table = ddb_resource.Table(CHUNK_TABLE_NAME)

        query_params = metadata_api.current_app.current_request.query_params

        if query_params and query_params.get("pts") == "false":
            pts = False

            response = chunk_table.query(
                KeyConditionExpression=Key("PK").eq(f"{program}#{event}") & Key("Start").lte(Decimal(reference_time)),
                FilterExpression=Attr("Profile").eq(profile),
                ProjectionExpression="#Start",
                ExpressionAttributeNames={
                    "#Start": "Start"
                },
                ScanIndexForward=False,
                Limit=1,
                ConsistentRead=True
            )

        else:
            pts = True

            response = chunk_table.query(
                IndexName=CHUNK_STARTPTS_INDEX,
                KeyConditionExpression=Key("PK").eq(f"{program}#{event}") & Key("StartPts").lte(
                    Decimal(reference_time)),
                FilterExpression=Attr("Profile").eq(profile),
                ProjectionExpression="StartPts",
                ScanIndexForward=False,
                Limit=1,
                ConsistentRead=True
            )

        if "Items" not in response or len(response["Items"]) < 1:
            print(
                f"Chunk start time not found for program '{program}' and event '{event}' based on the reference time '{reference_time}'")
            return None

    except Exception as e:
        print(
            f"Unable to get the chunk start time for program '{program}' and event '{event}' based on the reference time '{reference_time}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to get the chunk start time for program '{program}' and event '{event}' based on the reference time '{reference_time}': {str(e)}")

    else:
        if pts:
            return replace_decimals(response["Items"][0]["StartPts"])

        return replace_decimals(response["Items"][0]["Start"])

@metadata_api.route('/metadata/timecode/{program}/{event}/{filename}/{frame_number}', cors=True, methods=['GET'],
           authorizer=authorizer)
def get_timecode_of_frame(program, event, filename, frame_number):
    """
    Get the timecode of a frame by Program, Event, Filename and FrameNumber.
    By default, return the presentation (PTS) timecode of a frame as identified from the MPEG transport stream.

    The PTS timecode is usually not zero-based, i.e., the PTS timecode of the first frame in a video doesn't necessarily start at 00:00.
    PTS timecodes are ideal for accurately clipping a video given the start and end timecodes using tools such as ffmpeg. 
    
    For certain use-cases, a zero-based frame timecode may be needed and can be retrieved by including the query parameter "pts=false".

    Returns:

        Timecode of a frame
    
    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        program = urllib.parse.unquote(program)
        event = urllib.parse.unquote(event)
        filename = urllib.parse.unquote(filename)
        frame_number = urllib.parse.unquote(frame_number)

        print(
            f"Getting the timecode of frame '{frame_number}' in file '{filename}' for program '{program}' and event '{event}'")

        # Convert frame_number from a string of integer/float to integer
        frame_number = int(float(frame_number))

        query_params = metadata_api.current_app.current_request.query_params

        if query_params and query_params.get("pts") == "false":
            pts = False
        else:
            pts = True

        frame_table = ddb_resource.Table(FRAME_TABLE_NAME)

        response = frame_table.query(
            KeyConditionExpression=Key("Id").eq(f"{program}#{event}#{filename}") & Key("FrameNumber").lte(frame_number),
            FilterExpression=Attr("KeyFrame").eq(1),
            ProjectionExpression="FrameNumber, FramePtsTime, FrameTime, DurationTime",
            ScanIndexForward=False,
            Limit=1,
            ConsistentRead=True
        )

        if "Items" not in response or len(response["Items"]) < 1:
            raise NotFoundError(
                f"Frame '{frame_number}' not found in file '{filename}' for program '{program}' and event '{event}'")

        key_frame = replace_decimals(response["Items"][0])
        key_frame_number = key_frame["FrameNumber"]
        key_frame_time = key_frame["FrameTime"]
        key_frame_pts_time = key_frame["FramePtsTime"]
        key_frame_duration = key_frame["DurationTime"]

        if frame_number == key_frame_number:
            frame_time = key_frame_time
            frame_pts_time = key_frame_pts_time
        else:
            diff = frame_number - key_frame_number
            frame_time = round(key_frame_time + (diff * key_frame_duration), 3)
            frame_pts_time = round(key_frame_pts_time + (diff * key_frame_duration), 3)

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(
            f"Unable to get the timecode of frame '{frame_number}' in file '{filename}' for program '{program}' and event '{event}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to get the timecode of frame '{frame_number}' in file '{filename}' for program '{program}' and event '{event}': {str(e)}")

    else:
        if pts:
            return frame_pts_time

        return frame_time
