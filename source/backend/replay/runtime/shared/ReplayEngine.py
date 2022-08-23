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

OUTPUT_BUCKET = os.environ['OutputBucket']
EB_EVENT_BUS_NAME = os.environ['EB_EVENT_BUS_NAME']


s3_client = boto3.client("s3")


ssm = boto3.client('ssm')
TIMEGROUP_MULTIPLIER = 2

class ReplayEngine:

    def __init__(self, event):

        from MediaReplayEngineWorkflowHelper import ControlPlane
        self._controlplane = ControlPlane()

        from MediaReplayEnginePluginHelper import DataPlane
        self._dataplane = DataPlane({})


        self.__event = event

        if event['detail']['State'] == 'SEGMENT_END' or event['detail']['State'] == 'OPTIMIZED_SEGMENT_END':
            self._event = event['detail']['Segment']['Event']
        elif event['detail']['State'] == 'EVENT_END' or event['detail']['State'] == 'REPLAY_CREATED':
            self._event = event['detail']['Event']['Name']

        if event['detail']['State'] == 'SEGMENT_END' or event['detail']['State'] == 'OPTIMIZED_SEGMENT_END':
            self._program = event['detail']['Segment']['Program']
        elif event['detail']['State'] == 'EVENT_END' or event['detail']['State'] == 'REPLAY_CREATED':
            self._program = event['detail']['Event']['Program']

        if event['detail']['State'] == 'SEGMENT_END' or event['detail']['State'] == 'OPTIMIZED_SEGMENT_END':
            self._profile = event['detail']['Segment']['ProfileName']
        else:
            self._profile = self._get_profile_from_event()

        # Get Classifier from Profile
        self._classifier = self._get_profile()['Classifier']['Name']

        if event['detail']['State'] == 'OPTIMIZED_SEGMENT_END':
            self._audio_track = event['detail']['Segment']['AudioTrack']
        elif event['detail']['State'] == 'SEGMENT_END':
             self._audio_track = 1
        else:
            self._audio_track = event['detail']['Event']['AudioTrack']

        #Get Framerate from Event table
        self._frame_rate = self._get_frame_rate()

        self._segment_feature_maping = []
        

    def _create_replay(self):

        self.__mark_replay_in_progress()

        self._replay_to_be_processed = self.__event['ReplayRequest']

        # Get Segments with Features. OptoStart and OptoEndtime of Segments will be Maps by default.
        self.get_all_segments_with_features()

        # If We are dealing with Clip Based Features, we are done with Collecting the segments having Features, just push to DDB
        if not self._is_replay_duration_based():
            self._persist_replay_metadata(self._segment_feature_maping)
        else:
            print('Duration based, calculating total duration of chosen Segments')
            debuginfo = []

            replay_request_duration = self.__event['ReplayRequest']['DurationbasedSummarization']['Duration'] * 60 # In Secs

            # For Duration based, we need to check if the Sum of Segment Clip Duration is more than the Duration asked for in the 
            # Reply Request. If yes, we calculate scores and pick the best segments. If no, we simply push the segments into DDB
            duration_result, duration = self._does_total_duration_of_all_segments_exceed_configured()
            if not duration_result:
                print(f"Total duration {duration} secs of chosen Segments within Replay Request duration {replay_request_duration} secs. Not calculating Scores and weights.")

                self._persist_replay_metadata(self._segment_feature_maping, debuginfo)
                print(f"Total duration {duration} secs of chosen Segments is less than Replay Request duration {replay_request_duration} secs.")
                print(f"Total duration {duration} secs of chosen Segments is less than Replay Request duration {replay_request_duration} secs.")
            else:
                
                # If no Equal Distribution is sought, pick segments based on High Scores, duration
                if not self.__event['ReplayRequest']['DurationbasedSummarization']['EqualDistribution']:

                    print(f'Calculate Scores based on Weights .. total duration was {duration}')
                    self._calculate_segment_scores_basedon_weights(self._segment_feature_maping)

                    print("--------")
                    print(self._segment_feature_maping)

                    # After each Segment has been scored, sort them in Desc based on Score
                    sorted_segments = sorted(self._segment_feature_maping, key=lambda x: x['Score'], reverse=True)

                    print("--------AFTER SORT----------")
                    print(sorted_segments)

                    # Find which segments needs to be Removed to meet the Duration Requirements in Replay Request
                    total_duration_all = 0
                    total_duration = 0
                    final_segments = []
                    
                    # Event if the last segment time makes the overall time to beyond the Duration limit,
                    # lets add that segment. The rest of the segments will be ignored since the Duration limit
                    # will be crossed.
                    last_segment_crossed_duration_limit = False
                    for segment in sorted_segments:
                        segment_duration = self._get_segment_duration_in_secs(segment)
                        total_duration_all += segment_duration

                        if total_duration + segment_duration <= replay_request_duration:
                            final_segments.append(segment)
                            total_duration += segment_duration
                        else:
                            if not last_segment_crossed_duration_limit:
                                last_segment_crossed_duration_limit = True
                                final_segments.append(segment)
                                total_duration += segment_duration
                            else:
                                print(f"Ignoring the segment - StartTime {segment['Start']}, EndTime {segment['End']} - to avoid exceeding the replay request duration limit {replay_request_duration} secs")
                                print(f"Ignoring segment - StartTime {segment['Start']}, EndTime {segment['End']} Segment Duration {segment_duration} secs - to avoid exceeding the replay duration limit of {replay_request_duration} secs.")


                    print(f"Duration if all segments considered would be {total_duration_all} secs")

                    # Finally Sort the Segments based on the Start time in Asc Order
                    sorted_final_segments = sorted(final_segments, key=lambda x: x['Start'], reverse=False)
                    self._persist_replay_metadata(sorted_final_segments, debuginfo)

                else:

                    # Because Equal Distrbution is being asked for, 
                    # We will distribute the total segment duration into Multiple TimeGroups and Group segments within them based on Segment Start time.
                    # Within each TimeGroup, we will Score the Segments based on Weights and 
                    # pick the Highest Scoring Segment by adhering to the Duration which will be the TimeGroup Duration
                    # Each Time Group will also have an Absolute time representation. 
                    # For example, first Timegroup would be from 0 - 292 secs, 2nd from 292 to 584 secs .. the last one(t6th) from 1460 to 1752 Secs
                    # We will select segments whose StartTime falls in these Absolute time ranges to get a Equal Distribution

                    
                    first_segment = self._all_segments_with_features[0]
                    last_segment = self._all_segments_with_features[len(self._all_segments_with_features) - 1]


                    start_of_first_segment_secs = first_segment['OptoStart'][self._audio_track] if self._is_segment_optimized(first_segment) else first_segment['Start']
                    end_of_last_segment_secs = last_segment['OptoEnd'][self._audio_track] if self._is_segment_optimized(last_segment) else last_segment['End']

                    print(f"First Seg starts at {start_of_first_segment_secs} secs")
                    print(f"Last Seg Ends at {end_of_last_segment_secs} secs")

                    total_segment_duration_in_secs = end_of_last_segment_secs - start_of_first_segment_secs
                    print(f"total_segment_duration_in_secs = {total_segment_duration_in_secs} secs")

                    total_segment_duration_in_hrs = (end_of_last_segment_secs - start_of_first_segment_secs) / 3600 # Hours
                    print(f"total_segment_duration_in_hrs = {total_segment_duration_in_hrs} hrs")

                    # Find how many Time Groups we need. If we have more than 1 Hr lets divide into multiple groups.
                    if total_segment_duration_in_secs > 3600:
                        no_of_time_groups = (math.ceil(total_segment_duration_in_hrs)* 2) + TIMEGROUP_MULTIPLIER
                    else:
                        no_of_time_groups = TIMEGROUP_MULTIPLIER
                    print(f"no_of_time_groups = {no_of_time_groups}")

                    # Calculate the TimeGroup time based on the Replay Request Duration
                    timegroup_time_in_secs = replay_request_duration / no_of_time_groups
                    print(f"timegroup_time_in_secs = {timegroup_time_in_secs}")

                    # This represents the absolute time that should be added up for all TimeGroups
                    time_frame_in_time_group = round(total_segment_duration_in_secs / no_of_time_groups, 2)

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

                    print(time_groups)

                    final_segments_across_timegroups = []
                    # TimeGroups will be Asc Order by Default based on how its Constructed above
                    for timegroup in time_groups:
                        segments_within_timegroup = self._get_segments_with_features_within_timegroup(timegroup)

                        print(f'Calculate Scores based on Weights .. ')
                        self._calculate_segment_scores_basedon_weights(segments_within_timegroup)

                        # After each Segment has been scored, sort them in Desc based on Score
                        sorted_segments = sorted(segments_within_timegroup, key=lambda x: x['Score'], reverse=True)

                        # Find which segments needs to be Removed to meet the Duration Requirements in Replay Request
                        total_duration_all = 0
                        total_duration = 0
                        final_segments = []
                        
                        # Event if the last segment time makes the overall time to beyond the Duration limit,
                        # lets add that segment. The rest of the segments will be ignored since the Duration limit
                        # will be crossed.
                        last_segment_crossed_duration_limit = False
                        for segment in sorted_segments:
                            segment_duration = self._get_segment_duration_in_secs(segment)
                            total_duration_all += segment_duration

                            if total_duration + segment_duration <= timegroup_time_in_secs:
                                final_segments.append(segment)
                                total_duration += segment_duration
                            else:
                                if not last_segment_crossed_duration_limit:
                                    last_segment_crossed_duration_limit = True
                                    final_segments.append(segment)
                                    total_duration += segment_duration
                                else:
                                    print(f"Ignoring the segment - StartTime {segment['Start']}, EndTime {segment['End']} - to avoid exceeding the timegroup duration limit {timegroup_time_in_secs} secs")
                                #print(f"Ignoring the segment - StartTime {segment['Start']}, EndTime {segment['End']} Segment Duration {segment_duration} secs - to avoid exceeding the replay duration limit of {timegroup_time_in_secs} secs.")

                        #print(f"Duration if all segments within this timegroup considered would be {total_duration_all} secs")

                        # Finally Sort the Segments based on the Start time in Asc Order
                        sorted_final_segments = sorted(final_segments, key=lambda x: x['Start'], reverse=False)
                        final_segments_across_timegroups.extend(sorted_final_segments)
                    
                    # Persist all segment+features across all timegroups
                    self._persist_replay_metadata(final_segments_across_timegroups, debuginfo)


    def _get_segments_with_features_within_timegroup(self, timegroup):
        segments_within_timegroup = []
        for segment in self._segment_feature_maping:
            segment_startTime, segment_endTime = self._get_segment_start_and_end_times(segment)

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
            #multiplier = self._get_multiplier(feature['Weight'])
            #feature['MultiplierChosen'] = multiplier
            feature['MultiplierChosen'] = feature['Weight']
            total_score += feature['Weight'] #* multiplier

        return total_score
        
    
    def _get_multiplier(self, weight):
        return math.ceil(weight / 10)

    def _get_segment_start_and_end_times(self, segment):
        if self._is_segment_optimized(segment):
            startTime = Decimal(str(segment['OptoStart'][self._audio_track]))
            endTime = Decimal(str(segment['OptoEnd'][self._audio_track]))
        else:
            startTime = Decimal(str(segment['Start']))
            endTime = Decimal(str(segment['End']))
        
        return startTime, endTime

    def _get_segment_duration_in_secs(self, segment):
        startTime, endTime = self._get_segment_start_and_end_times(segment)
        return endTime - startTime
        
    def _does_total_duration_of_all_segments_exceed_configured(self):
        duration = 0
        for segment_feature in self._segment_feature_maping:
            # Total Duration of Segment in Secs
            duration += self._get_segment_duration_in_secs(segment_feature)

        return (True, duration) if duration > Decimal(str(self.__event['ReplayRequest']['DurationbasedSummarization']['Duration'])) * 60 else (False, duration)
            
        
    def _persist_replay_metadata(self, segmentInfo, additionalInfo=None):
        
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
                rep_res['OptoStart'] = segment_feature['OptoStart'][self._audio_track]
                rep_res['OptoEnd'] = segment_feature['OptoEnd'][self._audio_track]

            replay_results.append(rep_res)

        replay_result_payload = {}
        replay_result_payload['Program'] = self._program
        replay_result_payload['Event'] = self._event
        replay_result_payload['ReplayId'] = self.__event['ReplayRequest']['ReplayId']
        replay_result_payload['Profile'] = self._profile
        replay_result_payload['Classifier'] = self._classifier
        replay_result_payload['AdditionalInfo'] = additionalInfo if additionalInfo is not None else []
        replay_result_payload['ReplayResults'] = replay_results
        replay_result_payload['TotalScore'] = total_score_of_selected_segments

        self._dataplane.update_replay_result(replay_result_payload)

        
    
    @staticmethod
    def _mark_replay_complete(replayId, program, event):
        from MediaReplayEngineWorkflowHelper import ControlPlane
        controlplane = ControlPlane()
        controlplane.update_replay_request_status(program, event, replayId, "Complete")
        
    @staticmethod
    def _mark_replay_error(replayId, program, event):
        from MediaReplayEngineWorkflowHelper import ControlPlane
        controlplane = ControlPlane()
        controlplane.update_replay_request_status(program, event, replayId, "Error")

    def __mark_replay_in_progress(self):
        self._controlplane.update_replay_request_status(self._program, self._event, self.__event['ReplayRequest']['ReplayId'], "In Progress")

    
    def _get_segments_for_event(self):
        self._segments_created_so_far = self._dataplane.get_all_segments_for_event(self._program, self._event, self._classifier)

    def _get_event(self):
        return self._controlplane.get_event(self._event, self._program, )

    @staticmethod
    def get_replay(event, program, replay_request_id):
        from MediaReplayEngineWorkflowHelper import ControlPlane
        controlplane = ControlPlane()
        return controlplane.get_replay_request(event, program, replay_request_id)


    def _get_frame_rate(self):
        event = self._get_event()
        return event['FrameRate']
        # Get Segments in Ascending order based on StartTime of each Segment
        #response = event_table.query(
        #    KeyConditionExpression=Key("Name").eq(f"{self._event}") & Key('Program').eq(f"{self._program}")
        #)
        #return response['Items'][0]['FrameRate']


    def _get_profile_from_event(self):
        event = self._get_event()
        return event['Profile']
        #response = event_table.query(
        #    KeyConditionExpression=Key("Name").eq(f"{self._event}") & Key('Program').eq(f"{self._program}")
        #)
        #return response['Items'][0]['Profile']


    def _get_profile(self):
        return self._controlplane.get_profile(self._profile)

        

    def _get_featurers_by_profile(self):

        if self._profile == '':
            self._get_profile()

        # A List of Featurer names
        self._featurers = [feature_dict["Name"] for feature_dict in self._profile['Featurers']] 

    
    @staticmethod
    def _get_all_replays_for_event_end(event, program, audioTrack):
        '''
            Returns all Queued Replay Requests for the Program/Event and Audio Track
        '''
        from MediaReplayEngineWorkflowHelper import ControlPlane
        controlplane = ControlPlane()
        return controlplane.get_all_replay_requests_for_event_opto_segment_end(program, event, int(audioTrack))

    @staticmethod
    def get_all_replay_requests_for_completed_events(event, program, audioTrack):
        '''
            Returns all Queued Replay Requests for the Program/Event and Audio Track
        '''
        from MediaReplayEngineWorkflowHelper import ControlPlane
        controlplane = ControlPlane()
        return controlplane.get_all_replay_requests_for_completed_events(program, event, int(audioTrack))
    
    @staticmethod
    def _get_all_replays_for_segment_end(event, program):
        '''
            Returns all Queued Replay Requests for the Program/Event
        '''
        from MediaReplayEngineWorkflowHelper import ControlPlane
        controlplane = ControlPlane()
        return controlplane.get_all_replays_for_segment_end(event, program)

        
    def _get_all_replays_for_opto_segment_end(self):
        '''
            Returns all Queued Replay Requests for the Program/Event and Audio Track
        '''
        return self._controlplane.get_all_replay_requests_for_event_opto_segment_end(self._program, self._event, int(self._audio_track))

    def _is_catch_up_enabled(self):
        '''
            Checks if a Replay Request is for Catch Up or not.
        '''
        if 'Catchup' in self._replay_to_be_processed:
            if replay['Catchup']:
                return True

        return False

    def _is_replay_duration_based(self):
        '''
            Checks if the replay is Duration based or Clip based.
        '''
        return False if self._replay_to_be_processed['ClipfeaturebasedSummarization'] else True
            

        

    def _is_hls_enabled(self):
        if 'CreateHls' in self._replay_to_be_processed: # Replay has HLS Enabled
            return True
        return False
    
    def _is_media_channel_enabled(self):
        if 'MediaTailorChannel' in self._replay_to_be_processed:
            return True
        return False

    def _is_segment_optimized(self, segment):
        if 'OptoStart' in segment and 'OptoEnd' in segment:
            if len(segment['OptoStart']) > 0 and len(segment['OptoEnd']) > 0:
                return True

        return False
        
    def _is_features_found_in_segment(self,segment, feature):
        
        startTime = ''
        endTime = ''

        # Use the Segment Start time to find if a Feature exists in it or not. We dont care of the segment is optimized or not 
        # as we care about a feature found in the segment
        startTime = Decimal(str(segment['Start']))
        endTime = Decimal(str(segment['End']))

        # If StartTime and EndTime of a Segment is the same, dont bother
        if startTime == endTime:
            return False

        return self._dataplane._is_features_found_in_segment(self._program, self._event, startTime, feature['PluginName'], feature['AttribName'], feature['AttribValue'], endTime)

    def _record_segment_and_feature(self, segment, features):
        '''
            Creates a Flattened Dict having Segment and the matching Features Info
        '''
        
        feature = {
                    "AudioTrack": int(self._audio_track),
                    "Start": segment['Start'],
                    "End": segment['End'],
                    "Features": features
                }

        # Assign the Map from the Original Segment
        if self._is_segment_optimized(segment):
            feature['OptoStart'] = segment['OptoStart']
            feature['OptoEnd'] = segment['OptoEnd']

        self._segment_feature_maping.append(feature)

    def _get_segment_with_features(self, segment):
        features_in_segment = []
        
        for feature in self._replay_to_be_processed['Priorities']['Clips']:
            # If Clip based, select the segments which have at least one Feature selected in the Replay Request
            if not self._is_replay_duration_based():
                if feature['Include']:
                    print('CLip feature based Included feature')
                    print(segment)
                    print(feature)
                    res = self._is_features_found_in_segment(segment, feature)
                    print('=================_is_features_found_in_segment')
                    print(res)
                    if res:
                        features_in_segment.append(feature)
            else:
                if self._is_features_found_in_segment(segment, feature):
                        print('=================_is_features_found_in_segment')
                        print(feature)
                        features_in_segment.append(feature)

        # Only if we have features, map the segment with the features found
        if len(features_in_segment) > 0:
            print('recording segment and feature')
            self._record_segment_and_feature(segment, features_in_segment)
    
        if len(features_in_segment) > 0:
            return segment
        else:
            return None


    def get_all_segments_with_features(self):

        '''
            Builds a list of feature based time points for every segment within which they fall in
        '''

        # First get all segments created so far (Partial for CatchUp or All when event is complete)
        self._get_segments_for_event()
        print('segments for this event')
        print(self._segments_created_so_far)

        all_segments_with_features = []
        for segment in self._segments_created_so_far:
            seg = self._get_segment_with_features(segment)
            print('this segment has the feature')
            print(seg)

            if seg is not None:
                all_segments_with_features.append(segment)

        print('Final list of Segment and Features that were present in them ...')
        print(self._segment_feature_maping)

        self._all_segments_with_features = all_segments_with_features
        return all_segments_with_features
    
    
    
    

    # def _create_clip_feature_based_replay(self):

    #     from MediaReplayEnginePluginHelper import DataPlane
    #     mre_pluginhelper = DataPlane({})

    #     try:
        
    #         job_settings_filename = os.path.join(os.path.dirname(__file__), 'job_settings_mp4.json')
                    
    #         with open(job_settings_filename) as json_data:
    #             jobSettings = json.load(json_data)
            
    #         i = 0
    #         for segment in self._all_segments_with_features:
                
    #             if i > 0:
    #                 jobSettings['Inputs'].append(copy.deepcopy(jobSettings['Inputs'][0]))

                

    #             jobSettings['Inputs'][i]['FileInput'] = segment['OptimizedClipLocation'][self._audio_track] if 'OptimizedClipLocation' in segment else segment['OriginalClipLocation'][self._audio_track]
    #             jobSettings['Inputs'][i]['InputClippings'][0]['StartTimecode'] = mre_pluginhelper.get_mediaconvert_clip_format(
    #                                                                                     self._get_segment_start_time(segment),
    #                                                                                     self._program,
    #                                                                                     self._event,
    #                                                                                     self._profile,
    #                                                                                     self._frame_rate)
    #             #If we have a single Chunk we don't need the Endtime Configured. Remove it.
    #             jobSettings['Inputs'][0]['InputClippings'][0].pop('EndTimecode', None)
                
    #             #------------- Update MediaConvert AudioSelectors Input -------------

    #             jobSettings['Inputs'][i]['AudioSelectors'] = {
    #                                                             "Audio Selector 1": {
    #                                                                 "Tracks": [
    #                                                                     1   # Should be always one because the Opto Clip generated during seg would have a single AudioTrack?
    #                                                                 ],
    #                                                                 "DefaultSelection": "NOT_DEFAULT",
    #                                                                 "SelectorType": "TRACK"
    #                                                             }
    #                                                         }

    #             jobSettings['Inputs'][i]['AudioSelectorGroups'] =   {
    #                                                                     "Audio Selector Group 1": {
    #                                                                         "AudioSelectorNames": [
    #                                                                         "Audio Selector 1"
    #                                                                         ]
    #                                                                     }
    #                                                                 }
    #             #------------- Update MediaConvert AudioSelectors Input Ends ------------- 
    #             i += 1

    #         # Overrides to Job settings
    #         runid = str(uuid.uuid4())
    #         keyprefix = f"replay_assets/{runid}/MP4/{str(self._audio_track)}/{str(runid)}"

    #         job_output_destination = f"s3://{OUTPUT_BUCKET}/{keyprefix}"
            
    #         jobSettings["OutputGroups"][0]["OutputGroupSettings"]["FileGroupSettings"]["Destination"] = job_output_destination

    #         thumbnail_keyprefix = f"thumbnail/{runid}/{str(runid)}"
    #         thumbnail_job_output_destination = f"s3://{OUTPUT_BUCKET}/{thumbnail_keyprefix}"
    #         jobSettings["OutputGroups"][1]["OutputGroupSettings"]["FileGroupSettings"]["Destination"] = thumbnail_job_output_destination


    #         # get the account-specific mediaconvert endpoint for this region
    #         endpoint = ssm.get_parameter(Name='/MRE/ClipGen/MediaConvertEndpoint', WithDecryption=False)['Parameter']['Value'] 

    #         # add the account-specific endpoint to the client session 
    #         client = boto3.client('mediaconvert', endpoint_url=endpoint, verify=False)

    #         mediaConvertRole = os.environ['MediaConvertRole']

    #         # Convert the video using AWS Elemental MediaConvert
    #         jobid = str(uuid.uuid4())
    #         jobMetadata = { 'JobId': jobid }

    #         print('---------JOB SETTINGS -----------------------------')
    #         print(jobSettings)

    #         client.create_job(Role=mediaConvertRole, UserMetadata=jobMetadata, Settings=jobSettings)

    #         return {
    #             "ReplayClipLocation": f"{job_output_destination}.mp4",
    #             "ReplayThumbnailLocation": f"{thumbnail_job_output_destination}.0000000.jpg"
    #         }        
    #     except Exception as e:
    #         print(e)
    #         raise e
