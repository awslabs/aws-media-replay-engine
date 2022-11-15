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
import urllib.parse

CHUNK_TABLE_NAME = os.environ['CHUNK_TABLE_NAME']
PLUGIN_RESULT_TABLE_NAME = os.environ['PLUGIN_RESULT_TABLE_NAME']
PARTITION_KEY_END_INDEX = os.environ['PARTITION_KEY_END_INDEX']
MAX_DETECTOR_QUERY_WINDOW_SECS = int(os.environ['MAX_DETECTOR_QUERY_WINDOW_SECS'])
PROGRAM_EVENT_LABEL_INDEX = os.environ['PROGRAM_EVENT_LABEL_INDEX']
PAGINATION_QUERY_LIMIT = os.getenv('PAGINATION_QUERY_LIMIT')
NON_OPTO_SEGMENTS_INDEX = os.environ['NON_OPTO_SEGMENTS_INDEX']
PARTITION_KEY_CHUNK_NUMBER_INDEX = os.environ['PARTITION_KEY_CHUNK_NUMBER_INDEX']

authorizer = IAMAuthorizer()

ddb_resource = boto3.resource("dynamodb")
API_SCHEMA = load_api_schema()

EVAL_KEY_INDEX=3

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
            "MaxSegmentLength": integer,
            "LastEvaluatedKeys": list
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
        last_evaluated_keys = chunk['LastEvaluatedKeys'] if 'LastEvaluatedKeys' in chunk else {}

        print(
            f"Getting the state of the segment identified in prior chunks for program '{program}', event '{event}', plugin '{plugin_name}' and chunk number '{chunk_number}'")

        output={}

        plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

        response = plugin_result_table.query(
            KeyConditionExpression=Key("PK").eq(f"{program}#{event}#{plugin_name}") & Key("Start").lt(chunk_start),
            ScanIndexForward=False,
            Limit=1
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
            
            output['PriorSegment'] = prior_segment

            if prior_segment_end is None or prior_segment_start == prior_segment_end:  # Partial segment
                print("Prior segment is partial as only the 'Start' time is identified")
                output['State'] = "Start"
                start_key_condition = prior_segment_start

            else:  # Complete segment
                print("Prior segment is complete as both the 'Start' and 'End' times are identified")
                output['State'] = "End"
                start_key_condition = prior_segment_end

        print(
            f"Retrieving all the labels created by the dependent plugins '{dependent_plugins}' since '{start_key_condition}'")

        if dependent_plugins:
            output['DependentPluginResults'] = {}

        for d_plugin in dependent_plugins:
            # Only return the new data
            if last_evaluated_keys and d_plugin not in last_evaluated_keys:
                continue

            key_condition_expr = Key("PK").eq(f"{program}#{event}#{d_plugin}") & Key("Start").gt(start_key_condition)

            query_params = {
                "KeyConditionExpression": key_condition_expr,
                "FilterExpression": Attr("ChunkNumber").lte(chunk_number)
            }

            if PAGINATION_QUERY_LIMIT:
                query_params['Limit']=int(PAGINATION_QUERY_LIMIT)

            if d_plugin in last_evaluated_keys:
                print(f"Using LastEvaluatedKey '{last_evaluated_keys[d_plugin]}'")
                query_params["ExclusiveStartKey"]=last_evaluated_keys[d_plugin]

            response = plugin_result_table.query(**query_params)
            
            if 'Items' in response and response["Items"]:
                output['DependentPluginResults'][d_plugin] = {"Items" : response["Items"]}
            else:
                output['DependentPluginResults'][d_plugin] = {"Items" : []}

            if "LastEvaluatedKey" in response and response["LastEvaluatedKey"]:
                if d_plugin in output['DependentPluginResults']:
                    output['DependentPluginResults'][d_plugin]['LastEvaluatedKey'] = response["LastEvaluatedKey"]
                else:
                    output['DependentPluginResults'][d_plugin] = {"LastEvaluatedKey" : response["LastEvaluatedKey"]}

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
        last_evaluated_keys = request['LastEvaluatedKeys'] if 'LastEvaluatedKeys' in request else {}

        ## If the last evaluated keys include the classifier AND one or more of the dependent plugins- we should just GET the classifier object again

        print(
            f"Getting the complete, unlabeled segments for program '{program}', event '{event}', classifier '{classifier}' and chunk number '{chunk_number}'")

        output = {}

        plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

        query_params = {
            "IndexName": PROGRAM_EVENT_LABEL_INDEX,
            "KeyConditionExpression":Key("PK").eq(f"{program}#{event}#{classifier}") & Key("LabelCode").eq("Not Attempted"),
            "FilterExpression":Attr("ChunkNumber").lte(chunk_number),
            "Limit":1
            }
        
        # Pass in the StartKey via 'classifier' name
        if classifier in last_evaluated_keys:
            print(f"Using LastEvaluatedKey '{last_evaluated_keys[classifier]}'")
            query_params["ExclusiveStartKey"]=last_evaluated_keys[classifier]
            
        response = ''
        if classifier in last_evaluated_keys and len(last_evaluated_keys) > 1:
            # We need to use a temp key
            temp_key = {'PK': last_evaluated_keys[classifier]['PK'], 'Start': last_evaluated_keys[classifier]['Start']}
            ######
            response = plugin_result_table.get_item(Key=temp_key)
            print(response)
            ## Add response as Items to keep rest of flow
            response['Items'] = [response['Item']]
            response['LastEvaluatedKey'] =last_evaluated_keys[classifier]
        else:
            response = plugin_result_table.query(**query_params)
            while not response['Items'] and 'LastEvaluatedKey' in response:
                # Use the last evaluated key from the response that returned no items (due to filter)
                query_params["ExclusiveStartKey"]=response['LastEvaluatedKey']
                response = plugin_result_table.query(**query_params)
                print(f'Response from inner query: {response}')

        # Remove classifier from input; don't need it anymore
        last_evaluated_keys.pop(classifier,'n/a')

        print(f'Response from query: {response}')
       

        if "Items" not in response or len(response["Items"]) < 1:
            print(
                f"No unlabeled segments found for program '{program}', event '{event}', classifier '{classifier}' and chunk number '{chunk_number}'")

        else:
            print(
                f"One or more unlabeled segments found for program '{program}', event '{event}', classifier '{classifier}' and chunk number '{chunk_number}'")

            ## We're only working on 1 segment at a time
            segment = response["Items"][0]
            output['Segment'] = {'Item': segment}
            if 'LastEvaluatedKey' in response:
                output['Segment']['LastEvaluatedKey'] = response['LastEvaluatedKey']
            segment_start = segment["Start"]
            segment_end = segment["End"] if "End" in segment else None

            # Get the Labeler dependent plugins output for the segment only if it is complete
            if segment_end is not None and segment_start != segment_end:
                print(
                    f"Getting all the Labeler dependent plugins output between the segment Start '{segment_start}' and End '{segment_end}'")
                ## last evaluated keys is now pagination w/ out the classifier key
                dependent_plugins_output = get_labeler_dependent_plugins_output(program, event, dependent_plugins, 
                segment_start, segment_end, last_evaluated_keys)

                output["DependentPluginsOutput"] = dependent_plugins_output

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
        request = json.loads(workflow_api.current_app.current_request.raw_body.decode(), parse_float=Decimal)

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
        last_evaluated_keys = request['LastEvaluatedKeys'] if 'LastEvaluatedKeys' in request else {}

        output = {}

        plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

        print(
            f"Getting all the non-optimized segments identified in the current/prior chunks for program '{program}', event '{event}', classifier '{classifier}' and chunk number '{chunk_number}'")
        # Put together a value for limiting chunk #
        query_params = {
            "IndexName": NON_OPTO_SEGMENTS_INDEX,
            "KeyConditionExpression":Key("PK").eq(f"{program}#{event}#{classifier}") & Key("NonOptoChunkNumber").lte(chunk_number),
            "Limit": 1
            }
        # Pass in the StartKey via 'classifier' name
        if classifier in last_evaluated_keys:
            print(f"Using LastEvaluatedKey '{last_evaluated_keys[classifier]}'")
            query_params["ExclusiveStartKey"]=last_evaluated_keys[classifier]
            
        response = ''
        if classifier in last_evaluated_keys and len(last_evaluated_keys) > 1:
            # We need to use a temp key
            temp_key = {'PK': last_evaluated_keys[classifier]['PK']}
            ######
            response = plugin_result_table.get_item(Key=temp_key)
            print(response)
            ## Add response as Items to keep rest of flow
            response['Items'] = [response['Item']]
            response['LastEvaluatedKey'] =last_evaluated_keys[classifier]
        else:
            response = plugin_result_table.query(**query_params)
            while not response['Items'] and 'LastEvaluatedKey' in response:
                # Use the last evaluated key from the response that returned no items (due to filter)
                query_params["ExclusiveStartKey"]=response['LastEvaluatedKey']
                response = plugin_result_table.query(**query_params)
                print(f'Response from inner query: {response}')

        # Remove classifier from input; don't need it anymore
        last_evaluated_keys.pop(classifier,'n/a')

        print(f'Response from query: {response}')
       
        if "Items" not in response or len(response["Items"]) < 1:
            print(f"No non-optimized segment was identified in the current/prior chunks for program '{program}', event '{event}', classifier '{classifier}' and chunk number '{chunk_number}'")

        else:
            print(
                f"Got one non-optimized segments identified in the current/prior chunks for program '{program}', event '{event}', classifier '{classifier}' and chunk number '{chunk_number}'")

            ## We're only working on 1 segment at a time
            segment = response["Items"][0]
            output['Segment'] = {'Item': segment}
            if 'LastEvaluatedKey' in response:
                output['Segment']['LastEvaluatedKey'] = response['LastEvaluatedKey']
            segment_start = segment["Start"]
            segment_end = segment["End"] if "End" in segment else None

            detectors_output = get_detectors_output_for_segment(program, event, detectors, search_win_sec, audio_track, start=segment_start)
            output["DependentDetectorsOutput"] = detectors_output

            # Get the Labeler dependent plugins output for the segment only if it is complete
            if segment_end is not None and segment_start != segment_end:
                print(f"Getting all the dependent detectors output around segment End '{segment_end}' within a search window of '{search_win_sec}' seconds")
                ## last evaluated keys is now pagination w/ out the classifier key
                output["DependentDetectorsOutput"].extend(get_detectors_output_for_segment(program, event, detectors, search_win_sec, audio_track,
                                                    end=segment_end))

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


def get_labeler_dependent_plugins_output(program, event, dependent_plugins, start, end, last_evaluated_keys) -> dict:
    if not dependent_plugins:
        print(
            f"Skipping the retrieval of Labeler dependent plugins output as no dependent plugin is present in the request")
        return {}

    dependent_plugins_output = {}

    plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

    for dependent_plugin in dependent_plugins:

        if last_evaluated_keys and dependent_plugin not in last_evaluated_keys:
            continue

        dependent_plugins_output[dependent_plugin] = {}

        query_params = {
            "KeyConditionExpression":Key("PK").eq(f"{program}#{event}#{dependent_plugin}") & Key("Start").between(start,end),
            "ConsistentRead":True
        }

        if PAGINATION_QUERY_LIMIT:
            query_params['Limit']=int(PAGINATION_QUERY_LIMIT)

        if dependent_plugin in last_evaluated_keys:
            query_params['ExclusiveStartKey']=last_evaluated_keys[dependent_plugin]

        response = plugin_result_table.query(**query_params)

        dependent_plugins_output[dependent_plugin]['Items'] = response["Items"]

        if 'LastEvaluatedKey' in response:
            dependent_plugins_output[dependent_plugin]['LastEvaluatedKey'] = response["LastEvaluatedKey"]

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
                KeyConditionExpression=Key("PK").eq(pk) & Key("Start").between(start - MAX_DETECTOR_QUERY_WINDOW_SECS, start),
                FilterExpression=Attr("End").gte(start)
            )

            if "Items" not in response or len(response["Items"]) < 1:
                response = plugin_result_table.query(
                    IndexName=PARTITION_KEY_END_INDEX,
                    KeyConditionExpression=Key("PK").eq(pk) & Key("End").between(start - search_win_sec, start)
                )

                detector_obj["Start"] = response["Items"]

            else:
                detector_obj["Start"] = response["Items"]

        if end:
            response = plugin_result_table.query(
                KeyConditionExpression=Key("PK").eq(pk) & Key("Start").between(end - MAX_DETECTOR_QUERY_WINDOW_SECS, end),
                FilterExpression=Attr("End").gte(end)
            )

            if "Items" not in response or len(response["Items"]) < 1:
                response = plugin_result_table.query(
                    KeyConditionExpression=Key("PK").eq(pk) & Key("Start").between(end, end + search_win_sec)
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
        last_evaluated_key = request['LastEvaluatedKey'] if 'LastEvaluatedKey' in request else {}

        plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

        query_params = {
                "KeyConditionExpression":Key("PK").eq(f"{program}#{event}#{classifier}"),
                "FilterExpression":Attr("OptoStart").exists() & Attr("OptoEnd").exists(),
                "ProjectionExpression":"PK, Start, End, OptoStart, OptoEnd",
                "ConsistentRead":True
        }

        ## Add start key if passed in
        if last_evaluated_key:
            query_params['ExclusiveStartKey']=last_evaluated_key

        response = plugin_result_table.query(**query_params)
        segments = {"Items": response["Items"]}

        ## Return LastEvaluatedKey in response
        if 'LastEvaluatedKey' in response:
            segments['LastEvaluatedKey'] = response['LastEvaluatedKey']

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