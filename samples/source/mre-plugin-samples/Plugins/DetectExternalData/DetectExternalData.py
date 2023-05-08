# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import traceback
import ast
import dateutil.parser
from datetime import timedelta
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key, Attr
from MediaReplayEnginePluginHelper import DataPlane
from MediaReplayEnginePluginHelper import PluginHelper
from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import Status

ddb_resource = boto3.resource('dynamodb')


def replace_decimals(obj):
    if isinstance(obj, list):
        return [replace_decimals(o) for o in obj]
    elif isinstance(obj, dict):
        return {k: replace_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    else:
        return obj

def lambda_handler(event, context):
    print("Lambda got the following event:\n", event)
    results = []

    try:
        # Initialize the MRE Plugin Helper library
        mre_dataplane = DataPlane(event)
        mre_pluginhelper = PluginHelper(event)
        mre_outputhelper = OutputHelper(event)

        # Get all the required metadata from the event to query the DynamoDB data source
        plugin_config = mre_pluginhelper.get_plugin_configuration()
        ddb_table = plugin_config["lookup_ddb_table"]
        game_id = plugin_config["game_id"]
        frame_rate = event["Input"]["Metadata"]["HLSSegment"]["FrameRate"]
        event_start_str = event["Event"]["Start"]
        hls_segment_start_secs = event["Input"]["Metadata"]["HLSSegment"]["StartTime"]
        hls_segment_duration_secs = event["Input"]["Metadata"]["HLSSegment"]["Duration"]

        # Calculate Event Start and Chunk Start/End timestamps
        event_start_utc = dateutil.parser.parse(event_start_str)
        chunk_start_utc = event_start_utc + timedelta(seconds=hls_segment_start_secs)
        chunk_start_str = chunk_start_utc.isoformat()
        chunk_end_utc = chunk_start_utc + timedelta(seconds=hls_segment_duration_secs)
        chunk_end_str = chunk_end_utc.isoformat()
        table_resource = ddb_resource.Table(ddb_table)
        response = table_resource.query(
            # Update the line below to reflect the correct partition key and timestamp attributes for your table
            KeyConditionExpression=Key("partition_key").eq(f"mygameid#game#{game_id}"),
            FilterExpression=Attr("wall_clock").between(chunk_start_str, chunk_end_str)
        )
        plays = replace_decimals(response["Items"])

        while "LastEvaluatedKey" in response:
            response = table_resource.query(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                KeyConditionExpression=Key("partition_key").eq(f"mygameid#game#{game_id}"),
                FilterExpression=Attr("wall_clock").between(chunk_start_str, chunk_end_str)
            )
            plays.extend(replace_decimals(response["Items"]))

        if not plays or len(plays) < 1:
            print(f"Skipping the detection of events as no plays were found in the data source for the current HLS segment between '{chunk_start_utc}' and '{chunk_end_utc}'")
        else:
            print(f"Found {len(plays)} plays in the data source for the current HLS segment between '{chunk_start_str}' and '{chunk_end_str}'")

            # Extract the different events happening in the play
            for play in plays:
                # Start
                play_start_utc = dateutil.parser.parse(play["wall_clock"])
                play_start_secs = (play_start_utc - event_start_utc).total_seconds()

                # Events in the play
                events_to_detect = ast.literal_eval(plugin_config["events_to_detect"]) # Pass the events to detect from external data as a plugin config
                total_yards = 0
                delta = 0

                for play_event in play["details"]:
                    category = play_event["category"]

                    if category in events_to_detect:
                        if category in ["touchdown", "extra_point", "field_goal"]:
                            label = category

                        # If the event is either a rush or pass, check the yards covered
                        elif category in ["rush", "pass_completion"]:
                            yards = play_event["yards"]
                            total_yards += yards

                            if yards < 10:
                                label = category + "_below_10_yards"
                            elif 10 <= yards <= 20:
                                label = category + "_between_10_and_20_yards"
                            elif yards > 20:
                                label = category + "_above_20_yards"
                            else:
                                continue

                        else:
                            label = category

                        delta += round((frame_rate / 1000), 3)
                        result = {
                            "Start": play_start_secs + delta, # Add a delta to the Start of play to differentiate multiple features (categories) detected by the same plugin
                            "Label": label,
                            label: "True"
                        }
                        results.append(result)

            print("Results: ", results)

            # Persist plugin results for later use
            mre_dataplane.save_plugin_results(results)

        # Update the processing status of the plugin (required)
        mre_outputhelper.update_plugin_status(Status.PLUGIN_COMPLETE)

        # Add the results of the plugin to the payload (required if the plugin status is "complete"; Optional if the plugin has any errors)
        mre_outputhelper.add_results_to_output(results)
        
        return mre_outputhelper.get_output_object()

    except Exception as e:
        print(f"Encountered an exception while detecting events happening in the play: {str(e)}")
        print(traceback.format_exc())

        # Update the processing status of the plugin
        mre_outputhelper.update_plugin_status(Status.PLUGIN_ERROR)

        # Re-raise the exception for StepFunction callback
        raise
