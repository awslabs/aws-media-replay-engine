#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json
import os

import boto3
from MediaReplayEngineWorkflowHelper import ControlPlane
from shared.MreEventDataExporter import EventDataExporter
from shared.MreReplayDataExporter import ReplayDataExporter

EB_EVENT_BUS_NAME = os.environ['EB_EVENT_BUS_NAME']
ExportOutputBucket = os.environ['ExportOutputBucket']

s3_client = boto3.client("s3")
eb_client = boto3.client("events")


def GenerateDataExport(event, context):
    print(json.dumps(event))
    controlplane = ControlPlane()

    # Export Event Data when Clips are being generated
    if event['detail']['Event']['EventType'] in ["EVENT_CLIP_GEN"]:

        if event['detail']['Event']['EventType'] == "EVENT_CLIP_GEN":
            event_name = event['detail']['Event']['EventInfo']['Event']['Name']
            program_name = event['detail']['Event']['EventInfo']['Event']['Program']
        else:
            event_name = event['detail']['Event']['EventInfo']['EventName']
            program_name = event['detail']['Event']['EventInfo']['ProgramName']

        event_data_gen = EventDataExporter(event)
        event_data = event_data_gen.generate_event_data()
        print(json.dumps(event_data))

        event_info = event_data_gen.get_event_info()
        event_id = event_info['Id']

        # Save to S3
        create_tmp_file(event_data, "event_export.json")
        s3_location_key_prefix = f"base_event_export/{event_id}/{event_id}_event_export.json"
        s3_client.upload_file("/tmp/event_export.json", ExportOutputBucket, s3_location_key_prefix)

        #Update the S3 Location for the Event in DDB
        controlplane.update_event_data_export_location(event_name, program_name, f"s3://{ExportOutputBucket}/{s3_location_key_prefix}", "Y")
        # Notify EventBridge
        detail = {
            "State": "BASE_EVENT_DATA_EXPORTED",
            "Event": {
                "EventInfo": event['detail']['Event']['EventInfo'],
                "EventExportS3Location": f"s3://{ExportOutputBucket}/{s3_location_key_prefix}",
                "EventType": "EVENT_DATA"
            }
        }
        eb_client.put_events(
            Entries=[
                {
                    "Source": "awsmre",
                    "DetailType": "Base Event Data Exported",
                    "Detail": json.dumps(detail),
                    "EventBusName": EB_EVENT_BUS_NAME
                }
            ]
        )
    # Export Replay Data when Replay has been generated
    elif event['detail']['Event']['EventType'] in ["REPLAY_GEN_DONE", "REPLAY_GEN_DONE_WITH_CLIP"]:
        print(" Export Replay Data")
        replay_exporter =  ReplayDataExporter(event)
        replay_results = replay_exporter.generate_replay_data()

        # Save to S3
        replay_id = event['detail']['Event']['ReplayId']
        create_tmp_file(replay_results, "replay_export.json")
        s3_location_key_prefix = f"base_replay_export/{replay_id}/{replay_id}_replay_export.json"
        s3_client.upload_file("/tmp/replay_export.json", ExportOutputBucket, s3_location_key_prefix)    

        #Update the S3 Location for the Replay in DDB
        controlplane.update_replay_data_export_location(
            event['detail']['Event']['Event'], 
            event['detail']['Event']['Program'], 
            event['detail']['Event']['ReplayId'], 
            f"s3://{ExportOutputBucket}/{s3_location_key_prefix}", 
            "Y")

        # Notify EventBridge
        detail = {
            "State": "BASE_REPLAY_DATA_EXPORTED",
            "Event": {
                "Event": event['detail']['Event']['Event'],
                "Program": event['detail']['Event']['Program'],
                "ReplayId": event['detail']['Event']['ReplayId'],
                "ReplayExportS3Location": f"s3://{ExportOutputBucket}/{s3_location_key_prefix}",
                "EventType": "REPLAY_DATA_EXPORT"
            }
        }
        eb_client.put_events(
            Entries=[
                {
                    "Source": "awsmre",
                    "DetailType": "Base Replay Data Exported",
                    "Detail": json.dumps(detail),
                    "EventBusName": EB_EVENT_BUS_NAME
                }
            ]
        )


def create_tmp_file(file_content, filename):
    with open(f"/tmp/{filename}", "w") as output:
        json.dump(file_content, output, ensure_ascii=False)

