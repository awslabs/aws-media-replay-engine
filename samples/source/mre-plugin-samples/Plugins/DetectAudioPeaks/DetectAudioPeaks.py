# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import numpy as np
import wave 
import contextlib
from scipy.signal import hilbert, lfilter, butter
import ffmpeg
from ffmpeg import Error
import random
import string
import os

from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import PluginHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane

filter_lowcut = 4000
filter_highcut = 1000
sampleRate = 44000

def prepare_s3_object_name(file_name):
    object_name = file_name.replace(' ', '_')
    return object_name
    
def rip_audio_to_file(video_filename, track=1):
    print(video_filename)
    tmp_file = video_filename.split('.')[-2]
    tmp_file += '_track_' + str(track)
    tmp_file += '.wav'
    print('Temp wav file:',tmp_file)
    try:
        stream = ffmpeg.input(video_filename)
        out, err = (
            ffmpeg.output(stream[str(track)],tmp_file,format='wav',ar='44.1k')
            .run(capture_stdout=True, capture_stderr=True,overwrite_output=True)
        )
    except ffmpeg.Error as err:
        print(err.stderr)
        raise

    return tmp_file
    
# from http://stackoverflow.com/questions/2226853/interpreting-wav-data/2227174#2227174
def interpret_wav(raw_bytes, n_frames, n_channels, sample_width, interleaved = True):

    if sample_width == 1:
        dtype = np.uint8 # unsigned char
    elif sample_width == 2:
        dtype = np.int16 # signed 2-byte short
    else:
        raise ValueError("Only supports 8 and 16 bit audio formats.")

    channels = np.fromstring(raw_bytes, dtype=dtype)

    if interleaved:
        # channels are interleaved, i.e. sample N of channel M follows sample N of channel M-1 in raw data
        channels.shape = (n_frames, n_channels)
        channels = channels.T
    else:
        # channels are not interleaved. All samples from channel M occur before all samples from channel M-1
        channels.shape = (n_channels, n_frames)

    return channels

def butter_bandpass(filter_lowcut, filter_highcut, fs, order=5):
    nyq = 0.5 * fs
    low = filter_lowcut / nyq
    high = filter_highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a

def butter_bandpass_filter(data, filter_lowcut, filter_highcut, fs, order=5):
    b, a = butter_bandpass(filter_lowcut, filter_highcut, fs, order=order)
    y = lfilter(b, a, data)
    return y

def bandpass_filter(buffer):
    return butter_bandpass_filter(buffer, filter_lowcut, filter_highcut, sampleRate, order=6)
    
    
def lambda_handler(event, context):
    
    print(event)
    
    global filter_lowcut
    global filter_highcut
    global sampleRate
    
    results = []
    mre_dataplane = DataPlane(event)

    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)
    mre_pluginhelper = PluginHelper(event)

    try :

        # Download the HLS video segment from S3
        media_path = mre_dataplane.download_media()
        print('media_path=',media_path)
        
        bin_size_seconds = int(event['Plugin']['Configuration']['bin_size_seconds'])
        look_back_bin_cnt = int(event['Plugin']['Configuration']['look_back_bin_cnt'])
        num_stddevs_filter = int(event['Plugin']['Configuration']['num_stddevs_filter'])
        filter_lowcut = int(event['Plugin']['Configuration']['filter_lowcut'])
        filter_highcut = int(event['Plugin']['Configuration']['filter_highcut'])
    
        # Normally this plugin get processed by MRE with a map for the audio tracks present
        # However, there is a scenario where when added as a dependency to a video type segmenter plugin, it will not
        #if 'TrackNumber' in event:
        #    audio_track_num = event['TrackNumber']
        #else:
        audio_track_num = int(event['Plugin']['Configuration']['TrackNumber'])
        
        #convert video file to an audio file for the specified track
        audio_file = rip_audio_to_file(media_path, audio_track_num)
        object_name = prepare_s3_object_name(os.path.basename(audio_file))
        object_name = object_name + '-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        
        #outname = 'new-' + audio_file
        
        with contextlib.closing(wave.open(audio_file,'rb')) as spf:
            sampleRate = spf.getframerate()
            ampWidth = spf.getsampwidth()
            nChannels = spf.getnchannels()
            nFrames = spf.getnframes()
            
            # Extract Raw Audio from multi-channel Wav File
            signal = spf.readframes(nFrames*nChannels)
            spf.close()
            channels = interpret_wav(signal, nFrames, nChannels, ampWidth, True)
            original_audio = channels[audio_track_num]
        
        #apply bandpass filter
        filtered = np.apply_along_axis(bandpass_filter, 0, original_audio).astype('int16')

        #get the mod to know how much to trim the array before resizing it
        analytic_signal = hilbert(channels[audio_track_num])
        amplitude_envelope = np.abs(analytic_signal)
        
        #calculate the bin cnt
        clip_length_seconds = amplitude_envelope.size / sampleRate
        print(clip_length_seconds)
        
        bin_cnt = int(clip_length_seconds / bin_size_seconds)
        print(bin_cnt)
        
        #the last chunk may be very short, if so skip it
        if bin_cnt > 0:
            
            #get the mod to know how much to trim the array before resizing it    
            x = amplitude_envelope.size%bin_cnt
            
            #trim the end of the array to align with the new size per the bin_cnt specified above
            if x > 0:
                amplitude_envelope = amplitude_envelope[:-x]
            
            #bin the array into bin_cnt number of bins and calculate the mean for each bin
            bin_means = amplitude_envelope.reshape(bin_cnt, -1).mean(axis=1)
            
            #calculate rolling average
            rolling_avg = np.convolve(bin_means, np.ones(look_back_bin_cnt)/look_back_bin_cnt, mode='valid')
            
            #calculate aggregate statistics
            mean = np.mean(bin_means)
            stddev = np.std(rolling_avg) 
            threshold = mean + (num_stddevs_filter * stddev)
            
            #filter for the interesting stuff
            peak_array = np.argwhere(rolling_avg > threshold)
        
            #convert back to time base
            samples_per_bin = amplitude_envelope.size / bin_cnt
            peak_array_sec = peak_array * samples_per_bin / sampleRate
        
            if len(peak_array_sec) > 0:
                for item in peak_array_sec[0]:
                    print(item)
                    result = {}
                    result['Start'] = mre_pluginhelper.get_segment_absolute_time(float(item))
                    result['End'] = result['Start']
                    result['Label'] = 'Peak Audio Detected'
                    result['Peak Audio'] = True
                    results.append(result)
                    
        print(results)                
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
