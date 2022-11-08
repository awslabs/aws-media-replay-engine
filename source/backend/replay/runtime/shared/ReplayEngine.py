#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import copy
import decimal
import json
import os
import uuid
import boto3
import math
import urllib3
from decimal import Decimal
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr
from MediaReplayEngineWorkflowHelper import ControlPlane
from MediaReplayEnginePluginHelper import DataPlane
from shared.CacheSyncManager import CacheSyncManager
from shared.ReplayFeatureProcessor import ReplayFeatureProcessor
from shared.CacheDiscovery import CacheDiscovery
from aws_lambda_powertools import Logger
logger = Logger()


OUTPUT_BUCKET = os.environ['OutputBucket']
CACHE_BUCKET = os.environ['CACHE_BUCKET_NAME']
EB_EVENT_BUS_NAME = os.environ['EB_EVENT_BUS_NAME']

s3_client = boto3.client("s3")
ssm = boto3.client('ssm')
TIMEGROUP_MULTIPLIER = 2


class ReplayEngine:

    def __init__(self, event):

        self._controlplane = ControlPlane()
        self._dataplane = DataPlane({})

        self.__event = event

        if event['detail']['State'] == 'SEGMENT_CACHED' or event['detail']['State'] == 'OPTIMIZED_SEGMENT_CACHED':
            self._event = event['detail']['Segment']['Event']
        elif event['detail']['State'] == 'EVENT_END' or event['detail']['State'] == 'REPLAY_CREATED':
            self._event = event['detail']['Event']['Name']

        if event['detail']['State'] == 'SEGMENT_CACHED' or event['detail']['State'] == 'OPTIMIZED_SEGMENT_CACHED':
            self._program = event['detail']['Segment']['Program']
        elif event['detail']['State'] == 'EVENT_END' or event['detail']['State'] == 'REPLAY_CREATED':
            self._program = event['detail']['Event']['Program']

        if event['detail']['State'] == 'SEGMENT_CACHED' or event['detail']['State'] == 'OPTIMIZED_SEGMENT_CACHED':
            self._profile = event['detail']['Segment']['ProfileName']
        else:
            self._profile = self._get_profile_from_event()

        # Get Classifier from Profile
        self._classifier = self._get_profile()['Classifier']['Name']

        if event['detail']['State'] == 'OPTIMIZED_SEGMENT_CACHED':
            self._audio_track = event['detail']['Segment']['AudioTrack']
        elif event['detail']['State'] == 'SEGMENT_CACHED':
            self._audio_track = 1
        else:
            self._audio_track = event['detail']['Event']['AudioTrack']

        self._segment_feature_maping = []

        # This is the current ReplayRequest details
        self._replay_to_be_processed = self.__event['ReplayRequest'] if 'ReplayRequest' in self.__event else None

        # Logging ReplayId for better filtering in Logs
        if self._replay_to_be_processed:
            if 'ReplayId' in self._replay_to_be_processed:
                logger.append_keys(replay_id=str(self._replay_to_be_processed['ReplayId']))
                logger.append_keys(event_name=str(self._event))
                logger.append_keys(program_name=str(self._program))

        # CatchUp Replays will have Segment Dict coming in
        self.current_segment = event['detail']['Segment'] if self._is_catch_up_enabled() else {
        }

    def __does_current_segment_have_any_replay_feature(self, current_segment_cache_file_name):
        '''
            Returns True If segment has at least one Feature configured in ReplayRequest including the Feature value (bool)
            Returns False if this segment has no Features configured in ReplayRequest
        '''

        logger.info(
            f"Finding if Current segment has any replay features. Cache file opened = /tmp/{self._replay_to_be_processed['ReplayId']}/{current_segment_cache_file_name}")
        segment_feature_cache_file = open(
            f"/tmp/{self._replay_to_be_processed['ReplayId']}/{current_segment_cache_file_name}")
        segment_mapping_as_json = json.load(segment_feature_cache_file)

        '''
            self._replay_to_be_processed['Priorities']['Clips'] structure

            "Priorities": {
                "Clips": [
                    {
                        "AttribName": "Attribute40",
                        "AttribValue": true,
                        "Name": "DetectPassThrough90 | Attribute40 | true",
                        "PluginName": "DetectPassThrough90",
                        "Weight": 1
                    },
                    {
                        "AttribName": "Attribute41",
                        "AttribValue": true,
                        "Name": "DetectPassThrough100 | Attribute41 | true",
                        "PluginName": "DetectPassThrough100",
                        "Weight": 90
                    }.
                    {
                        "AttribName": "Attribute16",
                        "AttribValue": true,
                        "Name": "DetectPassThrough77 | Attribute16 | true",
                        "PluginName": "DetectPassThrough77",
                        "Weight": 2
                    }
                ]
        '''

        # For every feature enabled in the Replay Request
        for feature in self._replay_to_be_processed['Priorities']['Clips']:

            # Ensure we check the Features in both Audio and Video Sections of the Cache
            if 'FeaturesDataPoints' in segment_mapping_as_json:

                # Check in Video based Features
                if '0' in segment_mapping_as_json['FeaturesDataPoints']:
                    # Check Video based Feature data
                    for feature_data_point in segment_mapping_as_json['FeaturesDataPoints']["0"]:

                        # If any of the ReplayRequest Feature exists in the Segment
                        if feature['AttribName'] in feature_data_point:
                            # Ex. SegmentBySceneAndSR | score_change | true
                            feature_condition = feature['Name'].split("|")[-1]
                            if feature_data_point[feature['AttribName']] == True if feature_condition.lower().strip() == "true" else False:
                                return True

                # Check Audio based Feature data based on the current Audio Track
                if str(self._audio_track) in segment_mapping_as_json['FeaturesDataPoints']:
                    for feature_data_point in segment_mapping_as_json['FeaturesDataPoints'][str(self._audio_track)]:
                        # If any of the ReplayRequest Feature exists in the Segment
                        if feature['AttribName'] in feature_data_point:
                            # Ex. SegmentBySceneAndSR | score_change | true
                            feature_condition = feature['Name'].split("|")[-1]
                            if feature_data_point[feature['AttribName']] == True if feature_condition.lower().strip() == "true" else False:
                                return True

        return False

    def get_unique_segment_features_for_catchup(self, segments_with_features_from_new_cache_files):
        '''
            Matches Segments from new Cache Files with the existing replay created SegmentFeatures cache file to determine a Intersection 
            and remove all Duplicate Segments
        '''
        segments_with_features = []
        # If no Replay Cache exists,
        # if self._replay_to_be_processed['SegmentsFeaturesCacheFileLocation'] != '':
        try:
            # Get the CacheFile from S3 - This will be specific to the AudioTrack in ReplayRequest
            local_file = f"/tmp/{self._replay_to_be_processed['ReplayId']}/SegmentsFeaturesCache.json"
            s3_client.download_file(
                CACHE_BUCKET, f"replay-result-seg-cache/{self._replay_to_be_processed['ReplayId']}/SegmentsFeaturesCache.json", local_file)

            segment_feature_cache_file = open(local_file)
            segments_with_features_from_replay_cache_file = json.load(
                segment_feature_cache_file)

            # Make sure to start with all the Previous Replay Cached segments
            segments_with_features.extend(
                segments_with_features_from_replay_cache_file)

            for seg in segments_with_features_from_new_cache_files:  # this should be the last 10 segments
                segment_exists_in_cache = False
                # This list will typically get bigger for bigger events
                for segment in segments_with_features_from_replay_cache_file:
                    if seg["Start"] == segment["Start"]:
                        segment_exists_in_cache = True
                        break

                # Looks like we have a segment in the new Cache but not in the Rep;lay Processed Cache
                # Add it to the List
                if not segment_exists_in_cache:
                    segments_with_features.append(seg)
        # else:
        except Exception as e:
            logger.info('SEGMENT_FEATURE_MAPPING_CACHE_DOWNLOAD_ERROR - SegmentsFeaturesCache.json not downloaded , may not exist, which is ok if none of the previous segments having features.')
            segments_with_features.extend(
                segments_with_features_from_new_cache_files)

        return segments_with_features

    

    def initialize_segment_features(self):

        # Step1 : Get all Segments created so far. Also get the Features included in ReplayRequest
        #self._get_segments_for_event()  # stored in self._segments_created_so_far

        # Step2 : Build a unique list of S3 KeyPrefix Partitions - Sorted ASC by Segment Start time
        s3_key_prefixes = self.__get_s3_key_prefixes()

        # Step3 : Sync Cache from S3. How many S3 objects gets cached depends on CatchUp/NonCatchup
        '''
            This is the Cache file content structure - Segment to Feature Mapping
            {
                "OptoStart": 163.564,
                "End": 172.371,
                "OptoEnd": 172.371,
                "Start": 163.564,
                "FeaturesDataPoints": {
                    "0": [{
                            "FreeKick": false,
                            "End": 163.764,
                            "CornerKick": false,
                            "Start": 163.764,
                            "Label": "Near_View"
                        },
                        {
                            "FreeKick": false,
                            "End": 163.964,
                            "CornerKick": false,
                            "Start": 163.964,
                            "Label": "Near_View"
                        }
                    ],
                    "1": [{
                            "End": 163.764,
                            "Start": 163.764,
                            "Label": "Speech Present"
                        },
                        {
                            "End": 163.964,
                            "Start": 163.964,
                            "Label": "Speech Present"
                        }
                    ],
                    "2": [..]
                }
            }
        '''
        cache_mgr = CacheSyncManager(self._is_catch_up_enabled(), s3_key_prefixes, self._event,
                                     self._program,
                                     self._replay_to_be_processed['ReplayId'])

        cache_mgr.sync_cache()

        if self._is_catch_up_enabled():
            current_segment_cache_file_name = f"Seg_{self.current_segment['Start']}_{self.current_segment['End']}_{self._audio_track}.json"
            # Step 4 - For a CatchUp replay, check if current Segment has any features configured in the Replay Request? If no, SKIP the rest of the steps. Record this segment in DDB.
            if not self.__does_current_segment_have_any_replay_feature(current_segment_cache_file_name):

                # Update this Segment in the ReplayRequest "SegmentsToBeIgnored" attrib so we dont process this Segment Cache file to find features in future cycles
                #self._controlplane.update_segments_to_be_ignored(self._event,self._program, self._replay_to_be_processed['ReplayId'], current_segment_cache_file_name)

                # Update the ReplayRequest with current Segment's CacheFile name in the ReplayRequest "SegmentsToBeIgnored" attrib
                logger.info(
                    f"CURRENT Segment with Start {str(self.current_segment['Start'])} cache file name {current_segment_cache_file_name} has no ReplayRequest Feature's. IGNORING further processing for this Segment.")
                return False
            else:
                logger.info(
                    f"CURRENT Segment with Start {str(self.current_segment['Start'])} cache file name {current_segment_cache_file_name} HAS ONE OR MORE FEATURES !!! ")

        # Step 5 - Get all segments with Features mapped from Cache. This is a Multi-threaded process

        logger.info('Starting the Multi threaded process to find ReplayRequest Features in Segments from Cache ...')
        replay_feature_processor = ReplayFeatureProcessor(
            # Contains the Features that the ReplayRequest has been configured with
            self._replay_to_be_processed['Priorities']['Clips'],
            self._is_catch_up_enabled(),
            # list of Segment cache filenames,
            self._replay_to_be_processed['SegmentsToBeIgnored'] if 'SegmentsToBeIgnored' in self._replay_to_be_processed else [
            ],
            self._audio_track,
            self._event,
            self._program,
            self._replay_to_be_processed['ReplayId'],
            self._dataplane,
            False if 'IgnoreDislikedSegments' not in self._replay_to_be_processed else self._replay_to_be_processed['IgnoreDislikedSegments']
        )
        '''
        segments_with_features_from_new_cache_files structure

        [
            {
                "AudioTrack": 1,
                "End": 1701.697,
                "Features": [
                    {
                    "AttribName": "FreeKick",
                    "AttribValue": true,
                    "MultiplierChosen": 8,
                    "Name": "SegmentBySceneAndSR2 | FreeKick | true",
                    "PluginName": "SegmentBySceneAndSR2",
                    "Weight": 79
                    },
                    {
                    "AttribName": "free_kick",
                    "AttribValue": true,
                    "MultiplierChosen": 4,
                    "Name": "SegmentBySceneAndSR2 | free_kick | true",
                    "PluginName": "SegmentBySceneAndSR2",
                    "Weight": 39
                    }
                ],
                "OptoEnd": 1701.697,
                "OptoStart": 1688.422,
                "Start": 1690.939
            }
        ]
        '''

        # For CatchUp, this will be a list of the last 5 segment with features mapped
        # For NonCatchup, this will the full list of segment with features mapped
        segments_with_features_from_new_cache_files = replay_feature_processor.find_features_in_cached_files()
        logger.info(
            f'segments_with_features_from_new_cache_files={segments_with_features_from_new_cache_files}')

        # Step 6 - MAP Segments to Features - CatchUp Optimization - Get the existing Segments Features Cache File from S3. This is only for CatchUp replays as we dont want to re-process all Segments with Features.
        # We will re-use the Cache created after the previous Replay calculated and cached the results.
        # The new cache file may have a few segments which overlaps with the Previous Replay Cache content. We need to ignore such Segments so the replay calc doesn't account for the same segment twice.
        if self._is_catch_up_enabled():
            # This is a Mapping of ALL Segments with Features
            self._all_segments_with_features = segments_with_features_from_new_cache_files
            #logger.info('Optimizing 2 SegmentFeature list by creating an Intersection.')
            # self._all_segments_with_features = self.get_unique_segment_features_for_catchup(segments_with_features_from_new_cache_files) # This is a Mapping of Segments created so far with Features

            logger.info(
                f"CATCH UP _all_segments_with_features = {self._all_segments_with_features}")
        else:
            # This is a Mapping of ALL Segments with Features
            self._all_segments_with_features = segments_with_features_from_new_cache_files
            logger.info(
                f"NOT CATCH UP _all_segments_with_features = {self._all_segments_with_features}")

        # Sort Segments in Asc order based on Start time
        self._all_segments_with_features.sort(key=lambda x: x['Start'])

        logger.info(
            f"SORTED _all_segments_with_features before re-calculating Scores = {self._all_segments_with_features}")

        return True

    def create_tmp_file(self, file_content, filename):
        with open(f"/tmp/{filename}", "w") as output:
            json.dump(file_content, output, ensure_ascii=False)

    def cache_replay_calc_segment_feature_mapping_in_s3(self):
        '''
        Caches the Segment and Feature mapping into S3. This is a Global list before  which does not exclude any segments based on Scores etc.

        new_replay_segment_feature_cache_location structure

        [
            {
                "AudioTrack": 1,
                "End": 1701.697,
                "Features": [
                    {
                    "AttribName": "shot_saved",
                    "AttribValue": true,
                    "MultiplierChosen": 8,
                    "Name": "SegmentBySceneAndSR2 | shot_saved | true",
                    "PluginName": "SegmentBySceneAndSR2",
                    "Weight": 79
                    },
                    {
                    "AttribName": "free_kick",
                    "AttribValue": true,
                    "MultiplierChosen": 4,
                    "Name": "SegmentBySceneAndSR2 | free_kick | true",
                    "PluginName": "SegmentBySceneAndSR2",
                    "Weight": 39
                    }
                ],
                "OptoEnd": 1701.697,
                "OptoStart": 1688.422,
                'Score': 730,
                "Start": 1690.939
            }
        ]
        '''
        new_replay_segment_feature_cache_location = f"replay-result-seg-cache/{self._replay_to_be_processed['ReplayId']}/SegmentsFeaturesCache.json"
        # Save to S3
        self.create_tmp_file(self._all_segments_with_features,
                             f"{self._replay_to_be_processed['ReplayId']}-SegmentsFeaturesCache.json")
        s3_client.upload_file(
            f"/tmp/{self._replay_to_be_processed['ReplayId']}-SegmentsFeaturesCache.json", CACHE_BUCKET, new_replay_segment_feature_cache_location)

    def __get_s3_key_prefixes(self):
        '''
            Returns Unique cache S3 prefixes for the event based on which prefix a segment was found in
        '''

        # Each Segment has the HourElapsed attribute which will be used to construct
        # the S3 Key Prefix the Segment Cache is in.
        cache_discovery = CacheDiscovery (CACHE_BUCKET, self._program, self._event, self._profile)
        s3_key_prefixes = cache_discovery.discover_cache_key_prefixes()

        # for segment in self._segments_created_so_far:
        #     if 'HourElapsed' in segment:
        #         s3_key_prefix = f"{self._program}/{self._event}/{str(segment['HourElapsed'])}"
        #         if s3_key_prefix not in s3_key_prefixes:
        #             s3_key_prefixes.append(s3_key_prefix)

        logger.info(f"S3 Key Prefixes created so far ... = {s3_key_prefixes}")

        return s3_key_prefixes

    def _create_replay(self):

        # Only when a Replay is in Queued State, do we want to Update the Replay as In Progress
        if 'Status' in self._replay_to_be_processed:
            if self._replay_to_be_processed['Status'] == 'Queued':
                self.__mark_replay_in_progress()
        
        # The required segments with Features will get mapped out here
        # If a segment has not features that the Replay is Configured for, we come out of
        # the current processing cycle.
        if not self.initialize_segment_features():
            return False

        # Get Segments with Features. OptoStart and OptoEndtime of Segments will be Maps by default.
        # self.get_all_segments_with_features()

        # If We are dealing with Clip Based Features, we are done with Collecting the segments having Features, just push to DDB
        if not self._is_replay_duration_based():

            logger.info(
                f"-FINAL SEGMENTS SAVED IN REP RES - for {self._replay_to_be_processed['ReplayId']}--{json.dumps(self._all_segments_with_features)}")
            replay_res = self._persist_replay_metadata(
                self._all_segments_with_features)

            # Looks like replay results were not persisted. Race condition perhaps
            if not replay_res:
                logger.info(
                    f"Clip based replay. Replay results have not been persisted. Check for Race condition!!")
                return False

        else:
            logger.info('Duration based, calculating total duration of chosen Segments')
            debuginfo = []

            # replay_request_duration = self.__event['ReplayRequest']['DurationbasedSummarization']['Duration'] * 60 # In Secs
            # Secs
            replay_request_duration = self.__event['ReplayRequest']['DurationbasedSummarization']['Duration']

            # For Duration based, we need to check if the Sum of Segment Clip Duration is more than the Duration asked for in the
            # Reply Request. If yes, we calculate scores and pick the best segments. If no, we simply push the segments into DDB
            duration_result, duration = self._does_total_duration_of_all_segments_exceed_configured()
            if not duration_result:
                logger.info(
                    f"Total duration {duration} secs of chosen Segments within Replay Request duration {replay_request_duration} secs. Not calculating Scores and weights.")
                logger.info(
                    f"-FINAL SEGMENTS SAVED IN REP RES - for {self._replay_to_be_processed['ReplayId']}--{json.dumps(self._all_segments_with_features)}")
                replay_res = self._persist_replay_metadata(
                    self._all_segments_with_features, debuginfo)
                logger.info(
                    f"Total duration {duration} secs of chosen Segments is less than Replay Request duration {replay_request_duration} secs.")

                # Looks like replay results were not persisted. Race condition perhaps
                if not replay_res:
                    return False

            else:

                # If no Equal Distribution is sought, pick segments based on High Scores, duration
                if not self.__event['ReplayRequest']['DurationbasedSummarization']['EqualDistribution']:

                    logger.info(
                        f'Calculate Scores based on Weights .. total duration was {duration}')
                    self._calculate_segment_scores_basedon_weights(
                        self._all_segments_with_features)

                    '''
                    After Scoring, new structure includes "Score" attrib. For ex.

                    [
                        {
                            "AudioTrack": 1,
                            "End": 1701.697,
                            "Features": [
                                {
                                "AttribName": "FreeKick",
                                "AttribValue": true,
                                "MultiplierChosen": 8,
                                "Name": "SegmentBySceneAndSR2 | FreeKick | true",
                                "PluginName": "SegmentBySceneAndSR2",
                                "Weight": 79
                                },
                                {
                                "AttribName": "free_kick",
                                "AttribValue": true,
                                "MultiplierChosen": 4,
                                "Name": "SegmentBySceneAndSR2 | free_kick | true",
                                "PluginName": "SegmentBySceneAndSR2",
                                "Weight": 39
                                }
                            ],
                            "OptoEnd": 1701.697,
                            "OptoStart": 1688.422,
                            "Start": 1690.939,
                            "Score": 100
                        }
                    ]
                    '''

                    #logger.info("---- AFTER SORT - AllSegmentsWithFeatures ----")
                    # logger.info(self._all_segments_with_features)

                    # After each Segment has been scored, sort them in Desc based on Score
                    sorted_segments = sorted(
                        self._all_segments_with_features, key=lambda x: x['Score'], reverse=True)

                    logger.info(
                        "---- AFTER DESC SORT Before Filtering based on Duration and Score - AllSegmentsWithFeatures ----")
                    logger.info(sorted_segments)

                    # Find which segments needs to be Removed to meet the Duration Requirements in Replay Request
                    #total_duration_all = 0
                    total_duration = 0
                    final_segments = []

                    # Event if the last segment time makes the overall time to beyond the Duration limit,
                    # lets add that segment. The rest of the segments will be ignored since the Duration limit
                    # will be crossed.
                    last_segment_crossed_duration_limit = False
                    for segment in sorted_segments:

                        # This conditions is met when the Replay Duration has been exceeded. So stop processing all segments
                        if last_segment_crossed_duration_limit:
                            break

                        segment_duration = self._get_segment_duration_in_secs(
                            segment)
                        #total_duration_all += segment_duration

                        if (total_duration + segment_duration) <= replay_request_duration:
                            final_segments.append(segment)
                            total_duration += segment_duration
                        else:
                            if not last_segment_crossed_duration_limit:
                                last_segment_crossed_duration_limit = True
                                final_segments.append(segment)
                                total_duration += segment_duration
                            else:
                                logger.info(
                                    f"Ignoring segment - StartTime {segment['Start']}, EndTime {segment['End']} Segment Duration {segment_duration} secs - to avoid exceeding the replay duration limit of {replay_request_duration} secs.")

                    logger.info(
                        f"Duration if all segments considered would be {total_duration} secs")

                    # Finally Sort the Segments based on the Start time in Asc Order
                    sorted_final_segments = sorted(
                        final_segments, key=lambda x: x['Start'], reverse=False)
                    logger.info(
                        f"-FINAL SEGMENTS SAVED IN REP RES - for {self._replay_to_be_processed['ReplayId']}--{json.dumps(sorted_final_segments)}")
                    replay_res = self._persist_replay_metadata(
                        sorted_final_segments, debuginfo)

                    # Looks like replay results were not persisted. Race condition perhaps
                    if not replay_res:
                        return False

                else:

                    # Because Equal Distribution is being asked for,
                    # We will distribute the total segment duration into Multiple TimeGroups and Group segments within them based on Segment Start time.
                    # Within each TimeGroup, we will Score the Segments based on Weights and
                    # pick the Highest Scoring Segment by adhering to the Duration which will be the TimeGroup Duration
                    # Each Time Group will also have an Absolute time representation.
                    # For example, first Timegroup would be from 0 - 292 secs, 2nd from 292 to 584 secs .. the last one(t6th) from 1460 to 1752 Secs
                    # We will select segments whose StartTime falls in these Absolute time ranges to get a Equal Distribution

                    first_segment = self._all_segments_with_features[0]
                    last_segment = self._all_segments_with_features[-1]

                    start_of_first_segment_secs = first_segment['OptoStart'] if self._is_segment_optimized(
                        first_segment) else first_segment['Start']
                    end_of_last_segment_secs = last_segment['OptoEnd'] if self._is_segment_optimized(
                        last_segment) else last_segment['End']

                    logger.info(
                        f"First Seg starts at {start_of_first_segment_secs} secs")
                    logger.info(f"Last Seg Ends at {end_of_last_segment_secs} secs")

                    total_segment_duration_in_secs = end_of_last_segment_secs - \
                        start_of_first_segment_secs
                    logger.info(
                        f"total_segment_duration_in_secs = {total_segment_duration_in_secs} secs")

                    total_segment_duration_in_hrs = (
                        end_of_last_segment_secs - start_of_first_segment_secs) / 3600  # Hours
                    logger.info(
                        f"total_segment_duration_in_hrs = {total_segment_duration_in_hrs} hrs")

                    # Find how many Time Groups we need. If we have more than 1 Hr lets divide into multiple groups.
                    if total_segment_duration_in_secs > 3600:
                        no_of_time_groups = (
                            math.ceil(total_segment_duration_in_hrs) * 2) + TIMEGROUP_MULTIPLIER
                    else:
                        no_of_time_groups = TIMEGROUP_MULTIPLIER
                    logger.info(f"no_of_time_groups = {no_of_time_groups}")

                    # Calculate the TimeGroup time based on the Replay Request Duration
                    timegroup_time_in_secs = replay_request_duration / no_of_time_groups
                    logger.info(f"timegroup_time_in_secs = {timegroup_time_in_secs}")

                    # This represents the absolute time that should be added up for all TimeGroups
                    time_frame_in_time_group = round(
                        total_segment_duration_in_secs / no_of_time_groups, 2)

                    # Create a Dict of time groups with a Start and End time
                    # We will find segments which fall in them next
                    time_groups = []
                    total = 0
                    for x in range(no_of_time_groups):

                        if x == 0:
                            time_groups.append({
                                "TimeGroupStartInSecs": start_of_first_segment_secs,
                                "TimeGroupEndInSecs": start_of_first_segment_secs + time_frame_in_time_group,
                            })
                            total += start_of_first_segment_secs + time_frame_in_time_group
                        else:
                            time_groups.append({
                                "TimeGroupStartInSecs": total,
                                "TimeGroupEndInSecs": total + time_frame_in_time_group,
                            })
                            total += time_frame_in_time_group

                    logger.info(time_groups)

                    final_segments_across_timegroups = []
                    # TimeGroups will be Asc Order by Default based on how its Constructed above
                    for timegroup in time_groups:
                        segments_within_timegroup = self._get_segments_with_features_within_timegroup(
                            timegroup)

                        logger.info(f'Calculate Scores based on Weights .. ')
                        self._calculate_segment_scores_basedon_weights(
                            segments_within_timegroup)

                        # After each Segment has been scored, sort them in Desc based on Score
                        sorted_segments = sorted(
                            segments_within_timegroup, key=lambda x: x['Score'], reverse=True)

                        # Find which segments needs to be Removed to meet the Duration Requirements in Replay Request
                        #total_duration_all = 0
                        total_duration = 0
                        final_segments = []

                        # Event if the last segment time makes the overall time to beyond the Duration limit,
                        # lets add that segment. The rest of the segments will be ignored since the Duration limit
                        # will be crossed.
                        last_segment_crossed_duration_limit = False
                        for segment in sorted_segments:
                            # This conditions is met when the Replay Duration has been exceeded. So stop processing all segments
                            if last_segment_crossed_duration_limit:
                                break

                            segment_duration = self._get_segment_duration_in_secs(
                                segment)
                            #total_duration_all += segment_duration

                            if (total_duration + segment_duration) <= timegroup_time_in_secs:
                                final_segments.append(segment)
                                total_duration += segment_duration
                            else:
                                if not last_segment_crossed_duration_limit:
                                    last_segment_crossed_duration_limit = True
                                    final_segments.append(segment)
                                    total_duration += segment_duration
                                else:
                                    logger.info(
                                        f"Ignoring the segment - StartTime {segment['Start']}, EndTime {segment['End']} - to avoid exceeding the timegroup duration limit {timegroup_time_in_secs} secs")

                        # Finally Sort the Segments based on the Start time in Asc Order
                        sorted_final_segments = sorted(
                            final_segments, key=lambda x: x['Start'], reverse=False)
                        final_segments_across_timegroups.extend(
                            sorted_final_segments)

                    logger.info(
                        f"-FINAL SEGMENTS SAVED IN REP RES - for {self._replay_to_be_processed['ReplayId']}--{json.dumps(final_segments_across_timegroups)}")

                    # Persist all segment+features across all timegroups
                    replay_res = self._persist_replay_metadata(
                        final_segments_across_timegroups, debuginfo)
                    # Looks like replay results were not persisted. Race condition perhaps
                    if not replay_res:
                        return False

        return True

    def _get_segments_with_features_within_timegroup(self, timegroup):
        segments_within_timegroup = []
        for segment in self._all_segments_with_features:
            segment_startTime, segment_endTime = self._get_segment_start_and_end_times(
                segment)

            # Check if a Segments Startstime falls within the Timegroup Start and Endtimes
            if segment_startTime >= timegroup['TimeGroupStartInSecs'] and segment_startTime <= timegroup['TimeGroupEndInSecs']:
                segments_within_timegroup.append(segment)

        return segments_within_timegroup

    def _calculate_segment_scores_basedon_weights(self, segments_with_features):
        '''
            Seg 1
                |-> Feature 1 - Weight 1
                |-> Feature 2 - Weight 50
                |-> Feature 3 - Weight 90
            Seg 2
                |-> Feature 1 - Weight 1
                |-> Feature 2 - Weight 80
                |-> Feature 3 - Weight 0
            Seg 3
                |-> Feature 1 - Weight 45
                |-> Feature 2 - Weight 86
                |-> Feature 3 - Weight 15

            Seg 1 Score = 1  + 50 + 90 = 141
            Seg 2 Score = 1 + 80 + 0 = 81 
            Seg 3 Score = 45 + 86 + 15 = 146

            Sort Segments based on Scores - Desc
            Pick Segments Top down to meet the Duration
            If Only one Highest score segment gets selected, its ok even if it exceeds the duration

        '''

        for segment_feature in segments_with_features:
            score = self._calculate_score(segment_feature)
            segment_feature['Score'] = score

    def _calculate_score(self, segment):
        total_score = 0
        for feature in segment['Features']:
            total_score += feature['Weight']
        return total_score

    def _get_multiplier(self, weight):
        return math.ceil(weight / 10)

    def _get_segment_start_and_end_times(self, segment):
        if self._is_segment_optimized(segment):
            startTime = Decimal(str(segment['OptoStart']))
            endTime = Decimal(str(segment['OptoEnd']))
        else:
            startTime = Decimal(str(segment['Start']))
            endTime = Decimal(str(segment['End']))

        return startTime, endTime

    def _get_segment_duration_in_secs(self, segment):
        startTime, endTime = self._get_segment_start_and_end_times(segment)
        return endTime - startTime

    def _does_total_duration_of_all_segments_exceed_configured(self):
        duration = 0
        for segment_feature in self._all_segments_with_features:
            # Total Duration of Segment in Secs
            duration += self._get_segment_duration_in_secs(segment_feature)

        # return (True, duration) if duration > Decimal(str(self.__event['ReplayRequest']['DurationbasedSummarization']['Duration'])) * 60 else (False, duration)
        return (True, duration) if duration > Decimal(str(self.__event['ReplayRequest']['DurationbasedSummarization']['Duration'])) else (False, duration)

    def _persist_replay_metadata(self, segmentInfo, additionalInfo=None):
        '''
            Persists replay results. Handles Race conditions when a Old segments results tries to overwrite 
            new segments results for CatchUp.

            True if Persistance was a success. False if Race condition was found.
        '''

        # Grab all the Replay Results
        replay_results = []
        total_score_of_selected_segments = 0
        for segment_feature in segmentInfo:
            rep_res = {
                "AudioTrack": int(self._audio_track),
                "Start": segment_feature['Start'],
                "End": segment_feature['End'],
                "Score": segment_feature['Score'] if 'Score' in segment_feature else '-',
                "Features": segment_feature['Features']
            }

            if 'Score' in segment_feature:
                rep_res['Score'] = segment_feature['Score']

            # If a Valid Score exists, compute total Score for this Replay Run
            if rep_res['Score'] != '-':
                total_score_of_selected_segments += int(rep_res['Score'])

            if self._is_segment_optimized(segment_feature):
                rep_res['OptoStart'] = segment_feature['OptoStart']
                rep_res['OptoEnd'] = segment_feature['OptoEnd']

            replay_results.append(rep_res)

        replay_result_payload = {}
        replay_result_payload['Program'] = self._program
        replay_result_payload['Event'] = self._event
        replay_result_payload['ReplayId'] = self.__event['ReplayRequest']['ReplayId']
        replay_result_payload['Profile'] = self._profile
        replay_result_payload['Classifier'] = self._classifier
        replay_result_payload['AdditionalInfo'] = additionalInfo if additionalInfo is not None else [
        ]
        replay_result_payload['ReplayResults'] = replay_results
        replay_result_payload['TotalScore'] = total_score_of_selected_segments
        replay_result_payload["LastSegmentStartTime"] = self.current_segment['Start'] if self._is_catch_up_enabled() else 0
        

        update_result = self._dataplane.update_replay_result(replay_result_payload)
        return update_result

    """ @staticmethod
    def _mark_replay_complete(replayId, program, event):
        controlplane.update_replay_request_status(program, event, replayId, "Complete") """

    """  @staticmethod
    def _mark_replay_error(replayId, program, event):
        controlplane.update_replay_request_status(program, event, replayId, "Error") """

    def __mark_replay_in_progress(self):
        self._controlplane.update_replay_request_status(
            self._program, self._event, self.__event['ReplayRequest']['ReplayId'], "In Progress")

    # def _get_segments_for_event(self):
    #     self._segments_created_so_far = self._dataplane.get_all_segments_for_event(
    #         self._program, self._event, self._classifier)
    #     logger.info(
    #         f" List of Segments created so far ... = {self._segments_created_so_far}")

    def _get_event(self):
        return self._controlplane.get_event(self._event, self._program, )

    

    def _get_profile_from_event(self):
        event = self._get_event()
        return event['Profile']
        

    def _get_profile(self):
        return self._controlplane.get_profile(self._profile)

    def _get_featurers_by_profile(self):

        if self._profile == '':
            self._get_profile()

        # A List of Featurer names
        self._featurers = [feature_dict["Name"]
                           for feature_dict in self._profile['Featurers']]

    

    def _get_all_replays_for_opto_segment_end(self):
        '''
            Returns all Queued Replay Requests for the Program/Event and Audio Track
        '''
        return self._controlplane.get_all_replay_requests_for_event_opto_segment_end(self._program, self._event, int(self._audio_track))

    def _is_catch_up_enabled(self):
        '''
            Checks if a Replay Request is for Catch Up or not.
        '''
        if self._replay_to_be_processed:
            if 'Catchup' in self._replay_to_be_processed:
                if self._replay_to_be_processed['Catchup']:
                    return True

        return False

    def _is_replay_duration_based(self):
        '''
            Checks if the replay is Duration based or Clip based.
        '''
        return False if self._replay_to_be_processed['ClipfeaturebasedSummarization'] else True

    def _is_hls_enabled(self):
        if 'CreateHls' in self._replay_to_be_processed:  # Replay has HLS Enabled
            return True
        return False

    def _is_media_channel_enabled(self):
        if 'MediaTailorChannel' in self._replay_to_be_processed:
            return True
        return False

    def _is_segment_optimized(self, segment):
        if 'OptoStart' in segment and 'OptoEnd' in segment:
            if segment['OptoStart'] > 0 and segment['OptoEnd'] > 0:
                return True

        return False

    