# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import json
import urllib.parse
import boto3
import decimal
from decimal import Decimal
from chalice import Blueprint
from chalice import IAMAuthorizer
from chalice import ChaliceViewError, BadRequestError, NotFoundError
from botocore.client import ClientError
from boto3.dynamodb.conditions import Key, Attr
from jsonschema import validate, ValidationError
from chalicelib import load_api_schema, replace_decimals
from chalicelib.segment_helper import get_event_segment_metadata_v2, get_clip_metadata
from chalicelib.common import get_event_segment_metadata


segment_api = Blueprint(__name__)


PLUGIN_RESULT_TABLE_NAME = os.environ['PLUGIN_RESULT_TABLE_NAME']
CLIP_PREVIEW_FEEDBACK_TABLE_NAME = os.environ['CLIP_PREVIEW_FEEDBACK_TABLE_NAME']
CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_CLASSIFIER_START_INDEX = os.environ[
    'CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_CLASSIFIER_START_INDEX']

authorizer = IAMAuthorizer()

ddb_resource = boto3.resource("dynamodb")
s3_client = boto3.client("s3")

API_SCHEMA = load_api_schema()


@segment_api.route('/clip/result', cors=True, methods=['POST'], authorizer=authorizer)
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
        result = json.loads(segment_api.current_app.current_request.raw_body.decode(), parse_float=Decimal)

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

@segment_api.route('/event/{name}/program/{program}/profileClassifier/{classifier}/track/{tracknumber}/segments/for/edl',
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

@segment_api.route('/event/{name}/program/{program}/profileClassifier/{classifier}/track/{tracknumber}/segments/v2', cors=True,
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
    return get_event_segment_metadata_v2(name, program, classifier, tracknumber, segment_api)

@segment_api.route('/event/{name}/program/{program}/profileClassifier/{classifier}/track/{tracknumber}/segments', cors=True,
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


@segment_api.route('/event/{name}/program/{program}/clipstart/{start}/clipduration/{duration}/track/{tracknumber}/classifier/{classifier}/org/previewinfo',
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

@segment_api.route('/event/{name}/program/{program}/clipstart/{start}/clipduration/{duration}/track/{tracknumber}/classifier/{classifier}/opt/previewinfo',
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



@segment_api.route('/clip/preview/feedback', cors=True, methods=['POST'], authorizer=authorizer)
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
        request = json.loads(segment_api.current_app.current_request.raw_body.decode())
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


@segment_api.route('/clip/preview/program/{program}/event/{event}/classifier/{classifier}/start/{start_time}/track/{audio_track}/reviewer/{reviewer}/feedback',
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



@segment_api.route('/event/program/export/all/segments', cors=True, methods=['PUT'], authorizer=authorizer)
def get_all_event_segments():
    """
    Returns the Segment Metadata based on the segments found during Segmentation/Optimization process.

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    input = json.loads(segment_api.current_app.current_request.raw_body.decode(), parse_float=Decimal)
    name = input['Name']
    program = input['Program']
    classifier = input['Classifier']
    output_attributes = input['OutputAttributes']  # List
    plugins_in_profile = input['PluginsInProfile']  # List
    limit = int(input["Limit"]) if 'Limit' in input else 200
    last_start_value = input["LastStartValue"] if 'LastStartValue' in input else None

    
    print(f"output_attributes ...... {output_attributes}")
    print(f"plugins_in_profile ...... {plugins_in_profile}")

    
    try:
        # Get Clip Feedback for every segment Clip
        clip_preview_table = ddb_resource.Table(CLIP_PREVIEW_FEEDBACK_TABLE_NAME)
        plugin_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

        # Get Event Segment Details
        # From the PluginResult Table, get the Clips Info
        if not last_start_value:
            
            query = {
                'KeyConditionExpression': Key("PK").eq(f"{program}#{name}#{classifier}"),
                'ScanIndexForward': True,
                'Limit': limit
            }
        else:
             query = {
                'KeyConditionExpression': Key("PK").eq(f"{program}#{name}#{classifier}") & Key('Start').gt(last_start_value),
                'ScanIndexForward': True,
                'Limit': limit
            }   


        response = plugin_table.query(**query)
        plugin_responses = response['Items'] if 'Items' in response else None
        if plugin_responses:
            last_start_value = plugin_responses[len(plugin_responses) - 1]['Start']
        else:
            last_start_value = None


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

            segment_output_attributes = isOutputAttributeFoundInSegment(program, name, plugins_in_profile, res['Start'], output_attributes)

            if len(segment_output_attributes) > 0:
                segment_info['FeaturesFound'] = segment_output_attributes

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
        return {
            "Segments": replace_decimals(all_segments),
            "LastStartValue": last_start_value
        }



def isOutputAttributeFoundInSegment(program, event, plugins, segment_start, output_attributes):

    attributes_in_segment = []

    # For all Plugins in the profile, based on the Segment Start time +-1 
    # check if a Output Attribute exists with value True
    plugin_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

    for plugin in plugins:

        response = plugin_table.query(
            KeyConditionExpression=Key("ProgramEventPluginName").eq(f"{program}#{event}#{plugin}") & Key('Start').between(
                segment_start - decimal.Decimal(0.1), segment_start + decimal.Decimal(0.1)),
            ScanIndexForward=True,
            IndexName='ProgramEventPluginName_Start-index'
        )

        segment_info = response["Items"]

        while "LastEvaluatedKey" in response:
            response = plugin_table.query(
                KeyConditionExpression=Key("ProgramEventPluginName").eq(f"{program}#{event}#{plugin}") & Key('Start').between(
                segment_start - decimal.Decimal(0.1), segment_start + decimal.Decimal(0.1)),
                ScanIndexForward=True,
                ExclusiveStartKey=response["LastEvaluatedKey"],
                IndexName='ProgramEventPluginName_Start-index'
            )
            segment_info.extend(response["Items"])

        # Most cases this would just be One Segment matching the Start time
        for segment_item in segment_info:
            for output_attribute in output_attributes:
                if output_attribute in segment_item:
                    # If Attribute value is True, we have a Match
                    if segment_item[output_attribute]:
                        attributes_in_segment.append(output_attribute)

    
    return attributes_in_segment