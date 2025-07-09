# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
import pytest
import json
import sys
from chalice import ChaliceViewError, BadRequestError, NotFoundError, ConflictError, Response
import os
from datetime import datetime, timedelta, timezone
from utils.config_mgr import load_config
from utils.api_client import call_api, ApiUrlType
import time
import boto3
from boto3.dynamodb.conditions import Key, Attr
from models.event_config import MediaLiveEventConfig, BYOBEventConfig
import logging
from filelock import FileLock
from common import wait_for_event_completion, get_event_recorder_data, get_segment_start_times
from fixtures.media_channel_fixture import get_channel_ids
from fixtures.event_dependency_data_fixture import create_event_dependent_data
from fixtures.event_dependency_data_fixture_without_optimizer import create_event_dependent_data_with_no_opto


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logger = logging.getLogger()

CURRENT_PATH = os.path.dirname(__file__)
print(f"Current Path: {CURRENT_PATH}")

# These are segment Start times. Will be only used for Assertion and not processing.
segments_starts = [2.502, 12.512, 22.523, 32.532, 42.542, 52.552]



class TestEventGroup():
    
    def register_vod_media_live_event(self, eventConfig: MediaLiveEventConfig, profile_Name):
        event_config = load_config(f"{CURRENT_PATH}/config/EventPassThrough.json")
        cur_utc_time = datetime.utcnow()
        now = datetime.now(timezone.utc)
        timestamp = int(datetime.timestamp(now))

        event_name = f"{eventConfig.EventName}-{timestamp}"

        if eventConfig.FutureEvent:
            start_time = cur_utc_time + timedelta(minutes=2)
        else:
            # Assign a StartTime in the Past. This will start the Channel
            start_time = cur_utc_time - timedelta(minutes=1)
        
        event_config['Name'] = event_name
        event_config['Start'] = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
        event_config['Channel'] = eventConfig.Channel
        event_config['Profile'] = profile_Name #"TestSuite-EventTestPassThroughProfile"
        event_config['GenerateOptoClips'] = True if eventConfig.GenerateOptoClips else False
        event_config['GenerateOrigClips'] = True if eventConfig.GenerateOrigClips else False
        event_config['GenerateOrigThumbNails'] = True if eventConfig.GenerateOrigThumbNails else False
        event_config['GenerateOptoThumbNails'] = True if eventConfig.GenerateOptoThumbNails else False


        call_api(path="event", api_method="POST", api_body=json.dumps(event_config))
        return event_config
    

    def process_event(self, eventConfig, profile_Name, future_event=False):
        event_config = self.register_vod_media_live_event(eventConfig, profile_Name)

        if future_event:
            time.sleep(500) # Sleep for 9 mins (FUTURE TIME (2 Mins) + CHANNEL START UP TIME + EVENT DURATION (2Mins) + Buffer for Channel to stop and get into IDLE state). 
        else:
            time.sleep(420) # Sleep for 7 mins (CHANNEL START UP TIME + EVENT DURATION (2Mins) + Buffer for Channel to stop and get into IDLE state). 

        return event_config

    def assert_persisted_segment_start_times(self, event_config):
        # Assert that the Segments in Datastore (retrieved via DataPlane API) is as expected 
        api_route = f"event/{event_config['Name']}/program/Regression/profileClassifier/TestSuite-EventTest-SegmentPassThrough100/track/1/segments/v2?limit=10"
        ddb_persisted_segment_start_times = get_segment_start_times(api_route)
        for i in range(0, 3):
            assert float(ddb_persisted_segment_start_times[i]) == segments_starts[i]


    def assert_events_no_optimizer(self, event_config):
        # We keep checking for Event Completion in the next 5 mins
        is_event_complete = wait_for_event_completion(event_config)
        recorded_event_data = get_event_recorder_data(event_config)
        # Event is Complete
        assert is_event_complete == True
        assert len(recorded_event_data) >= 6

        # Assert every segment Start time
        orig_segments = [segment for segment in recorded_event_data if segment['SegmentEventType'].startswith('SEGMENT')]

        # Sort based on Start Time
        orig_segments.sort(key=lambda x: x['Start'])

        # Assert Original Segments
        otpo_segments = [segment for segment in recorded_event_data if segment['SegmentEventType'].startswith('OPTIMIZED_SEGMENT')]

        # No Optimized Segments should exist
        assert len(otpo_segments) == 0

        # Assert Optimized and Original Segment Start times
        for i in range(0, len(segments_starts)):
            assert float(orig_segments[i]['Start']) == segments_starts[i]

        # Assert that the Segments in Datastore (retrieved via DataPlane API) is as expected 
        self.assert_persisted_segment_start_times(event_config)
    
    def assert_events(self, event_config):
         # We keep checking for Event Completion in the next 5 mins
        is_event_complete = wait_for_event_completion(event_config)
        recorded_event_data = get_event_recorder_data(event_config)
        # Event is Complete
        assert is_event_complete == True
        assert len(recorded_event_data) >= 6

        # Assert every segment Start time
        orig_segments = [segment for segment in recorded_event_data if segment['SegmentEventType'].startswith('SEGMENT')]

        # Sort based on Start Time
        orig_segments.sort(key=lambda x: x['Start'])

        # Assert Original Segments
        opto_segments = [segment for segment in recorded_event_data if segment['SegmentEventType'].startswith('OPTIMIZED_SEGMENT')]

        # Sort Ascending based on Start Time
        opto_segments.sort(key=lambda x: x['Start'])

        # Do we have the same number of Original and Optimized Segments ?
        assert len(orig_segments) == len(opto_segments)

        # Assert Optimized and Original Segment Start times
        for i in range(0, len(segments_starts)):
            assert float(opto_segments[i]['OptoStart']) == segments_starts[i]
            assert float(orig_segments[i]['Start']) == segments_starts[i]

        # Assert that the Segments in Datastore (retrieved via DataPlane API) is as expected 
        self.assert_persisted_segment_start_times(event_config)


    @pytest.mark.past_event_media_live_as_source
    def test_past_event_with_passthrough_profile_orig_and_opto_clips(self, get_channel_ids, create_event_dependent_data):
        dep_data = create_event_dependent_data
        eventConfig = MediaLiveEventConfig(GenerateOptoClips=True, GenerateOrigClips=True, FutureEvent=False, Channel=get_channel_ids[0], EventName="TestSuite-VodEvent-WithClips")
        event_config = self.process_event(eventConfig, "TestSuite-EventTestPassThroughProfile")
        self.assert_events(event_config)

        
    @pytest.mark.past_event_media_live_as_source
    def test_past_event_with_passthrough_profile_no_clips(self, get_channel_ids, create_event_dependent_data):
        dep_data = create_event_dependent_data
        eventConfig = MediaLiveEventConfig(GenerateOptoClips=False, GenerateOrigClips=False, FutureEvent=False, Channel=get_channel_ids[1], EventName="TestSuite-VodEvent-WithNoClips")
        event_config = self.process_event(eventConfig, "TestSuite-EventTestPassThroughProfile")
        self.assert_events(event_config)

    
    @pytest.mark.past_event_media_live_as_source
    def test_past_event_with_passthrough_profile_with_orig_clips(self, get_channel_ids, create_event_dependent_data):
        dep_data = create_event_dependent_data
        eventConfig = MediaLiveEventConfig(GenerateOptoClips=False, GenerateOrigClips=True, FutureEvent=False, Channel=get_channel_ids[2], EventName="TestSuite-VodEvent-WithOrigClips")
        event_config = self.process_event(eventConfig, "TestSuite-EventTestPassThroughProfile")
        self.assert_events(event_config)


    @pytest.mark.past_event_media_live_as_source
    def test_past_event_with_passthrough_profile_with_Opto_clips(self, get_channel_ids, create_event_dependent_data):
        dep_data = create_event_dependent_data
        eventConfig = MediaLiveEventConfig(GenerateOptoClips=True, GenerateOrigClips=False, FutureEvent=False, Channel=get_channel_ids[3], EventName="TestSuite-VodEvent-WithOptoClips")
        event_config = self.process_event(eventConfig, "TestSuite-EventTestPassThroughProfile")
        self.assert_events(event_config)

    #===========

    
    @pytest.mark.past_event_media_live_as_source_thumbnails_control
    def test_past_event_with_passthrough_profile_orig_and_opto_clips_thumbnails(self, get_channel_ids, create_event_dependent_data):
        dep_data = create_event_dependent_data
        eventConfig = MediaLiveEventConfig(GenerateOptoClips=True, GenerateOrigClips=True, GenerateOptoThumbNails=True, GenerateOrigThumbNails=True, FutureEvent=False, Channel=get_channel_ids[0], EventName="TestSuite-Vod-AllClips-BothThumbnails")
        event_config = self.process_event(eventConfig, "TestSuite-EventTestPassThroughProfile")
        self.assert_events(event_config)
    
    @pytest.mark.past_event_media_live_as_source_thumbnails_control
    def test_past_event_with_passthrough_profile_no_clips_thumbnails(self, get_channel_ids, create_event_dependent_data):
        dep_data = create_event_dependent_data
        eventConfig = MediaLiveEventConfig(GenerateOptoClips=False, GenerateOrigClips=False, GenerateOptoThumbNails=True, GenerateOrigThumbNails=True, FutureEvent=False, Channel=get_channel_ids[1], EventName="TestSuite-Vod-WithNoClips-BothThumbnails")
        event_config = self.process_event(eventConfig, "TestSuite-EventTestPassThroughProfile")
        self.assert_events(event_config)
    
    @pytest.mark.past_event_media_live_as_source_thumbnails_control
    def test_past_event_with_passthrough_profile_with_orig_clips_thumbnails(self, get_channel_ids, create_event_dependent_data):
        dep_data = create_event_dependent_data
        eventConfig = MediaLiveEventConfig(GenerateOptoClips=False, GenerateOrigClips=True, GenerateOptoThumbNails=False, GenerateOrigThumbNails=True, FutureEvent=False, Channel=get_channel_ids[2], EventName="TestSuite-Vod-OrigClips-OrigThumbnails")
        event_config = self.process_event(eventConfig, "TestSuite-EventTestPassThroughProfile")
        self.assert_events(event_config)
    
    @pytest.mark.past_event_media_live_as_source_thumbnails_control
    def test_past_event_with_passthrough_profile_with_Opto_clips_thumbnails(self, get_channel_ids, create_event_dependent_data):
        dep_data = create_event_dependent_data
        eventConfig = MediaLiveEventConfig(GenerateOptoClips=True, GenerateOrigClips=False, GenerateOptoThumbNails=True, GenerateOrigThumbNails=False, FutureEvent=False, Channel=get_channel_ids[3], EventName="TestSuite-Vod-WithOptoClips-OptoThumbnails")
        event_config = self.process_event(eventConfig, "TestSuite-EventTestPassThroughProfile")
        self.assert_events(event_config)
    
    @pytest.mark.past_event_media_live_as_source_thumbnails_control
    def test_past_event_with_passthrough_profile_with_both_clips_no_thumbnails(self, get_channel_ids, create_event_dependent_data):
        dep_data = create_event_dependent_data
        eventConfig = MediaLiveEventConfig(GenerateOptoClips=True, GenerateOrigClips=True, GenerateOptoThumbNails=False, GenerateOrigThumbNails=False, FutureEvent=False, Channel=get_channel_ids[3], EventName="TestSuite-Vod-AllClips-NoThumbnails")
        event_config = self.process_event(eventConfig, "TestSuite-EventTestPassThroughProfile")
        self.assert_events(event_config)

    
    @pytest.mark.past_event_media_live_as_source_thumbnails_control
    def test_past_event_with_passthrough_profile_no_clips_opto_thumbnails(self, get_channel_ids, create_event_dependent_data):
        dep_data = create_event_dependent_data
        eventConfig = MediaLiveEventConfig(GenerateOptoClips=False, GenerateOrigClips=False, GenerateOptoThumbNails=True, GenerateOrigThumbNails=False, FutureEvent=False, Channel=get_channel_ids[1], EventName="TestSuite-Vod-WithNoClips-OptoThumbnail")
        event_config = self.process_event(eventConfig, "TestSuite-EventTestPassThroughProfile")
        self.assert_events(event_config)

    @pytest.mark.past_event_media_live_as_source_thumbnails_control
    def test_past_event_with_passthrough_profile_no_clips_orig_thumbnails(self, get_channel_ids, create_event_dependent_data):
        dep_data = create_event_dependent_data
        eventConfig = MediaLiveEventConfig(GenerateOptoClips=False, GenerateOrigClips=False, GenerateOptoThumbNails=False, GenerateOrigThumbNails=True, FutureEvent=False, Channel=get_channel_ids[1], EventName="TestSuite-Vod-WithNoClips-OrigThumbnail")
        event_config = self.process_event(eventConfig, "TestSuite-EventTestPassThroughProfile")
        self.assert_events(event_config)
    


    @pytest.mark.past_event_media_live_as_source_without_optimizer
    def test_past_event_with_passthrough_profile_orig_and_opto_clips_no_optimizer(self, get_channel_ids, create_event_dependent_data_with_no_opto):
        dep_data = create_event_dependent_data_with_no_opto
        eventConfig = MediaLiveEventConfig(GenerateOptoClips=True, GenerateOrigClips=True, FutureEvent=False, Channel=get_channel_ids[0], EventName="TestSuite-VodEvent-WithClips-NoOptimizer")
        event_config = self.process_event(eventConfig, "TestSuite-EventTestPassThroughProfile-WithoutOptimizer")
        self.assert_events_no_optimizer(event_config)


    ######### FUTURE EVENTS

    @pytest.mark.future_event_media_live_as_source
    def test_future_event_with_passthrough_profile_orig_and_opto_clips(self, get_channel_ids, create_event_dependent_data):
        dep_data = create_event_dependent_data
        eventConfig = MediaLiveEventConfig(GenerateOptoClips=True, GenerateOrigClips=True, FutureEvent=True, Channel=get_channel_ids[0], EventName="TestSuite-FutureEvent-WithClips")
        event_config = self.process_event(eventConfig, "TestSuite-EventTestPassThroughProfile", future_event=True)
        self.assert_events(event_config)

        
    @pytest.mark.future_event_media_live_as_source
    def test_future_event_with_passthrough_profile_no_clips(self, get_channel_ids, create_event_dependent_data):
        dep_data = create_event_dependent_data
        eventConfig = MediaLiveEventConfig(GenerateOptoClips=False, GenerateOrigClips=False, FutureEvent=True, Channel=get_channel_ids[1], EventName="TestSuite-FutureEvent-WithNoClips")
        event_config = self.process_event(eventConfig, "TestSuite-EventTestPassThroughProfile", future_event=True)
        self.assert_events(event_config)


    @pytest.mark.future_event_media_live_as_source
    def test_future_event_with_passthrough_profile_with_orig_clips(self, get_channel_ids, create_event_dependent_data):
        dep_data = create_event_dependent_data
        eventConfig = MediaLiveEventConfig(GenerateOptoClips=False, GenerateOrigClips=True, FutureEvent=True, Channel=get_channel_ids[2], EventName="TestSuite-FutureEvent-WithOrigClips")
        event_config = self.process_event(eventConfig, "TestSuite-EventTestPassThroughProfile", future_event=True)
        self.assert_events(event_config)


    @pytest.mark.future_event_media_live_as_source
    def test_future_event_with_passthrough_profile_with_Opto_clips(self, get_channel_ids, create_event_dependent_data):
        dep_data = create_event_dependent_data
        eventConfig = MediaLiveEventConfig(GenerateOptoClips=True, GenerateOrigClips=False, FutureEvent=True, Channel=get_channel_ids[3], EventName="TestSuite-FutureEvent-WithOptoClips")
        event_config = self.process_event(eventConfig, "TestSuite-EventTestPassThroughProfile", future_event=True)
        self.assert_events(event_config)


    @pytest.mark.future_event_media_live_as_source_without_optimizer
    def test_future_ml_event_with_passthrough_profile_orig_and_opto_clips_no_optimizer(self, get_channel_ids, create_event_dependent_data_with_no_opto):
        dep_data = create_event_dependent_data_with_no_opto
        eventConfig = MediaLiveEventConfig(GenerateOptoClips=True, GenerateOrigClips=True, FutureEvent=True, Channel=get_channel_ids[0], EventName="TestSuite-FutureEvent-WithClips-NoOptimizer")
        event_config = self.process_event(eventConfig, "TestSuite-EventTestPassThroughProfile-WithoutOptimizer")
        self.assert_events_no_optimizer(event_config)