# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os
import boto3
import cv2
import math
from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane

rek_client = boto3.client('rekognition')

def PointInRect(x, y, x1, y1, x2, y2) :
    if (x > x1 and x < x2 and
        y > y1 and y < y2) :
        return True
    else :
        return False

def lambda_handler(event, context):
    #dependplugin = event['Plugin']['DependentPlugins'][0]
    results = []
    mre_dataplane = DataPlane(event)

    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)


    try:
        # Download the HLS video segment from S3
        media_path = mre_dataplane.download_media()

        # plugin params
        _, chunk_filename = head, tail = os.path.split(event['Input']['Media']["S3Key"])

        # Frame rate for sampling
        p_fps = int(event["Profile"]["ProcessingFrameRate"])
        v_fps = int(event["Input"]["Metadata"]["HLSSegment"]["FrameRate"])
        frameRate = int(v_fps/p_fps)
        minimum_confidence = int(event['Plugin']["Configuration"]['minimum_confidence'])
        Scene_Classification = str(event['Plugin']['ModelEndpoint'])

        cap = cv2.VideoCapture(media_path)

        idx = 0
        while(cap.isOpened()):
            frameId = cap.get(1) #current frame number
            ret, frame = cap.read()

            if (ret != True):
                break

            if (frameId % math.floor(frameRate) == 0):
                imgHeight, imgWidth, _ = frame.shape
                vl = int(imgWidth * float(event['Plugin']['Configuration']['vl'])) #0.25
                vr = int(imgWidth * float(event['Plugin']['Configuration']['vr'])) #0.75
                vt = int(imgHeight * float(event['Plugin']['Configuration']['vt'])) #0.4
                vb = int(imgHeight * float(event['Plugin']['Configuration']['vb'])) #0.7
                hasFrame, imageBytes = cv2.imencode(".jpg", frame)

                # Get tennis_scene
                if(hasFrame):
                    #Call DetectCustomLabels
                    response = rek_client.detect_custom_labels(
                        Image={'Bytes': imageBytes.tobytes(),},
                        MinConfidence = minimum_confidence,
                        ProjectVersionArn = Scene_Classification
                    )
                    if len(response['CustomLabels']) > 0:
                        tennis_scene = response["CustomLabels"][0]['Name']

                elabel = {}
                elabel["Start"] = frameId
                elabel["End"] = frameId
                elabel["frameId"] = frameId
                elabel['Volley'] = '0'
                elabel['Confidence'] = '-1'
                elabel['Label'] = 'No Volley'
                if(hasFrame and tennis_scene == 'far'):
                    #Call DetectLabels
                    response = rek_client.detect_labels(
                        Image={
                            'Bytes': imageBytes.tobytes(),
                        },
                        MaxLabels=20,
                        MinConfidence=minimum_confidence
                    )
                    if len(response['Labels']) > 0:
                        for label in response['Labels']:
                            #print(label)
                            if label['Name'] == 'Person':
                                instances = label['Instances']
                                for instance in instances:
                                    box = instance['BoundingBox']
                                    left = int(imgWidth * box['Left'])
                                    top = int(imgHeight * box['Top'])
                                    width = int(imgWidth * box['Width'])
                                    height = int(imgHeight * box['Height'])
                                    # Coord-for the feet
                                    px = int(left+width/2)
                                    py = int(top+height)

                                    if PointInRect(px,py, vl,vt, vr, vb):
                                        #cv2.circle(imgw, (px, py),4,(0,0,255), 1)
                                        elabel["Start"] = mre_dataplane.get_frame_timecode(frameId)
                                        elabel["End"] = elabel["Start"]
                                        elabel["frameId"] = frameId
                                        elabel['Volley'] = '1'
                                        elabel['Label'] = 'Volley Detected'
                                        elabel['Confidence'] = '{:.2f}'.format(instance["Confidence"])
                                        print(elabel)
                                        break
                results.append(elabel)
                #print(elabel)

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
