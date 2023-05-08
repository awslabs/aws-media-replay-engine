# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os
import boto3
import cv2
import math
import numpy as np
from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane

rek_client = boto3.client('rekognition')

# define yellow color range
light_yellow = np.array([20,100,100])
dark_yellow = np.array([40,255,255])

def find_serving_player_yellow(img):
    imgHeight, _, _ = img.shape

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # Threshold the HSV image to get only yellow colors
    mask = cv2.inRange(hsv, light_yellow, dark_yellow)
    #server_y = np.average(np.where(mask>200)[0])
    #Average the y-coordin of the largest 10% of yellow pixels
    yellow_y = np.where(mask>200)[0]
    (n_yellow,) = yellow_y.shape
    server_y = np.average(yellow_y[-1*int(n_yellow/10):])
    server = 0 if server_y < imgHeight/2 else 1
    print(imgHeight, server_y, server)
    return server

def apply_brightness_contrast(input_img, gray = True, brightness = 0, contrast = 0, sharp = 9):
    if gray:
        buf = cv2.cvtColor(input_img, cv2.COLOR_BGR2GRAY)
    else:
        buf = input_img.copy()
        #cv2.imwrite('Woman_images/scorebox11_gray.jpg', grey_image)

    if brightness != 0:
        if brightness > 0:
            shadow = brightness
            highlight = 255
        else:
            shadow = 0
            highlight = 255 + brightness
        alpha_b = (highlight - shadow)/255
        gamma_b = shadow

        buf = cv2.addWeighted(buf, alpha_b, buf, 0, gamma_b)


    if contrast != 0:
        f = 131*(contrast + 127)/(127*(131-contrast))
        alpha_c = f
        gamma_c = 127*(1-f)

        buf = cv2.addWeighted(buf, alpha_c, buf, 0, gamma_c)

    if sharp != 0:
        kernel = np.array([[-1,-1,-1], [-1, sharp,-1], [-1,-1,-1]])
        buf = cv2.filter2D(buf, -1, kernel)

    return buf

def get_score_from_scorebox_rekog_word(scorebox, grey, bright, contrast, sharp):
    score_img = apply_brightness_contrast(scorebox, grey, bright, contrast, sharp)#True, 0, 0, 8)
    scoreBytes = cv2.imencode('.jpg', score_img)[1].tobytes()
    response = rek_client.detect_text(Image={'Bytes':scoreBytes})
    textDetections=response['TextDetections']

    Rows = [[],[]]
    for text in textDetections:
        if text['Type'] == 'WORD':
            #print('WORD',text['DetectedText'])
            bbox = text['Geometry']['BoundingBox']
            top = bbox['Top']
            right = bbox['Left']+bbox['Width']
            curr = [right, text['DetectedText']]

            rnum = 0
            if top > 0.5:
                rnum = +1
            #print(curr, rnum)
            if not Rows[rnum]:
                Rows[rnum].append(curr)
                continue

            for i, col in enumerate(Rows[rnum]):
                #print(i,'--->',col)
                if bbox['Left'] > col[0]:
                    continue
                else:
                    Rows[rnum].insert(i, curr)
                    break
            else:
                #print('Loop finishes')
                Rows[rnum].append(curr)
    Scores = [[col[1] for col in Rows[0]],[col[1] for col in Rows[1]]]
    return Scores


def lambda_handler(event, context):
    results = []
    mre_dataplane = DataPlane(event)
    print(event)

    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)
    try:

        # Download the HLS video segment from S3
        media_path = mre_dataplane.download_media()
        print('media_path=',media_path)

        # plugin params
        _, chunk_filename = head, tail = os.path.split(event['Input']['Media']["S3Key"])
        model_endpoint = str(event['Plugin']['ModelEndpoint'])
        minimum_confidence = float(event['Plugin']['Configuration']['minimum_confidence']) #60
        print('chunk_filename=',chunk_filename)

        # Frame rate for sampling
        p_fps = int(event["Profile"]["ProcessingFrameRate"]) #i.e. 5
        v_fps = int(event["Input"]["Metadata"]["HLSSegment"]["FrameRate"]) #i.e. 25
        frameRate = int(v_fps/p_fps)

        cap = cv2.VideoCapture(media_path)
        while(cap.isOpened()):
            frameId = cap.get(1) #current frame number
            ret, frame = cap.read()
            #print(type(frame),frame.shape)
            if (ret != True):
                break
            frame_height, frame_width, _ = frame.shape
            if (frameId % math.floor(frameRate) == 0):
                hasFrame, imageBytes = cv2.imencode(".jpg", frame)
                #print(frameId)
                if(hasFrame):
                    response = rek_client.detect_custom_labels(
                        Image={'Bytes': imageBytes.tobytes(),},
                        MinConfidence = minimum_confidence,
                        ProjectVersionArn = model_endpoint
                    )

                    label = None
                    if len(response['CustomLabels']) > 0:
                        #for label in response['CustomLabels']:
                        label = response['CustomLabels'][0]
                        bb = label['Geometry']['BoundingBox']
                        width = int(bb['Width']*frame_width)
                        height = int(bb['Height']*frame_height)
                        left = int(bb['Left']*frame_width)
                        top = int(bb['Top']*frame_height)

                    elabel = {}
                    # Get timecode from frame
                    elabel["Start"] = mre_dataplane.get_frame_timecode(frameId)
                    elabel["End"] = elabel["Start"]
                    elabel["frameId"] = frameId
                    elabel['Server'] = -1
                    elabel['Score'] = 'NA'
                    if(label and label['Confidence'] > float(minimum_confidence)):
                        elabel['sbConfidence'] = label['Confidence']
                        elabel['sbCoordinate'] = [left, top, left+width, top+height]

                        sbImage = frame[top:top+height,left:left+width]
                        score = get_score_from_scorebox_rekog_word(sbImage,True, 10, 64, 10)
                        if score:
                            #print('sbImage2=',np.sum(sbImage),left,top, left+width, top+height)
                            elabel['Server'] = find_serving_player_yellow(sbImage)
                            elabel['Score'] = score
                            elabel["Label"] = 'Scorebox'
                        else:
                            elabel["Label"] = 'Scorebox No Score'
                    else:
                        elabel['sbConfidence'] = 0
                        elabel['sbCoordinate'] = [0,0,0,0]
                        elabel["Label"] = 'No Scorebox'
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
