# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import json
import boto3
from decimal import Decimal
from chalice import IAMAuthorizer
from chalice import ChaliceViewError, BadRequestError
from boto3.dynamodb.conditions import Key, Attr
from jsonschema import validate, ValidationError
from chalice import Blueprint
from chalicelib import load_api_schema, replace_decimals

CHUNK_TABLE_NAME = os.environ['CHUNK_TABLE_NAME']
PLUGIN_RESULT_TABLE_NAME = os.environ['PLUGIN_RESULT_TABLE_NAME']

authorizer = IAMAuthorizer()

ddb_resource = boto3.resource("dynamodb")
API_SCHEMA = load_api_schema()

workflow_api = Blueprint(__name__)

@workflow_api.route('/workflow/segment/state', cors=True, methods=['POST'], authorizer=authorizer)
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
        chunk = json.loads(workflow_api.current_app.current_request.raw_body.decode(), parse_float=Decimal)

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


@workflow_api.route('/workflow/labeling/segment/state', cors=True, methods=['POST'], authorizer=authorizer)
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
        request = json.loads(workflow_api.current_app.current_request.raw_body.decode(), parse_float=Decimal)

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


@workflow_api.route('/workflow/optimization/segment/state', cors=True, methods=['POST'], authorizer=authorizer)
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
        request = json.loads(workflow_api.current_app.current_request.raw_body.decode())

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




@workflow_api.route('/workflow/engine/clipgen/segments', cors=True, methods=['POST'], authorizer=authorizer)
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
        request = json.loads(workflow_api.current_app.current_request.raw_body.decode())

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


@workflow_api.route('/workflow/engine/clipgen/chunks', cors=True, methods=['POST'], authorizer=authorizer)
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
        request = json.loads(workflow_api.current_app.current_request.raw_body.decode(), parse_float=Decimal)

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