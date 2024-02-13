# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os
import tempfile
import boto3
import ffmpeg
from ffmpeg import Error
import numpy as np
import audio2numpy as a2n
import matplotlib.pyplot as plt
from numpy.fft import fft, fftfreq

from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane


runtime_client = boto3.client('sagemaker-runtime')

def extract_audio(filename, track=1):
    tmp_dir = tempfile.mkdtemp(dir='/tmp')
    tmp_file = os.path.join(tmp_dir, filename.split('.')[-2][-3:])
    tmp_file += '_tmp.mp3'
    print('Temp MP3 file:',tmp_file)
    try:
        stream = ffmpeg.input(filename)
        out, err = (
            ffmpeg.output(stream[str(track)],tmp_file,format='mp3',ar='16000')
            .run(capture_stdout=True, capture_stderr=True,overwrite_output=True)
        )
    except ffmpeg.Error as err:
        print(err.stderr)
        raise

    x,sr = a2n.audio_from_file(tmp_file)
    x1 = [x2[0] for x2 in x]
    return np.array(x1), sr

def fft_power_output(audio_t, sr, beg, end, low_cut,high_cut,plot_f=False):
    # Number of sample points
    x = audio_t[beg:end]
    N = len(x)
    # sample spacing
    T = 1.0 / sr
    if plot_f:
        plt.figure()
        plt.title('Audio Signal in Time Domain')
        plt.plot(x)
        plt.ylim(-0.5,0.5)

    yf = fft(x)
    xf = fftfreq(N, T)[:N//2]
    y_fft = np.abs(yf[0:N//2])
    if plot_f:
        plt.figure()
        plt.title('Audio Signal in Freq Domain')
        plt.plot(xf, 2.0/N * y_fft)
        #plt.ylim(0,0.0012)
        plt.grid()
    lc = int(low_cut*N//2)
    hc = int(-1*high_cut*N//2)
    #print(N,low_cut,lc,hc,len(y_fft))
    return np.sum(y_fft[:lc]), np.sum(y_fft[hc:])


def feature_extraction(media_path, track=1, wsize=5, low_cut=0.1,high_cut=0.1,plot_f=False):
    # read in audio file by ffmpeg and convert to 16bit codec
    x_ffmpeg, sr = extract_audio(media_path, track)
    if plot_f:
        plt.title('Over all Audio Signal in Time Domain')
        plt.plot(x_ffmpeg)
        plt.ylim(-0.5,0.5)

    nsamples = len(x_ffmpeg)
    print(f'Sample rate of the radio is {sr}, total samples {nsamples}')
    nw = nsamples//(sr*wsize)
    print(f'Total length is {nsamples/sr}s with window size {wsize}s. Num of windows is {nw+1}')
    features=[]
    for i in range(nw):
        beg = i*sr*wsize
        end = (i+1)*sr*wsize
        print(f'Get FFT features from sample {beg} to {end}')
        low, high = fft_power_output(x_ffmpeg, sr, beg, end, low_cut, high_cut, plot_f)
        features.append([i*wsize, (i+1)*wsize, low,high])

    beg = nw*sr*wsize
    if (nsamples-beg)/(sr*wsize) > 0.3:
        print(f'Get FFT features from sample {beg} to {nsamples}')
        low, high = fft_power_output(x_ffmpeg, sr, beg, nsamples, low_cut, high_cut, plot_f)
        end = nw*wsize + (nsamples-beg)/sr
        features.append([nw*wsize, end, low,high])
    else:
        print(f'Skip last {nsamples-beg} samples, {(nsamples-beg)/sr} sec, from {beg} to {nsamples}')
    return features

def code2label(code):
    if code == 0:
        return 'Quiet'
    elif code == 1:
        return 'Tennis Ball Hit'
    elif code == 2:
        return 'Commentators'
    elif code == 3:
        return 'Crowd Noise'
    else:
        return '?'

def lambda_handler(event, context):
    #print(boto3.__version__)
    #return
    results = []
    mre_dataplane = DataPlane(event)

    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)

    # Audio scene codes
    # 1 is quiet. 2 is tennis shot 3 is commentary 4 is crowd noise

    try :

        # Download the HLS video segment from S3
        media_path = mre_dataplane.download_media()
        print('media_path=',media_path)
        model_endpoint = str(event['Plugin']['ModelEndpoint'])

        # if TrackNumber is present in the event
        # track = int(event['TrackNumber']) #2
        
        track = int(event['Plugin']['Configuration']['TrackNumber'])  #2
        wl = int(event['Plugin']['Configuration']['TimeWindowLength']) #5
        lc = float(event['Plugin']['Configuration']['LowCut']) #0.1
        hc = float(event['Plugin']['Configuration']['HighCut']) #0.2
        features = feature_extraction(media_path, track, wl, lc, hc, False)
        print(features)

        for feature in features:
            audio_payload = {}
            audio_payload['AudioScene'] = -1
            audio_payload['Conf'] = 0
            audio_payload['Label'] = 'NONE'
            s_f = [str(s) for s in feature]
            #Take the last 2 items from the feature, as low and high freq. component
            payload = ','.join(s_f[2:])
            print('payload=',payload)
            response = runtime_client.invoke_endpoint(EndpointName=model_endpoint,
                                           ContentType='text/csv',
                                           Body=payload)
            result = response['Body'].read().decode("utf-8")
            scene = int(result.split(',')[0])
            conf = float(result.split(',')[1])
            print(scene,conf)
            start = mre_dataplane.get_frame_timecode(0)
            audio_payload['Start'] = start + feature[0]
            audio_payload['End'] = start + feature[1]
            audio_payload['AudioScene'] = scene
            audio_payload['Conf'] = conf
            audio_payload['Label'] = code2label(scene)
            print(audio_payload)
            results.append(audio_payload)

        print('Results=',results)
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
