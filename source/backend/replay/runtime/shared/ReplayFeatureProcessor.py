#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from inspect import isclass
import os
import json
import string
import boto3
from botocore.client import ClientError
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
import threading
import sys
from queue import Queue
import datetime
from time import sleep
from pathlib import Path
from aws_lambda_powertools import Logger
logger = Logger()


# This is the number of Segment Cache Files which will be scanned to find Features in
# for CatchUp replays. This is required to avoid finding in ALL past segments. We search for features in these
# X number of Latest segment cache files and get the remaining from the SegmentFeature mapping cache file which the past replay
# execution has created. This should reduce the overall latency for CatchUp replays
CATCHUP_NUMBER_OF_LATEST_SEGMENTS_TO_FIND_FEATURES_IN = int(
    os.environ['CATCHUP_NUMBER_OF_LATEST_SEGMENTS_TO_FIND_FEATURES_IN'])

# Represents the Maximum number of Concurrent Threads that will Find Features in SegmentFeature cache files.
MAX_NUMBER_OF_THREADS = int(os.environ['MAX_NUMBER_OF_THREADS'])


ENABLE_CUSTOM_METRICS = os.environ['ENABLE_CUSTOM_METRICS']
client = boto3.client('cloudwatch')


class ReplayFeatureProcessor:
    def __init__(self, features: list, is_catchup_replay: bool, segments_ignore_file_list: list, audioTrack: str, event, program, replay_id, dataplane, ignore_disliked_segments, include_liked_segments, clip_preview_feedback, replay_to_be_processed):

        self.__queue = Queue()
        self.__segment_mapping_file_names = []
        self.threads = []
        self.features = features
        self.isCatchupReplay = is_catchup_replay
        self.segments_ignore_file_list = segments_ignore_file_list
        self.audio_track = str(audioTrack)
        self.event_name = event
        self.program_name = program
        self.replay_id = replay_id
        self._dataplane = dataplane
        # This is needed to Ignore segments which have been Disliked due to wrong segmentation or non important features
        self._clip_preview_feedback = clip_preview_feedback
        self._ignore_disliked_segments = ignore_disliked_segments
        self._include_liked_segments = include_liked_segments
        self._replay_to_be_processed = replay_to_be_processed
            
    

    def __sort_cache_files(self, cache_files, asc=True):
        cache_dicts = []
        for ca in cache_files:
            cache_dict = {}
            start_time = float(ca.split('_')[1])
            cache_dict['StartTime'] = start_time
            cache_dict['FileName'] = ca
            cache_dicts.append(cache_dict)

        if asc:
            sorted_files = sorted(cache_dicts, key=lambda x: x['StartTime'])
        else:

            sorted_files = sorted(
                cache_dicts, key=lambda x: x['StartTime'], reverse=True)
        return [f['FileName'] for f in sorted_files]

    def __get_segment_mapping_file_names(self):
        '''
            For CatchUp replays, Gets the Last X Cached files from /tmp/replay_id folder. Any segment cache files in the Ignore list are excluded from the 
            list of returned file names.
        '''

        logger.info('Getting a Subset of Segment Cache files ....')
        logger.info(f'Segments to be Ignored List = {self.segments_ignore_file_list}')
            

        cached_files = os.listdir(f"/tmp/{self.replay_id}")

        # For Non Catch up replay , we need to process every Cached file.
        final_cached_files = cached_files
        logger.info(
            f"After SYNC - /tmp/{self.replay_id} contents - {final_cached_files}")

        # For Catchup replays, we will pick the last 10 Cached files.
        if self.isCatchupReplay:

            '''
            reverse_cached_files = self.__sort_cache_files(final_cached_files, False)  # Sort file names in Desc order with the latest first
            logger.info(f"After SORTING /tmp/mre-cache contents in Desc Order to pick top X - {reverse_cached_files}")

            # Check if any Segments exist in the Segments Ignore list. Ignore them to ensure that the 
            # last few segments have at least one feature that the ReplayRequest is configured with.
            # Checks if a segment is in the Ignore list based on the Segment's Cache file name.
            # The Ignore list is a list of Segments which do not have a single feature
            # that the Replay is configured for.
            i = 0
            f_cached_files = []
            for final_cached_file_name in reverse_cached_files:
                if final_cached_file_name not in self.segments_ignore_file_list:
                    f_cached_files.append(final_cached_file_name)
                    i += 1

                # We need just 10 file Cache files to work with. Exit if we have met this limit.
                if i >= CATCHUP_NUMBER_OF_LATEST_SEGMENTS_TO_FIND_FEATURES_IN + 1:
                    break
            if f_cached_files:
                final_cached_files = f_cached_files
            '''

            # We need to consider all the Cache files for NonCatchup and just skip the ones which are in the Ignore list
            f_cached_files = []
            for final_cached_file_name in final_cached_files:
                if final_cached_file_name not in self.segments_ignore_file_list:
                    f_cached_files.append(final_cached_file_name)

            if f_cached_files:
                final_cached_files = f_cached_files
        else:

            # We need to consider all the Cache files for NonCatchup and just skip the ones which are in the Ignore list
            f_cached_files = []
            for final_cached_file_name in final_cached_files:
                if final_cached_file_name not in self.segments_ignore_file_list:
                    f_cached_files.append(final_cached_file_name)

            if f_cached_files:
                final_cached_files = f_cached_files

        self.__segment_mapping_file_names = final_cached_files
        logger.info(f"CatchUp - {str(self.isCatchupReplay)} Final Subset of Cache files which will be sent to the Multi-threaded process = {self.__segment_mapping_file_names}")

    def __find_features_in_segments(self, file_name):

        segment_feature_file = open(f"/tmp/{self.replay_id}/{file_name}")
        segment_mapping_as_json = json.load(segment_feature_file)

        segmentinfo = {}
        segmentinfo['Start'] = segment_mapping_as_json['Start']

        if 'OptoStart' in segment_mapping_as_json:
            segmentinfo['OptoStart'] = segment_mapping_as_json['OptoStart']

        segmentinfo['End'] = segment_mapping_as_json['End']

        if 'OptoEnd' in segment_mapping_as_json:
            segmentinfo['OptoEnd'] = segment_mapping_as_json['OptoEnd']

        segmentinfo['Features'] = []

        # We need to check for features that are present in sections that are AudioTrack depended (ex. DetectVoice)
        # as well as section that are Video specific (ex. DetectSoccerScene)
        # "0" will have Video based featurers data points
        # "1 ... N" will have Audio based featurers data points
        '''
            This is the Cache file content structure - Segment to Feature Mapping
            {
                "OptoStart": {},
                "End": 172.371,
                "OptoEnd": {},
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

        # Check if the ReplayRequest features are in any of the segments from the Cache and Map it out
        self.__map_segment_with_features(segmentinfo, segment_mapping_as_json)

        # Only if we have some features found, push it to the Queue
        if len(segmentinfo['Features']) > 0:
            self.__queue.put(segmentinfo)

    def __match_feature(self, feature, feature_data_point, segmentinfo):
        # Make sure that The Feature is Available in Cache and that the Weight is more than ZERO
        if 'Weight' in feature: #For ClipBased settings i n Replay, no weight attribute exists
            if feature['AttribName'] in feature_data_point and feature['Weight'] > 0:
                # Check if we have a Feature value which is Bool. feature['Name'] is as shown below
                # Ex. SegmentBySceneAndSR | score_change | true
                # Ex. DetectSentiment | Sentiment | false
                feature_condition = feature['Name'].split("|")[-1]
                if feature_data_point[feature['AttribName']] == True if feature_condition.lower().strip() == "true" else False:
                    segmentinfo['Features'].append(feature)
                    return True
        else:
            # Make sure that The Feature is Available in Cache
            if feature['AttribName'] in feature_data_point and feature['Include']:
                # Check if we have a Feature value which is Bool. feature['Name'] is as shown below
                # Ex. SegmentBySceneAndSR | score_change | true
                # Ex. DetectSentiment | Sentiment | false
                feature_condition = feature['Name'].split("|")[-1]
                if feature_data_point[feature['AttribName']] == True if feature_condition.lower().strip() == "true" else False:
                    segmentinfo['Features'].append(feature)
                    return True
        return False

    def should_segment_be_force_included(self, segment_start_time, segment):
        '''
            Checks if a Segment has been given a thumbs up and if the Replay Configured wants to Include such Segments
            If an Optimizer exists, we simply check for 
        '''

        does_replay_force_segments_inclusion = False if 'IncludeLikedSegments' not in self._replay_to_be_processed else self._replay_to_be_processed['IncludeLikedSegments']
        if does_replay_force_segments_inclusion:
            for clip_feedback in self._clip_preview_feedback:
                if 'Start' in clip_feedback:
                    if float(str(segment_start_time)) == float(str(clip_feedback['Start'])):
                        if 'OptoStart' in segment and 'OptoEnd' in segment:
                            if 'OptimizedFeedback' in clip_feedback:
                                if 'Feedback' in clip_feedback['OptimizedFeedback']:
                                    return True if clip_feedback['OptimizedFeedback']['Feedback'].lower() == "like" else False
                            return False        
                        elif 'OriginalFeedback' in clip_feedback:
                            if 'Feedback' in clip_feedback['OriginalFeedback']:
                                return True if clip_feedback['OriginalFeedback']['Feedback'].lower() == "like" else False
                            return False
        return False

    def __map_segment_with_features(self, segmentinfo, segment_mapping_as_json):
        '''
            Maps out the Features present in a given Segment Cache file with the Features in Replay Request
            If a Segment has been marked for force Inclusion, we dont check if the Segment Cache File 
            has any feature configured in the Replay Request. We simply map the entire Features present in 
            the Cache file
        '''

        unique_features = []

        # Only if the Current Segment (cache file) is not to be force Included, we find the matching features
        if not self.should_segment_be_force_included(segment_mapping_as_json['Start'], segment_mapping_as_json):

            # Check if the ReplayRequest features are in any of the segments from the Cache and Map it out
            for feature in self.features:  # This is the list of Features from ReplayRequest
                if 'FeaturesDataPoints' in segment_mapping_as_json:
                    if '0' in segment_mapping_as_json['FeaturesDataPoints']:
                        # Check Video based Feature data
                        for feature_data_point in segment_mapping_as_json['FeaturesDataPoints']["0"]:
                            if feature['AttribName'] not in unique_features:
                                if self.__match_feature(feature, feature_data_point, segmentinfo):
                                    unique_features.append(feature['AttribName'])

                    # Check Audio based Feature data based on the current Audio Track
                    if str(self.audio_track) in segment_mapping_as_json['FeaturesDataPoints']:
                        for feature_data_point in segment_mapping_as_json['FeaturesDataPoints'][str(self.audio_track)]:
                            if feature['AttribName'] not in unique_features:
                                if self.__match_feature(feature, feature_data_point, segmentinfo):
                                    unique_features.append(feature['AttribName'])
        else:
            # Since this Segment is to be Force Included we dont care about the features in it
            # We also add a Flag to Indicate that this Segment was Force Included
            # We add an Item into the Features list to help debug
            segmentinfo['Features'].append({
                "Reason": "Segment manually included"
            })
            segmentinfo['ForceIncluded'] = True
            logger.info(f"CLIP FORCE INCLUDED - Considering segment for replay with StartTime {segment_mapping_as_json['Start']}")

    def __configure_threads(self, cached_file_names):
        for file_name in cached_file_names:
            self.threads.append(threading.Thread(target=self.__find_features_in_segments, args=(file_name,)))
                

    def __start_threads(self):
        for thread in self.threads:
            thread.start()

    def __join_threads(self):
        for thread in self.threads:
            thread.join()

    def is_segment_disliked(self, segment_start_time, segment):
        for clip_feedback in self._clip_preview_feedback:
            if float(str(segment_start_time)) == float(str(clip_feedback['Start'])):
                # If we are dealing with Optimized Segments, just check the Optimized Feedback
                if 'OptoStart' in segment and 'OptoEnd' in segment:
                    if 'OptimizedFeedback' in clip_feedback:
                        if 'Feedback' in clip_feedback['OptimizedFeedback']:
                            if clip_feedback['OptimizedFeedback']['Feedback'].lower() == "dislike":
                                return True
                else:
                    if 'OriginalFeedback' in clip_feedback:
                        if 'Feedback' in clip_feedback['OriginalFeedback']:
                            if clip_feedback['OriginalFeedback']['Feedback'].lower() == "dislike":
                                return True
        return False

    def find_features_in_cached_files(self):
        segments_with_features = []

        self.__get_segment_mapping_file_names()

        # We will process 10 Cached Objects in parallel using Equivalent # of threads
        if not self.isCatchupReplay:

            # Create Groups of 10 Cached Object file names. We could have hundreds of Cache objects
            cached_file_groups = [self.__segment_mapping_file_names[i:i + MAX_NUMBER_OF_THREADS]
                                  for i in range(0, len(self.__segment_mapping_file_names), MAX_NUMBER_OF_THREADS)]
            logger.info(f"Cache File Groups for Non Catchup = {cached_file_groups}")
            logger.info(f"Cache File Groups Length for Non Catchup = {len(cached_file_groups)}")

            start_time = datetime.datetime.now()
            # Process each group with multiple threads and add the result of every thread into a global list
            for segment_mapping_file_names in cached_file_groups:
                self.__configure_threads(segment_mapping_file_names)
                self.__start_threads()
                self.__join_threads()

                while not self.__queue.empty():
                    segment_in_queue = self.__queue.get()
                    # First Check if this Replay needs to Ignore any Disliked Segments
                    if self._ignore_disliked_segments:
                        # Check if this Segment has been Disliked or marked for not to be Added to the Replay Clip
                        if not self.is_segment_disliked(segment_in_queue['Start'], segment_in_queue):
                            segments_with_features.append(segment_in_queue)
                        else:
                            logger.info(f"CLIP DISLIKED - Ignoring segment with StartTime {segment_in_queue['Start']}")
                    else:
                        segments_with_features.append(segment_in_queue)

                # Reset the thread list for the next group of Cache file processing
                self.threads = []

            end_time = datetime.datetime.now()
            find_features_time_in_secs = (
                end_time - start_time).total_seconds()
            logger.info(
                f'ReplayFeatureProcessor-NonCatchup Replay-Find Features Duration: {find_features_time_in_secs} seconds')
            self.__put_metric("NoCatchUpFindFeaturesTime", find_features_time_in_secs, [{'Name': 'Function', 'Value': 'MREReplayFeatureProcessor'}, {
                              'Name': 'EventProgramReplayId', 'Value': f"{self.event_name}#{self.program_name}#{self.replay_id}"}])

        else:

            start_time = datetime.datetime.now()

            # We will process only a handful (10) of cached objects for Catch Up replays
            self.__configure_threads(self.__segment_mapping_file_names)
            self.__start_threads()
            self.__join_threads()

            while not self.__queue.empty():
                segment_in_queue = self.__queue.get()

                # First Check if this Replay needs to Ignore any Disliked Segments
                if self._ignore_disliked_segments:
                    # Check if this Segment has been Disliked or marked for not to be Added to the Replay Clip
                    if not self.is_segment_disliked(segment_in_queue['Start'], segment_in_queue):
                        segments_with_features.append(segment_in_queue)
                    else:
                        logger.info(f"CLIP DISLIKED - Ignoring segment with StartTime {segment_in_queue['Start']}")
                else:
                    segments_with_features.append(segment_in_queue)

            end_time = datetime.datetime.now()
            find_features_time_in_secs = (end_time - start_time).total_seconds()
                
            logger.info(f'ReplayFeatureProcessor-Catchup Replay-Find Features Duration: {find_features_time_in_secs} seconds')
                
            self.__put_metric("CatchUpFindFeaturesTime", find_features_time_in_secs, [{'Name': 'Function', 'Value': 'MREReplayFeatureProcessor'}, {
                              'Name': 'EventProgramReplayId', 'Value': f"{self.event_name}#{self.program_name}#{self.replay_id}"}])

        # Sort Segments in Asc order based on Start time
        #segments_with_features.sort(key=lambda x: x.Start)

        return segments_with_features

    def __put_metric(self, metric_name, metric_value, dimensions: list):

        if ENABLE_CUSTOM_METRICS.lower() in ['yes', 'y']:
            client.put_metric_data(
                Namespace='MRE',
                MetricData=[
                    {
                        'MetricName': metric_name,
                        'Dimensions': dimensions,
                        'Value': metric_value * 1000,
                        'Unit': 'Milliseconds'
                    },
                ]
            )
