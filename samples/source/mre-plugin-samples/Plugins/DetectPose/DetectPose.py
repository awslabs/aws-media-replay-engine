# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os
import boto3
import cv2
from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane

smrt_client = boto3.client('sagemaker-runtime')

def extract_feature_from_keypoints(keypoints, feature_list):
    feature = ''
    for idx in feature_list:
        #map feature keypoints x/y coordinates into string
        feature += ','.join(map(str,keypoints[idx]))
        feature +=','
    return feature[:-1]

def lambda_handler(event, context):
    print (event)
    dependplugin = event['Plugin']['DependentPlugins'][0]
    model_endpoint = str(event['Plugin']['ModelEndpoint'])
    minimum_confidence = float(event['Plugin']['Configuration']['minimum_confidence']) # 0.7
    feature_list = event['Plugin']['Configuration']['Keypoints_List'] # [0,5,6,9,10,11,12,15,16]
    results = []
    mre_dataplane = DataPlane(event)

    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)

    try:
        # plugin params

        #get all detector data since last start or end plus this current chunk
        jsonResults = mre_dataplane.get_dependent_plugins_output()
        # print(jsonResults)
        # return
        if len(jsonResults) < 1:
            print('No results from the Dependent plugin for this chunk')
            return

        # Download the HLS video segment from S3
        media_path = mre_dataplane.download_media()
        print('media_path=',media_path)
        # plugin params
        _, chunk_filename = head, tail = os.path.split(event['Input']['Media']["S3Key"])
        print('chunk_filename=',chunk_filename)
        # Frame rate for sampling
        p_fps = int(event["Profile"]["ProcessingFrameRate"])
        v_fps = int(event["Input"]["Metadata"]["HLSSegment"]["FrameRate"]) #25
        frameRate = int(v_fps/p_fps)
        cap = cv2.VideoCapture(media_path)
        # get total number of frames
        totalFrames = cap.get(cv2.CAP_PROP_FRAME_COUNT)

        for result in jsonResults[dependplugin]:
            sbFrame = result['frameId']
            sbKeypoints = result['keypoints']
            for res in sbKeypoints:
                #print(res)
                #res =[[conf],[x1,y1],...[xn,yn]]
                # Skip the first ele in the res list, which is the confidence value
                payload = extract_feature_from_keypoints(res[1:], feature_list)
                #print(payload)
                response = smrt_client.invoke_endpoint(EndpointName=model_endpoint,
                       ContentType='text/csv',
                       Body=payload)
                result = response['Body'].read().decode("utf-8")
                pose = int(result.split(',')[0])
                conf = float(result.split(',')[1]) if pose==1 else 1-float(result.split(',')[1])
                #print(sbFrame, pose,conf)
                if pose == 1 and conf > minimum_confidence:
                    elabel = {}
                    elabel["Start"] = mre_dataplane.get_frame_timecode(sbFrame)
                    elabel["End"] = elabel["Start"]
                    elabel["frameId"] = sbFrame
                    elabel['PoseDetection'] = True
                    elabel['poseConfidence'] = conf
                    elabel["Label"] = 'Pointing_Pose'
                    results.append(elabel)
                    # Only record once to avoid duplicate Start time
                    # For muliple recordings, modify payload to include a list
                    break 

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
