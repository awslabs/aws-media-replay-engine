# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import os
import boto3
import cv2
import math
from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane

smrt_client = boto3.client('sagemaker-runtime')

def lambda_handler(event, context):
    results = []
    mre_dataplane = DataPlane(event)

    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)
    try:

        # Download the HLS video segment from S3
        media_path = mre_dataplane.download_media()
        print('media_path=',media_path)

        # plugin params
        _, chunk_filename = head, tail = os.path.split(event['Input']['Media']["S3Key"])
        model_endpoint = str(event['Plugin']['ModelEndpoint'])
        minimum_confidence = float(event['Plugin']['Configuration']['minimum_confidence']) #.6
        print('chunk_filename=',chunk_filename)

        # Frame rate for sampling
        p_fps = int(event["Profile"]["ProcessingFrameRate"]) #1
        v_fps = int(event["Input"]["Metadata"]["HLSSegment"]["FrameRate"]) #25
        frameRate = int(v_fps/p_fps)
        frameRate = 25

        cap = cv2.VideoCapture(media_path)
        while(cap.isOpened()):
            frameId = cap.get(1) #current frame number
            ret, frame = cap.read()
            #print(type(frame),frame.shape)
            if (ret != True):
                break

            if (frameId % math.floor(frameRate) == 0):
                hasFrame, imageBytes = cv2.imencode(".jpg", frame)

                if(hasFrame):
                    #Call SageMaker
                    response = smrt_client.invoke_endpoint(
                        EndpointName=model_endpoint,
                        Body=imageBytes.tobytes(),
                        ContentType='application/x-image'
                    )
                    result = response["Body"].read().decode("utf-8")
                    # prediction is a JSON string. Load it into a Python object.
                    result = json.loads(result) # result=[{'prediction':[...]}]
                    res_list = result[0]['prediction'] # res_list=[[[conf],[x1,y1],...],[...]]
                    #print(result)
                    #print(res_list[0][0][0],type(res_list[0][0][0]),type(minimum_confidence))
                    save_list = [ppl for ppl in res_list if ppl[0][0] > minimum_confidence ]
                    #print('save_list len is',len(save_list),save_list)
                    if len(save_list) >0:
                        elabel = {}
                        # Get timecode from frame
                        elabel["Start"] = mre_dataplane.get_frame_timecode(frameId)
                        elabel["End"] = elabel["Start"]
                        elabel["frameId"] = frameId
                        elabel['keypoints'] = save_list
                        elabel["Label"] = 'Human'
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
