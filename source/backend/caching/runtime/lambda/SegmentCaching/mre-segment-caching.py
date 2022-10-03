#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json
import traceback
import os
import boto3
import botocore
from math import ceil
from datetime import datetime, timezone
from dateutil.parser import parse
from threading import Thread, current_thread
from queue import Queue

from MediaReplayEngineWorkflowHelper import ControlPlane
from MediaReplayEnginePluginHelper import DataPlane

PLUGIN_TABLE = os.environ["PLUGIN_TABLE"]
SEGMENT_CACHE_BUCKET = os.environ["SEGMENT_CACHE_BUCKET"]
EB_EVENT_BUS_NAME = os.environ["EB_EVENT_BUS_NAME"]
ENABLE_CUSTOM_METRICS = os.environ["ENABLE_CUSTOM_METRICS"]
MAX_NUMBER_OF_THREADS = int(os.environ["MAX_NUMBER_OF_THREADS"])

s3_client = boto3.client("s3")
ddb_resource = boto3.resource("dynamodb")
eb_client = boto3.client("events")
cw_client = boto3.client("cloudwatch")


def is_obj_exists_in_s3(bucket, key):
    print(f"Checking if key '{key}' exists in bucket '{bucket}'")

    try:
        s3_client.head_object(Bucket=bucket, Key=key)

    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            print(f"The S3 object={bucket}/{key} does not exist")
            return False

        else:
            print(f"Client-side error while trying to access the S3 object={bucket}/{key}. \
                More details on the error below: \n{str(e)}")
            return False

    except Exception as e:
        print(f"Error while trying to access the S3 object={bucket}/{key}. \
                More details on the error below: \n{str(e)}")
        return False

    else:
        return True


def get_obj_from_s3(bucket, key):
    print(f"Getting key '{key}' from bucket '{bucket}'")

    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)

    except botocore.exceptions.ClientError as e:
        print(f"Client-side error while trying to access the S3 object={bucket}/{key}. \
            More details on the error below: \n{str(e)}")
        return {}

    except Exception as e:
        print(f"Error while trying to access the S3 object={bucket}/{key}. \
                More details on the error below: \n{str(e)}")
        return {}

    else:
        return json.loads(response["Body"].read().decode("utf-8"))


def put_obj_to_s3(bucket, key, obj):
    if not obj:
        print("Object to put in S3 is empty")
        return

    print(f"Putting object into the S3 location: {bucket}/{key}")

    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(obj).encode("utf-8")
        )

    except Exception as e:
        print(f"Error in persisting object to {bucket}/{key}. \
                More details on the error below: \n{str(e)}")


def get_plugin_item_from_ddb(plugin_name, plugin_version):
    plugin_table = ddb_resource.Table(PLUGIN_TABLE)

    response = plugin_table.get_item(
        Key={
            "Name": plugin_name,
            "Version": plugin_version
        },
        ProjectionExpression="SupportedMediaType, OutputAttributes",
        ConsistentRead=True
    )

    if "Item" in response:
        return response["Item"]

    return None


def get_output_attr_for_plugin(plugin_name, plugin_version):
    plugin_with_output_attr = {}

    item = get_plugin_item_from_ddb(plugin_name, plugin_version)

    if item:
        plugin_with_output_attr[plugin_name] = {
            "SupportedMediaType": item["SupportedMediaType"],
            "OutputAttributes": list(item["OutputAttributes"].keys()) if "OutputAttributes" in item else []
        }

    return plugin_with_output_attr


def get_replay_featurers_with_output_attr(profile, bucket, key):
    replay_featurers_with_output_attr = {}

    print("Getting all the Featurer plugins needed for replay along with their output attributes from Profile object and Plugin DDB")

    if "Classifier" in profile:
        classifier = profile["Classifier"]

        replay_featurers_with_output_attr.update(get_output_attr_for_plugin(classifier["Name"], classifier["Version"]))

        if "DependentPlugins" in classifier:
            for d_plugin in classifier["DependentPlugins"]:
                replay_featurers_with_output_attr.update(get_output_attr_for_plugin(d_plugin["Name"], d_plugin["Version"]))

    if "Labeler" in profile:
        labeler = profile["Labeler"]

        replay_featurers_with_output_attr.update(get_output_attr_for_plugin(labeler["Name"], labeler["Version"]))

        if "DependentPlugins" in labeler:
            for d_plugin in labeler["DependentPlugins"]:
                replay_featurers_with_output_attr.update(get_output_attr_for_plugin(d_plugin["Name"], d_plugin["Version"]))

    if "Featurers" in profile:
        for featurer in profile["Featurers"]:
            replay_featurers_with_output_attr.update(get_output_attr_for_plugin(featurer["Name"], featurer["Version"]))

            if "DependentPlugins" in featurer:
                for d_plugin in featurer["DependentPlugins"]:
                    replay_featurers_with_output_attr.update(get_output_attr_for_plugin(d_plugin["Name"], d_plugin["Version"]))

    # Cache the featurers with output attributes in S3
    put_obj_to_s3(bucket, key, replay_featurers_with_output_attr)

    return replay_featurers_with_output_attr


def put_events_to_event_bridge(detail_type, state, segment):
    try:
        print(f"Sending an event to EventBridge with state '{state}' for the segment with start '{segment['Start']}' and end '{segment['End']}'")

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
                f"Failed to send an event to EventBridge with state '{state}' for the segment with start '{segment['Start']}' and end '{segment['End']}'. More details below:")
            print(response["Entries"])

    except Exception as e:
        print(f"Unable to send an event to EventBridge for the segment with start '{segment['Start']}' and end '{segment['End']}': {str(e)}")


def get_replay_features_in_segment(thread_queue, dataPlaneHelper, program, event, featurer, featurer_media_type, featurer_output_attr, seg_start, seg_end, audio_track):
    thread_name = current_thread().name

    print(f"{thread_name}: Getting value for all the output attributes defined in the config of plugin '{featurer}'")

    if featurer_media_type == "Video":
        thread_queue.put(
            {
                "0": dataPlaneHelper.get_replay_features_in_segment(program, event, featurer, featurer_output_attr, seg_start, seg_end)
            }
        )

    elif featurer_media_type == "Audio":
        thread_queue.put(
            {
                audio_track: dataPlaneHelper.get_replay_features_in_segment(program, event, featurer, featurer_output_attr, seg_start, seg_end, audio_track)
            }
        )

    print(f"{thread_name}: Done")


def start_threads(threads):
    print(f"Starting {len(threads)} threads for performing the caching operation")
    for thread in threads:
        thread.start()


def join_threads(threads):
    print("Waiting for all the threads to complete")
    for thread in threads:
        thread.join()


def put_custom_metric(metric_name, metric_value, dimensions):
    if ENABLE_CUSTOM_METRICS.lower() in ["yes", "y"]:
        print(f"Sending custom metric value '{metric_value}' with '{len(dimensions)}' dimensions to CloudWatch")

        cw_client.put_metric_data(
            Namespace="MRE",
            MetricData=[
                {
                    "MetricName": metric_name,
                    "Dimensions": dimensions,
                    "Value": metric_value * 1000,
                    "Unit": "Milliseconds"
                }
            ]
        )


def cache_segment_and_features(replay_featurers_with_output_attr, eb_state, program, event, event_start, segment, audio_track):
    dataPlaneHelper = DataPlane({})

    cache_start_time = datetime.now(timezone.utc)

    seg_start = segment["Start"]
    seg_end = segment["End"]

    event_start_dt = parse(event_start)
    cur_utc_dt = datetime.now(timezone.utc)
    hour_elapsed = ceil((cur_utc_dt - event_start_dt).total_seconds() / 3600)

    print(f"Caching segment having start '{seg_start}' and end '{seg_end}' with {len(replay_featurers_with_output_attr)} number of featurers")

    cached_segment_features = {
        "Start": seg_start,
        "End": seg_end,
        "FeaturesDataPoints": {
            "0": [],
            audio_track: []
        }
    }

    if eb_state == "OPTIMIZED_SEGMENT_END":
        cached_segment_features["OptoStart"] = segment["OptoStart"]
        cached_segment_features["OptoEnd"] = segment["OptoEnd"]

        classifier_name = segment["Classifier"]
        eb_detail_type = "Optimized Segment Caching Status"
        new_eb_state = "OPTIMIZED_SEGMENT_CACHED"

    else:
        classifier_name = segment["PluginName"]
        eb_detail_type = "Segment Caching Status"
        new_eb_state = "SEGMENT_CACHED"

    # Create groups of up to MAX_NUMBER_OF_THREADS to cache segment and related featurers in parallel
    replay_featurers = list(replay_featurers_with_output_attr.keys())
    replay_featurers_group = [replay_featurers[i:i + MAX_NUMBER_OF_THREADS] for i in range(0, len(replay_featurers), MAX_NUMBER_OF_THREADS)]
    print("Featurers Group length:", len(replay_featurers_group))

    # Queue to collect output of all the threads
    thread_queue = Queue()

    for featurer_group in replay_featurers_group:
        threads = []

        for featurer in featurer_group:
            featurer_media_type = replay_featurers_with_output_attr[featurer]["SupportedMediaType"]
            featurer_output_attr = replay_featurers_with_output_attr[featurer]["OutputAttributes"]

            if not featurer_output_attr:
                print(f"Ignoring plugin '{featurer}' for caching as no OutputAttributes are present in its config")

            else:
                threads.append(Thread(target=get_replay_features_in_segment, args=(thread_queue, dataPlaneHelper, program, event, featurer, featurer_media_type, featurer_output_attr, seg_start, seg_end, audio_track,)))

        if threads:
            # Start all the threads
            start_threads(threads)

            # Wait for all the threads to complete
            join_threads(threads)

            # Gather the output of all the threads from the Queue
            while not thread_queue.empty():
                item = thread_queue.get()

                if "0" in item:
                    cached_segment_features["FeaturesDataPoints"]["0"].extend(item["0"])

                if audio_track in item:
                    cached_segment_features["FeaturesDataPoints"][audio_track].extend(item[audio_track])

        else:
            print("No OutputAttributes found to cache in the Featurers group:", featurer_group)

    cache_obj_s3_key = f"{program}/{event}/{hour_elapsed}/Seg_{seg_start}_{seg_end}_{audio_track}.json"

    # Store the cached object in S3
    put_obj_to_s3(SEGMENT_CACHE_BUCKET, cache_obj_s3_key, cached_segment_features)

    cache_end_time = datetime.now(timezone.utc)
    cache_time_in_secs = (cache_end_time - cache_start_time).total_seconds()
    print(f"Caching Duration: {cache_time_in_secs} seconds")

    # Update segment in the Plugin Result table with elapsed hour
    dataPlaneHelper.add_attribute_to_existing_segment(program, event, classifier_name, seg_start, "HourElapsed", hour_elapsed)

    # Send the caching status to EventBridge
    put_events_to_event_bridge(eb_detail_type, new_eb_state, segment)

    # Send the caching duration as custom metric to CloudWatch
    put_custom_metric("SegmentCachingTime", cache_time_in_secs, [{'Name': 'Function', 'Value': 'MRESegmentCaching'}, {'Name': 'Program', 'Value': program}, {'Name': 'Event', 'Value': event}])


def lambda_handler(event, context):
    try:
        controlPlaneHelper = ControlPlane()

        eb_state = event["detail"]["State"]
        segment = event["detail"]["Segment"]
        event_name = segment["Event"]
        program_name = segment["Program"]
        profile_name = segment["ProfileName"]
        audio_track = segment["AudioTrack"] if "AudioTrack" in segment else "1"

        profile = controlPlaneHelper.get_profile(profile_name)

        # Don't take any action if the EB state is "SEGMENT_END" and there's an Optimizer in the profile
        if "Optimizer" in profile and eb_state == "SEGMENT_END":
            print("Got 'SEGMENT_END' as the EventBridge state but ignoring as there is an Optimizer in the profile")
            print("Caching will happen when the EventBridge state is 'OPTIMIZED_SEGMENT_END'")
            return

        replay_featurers_s3_key = f"{program_name}/{event_name}/{profile_name}/replay_featurers_with_output_attr.json"
        is_replay_featurers_in_cache = False

        if is_obj_exists_in_s3(SEGMENT_CACHE_BUCKET, replay_featurers_s3_key):
            replay_featurers_with_output_attr = get_obj_from_s3(SEGMENT_CACHE_BUCKET, replay_featurers_s3_key)
            is_replay_featurers_in_cache = True if replay_featurers_with_output_attr else False

        if not is_replay_featurers_in_cache:
            replay_featurers_with_output_attr = get_replay_featurers_with_output_attr(profile, SEGMENT_CACHE_BUCKET, replay_featurers_s3_key)

        if not replay_featurers_with_output_attr:
            print("Profile does not contain any Featurer plugin used for Replay. Nothing to cache.")
            return

        else:
            event_start = controlPlaneHelper.get_event(event_name, program_name)["Start"]
            cache_segment_and_features(replay_featurers_with_output_attr, eb_state, program_name, event_name, event_start, segment, audio_track)

    except Exception as e:
        print(f"Encountered an exception while caching the segment and its related featurers:\n{str(e)}")
        print(traceback.format_exc())
