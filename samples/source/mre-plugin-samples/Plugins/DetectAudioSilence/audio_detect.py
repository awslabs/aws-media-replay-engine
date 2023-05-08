# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import ffmpeg
import re
from collections import namedtuple

silence_start_re = re.compile(r' silence_start: (?P<start>[0-9]+(\.?[0-9]*))')
silence_end_re = re.compile(r' silence_end: (?P<end>[0-9]+(\.?[0-9]*))')
silence_duration_re = re.compile(r' silence_duration: (?P<duration>[0-9]+(\.?[0-9]*))')

mean_volume_re = re.compile(r' mean_volume: (?P<mean>-?[0-9]+(\.?[0-9]*))')
max_volume_re = re.compile(r' max_volume: (?P<max>-?[0-9]+(\.?[0-9]*))')

# For more info on the silencedetect filter see https://www.ffmpeg.org/ffmpeg-filters.html#silencedetect
DEFAULT_THRESHOLD = '-50dB'    # silence threshold in dB
DEFAULT_DURATION = 2    # silence duration in seconds
DEFAULT_AUDIO_TRACK = 0

AudioProcessor = namedtuple('AudioProcessor', ['name', 'with_filter', 'output_processor'])

def with_silencedetect(stream, threshold=DEFAULT_THRESHOLD, duration=DEFAULT_DURATION, track=DEFAULT_AUDIO_TRACK, **kwargs):
    """Adds the ffmpeg silencedetect filter to detect silence in a stream"""
    #return ffmpeg.filter(stream[track], 'silencedetect', 'map="0:a:' + str(int(track)) + '"', n=threshold, d=duration)
    return ffmpeg.filter(stream[str(track)], 'silencedetect', n=threshold, d=duration)

def with_volumedetect(stream, **kwargs):
    """Adds the ffmpeg volumedetect"""
    return ffmpeg.filter(stream, 'volumedetect')

def with_astats(stream, track=DEFAULT_AUDIO_TRACK, **kwargs):
    """Adds the ffmpeg astats"""
    # ffmpeg -i sample.ts -af astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=log.txt -f null -
    return ffmpeg.filter(stream, 'astats', 'map 0:a:' + str(track), reset='1', ametadata='print', key='lavfi.astats.Overall.RMS_level')

def parse_volume_output(lines):
    """Parses the output of ffmpeg for volume data"""

    max_volume = None
    mean_volume = None

    for line in lines:
        max_result = max_volume_re.search(line)
        mean_result = mean_volume_re.search(line)

        if max_result:
            max_volume = float(max_result.group('max'))

        elif mean_result:
            mean_volume = float(mean_result.group('mean'))

    if max_volume and mean_volume:
        return mean_volume, max_volume


def parse_silence_output(lines):
    """Parses the output of ffmpeg for chunks of silence section denoted by a start, end tuples"""
    # [silencedetect @ 0x7f93407d4640] silence_start: 0.411417
    # [silencedetect @ 0x7f93407d4640] silence_end: 1.71752 | silence_duration: 1.3061

    chunk_starts = []
    chunk_ends = []

    for line in lines:
        silence_start = silence_start_re.search(line)
        silence_end = silence_end_re.search(line)

        if silence_start:
            chunk_starts.append(float(silence_start.group('start')))
        elif silence_end:
            chunk_ends.append(float(silence_end.group('end')))

    return list(zip(chunk_starts, chunk_ends))


#def execute_ffmpeg(input_file, p_threshold, p_duration, p_track, processors=None, **kwargs):
def execute_ffmpeg(input_file, processors=None, **kwargs):
    """
    Run ffmpeg with a set of audio processors to add filters to a call
    and process the results into a dict
    ffmpeg -i sample.ts -af silencedetect=n=-50dB:d=5 -map 0:a:0 -f null - 2> ffout
    """

    if processors is None:
        processors = [
            AudioProcessor('silencedetect', with_silencedetect, parse_silence_output),
        ]

    stream = ffmpeg.input(input_file)

    for with_filter in [ap.with_filter for ap in processors]:
        stream = with_filter(stream, **kwargs)

    ret_code, out = ffmpeg.output(stream, '-', format='null').run(quiet=True)

    if ret_code:
        raise RuntimeError

    output_lines = out.decode('utf-8').splitlines()

    return {ap.name: ap.output_processor(output_lines) for ap in processors}
