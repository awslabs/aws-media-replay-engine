#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import copy
import json
import os
import uuid
import boto3
from datetime import datetime
from botocore.config import Config
from MediaReplayEnginePluginHelper import DataPlane
from MediaReplayEngineWorkflowHelper import ControlPlane

s3_client = boto3.client("s3")
ExportOutputBucket = os.environ['ExportOutputBucket']

class ReplayDataExporter:

    def __init__(self, event):
        self._event = event
        self._event_name = self._event['detail']['Event']['Event']
        self._program_name = self._event['detail']['Event']['Program']
        self._replay_request_id = self._event['detail']['Event']['ReplayId']
        
        self._dataplane = DataPlane({})
        self._controlplane = ControlPlane()

    def generate_replay_data(self):
        '''
            Generates the Replay Data Export in JSON format
        '''
        event_info = self._get_additional_event_data()
        if 'EventDataExportLocation' in event_info:
            print(event_info['EventDataExportLocation'])
        
        # Load the default Event Data export data. We will need to re-use most of it and 
        # plugin the Replay payload into it.
        local_base_event_export = '/tmp/event_export.json'
        key_prefix_parts = event_info['EventDataExportLocation'].split('/')
        s3_client.download_file(ExportOutputBucket, f"{key_prefix_parts[3]}/{key_prefix_parts[4]}/{key_prefix_parts[5]}", local_base_event_export)

        
        with open(local_base_event_export) as f:
            self.__event_exported_data = json.load(f)

        replay = self._build_replay_request_payload()
        replay_segments = self._build_replay_segments()
        self.__event_exported_data.pop('Segments')
        self.__event_exported_data['Replay'] = replay
        self.__event_exported_data['Segments'] = replay_segments

        print("=================== REPLAY ========================")
        print(json.dumps(self.__event_exported_data))

        return self.__event_exported_data


    
    def _build_replay_request_payload(self):
        #Build Replay request payload
        replay_request = self._controlplane.get_replay_request(self._event_name, self._program_name, self._replay_request_id)
        self.__audioTrack = str(int(replay_request['AudioTrack']))

        replay_payload = {}
        if 'DurationbasedSummarization' in replay_request:
            replay_payload['Duration'] = replay_request['DurationbasedSummarization']['Duration']
            replay_payload['EqualDistribution'] = 'Y' if replay_request['DurationbasedSummarization']['EqualDistribution'] else 'N'

        replay_payload['Id'] = self._replay_request_id
        replay_payload['AudioTrack'] = replay_request['AudioTrack']

        features = []
        for feature in replay_request['Priorities']['Clips']:
            feature_selected = {}
            feature_selected['FeatureName'] = feature['AttribName']
            feature_selected['FeatureValue'] = feature['AttribValue']
            if replay_request['ClipfeaturebasedSummarization']:
                feature_selected['Include'] = feature['Include']
            else:
                feature_selected['Weight'] = feature['Weight']

            features.append(feature_selected)

        replay_payload['FeaturesSelected'] = features
        replay_payload['ReplayFormat'] = "Mp4" if replay_request['CreateMp4'] else "Hls" if replay_request['CreateHls'] else 'N/A'
        replay_payload['Resolutions'] = replay_request['Resolutions']
        replay_payload['Catchup'] = 'Y' if replay_request['Catchup'] else 'N'

        if replay_request['CreateHls']:
            replay_payload['HlsThumbnailLoc'] = replay_request['HlsThumbnailLoc']
            replay_payload['HlsLocation'] = replay_request['HlsLocation']
        
        if replay_request['CreateMp4']:
            replay_payload['Mp4Location'] = replay_request['Mp4Location']
            replay_payload['Mp4ThumbnailLocation'] = replay_request['Mp4ThumbnailLocation']
        
        return replay_payload
    
    def _build_replay_segments(self):
        replay_segments = []
        # Get ReplayResults
        replay_results = self._dataplane.get_all_segments_for_replay(self._program_name, self._event_name, self._replay_request_id)
        print(f"got replay results = {replay_results}")
        for replay_result in replay_results:

            # First get all the segments which have been identified by the Event so far
            for segment in self.__event_exported_data['Segments']:
                print(f"segment info = {segment}")
                
                # Compare OptoStart and OptoEnd when Optimized
                if 'OptoStart' in replay_result and len(segment['OptoStart'].keys()) > 0:
                    #if self.__audioTrack in segment['OptoStart']:
                    print(f"Inside = {replay_result['OptoStart']}")
                    print(f"Inside = {segment['OptoStart'][self.__audioTrack]}")
                    if replay_result['OptoStart'] == segment['OptoStart'][self.__audioTrack]:
                        segment['FeaturesFound'] = replay_result['Features']
                        if 'OutputAttributesFound' in segment:
                            segment.pop('OutputAttributesFound')
                        replay_segments.append(segment)
                else:
                    if replay_result['Start'] == segment['Start']:
                        segment['FeaturesFound'] = replay_result['Features']
                        if 'OutputAttributesFound' in segment:
                            segment.pop('OutputAttributesFound')
                        replay_segments.append(segment)

        return replay_segments

    def _get_additional_event_data(self):
        '''
            Gets additional event data not received from the EventBridge Payload
        '''
        
        self.__orig_event_info = self._controlplane.get_event(self._event_name, self._program_name)
        return self.__orig_event_info

    def get_event_id(self):
        return self.__orig_event_info["Id"]

    