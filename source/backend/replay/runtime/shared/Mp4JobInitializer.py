#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json
import threading
from datetime import datetime
from queue import Queue

from aws_lambda_powertools import Logger

logger = Logger()

# Represents the Maximum number of Concurrent Threads
MAX_NUMBER_OF_THREADS = 20


class Mp4JobInitializer:
    def __init__(
        self,
        replay_items,
        data_plane,
        event_name,
        program,
        profile_name,
        audio_track,
        framerate,
        replay_id,
        item_type="SEGMENT",
    ):

        self.event_name = event_name
        self.program_name = program
        self.profile_name = profile_name
        self.replay_items = replay_items
        self._data_plane = data_plane
        self.input_job_settings = []
        self.temp_input_job_settings = []
        self.__queue = Queue()
        self.audio_track = audio_track
        self.__framerate = framerate
        self.threads = []
        self.replay_id = replay_id
        self.item_type = item_type

    def __process_mp4_input(self, item):
        # Only if we have some features found, push it to the Queue
        startTime = None
        endTime = None
        if self.item_type == "CLIP":
            startTime = item["StartTime"]
            endTime = item["EndTime"]
        elif self.item_type == "SEGMENT":
            startTime = item["OptoStart"] if "OptoStart" in item else item["Start"]
            endTime = item["OptoEnd"] if "OptoEnd" in item else item["End"]

        chunks = self._data_plane.get_chunks_for_segment(
            startTime, endTime, self.program_name, self.event_name, self.profile_name
        )
        print("CHUNKS: ")
        print(json.dumps(chunks))
        input_settings = self.__build_mp4_input(
            chunks, self.audio_track, startTime, endTime
        )

        logger.info(
            f"Got {len(chunks)} chunks for segment with Start time = {startTime} and End = {endTime}"
        )
        logger.info(
            f"INPUT SETTINGS = {json.dumps(input_settings)} for SEGMENT start = {startTime}"
        )

        self.__queue.put({"SegStartTime": startTime, "input_settings": input_settings})

    def __build_mp4_input(self, chunks, audioTrack, start_time, end_time):

        inputs = []

        # Only chunk, so will have Start and End Clipping time
        if len(chunks) == 1:
            inputClippings = []
            inputClip = {}
            ic = {}

            endtime = self._data_plane.get_mediaconvert_clip_format(
                end_time,
                program=self.program_name,
                event=self.event_name,
                profile=self.profile_name,
                frame_rate=self.__framerate,
            )
            starttime = self._data_plane.get_mediaconvert_clip_format(
                start_time,
                program=self.program_name,
                event=self.event_name,
                profile=self.profile_name,
                frame_rate=self.__framerate,
            )

            # endtime, starttime = self._data_plane.get_mediaconvert_clip_format(end_time), self._data_plane.get_mediaconvert_clip_format(start_time)
            ic["EndTimecode"] = str(endtime)
            ic["StartTimecode"] = str(starttime)

            # If we have a single Chunk we don't need the Endtime Configured if it is less than Start time. Remove it.
            if datetime.strptime(endtime, "%H:%M:%S:%f") < datetime.strptime(
                starttime, "%H:%M:%S:%f"
            ):
                ic.pop("EndTimecode", None)

            # ic['EndTimecode'], ic['StartTimecode'] = get_clip_timings(segment, event)
            inputClippings.append(ic)
            inputClip["InputClippings"] = inputClippings

            # ------------- Update MediaConvert AudioSelectors Input -------------

            # Leave the default Input AudioSelectors as is if we are dealing with default Track or only one.
            # If we have multiple AudioTracks, this lambda will be provided with one.

            inputClip["AudioSelectors"] = {
                "Audio Selector 1": {
                    "Tracks": [int(audioTrack)],
                    "DefaultSelection": "NOT_DEFAULT",
                    "SelectorType": "TRACK",
                }
            }

            inputClip["AudioSelectorGroups"] = {
                "Audio Selector Group 1": {"AudioSelectorNames": ["Audio Selector 1"]}
            }

            # ------------- Update MediaConvert AudioSelectors Input Ends -------------

            inputClip["VideoSelector"] = {}
            inputClip["TimecodeSource"] = "ZEROBASED"
            inputClip["FileInput"] = (
                f"s3://{chunks[0]['S3Bucket']}/{chunks[0]['S3Key']}"
            )
            inputs.append(inputClip)
        elif len(chunks) > 1:
            for chunk_index in range(len(chunks)):
                ic = {}
                inputClippings = []
                inputClip = {}
                if chunk_index == 0:  # First Chunk
                    ic["StartTimecode"] = self._data_plane.get_mediaconvert_clip_format(
                        start_time,
                        program=self.program_name,
                        event=self.event_name,
                        profile=self.profile_name,
                        frame_rate=self.__framerate,
                    )

                    inputClippings.append(ic)
                    inputClip["InputClippings"] = inputClippings
                elif chunk_index == len(chunks) - 1:  # Last Chunk
                    ic["EndTimecode"] = self._data_plane.get_mediaconvert_clip_format(
                        end_time,
                        program=self.program_name,
                        event=self.event_name,
                        profile=self.profile_name,
                        frame_rate=self.__framerate,
                    )
                    inputClippings.append(ic)
                    inputClip["InputClippings"] = inputClippings
                else:  # Sandwitch Chunks have no clippings
                    inputClip["InputClippings"] = []

                # ------------- Update MediaConvert AudioSelectors Input -------------

                # Leave the default Input AudioSelectors as is if we are dealing with default Track or only one.
                # If we have multiple AudioTracks, this lambda will be provided with one.
                inputClip["AudioSelectors"] = {
                    "Audio Selector 1": {
                        "Tracks": [int(audioTrack)],
                        "DefaultSelection": "NOT_DEFAULT",
                        "SelectorType": "TRACK",
                    }
                }

                inputClip["AudioSelectorGroups"] = {
                    "Audio Selector Group 1": {
                        "AudioSelectorNames": ["Audio Selector 1"]
                    }
                }

                # ------------- Update MediaConvert AudioSelectors Input Ends -------------
                inputClip["VideoSelector"] = {}
                inputClip["TimecodeSource"] = "ZEROBASED"
                inputClip["FileInput"] = (
                    f"s3://{chunks[chunk_index]['S3Bucket']}/{chunks[chunk_index]['S3Key']}"
                )
                inputs.append(inputClip)

        return inputs

    def create_input_settings(self):
        item_groups = [
            self.replay_items[i : i + MAX_NUMBER_OF_THREADS]
            for i in range(0, len(self.replay_items), MAX_NUMBER_OF_THREADS)
        ]

        logger.append_keys(replay_id=str(self.replay_id))
        logger.info(
            f"No. of Replay segments for creating MP4 = {len(self.replay_items)}"
        )

        for item_group in item_groups:
            logger.info(
                f"No. of threads being spawned for creating MP4 = {len(item_group)}"
            )
            self.__configure_threads(item_group)
            self.__start_threads()
            self.__join_threads()

            """
            [
                {
                    "SegStartTime": segmentStartTime,
                    "input_settings": input_settings
                }
            ]
            """
            while not self.__queue.empty():
                self.temp_input_job_settings.append(self.__queue.get())

            # Sort based on Seg Start time to keep the Input files in order based on Seg start time iff the replay isn't being created using specified timestamps
            if self.item_type == "SEGMENT":
                # enforce ordering by start time
                sorted_job_settings = sorted(
                    self.temp_input_job_settings, key=lambda x: x["SegStartTime"]
                )
                for job_setting in sorted_job_settings:
                    self.input_job_settings.extend(
                        job_setting["input_settings"] 
                    )
            elif self.item_type == "CLIP":
                # enforce original ordering of list
                index_map = {item["StartTime"]: index for index, item in enumerate(self.replay_items)}

                sorted_job_settings = sorted(
                    self.temp_input_job_settings, key=lambda x: index_map[x["SegStartTime"]]
                )
                for job_setting in sorted_job_settings:
                    self.input_job_settings.extend(
                        job_setting["input_settings"]
                    )
            else:
                raise Exception(f"Invalid Item Type: {self.item_type}")

            # Reset the thread list for the next group of processing
            self.threads = []
            self.temp_input_job_settings = []

        return self.input_job_settings

    def __configure_threads(self, items):
        logger.info(f"Creating MP4 Input settings for segments {json.dumps(items)}")

        for item in items:
            self.threads.append(
                threading.Thread(target=self.__process_mp4_input, args=(item,))
            )

    def __start_threads(self):
        for thread in self.threads:
            thread.start()

    def __join_threads(self):
        for thread in self.threads:
            thread.join()
