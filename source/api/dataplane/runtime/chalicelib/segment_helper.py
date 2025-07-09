# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import decimal
import json
import os
import urllib.parse
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr, Key
from chalice import ChaliceViewError, NotFoundError
from chalicelib import replace_decimals
from chalicelib.common import create_signed_url, populate_segment_data_matching
from aws_lambda_powertools import Logger


PLUGIN_RESULT_TABLE_NAME = os.environ['PLUGIN_RESULT_TABLE_NAME']
CLIP_PREVIEW_FEEDBACK_TABLE_NAME = os.environ['CLIP_PREVIEW_FEEDBACK_TABLE_NAME']
CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_CLASSIFIER_START_INDEX = os.environ[
    'CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_CLASSIFIER_START_INDEX']

ddb_resource = boto3.resource("dynamodb")
logger = Logger(service="aws-mre-dataplane-api")

def get_event_segment_metadata_v2(name, program, classifier, tracknumber, segment_api):
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

    query_params = segment_api.current_app.current_request.query_params
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
        logger.info(e)
        logger.info(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        logger.info(e)
        logger.info(f"Unable to get the Event '{name}' in Program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to get the Event '{name}' in Program '{program}': {str(e)}")

    else:
        ret_val = {
            "LastEvaluatedKey": response["LastEvaluatedKey"] if "LastEvaluatedKey" in response else "",
            "Items": replace_decimals(final_response)
        }

        return ret_val






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
                if 'Label' in item:
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
        logger.info(f"Unable to retrieve Plugin results '{name}' in Program '{program}': {str(e)}")
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

    if 'Label' in clipItem:
        clip[f"{clipItem['PluginName']}-{clipItem['Label']}"] = 1
        clip['featureAt'] = max(0, clipItemStartTime - startTime)

    return None if len(clip.keys()) == 0 else clip


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

    # logger.info(f"inside get_clip_signed_url - {replace_decimals(plugin_response['Items'])}")
    for res in replace_decimals(plugin_response['Items']):
        if mode == 'Original':
            return create_signed_url(res['OriginalClipLocation'][str(audioTrack)]) if len(res['OriginalClipLocation'][str(audioTrack)]) > 0 else ""
        else:
            return create_signed_url(res['OptimizedClipLocation'][str(audioTrack)]) if len(res['OptimizedClipLocation'][str(audioTrack)]) > 0 else ""

    return ""

