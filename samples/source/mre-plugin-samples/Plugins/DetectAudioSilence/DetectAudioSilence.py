# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from audio_detect import execute_ffmpeg
from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import PluginHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane

def lambda_handler(event, context):

    print(event)

    """Download a transport stream file and process the audio to detect
    silence and the mean volume
    :param event:

    :param context: lambda context object
    :return: A dict with representations of silence chunks
    {
      "silence_chunks": [
        { "start": 1.33494, "end": 1.84523 },
        { "start": 3.52498, "end": 3.85456 }
      ]
    }
    """

    results = []
    mre_dataplane = DataPlane(event)

    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)
    mre_pluginhelper = PluginHelper(event)

    try:
        # Download the HLS video segment from S3
        media_path = mre_dataplane.download_media()

        # process chunk with ffmpeg using options provided
        silence_threshold_db = str(event['Plugin']['Configuration']['silence_threshold_db']) + 'dB'
        silence_duration_sec = event['Plugin']['Configuration']['silence_duration_sec']
        
        try:
          audio_track_num = event['TrackNumber']
        except KeyError:
          audio_track_num = 1

        raw_results = execute_ffmpeg(
            media_path,
            threshold=silence_threshold_db,
            duration=silence_duration_sec,
            track=audio_track_num
        )

        print(f'raw results:{raw_results}')

        # Loop through results and convert chunk time values to event time
        for seq in raw_results['silencedetect']:
            start = mre_pluginhelper.get_segment_absolute_time(seq[0])
            end = mre_pluginhelper.get_segment_absolute_time(seq[1])
            results.append({"Start": start, "End": end})

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
