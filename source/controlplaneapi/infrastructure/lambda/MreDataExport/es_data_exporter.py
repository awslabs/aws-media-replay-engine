#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import copy
import json
import os
import uuid
import boto3
from datetime import datetime
from botocore.config import Config
from shared.es_EventDataExporter import ESEventDataExporter
from shared.es_ReplayDataExporter import ESReplayDataExporter
from MediaReplayEngineWorkflowHelper import ControlPlane

EB_EVENT_BUS_NAME = os.environ['EB_EVENT_BUS_NAME']
ExportOutputBucket = os.environ['ExportOutputBucket']

s3_client = boto3.client("s3")
eb_client = boto3.client("events")

def GenerateDataExport(event, context):
    print(json.dumps(event))
    controlplane = ControlPlane()

    # Export Event Data when Clips are being generated
    if event['detail']['Event']['EventType'] == "EVENT_DATA":
        event_name = event['detail']['Event']['EventInfo']['Event']['Name']
        program_name = event['detail']['Event']['EventInfo']['Event']['Program']

        event_data_gen = ESEventDataExporter(event)
        event_data = event_data_gen.generate_event_data()

        print(json.dumps(event_data))
        
        event_info = event_data_gen.get_event_info()
        event_id = event_info['Id']

        # Save to S3
        create_tmp_file(event_data, "es_event_export.json")
        s3_location_key_prefix = f"final_event_export/{event_id}/{event_id}_es_event_export.json"
        s3_client.upload_file("/tmp/es_event_export.json", ExportOutputBucket, s3_location_key_prefix)

        #Update the S3 Location for the Event in DDB
        controlplane.update_event_data_export_location(event_name, program_name, f"s3://{ExportOutputBucket}/{s3_location_key_prefix}", "N")
    elif event['detail']['Event']['EventType'] == "REPLAY_DATA":

        print("XXXXXXXXXXXXXXXXXXX")
        print(event)
        replay_data_gen = ESReplayDataExporter(event)
        replay_data = replay_data_gen.generate_replay_data()

        print(json.dumps(replay_data))
        
        event_name = event['detail']['Event']['Event']
        program_name = event['detail']['Event']['Program']
        replay_id = event['detail']['Event']['ReplayId']

        # Save to S3
        create_tmp_file(replay_data, "es_replay_export.json")
        s3_location_key_prefix = f"final_replay_export/{replay_id}/{replay_id}_es_replay_export.json"
        s3_client.upload_file("/tmp/es_replay_export.json", ExportOutputBucket, s3_location_key_prefix)

        #Update the S3 Location for the Event in DDB
        
        controlplane.update_replay_data_export_location(
            event_name, 
            program_name, 
            replay_id, 
            f"s3://{ExportOutputBucket}/{s3_location_key_prefix}", 
            "N")
    
def create_tmp_file(file_content, filename):
    with open(f"/tmp/{filename}", "w") as output:
        json.dump(file_content, output, ensure_ascii=False)

