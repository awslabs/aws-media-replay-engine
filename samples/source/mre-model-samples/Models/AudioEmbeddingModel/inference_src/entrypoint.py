# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# import packages ##
import os
import base64
import json
import mxnet as mx
import ffmpeg
import numpy as np
import audio2numpy as a2n
import openl3
import tempfile
from os.path import isfile, join, getsize
#import boto3, botocore

import gluoncv as gcv

def model_fn(model_dir):
    """
    Load the pretrained model 
    
    Args:
        model_dir (str): directory where model artifacts are saved/loaded
    """
    print('Ready to load model from '+model_dir)
 
    #You have to override this function
    #Otherwise the default model_fn can't find the model
    return 0,0

## SageMaker loading function ##
def transform_fn(net, data, input_content_type, output_content_type):
    # temporary directory to store files
    tmpdir = tempfile.mkdtemp(dir='/tmp')
    v_output = os.path.join(tmpdir, 'test.mp3')

    ## retrive model and contxt from the first parameter, net
    model, ctx = net
    
    ## decode image ##
    # for endpoint API calls
    print(type(data))
    if type(data) == str:
        parsed = json.loads(data)
        img = mx.nd.array(parsed)
    # for batch transform jobs
    else:
        with open(v_output,'wb') as writer:
            writer.write(data)
    print('file saved',isfile(v_output))
    
    x,sr = a2n.open_audio(v_output)
    nwin = int(len(x)/sr)
    x_input = []
    for i in range(nwin):
        win = x[i*sr:(i+1)*sr,0]
        if max(win) > 0.1:
            x_input.extend(win)
    if not x_input:
        print('Empety file, skip',v_output)
        return [{'prediction':''}]
    print(nwin,len(x_input))
    emb, ts = openl3.get_audio_embedding(np.array(x_input), sr, content_type="env", center=False,
                input_repr="linear", embedding_size=512, hop_size=1)
    aver_emb = np.average(emb,axis=0)
    #label_emb = np.append(file[0],aver_emb)
    result = np.append(aver_emb,nwin)
    print(result)
    # normalization values taken from gluoncv
    predictions = {'prediction':result.tolist()}
    predictionslist = [predictions]
    
    return predictionslist
