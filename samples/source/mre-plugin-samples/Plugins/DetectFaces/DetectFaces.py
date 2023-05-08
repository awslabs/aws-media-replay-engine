# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os
import boto3
import math
import random
import cv2

from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import PluginHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane

rek_client = boto3.client('rekognition')
    
def consolidate_plugin_results(results, ids, separateThreshold):
    # The current results are a list of face appearances by faceID, by frame. So we may have a lot of items that are for the same face, 
    # but with different times, now we want to group by faceID and melt together the time stamps so the end result is a smaller list
    if len(results) < 1:
        return []
    
    results.sort(key=lambda res: res['Start'], reverse=False)
    consolidated_result = []

    # separate the reuslts by identification, add items to consolidated result and separate if time between is long enough
    for id in ids:
        start = 0
        lastId = None
        isolatedList = [i for i in results if i['Label'] == id]

        if len(isolatedList) < 1:
            continue
        
        for i in range(len(isolatedList)-1):
            res = isolatedList[i]
            nextRes = isolatedList[i+1] 
            if lastId == None: #first item
                start = res["Start"]
                lastId =  res["Label"]
                
            if nextRes["Start"] - res["End"] > separateThreshold: #new Id
                # close this item
                resItem = { 
                        "Label": res["Label"],
                        "Start": start+ round(random.uniform(0.0,0.5),4), # the dynamoDB table cannot have duplicate start times, but faces may appear at the same time. Using a small random number to break parity
                        "End": res["End"] + + round(random.uniform(0.0,0.5),4)
                    }
                consolidated_result.append(resItem)
                    
                # start new item
                start = res["Start"]
                lastId =  res["Label"]
        
        #close last item
        lastItem = isolatedList[-1:][0]
        lastResItem = { 
                        "Label": lastItem["Label"],
                        "Start": start + round(random.uniform(0.0,0.5),4),
                        "End": lastItem["End"] + round(random.uniform(0.0,0.5),4)
                    }

        print("item for "+ id + ": " + str(lastResItem))
        
    return consolidated_result

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

        _, chunk_filename = head, tail = os.path.split(event['Input']['Media']["S3Key"])

        # Frame rate for sampling
        p_fps = int(event["Profile"]["ProcessingFrameRate"]) #i.e. 5
        v_fps = int(event["Input"]["Metadata"]["HLSSegment"]["FrameRate"]) #i.e. 25
        frameRate = int(v_fps/p_fps)

        cap = cv2.VideoCapture(media_path)

        # get plugin config values
        faces_collection_id = event['Plugin']['Configuration']['faces_collection_id']
        max_faces = int(event['Plugin']['Configuration']['max_faces'])
        quality_filter = event['Plugin']['Configuration']['quality_filter']
        minimum_confidence = int(event['Plugin']['Configuration']['minimum_confidence'])
        separate_threshold = float(event['Plugin']['Configuration']['separate_threshold'])

        faceIds = set() #set of faces local to the entire segment
        
        while(cap.isOpened()):
            frameId = cap.get(1) #current frame number
            ret, frame = cap.read()
            
            
            if (ret != True):
                break
            
            # skip frames to meet processing FPS requirement
            if (frameId % math.floor(frameRate) == 0):
                hasFrame, imageBytes = cv2.imencode(".jpg", frame)
                if(hasFrame):
                    try: 
                        #https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/rekognition.html#Rekognition.Client.index_faces
                        #https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/rekognition.html#Rekognition.Client.search_faces_by_image
                        response = rek_client.search_faces_by_image(
                            CollectionId = faces_collection_id,
                            Image = {'Bytes': imageBytes.tobytes(),},
                            QualityFilter = quality_filter,
                            MaxFaces = max_faces,
                            FaceMatchThreshold = minimum_confidence 
                        )
                        
                        # For each frame we want to collect the highest scoring result for each person identified
                        response["FaceMatches"].sort(key=lambda match: match['Face']['Confidence'], reverse=True)
                        response["FaceMatches"] = list(filter(lambda match: match['Face']['Confidence'] > minimum_confidence, response["FaceMatches"]))
        
                        frameFaceIds = set() #set of faces local to the frame
                        
                        for match in response["FaceMatches"]:
                            if match['Face']["ExternalImageId"] not in frameFaceIds:
                                # The faces are already sorted by confidence so we know the first element for each ID will have the best result
                                # isolate each faceID match in the results
                                result = {}
                                matchAppearances = [i for i in response["FaceMatches"] if i['Face']["ExternalImageId"] == match['Face']["ExternalImageId"]]
                                result["Label"] = matchAppearances[0]["Face"]["ExternalImageId"]
                                result['Start'] = mre_pluginhelper.get_segment_absolute_time(frameId/v_fps)
                                result['End'] = mre_pluginhelper.get_segment_absolute_time(frameId/v_fps)
                                results.append(result)
                                
                                frameFaceIds.add(match['Face']["ExternalImageId"])
                                faceIds.add(match['Face']["ExternalImageId"])
                        
                        
                    except rek_client.exceptions.InvalidParameterException as e:
                        error = str(e)
                        if error == "An error occurred (InvalidParameterException) when calling the SearchFacesByImage operation: There are no faces in the image. Should be at least 1.":
                            continue
                        else:
                            print("Error occured: " + error)
                            raise Exception(error)


        results = consolidate_plugin_results(results, faceIds, separate_threshold)
        print("Results: " + str(results))

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
