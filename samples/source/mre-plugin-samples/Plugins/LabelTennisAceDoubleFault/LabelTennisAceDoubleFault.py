# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import os
import boto3
from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane

s3 = boto3.client('s3')
sm_client = boto3.client('sagemaker-runtime')

def detect_ace_df_serve(segments, embedding_endpoint, classification_endpoint):
    results = []
    result = {}
    ep_name = embedding_endpoint #'ace-df-endpoint'
    ep_name_classifier = classification_endpoint #'ace-all-1-endpoint'

    result['Label'] = 'Ace = False;DoubleFault = False'
    for seg in segments:
        result['LabelCode'] = 'Not Attempted'
        result['Start'] = seg['Segment']['Start']
        result['End'] = seg['Segment']['End']

        clip_location = seg['Segment']['OriginalClipLocation']
        if '1' in clip_location.keys():
            clip_loc = clip_location['1'].split('/')
            print(clip_loc)
            bucket_name = clip_loc[2]
            object_name = '/'.join(clip_loc[3:])
            file_name = '/tmp/seg.mp4'
            print(bucket_name,object_name)
            s3.download_file(bucket_name, object_name, file_name)
            if os.path.isfile(file_name):
                print('Segment file downloaded')
            else:
                print('Segment not exsit')
                results.append(result)
                continue
            img = open(file_name, 'rb').read()
            response = sm_client.invoke_endpoint(
                EndpointName= embedding_endpoint,
                Body=img,
                ContentType='application/x-image')

            res = response["Body"].read().decode("utf-8")
            embedding = [str(pred) for pred in json.loads(res)[0]['prediction']]
            #print(type(embedding),type(embedding[0]),embedding[:3]) #List of string
            response = sm_client.invoke_endpoint(
                EndpointName= classification_endpoint,
                Body=','.join(embedding),
                ContentType='text/csv')
            res = response["Body"].read().decode("utf-8")
            ace_df = int(res.split(',')[0])
            conf = float(res.split(',')[1])
            print('ace_df and conf.=',ace_df, conf)
            if conf > 0.5:
                if ace_df == 1:
                    result['Ace'] = 'True'
                    result['Label'] = 'Ace = True;'
                if ace_df == 2:
                    result['DoubleFault'] = 'True'
                    result['Label'] += 'DoubleFault = True'
                if ace_df in [1,2]:
                    result['LabelCode'] += 'Ace/DF Detected;'
        results.append(result)

    return results

def lambda_handler(event, context):
    print (event)
    dependplugin = event['Plugin']['DependentPlugins'][0]
    results = []
    mre_dataplane = DataPlane(event)

    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)

    try:

        # plugin params
        embedding_endpoint = str(event['Plugin']['ModelEndpoint'][0])
        classification_endpoint = str(event['Plugin']['ModelEndpoint'][1])

        #get all detector data since last start or end plus this current chunk
        jsonResults = mre_dataplane.get_segment_state_for_labeling()
        print('jsonResults=',jsonResults)

        results = detect_ace_df_serve(jsonResults, embedding_endpoint, classification_endpoint)
        print('results=',results)

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
