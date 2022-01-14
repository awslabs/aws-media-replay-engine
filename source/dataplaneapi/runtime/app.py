# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import json
import urllib.parse
import boto3
import decimal

from decimal import Decimal
from datetime import datetime
from chalice import Chalice
from chalice import IAMAuthorizer
from chalice import ChaliceViewError, BadRequestError, NotFoundError
from botocore.config import Config
from botocore.client import ClientError
from boto3.dynamodb.conditions import Key, Attr, In
from jsonschema import validate, ValidationError

from chalicelib import load_api_schema, replace_decimals

app = Chalice(app_name='aws-mre-dataplane-api')

API_VERSION = '1.0.0'

# Environment variables defined in the CDK stack
FRAME_TABLE_NAME = os.environ['FRAME_TABLE_NAME']
CHUNK_TABLE_NAME = os.environ['CHUNK_TABLE_NAME']
CHUNK_STARTPTS_INDEX = os.environ['CHUNK_STARTPTS_INDEX']
PLUGIN_RESULT_TABLE_NAME = os.environ['PLUGIN_RESULT_TABLE_NAME']
CLIP_PREVIEW_FEEDBACK_TABLE_NAME = os.environ['CLIP_PREVIEW_FEEDBACK_TABLE_NAME']
EB_EVENT_BUS_NAME = os.environ['EB_EVENT_BUS_NAME']
REPLAY_RESULT_TABLE_NAME = os.environ['REPLAY_RESULT_TABLE_NAME']
PROGRAM_EVENT_INDEX = os.environ['PROGRAM_EVENT_INDEX']
CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_TRACK_INDEX = os.environ['CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_TRACK_INDEX']
CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_CLASSIFIER_START_INDEX = os.environ[
    'CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_CLASSIFIER_START_INDEX']

authorizer = IAMAuthorizer()

ddb_resource = boto3.resource("dynamodb")
s3_client = boto3.client("s3")
eb_client = boto3.client("events")

API_SCHEMA = load_api_schema()


@app.route('/version', cors=True, methods=['GET'], authorizer=authorizer)
def version():
    """
    Get the data plane api version number.

    Returns:

        Dictionary containing Data plane api version number.

        .. code-block:: python
        
            {
                "api_version": "x.x.x"
            }
    """
    return {
        "api_version": API_VERSION
    }


@app.route('/manifest/{bucket}/{key}/{version}', cors=True, methods=['GET'], authorizer=authorizer)
def get_manifest_content(bucket, key, version):
    """
    Get the content of the HLS Manifest (.m3u8) file from S3.

    Returns:

        Content of the HLS Manifest (.m3u8) file.
    
    Raises:
        500 - ChaliceViewError
    """
    bucket = urllib.parse.unquote(bucket)
    key = urllib.parse.unquote(key)
    version = urllib.parse.unquote(version)

    print(f"Getting the HLS Manifest (.m3u8) file content from bucket={bucket} with key={key} and versionId={version}")

    try:
        response = s3_client.get_object(
            Bucket=bucket,
            Key=key,
            VersionId=version
        )

    except ClientError as e:
        error = e.response['Error']['Message']
        print(f"Unable to get the HLS Manifest file content from S3: {str(error)}")
        raise ChaliceViewError(f"Unable to get the HLS Manifest file content from S3: {str(error)}")

    except Exception as e:
        print(f"Unable to get the HLS Manifest file content from S3: {str(e)}")
        raise ChaliceViewError(f"Unable to get the HLS Manifest file content from S3: {str(e)}")

    else:
        return response['Body'].read().decode('utf-8')


@app.route('/media/{bucket}/{key}', cors=True, methods=['GET'], authorizer=authorizer)
def get_media_presigned_url(bucket, key):
    """
    Generate pre-signed URL for downloading the media (video) file from S3.

    Returns:

        S3 pre-signed URL for downloading the media (video) file.
    
    Raises:
        500 - ChaliceViewError
    """
    bucket = urllib.parse.unquote(bucket)
    key = urllib.parse.unquote(key)

    print(
        f"Generating S3 pre-signed URL for downloading the media file content from bucket '{bucket}' with key '{key}'")

    s3 = boto3.client('s3', config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'}))

    try:
        response = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': bucket,
                'Key': key
            },
            ExpiresIn=300
        )

    except ClientError as e:
        print(f"Got S3 ClientError: {str(e)}")
        error = e.response['Error']['Message']
        print(f"Unable to generate S3 pre-signed URL for bucket '{bucket}' with key '{key}': {str(error)}")
        raise ChaliceViewError(
            f"Unable to generate S3 pre-signed URL for bucket '{bucket}' with key '{key}': {str(error)}")

    except Exception as e:
        print(f"Unable to generate S3 pre-signed URL for bucket '{bucket}' with key '{key}': {str(e)}")
        raise ChaliceViewError(f"Unable to generate S3 pre-signed URL for bucket '{bucket}' with key '{key}': {str(e)}")

    else:
        return response


@app.route('/metadata/frame', cors=True, methods=['POST'], authorizer=authorizer)
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
        frame = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

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


@app.route('/metadata/chunk', cors=True, methods=['POST'], authorizer=authorizer)
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
        chunk = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

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


@app.route('/metadata/chunk/start/{program}/{event}/{profile}/{reference_time}', cors=True, methods=['GET'],
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

        query_params = app.current_request.query_params

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


@app.route('/metadata/timecode/{program}/{event}/{filename}/{frame_number}', cors=True, methods=['GET'],
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

        query_params = app.current_request.query_params

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


def put_events_to_event_bridge(plugin_class, segment):
    try:
        segment = replace_decimals(segment)

        if plugin_class == "Classifier":
            segment_start = segment["Start"]
            segment_end = segment["End"] if "End" in segment else None
            detail_type = "Segmentation Status"

            if segment_end is None or segment_start == segment_end:
                state = "SEGMENT_START"
            else:
                state = "SEGMENT_END"

        elif plugin_class == "Optimizer":
            detail_type = "Optimization Status"

            if "OptoEnd" in segment and segment["OptoEnd"]:
                state = "OPTIMIZED_SEGMENT_END"
            elif "OptoStart" in segment and segment["OptoStart"]:
                state = "OPTIMIZED_SEGMENT_START"

        print(f"Sending an event for '{detail_type}' to EventBridge with state '{state}' for the segment '{segment}'")

        detail = {
            "State": state,
            "Segment": segment
        }

        response = eb_client.put_events(
            Entries=[
                {
                    "Source": "awsmre",
                    "DetailType": detail_type,
                    "Detail": json.dumps(detail),
                    "EventBusName": EB_EVENT_BUS_NAME
                }
            ]
        )

        if response["FailedEntryCount"] > 0:
            print(
                f"Failed to send an event for '{detail_type}' to EventBridge with state '{state}' for the segment '{segment}'. More details below:")
            print(response["Entries"])

    except Exception as e:
        print(f"Unable to send an event to EventBridge for the segment '{segment}': {str(e)}")


@app.route('/plugin/result', cors=True, methods=['POST'], authorizer=authorizer)
def store_plugin_result():
    """
    Store the result of a plugin in a DynamoDB table.

    Body:

    .. code-block:: python

        {
            "Program": string,
            "Event": string,
            "ProfileName": string,
            "ChunkSize": integer,
            "ProcessingFrameRate": integer,
            "Classifier": string,
            "ExecutionId": string,
            "AudioTrack": integer,
            "Filename": string,
            "ChunkNumber": integer,
            "PluginName": string,
            "PluginClass": string,
            "ModelEndpoint": string,
            "Configuration": object,
            "OutputAttributesNameList": list,
            "Location": object,
            "Results": list
        }

    Returns:

        None
    
    Raises:
        400 - BadRequestError
        500 - ChaliceViewError
    """
    try:
        result = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=result, schema=API_SCHEMA["store_plugin_result"])

        print("Got a valid plugin result schema")

        program = result["Program"]
        event = result["Event"]
        plugin_name = result["PluginName"]
        plugin_class = result["PluginClass"]
        audio_track = str(result["AudioTrack"]) if "AudioTrack" in result else None
        results = result["Results"]

        print(
            f"Storing the result of program '{program}', event '{event}', plugin '{plugin_name}' in the DynamoDB table '{PLUGIN_RESULT_TABLE_NAME}'")
        print(f"Number of items to store: {len(results)}")

        plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

        # If the plugin class is Optimizer, append the results to existing items in DynamoDB
        if plugin_class == "Optimizer":
            classifier = result["Classifier"]
            opto_audio_track = audio_track if audio_track is not None else "1"

            for item in results:
                is_update_required = False
                update_expression = []
                expression_attribute_names = {}
                expression_attribute_values = {}

                if "OptoStartCode" in item:
                    is_update_required = True
                    update_expression.append("#OptoStartCode = :OptoStartCode")
                    expression_attribute_names["#OptoStartCode"] = "OptoStartCode"
                    expression_attribute_values[":OptoStartCode"] = item["OptoStartCode"]

                    if "OptoStart" in item:
                        update_expression.append("#OptoStart.#AudioTrack = :OptoStart")
                        expression_attribute_names["#OptoStart"] = "OptoStart"
                        expression_attribute_names["#AudioTrack"] = opto_audio_track
                        expression_attribute_values[":OptoStart"] = round(item["OptoStart"], 3)

                        if "OptoStartDescription" in item:
                            update_expression.append("#OptoStartDescription = :OptoStartDescription")
                            expression_attribute_names["#OptoStartDescription"] = "OptoStartDescription"
                            expression_attribute_values[":OptoStartDescription"] = item["OptoStartDescription"]

                        if "OptoStartDetectorResults" in item:
                            update_expression.append("#OptoStartDetectorResults = :OptoStartDetectorResults")
                            expression_attribute_names["#OptoStartDetectorResults"] = "OptoStartDetectorResults"
                            expression_attribute_values[":OptoStartDetectorResults"] = item["OptoStartDetectorResults"]

                if "OptoEndCode" in item:
                    is_update_required = True
                    update_expression.append("#OptoEndCode = :OptoEndCode")
                    expression_attribute_names["#OptoEndCode"] = "OptoEndCode"
                    expression_attribute_values[":OptoEndCode"] = item["OptoEndCode"]

                    if "OptoEnd" in item:
                        update_expression.append("#OptoEnd.#AudioTrack = :OptoEnd")
                        expression_attribute_names["#OptoEnd"] = "OptoEnd"
                        expression_attribute_names["#AudioTrack"] = opto_audio_track
                        expression_attribute_values[":OptoEnd"] = round(item["OptoEnd"], 3)

                        if "OptoEndDescription" in item:
                            update_expression.append("#OptoEndDescription = :OptoEndDescription")
                            expression_attribute_names["#OptoEndDescription"] = "OptoEndDescription"
                            expression_attribute_values[":OptoEndDescription"] = item["OptoEndDescription"]

                        if "OptoEndDetectorResults" in item:
                            update_expression.append("#OptoEndDetectorResults = :OptoEndDetectorResults")
                            expression_attribute_names["#OptoEndDetectorResults"] = "OptoEndDetectorResults"
                            expression_attribute_values[":OptoEndDetectorResults"] = item["OptoEndDetectorResults"]

                if is_update_required:
                    print(f"Updating existing segment having Start={item['Start']} with the Optimizer plugin result")

                    plugin_result_table.update_item(
                        Key={
                            "PK": f"{program}#{event}#{classifier}",
                            "Start": item["Start"]
                        },
                        UpdateExpression="SET " + ", ".join(update_expression),
                        ExpressionAttributeNames=expression_attribute_names,
                        ExpressionAttributeValues=expression_attribute_values
                    )

                    item["Program"] = program
                    item["Event"] = event
                    item["ProfileName"] = result["ProfileName"]
                    item["PluginClass"] = result["PluginClass"]
                    item["Classifier"] = classifier
                    item["AudioTrack"] = opto_audio_track

                    # Send the Optimization status to EventBridge
                    put_events_to_event_bridge(plugin_class, item)

        # If the plugin class is Labeler, append the results to existing items in DynamoDB
        elif plugin_class == "Labeler":
            classifier = result["Classifier"]

            for item in results:
                update_expression = []
                expression_attribute_names = {}
                expression_attribute_values = {}

                if "LabelCode" in item:
                    update_expression.append("#LabelCode = :LabelCode")
                    expression_attribute_names["#LabelCode"] = "LabelCode"
                    expression_attribute_values[":LabelCode"] = item["LabelCode"]

                    if "Label" in item:
                        update_expression.append("#Label = :Label")
                        expression_attribute_names["#Label"] = "Label"
                        expression_attribute_values[":Label"] = item["Label"]

                    if "OutputAttributesNameList" in result:
                        for index, output_attribute in enumerate(result["OutputAttributesNameList"]):
                            if output_attribute in item and output_attribute != "Label":
                                update_expression.append(f"#OutAttr{index} = :OutAttr{index}")
                                expression_attribute_names[f"#OutAttr{index}"] = output_attribute
                                expression_attribute_values[f":OutAttr{index}"] = item[output_attribute]

                    print(f"Updating existing segment having Start={item['Start']} with the Labeler plugin result")

                    plugin_result_table.update_item(
                        Key={
                            "PK": f"{program}#{event}#{classifier}",
                            "Start": item["Start"]
                        },
                        UpdateExpression="SET " + ", ".join(update_expression),
                        ExpressionAttributeNames=expression_attribute_names,
                        ExpressionAttributeValues=expression_attribute_values
                    )

        else:
            with plugin_result_table.batch_writer() as batch:
                if audio_track is not None:
                    pk = f"{program}#{event}#{plugin_name}#{audio_track}"
                else:
                    pk = f"{program}#{event}#{plugin_name}"

                for item in results:
                    if plugin_class == "Classifier":
                        if "OptoStartCode" not in item:
                            item["OptoStartCode"] = "Not Attempted"
                            item["OptoStart"] = {}
                            item["OriginalClipStatus"] = {}
                            item["OriginalClipLocation"] = {}
                            item["OptimizedClipStatus"] = {}
                            item["OptimizedClipLocation"] = {}

                        if "End" in item and "OptoEndCode" not in item:
                            item["OptoEndCode"] = "Not Attempted"
                            item["OptoEnd"] = {}
                            item["LabelCode"] = "Not Attempted"
                            item["Label"] = ""

                    item["PK"] = pk
                    item["Start"] = round(item["Start"], 3)
                    item["End"] = round(item["End"], 3) if "End" in item else item["Start"]
                    item["ProgramEvent"] = f"{program}#{event}"
                    item["Program"] = program
                    item["Event"] = event
                    item["ProfileName"] = result["ProfileName"]
                    item["ChunkSize"] = result["ChunkSize"]
                    item["ProcessingFrameRate"] = result["ProcessingFrameRate"]
                    item["ExecutionId"] = result["ExecutionId"]
                    item["PluginName"] = plugin_name
                    item["Filename"] = result["Filename"]
                    item["ChunkNumber"] = result["ChunkNumber"]
                    item["PluginClass"] = result["PluginClass"]
                    item["ModelEndpoint"] = result["ModelEndpoint"] if "ModelEndpoint" in result else ""
                    item["Configuration"] = result["Configuration"] if "Configuration" in result else {}
                    item["Location"] = result["Location"]

                    if audio_track is not None:
                        item["AudioTrack"] = audio_track

                    batch.put_item(
                        Item=item
                    )

                    # Send the Segmentation status to EventBridge
                    if plugin_class == "Classifier":
                        put_events_to_event_bridge(plugin_class, item)

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")
        error = e.response['Error']['Message']
        print(
            f"Unable to store the result of program '{program}', event '{event}', plugin '{plugin_name}' in the DynamoDB table '{PLUGIN_RESULT_TABLE_NAME}': {str(error)}")
        raise ChaliceViewError(
            f"Unable to store the result of program '{program}', event '{event}', plugin '{plugin_name}' in the DynamoDB table '{PLUGIN_RESULT_TABLE_NAME}': {str(error)}")

    except Exception as e:
        print(
            f"Unable to store the result of program '{program}', event '{event}', plugin '{plugin_name}' in the DynamoDB table '{PLUGIN_RESULT_TABLE_NAME}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to store the result of program '{program}', event '{event}', plugin '{plugin_name}' in the DynamoDB table '{PLUGIN_RESULT_TABLE_NAME}': {str(e)}")

    else:
        return {}


@app.route('/workflow/segment/state', cors=True, methods=['POST'], authorizer=authorizer)
def get_segment_state():
    """
    Retrieve the state of the segment identified in chunks (HLS .ts files) prior to the given chunk number and all the 
    labels created by the dependent plugins after that segment was found. If no segment was identified in prior chunks, 
    return None along with all the labels created by the dependent plugins before the given chunk number.
    
    Segment identified in prior chunks can be either complete or partial. Complete segments have both their "start" and 
    "end" times identified whereas partial segments have only their "start" time identified.

    Body:

    .. code-block:: python

        {
            "Program": string,
            "Event": string,
            "PluginName": string,
            "DependentPlugins": list,
            "ChunkNumber": integer,
            "ChunkStart": number,
            "MaxSegmentLength": integer
        }

    Returns:

        List containing the state of the segment identified in prior chunks along with the labels created by the dependent plugins
    
    Raises:
        400 - BadRequestError
        500 - ChaliceViewError
    """
    try:
        chunk = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=chunk, schema=API_SCHEMA["get_segment_state"])

        print("Got a valid chunk schema")

        program = chunk["Program"]
        event = chunk["Event"]
        plugin_name = chunk["PluginName"]
        dependent_plugins = chunk["DependentPlugins"]
        chunk_number = chunk["ChunkNumber"]
        chunk_start = chunk["ChunkStart"]
        max_segment_length = chunk["MaxSegmentLength"]

        print(
            f"Getting the state of the segment identified in prior chunks for program '{program}', event '{event}', plugin '{plugin_name}' and chunk number '{chunk_number}'")

        output = [None, {}, []]

        plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

        response = plugin_result_table.query(
            KeyConditionExpression=Key("PK").eq(f"{program}#{event}#{plugin_name}"),
            FilterExpression=Attr("ChunkNumber").lt(chunk_number),
            ScanIndexForward=False,
            Limit=1,
            ConsistentRead=True
        )

        if "Items" not in response or len(response["Items"]) < 1:
            print(
                f"No segment was identified in prior chunks for program '{program}', event '{event}', plugin '{plugin_name}' and chunk number '{chunk_number}'")
            start_key_condition = chunk_start - max_segment_length

        else:
            print(
                f"A segment was identified in prior chunks for program '{program}', event '{event}', plugin '{plugin_name}' and chunk number '{chunk_number}'")

            prior_segment = response["Items"][0]
            prior_segment_start = prior_segment["Start"]
            prior_segment_end = prior_segment["End"] if "End" in prior_segment else None

            if prior_segment_end is None or prior_segment_start == prior_segment_end:  # Partial segment
                print("Prior segment is partial as only the 'Start' time is identified")
                output[0] = "Start"
                output[1] = prior_segment
                start_key_condition = prior_segment_start

            else:  # Complete segment
                print("Prior segment is complete as both the 'Start' and 'End' times are identified")
                output[0] = "End"
                output[1] = prior_segment
                start_key_condition = prior_segment_end

        print(
            f"Retrieving all the labels created by the dependent plugins '{dependent_plugins}' since '{start_key_condition}'")

        for d_plugin in dependent_plugins:
            key_condition_expr = Key("PK").eq(f"{program}#{event}#{d_plugin}") & Key("Start").gt(start_key_condition)

            response = plugin_result_table.query(
                KeyConditionExpression=key_condition_expr,
                FilterExpression=Attr("ChunkNumber").lte(chunk_number),
                ConsistentRead=True
            )

            output[2].extend(response["Items"])

            while "LastEvaluatedKey" in response:
                response = plugin_result_table.query(
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                    KeyConditionExpression=key_condition_expr,
                    FilterExpression=Attr("ChunkNumber").lte(chunk_number),
                    ConsistentRead=True
                )

                output[2].extend(response["Items"])

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except Exception as e:
        print(
            f"Unable to get the state of the segment identified in prior chunks for program '{program}', event '{event}', plugin '{plugin_name}' and chunk number '{chunk_number}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to get the state of the segment identified in prior chunks for program '{program}', event '{event}', plugin '{plugin_name}' and chunk number '{chunk_number}': {str(e)}")

    else:
        return replace_decimals(output)


def get_labeler_dependent_plugins_output(program, event, dependent_plugins, start, end):
    if not dependent_plugins:
        print(
            f"Skipping the retrieval of Labeler dependent plugins output as no dependent plugin is present in the request")
        return []

    dependent_plugins_output = {}

    plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

    for dependent_plugin in dependent_plugins:
        response = plugin_result_table.query(
            KeyConditionExpression=Key("PK").eq(f"{program}#{event}#{dependent_plugin}") & Key("Start").between(start,
                                                                                                                end),
            ConsistentRead=True
        )

        dependent_plugins_output[dependent_plugin] = response["Items"]

        while "LastEvaluatedKey" in response:
            response = plugin_result_table.query(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("PK").eq(f"{program}#{event}#{dependent_plugin}") & Key("Start").between(
                    start, end),
                ConsistentRead=True
            )

            dependent_plugins_output[dependent_plugin].extend(response["Items"])

    return dependent_plugins_output


@app.route('/workflow/labeling/segment/state', cors=True, methods=['POST'], authorizer=authorizer)
def get_segment_state_for_labeling():
    """
    Retrieve one or more complete segments that are not associated with a Label yet. Besides retrieving the segments, 
    get all the data identified by the Labeler dependent plugins between the start and end of the segments. If no dependent 
    plugins data is found, return an empty object with the segments.

    Body:

    .. code-block:: python

        {
            "Program": string,
            "Event": string,
            "Classifier": string,
            "DependentPlugins": list,
            "ChunkNumber": integer
        }

    Returns:

        List containing the complete segments along with the associated data created by the Labeler dependent plugins
    
    Raises:
        400 - BadRequestError
        500 - ChaliceViewError
    """
    try:
        request = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=request, schema=API_SCHEMA["get_segment_state_for_labeling"])

        print("Got a valid schema")

        program = request["Program"]
        event = request["Event"]
        classifier = request["Classifier"]
        dependent_plugins = request["DependentPlugins"]
        chunk_number = request["ChunkNumber"]

        print(
            f"Getting the complete, unlabeled segments for program '{program}', event '{event}', classifier '{classifier}' and chunk number '{chunk_number}'")

        output = []

        plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

        response = plugin_result_table.query(
            KeyConditionExpression=Key("PK").eq(f"{program}#{event}#{classifier}"),
            FilterExpression=Attr("ChunkNumber").lte(chunk_number) & Attr("LabelCode").eq("Not Attempted"),
            ConsistentRead=True
        )

        if "Items" not in response or len(response["Items"]) < 1:
            print(
                f"No unlabeled segments found for program '{program}', event '{event}', classifier '{classifier}' and chunk number '{chunk_number}'")

        else:
            print(
                f"One or more unlabeled segments found for program '{program}', event '{event}', classifier '{classifier}' and chunk number '{chunk_number}'")

            segments = response["Items"]

            while "LastEvaluatedKey" in response:
                response = plugin_result_table.query(
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                    KeyConditionExpression=Key("PK").eq(f"{program}#{event}#{classifier}"),
                    FilterExpression=Attr("ChunkNumber").lte(chunk_number) & Attr("LabelCode").eq("Not Attempted"),
                    ConsistentRead=True
                )

                segments.extend(response["Items"])

            for segment in segments:
                segment_start = segment["Start"]
                segment_end = segment["End"] if "End" in segment else None

                # Get the Labeler dependent plugins output for the segment only if it is complete
                if segment_end is not None and segment_start != segment_end:
                    print(
                        f"Getting all the Labeler dependent plugins output between the segment Start '{segment_start}' and End '{segment_end}'")
                    dependent_plugins_output = get_labeler_dependent_plugins_output(program, event, dependent_plugins,
                                                                                    segment_start, segment_end)

                    output.append(
                        {
                            "Segment": segment,
                            "DependentPluginsOutput": dependent_plugins_output
                        }
                    )

                else:
                    print(f"Skipping the segment with Start '{segment_start}' as it is not a complete segment")

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except Exception as e:
        print(
            f"Unable to get the complete, unlabeled segments along with the associated dependent plugins result for program '{program}', event '{event}', classifier '{classifier}' and chunk number '{chunk_number}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to get the complete, unlabeled segments along with the associated dependent plugins result for program '{program}', event '{event}', classifier '{classifier}' and chunk number '{chunk_number}': {str(e)}")

    else:
        return replace_decimals(output)


def get_detectors_output_for_segment(program, event, detectors, search_win_sec, audio_track, start=None, end=None):
    if not detectors:
        print(f"Skipping the retrieval of dependent detectors output as no detector plugin is present in the request")
        return []

    detectors_output = []

    plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

    for detector in detectors:
        detector_name = detector["Name"]
        detector_media_type = detector["SupportedMediaType"]

        detector_obj = {
            "DependentDetector": detector_name
        }

        if detector_media_type == "Audio":
            if audio_track is None:
                raise BadRequestError(
                    f"Unable to get the segment state for optimization: Error in retrieving the output of the dependent detector '{detector_name}' with an audio track of 'None'")

            pk = f"{program}#{event}#{detector_name}#{audio_track}"
        else:
            pk = f"{program}#{event}#{detector_name}"

        if start:
            response = plugin_result_table.query(
                KeyConditionExpression=Key("PK").eq(pk) & Key("Start").lte(start),
                FilterExpression=Attr("End").gte(start),
                ConsistentRead=True
            )

            if "Items" not in response or len(response["Items"]) < 1:
                response = plugin_result_table.query(
                    KeyConditionExpression=Key("PK").eq(pk),
                    FilterExpression=Attr("End").between(start - search_win_sec, start),
                    ConsistentRead=True
                )

                detector_obj["Start"] = response["Items"]

            else:
                detector_obj["Start"] = response["Items"]

        if end:
            response = plugin_result_table.query(
                KeyConditionExpression=Key("PK").eq(pk) & Key("Start").lte(end),
                FilterExpression=Attr("End").gte(end),
                ConsistentRead=True
            )

            if "Items" not in response or len(response["Items"]) < 1:
                response = plugin_result_table.query(
                    KeyConditionExpression=Key("PK").eq(pk) & Key("Start").between(end, end + search_win_sec),
                    ConsistentRead=True
                )

                detector_obj["End"] = response["Items"]

            else:
                detector_obj["End"] = response["Items"]

        detectors_output.append(detector_obj)

    return detectors_output


@app.route('/workflow/optimization/segment/state', cors=True, methods=['POST'], authorizer=authorizer)
def get_segment_state_for_optimization():
    """
    Retrieve one or more non-optimized segments identified in the current/prior chunks and all the dependent detectors output 
    around the segments for optimization. Use "SearchWindowSeconds" to control the time window around the segments within which 
    the dependent detectors output are queried for.

    Body:

    .. code-block:: python

        {
            "Program": string,
            "Event": string,
            "ChunkNumber": integer,
            "Classifier": string,
            "Detectors": list,
            "AudioTrack": integer,
            "SearchWindowSeconds": integer
        }

    Returns:

        List containing one or more non-optimized segments identified in the current/prior chunks along with all the dependent 
        detectors output around the segments
    
    Raises:
        400 - BadRequestError
        500 - ChaliceViewError
    """
    try:
        request = json.loads(app.current_request.raw_body.decode())

        validate(instance=request, schema=API_SCHEMA["get_segment_state_for_optimization"])

        print("Got a valid schema")

        program = request["Program"]
        event = request["Event"]
        chunk_number = request["ChunkNumber"]
        classifier = request["Classifier"]
        detectors = request["Detectors"] if "Detectors" in request else []
        audio_track = str(request["AudioTrack"]) if "AudioTrack" in request else None
        opto_audio_track = audio_track if audio_track is not None else "1"
        search_win_sec = request["SearchWindowSeconds"]

        output = []

        plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

        print(
            f"Getting all the non-optimized segments identified in the current/prior chunks for program '{program}', event '{event}', classifier '{classifier}' and chunk number '{chunk_number}'")

        response = plugin_result_table.query(
            KeyConditionExpression=Key("PK").eq(f"{program}#{event}#{classifier}"),
            FilterExpression=Attr("ChunkNumber").lte(chunk_number) & (
                    Attr("OptoStart").not_exists() | Attr(f"OptoStart.{opto_audio_track}").not_exists() | Attr(
                "OptoEnd").not_exists() | Attr(f"OptoEnd.{opto_audio_track}").not_exists()),
            ConsistentRead=True
        )

        if "Items" not in response or len(response["Items"]) < 1:
            print(
                f"No non-optimized segment was identified in the current/prior chunks for program '{program}', event '{event}', classifier '{classifier}' and chunk number '{chunk_number}'")

        else:
            print(
                f"Got one or more non-optimized segments identified in the current/prior chunks for program '{program}', event '{event}', classifier '{classifier}' and chunk number '{chunk_number}'")

            segments = response["Items"]

            while "LastEvaluatedKey" in response:
                response = plugin_result_table.query(
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                    KeyConditionExpression=Key("PK").eq(f"{program}#{event}#{classifier}"),
                    FilterExpression=Attr("ChunkNumber").lte(chunk_number) & (Attr("OptoStart").not_exists() | Attr(
                        f"OptoStart.{opto_audio_track}").not_exists() | Attr("OptoEnd").not_exists() | Attr(
                        f"OptoEnd.{opto_audio_track}").not_exists()),
                    ConsistentRead=True
                )

                segments.extend(response["Items"])

            for segment in segments:
                segment_start = segment["Start"]
                segment_end = segment["End"] if "End" in segment else None

                print(
                    f"Getting all the dependent detectors output around segment Start '{segment_start}' within a search window of '{search_win_sec}' seconds")

                # Get dependent detectors output for optimizing the segment Start
                detectors_output = get_detectors_output_for_segment(program, event, detectors, search_win_sec,
                                                                    audio_track, start=segment_start)

                # Get dependent detectors output for optimizing the segment End if segment End is present
                if segment_end is not None and segment_start != segment_end:
                    print(
                        f"Getting all the dependent detectors output around segment End '{segment_end}' within a search window of '{search_win_sec}' seconds")

                    detectors_output.extend(
                        get_detectors_output_for_segment(program, event, detectors, search_win_sec, audio_track,
                                                         end=segment_end))

                output.append(
                    {
                        "Segment": segment,
                        "DependentDetectorsOutput": detectors_output
                    }
                )

    except BadRequestError as e:
        print(f"Got chalice BadRequestError: {str(e)}")
        raise

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except Exception as e:
        print(
            f"Unable to get the non-optimized segments and dependent detectors output for program '{program}', event '{event}' and chunk number '{chunk_number}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to get the non-optimized segments and dependent detectors output for program '{program}', event '{event}' and chunk number '{chunk_number}': {str(e)}")

    else:
        return replace_decimals(output)


@app.route('/workflow/engine/clipgen/segments', cors=True, methods=['POST'], authorizer=authorizer)
def get_segments_for_clip_generation():
    """
    Retrieve non-optimized and optimized segments for a given program and event which are then used as an input 
    for the MRE Clip Generation Engine.

    Body:

    .. code-block:: python

        {
            "Program": string,
            "Event": string,
            "Classifier": string
        }

    Returns:

        List containing non-optimized and optimized segments
    
    Raises:
        400 - BadRequestError
        500 - ChaliceViewError
    """
    try:
        request = json.loads(app.current_request.raw_body.decode())

        validate(instance=request, schema=API_SCHEMA["get_segments_for_clip_generation"])

        print("Got a valid schema")

        program = request["Program"]
        event = request["Event"]
        classifier = request["Classifier"]

        plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

        response = plugin_result_table.query(
            KeyConditionExpression=Key("PK").eq(f"{program}#{event}#{classifier}"),
            FilterExpression=Attr("OptoStart").exists() & Attr("OptoEnd").exists(),
            ProjectionExpression="PK, Start, End, OptoStart, OptoEnd",
            ConsistentRead=True
        )

        segments = response["Items"]

        while "LastEvaluatedKey" in response:
            response = plugin_result_table.query(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("PK").eq(f"{program}#{event}#{classifier}"),
                FilterExpression=Attr("OptoStart").exists() & Attr("OptoEnd").exists(),
                ProjectionExpression="PK, Start, End, OptoStart, OptoEnd",
                ConsistentRead=True
            )

            segments.extend(response["Items"])

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except Exception as e:
        print(
            f"Unable to get the non-optimized and optimized segments for program '{program}' and event '{event}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to get the non-optimized and optimized segments for program '{program}' and event '{event}': {str(e)}")

    else:
        return replace_decimals(segments)


@app.route('/workflow/engine/clipgen/chunks', cors=True, methods=['POST'], authorizer=authorizer)
def get_chunks_for_segment():
    """
    Retrieve the filename, location and duration of all the chunks that contain the provided segment 
    Start and End time.

    Body:

    .. code-block:: python

        {
            "Program": string,
            "Event": string,
            "Profile": string,
            "Start": number,
            "End": number
        }

    Returns:

        List containing the filename, location and duration of all the chunks
    
    Raises:
        400 - BadRequestError
        500 - ChaliceViewError
    """
    try:
        request = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=request, schema=API_SCHEMA["get_chunks_for_segment"])

        print("Got a valid schema")

        program = request["Program"]
        event = request["Event"]
        profile = request["Profile"]
        start = request["Start"]
        end = request["End"]

        chunks = []

        chunk_table_name = ddb_resource.Table(CHUNK_TABLE_NAME)

        print(
            f"Getting the latest chunk metadata before segment Start '{start}' in program '{program}', event '{event}'")

        response = chunk_table_name.query(
            KeyConditionExpression=Key("PK").eq(f"{program}#{event}") & Key("Start").lte(start),
            ProjectionExpression="#Filename, #Duration, #S3Bucket, #S3Key",
            FilterExpression=Attr("Profile").eq(profile),
            ExpressionAttributeNames={
                "#Filename": "Filename",
                "#Duration": "Duration",
                "#S3Bucket": "S3Bucket",
                "#S3Key": "S3Key"
            },
            ScanIndexForward=False,
            Limit=1,
            ConsistentRead=True
        )

        chunks.extend(response["Items"])

        print(
            f"Getting metadata of all the chunks between segment Start '{start}' and End '{end}' in program '{program}', event '{event}'")

        response = chunk_table_name.query(
            KeyConditionExpression=Key("PK").eq(f"{program}#{event}") & Key("Start").between(start, end),
            ProjectionExpression="#Filename, #Duration, #S3Bucket, #S3Key",
            FilterExpression=Attr("Profile").eq(profile),
            ExpressionAttributeNames={
                "#Filename": "Filename",
                "#Duration": "Duration",
                "#S3Bucket": "S3Bucket",
                "#S3Key": "S3Key"
            },
            ConsistentRead=True
        )

        chunks.extend(response["Items"])

        # DeDup logic to remove all the duplicate chunk metadata
        seen = []
        final_chunks = []

        for chunk in chunks:
            if chunk["Filename"] not in seen:
                seen.append(chunk["Filename"])
                final_chunks.append(chunk)

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except Exception as e:
        print(
            f"Unable to get all the chunk metadata for segment Start '{start}' and End '{end}' in program '{program}', event '{event}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to get all the chunk metadata for segment Start '{start}' and End '{end}' in program '{program}', event '{event}': {str(e)}")

    else:
        return replace_decimals(final_chunks)


@app.route('/clip/result', cors=True, methods=['POST'], authorizer=authorizer)
def store_clip_result():
    """
    Store the result of the MRE Clip Generation Engine in a DynamoDB table.

    Body:

    .. code-block:: python

        {
            "Program": string,
            "Event": string,
            "Classifier": string,
            "Results": list
        }

    Returns:

        None
    
    Raises:
        400 - BadRequestError
        500 - ChaliceViewError
    """
    try:
        result = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=result, schema=API_SCHEMA["store_clip_result"])

        print("Got a valid clip result schema")

        program = result["Program"]
        event = result["Event"]
        classifier = result["Classifier"]
        results = result["Results"]

        print(
            f"Storing the result of Clip Generation Engine for program '{program}' and event '{event}' in the DynamoDB table '{PLUGIN_RESULT_TABLE_NAME}'")
        print(f"Number of items to store: {len(results)}")

        plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

        for item in results:
            is_update_required = False
            update_expression = []
            expression_attribute_names = {}
            expression_attribute_values = {}

            audio_track = str(item["AudioTrack"]) if "AudioTrack" in item else "1"

            # Original segment
            if "OriginalClipStatus" in item:
                is_update_required = True
                update_expression.append("#OriginalClipStatus.#AudioTrack = :OriginalClipStatus")
                expression_attribute_names["#OriginalClipStatus"] = "OriginalClipStatus"
                expression_attribute_names["#AudioTrack"] = audio_track
                expression_attribute_values[":OriginalClipStatus"] = item["OriginalClipStatus"]

                if "OriginalClipLocation" in item:
                    update_expression.append("#OriginalClipLocation.#AudioTrack = :OriginalClipLocation")
                    expression_attribute_names["#OriginalClipLocation"] = "OriginalClipLocation"
                    expression_attribute_names["#AudioTrack"] = audio_track
                    expression_attribute_values[":OriginalClipLocation"] = item["OriginalClipLocation"]

                if "OriginalThumbnailLocation" in item:
                    update_expression.append("#OriginalThumbnailLocation = :OriginalThumbnailLocation")
                    expression_attribute_names["#OriginalThumbnailLocation"] = "OriginalThumbnailLocation"
                    expression_attribute_values[":OriginalThumbnailLocation"] = item["OriginalThumbnailLocation"]

            # Optimized segment
            if "OptimizedClipStatus" in item:
                is_update_required = True
                update_expression.append("#OptimizedClipStatus.#AudioTrack = :OptimizedClipStatus")
                expression_attribute_names["#OptimizedClipStatus"] = "OptimizedClipStatus"
                expression_attribute_names["#AudioTrack"] = audio_track
                expression_attribute_values[":OptimizedClipStatus"] = item["OptimizedClipStatus"]

                if "OptimizedClipLocation" in item:
                    update_expression.append("#OptimizedClipLocation.#AudioTrack = :OptimizedClipLocation")
                    expression_attribute_names["#OptimizedClipLocation"] = "OptimizedClipLocation"
                    expression_attribute_names["#AudioTrack"] = audio_track
                    expression_attribute_values[":OptimizedClipLocation"] = item["OptimizedClipLocation"]

                if "OptimizedThumbnailLocation" in item:
                    update_expression.append("#OptimizedThumbnailLocation = :OptimizedThumbnailLocation")
                    expression_attribute_names["#OptimizedThumbnailLocation"] = "OptimizedThumbnailLocation"
                    expression_attribute_values[":OptimizedThumbnailLocation"] = item["OptimizedThumbnailLocation"]

            if is_update_required:
                plugin_result_table.update_item(
                    Key={
                        "PK": f"{program}#{event}#{classifier}",
                        "Start": item["Start"]
                    },
                    UpdateExpression="SET " + ", ".join(update_expression),
                    ExpressionAttributeNames=expression_attribute_names,
                    ExpressionAttributeValues=expression_attribute_values
                )

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")
        error = e.response['Error']['Message']
        print(
            f"Unable to store the result of Clip Generation Engine for program '{program}' and event '{event}': {str(error)}")
        raise ChaliceViewError(
            f"Unable to store the result of Clip Generation Engine for program '{program}' and event '{event}': {str(error)}")

    except Exception as e:
        print(
            f"Unable to store the result of Clip Generation Engine for program '{program}' and event '{event}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to store the result of Clip Generation Engine for program '{program}' and event '{event}': {str(e)}")

    else:
        return {}


@app.route('/plugin/dependentplugins/output', cors=True, methods=['POST'], authorizer=authorizer)
def get_dependent_plugins_output():
    """
    Retrieve the output of one or more dependent plugins of a plugin for a given chunk number.

    Body:
    
    .. code-block:: python

        {
            "Program": string,
            "Event": string,
            "ChunkNumber": integer,
            "DependentPlugins": list,
            "AudioTrack": integer
        }

    Returns:

        Dictionary containing the output of one or more dependent plugins
    
    Raises:
        400 - BadRequestError
        500 - ChaliceViewError
    """
    try:
        request = json.loads(app.current_request.raw_body.decode())

        validate(instance=request, schema=API_SCHEMA["get_dependent_plugins_output"])

        print("Got a valid schema")

        program = request["Program"]
        event = request["Event"]
        chunk_number = request["ChunkNumber"]
        dependent_plugins = request["DependentPlugins"]
        audio_track = str(request["AudioTrack"]) if "AudioTrack" in request else None

        plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

        output = {}

        for d_plugin in dependent_plugins:
            d_plugin_name = d_plugin["Name"]
            d_plugin_media_type = d_plugin["SupportedMediaType"]
            
            print(
                f"Getting the output of dependent plugin '{d_plugin_name}' for program '{program}', event '{event}' and chunk number '{chunk_number}'")

            if d_plugin_media_type == "Audio":
                if audio_track is None:
                    raise BadRequestError(
                        f"Unable to get the output of dependent plugin '{d_plugin_name}' with an audio track of 'None'")

                pk = f"{program}#{event}#{d_plugin_name}#{audio_track}"
            else:
                pk = f"{program}#{event}#{d_plugin_name}"
            
            response = plugin_result_table.query(
                KeyConditionExpression=Key("PK").eq(pk),
                FilterExpression=Attr("ChunkNumber").eq(chunk_number),
                ConsistentRead=True
            )

            output[d_plugin_name] = response["Items"]

            while "LastEvaluatedKey" in response:
                response = plugin_result_table.query(
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                    KeyConditionExpression=Key("PK").eq(pk),
                    FilterExpression=Attr("ChunkNumber").eq(chunk_number),
                    ConsistentRead=True
                )

                output[d_plugin_name].extend(response["Items"])

    except BadRequestError as e:
        print(f"Got chalice BadRequestError: {str(e)}")
        raise
    
    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except Exception as e:
        print(
            f"Unable to get the output of one or more dependent plugins for program '{program}', event '{event}' and chunk number '{chunk_number}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to get the output of one or more dependent plugins for program '{program}', event '{event}' and chunk number '{chunk_number}': {str(e)}")

    else:
        return replace_decimals(output)


def get_event_segment_metadata(name, program, classifier, tracknumber):
    """
    Gets the Segment Metadata based on the segments found during Segmentation/Optimization process.
    """
    name = urllib.parse.unquote(name)
    program = urllib.parse.unquote(program)
    classifier = urllib.parse.unquote(classifier)
    tracknumber = urllib.parse.unquote(tracknumber)
    try:
        # Get Event Segment Details
        # From the PluginResult Table, get the Clips Info
        plugin_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)
        response = plugin_table.query(
            KeyConditionExpression=Key("PK").eq(f"{program}#{name}#{classifier}"),
            ScanIndexForward=False
        )

        plugin_responses = response['Items']

        while "LastEvaluatedKey" in response:
            response = plugin_table.query(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("PK").eq(f"{program}#{name}#{classifier}"),
                ScanIndexForward=False
            )
            plugin_responses.extend(response["Items"])

        # if "Items" not in plugin_response or len(plugin_response["Items"]) == 0:
        #    print(f"No Plugin Responses found for event '{name}' in Program '{program}' for Classifier {classifier}")
        #    raise NotFoundError(f"No Plugin Responses found for event '{name}' in Program '{program}' for Classifier {classifier}")

        clip_info = []

        for res in plugin_responses:

            optoLength = 0
            if 'OptoEnd' in res and 'OptoStart' in res:
                # By default OptoEnd and OptoStart are maps and have no Keys. Only when they do, we check for TrackNumber's
                if len(res['OptoEnd'].keys()) > 0 and len(res['OptoStart'].keys()) > 0:
                    try:
                        optoLength = res['OptoEnd'][tracknumber] - res['OptoStart'][tracknumber]
                    except Exception as e:
                        pass  # Error if the TrackNumber does not exist. Simply Ignore since its a problem with Clip Gen

            # Calculate Opto Clip Duration for each Audio Track
            optoDurationsPerTrack = []
            if 'OptoEnd' in res and 'OptoStart' in res:
                for k in res['OptoStart'].keys():
                    try:
                        optoDur = {}
                        optoDur[k] = res['OptoEnd'][k] - res['OptoStart'][k]
                        optoDurationsPerTrack.append(optoDur)
                    except Exception as e:
                        pass  # Error if the TrackNumber does not exist. Simply Ignore since its a problem with Clip Gen

            optoClipLocation = ''
            if 'OptimizedClipLocation' in res:
                # This is not ideal. We need to check of there exists a OptimizedClipLocation with the requested TrackNumber.
                # If not, likely a problem with Clip Gen. Instead of failing, we send an empty value for optoClipLocation back.
                for trackNo in res['OptimizedClipLocation'].keys():
                    if str(trackNo) == str(tracknumber):
                        optoClipLocation = create_signed_url(res['OptimizedClipLocation'][tracknumber])
                        break

            origClipLocation = ''
            if 'OriginalClipLocation' in res:
                for trackNo in res['OriginalClipLocation'].keys():
                    if str(trackNo) == str(tracknumber):
                        origClipLocation = create_signed_url(res['OriginalClipLocation'][tracknumber])
                        break

            label = ''
            if 'Label' in res:
                label = res['Label']
                if str(label) == "":
                    label = '<no label plugin configured>'

            clip_info.append({
                'OriginalClipLocation': origClipLocation,
                'OriginalThumbnailLocation': create_signed_url(
                    res['OriginalThumbnailLocation']) if 'OriginalThumbnailLocation' in res else '',
                'OptimizedClipLocation': optoClipLocation,
                'OptimizedThumbnailLocation': create_signed_url(
                    res['OptimizedThumbnailLocation']) if 'OptimizedThumbnailLocation' in res else '',
                'StartTime': res['Start'],
                'Label': label,
                'FeatureCount': 'TBD',
                'OrigLength': 0 if 'Start' not in res else res['End'] - res['Start'],
                'OptoLength': optoLength,
                'OptimizedDurationPerTrack': optoDurationsPerTrack,
                'OptoStartCode': '' if 'OptoStartCode' not in res else res['OptoStartCode'],
                'OptoEndCode': '' if 'OptoEndCode' not in res else res['OptoEndCode']
            })

        final_response = {}
        final_response['Segments'] = clip_info

    except NotFoundError as e:
        print(e)
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(e)
        print(f"Unable to get the Event '{name}' in Program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to get the Event '{name}' in Program '{program}': {str(e)}")

    else:
        return replace_decimals(final_response)


@app.route('/event/{name}/program/{program}/profileClassifier/{classifier}/track/{tracknumber}/segments/for/edl',
           cors=True, methods=['GET'], authorizer=authorizer)
def get_event_segments_for_edl(name, program, classifier, tracknumber):
    """
    Gets the Segment Metadata based on the segments found during Segmentation/Optimization process for Edl Generation

    Returns:

        A list of Segments found
    
    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    name = urllib.parse.unquote(name)
    program = urllib.parse.unquote(program)
    classifier = urllib.parse.unquote(classifier)
    tracknumber = urllib.parse.unquote(tracknumber)

    # Get Event Segment Details
    # From the PluginResult Table, get the Clips Info
    plugin_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)
    response = plugin_table.query(
        KeyConditionExpression=Key("PK").eq(f"{program}#{name}#{classifier}"),
        ScanIndexForward=True
    )
    plugin_response = response['Items']

    while "LastEvaluatedKey" in response:
        response = plugin_table.query(
            ExclusiveStartKey=response["LastEvaluatedKey"],
            KeyConditionExpression=Key("PK").eq(f"{program}#{name}#{classifier}"),
            ScanIndexForward=True
        )
        plugin_response.extend(response['Items'])

    all_segments = []
    for res in plugin_response:

        segment = {
            'Start': res['Start'],
            'End': res['End']
        }

        if 'OptoEnd' in res and 'OptoStart' in res:
            # By default OptoEnd and OptoStart are maps and have no Keys. Only when they do, we check for TrackNumber's
            if len(res['OptoEnd'].keys()) > 0 and len(res['OptoStart'].keys()) > 0:
                segment['OptoStart'] = res['OptoStart'][tracknumber]
                segment['OptoEnd'] = res['OptoEnd'][tracknumber]

        all_segments.append(segment)

    return all_segments


def get_event_segment_metadata_v2(name, program, classifier, tracknumber):
    """
    Returns the Segment Metadata based on the segments found during Segmentation/Optimization process.

    Query String Params:
    :param limit: Limits how many segments the API returns. Returns a LastEvaluatedKey if more segments exist.
    :param LastEvaluatedKey: Set the LastEvaluatedKey returned by the previous call to the API to fetch the next list of segments


    Returns:
    .. code-block:: python
        {
            "Segments": [
                {
                "OriginalClipLocation": "",
                "OriginalThumbnailLocation": "",
                "OptimizedClipLocation": "",
                "OptimizedThumbnailLocation": "",
                "StartTime": 4.8,
                "Label": "TBD",
                "FeatureCount": "TBD",
                "OrigLength": 16.2,
                "OptoLength": 0
                }
            ]
        }
    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    name = urllib.parse.unquote(name)
    program = urllib.parse.unquote(program)
    classifier = urllib.parse.unquote(classifier)
    tracknumber = urllib.parse.unquote(tracknumber)

    query_params = app.current_request.query_params
    limit = 100
    last_evaluated_key = None
    
    try:
        if query_params:
            if "limit" in query_params:
                limit = int(query_params.get("limit"))
            if "LastEvaluatedKey" in query_params:
                last_evaluated_key = query_params.get("LastEvaluatedKey")

        # Get Event Segment Details
        # From the PluginResult Table, get the Clips Info
        plugin_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

        query = {
            'KeyConditionExpression': Key("PK").eq(f"{program}#{name}#{classifier}"),
            'ScanIndexForward': False,
            'Limit': limit
        }

        if last_evaluated_key:
            last_evaluated_key = json.loads(last_evaluated_key)
            last_evaluated_key['Start'] = decimal.Decimal(str(last_evaluated_key['Start']))
            query["ExclusiveStartKey"] = last_evaluated_key

        response = plugin_table.query(**query)
        plugin_responses = response['Items']

        while "LastEvaluatedKey" in response and (limit - len(plugin_responses) > 0):
            last_evaluated_key = response['LastEvaluatedKey']
            last_evaluated_key['Start'] = decimal.Decimal(str(last_evaluated_key['Start']))
            query["ExclusiveStartKey"] = last_evaluated_key

            query["Limit"] = limit - len(plugin_responses)
            response = plugin_table.query(**query)
            plugin_responses.extend(response["Items"])

        clip_info = []

        for res in plugin_responses:
            segment_data = populate_segment_data_matching(res, tracknumber)
            clip_info.append(segment_data)

        final_response = {}
        final_response['Segments'] = clip_info

    except NotFoundError as e:
        print(e)
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(e)
        print(f"Unable to get the Event '{name}' in Program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to get the Event '{name}' in Program '{program}': {str(e)}")

    else:
        ret_val = {
            "LastEvaluatedKey": response["LastEvaluatedKey"] if "LastEvaluatedKey" in response else "",
            "Items": replace_decimals(final_response)
        }

        return ret_val


@app.route('/event/{name}/program/{program}/profileClassifier/{classifier}/track/{tracknumber}/segments/v2', cors=True,
           methods=['GET'], authorizer=authorizer)
def get_event_segments_v2(name, program, classifier, tracknumber):
    """
    Returns the Segment Metadata based on the segments found during Segmentation/Optimization process.

    Query String Params:
    :param limit: Limits how many segments the API returns. Returns a LastEvaluatedKey if more segments exist.
    :param LastEvaluatedKey: Set the LastEvaluatedKey returned by the previous call to the API to fetch the next list of segments

    Returns:

        A list of Segments along with LastEvaluatedKey. Any empty LastEvaluatedKey indicates that no additional segments exist.

        .. code-block:: python

            {
                "LastEvaluatedKey": "",
                "Items": 
            }

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    return get_event_segment_metadata_v2(name, program, classifier, tracknumber)


def populate_segment_data_matching(segment_response_data, tracknumber):
    result = {}

    optoLength = 0
    if 'OptoEnd' in segment_response_data and 'OptoStart' in segment_response_data:
        # By default OptoEnd and OptoStart are maps and have no Keys. Only when they do, we check for TrackNumber's
        if len(segment_response_data['OptoEnd'].keys()) > 0 and len(segment_response_data['OptoStart'].keys()) > 0:
            try:
                optoLength = segment_response_data['OptoEnd'][tracknumber] - segment_response_data['OptoStart'][
                    tracknumber]
            except Exception as e:
                pass  # Error if the TrackNumber does not exist. Simply Ignore since its a problem with Clip Gen

    # Calculate Opto Clip Duration for each Audio Track
    optoDurationsPerTrack = []
    if 'OptoEnd' in segment_response_data and 'OptoStart' in segment_response_data:
        for k in segment_response_data['OptoStart'].keys():
            try:
                optoDur = {}
                optoDur[k] = segment_response_data['OptoEnd'][k] - segment_response_data['OptoStart'][k]
                optoDurationsPerTrack.append(optoDur)
            except Exception as e:
                pass  # Error if the TrackNumber does not exist. Simply Ignore since its a problem with Clip Gen

    optoClipLocation = ''
    if 'OptimizedClipLocation' in segment_response_data:
        # This is not ideal. We need to check of there exists a OptimizedClipLocation with the requested TrackNumber.
        # If not, likely a problem with Clip Gen. Instead of failing, we send an empty value for optoClipLocation back.
        for trackNo in segment_response_data['OptimizedClipLocation'].keys():
            if str(trackNo) == str(tracknumber):
                optoClipLocation = create_signed_url(segment_response_data['OptimizedClipLocation'][tracknumber])
                break

    origClipLocation = ''
    if 'OriginalClipLocation' in segment_response_data:
        for trackNo in segment_response_data['OriginalClipLocation'].keys():
            if str(trackNo) == str(tracknumber):
                origClipLocation = create_signed_url(segment_response_data['OriginalClipLocation'][tracknumber])
                break

    label = ''
    if 'Label' in segment_response_data:
        label = segment_response_data['Label']
        if str(label) == "":
            label = '<no label plugin configured>'

    result = {
        'OriginalClipLocation': origClipLocation,
        'OriginalThumbnailLocation': create_signed_url(
            segment_response_data[
                'OriginalThumbnailLocation']) if 'OriginalThumbnailLocation' in segment_response_data else '',
        'OptimizedClipLocation': optoClipLocation,
        'OptimizedThumbnailLocation': create_signed_url(
            segment_response_data[
                'OptimizedThumbnailLocation']) if 'OptimizedThumbnailLocation' in segment_response_data else '',
        'StartTime': segment_response_data['Start'],
        'Label': label,
        'FeatureCount': 'TBD',
        'OrigLength': 0 if 'Start' not in segment_response_data else segment_response_data['End'] -
                                                                     segment_response_data['Start'],
        'OptoLength': optoLength,
        'OptimizedDurationPerTrack': optoDurationsPerTrack,
        'OptoStartCode': '' if 'OptoStartCode' not in segment_response_data else segment_response_data['OptoStartCode'],
        'OptoEndCode': '' if 'OptoEndCode' not in segment_response_data else segment_response_data['OptoEndCode']
    }

    return result


def match_replays_with_segments(replay_items, program, event_name, classifier, tracknumber, last_evaluated_key_input, limit):
    plugin_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)
    result_items = []
    last_evaluated_key_result = ""

    for replay_index in range(last_evaluated_key_input, len(replay_items)):
        if len(result_items) < limit:
            replay_result = replay_items[replay_index]
            start_time = Decimal(str(replay_result['Start']))
            segment_response = plugin_table.query(
                IndexName='ProgramEvent_Start-index',
                KeyConditionExpression=Key("ProgramEvent").eq(f"{program}#{event_name}") &
                                       Key("Start").eq(start_time),
                FilterExpression=Attr('PK').eq(f"{program}#{event_name}#{classifier}")
            )
            if 'Items' in segment_response and len(segment_response['Items']) > 0:
                segment_response_data = segment_response['Items'][0]
                segment_data = populate_segment_data_matching(segment_response_data, tracknumber)
                if segment_data:
                    result_items.append(segment_data)
                    last_evaluated_key_result = replay_index

    if len(result_items) < limit:
        last_evaluated_key_result = ""

    result = {
        "Items": result_items,
        "LastEvaluatedKey": last_evaluated_key_result
    }

    return result


@app.route(
    '/event/{name}/program/{program}/profileClassifier/{classifier}/track/{tracknumber}/replay/{replayId}/segments/v2',
    cors=True, methods=['GET'], authorizer=authorizer)
def get_matching_replay_segments_v2(name, program, classifier, tracknumber, replayId):
    """
    Gets the Replay Segments by matching the StartTime of each Replay Segment with the segments created so far for the event

    Query String Params:
    :param limit: Limits how many segments the API returns. Returns a LastEvaluatedKey if more segments exist.
    :param LastEvaluatedKey: Set the LastEvaluatedKey returned by the previous call to the API to fetch the next list of segments

    Returns:

        A list of Segments along with LastEvaluatedKey. Any empty LastEvaluatedKey indicates that no additional segments exist.

        .. code-block:: python

            {
                "LastEvaluatedKey": "",
                "Items": 
            }

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    name = urllib.parse.unquote(name)
    program = urllib.parse.unquote(program)
    classifier = urllib.parse.unquote(classifier)
    tracknumber = urllib.parse.unquote(tracknumber)
    limit = 100
    last_evaluated_key = 0
    replay_clips = []

    try:
        query_params = app.current_request.query_params
        if query_params:
            if "limit" in query_params:
                limit = int(query_params.get("limit"))
            if "LastEvaluatedKey" in query_params and query_params["LastEvaluatedKey"]:
                last_evaluated_key = int(query_params.get("LastEvaluatedKey"))

        replay_results_table = ddb_resource.Table(REPLAY_RESULT_TABLE_NAME)

        replay_results_query = replay_results_table.query(
            KeyConditionExpression=Key("ProgramEventReplayId").eq(f"{program}#{name}#{replayId}")
        )

        if len(replay_results_query['Items']) > 0:
            try:
                replay_clips = match_replays_with_segments(replay_results_query['Items'][0]['ReplayResults'], program, name,
                                                        classifier, tracknumber, last_evaluated_key, limit)
            except KeyError:
                pass
        else:
            return {
                "LastEvaluatedKey": None,
                "Items": [],
            }
    except Exception as e:
        print(e)
        print(f"Unable to match replays for event '{name}' in Program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to match replays for event '{name}' in Program '{program}': {str(e)}")

    else:
        return {
            "LastEvaluatedKey": replay_clips["LastEvaluatedKey"],
            "Items": replay_clips["Items"],
        }


@app.route('/event/{name}/program/{program}/profileClassifier/{classifier}/track/{tracknumber}/segments', cors=True,
           methods=['GET'], authorizer=authorizer)
def get_event_segments(name, program, classifier, tracknumber):
    """
    Gets the Segment Metadata based on the segments found during Segmentation/Optimization process.

    Returns:

        .. code-block:: python

            {
                "Segments": [
                    {
                    "OriginalClipLocation": "",
                    "OriginalThumbnailLocation": "",
                    "OptimizedClipLocation": "",
                    "OptimizedThumbnailLocation": "",
                    "StartTime": "",
                    "Label": "",
                    "FeatureCount": "",
                    "OrigLength": "",
                    "OptoLength": ""
                    }
                ]
            }
    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    return get_event_segment_metadata(name, program, classifier, tracknumber)


@app.route(
    '/event/{name}/program/{program}/profileClassifier/{classifier}/track/{tracknumber}/replay/{replayId}/segments',
    cors=True, methods=['GET'], authorizer=authorizer)
def get_matching_replay_segments(name, program, classifier, tracknumber, replayId):
    """
    Gets the Replay Segments by matching the StartTime of each Replay Segment with the segments created so far for the event.

    Returns:

        A list of replay Segments.

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """

    name = urllib.parse.unquote(name)
    program = urllib.parse.unquote(program)
    classifier = urllib.parse.unquote(classifier)

    segment_metadata = get_event_segment_metadata(name, program, classifier, tracknumber)

    replay_results_table = ddb_resource.Table(REPLAY_RESULT_TABLE_NAME)

    response = replay_results_table.query(
        KeyConditionExpression=Key("ProgramEventReplayId").eq(f"{program}#{name}#{replayId}")
    )

    replay_clips = []
    if 'Items' in response:
        replay_results_response = response['Items']

        while "LastEvaluatedKey" in response:
            response = replay_results_table.query(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("ProgramEventReplayId").eq(f"{program}#{name}#{replayId}")
            )
            replay_results_response.extend(response['Items'])

        for replay_result in replay_results_response:
            for result in replay_result['ReplayResults']:
                # print(f"Replay Start = {type(result['Start'])}")
                for segment in segment_metadata['Segments']:
                    # print(type(segment['StartTime']))
                    if Decimal(str(result['Start'])) == Decimal(str(segment['StartTime'])):
                        replay_clips.append(segment)
                        break

    return replay_clips


@app.route('/event/{name}/program/{program}/replay/{replayId}/segments', cors=True, methods=['GET'],
           authorizer=authorizer)
def get_replay_segments(name, program, replayId):
    """
    Gets the Replay Segments for a ReplayId

    Returns:

        A list of replay Segments.

    """

    name = urllib.parse.unquote(name)
    program = urllib.parse.unquote(program)

    replay_results_table = ddb_resource.Table(REPLAY_RESULT_TABLE_NAME)
    response = replay_results_table.query(
        KeyConditionExpression=Key("ProgramEventReplayId").eq(f"{program}#{name}#{replayId}")
    )

    if 'Items' in response:
        replay_results_response = response['Items']
        while "LastEvaluatedKey" in response:
            response = replay_results_table.query(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("ProgramEventReplayId").eq(f"{program}#{name}#{replayId}")
            )
            replay_results_response.extend(response['Items'])

        if len(replay_results_response) > 0:
            return replay_results_response[0]['ReplayResults'] if 'ReplayResults' in replay_results_response[0] else []
        else:
            return []
    else:
        return []


def create_signed_url(s3_path):
    bucket, objkey = split_s3_path(s3_path)
    try:
        expires = 86400
        url = s3_client.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': bucket,
                'Key': objkey
            }, ExpiresIn=expires)
        return url
    except Exception as e:
        print(e)
        raise e

def split_s3_path(s3_path):
    path_parts = s3_path.replace("s3://", "").split("/")
    bucket = path_parts.pop(0)
    key = "/".join(path_parts)
    return bucket, key

@app.route(
    '/event/{name}/program/{program}/clipstart/{start}/clipduration/{duration}/track/{tracknumber}/classifier/{classifier}/org/previewinfo',
    cors=True, methods=['GET'], authorizer=authorizer)
def get_original_clip_preview_details(name, program, start, duration, tracknumber, classifier):
    """
    Returns metadata about a Segment such as Range based features, point based features and Clip Signed Urls

    Returns:

        Metadata about a Segment such as Range based features, point based features and Clip Signed Urls

    Raises:
        500 - ChaliceViewError
    """
    name = urllib.parse.unquote(name)
    program = urllib.parse.unquote(program)
    classifier = urllib.parse.unquote(classifier)

    return get_clip_metadata(name, program, start, duration, tracknumber, classifier, "Original")


def get_clipinfo_from_plugin_results(name, program, start, duration):
    event = urllib.parse.unquote(name)
    program = urllib.parse.unquote(program)
    clip_startsAt_secs = Decimal(urllib.parse.unquote(start))
    clip_duration = Decimal(urllib.parse.unquote(duration))

    # We have the Clip duration. So we know the clip end time on a Time series
    clip_endsAt_secs = clip_startsAt_secs + clip_duration

    # We need to account for Silence detection (or any other feature)
    # which has been detected prior to the Clip Start time and overlaps with the
    # clips duration or exceeds it.
    # We'll go back 20 seconds to account for any feature that was detected earlier.
    mod_clip_startsAt_secs = clip_startsAt_secs - 20

    plugin_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

    # Get all Plugin results for the current clip's Start and End times.
    # We will end up getting data from other clips which will be filtered out downstream    
    response = plugin_table.query(
        KeyConditionExpression=Key("ProgramEvent").eq(f"{program}#{event}") & Key('Start').between(
            mod_clip_startsAt_secs, clip_endsAt_secs),
        FilterExpression=Attr('End').gte(clip_startsAt_secs),
        ScanIndexForward=True,
        IndexName='ProgramEvent_Start-index'
    )

    clips_info = response["Items"]

    while "LastEvaluatedKey" in response:
        response = plugin_table.query(
            KeyConditionExpression=Key("ProgramEvent").eq(f"{program}#{event}") & Key('Start').between(
                mod_clip_startsAt_secs, clip_endsAt_secs),
            FilterExpression=Attr('End').gte(clip_startsAt_secs),
            ScanIndexForward=True,
            ExclusiveStartKey=response["LastEvaluatedKey"],
            IndexName='ProgramEvent_Start-index'
        )

        clips_info.extend(response["Items"])

    return clips_info


def get_clip_metadata(name, program, start, duration, tracknumber, classifier, mode):
    try:
        event = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)
        clip_startsAt_secs = Decimal(urllib.parse.unquote(start))
        clip_duration = Decimal(urllib.parse.unquote(duration))
        tracknumber = str(urllib.parse.unquote(tracknumber))
        classifier = urllib.parse.unquote(classifier)

        clips_info = get_clipinfo_from_plugin_results(name, program, start, duration)

        # We need to generate 2 Datasets from the Clips Info for this Specific Clip
        # Range based Event - Silence detection, Scene Detection etc.
        # Single value Feature - Ace Shot, Labels - Far/Near etc.

        range_based_events = []
        unique_range_labels = []
        single_value_features = []
        unique_feature_labels = []
        range_based_events_chart = []

        for item in clips_info:

            # Its a Single Value feature if the Start and End times are the same
            if item['Start'] == item['End']:
                if mode == 'Optimized':
                    tmp_feature = create_feature(item, clip_startsAt_secs, tracknumber, "Optimized")
                else:
                    tmp_feature = create_feature(item, clip_startsAt_secs, -1, "Original")

                if tmp_feature is not None:
                    single_value_features.append(tmp_feature)

                # Return Labels for Chart rendering
                if f"{item['PluginName']}-{item['Label']}" not in unique_feature_labels:
                    unique_feature_labels.append(f"{item['PluginName']}-{item['Label']}")
            else:
                # Only display Featurers in the Range Plugin Table
                if item['PluginClass'] in ['Featurer', 'Labeler', 'Classifier']:
                    if mode == 'Optimized':
                        range_event = create_range_event(item, clip_startsAt_secs, tracknumber, "Optimized")
                    else:
                        range_event = create_range_event(item, clip_startsAt_secs, -1, "Original")

                    if range_event is not None:
                        range_based_events.append(range_event)

                    if item['PluginName'] not in unique_range_labels:
                        unique_range_labels.append(item['PluginName'])

                    # Data for the Bar Chart
                    # -X--|------                           |
                    #    |         -------------           |
                    #    |               ------------------|--Y--      
                    #    |    --------------               | 
                    #    |       -----------------------   |
                    # Marker represents the start and end of a Bar in the Bar Chart.
                    # The Start time will be set to Zero if the ClipsStart time was Negative. (X in the above schematic)
                    # The Length of Each bar is Sum of Start and Duration. For example, Starttime is 4 Secs and Duration 10 secs. 
                    # The Bar would start from 4 Secs and End at 14 secs on the Bar Chart.
                    # If the Bar length goes beyond the Clip's length, we truncate the Bar length (Y in the above schematic)
                    if range_event is not None:
                        range_event_chart = {}
                        range_event_chart[range_event['Marker']] = [range_event['Start'],
                                                                    range_event['Start'] + range_event['Duration'] if (
                                                                                                                              range_event[
                                                                                                                                  'Start'] +
                                                                                                                              range_event[
                                                                                                                                  'Duration']) < clip_duration else
                                                                    range_event['Start'] + (
                                                                            clip_duration - range_event['Start'])]
                        range_event_chart['Start'] = range_event['Start']
                        range_based_events_chart.append(range_event_chart)


    except Exception as e:
        print(f"Unable to retrieve Plugin results '{name}' in Program '{program}': {str(e)}")
        raise ChaliceViewError(e)

    else:

        clip_url = ""

        if mode == 'Optimized':
            clip_url = get_clip_signed_url(clip_startsAt_secs, event, program, classifier, tracknumber, 'Optimized')
        else:
            clip_url = get_clip_signed_url(clip_startsAt_secs, event, program, classifier, tracknumber, 'Original')

        finalresults = {
            "RangeEvents": range_based_events,
            "RangeEventsChart": range_based_events_chart,
            "RangeLabels": unique_range_labels,
            "Features": single_value_features,
            "FeatureLabels": unique_feature_labels
        }
        if mode == 'Optimized':
            finalresults['OptimizedClipLocation'] = clip_url
        else:
            finalresults['OriginalClipLocation'] = clip_url

        return replace_decimals(finalresults)


@app.route(
    '/event/{name}/program/{program}/clipstart/{start}/clipduration/{duration}/track/{tracknumber}/classifier/{classifier}/opt/previewinfo',
    cors=True, methods=['GET'], authorizer=authorizer)
def get_optimized_clip_preview_details(name, program, start, duration, tracknumber, classifier):
    """
    Retrieve the pts timecode of the first frame of the first HLS video segment.

    Returns:

        The pts timecode of the first frame of the first HLS video segment if it exists. Else, None.

    Raises:
        500 - ChaliceViewError
    """
    name = urllib.parse.unquote(name)
    program = urllib.parse.unquote(program)
    classifier = urllib.parse.unquote(classifier)
    return get_clip_metadata(name, program, start, duration, tracknumber, classifier, "Optimized")


def create_feature(clipItem, startTime, tracknumber, clipType):
    # Match this Feature to the corresponding AudioTrack if one exists.
    if 'AudioTrack' in clipItem:
        if clipItem['AudioTrack'] == tracknumber and clipType == 'Optimized':
            return get_feature_clip(clipItem, clipItem['Start'], startTime)
        else:
            # Don't return a Feature if the TrackNumber did not match
            return None

    return get_feature_clip(clipItem, clipItem['Start'], startTime)


def get_feature_clip(clipItem, clipItemStartTime, startTime):
    clip = {}

    # clip[clipItem['Label']] = 1 # We set 1 as a Constant value to be Displayed on the Y Axis as Bar height
    clip[f"{clipItem['PluginName']}-{clipItem['Label']}"] = 1
    clip['featureAt'] = max(0, clipItemStartTime - startTime)
    return clip


def create_range_event(clipItem, startTime, tracknumber, clipType):
    # Match this Feature to the corresponding AudioTrack if one exists.
    if 'AudioTrack' in clipItem and clipType == 'Optimized':
        if clipItem['AudioTrack'] == tracknumber:
            clip = {}
            clip['Marker'] = clipItem['PluginName']

            # Make the Start time as Zero if the Clip Starts before the StartTime 
            clip['Start'] = 0 if clipItem['Start'] < startTime else clipItem['Start'] - startTime
            clip['Duration'] = clipItem['End'] - clipItem['Start'] if clipItem['Start'] > startTime else clipItem[
                                                                                                             'End'] - startTime
            clip['Label'] = '' if 'Label' not in clipItem else clipItem['Label']
            return clip

    else:
        clip = {}
        clip['Marker'] = clipItem['PluginName']

        # Make the Start time as Zero if the Clip Starts before the StartTime 
        clip['Start'] = 0 if clipItem['Start'] < startTime else clipItem['Start'] - startTime
        clip['Duration'] = clipItem['End'] - clipItem['Start'] if clipItem['Start'] > startTime else clipItem[
                                                                                                         'End'] - startTime
        clip['Label'] = '' if 'Label' not in clipItem else clipItem['Label']
        return clip

    return None


def get_clip_signed_url(startTime, event, program, classifier, audioTrack, mode):
    # Get Event Segment Details
    # From the PluginResult Table, get the Clips Info
    plugin_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)
    plugin_response = plugin_table.query(
        KeyConditionExpression=Key("PK").eq(f"{program}#{event}#{classifier}") & Key("Start").eq(Decimal(startTime)),
        ProjectionExpression="#Start, #originalClipLocation, #optimizedClipLocation",
        ExpressionAttributeNames={
            "#Start": "Start",
            "#originalClipLocation": "OriginalClipLocation",
            "#optimizedClipLocation": "OptimizedClipLocation"
        },
        ScanIndexForward=True
    )

    # print(f"inside get_clip_signed_url - {replace_decimals(plugin_response['Items'])}")
    for res in replace_decimals(plugin_response['Items']):
        # if res['Start'] == startTime:
        if mode == 'Original':
            return create_signed_url(res['OriginalClipLocation'][str(audioTrack)]) if len(
                res['OriginalClipLocation']) > 0 else ""
        else:
            return create_signed_url(res['OptimizedClipLocation'][str(audioTrack)]) if len(
                res['OptimizedClipLocation']) > 0 else ""

    return ""


@app.route('/clip/preview/feedback', cors=True, methods=['POST'], authorizer=authorizer)
def record_clip_preview_feedback():
    """
    Captures Feedback on the Original and Optimized Clips

    Body:

    .. code-block:: python

        {
            "Program": string,
            "Event": string,
            "Classifier": string,
            "StartTime": number,
            "AudioTrack": number,
            "OriginalFeedback: {
                "Feedback": string,
                "FeedbackDetail": string
            },
            "OptimizedFeedback: {
                "Feedback": string,
                "FeedbackDetail": string
            }
        }

    Returns:

        None
    
    Raises:
        400 - BadRequestError
        500 - ChaliceViewError
    """
    try:
        request = json.loads(app.current_request.raw_body.decode())
        validate(instance=request, schema=API_SCHEMA["store_clip_preview_feedback"])

        program = request["Program"]
        event = request["Event"]
        classifier = request["Classifier"]
        start_time = request["StartTime"]
        audio_track = request["AudioTrack"]
        reviewer = request["Reviewer"]
        original_feedback = request['OriginalFeedback'] if 'OriginalFeedback' in request else None
        optimized_feedback = request['OptimizedFeedback'] if 'OptimizedFeedback' in request else None

        clip_preview_table = ddb_resource.Table(CLIP_PREVIEW_FEEDBACK_TABLE_NAME)

        feedback = {}
        feedback["PK"] = f"{program}#{event}#{classifier}#{start_time}#{audio_track}#{reviewer}"
        feedback["ProgramEventTrack"] = f"{program}#{event}#{classifier}#{start_time}#{audio_track}"
        feedback["ProgramEventClassifierStart"] = f"{program}#{event}#{classifier}#{start_time}"
        feedback["Program"] = program
        feedback["Event"] = event
        feedback["Classifier"] = classifier
        feedback["Start"] = Decimal(str(start_time))
        feedback["AudioTrack"] = audio_track
        feedback["Reviewer"] = reviewer
        if original_feedback is not None:
            feedback['OriginalFeedback'] = original_feedback

        if optimized_feedback is not None:
            feedback['OptimizedFeedback'] = optimized_feedback

        clip_preview_table.put_item(Item=feedback)

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except Exception as e:
        print(f"Unable to save clip preview program '{program}' and event '{event}': {str(e)}")
        raise ChaliceViewError(f"Unable to save clip preview program '{program}' and event '{event}': {str(e)}")
    else:
        return {}


@app.route(
    '/clip/preview/program/{program}/event/{event}/classifier/{classifier}/start/{start_time}/track/{audio_track}/reviewer/{reviewer}/feedback',
    cors=True, methods=['GET'], authorizer=authorizer)
def get_clip_preview_feedback(program, event, classifier, start_time, audio_track, reviewer):
    """
    Gets the feedback provided by a user for a Segment's clip

    Returns:

        Feedback if present. Empty Dictionary of no feedback exists.
    """
    event = urllib.parse.unquote(event)
    program = urllib.parse.unquote(program)
    classifier = urllib.parse.unquote(classifier)
    start_time = Decimal(urllib.parse.unquote(start_time))
    tracknumber = urllib.parse.unquote(audio_track)

    clip_preview_table = ddb_resource.Table(CLIP_PREVIEW_FEEDBACK_TABLE_NAME)

    response = clip_preview_table.query(
        KeyConditionExpression=Key("PK").eq(
            f"{program}#{event}#{classifier}#{str(start_time)}#{str(tracknumber)}#{reviewer}")
    )

    if "Items" not in response or len(response["Items"]) == 0:
        return {}

    return response["Items"][0]


@app.route('/replay/feature/program/{program}/event/{event}/outputattribute/{pluginattribute}/plugin/{pluginname}',
           cors=True, methods=['GET'], authorizer=authorizer)
def get_plugin_output_attributes_values(program, event, pluginattribute, pluginname):
    """
    Gets a list of Unique Plugin output attribute values for a Plugin and Output Attribute

    Returns:

        A list of Unique Plugin output attribute values for a Plugin and Output Attribute
    """
    event = urllib.parse.unquote(event)
    program = urllib.parse.unquote(program)
    pluginattribute = urllib.parse.unquote(pluginattribute)
    pluginname = urllib.parse.unquote(pluginname)

    plugin_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

    # Get all Plugin results for the current clip's Start and End times.
    # We will end up getting data from other clips which will be filtered out downstream    
    response = plugin_table.query(
        KeyConditionExpression=Key("ProgramEvent").eq(f"{program}#{event}"),
        FilterExpression=Attr('PluginName').eq(pluginname) & Attr('PluginClass').is_in(
            ['Featurer', 'Labeler', 'Classifier']),
        ScanIndexForward=True,
        IndexName='ProgramEvent_Start-index',
        Limit=25
    )

    clips_info = response["Items"]

    unique_values = []
    for item in clips_info:
        # Only consider Items which match the Plugin Name and has the Attribute 
        if pluginattribute in item:
            if item[pluginattribute] not in unique_values:
                unique_values.append(item[pluginattribute])

    return {
        pluginname + " | " + pluginattribute: unique_values
    }


@app.route(
    '/feature/in/segment/program/{program}/event/{event}/plugin/{pluginname}/attrn/{attrname}/attrv/{attrvalue}/start/{starttime}/end/{endtime}',
    cors=True, methods=['GET'], authorizer=authorizer)
def get_feature_in_segment(program, event, starttime, pluginname, attrname, attrvalue, endtime):
    """
    Gets the plugin result for a Plugin Output attribute based on the output attribute name and value

    Returns:

        Plugin result, if the feature (output attribute) exists in any segment
    """
    event = urllib.parse.unquote(event)
    program = urllib.parse.unquote(program)
    starttime = Decimal(urllib.parse.unquote(starttime))
    pluginname = urllib.parse.unquote(pluginname)
    attrname = urllib.parse.unquote(attrname)
    attrvalue = urllib.parse.unquote(attrvalue)
    endtime = Decimal(urllib.parse.unquote(endtime))

    plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

    response = plugin_result_table.query(
        IndexName=PROGRAM_EVENT_INDEX,
        ScanIndexForward=True,
        ProjectionExpression="#start",
        ExpressionAttributeNames={'#start': 'Start'},
        KeyConditionExpression=Key("ProgramEvent").eq(f"{program}#{event}") & Key('Start').gte(starttime),
        FilterExpression=Attr('PluginClass').is_in(['Classifier', 'Labeler', 'Featurer']) & Attr(attrname).eq(
            attrvalue) & Attr('End').lte(endtime)
    )

    return response


@app.route('/segments/all/program/{program}/event/{event}/classifier/{classifier}/replay', cors=True, methods=['GET'],
           authorizer=authorizer)
def get_segments_for_event(program, event, classifier):
    """
    Gets all segments created for an event.

    Returns:

        All segments created for an event.
    """
    event = urllib.parse.unquote(event)
    program = urllib.parse.unquote(program)
    classifier = urllib.parse.unquote(classifier)

    plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

    response = plugin_result_table.query(
        ProjectionExpression="#start, #originalClipLocation, #optimizedClipLocation, #optoStart, #pluginClass, #end, #optoEnd",
        ExpressionAttributeNames={'#start': 'Start', '#originalClipLocation': 'OriginalClipLocation',
                                  '#optimizedClipLocation': 'OptimizedClipLocation', '#optoStart': 'OptoStart',
                                  '#pluginClass': 'PluginClass', '#end': 'End', '#optoEnd': 'OptoEnd'},
        KeyConditionExpression=Key("PK").eq(f"{program}#{event}#{classifier}"),
        ScanIndexForward=True
    )

    segments = response["Items"]

    while "LastEvaluatedKey" in response:
        response = plugin_result_table.query(
            ProjectionExpression="#start, #originalClipLocation, #optimizedClipLocation, #optoStart, #pluginClass, #end, #optoEnd",
            ExpressionAttributeNames={'#start': 'Start', '#originalClipLocation': 'OriginalClipLocation',
                                      '#optimizedClipLocation': 'OptimizedClipLocation', '#optoStart': 'OptoStart',
                                      '#pluginClass': 'PluginClass', '#end': 'End', '#optoEnd': 'OptoEnd'},
            ExclusiveStartKey=response["LastEvaluatedKey"],
            KeyConditionExpression=Key("PK").eq(f"{program}#{event}#{classifier}"),
            ScanIndexForward=True
        )

        segments.extend(response["Items"])

    return replace_decimals(segments)


@app.route('/replay/result', cors=True, methods=['POST'], authorizer=authorizer)
def update_replay_results():
    """
    Store the result of a plugin in a DynamoDB table.

    Body:

    .. code-block:: python

        {
            "Program": string,
            "Event": string,
            "ReplayId": string,
            "Profile": string,
            "Classifier": string,
            "AdditionalInfo" : list,
            "ReplayResults: list
        }

    Returns:

        None
    """

    replay_result = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)
    print(replay_result)

    program = replay_result["Program"]
    event = replay_result["Event"]
    replay_id = replay_result["ReplayId"]
    profile = replay_result["Profile"]
    classifier = replay_result["Classifier"]
    replay_results = replay_result["ReplayResults"]
    additional_info = replay_result["AdditionalInfo"]
    total_score = replay_result["TotalScore"]

    update_expression = []
    expression_attribute_names = {}
    expression_attribute_values = {}

    update_expression.append("#CreatedOn = :CreatedOn")
    expression_attribute_names["#CreatedOn"] = "CreatedOn"
    expression_attribute_values[":CreatedOn"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    update_expression.append("#ReplayId = :ReplayId")
    expression_attribute_names["#ReplayId"] = "ReplayId"
    expression_attribute_values[":ReplayId"] = replay_id

    update_expression.append("#Event = :Event")
    expression_attribute_names["#Event"] = "Event"
    expression_attribute_values[":Event"] = event

    update_expression.append("#Program = :Program")
    expression_attribute_names["#Program"] = "Program"
    expression_attribute_values[":Program"] = program

    update_expression.append("#Profile = :Profile")
    expression_attribute_names["#Profile"] = "Profile"
    expression_attribute_values[":Profile"] = profile

    update_expression.append("#Classifier = :Classifier")
    expression_attribute_names["#Classifier"] = "Classifier"
    expression_attribute_values[":Classifier"] = classifier

    update_expression.append("#TotalScore = :TotalScore")
    expression_attribute_names["#TotalScore"] = "TotalScore"
    expression_attribute_values[":TotalScore"] = total_score

    # Upsert will first Insert an Empty list and then append Debug Information if any found
    # This will serve as a Audit Trail on which segments were Included/Excluded for every Segment End event processing
    update_expression.append("#DebugInfo = list_append(if_not_exists(#DebugInfo, :initialDebugInfo), :DebugInfo)")
    expression_attribute_names["#DebugInfo"] = "DebugInfo"
    expression_attribute_values[":DebugInfo"] = []  # additional_info
    expression_attribute_values[":initialDebugInfo"] = []

    update_expression.append("#ReplayResults = :ReplayResults")
    expression_attribute_names["#ReplayResults"] = "ReplayResults"
    expression_attribute_values[
        ":ReplayResults"] = replay_results  # json.loads(json.dumps(replay_results), parse_float=Decimal)

    if len(replay_results) > 0:
        replay_results_table = ddb_resource.Table(REPLAY_RESULT_TABLE_NAME)

        replay_results_table.update_item(
            Key={"ProgramEventReplayId": f"{program}#{event}#{replay_id}"},
            UpdateExpression="SET " + ", ".join(update_expression),
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values
        )

        return "Replay results updated"

    return ""


@app.route('/event/program/classifier/all/segments', cors=True, methods=['PUT'], authorizer=authorizer)
def get_all_event_segments():
    """
    Returns the Segment Metadata based on the segments found during Segmentation/Optimization process.
    
    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    input = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)
    name = input['Name']
    program = input['Program']
    classifier = input['Classifier']
    output_attributes = input['OutputAttributes']  # List
    print(f"output_attributes ...... {output_attributes}")
    print(f"output_attributes type ...... {output_attributes}")

    
    try:
        # Get Clip Feedback for every segment Clip
        clip_preview_table = ddb_resource.Table(CLIP_PREVIEW_FEEDBACK_TABLE_NAME)

        # Get Event Segment Details
        # From the PluginResult Table, get the Clips Info
        plugin_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)
        response = plugin_table.query(
            KeyConditionExpression=Key("PK").eq(f"{program}#{name}#{classifier}"),
            ScanIndexForward=True
        )

        plugin_responses = response['Items']

        while "LastEvaluatedKey" in response:
            response = plugin_table.query(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("PK").eq(f"{program}#{name}#{classifier}"),
                ScanIndexForward=True
            )
            plugin_responses.extend(response["Items"])

        all_segments = []

        for res in plugin_responses:
            segment_info = {}
            segment_output_attributes = []
            feedback = []

            segment_info['Start'] = res['Start']
            segment_info['End'] = res['End']

            if 'OptoEnd' in res and 'OptoStart' in res:
                segment_info['OptoStart'] = res['OptoStart']
                segment_info['OptoEnd'] = res['OptoEnd']

            if 'OptimizedClipLocation' in res:
                segment_info['OptimizedClipLocation'] = res['OptimizedClipLocation']

            if 'OriginalClipLocation' in res:
                segment_info['OriginalClipLocation'] = res['OriginalClipLocation']

            if 'OriginalThumbnailLocation' in res:
                segment_info['OriginalThumbnailLocation'] = res['OriginalThumbnailLocation']

            if 'OptimizedThumbnailLocation' in res:
                segment_info['OptimizedThumbnailLocation'] = res['OptimizedThumbnailLocation']

            for output_attrib in output_attributes:
                if output_attrib in res:
                    if res[output_attrib] == 'True':
                        segment_output_attributes.append(output_attrib)

            if len(segment_output_attributes) > 0:
                segment_info['OutputAttributesFound'] = segment_output_attributes

            feedback_audio_track = {}
            response = clip_preview_table.query(
                IndexName=CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_CLASSIFIER_START_INDEX,
                KeyConditionExpression=Key("ProgramEventClassifierStart").eq(
                    f"{program}#{name}#{classifier}#{str(res['Start'])}")
            )
            feedback_info = {}
            for item in response['Items']:

                if 'OptimizedFeedback' in item:
                    if item['OptimizedFeedback']['Feedback'] != '-':
                        feedback_info['OptimizedFeedback'] = item['OptimizedFeedback']['Feedback']

                if 'OriginalFeedback' in item:
                    if item['OriginalFeedback']['Feedback'] != '-':
                        feedback_info['OriginalFeedback'] = item['OriginalFeedback']['Feedback']

                feedback_audio_track[str(item['AudioTrack'])] = feedback_info
                feedback.append(feedback_audio_track)

            segment_info['Feedback'] = feedback

            all_segments.append(segment_info)

    except NotFoundError as e:
        print(e)
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(e)
        print(f"Unable to get the Event '{name}' in Program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to get the Event '{name}' in Program '{program}': {str(e)}")

    else:
        return replace_decimals(all_segments)
