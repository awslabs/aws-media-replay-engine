# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import pytest
import json
import sys
import time
import boto3
import os
import logging
from datetime import datetime, timedelta, timezone
from utils.config_mgr import load_config
from utils.api_client import call_api
from fixtures.media_channel_fixture import get_byob_bucket_names
from channel import start_channel, stop_channel, get_channel_by_destination_bucket
from fixtures.event_dependency_data_fixture import create_event_dependent_data
from fixtures.event_dependency_data_fixture_without_optimizer import create_event_dependent_data_with_no_opto
from boto3.dynamodb.conditions import Key
from models.event_config import BYOBEventConfig
from common import wait_for_event_completion, get_event_recorder_data, get_segment_start_times

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logger = logging.getLogger()

CURRENT_PATH = os.path.dirname(__file__)
print(f"Current Path: {CURRENT_PATH}")

medialive_client = boto3.client("medialive")

# These are segment Start times. Will be only used for Assertion and not processing.
segments_starts = [2.502, 12.512, 22.523, 32.532, 42.542, 52.552]

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "past_event_byob_as_source"
    )

class TestByobEventGroup():

    
    def register_vod_byob_event(self, eventConfig: BYOBEventConfig, profile_name):
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
        event_config['SourceVideoBucket'] = eventConfig.SourceVideoBucket
        event_config['Profile'] = profile_name
        event_config['GenerateOptoClips'] = True if eventConfig.GenerateOptoClips else False
        event_config['GenerateOrigClips'] = True if eventConfig.GenerateOrigClips else False

        event_config.pop('Channel')
        call_api(path="event", api_method="POST", api_body=json.dumps(event_config))
        return event_config


    def process_byob_event(self, byob_bucket, eventConfig, profile_name, future_event=False):
        event_config = self.register_vod_byob_event(eventConfig, profile_name)
        # Now that BYOB Event has been registered, lets manually start the MediaLive channel to simulate an external process delivering chunks to an S3 Bucket
        channel_id=get_channel_by_destination_bucket(byob_bucket)

        # Update the Channel Destination to match s3ssl://BUCKET_NAME/PROGRAM/EVENT/PROFILE/PROGRAM_EVENT
        medialive_client.update_channel(ChannelId=channel_id, 
        Destinations=[
        {
            'Id': 'awsmre',
            'Settings': [
                {
                   'Url': f's3ssl://{byob_bucket}/{event_config["Program"]}/{event_config["Name"]}/{event_config["Profile"]}/{event_config["Program"]}_{event_config["Name"]}'
                },
            ]
        }
        ])

        if future_event:
            time.sleep(120) # Sleep for 2 mins to simulate start of Event in future

        start_channel(channel_id)

        time.sleep(300) # Sleep for 7 mins (CHANNEL START UP TIME + EVENT DURATION (2Mins)). 

        # Stop the MediaLive Channel
        stop_channel(channel_id)

        time.sleep(120) # Sleep for 2 mins (To let the channel stop and get into IDLE state). 

        return event_config
    

    def assert_events_no_optimizer(self, byob_bucket, event_config, profile_name, future_event=False):

        event_config = self.process_byob_event(byob_bucket, event_config, profile_name, future_event)
        
        # We try for Event Completion in the next 2.5 mins 
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

        # No Optimized Segments should be created
        assert len(otpo_segments) == 0

        # Assert Optimized and Original Segment Start times
        #for i in range(0, len(segments_starts)):
        #    assert float(orig_segments[i]['Start']) == segments_starts[i]

        self.assert_persisted_segment_start_times(event_config)

    def assert_events(self, byob_bucket, event_config, profile_name, future_event=False):

        event_config = self.process_byob_event(byob_bucket, event_config, profile_name, future_event)
        
        # We try for Event Completion in the next 2.5 mins 
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
        #for i in range(0, len(segments_starts)):
        #    assert float(opto_segments[i]['OptoStart']) == segments_starts[i]
        #    assert float(orig_segments[i]['Start']) == segments_starts[i]

        self.assert_persisted_segment_start_times(event_config)

    def assert_persisted_segment_start_times(self, event_config):
        # Assert that the Segments in Datastore (retrieved via DataPlane API) is as expected 
        api_route = f"event/{event_config['Name']}/program/Regression/profileClassifier/TestSuite-EventTest-SegmentPassThrough100/track/1/segments/v2?limit=10"
        ddb_persisted_segment_start_times = get_segment_start_times(api_route)
        for i in range(0, 3):
            assert float(ddb_persisted_segment_start_times[i]) == segments_starts[i]

    @pytest.mark.past_event_byob_as_source
    def test_past_byob_event_with_passthrough_profile_orig_and_opto_clips(self, get_byob_bucket_names, create_event_dependent_data):
        dep_data = create_event_dependent_data
        byob_bucket = get_byob_bucket_names[0]

        eventConfig = BYOBEventConfig(GenerateOptoClips=True, GenerateOrigClips=True, FutureEvent=False, SourceVideoBucket=byob_bucket, EventName="TestSuite-PassThrough-BYOB-WithClips")
        self.assert_events(byob_bucket, eventConfig, "TestSuite-EventTestPassThroughProfile")

    @pytest.mark.past_event_byob_as_source
    def test_byob_past_event_with_passthrough_profile_with_Opto_clips(self, get_byob_bucket_names, create_event_dependent_data):
        dep_data = create_event_dependent_data
        byob_bucket = get_byob_bucket_names[1]
        eventConfig = BYOBEventConfig(GenerateOptoClips=True, GenerateOrigClips=False, FutureEvent=False, SourceVideoBucket=byob_bucket, EventName="TestSuite-PassThrough-BYOB-WithOptoClips")
        self.assert_events(byob_bucket, eventConfig, "TestSuite-EventTestPassThroughProfile")
        

    @pytest.mark.past_event_byob_as_source
    def test_byob_past_event_with_passthrough_profile_with_Orig_clips(self, get_byob_bucket_names, create_event_dependent_data):
        dep_data = create_event_dependent_data
        byob_bucket = get_byob_bucket_names[2]
        eventConfig = BYOBEventConfig(GenerateOptoClips=False, GenerateOrigClips=True, FutureEvent=False, SourceVideoBucket=byob_bucket, EventName="TestSuite-PassThrough-BYOB-WithOrigClips")
        self.assert_events(byob_bucket, eventConfig, "TestSuite-EventTestPassThroughProfile")

    @pytest.mark.past_event_byob_as_source
    def test_byob_past_event_with_passthrough_profile_with_no_clips(self, get_byob_bucket_names, create_event_dependent_data):
        dep_data = create_event_dependent_data
        byob_bucket = get_byob_bucket_names[3]
        eventConfig = BYOBEventConfig(GenerateOptoClips=False, GenerateOrigClips=False, FutureEvent=False, SourceVideoBucket=byob_bucket, EventName="TestSuite-PassThrough-BYOB-WithNoClips")
        self.assert_events(byob_bucket, eventConfig, "TestSuite-EventTestPassThroughProfile")


    @pytest.mark.past_event_byob_as_source_without_optimizer
    def test_past_byob_event_orig_and_opto_clips_without_optimizer(self, get_byob_bucket_names, create_event_dependent_data_with_no_opto):
        dep_data = create_event_dependent_data_with_no_opto
        byob_bucket = get_byob_bucket_names[0]
        eventConfig = BYOBEventConfig(GenerateOptoClips=True, GenerateOrigClips=True, FutureEvent=False, SourceVideoBucket=byob_bucket, EventName="TestSuite-PassThrough-BYOB-WithClips-NoOptoPlugin")
        self.assert_events_no_optimizer(byob_bucket, eventConfig, "TestSuite-EventTestPassThroughProfile-WithoutOptimizer")



    # FUTURE EVENTS
    @pytest.mark.future_event_byob_as_source
    def test_future_byob_event_with_passthrough_profile_orig_and_opto_clips(self, get_byob_bucket_names, create_event_dependent_data):
        dep_data = create_event_dependent_data
        byob_bucket = get_byob_bucket_names[0]
        eventConfig = BYOBEventConfig(GenerateOptoClips=True, GenerateOrigClips=True, FutureEvent=True, SourceVideoBucket=byob_bucket, EventName="TestSuite-Future-BYOB-WithClips")
        self.assert_events(byob_bucket, eventConfig, "TestSuite-EventTestPassThroughProfile", True)

    @pytest.mark.future_event_byob_as_source
    def test_future_past_byob_event_with_passthrough_profile_with_Opto_clips(self, get_byob_bucket_names, create_event_dependent_data):
        dep_data = create_event_dependent_data
        byob_bucket = get_byob_bucket_names[1]
        eventConfig = BYOBEventConfig(GenerateOptoClips=True, GenerateOrigClips=False, FutureEvent=True, SourceVideoBucket=byob_bucket, EventName="TestSuite-Future-BYOB-WithOptoClips")
        self.assert_events(byob_bucket, eventConfig, "TestSuite-EventTestPassThroughProfile", True)
        

    @pytest.mark.future_event_byob_as_source
    def test_future_byob_event_with_passthrough_profile_with_Orig_clips(self, get_byob_bucket_names, create_event_dependent_data):
        dep_data = create_event_dependent_data
        byob_bucket = get_byob_bucket_names[2]
        eventConfig = BYOBEventConfig(GenerateOptoClips=False, GenerateOrigClips=True, FutureEvent=True, SourceVideoBucket=byob_bucket, EventName="TestSuite-Future-BYOB-WithOrigClips")
        self.assert_events(byob_bucket, eventConfig, "TestSuite-EventTestPassThroughProfile", True)

    @pytest.mark.future_event_byob_as_source
    def test_future_byob_event_with_passthrough_profile_with_no_clips(self, get_byob_bucket_names, create_event_dependent_data):
        dep_data = create_event_dependent_data
        byob_bucket = get_byob_bucket_names[3]
        eventConfig = BYOBEventConfig(GenerateOptoClips=False, GenerateOrigClips=False, FutureEvent=True, SourceVideoBucket=byob_bucket, EventName="TestSuite-Future-BYOB-WithNoClips")
        self.assert_events(byob_bucket, eventConfig, "TestSuite-EventTestPassThroughProfile", True)

    @pytest.mark.future_event_byob_as_source_without_optimizer
    def test_future_byob_event_orig_and_opto_clips_without_optimizer(self, get_byob_bucket_names, create_event_dependent_data_with_no_opto):
        dep_data = create_event_dependent_data_with_no_opto
        byob_bucket = get_byob_bucket_names[0]
        eventConfig = BYOBEventConfig(GenerateOptoClips=True, GenerateOrigClips=True, FutureEvent=True, SourceVideoBucket=byob_bucket, EventName="TestSuite-FutureEvent-WithClips-NoOptoPlugin")
        self.assert_events_no_optimizer(byob_bucket, eventConfig, "TestSuite-EventTestPassThroughProfile-WithoutOptimizer", True)