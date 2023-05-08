# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import ffmpeg
import re
from collections import namedtuple

scene_end_re = re.compile(r' pts_time:(?P<end>[0-9]+(\.?[0-9]*))')
clip_duration_re = re.compile(r' Duration: (([0-1][0-9])|([2][0-3])):(?P<dur_min>[0-5][0-9]):(?P<dur_sec>[0-5][0-9].[0-9]*)')  #Duration: 00:00:21.60, start: 164.300000, bitrate: 6667 kb/s

# For more info on the silencedetect filter see https://www.ffmpeg.org/ffmpeg-filters.html#silencedetect
DEFAULT_THRESHOLD = 0.4    # scene change threshold between 0.3 and 0.5

VideoProcessor = namedtuple('VideoProcessor', ['name', 'with_filter', 'output_processor'])

def with_select(stream, threshold=DEFAULT_THRESHOLD, **kwargs):
    """Adds the ffmpeg select
        filter:v "select='gt(scene,0.4)',showinfo"
    """
    return ffmpeg.filter(stream, 'select', 'gt(scene,' + str(threshold) +')')


def with_showinfo(stream, **kwargs):
    """Adds the ffmpeg showinfo"""
    return ffmpeg.filter(stream, 'showinfo')

def parse_video_output(lines):
    """Parses the output of ffmpeg for chunks of scene section denoted by a start, end tuples"""
    # [Parsed_showinfo_1 @ 0x7ffdfc804340] n:   0 pts: 352800 pts_time:3.92    pos:   796299 fmt:yuv420p sar:540/539 s:1280x720 i:P iskey:1 type:I checksum:9463B263 plane_checksum:[FF662CF3 DF539F0F 15FCE652] mean:[165 129 132 ] stdev:[54.4 5.9 9.0 ]
    # [Parsed_showinfo_1 @ 0x7ffdfc804340] color_range:tv color_space:bt709 color_primaries:bt709 color_trc:bt709

    chunk_starts = []
    chunk_ends = []

    scene_start = '0'
    scene_length = None
    for line in lines:

        scene_end = scene_end_re.search(line)
        if scene_end:
            chunk_starts.append(float(scene_start))
            chunk_ends.append(float(scene_end.group('end')))
            scene_start = scene_end.group('end')

        clip_duration = clip_duration_re.search(line)
        if clip_duration:
            scene_length = clip_duration.group('dur_sec')

    if (len(chunk_starts) > 0):
        chunk_starts.append(float(scene_start))
        chunk_ends.append(float(scene_length)) #end here is max length of the

    return list(zip(chunk_starts, chunk_ends))


def execute_ffmpeg(input_file, processors=None, **kwargs):
    """
    Run ffmpeg with a set of audio processors to add filters to a call
    and process the results into a dict
    ffmpeg -i sample.m4v -filter:v "select='gt(scene,0.3)',showinfo" -f null - 2> ffout
    """
    if processors is None:
        processors = [
            VideoProcessor('select', with_select, parse_video_output),
            VideoProcessor('showinfo', with_showinfo, parse_video_output)
        ]

    stream = ffmpeg.input(input_file)

    for with_filter in [ap.with_filter for ap in processors]:
        stream = with_filter(stream, **kwargs)
    print(stream)

    ret_code, out = ffmpeg.output(stream, '-', format='null').run(quiet=True)

    if ret_code:
        raise RuntimeError

    output_lines = out.decode('utf-8').splitlines()

    return {ap.name: ap.output_processor(output_lines) for ap in processors}
