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
from botocore.config import Config
from MediaReplayEngineWorkflowHelper import ControlPlane
from MediaReplayEnginePluginHelper import DataPlane
from shared.Mp4JobInitializer import Mp4JobInitializer
from timecode import Timecode
import copy
from queue import Queue
import threading
from collections import namedtuple

from aws_lambda_powertools import Logger
logger = Logger()

OutputResTuple = namedtuple(
                                "OutputResTuple",
                                ['ResWidth', 'ResHeight', 'QVBR', 'MaxBitRate']                
                            )



MAX_INPUTS_PER_JOB = int(os.environ['MediaConvertMaxInputJobs'])
ACCELERATION_MEDIA_CONVERT_QUEUE = os.environ['MediaConvertAcceleratorQueueArn']
OUTPUT_BUCKET = os.environ['OutputBucket']
ENABLE_CUSTOM_METRICS = os.environ['ENABLE_CUSTOM_METRICS']
MEDIA_CONVERT_ENDPOINT = os.environ['MEDIA_CONVERT_ENDPOINT']

ssm = boto3.client('ssm')
cw_client = boto3.client('cloudwatch')


class Mp4Generator:

    def __init__(self, event):

        self._controlPlane = ControlPlane()
        tmpEvent = self.__get_dataplane_payload(event)
        self.__eventName = tmpEvent['Event']['Name']
        self.__program = tmpEvent['Event']['Program']
        self.__profile = tmpEvent['Profile']['Name']
        self.__framerate = tmpEvent['Profile']['ProcessingFrameRate']
        self.__video_framerate = float(tmpEvent['Event']['FrameRate'])
        self._dataplane = DataPlane(tmpEvent)
        self.__event = event
        self.__queue = Queue()

    def __get_dataplane_payload(self, event):

        program = event['ReplayRequest']['Program']
        event = event['ReplayRequest']['Event']

        event_details = self._controlPlane.get_event(event, program)
        profile_name = event_details['Profile']

        profile_detail = self._controlPlane.get_profile(profile_name)

        final_event = {
            "Event": {
                "Program": program,
                "Name": event,
                "FrameRate": event_details['FrameRate']
            },
            "Profile": {
                "Name": profile_name,
                "ChunkSize": profile_detail['ChunkSize'],
                "ProcessingFrameRate": profile_detail['ProcessingFrameRate'],
                "Classifier": profile_detail['Classifier']['Name'],
                "MaxSegmentLengthSeconds": profile_detail['MaxSegmentLengthSeconds']
            }
        }

        return final_event

    def __get_event_details(self, event_name, program_name):
        event_details = self._controlPlane.get_event(event_name, program_name)
        self.__queue.put({
            "EventDetails": event_details
        })

    def __get_all_segments_for_replay(self, program_name, event_name, replay_id):
        replay_segments = self._dataplane.get_all_segments_for_replay(
            program_name, event_name, replay_id)
        self.__queue.put({
            "ReplaySegments": replay_segments
        })

    def is_transition_video_based(self):
        if self.transition_config:
            if 'MediaType' in self.transition_config:
                if self.transition_config['MediaType'].lower() == 'video':
                    return True
        return False

    def is_transition_image_based(self):
        if self.transition_config:
            if 'MediaType' in self.transition_config:
                if self.transition_config['MediaType'].lower() == 'image':
                    return True
        return False

    def get_overlay_start_timecode_for_last_chunk_in_segment(self, end_time_code, fade_in_duration):
        # We need to walk back X frames from the EndTimecode of this Last Chunk
        # To find the No. of Frames to go back, we use the formula
        # frames = ( __video_framerate / 1000 ) * fade_in_duration (ms)
        no_of_frames =  math.ceil((self.__video_framerate / 1000) * fade_in_duration)
        try:
            tc = Timecode(self.__video_framerate, end_time_code)
            tc.sub_frames(no_of_frames)
            logger.info(f"{self.__video_framerate} fps, Endtime = {end_time_code} -> OverlayStartTime = {tc}")
        except ValueError as e:
            # Timecode.frames should be a positive integer bigger than zero, not -17
            return "00:00:00:00"
        return str(tc)


    def insert_transition_overlay_fade_in_fade_out_setting(self, input_job_settings) -> None:
        mutated_input_job_settings = []

        ImageInserter = {
          "InsertableImages": [
            {
              "ImageX": 0,
              "ImageY": 0,
              "Duration": 0,
              "Layer": 1,
              "ImageInserterInput": self.transition_config['ImageLocation'],
              "StartTime": "",
              "Opacity": 100
            }
          ]
        }
        logger.info('in insert_transition_overlay_fade_in_fade_out_setting')
        i = 1
        for input_job_setting in input_job_settings:
            if 'InputClippings' in input_job_setting:
                if input_job_setting['InputClippings']:
                    # CHUNKS in between will not have any Input Clippings
                    # Make sure we have at least 1 Input Clipping. Which can be EndTimeCode or StartTimeCode
                    # For Settings which do not have InputClipping, just add them into the List
                    if len(input_job_setting['InputClippings']) > 0:

                        '''
                        We have to Create Overlays based on the Start and EndTimeCode for each segment

                        |    Segment 1                   |       Segment 2                  |
                        |   Chunk1  | Chunk 2 | Chunk 3  |   Chunk1  | Chunk 2 | Chunk 3    |    
                        | START_TIME|         | END TIME | START_TIME|         | END TIME   | 
                        '''

                        if 'StartTimecode' in input_job_setting['InputClippings'][0] and 'EndTimecode' not in input_job_setting['InputClippings'][0]:
                            # DO NOT Modify the First Chunk of the Replay
                            # For the rest, we will set an Overlay at the beginning of the Chunk
                            if i == 1:
                                mutated_input_job_settings.append(input_job_setting)
                            else: 
                                # We need to Overlay at the Beginning of the Chunk TimeCode. Lets go back by 1 frame and add transition
                                # If "00:00:05:08" is the StartTimeCode, we change it to "00:00:05:07"
                                start_time_code = input_job_setting['InputClippings'][0]['StartTimecode']
                                try:
                                    tc = Timecode(self.__video_framerate, start_time_code)
                                    tc.sub_frames(1)
                                    final_start_time_code = str(tc)
                                except ValueError as e:
                                    # Timecode.frames should be a positive integer bigger than zero, not -17
                                    # This happens when StartTimeCode is already at 00:00:00:00
                                    final_start_time_code = "00:00:00:00"
                                
                                image_inserter = copy.deepcopy(ImageInserter)
                                # Override Duration, StartTime, FadeOut
                                image_inserter['InsertableImages'][0]['Duration'] = self.replay_request['TransitionOverride']['FadeOutMs']
                                image_inserter['InsertableImages'][0]['FadeOut'] = self.replay_request['TransitionOverride']['FadeOutMs']
                                image_inserter['InsertableImages'][0]['StartTime'] = final_start_time_code
                                input_job_setting['ImageInserter'] = image_inserter
                                mutated_input_job_settings.append(input_job_setting)
                        
                        if 'EndTimecode' in input_job_setting['InputClippings'][0] and 'StartTimecode' not in input_job_setting['InputClippings'][0]:
                            # Make sure not to add a Transition at the end of the Last Chunk of the Last segment
                            if i != len(input_job_settings):
                                overlay_start_time_code = self.get_overlay_start_timecode_for_last_chunk_in_segment(
                                                        input_job_setting['InputClippings'][0]['EndTimecode'], self.replay_request['TransitionOverride']['FadeInMs'])

                                image_inserter = copy.deepcopy(ImageInserter)
                                # Override Duration, StartTime, FadeIn
                                image_inserter['InsertableImages'][0]['Duration'] = self.replay_request['TransitionOverride']['FadeInMs']
                                image_inserter['InsertableImages'][0]['FadeIn'] = self.replay_request['TransitionOverride']['FadeInMs']
                                image_inserter['InsertableImages'][0]['StartTime'] = overlay_start_time_code
                                input_job_setting['ImageInserter'] = image_inserter 
                            
                            # Make sure to add the Job setting here. Otherwise this causes Clips to be Truncated
                            mutated_input_job_settings.append(input_job_setting)

                        '''
                            Here we create Overlays based on the Start and EndTimeCode for a segment which has only one Chunk

                            |    Segment 1                   |       Segment 2                  |
                            |             Chunk 1            |              Chunk 1             |    
                            | START_TIME|         | END TIME | START_TIME|         | END TIME   | 
                        '''

                        if 'StartTimecode' in input_job_setting['InputClippings'][0] and 'EndTimecode' in input_job_setting['InputClippings'][0]:
                            # This segment has only one chunk and so Add an overlay at the end
                            if i == 1:

                                overlay_start_time_code = self.get_overlay_start_timecode_for_last_chunk_in_segment(
                                                        input_job_setting['InputClippings'][0]['EndTimecode'], self.replay_request['TransitionOverride']['FadeInMs'])

                                image_inserter = copy.deepcopy(ImageInserter)
                                # Override Duration, StartTime, FadeIn
                                image_inserter['InsertableImages'][0]['Duration'] = self.replay_request['TransitionOverride']['FadeInMs']
                                image_inserter['InsertableImages'][0]['FadeIn'] = self.replay_request['TransitionOverride']['FadeInMs']
                                image_inserter['InsertableImages'][0]['StartTime'] = overlay_start_time_code
                                input_job_setting['ImageInserter'] = image_inserter 
                                mutated_input_job_settings.append(input_job_setting)
                            else: 

                                # Handle StartTimeCode here

                                # We need to Overlay at the Beginning of the Chunk TimeCode. Lets go back by 1 frame and add transition
                                # If "00:00:05:08" is the StartTimeCode, we change it to "00:00:05:07"
                                start_time_code = input_job_setting['InputClippings'][0]['StartTimecode']
                                try:
                                    tc = Timecode(self.__video_framerate, start_time_code)
                                    tc.sub_frames(1)
                                    final_start_time_code = str(tc)
                                except ValueError as e:
                                    # Timecode.frames should be a positive integer bigger than zero, not -17
                                    # This happens when StartTimeCode is already at 00:00:00:00
                                    final_start_time_code = "00:00:00:00"
                                
                                image_inserter_for_start_time = {
                                                                "ImageX": 0,
                                                                "ImageY": 0,
                                                                "Duration": self.replay_request['TransitionOverride']['FadeOutMs'],
                                                                "Layer": 1,
                                                                "ImageInserterInput": self.transition_config['ImageLocation'],
                                                                "StartTime": final_start_time_code,
                                                                "Opacity": 100,
                                                                "FadeOut": self.replay_request['TransitionOverride']['FadeOutMs']
                                                                }
                                
                                # Handle EndTimeCode here
                                # If this is the Last Segment and the Last Chunk do not add a Overlay at the end
                                if i != len(input_job_settings):
                                    overlay_start_time_code = self.get_overlay_start_timecode_for_last_chunk_in_segment(input_job_setting['InputClippings'][0]['EndTimecode'], self.replay_request['TransitionOverride']['FadeInMs'])
                                                            
                                    
                                    image_inserter_for_end_time = {
                                                                "ImageX": 0,
                                                                "ImageY": 0,
                                                                "Duration": self.replay_request['TransitionOverride']['FadeInMs'],
                                                                "Layer": 1,
                                                                "ImageInserterInput": self.transition_config['ImageLocation'],
                                                                "StartTime": overlay_start_time_code,
                                                                "Opacity": 100,
                                                                "FadeIn": self.replay_request['TransitionOverride']['FadeInMs']
                                                                }


                                    # Override Duration, StartTime, FadeOut
                                    input_job_setting['ImageInserter'] = {
                                                                "InsertableImages": [
                                                                        image_inserter_for_start_time,
                                                                        image_inserter_for_end_time
                                                                    ]
                                                                }
                                    logger.info(f"Segment with a single chunk. Updated ImageInserter")

                                mutated_input_job_settings.append(input_job_setting)

                if len(input_job_setting['InputClippings']) == 0:
                    mutated_input_job_settings.append(input_job_setting)

            i+=1            

        return mutated_input_job_settings

    def insert_transition_clip_between_segments(self, input_job_settings) -> None:
        mutated_input_job_settings = []

        logger.info('in insert_transition_clip_between_segments')
        # Check if the Replay Request has been Configured to use a Video Transition
        if 'TransitionClipLocation' in self.transition_config:
            video_transition_clip_setting = {
                "InputClippings": [],
                "VideoSelector": {},
                "TimecodeSource": "ZEROBASED",
                "FileInput": self.transition_config['TransitionClipLocation']
            }
            i = 1
            for input_job_setting in input_job_settings:
                mutated_input_job_settings.append(
                    input_job_setting)
                # Dont add the Transition after the last Segment's Input Setting.
                if i < len(input_job_settings):
                    i += 1

                    # We should add the Transition Clip setting only if the
                    # current Input setting has a EndTimecode set (Last part of the segment)
                    # Segment 1 (StartTimeCode) - Segment 2 - Segment 3 (EndTimecode) ->>>> TransitionClip <<<< Segment 1 (StartTimeCode) - Segment (EndTimecode)
                    if 'InputClippings' in input_job_setting:
                        if input_job_setting['InputClippings']:
                            # CHUNKS in between will not have any Input Clippings
                            # Make sure we have at least 1 Input Clipping. Which can be EndTimeCode or StartTimeCode
                            # Since we want to identify the end Chunk, we check for EndTimeCode 
                            if len(input_job_setting['InputClippings']) > 0:
                                if 'EndTimecode' in input_job_setting['InputClippings'][0]:
                                    mutated_input_job_settings.append(
                                        video_transition_clip_setting)

        return mutated_input_job_settings

    def generate_mp4(self):
        replay_id = self.__event['ReplayRequest']['ReplayId']
        audio_track = self.__event['ReplayRequest']['AudioTrack']

        logger.append_keys(replay_id=str(self.__event['ReplayRequest']['ReplayId']))

        # We need this to get the Transition Name - The ReplayRequest and Transitions table have a one to One relationship
        # Transitions Configuration is not repeated in ReplayRequest
        self.replay_request = self._controlPlane.get_replay_request(self.__eventName, self.__program, replay_id)
            
        # This the call to get Transition Configuration
        self.transition_config = None
        if 'TransitionName' in self.replay_request:
            # By default Transition Configuration is set to None during Replay creation.
            # We load the config only if a user choose a Transition
            if self.replay_request['TransitionName'].lower() != 'none':
                self.transition_config = self._controlPlane.get_transitions_config(self.replay_request['TransitionName'])


        
        t1 = threading.Thread(target=self.__get_event_details, args=(
            self.__eventName, self.__program,))
        t2 = threading.Thread(target=self.__get_all_segments_for_replay, args=(
            self.__program, self.__eventName, replay_id,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        event_details = None
        replay_segments = []

        while not self.__queue.empty():
            queue_item = self.__queue.get()
            if 'EventDetails' in queue_item:
                event_details = queue_item['EventDetails']
            if 'ReplaySegments' in queue_item:
                replay_segments = queue_item['ReplaySegments']

        profile_name = event_details['Profile']
        output_resolutions = self.__event['ReplayRequest']['Resolutions']

        logger.info(f"Replay Segments picked to Create MP4 Job Inputs --{replay_segments}")
        batch_id = f"{str(uuid.uuid4())}"

        # This is a Multi Threaded Process which builds MP4 Input settings for every Segment
        input_job_settings = []
        mp4_job_obj = Mp4JobInitializer(replay_segments,
                                        self._dataplane,
                                        self.__eventName,
                                        self.__program,
                                        profile_name,
                                        audio_track,
                                        self.__framerate,
                                        replay_id)
        input_job_settings = mp4_job_obj.create_input_settings_for_segments()

        logger.info(f'---------------- MP4 BEFORE Mutation input_job_settings = {json.dumps(input_job_settings)}')


        # Should the Final Clip have Transitions ?
        # If the Transition type is a Video with No Overlays, we need to append an Input Setting between every Segment's Input Setting
        # If the Transition type is an Image, its an Overlay and will be handled within another method
        if self.transition_config:
            if self.is_transition_video_based():
                new_input_job_settings = self.insert_transition_clip_between_segments(input_job_settings)
            elif self.is_transition_image_based():
                new_input_job_settings = self.insert_transition_overlay_fade_in_fade_out_setting(input_job_settings)
                
            if new_input_job_settings:
                input_job_settings = new_input_job_settings

        logger.info(f'---------------- MP4 AFTER Mutation input_job_settings = {json.dumps(input_job_settings)}')

        job_metadata = []
        resolution_thumbnail_mapping = []
        # For each Resolution in the Replay Request, create Media Convert Jobs
        # by configuring the Output Resolution and Input Clip settings using Replay Segment Information
        for resolution in output_resolutions:

            # Contains Job IDs for all the MP4 Jobs. We will need to
            # check if all Jobs have completed before updating the Replay request with the S3 location
            all_mp4_clip_job_metadata = []

            groups_of_input_settings = [input_job_settings[x:x+MAX_INPUTS_PER_JOB]
                                        for x in range(0, len(input_job_settings), MAX_INPUTS_PER_JOB)]
            index = 1
            res = resolution.split(' ')[0]

            logger.info('---------------- groups_of_input_settings -----------------------')
            logger.info(groups_of_input_settings)

            for inputsettings in groups_of_input_settings:
                # Each Input setting will have the relevant AudioTrack embedded.
                logger.info('---------------- inputsettings -----------------------')
                logger.info(inputsettings)

                job, job_output_destination = self.__create_mp4_clips(
                    inputsettings, index, batch_id, res.strip(), resolution_thumbnail_mapping)

                logger.info(
                    '---------------- after __create_mp4_clips -----------------------')
                logger.info(job)

                if job != None:
                    all_mp4_clip_job_metadata.append({
                        "JobsId": job['Job']['Id'],
                        "OutputDestination": job_output_destination,
                        "BatchId": batch_id
                    })

                index += 1

            job_metadata.append({
                "Resolution": res,
                "JobMetadata": all_mp4_clip_job_metadata,
                "ThumbnailLocations": resolution_thumbnail_mapping
            })

        # Record the JobIds in DDB. We do this to avoid hitting MediaConvert APIs
        # and mitigate throttling. Jobs are recorded with a status of CREATED.
        # When MediaConvert emits a change in Status to Event Bridge, we update the Status
        # of the Job in DDB
        logger.info(f'JobMetadata = {job_metadata}')
        for jdata in job_metadata:
            if 'JobMetadata' in jdata:
                for job_meta in jdata['JobMetadata']:
                    jobid = job_meta['JobsId']
                    self._dataplane.save_media_convert_job_details(jobid)

        return job_metadata

    def __create_mp4_clips(self, inputSettings, index, batch_id, resolution, resolution_thumbnail_mapping):

        if len(inputSettings) == 0:
            return None

        try:

            job_settings_filename = os.path.join(
                os.path.dirname(__file__), 'job_settings_mp4.json')

            with open(job_settings_filename) as json_data:
                jobSettings = json.load(json_data)

            job_output_destination = f"s3://{OUTPUT_BUCKET}/mp4replay/{batch_id}/{resolution}/"

            jobSettings["OutputGroups"][0]["OutputGroupSettings"]["FileGroupSettings"]["Destination"] = job_output_destination

            #jobSettings["OutputGroups"][0]['Outputs'][0]["NameModifier"] = f"Part-{index}"

            # Set Resolution to the Output Groups for Video
            res = resolution.split(' ')[0]
            video_res = self.__get_output_jobsetting_by_resolution(res)
            
                
            jobSettings["OutputGroups"][0]['Outputs'][0]["VideoDescription"]["Width"] = video_res.ResWidth
            jobSettings["OutputGroups"][0]['Outputs'][0]["VideoDescription"]["Height"] = video_res.ResHeight
            jobSettings["OutputGroups"][0]['Outputs'][0]["VideoDescription"]["CodecSettings"]["H264Settings"]["MaxBitrate"] = video_res.MaxBitRate
            jobSettings["OutputGroups"][0]['Outputs'][0]["VideoDescription"]["CodecSettings"]["H264Settings"]["QvbrSettings"]["QvbrQualityLevel"] = video_res.QVBR

            # Set Thumbnail location as another Output Group
            thumbnail_destination = f"s3://{OUTPUT_BUCKET}/mp4replay/{batch_id}/thumbnails/{resolution}/"
            jobSettings["OutputGroups"][1]['OutputGroupSettings']['FileGroupSettings']['Destination'] = thumbnail_destination
            jobSettings["OutputGroups"][1]['Outputs'][0]["VideoDescription"]["Width"] = video_res.ResWidth
            jobSettings["OutputGroups"][1]['Outputs'][0]["VideoDescription"]["Height"] = video_res.ResHeight

            resolution_thumbnail_mapping.append({
                resolution: thumbnail_destination
            })
            jobSettings['Inputs'] = inputSettings

            # Convert the video using AWS Elemental MediaConvert
            jobMetadata = {'BatchId': batch_id, "Source": "Replay"}

            self.__put_metric("NumberOfInputsForMp4Job", len(inputSettings), [{'Name': 'Function', 'Value': 'ReplayMp4Generator'}, {
                              'Name': 'EventProgramReplayId', 'Value': f"{self.__eventName}#{self.__program}#{self.__event['ReplayRequest']['ReplayId']}"}])

            return self.__create_job(jobMetadata, jobSettings), job_output_destination

        except Exception as e:
            logger.info('Exception: %s' % e)
            raise

    def __create_job(self, jobMetadata, jobSettings):

        # Customizing Exponential backoff
        # Retries with additional client side throttling.
        boto_config = Config(
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            }
        )
        # add the account-specific endpoint to the client session
        client = boto3.client('mediaconvert', config=boto_config,
                              endpoint_url=MEDIA_CONVERT_ENDPOINT, verify=False)

        mediaConvertRole = os.environ['MediaConvertRole']

        return client.create_job(Role=mediaConvertRole, UserMetadata=jobMetadata, Settings=jobSettings, AccelerationSettings={
            'Mode': 'PREFERRED'
        }, Queue=ACCELERATION_MEDIA_CONVERT_QUEUE,)

    def __get_output_jobsetting_by_resolution(self, resolution):

        if "360p" in resolution:
            return OutputResTuple(640, 360, 7, 700000)
        elif "480p" in resolution:
            return OutputResTuple(854, 480, 7, 1000000)
        elif "720p" in resolution:
            return OutputResTuple(1280, 720, 8, 4000000)
        elif "16:9" in resolution:
            return OutputResTuple(1920, 1080, 9, 6000000)
        elif "1:1" in resolution:
            return OutputResTuple(1080, 1080, 9, 6000000)
        elif "4:5" in resolution:
            return OutputResTuple(864, 1080, 9, 6000000)
        elif "9:16" in resolution:
            return OutputResTuple(608, 1080, 9, 6000000)
        elif "2K" in resolution:
            return OutputResTuple(2560, 1440, 9, 6000000)
        elif "4K" in resolution:
            return OutputResTuple(3840, 2160, 9, 6000000)

    def __put_metric(self, metric_name, metric_value, dimensions: list):

        if ENABLE_CUSTOM_METRICS.lower() in ['yes', 'y']:
            cw_client.put_metric_data(
                Namespace='MRE',
                MetricData=[
                    {
                        'MetricName': metric_name,
                        'Dimensions': dimensions,
                        'Value': metric_value,
                        'Unit': 'Count'
                    },
                ]
            )
