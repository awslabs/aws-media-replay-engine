# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import os
import tempfile
import boto3
from botocore.exceptions import ClientError
import time
import ffmpeg
import random
import string
import base64

from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import PluginHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane
from MediaReplayEnginePluginHelper import ControlPlane

s3_client = boto3.client("s3")
transcribe_client = boto3.client("transcribe")
sagemaker_runtime_client = boto3.client("sagemaker-runtime")


def prepare_s3_object_name(file_name):
    object_name = file_name.replace(" ", "_")
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
        s3_client.upload_file(file_name, bucket, object_name)

    except ClientError as e:
        print(e)
        return False
    return True


def clip_voices_and_upload(
    file_name,
    local_transcription_file,
    base_filename,
    use_voice_model,
    voice_model_ep,
    training_bucket,
    upload_enabled,
    mre_program,
    mre_event,
):
    track_num = 0
    a_speaker_list = {}
    with open(local_transcription_file, encoding="utf8", errors="ignore") as f:
        raw_results = json.load(f)

        # check if there are any speaker labels available
        if raw_results["results"]["speaker_labels"] is not None:
            # Loop through results and convert chunk time values to event time
            for voice in raw_results["results"]["speaker_labels"]["segments"]:
                print(voice)
                a_length = float(voice["end_time"]) - float(voice["start_time"])
                a_speaker_label = voice["speaker_label"]

                tmp_file = base_filename.split(".")[-2]
                tmp_file = (
                    tmp_file
                    + "-"
                    + str(voice["start_time"])
                    + "-"
                    + a_speaker_label
                    + ".wav"
                )
                print(tmp_file)

                try:
                    stream = ffmpeg.input(file_name, ss=float(voice["start_time"]))
                    out, err = ffmpeg.output(
                        stream[str(track_num)],
                        "/tmp/" + tmp_file,
                        t=a_length,
                        format="wav",
                        ar="16000",
                    ).run(
                        capture_stdout=True, capture_stderr=True, overwrite_output=True
                    )

                    # determine who the voice is
                    if use_voice_model:
                        with open("/tmp/" + tmp_file, "rb") as audio_file:
                            payload = base64.b64encode(audio_file.read()).decode(
                                "utf-8"
                            )
                            response = (
                                sagemaker_runtime_client.invoke_endpoint(
                                    EndpointName=voice_model_ep,
                                    Body=payload,
                                    ContentType="audio/wav",
                                    Accept="application/json",
                                )["Body"]
                                .read()
                                .decode("utf-8")
                            )

                        # map the speaker placeholder with a real name from the model
                        a_speaker_list[a_speaker_label] = response.replace('"', "")

                    # copy to s3 for training dataset
                    if upload_enabled:
                        object_name = (
                            mre_program
                            + "/"
                            + mre_event
                            + "/"
                            + a_speaker_label
                            + "/"
                            + tmp_file
                        )
                        object_name = object_name.replace(" ", "-")
                        upload_file("/tmp/" + tmp_file, training_bucket, object_name)

                except ffmpeg.Error as err:
                    print(err.stderr)
                    raise

    return a_speaker_list


def get_speaker(a_speaker_list, a_speaker_label):
    speaker = ""
    if a_speaker_label in a_speaker_list:
        # spk_0, spk_1, etc
        speaker = a_speaker_list[a_speaker_label]
    else:
        # not found
        speaker = ""

    return speaker


def rip_audio_to_file(video_filename, track=1):
    print(video_filename)
    tmp_file = video_filename.split(".")[-2]
    tmp_file += "_track_" + str(track)
    tmp_file += ".wav"
    print("Temp WAV file:", tmp_file)
    try:
        stream = ffmpeg.input(video_filename)
        out, err = ffmpeg.output(
            stream[str(track)], tmp_file, format="wav", ar="16000"
        ).run(capture_stdout=True, capture_stderr=True, overwrite_output=True)
    except ffmpeg.Error as err:
        print(err.stderr)
        raise

    return tmp_file


def consolidate_transcribe_results(
    raw_results_file, mre_pluginhelper, a_speaker_list, speech_delay_sec=2
):
    results = []
    result = {}

    with open(raw_results_file, encoding="utf8", errors="ignore") as f:
        raw_results = json.load(f)

        # Loop through results and convert chunk time values to event time
        for item in raw_results["results"]["items"]:
            # print(item)
            # not all results have a start and end time
            if item["type"] == "pronunciation":
                if "Start" not in result:
                    result = {}
                    result["Start"] = mre_pluginhelper.get_segment_absolute_time(
                        float(item["start_time"])
                    )
                    result["End"] = mre_pluginhelper.get_segment_absolute_time(
                        float(item["end_time"])
                    )
                    result["Transcription"] = item["alternatives"][0]["content"]
                    result["Speaker"] = get_speaker(
                        a_speaker_list, item["speaker_label"]
                    )
                    result["Label"] = "Speech Present: " + result["Speaker"]

                else:
                    # check if the start is > the delay relative to the last item
                    start = mre_pluginhelper.get_segment_absolute_time(
                        float(item["start_time"])
                    )

                    if start > (result["End"] + speech_delay_sec):
                        # append the prior result and start a new record
                        results.append(result)
                        result = {}
                        result["Start"] = start
                        result["End"] = mre_pluginhelper.get_segment_absolute_time(
                            float(item["end_time"])
                        )
                        result["Transcription"] = item["alternatives"][0]["content"]
                        result["Speaker"] = get_speaker(
                            a_speaker_list, item["speaker_label"]
                        )
                        result["Label"] = "Speech Present: " + result["Speaker"]
                    else:
                        # extend the end with this next item
                        result["End"] = mre_pluginhelper.get_segment_absolute_time(
                            float(item["end_time"])
                        )
                        result["Transcription"] = (
                            result["Transcription"]
                            + " "
                            + item["alternatives"][0]["content"]
                        )

            elif item["type"] == "punctuation":
                if "alternatives" in item:
                    result["Transcription"] = (
                        result["Transcription"]
                        + item["alternatives"][0]["content"]
                        + " "
                    )

        if result:
            results.append(result)

    return results


def lambda_handler(event, context):

    print(event)

    results = []
    mre_dataplane = DataPlane(event)
    mre_controlplane = ControlPlane(event)

    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)
    mre_pluginhelper = PluginHelper(event)

    mre_program = event["Event"]["Program"]
    mre_event = event["Event"]["Name"]

    try:

        # Download the HLS video segment from S3
        media_path = mre_dataplane.download_media()
        print("media_path=", media_path)

        # process chunk with ffmpeg using options provided
        silence_duration_sec = float(
            event["Plugin"]["Configuration"]["silence_duration_sec"]
        )
        input_bucket_name = event["Plugin"]["Configuration"]["input_bucket_name"]
        output_bucket_name = event["Plugin"]["Configuration"]["output_bucket_name"]
        show_speaker_labels = event["Plugin"]["Configuration"]["show_speaker_labels"]
        max_speaker_labels = int(event["Plugin"]["Configuration"]["max_speaker_labels"])
        training_bucket_name = event["Plugin"]["Configuration"]["training_bucket_name"]
        training_upload_enabled = (
            True
            if event["Plugin"]["Configuration"]["training_upload_enabled"] == "True"
            else False
        )
        speaker_inference_enabled = (
            True
            if event["Plugin"]["Configuration"]["speaker_inference_enabled"] == "True"
            else False
        )
        voice_model_ep = str(event["Plugin"]["ModelEndpoint"])

        # get event level context variables
        context_vars = mre_controlplane.get_event_context_variables()
        print(context_vars)
        if "transcribe_lang_code" in context_vars:
            transcribe_lang_code = context_vars["transcribe_lang_code"]
        else:
            transcribe_lang_code = (
                event["Plugin"]["Configuration"]["transcribe_lang_code"]
                if "transcribe_lang_code" in event["Plugin"]["Configuration"]
                else "en-US"
            )

        if "transcribe_identify_lang" in context_vars:
            transcribe_identify_lang = (
                True if context_vars["transcribe_identify_lang"] == "True" else False
            )
        else:
            transcribe_identify_lang = (
                True
                if event["Plugin"]["Configuration"]["transcribe_identify_lang"]
                == "True"
                else False
            )

        if show_speaker_labels == "True":
            show_speaker_labels = True
        else:
            show_speaker_labels = False

        # Normally this plugin get processed by MRE with a map for the audio tracks present
        # However, there is a scenario where when added as a dependency to a video type segmenter plugin, it will not
        try:
            audio_track_num = event["TrackNumber"]
        except KeyError:
            audio_track_num = event["Plugin"]["Configuration"]["TrackNumber"]

        # convert video file to an audio file for the specified track
        audio_file = rip_audio_to_file(media_path, audio_track_num)
        object_name = prepare_s3_object_name(os.path.basename(audio_file))
        object_name = (
            object_name
            + "-"
            + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
        )

        # upload the file to S3
        upload_file(audio_file, input_bucket_name, object_name)

        # execute a transcription job
        # job_uri = "s3://DOC-EXAMPLE-BUCKET1/key-prefix/file.file-extension"
        media_file_uri = "s3://" + input_bucket_name + "/" + object_name

        transcribe_job_name = object_name

        # auto detect language
        if transcribe_identify_lang:
            response = transcribe_client.start_transcription_job(
                TranscriptionJobName=transcribe_job_name,
                IdentifyLanguage=transcribe_identify_lang,
                Settings={
                    "ShowSpeakerLabels": show_speaker_labels,
                    "MaxSpeakerLabels": max_speaker_labels,
                },
                MediaFormat="wav",
                Media={"MediaFileUri": media_file_uri},
                OutputBucketName=output_bucket_name,
            )

        else:
            response = transcribe_client.start_transcription_job(
                TranscriptionJobName=transcribe_job_name,
                LanguageCode=transcribe_lang_code,
                Settings={
                    "ShowSpeakerLabels": show_speaker_labels,
                    "MaxSpeakerLabels": max_speaker_labels,
                },
                MediaFormat="wav",
                Media={"MediaFileUri": media_file_uri},
                OutputBucketName=output_bucket_name,
            )

        # pause for async process to complete
        time.sleep(3)

        # poll for completion
        transcribe_status = "IN_PROGRESS"
        while transcribe_status == "IN_PROGRESS":
            response = transcribe_client.get_transcription_job(
                TranscriptionJobName=transcribe_job_name
            )
            transcribe_status = response["TranscriptionJob"]["TranscriptionJobStatus"]
            time.sleep(5)

        # retrieve the results from s3
        results_file = object_name + ".json"
        tmp_dir = tempfile.mkdtemp(dir="/tmp")
        local_transcription_file = os.path.join(tmp_dir, results_file)
        s3_client.download_file(
            output_bucket_name, results_file, local_transcription_file
        )

        # split audio by voice and upload to s3
        speaker_list = clip_voices_and_upload(
            audio_file,
            local_transcription_file,
            object_name,
            speaker_inference_enabled,
            voice_model_ep,
            training_bucket_name,
            training_upload_enabled,
            mre_program,
            mre_event,
        )

        # process results
        results = consolidate_transcribe_results(
            local_transcription_file,
            mre_pluginhelper,
            speaker_list,
            silence_duration_sec,
        )
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
