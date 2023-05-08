# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import os
import boto3
from botocore.exceptions import ClientError
import math
import time
import ffmpeg
from ffmpeg import Error
import random
import string

from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import PluginHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane

s3_client = boto3.client('s3')
transcribe_client = boto3.client('transcribe')

def prepare_s3_object_name(file_name):
    object_name = file_name.replace(' ', '_')
    return object_name


def upload_file(file_name, bucket, object_name=None):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    print("Uploading to: " + bucket)
    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = file_name

    # Upload the file
    try:
        response = s3_client.upload_file(file_name, bucket, object_name)

    except ClientError as e:
        print(e)
        return False
    return True

def rip_audio_to_file(video_filename, track=1):
    print(video_filename)
    tmp_file = video_filename.split('.')[-2]
    tmp_file += '_track_' + str(track)
    tmp_file += '.mp3'
    print('Temp MP3 file:',tmp_file)
    try:
        stream = ffmpeg.input(video_filename)
        out, err = (
            ffmpeg.output(stream[str(track)],tmp_file,format='mp3',ar='16000')
            .run(capture_stdout=True, capture_stderr=True,overwrite_output=True)
        )
    except ffmpeg.Error as err:
        print(err.stderr)
        raise

    return tmp_file


def consolidate_transcribe_results(raw_results_file, mre_pluginhelper, speech_delay_sec=2):
    results = []
    result = {}
    
    with open(raw_results_file, encoding="utf8", errors='ignore') as f:
        raw_results = json.load(f)

        # Loop through results and convert chunk time values to event time
        for item in raw_results['results']['items']:
            #not all results have a start and end time
            if item['type'] == 'pronunciation':
                if 'Start' not in result:
                    result = {}
                    result['Start'] = mre_pluginhelper.get_segment_absolute_time(float(item['start_time']))
                    result['End'] = mre_pluginhelper.get_segment_absolute_time(float(item['end_time']))
                    result['Label'] = 'speech present'
                    result['Transcription'] = item['alternatives'][0]['content']
                    
                else:
                    #check if the start is > the delay relative to the last item
                    start = mre_pluginhelper.get_segment_absolute_time(float(item['start_time']))
                   
                    if start > (result['End'] + speech_delay_sec):
                        #append the prior result and start a new record
                        results.append(result)
                        result = {}
                        result['Start'] = start
                        result['End'] = mre_pluginhelper.get_segment_absolute_time(float(item['end_time']))
                        result['Label'] = 'speech present'
                        result['Transcription'] = item['alternatives'][0]['content']
                    else:
                        #extend the end with this next item
                        result['End'] = mre_pluginhelper.get_segment_absolute_time(float(item['end_time']))
                        result['Transcription'] = result['Transcription'] + ' ' + item['alternatives'][0]['content']

        if result:
            results.append(result)

    return results

def lambda_handler(event, context):

    print(event)

    results = []
    mre_dataplane = DataPlane(event)

    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)
    mre_pluginhelper = PluginHelper(event)

    try :

        # Download the HLS video segment from S3
        media_path = mre_dataplane.download_media()
        print('media_path=',media_path)

        # process chunk with ffmpeg using options provided
        silence_duration_sec = float(event['Plugin']['Configuration']['silence_duration_sec'])
        input_bucket_name = event['Plugin']['Configuration']['input_bucket_name']
        output_bucket_name = event['Plugin']['Configuration']['output_bucket_name']

        # Normally this plugin get processed by MRE with a map for the audio tracks present
        # However, there is a scenario where when added as a dependency to a video type segmenter plugin, it will not
        try:
            audio_track_num = event['TrackNumber']
        except KeyError:
            audio_track_num = event['Plugin']['Configuration']['TrackNumber']

        #convert video file to an audio file for the specified track
        audio_file = rip_audio_to_file(media_path, audio_track_num)
        object_name = prepare_s3_object_name(os.path.basename(audio_file))
        object_name = object_name + '-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

        #upload the file to S3
        upload_file(audio_file, input_bucket_name, object_name)

        #execute a transcription job
        #job_uri = "s3://DOC-EXAMPLE-BUCKET1/key-prefix/file.file-extension"
        media_file_uri = 's3://' + input_bucket_name + '/' + object_name

        transcribe_job_name = object_name

        response = transcribe_client.start_transcription_job(
            TranscriptionJobName=transcribe_job_name,
            LanguageCode='en-US',  #'en-US'|'es-US'|'en-AU'|'fr-CA'|'en-UK'
            MediaFormat='mp3', #|'mp4'|'wav'|'flac',
            Media={
                'MediaFileUri': media_file_uri
            },
            OutputBucketName=output_bucket_name
        )

        #pause for async process to complete
        time.sleep(3)

        #poll for completion
        transcribe_status = 'IN_PROGRESS'
        while transcribe_status == 'IN_PROGRESS':
            response = transcribe_client.get_transcription_job(
                TranscriptionJobName=transcribe_job_name
            )
            transcribe_status = response['TranscriptionJob']['TranscriptionJobStatus']
            time.sleep(5)

        #retrieve the results from s3
        results_file = object_name + '.json'
        s3_client.download_file(output_bucket_name, results_file, '/tmp/' + results_file)

        #process results
        results = consolidate_transcribe_results('/tmp/' + results_file, mre_pluginhelper, silence_duration_sec)
        print(results)

        # Add the results of the plugin to the payload (required if the plugin status is "complete"; Optional if the plugin has any errors)
        mre_outputhelper.add_results_to_output(results)

        # Persist plugin results for later use
        mre_dataplane.save_plugin_results(results)

        # Update the processing status of the plugin (required)
        mre_outputhelper.update_plugin_status(Status.PLUGIN_COMPLETE)

        # Returns expected payload built by MRE helper library
        return mre_outputhelper.get_output_object()

    except Exception as e:
        print(e)

        # Update the processing status of the plugin (required)
        mre_outputhelper.update_plugin_status(Status.PLUGIN_ERROR)

        # Re-raise the exception to MRE processing where it will be handled
        raise
