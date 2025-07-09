# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os
import cv2
import math
import base64
import json
import boto3
from botocore.config import Config

from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane
from MediaReplayEnginePluginHelper import ControlPlane

config = Config(retries={"max_attempts": 100, "mode": "standard"})
bedrock = boto3.client("bedrock-runtime", config=config)

BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID",
    "us.anthropic.claude-3-sonnet-20240229-v1:0",  # Use the cross-region inference profile as model id
)

MAX_NUM_FRAMES = 20

def lambda_handler(event, context):

    print(event)

    results = []
    mre_dataplane = DataPlane(event)
    mre_controlplane = ControlPlane()

    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)
    
    try:

        # Download the HLS video segment from S3
        media_path = mre_dataplane.download_media()

        # plugin params
        prompt = mre_controlplane.get_prompt_template(name="DescribeScenePrompt")
        print(json.dumps(prompt))

        # Frame rate for sampling
        p_fps = int(event["Profile"]["ProcessingFrameRate"]) #i.e. 5
        v_fps = int(event["Input"]["Metadata"]["HLSSegment"]["FrameRate"]) #i.e. 25
        frameRate = int(v_fps/p_fps)

        cap = cv2.VideoCapture(media_path)
        llm_messages = []
        frame_data = []
        startFrameId = None
        endFrameId = None
        while(cap.isOpened()):
            frameId = cap.get(1) #current frame number
            endFrameId = frameId
            if startFrameId is None:
                startFrameId = frameId
            ret, frame = cap.read()

            if (ret != True):
                break

            # skip frames to meet processing FPS requirement
            if (frameId % math.floor(frameRate) == 0):
                hasFrame, imageBytes = cv2.imencode(".jpg", frame)
                if(hasFrame):
                    # TODO Gather Image data
                    frame_data.append(
                        {
                            "identifying_text": {
                                "type": "text",
                                "text": f"Frame {frameId}:",
                            },
                            "image": {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": base64.b64encode(imageBytes).decode("utf-8"),
                                },
                            }
                        }
                    )
            
        
        # Naively sample frames to meet max number of frames requirement
        for frame_datum in frame_data[::max(round(len(frame_data)/MAX_NUM_FRAMES),1)][:MAX_NUM_FRAMES]:
            llm_messages.append(frame_datum["identifying_text"])
            llm_messages.append(frame_datum["image"])

        
        llm_messages.append(
            {
                "type": "text",
                "text": prompt["Template"],
            }
        )

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": llm_messages}],
        }

        response = bedrock.invoke_model(
            body=json.dumps(body),
            modelId=BEDROCK_MODEL_ID,
            accept="application/json",
            contentType="application/json",
        )
        output_binary = response["body"].read()
        output_json = json.loads(output_binary)


        elabel = {}
        elabel['Label'] = output_json['content'][0]['text']

        # Get timecode from frame
        elabel["Start"] = mre_dataplane.get_frame_timecode(startFrameId)
        elabel["End"] = mre_dataplane.get_frame_timecode(endFrameId)
        elabel["frameId"] = startFrameId
        results.append(elabel)

        print(f'results:{results}')

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
