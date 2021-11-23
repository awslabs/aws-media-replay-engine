#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import copy
import json
import os
import uuid
import boto3
from datetime import datetime
from datetime import timedelta
from botocore.config import Config

ExportOutputBucket = os.environ['ExportOutputBucket']

s3_client = boto3.client("s3")

from MediaReplayEnginePluginHelper import DataPlane
from MediaReplayEngineWorkflowHelper import ControlPlane

class ESEventDataExporter:

    def __init__(self, event):
        self._event = event
        
        self._dataplane = DataPlane(event)
        self._controlplane = ControlPlane()
        self._event_info = self._get_additional_event_data()
        self._event_metadata = self._event_info['SourceVideoMetadata']

    def get_event_info(self):
        return self._event_info

    def _get_details_from_metadata(self):
        
        # TO get the asset_id consider the latest Playout
        sorted_playouts = sorted(self._event_metadata['playouts'], key=lambda x: x['createdTime'], reverse=True)

        # Get the first playout on the sorted list - Latest based on createdTime
        return sorted_playouts[0]['id'], sorted_playouts[0]['actualStartTime'],sorted_playouts[0]['actualEndTime'],sorted_playouts[0]['type']

    

    def _get_additional_event_data(self):
        '''
            Gets additional event data not received from the EventBridge Payload
        '''
        event_name = self._event['detail']['Event']['EventInfo']['Event']['Name']
        program_name = self._event['detail']['Event']['EventInfo']['Event']['Program']
        self.__orig_event_info = self._controlplane.get_event(event_name, program_name)
        return self.__orig_event_info
    
    def _build_event_data(self):
        
        event = {}

        if 'ProgramId' in self._event_info:
            event['BroadcastId'] = self._event_info['ProgramId']

        assetId, eventActualStartTime, eventActualEndTime, eventType = self._get_details_from_metadata()
        event['VideoId'] = assetId
        event['ActualStartTime'] = eventActualStartTime.split('.')[0] + 'Z' if '.' in eventActualStartTime else eventActualStartTime
        event['ActualEndTime'] = eventActualEndTime.split('.')[0] + 'Z' if '.' in eventActualEndTime else eventActualEndTime
        event['VideoType'] = eventType
        event['LogTime'] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            duration = datetime.strptime(event['ActualEndTime'],"%Y-%m-%dT%H:%M:%SZ") - datetime.strptime(event['ActualStartTime'],"%Y-%m-%dT%H:%M:%SZ")
            event['DurationInSecs'] = duration.total_seconds()
        except Exception as e:
            print(f"Error calclulating Duration - {str(e)}")

        #Store the Event's ActualStart and ActualEnd times for future use
        self.__event_actual_start_time = event['ActualStartTime']

        return event

    def _get_all_segments_for_event(self):
        base_event_data_export_loc = self._event['detail']['Event']['EventExportS3Location']
        s3_prefix_parts = base_event_data_export_loc.split('/')
        key_prefix = f"{s3_prefix_parts[3]}/{s3_prefix_parts[4]}/{s3_prefix_parts[5]}"
        tmp_filename = f"/tmp/{s3_prefix_parts[5]}"
        s3_client.download_file(ExportOutputBucket, key_prefix, tmp_filename)

        exported_event_data = ''
        with open(tmp_filename) as f:
            exported_event_data = json.load(f)

        return exported_event_data['Segments']

    def _build_segments_for_event(self):
        segments_payload = self._get_all_segments_for_event()

        '''
        This is the base format of Segments from the default MRe Export

        "Segments": [
            {
                "Start": 11.612,
                "End": 22.221,
                "OptoStart": {},
                "OptoEnd": {},
                "OptimizedClipLocation": {},
                "OriginalClipLocation": {
                    "1": ""
                },
                "OriginalThumbnailLocation": "",
                "Feedback": [],
                "OutputAttributesFound": [
                    "SetPoint",
                    "MatchPoint",
                    "GamePoint"
                ],
            }
        ]

        format this to customer specific ....

        "KeyEvents": [
            {
                “EventType”: “aws:mre:tennis:BreakPoint,
                ”eventActualStartTime": UTC DATETIME,
                ”eventActualEndTime": UTC DATETIME,
                “VideoPathLocations”: [
                { “1”: “” },
                “ “2”: “” } ],
                “ThumbnailPathLocation”: “”
            },
            {
                “EventType”: “aws:mre:tennis:MatchPoint,
                ”eventActualStartTime": UTC DATETIME,
                ”eventActualEndTime": UTC DATETIME,
                “VideoPathLocations”: [
                { “1”: “” },
                “ “2”: “” } ],
                “ThumbnailPathLocation”: “”
            },
        ]

        '''
        new_segments = []

        for segment in segments_payload:
            if 'OutputAttributesFound' in segment:
                for output_attrib in segment['OutputAttributesFound']:
                    seg = {}
                    seg['EventType'] = self._get_event_type(output_attrib)
                    seg['eventActualStartTime'] = self._get_segment_start_time(segment)
                    seg['eventActualEndTime'] = self._get_segment_end_time(segment)
                    seg['VideoPathLocations'] = self._get_clip_locations(segment)
                    seg['“ThumbnailPathLocation”'] = self._get_thumbnail_loc(segment)
                    new_segments.append(seg)

        return new_segments


    def generate_event_data(self):

        '''
            Generates the Event Data Export in JSON format
            {
                "aws:mre" : {
                    “BroadcastId”: “”,
                    “VideoId”: “”,
                    “LogTime”: “”,
                    “ActualStartTime”: “”,
                    “ActualEndTime”: “”,
                    “VideoType”: “”,
                    “Duration”: “”
                },
                "KeyEvents": [
                    {

                    },
                    {

                    }
                ]
            }
        '''
        event_data_export = {}
        event_payload = self._build_event_data()
        segment_payload = self._build_segments_for_event()
        event_data_export["aws:mre"] = event_payload
        event_data_export["KeyEvents"] = segment_payload
        return event_data_export
    
    def _get_thumbnail_loc(self, segment):

        if 'OptimizedThumbnailLocation' in segment:
            if len(segment['OptimizedThumbnailLocation'].keys()) > 0:
                return segment['OptimizedThumbnailLocation']
        return segment['OriginalThumbnailLocation']

    def _get_clip_locations(self, segment):
        clips_locs = []
        clip_loc = segment['OriginalClipLocation']

        if 'OptimizedClipLocation' in segment:
            if len(segment['OptimizedClipLocation'].keys()) > 0:
                clip_loc = segment['OptimizedClipLocation']

        
        for cliploc_audio_track, loc in clip_loc.items():
            clips_locs.append({
                cliploc_audio_track : loc
            })
        
        return clips_locs
    
    def _get_segment_start_time(self, segment):
        start_time = segment['Start']

        new_start_times = []
        if 'OptoStart' in segment:
            if len(segment['OptoStart'].keys()) > 0:
                for audio_track, startTime in segment['OptoStart'].items():
                    # Add the MRE specific Start time in Secs to the Event's Actual StartTime (in UTC)
                    tmp_new_start_time = datetime.strptime(self.__event_actual_start_time,"%Y-%m-%dT%H:%M:%SZ") + timedelta(seconds=startTime)
                    new_start_time = datetime.strftime(tmp_new_start_time, "%Y-%m-%dT%H:%M:%SZ")
                    new_start_times.append({
                        audio_track: new_start_time
                    })

        if len(new_start_times) > 0:
            return new_start_times
        
        # When No OptoStart found, we have a single Start time and not per AudioTrack
        tmp_new_start_time = datetime.strptime(self.__event_actual_start_time,"%Y-%m-%dT%H:%M:%SZ") + timedelta(seconds=start_time)
        new_start_time = datetime.strftime(tmp_new_start_time, "%Y-%m-%dT%H:%M:%SZ")
        return new_start_time

    def _get_segment_end_time(self, segment):
        end_time = segment['End']

        new_end_times = []
        if 'OptoEnd' in segment:
            if len(segment['OptoEnd'].keys()) > 0:
                for audio_track, endTime in segment['OptoEnd'].items():
                    # Add the MRE specific End time in Secs to the Event's Actual EndTime (in UTC)
                    tmp_new_end_time = datetime.strptime(self.__event_actual_start_time,"%Y-%m-%dT%H:%M:%SZ") + timedelta(seconds=endTime)
                    new_end_time = datetime.strftime(tmp_new_end_time, "%Y-%m-%dT%H:%M:%SZ")
                    new_end_times.append({
                        audio_track: new_end_time
                    })

        if len(new_end_times) > 0:
            return new_end_times
        
        # When No OptoStart found, we have a single End time and not per AudioTrack
        tmp_new_end_time = datetime.strptime(self.__event_actual_start_time,"%Y-%m-%dT%H:%M:%SZ") + timedelta(seconds=end_time)
        new_end_time = datetime.strftime(tmp_new_end_time, "%Y-%m-%dT%H:%M:%SZ")
        return new_end_time


    def _get_event_type(self, feature_name):
        feature_event_type_map = {
            "MatchPoint": "aws:mre:tennis:MatchPoint",
            "Ace": "aws:mre:tennis:Ace",
            "DoubleFaults": "aws:mre:tennis:DoubleFaults",
            "GamePoint": "aws:mre:tennis:GamePoint",
            "SetPoint": "aws:mre:tennis:SetPoint",
            "BreakPoint": "aws:mre:tennis:BreakPoint"
        }

        return feature_event_type_map[feature_name]
