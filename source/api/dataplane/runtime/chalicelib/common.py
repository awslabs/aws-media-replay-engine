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
from chalicelib import replace_decimals

s3_client = boto3.client("s3")
ddb_resource = boto3.resource("dynamodb")

PLUGIN_RESULT_TABLE_NAME = os.environ['PLUGIN_RESULT_TABLE_NAME']

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