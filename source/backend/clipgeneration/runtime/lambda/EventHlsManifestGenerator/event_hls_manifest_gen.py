#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import boto3
import urllib3
from boto3 import client
from botocore.config import Config

urllib3.disable_warnings()
s3 = boto3.resource('s3')
s3_client = boto3.client('s3')
ssm = boto3.client('ssm')

'''
Event Payload Structure expected from 

{
  "Event": {
    "Name": "Olympics",
    "Program": "Olympics",
    "FrameRate": 25
  },
  "Segments": [
    {
      ....
    }
  ],
  "ClipGen": {
    "Payload": {
      "MediaConvertJobs": [
        "1623711086610-30l2m9"
      ],
      "HLSOutputKeyPrefix": "HLS/c481f5f5-c80d-4c23-90fc-9e69acf4fbca",
      "OutputBucket": "aws-mre-clip-gen-output"
    },

Creates a Output HLS Manifest (main.m3u8) in the following format
Open the final Manifest in Safari or at https://hls-js.netlify.app/demo/

#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:11
#EXT-X-MEDIA-SEQUENCE:1
#EXTINF:11,
Reeu1200927005_1-YS-3min_1_00001Part1_00001.ts
#EXTINF:11,
Reeu1200927005_1-YS-3min_1_00001Part1_00002.ts
#EXTINF:10,
Reeu1200927005_1-YS-3min_1_00001Part1_00003.ts
#EXTINF:8,
Reeu1200927005_1-YS-3min_1_00001Part1_00004.ts
#EXT-X-DISCONTINUITY
#EXTINF:11,
Reeu1200927005_1-YS-3min_1_00003Part2_00001.ts
#EXTINF:11,
Reeu1200927005_1-YS-3min_1_00003Part2_00002.ts
#EXTINF:10,
Reeu1200927005_1-YS-3min_1_00003Part2_00003.ts
#EXTINF:8,
Reeu1200927005_1-YS-3min_1_00003Part2_00004.ts
#EXT-X-DISCONTINUITY

#EXTM3U
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=2149280,CODECS="mp4a.40.2,avc1.64001f",RESOLUTION=1280x720,NAME="720"
url_0/193039199_mp4_h264_aac_hd_7.m3u8
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=246440,CODECS="mp4a.40.5,avc1.42000d",RESOLUTION=320x184,NAME="240"
url_2/193039199_mp4_h264_aac_ld_7.m3u8
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=460560,CODECS="mp4a.40.5,avc1.420016",RESOLUTION=512x288,NAME="380"
url_4/193039199_mp4_h264_aac_7.m3u8
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=836280,CODECS="mp4a.40.2,avc1.64001f",RESOLUTION=848x480,NAME="480"
url_6/193039199_mp4_h264_aac_hq_7.m3u8
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=6221600,CODECS="mp4a.40.2,avc1.640028",RESOLUTION=1920x1080,NAME="1080"
url_8/193039199_mp4_h264_aac_fhd_7.m3u8

'''

#@app.lambda_function()
def create_hls_manifest(event, context):

    from MediaReplayEngineWorkflowHelper import ControlPlane
    controlplane = ControlPlane()


    print('Processing the following m3u8 files')
    print(event['ClipGen']['Payload']['MediaConvertJobs'])
    bucket = event['ClipGen']['Payload']['OutputBucket']

    if 'Optimizer' in event['Profile']:
        print('Optimizer')
        keyPrefix = event['ClipGen']['Payload']['HLSOutputKeyPrefix']
        manifest_content = create_final_manifest(bucket, keyPrefix)

        
        # Create final merged maniest file
        if len(manifest_content) > 0:
            create_manifest_file(manifest_content)

            event_name = event['Event']['Name']
            program_name = event['Event']['Program']

            track = "0" if 'TrackNumber' not in event else str(event['TrackNumber'])

            # If no tracknumber found, we will only have one HlsMasterManifest - For Original Segments
            #if track == "0":
            #    key_prefix = f"{keyPrefix}master-manifest-{track}.m3u8"
            #else:
            # If tracknumber found, we there will be one HlsMasterManifest per track
            key_prefix = f"{keyPrefix}master-manifest-{track}.m3u8"

            # Upload final Manifest File to S3
            # s3_client.upload_file("/tmp/main.m3u8", bucket, f"{keyPrefix}/main.m3u8", ExtraArgs={'ACL':'public-read'})
            s3_client.upload_file("/tmp/main.m3u8", bucket, key_prefix)

            hls_location = f"s3://{bucket}/{key_prefix}"

            # Update the HLS Manifest location with the event
            if track != "0":
                controlplane.update_hls_master_manifest_location(event_name, program_name, hls_location, track)

            return {
                "ManifestLocation": hls_location
            }
        else:
            return {
                "ManifestLocation": "Master Manifest Not generated. No child manifests were found."
            }
    else:
        hls_locations = []
        for track in event['Event']['AudioTracks']:
            print(f'Not Optimizer ...{track}')

            keyPrefix = event['ClipGen']['Payload']['HLSOutputKeyPrefix']
            keyPrefix = f"{keyPrefix}{track}/"
            
            print(keyPrefix)
            print(bucket)

            manifest_content = create_final_manifest(bucket, keyPrefix)
            print(f'manifest_content ...{manifest_content}')

            # Create final merged maniest file
            if len(manifest_content) > 0:
                create_manifest_file(manifest_content)

                event_name = event['Event']['Name']
                program_name = event['Event']['Program']
                
                key_prefix = f"{keyPrefix}master-manifest-{track}.m3u8"

                # Upload final Manifest File to S3
                # s3_client.upload_file("/tmp/main.m3u8", bucket, f"{keyPrefix}/main.m3u8", ExtraArgs={'ACL':'public-read'})
                s3_client.upload_file("/tmp/main.m3u8", bucket, key_prefix)

                hls_location = f"s3://{bucket}/{key_prefix}"

                # Update the HLS Manifest location with the event
                if track != "0":
                    controlplane.update_hls_master_manifest_location(event_name, program_name, hls_location, str(track))

                hls_locations.append(hls_location)
            else:
                hls_locations.append("Master Manifest Not generated. No child manifests were found.")
                    
        return {
                "ManifestLocation": hls_locations
            }        
    
#@app.lambda_function()
def media_convert_job_status(event, context):
    
    if are_all_jobs_complete(event['ClipGen']['Payload']['MediaConvertJobs']):
        return {
            "Status": "Complete"
        }
    else:
        return {
            "Status": "InComplete"
        }
    
    
def are_all_jobs_complete(jobs):

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

    
    for jobId in jobs:
        response = client.get_job(Id=jobId)
        if response['Job']['Status'] != 'COMPLETE':
            return False


    return True



def create_final_manifest(bucket, keyPrefix):
    final_manifest_content = []
    all_manifests = get_all_manifests(bucket, keyPrefix)

    # The above Manifests would be in Ascending order by default (via s3)
    # Add #EXT-X-DISCONTINUITY for every new manifest 
    #For subsequent Manifests
    # Skip the top 5 Lines
    # Read the rest ignoring the last line - #EXT-X-ENDLIST
    if len(all_manifests) > 0:
        final_manifest_content = read_first_manifest(all_manifests[0], bucket)
        final_manifest_content.extend(process_other_manifests(all_manifests, bucket))
        final_manifest_content.append("#EXT-X-ENDLIST")

    return final_manifest_content

def create_manifest_file(final_manifest_content):
    with open("/tmp/main.m3u8", "w") as output:
        for row in final_manifest_content:
            output.write(str(row) + '\n')
            

def read_first_manifest(firstManifest, bucket):

    reqd_content = []
     # Read the first 4 Lines from the First Manifest
    # Skip the 5th - #EXT-X-PLAYLIST-TYPE:VOD
    # Read the Rest ignoring the last line - #EXT-X-ENDLIST

    s3 = boto3.resource('s3')
    first_manifest_content = s3.Object(bucket, firstManifest).get()['Body'].read().decode('utf-8').splitlines()

    print(first_manifest_content)

    i = 1
    for line in first_manifest_content:
        # Skip 5th line and the Last line
        if i == 5 or i == len(first_manifest_content):
            i += 1
        else:
            reqd_content.append(line)
            i += 1

    reqd_content.append("#EXT-X-DISCONTINUITY")
    return reqd_content

def read_other_manifest(manifest, bucket):    

    reqd_content = []

    # For subsequent Manifests
    # Skip the top 5 Lines
    # Read the rest ignoring the last line - #EXT-X-ENDLIST

    s3 = boto3.resource('s3')
    manifest_content = s3.Object(bucket, manifest).get()['Body'].read().decode('utf-8').splitlines()
    i = 1
    for line in manifest_content:
        # Skip 5th line and the Last line
        if i <= 5 or i == len(manifest_content):
            i += 1
        else:
            reqd_content.append(line)
            i += 1

    return reqd_content

def process_other_manifests(manifests, bucket):
    manifest_content = []
    i = 1
    for manifest in manifests:
        if i != 1:
            content = read_other_manifest(manifest, bucket)

            # Append the Content array to the manifest_content
            manifest_content.extend(content)

            # Add #EXT-X-DISCONTINUITY for every playlist manifest excepting the last one
            if i != len(manifests):
                manifest_content.append("#EXT-X-DISCONTINUITY")
        i += 1

    return manifest_content

def get_all_manifests(bucket, keyPrefix):
    
    manifests = []
    s3_paginator = boto3.client('s3').get_paginator('list_objects_v2')
    
    for page in s3_paginator.paginate(Bucket=bucket, Prefix=keyPrefix):
        for content in page.get('Contents', ()):
            if "Part" in content['Key'] and ".m3u8" in content['Key']:
                manifests.append(content['Key'])

    return manifests
