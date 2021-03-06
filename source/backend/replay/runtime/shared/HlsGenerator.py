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

MAX_INPUTS_PER_JOB = int(os.environ['MediaConvertMaxInputJobs']) 
ACCELERATION_MEDIA_CONVERT_QUEUE = os.environ['MediaConvertAcceleratorQueueArn']
OUTPUT_BUCKET = os.environ['OutputBucket'] 
ssm = boto3.client('ssm')

class HlsGenerator:

    def __init__(self, event):

        from MediaReplayEngineWorkflowHelper import ControlPlane
        self._controlPlane = ControlPlane()

        tmpEvent = self.__get_dataplane_payload(event)

        self.__eventName = tmpEvent['Event']['Name']
        self.__program = tmpEvent['Event']['Program']
        self.__profile = tmpEvent['Profile']['Name']
        self.__framerate = tmpEvent['Profile']['ProcessingFrameRate']

        from MediaReplayEnginePluginHelper import DataPlane
        self._dataplane = DataPlane(tmpEvent)

        
        self.__event = event

    def __get_dataplane_payload(self, event):

        program = event['ReplayRequest']['Program']
        event = event['ReplayRequest']['Event']

        event_details = self._controlPlane.get_event(event, program)
        profile_name = event_details['Profile']

        profile_detail = self._controlPlane.get_profile(profile_name)

        final_event = {
            "Event": {
                "Program": program,
                "Name": event
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

        
    def generate_hls(self):
        #program = self.__event['ReplayRequest']['Program']
        #event = self.__event['ReplayRequest']['Event']
        replay_id = self.__event['ReplayRequest']['ReplayId']
        audio_track = self.__event['ReplayRequest']['AudioTrack']

        event_details = self._controlPlane.get_event(self.__eventName, self.__program)
        profile_name = event_details['Profile']

        output_resolutions = self.__event['ReplayRequest']['Resolutions']
        
        # Segments that have beeb created for the current Replay
        replay_segments = self._dataplane.get_all_segments_for_replay(self.__program, self.__eventName, replay_id)

        print('---------------- get_all_segments_for_replay -----------------------')
        print(replay_segments)
        #batch_id = f"{str(self.__eventName).lower()}-{str(self.__program).lower()}-{replay_id}"
        batch_id = f"{str(uuid.uuid4())}"


        
        job_metadata = []
        resolution_thumbnail_mapping = []
        # For each Resolution in the Replay Request, create Media Convert Jobs
        # by configuring the Output Resolution and Input Clip settings using Replay Segment Information
        for resolution in output_resolutions:

            job_output_destinations = []
            # Contains Job IDs for all the HLS Jobs. We will need to 
            # check if all Jobs have completed before creating the Aggregated
            # m3u8 file
            all_hls_clip_job_metadata = []


            # Create Input settings per segment
            input_job_settings = []
            for segment in replay_segments:

                startTime = segment['OptoStart'] if 'OptoStart' in segment else segment['Start']
                endTime = segment['OptoEnd'] if 'OptoEnd' in segment else segment['End']
                chunks = self._dataplane.get_chunks_for_segment(startTime, endTime, self.__program, self.__eventName, profile_name )
                

                input_settings = self.__build_hls_input(chunks, audio_track, startTime, endTime)
                print('---------------- __build_hls_input -----------------------')
                print(input_settings)
                input_job_settings.extend(input_settings)

            
            groups_of_input_settings = [input_job_settings[x:x+MAX_INPUTS_PER_JOB] for x in range(0, len(input_job_settings), MAX_INPUTS_PER_JOB)]
            index = 1
            res = resolution.split(' ')[0]

            print('---------------- groups_of_input_settings -----------------------')
            print(groups_of_input_settings)

            for inputsettings in groups_of_input_settings:
                # Each Input setting will have the relevant AudioTrack embedded.
                print('---------------- inputsettings -----------------------')
                print(inputsettings)
                
                job, job_output_destination = self.__create_HLS_clips(inputsettings, index, batch_id, res.strip(), resolution_thumbnail_mapping)

                print('---------------- after __create_HLS_clips -----------------------')
                print(job)

                if job != None:
                    all_hls_clip_job_metadata.append({
                        "JobsId": job['Job']['Id'],
                        "OutputDestination": job_output_destination,
                        "BatchId": batch_id
                    })

                index += 1
            
            job_metadata.append({
                "Resolution": res,
                "JobMetadata": all_hls_clip_job_metadata,
                "ThumbnailLocations": resolution_thumbnail_mapping
                
            })

        return job_metadata

    def __build_hls_input(self, chunks ,audioTrack, start_time, end_time):
    
        inputs = []

        # Only chunk, so will have Start and End Clipping time
        if len(chunks) == 1:
            inputClippings = []
            inputClip = {}
            ic = {}

            endtime = self._dataplane.get_mediaconvert_clip_format(end_time, program=self.__program, event=self.__eventName, profile=self.__profile, frame_rate=self.__framerate)
            starttime = self._dataplane.get_mediaconvert_clip_format(start_time, program=self.__program, event=self.__eventName, profile=self.__profile, frame_rate=self.__framerate)

            #endtime, starttime = self._dataplane.get_mediaconvert_clip_format(end_time), self._dataplane.get_mediaconvert_clip_format(start_time)
            ic['EndTimecode'] = str(endtime)
            ic['StartTimecode'] = str(starttime)

            #If we have a single Chunk we don't need the Endtime Configured if it is less than Start time. Remove it.
            if datetime.strptime(endtime, "%H:%M:%S:%f") < datetime.strptime(starttime, "%H:%M:%S:%f"):
                ic.pop('EndTimecode', None)

            #ic['EndTimecode'], ic['StartTimecode'] = get_clip_timings(segment, event)
            inputClippings.append(ic)
            inputClip['InputClippings'] = inputClippings
        
            #------------- Update MediaConvert AudioSelectors Input -------------

            # Leave the default Input AudioSelectors as is if we are dealing with default Track or only one.
            # If we have multiple AudioTracks, this lambda will be provided with one.
            
            inputClip['AudioSelectors'] =   {
                                                "Audio Selector 1": {
                                                    "Tracks": [
                                                        int(audioTrack)
                                                    ],
                                                    "DefaultSelection": "NOT_DEFAULT",
                                                    "SelectorType": "TRACK"
                                                }
                                            }

            inputClip['AudioSelectorGroups'] =  {
                                                    "Audio Selector Group 1": {
                                                        "AudioSelectorNames": [
                                                        "Audio Selector 1"
                                                        ]
                                                    }
                                                }
                                                
            #------------- Update MediaConvert AudioSelectors Input Ends -------------
            
            inputClip['VideoSelector'] = {}
            inputClip['TimecodeSource'] = "ZEROBASED"
            inputClip['FileInput'] = f"s3://{chunks[0]['S3Bucket']}/{chunks[0]['S3Key']}"
            inputs.append(inputClip)
        elif len(chunks) > 1:
            for chunk_index in range(len(chunks)):
                ic = {}
                inputClippings = []
                inputClip = {}
                if chunk_index == 0:    # First Chunk
                    ic['StartTimecode'] = self._dataplane.get_mediaconvert_clip_format(start_time, program=self.__program, event=self.__eventName, profile=self.__profile, frame_rate=self.__framerate)
                    
                    inputClippings.append(ic)
                    inputClip['InputClippings'] = inputClippings
                elif chunk_index == len(chunks)-1:  # Last Chunk
                    ic['EndTimecode'] = self._dataplane.get_mediaconvert_clip_format(end_time, program=self.__program, event=self.__eventName, profile=self.__profile, frame_rate=self.__framerate)
                    inputClippings.append(ic)
                    inputClip['InputClippings'] = inputClippings
                else:   # Sandwitch Chunks have no clippings
                    inputClip['InputClippings'] = []

                
                #------------- Update MediaConvert AudioSelectors Input -------------

                # Leave the default Input AudioSelectors as is if we are dealing with default Track or only one.
                # If we have multiple AudioTracks, this lambda will be provided with one.
                inputClip['AudioSelectors'] =   {
                                                    "Audio Selector 1": {
                                                        "Tracks": [
                                                            int(audioTrack)
                                                        ],
                                                        "DefaultSelection": "NOT_DEFAULT",
                                                        "SelectorType": "TRACK"
                                                    }
                                                }

                inputClip['AudioSelectorGroups'] =  {
                                                        "Audio Selector Group 1": {
                                                            "AudioSelectorNames": [
                                                            "Audio Selector 1"
                                                            ]
                                                        }
                                                    }
                                                    
            #------------- Update MediaConvert AudioSelectors Input Ends -------------
                inputClip['VideoSelector'] = {}
                inputClip['TimecodeSource'] = "ZEROBASED"
                inputClip['FileInput'] = f"s3://{chunks[chunk_index]['S3Bucket']}/{chunks[chunk_index]['S3Key']}"
                inputs.append(inputClip)

        return inputs


    def __create_HLS_clips(self, inputSettings, index, batch_id, resolution, resolution_thumbnail_mapping):

        if len(inputSettings) == 0:
            return None

        try:
            # For specific Aspect Ratio's having ':' (like 16:9) , remove them. This causes problems when HLS manifest files have : in child manifest file paths
            resolution = resolution.replace(":", "")

            job_settings_filename = os.path.join(os.path.dirname(__file__), 'job_settings_hls.json')
                    
            with open(job_settings_filename) as json_data:
                jobSettings = json.load(json_data)
                
            job_output_destination = f"s3://{OUTPUT_BUCKET}/HLS/{batch_id}/{resolution}/"
            
            jobSettings["OutputGroups"][0]["OutputGroupSettings"]["HlsGroupSettings"]["Destination"] = job_output_destination
            
            jobSettings["OutputGroups"][0]['Outputs'][0]["NameModifier"] = f"Part-{index}"
            
            # Set Resolution to the Output Groups
            res = resolution.split(' ')[0]
            video_res_width, video_res_height = self.__get_output_jobsetting_by_resolution(res)
            jobSettings["OutputGroups"][0]['Outputs'][0]["VideoDescription"]["Width"] = video_res_width
            jobSettings["OutputGroups"][0]['Outputs'][0]["VideoDescription"]["Height"] = video_res_height

            jobSettings["OutputGroups"][0]["OutputGroupSettings"]["HlsGroupSettings"]["AdditionalManifests"] =  [{
                                                                                                                    "ManifestNameModifier": f"Batch-{index}",
                                                                                                                    "SelectedOutputs": [
                                                                                                                            f"Part-{index}"
                                                                                                                        ]
                                                                                                                }]
            # Set Thumbnail location
            thumbnail_destination = f"s3://{OUTPUT_BUCKET}/HLS/{batch_id}/thumbnails/{resolution}/"
            jobSettings["OutputGroups"][1]['OutputGroupSettings']['FileGroupSettings']['Destination'] = thumbnail_destination
            jobSettings["OutputGroups"][1]['Outputs'][0]["VideoDescription"]["Width"] = video_res_width
            jobSettings["OutputGroups"][1]['Outputs'][0]["VideoDescription"]["Height"] = video_res_height
            resolution_thumbnail_mapping.append({
                resolution: thumbnail_destination
            })     
            jobSettings['Inputs'] = inputSettings

            # Convert the video using AWS Elemental MediaConvert
            jobMetadata = { 'BatchId': batch_id }

            return self.__create_job(jobMetadata, jobSettings), job_output_destination

        except Exception as e:
            print ('Exception: %s' % e)
            raise

    def __create_job(self, jobMetadata, jobSettings):

        # get the account-specific mediaconvert endpoint for this region
        endpoint = ssm.get_parameter(Name='/MRE/ClipGen/MediaConvertEndpoint', WithDecryption=False)['Parameter']['Value'] 

        # Customizing Exponential backoff
        # Retries with additional client side throttling.
        boto_config = Config(
            retries = {
                'max_attempts': 10,
                'mode': 'adaptive'
            }
        )
        
        # add the account-specific endpoint to the client session 
        client = boto3.client('mediaconvert', config=boto_config, endpoint_url=endpoint, verify=False)

        mediaConvertRole = os.environ['MediaConvertRole']
        return client.create_job(Role=mediaConvertRole, UserMetadata=jobMetadata, Settings=jobSettings, AccelerationSettings={
        'Mode': 'PREFERRED'
        }, Queue=ACCELERATION_MEDIA_CONVERT_QUEUE,)

    def __get_output_jobsetting_by_resolution(self, resolution):

        if "360p" in resolution:
            return 640, 360
        elif "480p" in resolution:
            return 854, 480
        elif "720p" in resolution:
            return 1280, 720
        elif "169" in resolution:
            return 1920, 1080
        elif "11" in resolution:
            return 1080, 1080
        elif "45" in resolution:
            return 864, 1080
        elif "916" in resolution:
            return 608, 1080
        elif "2K" in resolution:
            return 2560, 1440
        elif "4K" in resolution:
            return 3840, 2160
            
    