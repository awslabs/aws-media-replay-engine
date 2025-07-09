# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import av
import io
import json
from botocore.config import Config

from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane
from MediaReplayEnginePluginHelper import ControlPlane

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

        sampling_seconds = int(event["Plugin"]["Configuration"]["sampling_seconds"])
        bedrock_model_id = get_bedrock_inference_profile_id(
            event["Plugin"]["Configuration"]["bedrock_model_id"]
        )
        prompt_template_name = event["Plugin"]["Configuration"]["prompt_template_name"]
        prompt_template = mre_controlplane.get_prompt_template(prompt_template_name)[
            "Template"
        ]
        print(prompt_template)

        chunk_start = event["Input"]["Metadata"]["HLSSegment"]["StartTime"]

        with av.open(media_path) as container:
            # Signal that we only want to look at keyframes.
            stream = container.streams.video[0]
            # get only keyframes
            stream.codec_context.skip_frame = "NONKEY"

            for frameId, frame in enumerate(container.decode(stream)):
                frame_start = mre_dataplane.get_frame_timecode(frameId)
                frame_start_absolute = frame_start - chunk_start

                # skip frames to meet processing FPS requirement
                # if frameId % math.floor(frameRate) == 0:
                if frame_start_absolute % sampling_seconds == 0:
                    buffIO = io.BytesIO()
                    frame.to_image().save(buffIO, format="JPEG")
                    imageBytes = buffIO.getvalue()

                    response = process_image(
                        bedrock_model_id, imageBytes, prompt_template
                    )

                    try:
                        # try to load the response as json
                        scene_labels = json.loads(response)
                    except json.JSONDecodeError:
                        print(f"Response is not a valid JSON: {response}")
                        # check if the response is cut off due to LLM maxTokens limit (which may happen due to token repetition)
                        if not response.endswith("}"):
                            print("Response is cut off by the LLM")
                            # try to salvage the response by manipulating the LLM output
                            response_list = response.split(",")
                            scene_labels = json.loads(
                                ",".join(response_list[:-1]) + "]}"
                            )

                    result = {}

                    # Get timecode from frame
                    result["Start"] = frame_start
                    result["End"] = result["Start"]
                    result["frameId"] = frameId
                    result["Label"] = "The image has been described"
                    result["Image_Summary"] = json.dumps(scene_labels["Labels"])
                    results.append(result)
                    print(result)

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
