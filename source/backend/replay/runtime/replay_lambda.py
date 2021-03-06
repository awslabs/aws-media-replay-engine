#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from shared.ReplayEngine import ReplayEngine
from shared.HlsGenerator import HlsGenerator 
from shared.Mp4Generator import Mp4Generator 
import boto3
import os
import json
import uuid
import datetime
from botocore.config import Config

s3_client = boto3.client("s3")
ssm = boto3.client('ssm')

OUTPUT_BUCKET = os.environ['OutputBucket']
EB_EVENT_BUS_NAME = os.environ['EB_EVENT_BUS_NAME']
eb_client = boto3.client("events")

def CreateReplay(event, context):
    '''
        Gets Invoked within the Map state. 
    '''
   
    print(event)

    process_replay, msg = should_replay_be_processed(event)
    if process_replay:

        # Within a Map state, if the EVENT has ended, update the Incoming dict with the AudioTrack
        # passed from the Map State
        if event['detail']['State'] == 'EVENT_END' or event['detail']['State'] == 'REPLAY_CREATED':
            event['detail']['Event']['AudioTrack'] = str(event['ReplayRequest']['AudioTrack'])

        # If SEGMENT_END comes in, check if an Optimizer is attached to the Profile.
        # If yes, Do not create a Replay
        if event['detail']['State'] == 'SEGMENT_END':

            from MediaReplayEngineWorkflowHelper import ControlPlane
            controlplane = ControlPlane()
            response = controlplane.get_profile(event['detail']['Segment']['ProfileName'])

            # There's an optimizer configured and has values in it, skip replay creation.
            # This is because, replays will get created when Segments are optimized.
            if 'Optimizer' in response:
                if len(response['Optimizer']) > 0:
                    return {
                        "Status": f"Replay not processed as the Profile has an Optimizer configured."
                    }

        runId = str(uuid.uuid4())
        start_time = datetime.datetime.now()
        print(f"------- Starting replay creation run id {runId} ----------------- {start_time}")
        replay = ReplayEngine(event)
        replay._create_replay()
        end_time = datetime.datetime.now()
        print(f"------- Starting replay end run id {runId}----------------- {end_time}")
        return {
            "Status": "Replay Processed",
            "RunId": runId
        }
        
    else:
        return {
            "Status": msg
        }

##@app.lambda_function()
def GetEligibleReplays(event, context):
    """
       Gets all eligible Replay Requests to be processed
    """

    from MediaReplayEngineWorkflowHelper import ControlPlane
    controlplane = ControlPlane()
    
    print(event)

    # Only if the Event has Completed, then create a replay for the Event
    # Supports use case of Creating Replays for Past/Completed Events
    if event['detail']['State'] == 'REPLAY_CREATED':
        event_name = event['detail']['Event']['Name']
        program_name = event['detail']['Event']['Program']
        
        all_replays = []
        response = get_event(event_name, program_name)
        # ONLY if the event is COMPLETE, pick up the Replay Request
        if response['Status'] == "Complete":
            if 'AudioTracks' not in response:
                raise (Exception('Event does not have AudioTracks'))

            for audioTrack in response['AudioTracks']: 
                replays = ReplayEngine.get_all_replay_requests_for_completed_events(event_name, program_name, audioTrack)
                all_replays.extend(replays)

            return { "AllReplays": all_replays }
        else:
            return {
                "AllReplays": []
            }

    # If this needs to be triggered when an Event Ends, we create a Wrapping Dict to be passed to 
    # Replay Engine.
    elif event['detail']['State'] == 'EVENT_END':
        
        event_name = event['detail']['Event']['Name']
        program_name = event['detail']['Event']['Program']

        
        all_replays = []
        response = get_event(event_name, program_name)

        #for item in response['Items']:
        if 'AudioTracks' not in response:
            raise (Exception('Event does not have AudioTracks'))

        for audioTrack in response['AudioTracks']: 
            replays = ReplayEngine._get_all_replays_for_event_end(event_name, program_name, audioTrack)
            all_replays.extend(replays)

        return { "AllReplays": all_replays }

    elif event['detail']['State'] == 'OPTIMIZED_SEGMENT_END':

        replay = ReplayEngine(event)
        replays = replay._get_all_replays_for_opto_segment_end()
    
        if len(replays) == 0:
            print('No Reply requests found for the Program/Event/AudioTrack/Status Combo')

        return {
                "AllReplays": replays
            }

    elif event['detail']['State'] == 'SEGMENT_END':

        event_name = event['detail']['Segment']['Event']
        program_name = event['detail']['Segment']['Program']
        
        replays = ReplayEngine._get_all_replays_for_segment_end(event_name, program_name)
    
        if len(replays) == 0:
            print('No Reply requests found for the Program/Event/Status Combo')

        return {
                "AllReplays": replays
        }


def get_event(event_name, program_name):
    from MediaReplayEngineWorkflowHelper import ControlPlane
    controlplane = ControlPlane()
    return controlplane.get_event(event_name, program_name)


def should_replay_be_processed(event):

    
    # If the Event received is SEGMENT based, we will only create Replay Clips
    # for CatchUp Replay Requests
    if event['detail']['State'] == 'SEGMENT_END' or event['detail']['State'] == 'OPTIMIZED_SEGMENT_END':
        if not event['ReplayRequest']['Catchup']:
            return False, f"Replay not processed as Catchup is Disabled."
    
    # If an Event has Ended and the ReplayRequest had CatchUp enabled, DO NOT Process it again.
    # The last Segment of the Catchup workflow would have generated the final Replay.
    # Just mark the Replay as Complete
    if event['detail']['State'] == 'EVENT_END':
        if event['ReplayRequest']['Catchup']:

            event_name = event['detail']['Event']['Name']
            program_name = event['detail']['Event']['Program']

            
            response = get_event(event_name, program_name)
            all_replays = []
            #for item in response['Items']:
                
            if 'AudioTracks' in response:
                for audioTrack in response['AudioTracks']: 
                    replays = ReplayEngine._get_all_replays_for_event_end(event_name, program_name, audioTrack)
                    all_replays.extend(replays)
            else:
                # If No Audio Tracks were found, this could be due to no Optimizer Configured.
                # Get all the Replay Requests for AudioTrack 1
                replays = ReplayEngine._get_all_replays_for_segment_end(event_name, program_name)
                all_replays.extend(replays)

            for replay in all_replays:
                ReplayEngine._mark_replay_complete(replay['ReplayId'], program_name, event_name)
                    
            return False, "Ignoring the creation of Replay for EVENT_END since the last CatchUp Segment has been processed."

    return True, ""

##@app.lambda_function()
def mark_replay_complete(event, context):
    print(event)
    
    if event['detail']['State'] == 'EVENT_END' or event['detail']['State'] == 'REPLAY_CREATED':
        event_name = event['detail']['Event']['Name']
        program_name = event['detail']['Event']['Program']

        for replay in event['ReplayResult']['Payload']['AllReplays']:
            ReplayEngine._mark_replay_complete(replay['ReplayId'], program_name, event_name)

    return event['MapResult'] # Used to generate Maser m3u8 files

def update_replay_with_mp4_location(event, context):
    from MediaReplayEngineWorkflowHelper import ControlPlane
    controlplane = ControlPlane()

    event_name = event['ReplayRequest']['Event']
    program_name = event['ReplayRequest']['Program']
    replay_request_id = event['ReplayRequest']['ReplayId']
    mp4_location = {}
    mp4_thumbnail_location = {}

    
    for jobresult in event['CreateMp4JobsResult']['Payload']:
        resolution = jobresult['Resolution']
        mp4_locs = []
        mp4_thumb_locs = []

        
        
        for jobdata in jobresult['JobMetadata']:
            s3_path = jobdata['OutputDestination'].split('/')
            keyprefix = f"{s3_path[3]}/{s3_path[4]}/{s3_path[5]}/"
            print(f"keyprefix = {keyprefix}")
            filenames = get_output_filename(keyprefix, "mp4")
            print(f"filenames = {filenames}")
            if len(filenames) > 0:
                mp4_locs.append("s3://" + OUTPUT_BUCKET + "/" + filenames[0])
            else:
                mp4_locs.append(jobdata['OutputDestination'])
        
        # Store Replay MP4 Thumbnails
        for jobdata in jobresult['ThumbnailLocations']:
            if resolution in jobdata.keys():
                s3_path = jobdata[resolution].split('/')
                keyprefix = f"{s3_path[3]}/{s3_path[4]}/{s3_path[5]}/{s3_path[6]}/"
                print(f"keyprefix = {keyprefix}")
                filenames = get_output_filename(keyprefix, "jpg")
                print(f"filenames = {filenames}")
                if len(filenames) > 0:
                    mp4_thumb_locs.append("s3://" + OUTPUT_BUCKET + "/" + filenames[0])
                else:
                    mp4_thumb_locs.append(jobdata[resolution])
                

        # Store Replay MP4 Clips
        mp4_location[resolution] = {}
        mp4_location[resolution]['ReplayClips'] = mp4_locs
        mp4_thumbnail_location[resolution] = {}
        mp4_thumbnail_location[resolution]['ReplayThumbnails'] = mp4_thumb_locs
    
    controlplane.update_replay_request_with_mp4_location(event_name, program_name, replay_request_id, mp4_location, mp4_thumbnail_location)

    # Update the Event that a replay has been created for the Event
    controlplane.update_event_has_replays(event_name, program_name)

    # Notify EventBridge
    detail = {
        "State": "REPLAY_PROCESSED",
        "Event": {
            "Event": event_name,
            "Program": program_name,
            "ReplayId": replay_request_id,
            "EventType": "REPLAY_GEN_DONE"
        }
    }
    eb_client.put_events(
        Entries=[
            {
                "Source": "awsmre",
                "DetailType": "Base Replay Data Exported",
                "Detail": json.dumps(detail),
                "EventBusName": EB_EVENT_BUS_NAME
            }
        ]
    )


#@app.lambda_function()
def generate_master_playlist(event, context):
    '''
        Generates a master Playlist with various Quality levels representing different resolutions
        #EXTM3U
        #EXT-X-STREAM-INF:BANDWIDTH=25000000,RESOLUTION=3840x2160
        4K/TestProgram_AK555_1_00002Part-1.m3u8
        #EXT-X-STREAM-INF:BANDWIDTH=25000000,RESOLUTION=2560x1440
        2K/TestProgram_AK555_1_00002Part-1.m3u8
        #EXT-X-STREAM-INF:BANDWIDTH=6000000,RESOLUTION=1920x1080
        1080p/TestProgram_AK555_1_00002Part-1.m3u8
        #EXT-X-STREAM-INF:BANDWIDTH=3000000,RESOLUTION=1280x720
        720p/TestProgram_AK555_1_00002Part-1.m3u8
    '''

    from MediaReplayEngineWorkflowHelper import ControlPlane
    controlplane = ControlPlane()

    playlist_content = []
    playlist_content.append('#EXTM3U')
    bucket = ''
    thumbnail_location = '-'
    does_play_list_exist = False
    for jobResult in event['CreateHlsJobsResult']["Payload"]:

        resolution = jobResult['Resolution']

        res_desc = get_resolution_hls_desc(resolution)
        playlist_content.append(res_desc)
        if 'JobMetadata' in jobResult:
            if len(jobResult['JobMetadata']) > 0:
                s3_path = jobResult['JobMetadata'][0]['OutputDestination'].split('/')

                #['s3', '', 'aws-mre-clip-gen-output', 'HLS', 'ak555-testprogram', '4K', '']
                bucket = s3_path[2]
                keyprefix = f"{s3_path[3]}/{s3_path[4]}/{s3_path[5]}/"

                manifests = get_all_manifests(bucket, keyprefix)
                for manifest in manifests:
                    manifest_path = manifest.split('/')
                    playlist_content.append(f"{resolution.replace(':', '')}/{manifest_path[3]}")
                    
                does_play_list_exist = True #We know at least 1 HLS manifest exists, mark this so we can trigger the creation of the Master Manifest

        # Get the location of the Thumbnail generated for the Hls stream
        # We pick up the last thumbnail location in the CreateHlsJobsResult list
        if 'ThumbnailLocations' in jobResult:
            if len(jobResult['ThumbnailLocations']) > 0:
                # S3 location of the Thumbnail (without the file name generated by MediaConvert).
                key_name = list(jobResult['ThumbnailLocations'][0].keys())[0]
                thumbnail_loc = jobResult['ThumbnailLocations'][0][key_name]

                # Get the thumbnail file s3 Path
                tmp_loc = thumbnail_loc.split('/')
                thumbnail_location_tmp_loc = f"{tmp_loc[3]}/{tmp_loc[4]}/{tmp_loc[5]}/{tmp_loc[6]}/"
                thumbnail_location = get_s3_thumbnail_path(thumbnail_location_tmp_loc)
                thumbnail_location = f"s3://{OUTPUT_BUCKET}/{thumbnail_location}"

    playlist_location = ''
    # If the Playlist content has no manifest file locations of HLS, theres no point in creating a new Master Manifest
    if does_play_list_exist:
        create_manifest_file(playlist_content)
        
        event_name = event['ReplayRequest']['Event']
        program_name = event['ReplayRequest']['Program']
        replay_request_id = event['ReplayRequest']['ReplayId']
        batch_id = event['CreateHlsJobsResult']["Payload"][0]['JobMetadata'][0]['BatchId']

        #key_prefix = f"HLS/{event_name.lower()}-{program_name.lower()}-{replay_request_id}/master-playlist.m3u8"
        key_prefix = f"HLS/{batch_id}/master-playlist.m3u8"

        # Upload final Manifest File to S3
        # s3_client.upload_file("/tmp/main.m3u8", bucket, f"{keyPrefix}/main.m3u8", ExtraArgs={'ACL':'public-read'})
        s3_client.upload_file("/tmp/main.m3u8", bucket, key_prefix)

        playlist_location = f"s3://{bucket}/{key_prefix}"

        payload = {
            "Event": event_name,
            "Program": program_name,
            "ReplayRequestId": replay_request_id,
            "HlsLocation": playlist_location,
            "Thumbnail": thumbnail_location
        }

        controlplane.update_replay_request_with_hls_location(payload)

        # Update the Event that a replay has been created for the Event
        controlplane.update_event_has_replays(event_name, program_name)

        # Notify EventBridge
        detail = {
            "State": "REPLAY_PROCESSED",
            "Event": {
                "Event": event_name,
                "Program": program_name,
                "ReplayId": replay_request_id,
                "EventType": "REPLAY_GEN_DONE"
            }
        }
        eb_client.put_events(
            Entries=[
                {
                    "Source": "awsmre",
                    "DetailType": "Base Replay Data Exported",
                    "Detail": json.dumps(detail),
                    "EventBusName": EB_EVENT_BUS_NAME
                }
            ]
        )

        runId = 'NA'
        if 'CurrentReplayResult' in event:
            if 'RunId' in event['CurrentReplayResult']:
                runId = event['CurrentReplayResult']['RunId']
        
        if runId != 'NA':
            end_time = datetime.datetime.now()
            print(f"------- Updated HLS Location - RunID - {runId} ----------------- {end_time}")

    return {
        "MasterPlaylist": 'No playlist was found. This may not always be an error.' if playlist_location == '' else playlist_location
    }

def get_s3_thumbnail_path(keyPrefix):
    
    s3_paginator = boto3.client('s3').get_paginator('list_objects_v2')
    for page in s3_paginator.paginate(Bucket=OUTPUT_BUCKET, Prefix=keyPrefix):
        for content in page.get('Contents', ()):
            return content['Key']

    return '-'
def create_manifest_file(final_manifest_content):
    with open("/tmp/main.m3u8", "w") as output:
        for row in final_manifest_content:
            output.write(str(row) + '\n')


def get_all_manifests(bucket, keyPrefix):
    
    manifests = []
    s3_paginator = boto3.client('s3').get_paginator('list_objects_v2')
    
    for page in s3_paginator.paginate(Bucket=bucket, Prefix=keyPrefix):
        for content in page.get('Contents', ()):
            if "Part" in content['Key'] and ".m3u8" in content['Key']:
                manifests.append(content['Key'])

    return manifests


def get_resolution_hls_desc(resolution):
    if resolution.lower() == "4k":
        return "#EXT-X-STREAM-INF:BANDWIDTH=18200,RESOLUTION=3840x2160"
    elif resolution.lower() == "2k":
        return "#EXT-X-STREAM-INF:BANDWIDTH=7400000,RESOLUTION=2560x1440"
    elif resolution.lower() == "16:9":
        return "#EXT-X-STREAM-INF:BANDWIDTH=5300000,RESOLUTION=1920x1080"
    elif resolution.lower() == "1:1":
        return "#EXT-X-STREAM-INF:BANDWIDTH=5300000,RESOLUTION=1080x1080"
    elif resolution.lower() == "4:5":
        return "#EXT-X-STREAM-INF:BANDWIDTH=5300000,RESOLUTION=864x1080"
    elif resolution.lower() == "9:16":
        return "#EXT-X-STREAM-INF:BANDWIDTH=5300000,RESOLUTION=608x1080"
    elif resolution.lower() == "720p":
        return "#EXT-X-STREAM-INF:BANDWIDTH=3200000,RESOLUTION=1280x720"
    elif resolution.lower() == "480p":
        return "#EXT-X-STREAM-INF:BANDWIDTH=1600000,RESOLUTION=854x480"
    elif resolution.lower() == "360p":
        return "#EXT-X-STREAM-INF:BANDWIDTH=900000,RESOLUTION=640x360"

#@app.lambda_function()
def generate_hls_clips(event, context):

    #1. Get Replay Segments
    #2. Segment could be Opto or no Opto
    #3. Create HLS Jobs for every segment by considering Chunk timings
    #4. Send Job Ids to the next State
    hls_gen = HlsGenerator(event)
    return hls_gen.generate_hls()

def generate_mp4_clips(event, context):

    #1. Get Replay Segments
    #2. Segment could be Opto or no Opto
    #3. Create MP4 Jobs for every segment by considering Chunk timings
    #4. Send Job Ids to the next State
    mp4_gen = Mp4Generator(event)
    return mp4_gen.generate_mp4()

def check_mp4_job_status(event, context):
    endpoint = ssm.get_parameter(Name='/MRE/ClipGen/MediaConvertEndpoint', WithDecryption=False)['Parameter']['Value'] 

    # Customizing Exponential backoff
    # Retries with additional client side throttling.
    boto_config = Config(
        retries = {
            'max_attempts': 10,
            'mode': 'adaptive'
        }
    )
    # add the account-specific endpoint to the client session x
    client = boto3.client('mediaconvert', config=boto_config, endpoint_url=endpoint, verify=False)
    
    all_jobs_complete = True
    for jobResult in event['CreateMp4JobsResult']["Payload"]:
        for jobMetData in jobResult['JobMetadata']:
            try:
                response = client.get_job(Id=jobMetData['JobsId'])
                if response['Job']['Status'] != 'COMPLETE':
                    all_jobs_complete = False
                    break
            except Exception as e:
                # get_job may fail with a TooManyRequest exception. Lets have the State machine re-try this in the subsequent execution
                all_jobs_complete = False

    return { "Status": "Complete" } if all_jobs_complete else { "Status": "InComplete" }

#@app.lambda_function()
def check_Hls_job_status(event, context):

    endpoint = ssm.get_parameter(Name='/MRE/ClipGen/MediaConvertEndpoint', WithDecryption=False)['Parameter']['Value'] 

    # Customizing Exponential backoff
    # Retries with additional client side throttling.
    boto_config = Config(
        retries = {
            'max_attempts': 10,
            'mode': 'adaptive'
        }
    )
    # add the account-specific endpoint to the client session x
    client = boto3.client('mediaconvert', config=boto_config, endpoint_url=endpoint, verify=False)
    
    all_jobs_complete = True
    for jobResult in event['CreateHlsJobsResult']["Payload"]:
        for jobMetData in jobResult['JobMetadata']:
            try:
                response = client.get_job(Id=jobMetData['JobsId'])
                if response['Job']['Status'] != 'COMPLETE':
                    all_jobs_complete = False
                    break
            except Exception as e:
                # get_job may fail with a TooManyRequest exception. Lets have the State machine re-try this in the subsequent execution
                all_jobs_complete = False

    return { "Status": "Complete" } if all_jobs_complete else { "Status": "InComplete" }

def get_output_filename(keyPrefix, file_extn):
    
        manifests = []
        s3_paginator = boto3.client('s3').get_paginator('list_objects_v2')
        
        for page in s3_paginator.paginate(Bucket=OUTPUT_BUCKET, Prefix=keyPrefix):
            for content in page.get('Contents', ()):
                if f".{file_extn}" in content['Key']:
                    manifests.append(content['Key'])

        return manifests