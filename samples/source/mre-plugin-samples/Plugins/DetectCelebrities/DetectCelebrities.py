# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import av
import io
import math
import ast
import json
from botocore.config import Config

from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane
from MediaReplayEnginePluginHelper import ControlPlane

rek_client = boto3.client("rekognition")
config = Config(retries={"max_attempts": 20, "mode": "standard"})
brt = boto3.client("bedrock-runtime", config=config)
bedrock_client = boto3.client("bedrock")


def process_image(model, a_image, a_prompt):
    # Prepare the message with image and text
    message = {
        "role": "user",
        "content": [
            {
                "image": {
                    "format": "jpeg",
                    "source": {"bytes": a_image},  # Use raw image bytes
                }
            },
            {"text": a_prompt},
        ],
    }

    # Set up inference configuration
    inference_config = {"maxTokens": 2048}

    # Call the Converse API
    response = brt.converse(
        modelId=model, messages=[message], inferenceConfig=inference_config
    )

    # Extract the response text
    output_message = response["output"]["message"]
    return output_message["content"][0]["text"]


# check if a specific celebrity is in a search list that is desired to be flagged
def check_celeb(celeb_name, search_list):
    list_position = [idx for idx, s in enumerate(search_list) if celeb_name in s]
    if len(list_position) > 0:
        return "flag_celebrity" + str(list_position[0])
    else:
        return ""


def get_bedrock_inference_profile_id(model_id):
    # Check if a cross-region inference profile id could be used instead of the given model_id
    # If not, then return the given model_id
    response = bedrock_client.list_inference_profiles(typeEquals="SYSTEM_DEFINED")
    profile_summaries = response["inferenceProfileSummaries"]

    while "nextToken" in response:
        response = bedrock_client.list_inference_profiles(
            typeEquals="SYSTEM_DEFINED", nextToken=response["nextToken"]
        )
        profile_summaries.extend(response["inferenceProfileSummaries"])

    for profile in profile_summaries:
        if (
            profile["inferenceProfileId"].endswith(model_id)
            and profile["status"] == "ACTIVE"
        ):
            print(f"Found inference profile: {profile['inferenceProfileId']}")
            return profile["inferenceProfileId"]

    return model_id


def lambda_handler(event, context):
    print(event)

    results = []
    mre_controlplane = ControlPlane(event)
    mre_dataplane = DataPlane(event)
    mre_outputhelper = OutputHelper(event)

    try:
        # Download the HLS video segment from S3
        media_path = mre_dataplane.download_media()

        # plugin config
        minimum_confidence = int(event["Plugin"]["Configuration"]["minimum_confidence"])
        celebrity_list = ast.literal_eval(
            event["Plugin"]["Configuration"]["celebrity_list"]
        )
        mode = event["Plugin"]["Configuration"]["mode"]
        bedrock_model_id = (
            get_bedrock_inference_profile_id(
                event["Plugin"]["Configuration"]["bedrock_model_id"]
            )
            if mode == "LLM"
            else None
        )
        prompt_template_name = (
            event["Plugin"]["Configuration"]["prompt_template_name"]
            if mode == "LLM"
            else None
        )
        prompt_template = (
            mre_controlplane.get_prompt_template(prompt_template_name)["Template"]
            if mode == "LLM"
            else None
        )

        # Frame rate for sampling
        p_fps = int(event["Profile"]["ProcessingFrameRate"])  # i.e. 5
        v_fps = int(event["Input"]["Metadata"]["HLSSegment"]["FrameRate"])  # i.e. 25
        frameRate = int(v_fps / p_fps)

        # loop through frames in video chunk file
        with av.open(media_path) as container:
            # Signal that we only want to look at keyframes.
            stream = container.streams.video[0]
            # get only keyframes
            stream.codec_context.skip_frame = "NONKEY"

            for frameId, frame in enumerate(container.decode(stream)):
                frame_start = mre_dataplane.get_frame_timecode(frameId)
                print(f"start: {frame_start}")

                # process frame every 1 second
                if frameId % math.floor(frameRate) == 0:
                    buffIO = io.BytesIO()
                    frame.to_image().save(buffIO, format="JPEG")
                    imageBytes = buffIO.getvalue()

                    if mode == "LLM":
                        print(prompt_template)
                        response = process_image(
                            bedrock_model_id, imageBytes, prompt_template
                        )
                        result = {}
                        a_celeb_list = []
                        label = ""
                        print(response)
                        celebs = json.loads(response)

                        for celeb in celebs["Celebrities"]:
                            label += celeb + ", "
                            a_celeb_list.append(celeb)
                            out_attribute = check_celeb(celeb, celebrity_list)
                            if out_attribute != "":
                                result[out_attribute] = True

                        # Get timecode from frame
                        result["Start"] = mre_dataplane.get_frame_timecode(frameId)
                        result["End"] = result["Start"]
                        result["frameId"] = frameId
                        result["Label"] = label
                        result["Celebrities_List"] = json.dumps(a_celeb_list)
                        results.append(result)

                    else:
                        # print(f'working on frame {frameId}')
                        response = rek_client.recognize_celebrities(
                            Image={"Bytes": imageBytes}
                        )

                        result = {}
                        a_celeb_list = []
                        if len(response["CelebrityFaces"]) > 0:
                            label = ""
                            for celeb in response["CelebrityFaces"]:
                                if celeb["MatchConfidence"] > minimum_confidence:
                                    label += celeb["Name"] + ", "
                                    a_celeb_list.append(celeb["Name"])
                                    out_attribute = check_celeb(
                                        celeb["Name"], celebrity_list
                                    )
                                    if out_attribute != "":
                                        result[out_attribute] = True

                            # Get timecode from frame
                            result["Start"] = mre_dataplane.get_frame_timecode(frameId)
                            result["End"] = result["Start"]
                            result["frameId"] = frameId
                            result["Label"] = label
                            result["Celebrities_List"] = json.dumps(a_celeb_list)
                            results.append(result)

        print(f"results:{results}")

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
