#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

##############################################################################
#
# PURPOSE:
# Helper library to aid the development of custom plugins for the 
# Media Replay Engine
#
##############################################################################

import os
import re
import json
import urllib.parse
import urllib3
import shutil
import math
from time import sleep
from functools import wraps
from datetime import date, datetime, time, timedelta

import boto3
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from requests_aws4auth import AWS4Auth

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ssm_client = boto3.client(
    'ssm',
    region_name=os.environ['AWS_REGION']
)

 ## Init dict for caching params
_PARAM_CACHE = {}

def get_dataplane_url():
     return _PARAM_CACHE.get("/MRE/DataPlane/EndpointURL")

def get_endpoint_urls_from_ssm():
    response = ssm_client.get_parameters(
        Names=['/MRE/DataPlane/EndpointURL','/MRE/ControlPlane/EndpointURL'],
        WithDecryption=True
    )

    assert "Parameters" in response

    for parameter in response["Parameters"]:
        endpoint_name = parameter["Name"]
        endpoint_url = parameter["Value"]
        
        endpoint_url_regex = ".*.execute-api."+os.environ['AWS_REGION']+".amazonaws.com/api/.*"

        assert re.match(endpoint_url_regex, endpoint_url)
        
        _PARAM_CACHE[endpoint_name] = endpoint_url

# Single call per Execution Env of a Lambda
get_endpoint_urls_from_ssm()

class Status:
    # Status messages for the workflow
    WORKFLOW_QUEUED = "Queued"
    WORKFLOW_IN_PROGRESS = "In Progress"
    WORKFLOW_PAUSED = "Paused"
    WORKFLOW_ERROR = "Error"
    WORKFLOW_COMPLETE = "Complete"

    # Status messages for the plugin
    PLUGIN_QUEUED = "Queued"
    PLUGIN_IN_PROGRESS = "In Progress"
    PLUGIN_ERROR = "Error"
    PLUGIN_COMPLETE = "Complete"


class PluginClass:
    CLASSIFIER = "Classifier"
    OPTIMIZER = "Optimizer"
    FEATURER = "Featurer"
    LABELER = "Labeler"


class Optimization:
    NOT_ATTEMPTED = "Not Attempted"
    NOT_ATTEMPTED_OUT_OF_RANGE = "Not Attempted - Out of chunk range"
    SUCCESS = "Succeeded"
    SUCCESS_PARTIAL = "Succeeded - Truncated extension due to search window limit"
    FAILED = "Failed"
    FAILED_CONFLICT = "Failed - Overlap with adjacent segment"


class MREExecutionError(Exception):
    pass


class OutputHelper:
    """
    Helper Class for generating a valid output object
    """
    def __init__(self, event):
        # From the event passed in to the plugin
        self.program = event["Event"]["Program"]
        self.event = event["Event"]["Name"]
        self.event_start = event["Event"]["Start"] if "Start" in event["Event"] else None
        self.timecode_source = event["Event"]["TimecodeSource"] if "TimecodeSource" in event["Event"] else "NOT_EMBEDDED"
        self.generate_orig_clips = event["Event"]["GenerateOrigClips"] if "GenerateOrigClips" in event["Event"] else None
        self.generate_opto_clips = event["Event"]["GenerateOptoClips"] if "GenerateOptoClips" in event["Event"] else None
        self.audio_tracks = event["Event"]["AudioTracks"] if "AudioTracks" in event["Event"] else []
        self.audio_track = event["TrackNumber"] if "TrackNumber" in event else None

        self.execution_id = event["Input"]["ExecutionId"]
        self.media = event["Input"]["Media"]
        self.metadata = event["Input"]["Metadata"]

        self.plugin_name = event["Plugin"]["Name"]
        self.plugin_class = event["Plugin"]["Class"]
        self.execution_type = event["Plugin"]["ExecutionType"]
        self.dependent_plugins = event["Plugin"]["DependentPlugins"]
        self.model_endpoint = event["Plugin"]["ModelEndpoint"] if self.execution_type == "SyncModel" else ""
        self.configuration = event["Plugin"]["Configuration"]
        self.output_attributes = event["Plugin"]["OutputAttributes"]

        self.status = ""
        self.results = []

    def update_plugin_status(self, status):
        """
        Method to update the plugin status in the output object.

        :param status: Status of the plugin as defined in the Status class

        :return: Nothing
        """
        self.status = status

    def add_metadata(self, **kwargs):
        """
        Method to add one or more key-value pairs to the metadata in the output object.
        
        :param kwargs: One or more key-value pairs 
        
        :return: Nothing
        """
        for key, value in kwargs.items():
            self.metadata.update({key: value})

    def add_results_to_output(self, results):
        """
        Method to add one or more results of the plugin to the output object.
        
        :param results: List containing one or more plugin results 
        
        :return: Nothing
        """
        new_results = []

        for item in results:
            if "Start" in item:
                item["Start"] = round(item["Start"], 3)

            if "End" in item:
                item["End"] = round(item["End"], 3)

            if "OptoStart" in item:
                item["OptoStart"] = round(item["OptoStart"], 3)

            if "OptoEnd" in item:
                item["OptoEnd"] = round(item["OptoEnd"], 3)

            new_results.append(item)

        self.results = new_results

    def get_output_object(self):
        """
        Method to return the plugin output object.

        :return: Output object dictionary
        """
        new_event = {
            "Name": self.event,
            "Program": self.program,
            "AudioTracks": self.audio_tracks
        }

        if self.event_start:
            new_event["Start"] = self.event_start

        if self.timecode_source:
            new_event["TimecodeSource"] = self.timecode_source

        if self.generate_orig_clips is not None:
            new_event["GenerateOrigClips"] = self.generate_orig_clips

        if self.generate_opto_clips is not None:
            new_event["GenerateOptoClips"] = self.generate_opto_clips
        
        output = {
            "Event": new_event,
            "Input": {
                "ExecutionId": self.execution_id,
                "Media": self.media,
                "Metadata": self.metadata
            },
            "Output": {
                "PluginName": self.plugin_name,
                "PluginClass": self.plugin_class,
                "ExecutionType": self.execution_type,
                "DependentPlugins": self.dependent_plugins,
                "ModelEndpoint": self.model_endpoint,
                "Configuration": self.configuration,
                "OutputAttributes": self.output_attributes,
                "Status": self.status,
                "Results": self.results
            }
        }

        if self.audio_track:
            output["TrackNumber"] = self.audio_track

        return output
        

class PluginHelper:
    """
    Helper Class containing useful utility functions used in plugin development
    """
    def __init__(self, event):
        # From the event passed in to the plugin
        self.program = event["Event"]["Program"]
        self.event = event["Event"]["Name"]
        self.event_start = event["Event"]["Start"] if "Start" in event["Event"] else None
        self.timecode_source = event["Event"]["TimecodeSource"] if "TimecodeSource" in event["Event"] else "NOT_EMBEDDED"
        self.generate_orig_clips = event["Event"]["GenerateOrigClips"] if "GenerateOrigClips" in event["Event"] else None
        self.generate_opto_clips = event["Event"]["GenerateOptoClips"] if "GenerateOptoClips" in event["Event"] else None
        self.audio_tracks = event["Event"]["AudioTracks"] if "AudioTracks" in event["Event"] else []

        self.execution_id = event["Input"]["ExecutionId"]
        self.media = event["Input"]["Media"]
        self.metadata = event["Input"]["Metadata"]

        if "Plugin" in event:
            self.plugin_name = event["Plugin"]["Name"]
            self.plugin_class = event["Plugin"]["Class"]
            self.execution_type = event["Plugin"]["ExecutionType"]
            self.dependent_plugins = event["Plugin"]["DependentPlugins"]
            self.model_endpoint = event["Plugin"]["ModelEndpoint"] if self.execution_type == "SyncModel" else ""
            self.configuration = event["Plugin"]["Configuration"]
            self.output_attributes = event["Plugin"]["OutputAttributes"]

        if "Profile" in event:
            self.profile_name = event["Profile"]["Name"]
            self.chunk_size = event["Profile"]["ChunkSize"]
            self.processing_frame_rate = event["Profile"]["ProcessingFrameRate"]
            self.classifier = event["Profile"]["Classifier"]
            self.optimizer = event["Profile"]["Optimizer"] if "Optimizer" in event["Profile"] else {}
            self.featurers = event["Profile"]["Featurers"] if "Featurers" in event["Profile"] else []
            self.labeler = event["Profile"]["Labeler"] if "Labeler" in event["Profile"] else {}

    def get_plugin_configuration(self):
        """
        Method to get the plugin 'Configuration' dictionary.

        :return: Plugin 'Configuration' dictionary
        """

        return self.configuration

    def get_plugin_output_attributes(self):
        """
        Method to get the plugin 'OutputAttributes' dictionary.

        :return: Plugin 'OutputAttributes' dictionary
        """

        return self.output_attributes

    def get_dependent_plugins_configuration(self):
        """
        Method to get the 'Configuration' dictionary of all the dependent plugins associated with the 
        current plugin.

        :return: 'Configuration' dictionary of all the dependent plugins
        """

        dependent_plugins_configuration = {}

        if self.plugin_class in ["Classifier", "Featurer"]:
            if "DependentPlugins" in self.classifier:
                for d_plugin in self.classifier["DependentPlugins"]:
                    if d_plugin["Name"] in self.dependent_plugins:
                        dependent_plugins_configuration[d_plugin["Name"]] = d_plugin["Configuration"] if "Configuration" in d_plugin else {}

        if not dependent_plugins_configuration and self.plugin_class in ["Optimizer", "Featurer"]:
            if "DependentPlugins" in self.optimizer:
                for d_plugin in self.optimizer["DependentPlugins"]:
                    if d_plugin["Name"] in self.dependent_plugins:
                        dependent_plugins_configuration[d_plugin["Name"]] = d_plugin["Configuration"] if "Configuration" in d_plugin else {}

        if not dependent_plugins_configuration and self.plugin_class in ["Labeler", "Featurer"]:
            if "DependentPlugins" in self.labeler:
                for d_plugin in self.labeler["DependentPlugins"]:
                    if d_plugin["Name"] in self.dependent_plugins:
                        dependent_plugins_configuration[d_plugin["Name"]] = d_plugin["Configuration"] if "Configuration" in d_plugin else {}

        if not dependent_plugins_configuration and self.plugin_class == "Featurer":
            for featurer in self.featurers:
                if "DependentPlugins" in featurer:
                    for d_plugin in featurer["DependentPlugins"]:
                        if d_plugin["Name"] in self.dependent_plugins:
                            dependent_plugins_configuration[d_plugin["Name"]] = d_plugin["Configuration"] if "Configuration" in d_plugin else {}

        return dependent_plugins_configuration

    def get_segment_absolute_time(self, time, pts=False):
        """
        Method to get HLS segment-level absolute time for a given time value.
        Segment-level absolute time is nothing but the addition of HLS segment start time and 
        the given time value.

        :param time: Time value for which segment-level absolute time needs to be calculated
        
        :return: Segment-level absolute time
        """
        if pts:
            start_time = float(self.metadata["HLSSegment"]["StartPtsTime"])
        else:
            start_time = float(self.metadata["HLSSegment"]["StartTime"])

        return round(start_time + time, 3)


class DataPlane:
    """
    Helper Class for interacting with the Data plane
    """
    class Decorator:
        """
        Class that contains one or more decorator functions
        """
        @classmethod
        def cleanup_tmp_dir(cls, path="/tmp/mre/"):
            """
            Decorator function to clean up all the files and sub-directories in the /tmp/mre directory
            """
            def rm_content(path):
                if os.path.exists(path):
                    rm_count = 0
                    
                    for filename in os.listdir(path):
                        filepath = os.path.join(path, filename)

                        if os.path.isfile(filepath) or os.path.islink(filepath):
                            os.remove(filepath)
                        else:
                            shutil.rmtree(filepath)
                        
                        rm_count += 1
                
                    print(f"Message from Cleanup Decorator: Removed {rm_count} files/sub-directories in '{path}'")
                
                else:
                    print(f"Message from Cleanup Decorator: No cleanup required as the path '{path}' does not exist")

            def inner(f):
                @wraps(f)
                def dir_cleanup_wrapper(*args, **kwargs):
                    rm_content(path)
                    result = f(*args, **kwargs)
                    return result

                return dir_cleanup_wrapper

            return inner

    def __init__(self, event):
        self.endpoint_url = get_dataplane_url()
        self.auth = AWS4Auth(
            os.environ['AWS_ACCESS_KEY_ID'],
            os.environ['AWS_SECRET_ACCESS_KEY'],
            os.environ['AWS_REGION'],
            'execute-api',
            session_token=os.getenv('AWS_SESSION_TOKEN')
        )

        if "Event" in event:
            self.program = event["Event"]["Program"]
            self.event = event["Event"]["Name"]
            self.event_start = event["Event"]["Start"] if "Start" in event["Event"] else None
            self.timecode_source = event["Event"]["TimecodeSource"] if "TimecodeSource" in event["Event"] else "NOT_EMBEDDED"
            self.generate_orig_clips = event["Event"]["GenerateOrigClips"] if "GenerateOrigClips" in event["Event"] else None
            self.generate_opto_clips = event["Event"]["GenerateOptoClips"] if "GenerateOptoClips" in event["Event"] else None
            self.audio_tracks = event["Event"]["AudioTracks"] if "AudioTracks" in event["Event"] else []
            
        self.audio_track = event["TrackNumber"] if "TrackNumber" in event else None

        if "Input" in event:
            self.execution_id = event["Input"]["ExecutionId"]

            self.metadata = event["Input"]["Metadata"] if "Metadata" in event["Input"] else {}
            self.chunk_start = self.metadata["HLSSegment"]["StartTime"] if self.metadata else 0
            self.frame_rate = self.metadata["HLSSegment"]["FrameRate"] if self.metadata else 0

            self.media = event["Input"]["Media"]
            self.bucket = self.media["S3Bucket"]
            self.key = self.media["S3Key"]
            self.filename = os.path.split(self.key)[-1]

        if "Plugin" in event:
            self.plugin_name = event["Plugin"]["Name"]
            self.plugin_class = event["Plugin"]["Class"]
            self.execution_type = event["Plugin"]["ExecutionType"]
            self.dependent_plugins = event["Plugin"]["DependentPlugins"]
            self.model_endpoint = event["Plugin"]["ModelEndpoint"] if self.execution_type == "SyncModel" else ""
            self.configuration = event["Plugin"]["Configuration"]
            self.output_attributes = event["Plugin"]["OutputAttributes"]

        if "Profile" in event:
            self.profile_name = event["Profile"]["Name"]
            self.chunk_size = event["Profile"]["ChunkSize"]
            self.max_segment_length = event["Profile"]["MaxSegmentLengthSeconds"]
            self.processing_frame_rate = event["Profile"]["ProcessingFrameRate"]
            self.classifier = event["Profile"]["Classifier"]
            self.optimizer = event["Profile"]["Optimizer"] if "Optimizer" in event["Profile"] else {}
            self.featurers = event["Profile"]["Featurers"] if "Featurers" in event["Profile"] else []
            self.labeler = event["Profile"]["Labeler"] if "Labeler" in event["Profile"] else {}

    def invoke_dataplane_api(self, path, method, headers=None, body=None, params=None):
        """
        Method to invoke the Data plane REST API Endpoint.

        :param path: Path to the corresponding API resource
        :param method: REST API method
        :param headers: (optional) headers to include in the request
        :param body: (optional) data to send in the body of the request
        :param params: (optional) data to send in the request query string

        :return: Data plane API response object
        """

        print(f"{method} {path}")

        conn_max_retries = http_max_retries = 5
        backoff_secs = 0.3
        http_status_retry_list = [429, 500, 503, 504]

        while True:
            try:
                response = requests.request(
                    method=method,
                    url=self.endpoint_url + path,
                    params=params,
                    headers=headers,
                    data=body,
                    verify=False,
                    auth=self.auth
                )

                response.raise_for_status()

            except requests.exceptions.ConnectionError as e:
                print(f"Encountered a connection error while invoking the data plane api: {str(e)}")

                if conn_max_retries == 0:
                    raise Exception(e)

                backoff = backoff_secs * (2 ** (5 - conn_max_retries))
                print(f"Retrying after {backoff} seconds")
                sleep(backoff)
                conn_max_retries -= 1
                continue

            except requests.exceptions.HTTPError as e:
                print(f"Encountered an HTTP error while invoking the data plane api: {str(e)}")

                status_code = e.response.status_code
                print("HTTP status code:", status_code)

                if status_code in http_status_retry_list: # Retry only specific status codes
                    if http_max_retries == 0:
                        raise Exception(e)

                    backoff = backoff_secs * (2 ** (5 - http_max_retries))
                    print(f"Retrying after {backoff} seconds")
                    sleep(backoff)
                    http_max_retries -= 1
                    continue

                else:
                    print("Got a non-retryable HTTP status code")
                    raise Exception(e)

            except requests.exceptions.RequestException as e:
                print(f"Encountered an unknown error while invoking the data plane api: {str(e)}")
                raise Exception(e)

            else:
                return response
    
    def get_media_presigned_url(self):
        """
        Method to get the S3 pre-signed URL from the Data plane.

        :return: Data plane response containing the S3 pre-signed URL
        """

        # URLEncode key as it could contain one or more forward slashes
        encoded_key = urllib.parse.quote(self.key, safe='')

        path = f"/media/{self.bucket}/{encoded_key}"
        method = "GET"

        api_response = self.invoke_dataplane_api(path, method)

        return api_response.text

    @Decorator.cleanup_tmp_dir()
    def download_media(self, path="/tmp/mre/media/"):
        """
        Method to download the media (video) file from the Data plane to a local path.

        :param path: Local path to download the media file to

        :return: Absolute path of the downloaded media file
        """

        media_presigned_url = self.get_media_presigned_url()

        try:
            session = requests.Session()

            retry = Retry(
                total=5,
                backoff_factor=0.3,
                status_forcelist=[500, 503]
            )

            session.mount('https://', HTTPAdapter(max_retries=retry))

            # Get the media file content using the presigned url
            response = session.get(
                url=media_presigned_url
            )

            response.raise_for_status()
        
        except requests.exceptions.RequestException as e:
            print(f"Encountered an error while downloading the media file using S3 pre-signed URL: {str(e)}")
            raise Exception(e)

        else:
            # Create path directory if it doesn't exist
            os.makedirs(path, exist_ok=True)
            
            # download_path is path parameter + media filename
            download_path = os.path.join(path, self.filename)

            # Write the media content to download_path
            with open(download_path, 'wb') as f_out:
                f_out.write(response.content)
        
            return download_path
    
    def store_frames(self, frames):
        """
        Method to store all the frame metadata of a media (video) in the Data plane.

        :param frames: Frame metadata extracted from the video file

        :return: Data plane response
        """

        path = "/metadata/frame"
        method = "POST"
        headers = {
            "Content-Type": "application/json"
        }

        body = {
            "Program": self.program,
            "Event": self.event,
            "Filename": self.filename,
            "Frames": frames
        }

        api_response = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(body))
        
        return api_response.json()

    def store_chunk_metadata(self, start, start_pts, duration, bucket, key):
        """
        Method to store the HLS Segment (Chunk) metadata in the Data plane.

        :param start: Start timecode of the chunk
        :param start_pts: StartPts timecode of the chunk
        :param duration: Duration of the chunk
        :param bucket: S3 Bucket name of the chunk
        :param key: S3 Key location of the chunk

        :return: Data plane response
        """

        path = "/metadata/chunk"
        method = "POST"
        headers = {
            "Content-Type": "application/json"
        }

        body = {
            "Program": self.program,
            "Event": self.event,
            "Profile": self.profile_name,
            "Filename": self.filename,
            "Start": start,
            "StartPts": start_pts,
            "Duration": duration,
            "S3Bucket": bucket,
            "S3Key": key
        }

        api_response = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(body))
        
        return api_response.json()

    def get_chunk_start_time(self, reference_time, program=None, event=None, profile=None, pts=False):
        """
        Method to get the HLS Segment (Chunk) start time based on the given reference time from the 
        Data plane.

        By default, the method gets the zero-based start timecode of the chunk. To get the PTS start timecode 
        instead, call the method with an argument of "True" for the "pts" parameter.

        :param reference_time: Reference time used in getting the chunk start time
        :param program: Program name
        :param event: Event name
        :param profile: Processing Profile name
        :param pts: Boolean value that indicates whether or not to get the PTS start timecode of the chunk

        :return: Chunk start time based on the provided reference time
        """
        
        program = program if program else self.program
        event = event if event else self.event
        profile = profile if profile else self.profile_name
        
        path = f"/metadata/chunk/start/{program}/{event}/{profile}/{reference_time}"
        method = "GET"

        if not pts:
            path += "?pts=false"

        api_response = self.invoke_dataplane_api(path, method)
        
        if api_response.text == "null":
            return None

        return api_response.text

    def get_mediaconvert_clip_format(self, time_secs, program=None, event=None, profile=None, frame_rate=0, pts=False):
        """
        Method to convert the time in seconds to the AWS Elemental MediaConvert clip format (HH:MM:SS:FF).

        By default, the method assumes that the time_secs parameter is in zero-based format. If time_secs is in 
        the PTS format, call the method with an argument of "True" for the "pts" parameter.

        :param time_secs: Time value that needs to be converted to the MediaConvert clip format
        :param program: Program name
        :param event: Event name
        :param profile: Processing Profile name
        :param frame_rate: Frame Rate associated with the Event
        :param pts: Boolean value that indicates whether or not to get the clip timestamp in PTS format

        :return: Time in MediaConvert clip format which is HH:MM:SS:FF
        """

        frame_rate = frame_rate if frame_rate else self.frame_rate

        if frame_rate == 0:
            raise Exception("Error in getting mediaconvert clip format: Frame rate cannot have a value of zero")

        fpms = int(frame_rate) / 1000

        chunk_start_time = self.get_chunk_start_time(time_secs, program=program, event=event, profile=profile, pts=pts)

        print(f"Mediaconvert clip format - Chunk start time: {chunk_start_time}")

        if not chunk_start_time:
            relative_time_secs = time_secs
        else:
            relative_time_secs = time_secs - float(chunk_start_time)

        print(f"Mediaconvert clip format - Relative start time: {relative_time_secs}")

        seconds = int(relative_time_secs)
        millis = int(round((relative_time_secs % 1), 3) * 1000)

        frame_num = math.ceil(millis * fpms)

        return (datetime.combine(date.today(), time(0, 0, 0)) + timedelta(seconds=seconds)).strftime("%H:%M:%S") + f":{frame_num:02}"

    def get_frame_timecode(self, frame_number, pts=False):
        """
        Method to get the timecode of a frame from the Data plane.

        By default, the method gets the zero-based timecode of a frame. To get the PTS timecode instead, 
        call the method with an argument of "True" for the "pts" parameter.

        :param frame_number: FrameNumber of the frame in the video file
        :param pts: Boolean value that indicates whether or not to get the PTS timecode of a frame

        :return: Timecode of the frame
        """
        
        path = f"/metadata/timecode/{self.program}/{self.event}/{self.filename}/{frame_number}"
        method = "GET"

        if not pts:
            path += "?pts=false"

        api_response = self.invoke_dataplane_api(path, method)
        
        return float(api_response.text)

    def get_chunk_number(self, filename):
        """
        Method to extract the chunk number from HLS segment filename.

        :param filename: Name of the HLS segment file

        :return: Chunk number as integer
        """

        root, _ = os.path.splitext(filename)

        return int(root.split("_")[-1].lstrip("0"))
        
    def save_plugin_results(self, results):
        """
        Method to save one or more results of a plugin in the Data plane.

        :param results: List containing one or more plugin results

        :return: Data plane response
        """

        if not results:
            print("Not saving the plugin results as the 'results' list is empty")
            return

        path = "/plugin/result"
        method = "POST"
        headers = {
            "Content-Type": "application/json"
        }

        body = {
            "Program": self.program,
            "Event": self.event,
            "ProfileName": self.profile_name,
            "ChunkSize": self.chunk_size,
            "ProcessingFrameRate": self.processing_frame_rate,
            "Classifier": self.classifier["Name"],
            "ExecutionId": self.execution_id,
            "Filename": self.filename,
            "ChunkNumber": self.get_chunk_number(self.filename),
            "PluginName": self.plugin_name,
            "PluginClass": self.plugin_class,
            "ModelEndpoint": self.model_endpoint,
            "OutputAttributesNameList": [*self.output_attributes],
            "Location": self.media,
            "Results": results
        }

        if self.audio_track:
            body["AudioTrack"] = self.audio_track

        api_response = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(body))
        
        return api_response.json()


    def get_segment_state(self):
        """
        Method to retrieve the state of the segment identified in prior chunks (HLS .ts files) from 
        the Data plane.

        :return: Data plane response
        """

        path = "/workflow/segment/state"
        method = "POST"
        headers = {
            "Content-Type": "application/json"
        }

        body = {
            "Program": self.program,
            "Event": self.event,
            "PluginName": self.plugin_name,
            "DependentPlugins": self.dependent_plugins,
            "ChunkNumber": self.get_chunk_number(self.filename),
            "ChunkStart": self.chunk_start,
            "MaxSegmentLength": self.max_segment_length
        }

        api_response =  self.__segment_state_transformation(path,method,headers,body)
        return api_response

    
    # This is to prevent a breaking change for the addition of pagination
    def __segment_state_transformation(self,path,method,headers,body):
        api_response = [None, {}, {}]
        results = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(body)).json()
        if 'State' in results:
            api_response[0] = results['State']
        if 'PriorSegment' in results:
            api_response[1] = results['PriorSegment']
        if 'DependentPluginResults' in results:
            new_body, last_eval_keys = process_dependent_plugin_segments(results,api_response,body)
            while last_eval_keys:
                results = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(new_body)).json()
                if 'DependentPluginResults' in results:
                   new_body, last_eval_keys = process_dependent_plugin_segments(results,api_response,body)
        return api_response

    def get_segment_state_for_labeling(self):
        """
        Method to retrieve one or more complete, unlabeled segments identified in the current/prior chunks and 
        all the Labeler dependent plugins output associated with those segments from the Data plane.

        :return: Data plane response
        """

        path = "/workflow/labeling/segment/state"
        method = "POST"
        headers = {
            "Content-Type": "application/json"
        }

        body = {
            "Program": self.program,
            "Event": self.event,
            "Classifier": self.classifier["Name"],
            "DependentPlugins": self.dependent_plugins,
            "ChunkNumber": self.get_chunk_number(self.filename)
        }

        api_response = self.__segment_state_for_labeling_transformation(path,method,headers,body)
        return api_response
    
    # This is to prevent a breaking change for the addition of pagination
    def __segment_state_for_labeling_transformation(self,path,method,headers,body):
        api_response = []
        last_eval_keys = {}
        results = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(body)).json()
        print(results)
        if results and 'Segment' in results:
            segment = results['Segment']['Item']
            if 'LastEvaluatedKey' in results['Segment']:
                last_eval_keys = {self.classifier["Name"]:results['Segment']['LastEvaluatedKey']}
            dependent_plugin_output = {}
            process_label_plugin_output(results,last_eval_keys,dependent_plugin_output)
            new_body = {**{'LastEvaluatedKeys':last_eval_keys}, **body}
            while len(last_eval_keys) > 1:
                results = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(new_body)).json()
                process_label_plugin_output(results,last_eval_keys,dependent_plugin_output)
                new_body = {**{'LastEvaluatedKeys':last_eval_keys}, **body}
            api_response.append({'Segment':segment,'DependentPluginsOutput': dependent_plugin_output})
            while 'Segment' in results and 'LastEvaluatedKey' in results['Segment']:
                results = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(new_body)).json()
                if results and 'Segment' in results:
                    segment = results['Segment']['Item']
                    if 'LastEvaluatedKey' in results['Segment']:
                        last_eval_keys = {self.classifier["Name"]:results['Segment']['LastEvaluatedKey']}
                    dependent_plugin_output = {}
                    process_label_plugin_output(results,last_eval_keys,dependent_plugin_output)
                    new_body = {**{'LastEvaluatedKeys':last_eval_keys}, **body}
                    while len(last_eval_keys) > 1:
                        results = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(new_body)).json()
                        process_label_plugin_output(results,last_eval_keys,dependent_plugin_output)
                        new_body = {**{'LastEvaluatedKeys':last_eval_keys}, **body}
                    api_response.append({'Segment':segment,'DependentPluginsOutput': dependent_plugin_output})
        return api_response


    def get_segment_state_for_optimization(self, search_window_sec=0):
        """
        Method to retrieve one or more non-optimized segments identified in the current/prior chunks and all the 
        dependent detectors output around the segments for optimization from the Data plane.

        :param search_window_sec: Maximum time window to consider when querying for the dependent detectors output

        :return: Data plane response
        """

        path = "/workflow/optimization/segment/state"
        method = "POST"
        headers = {
            "Content-Type": "application/json"
        }

        detectors = []

        if "DependentPlugins" in self.optimizer:
            for d_plugin in self.optimizer["DependentPlugins"]:
                if d_plugin["Name"] in self.dependent_plugins:
                    detectors.append(
                        {
                            "Name": d_plugin["Name"],
                            "SupportedMediaType": d_plugin["SupportedMediaType"]
                        }
                    )

        body = {
            "Program": self.program,
            "Event": self.event,
            "ChunkNumber": self.get_chunk_number(self.filename),
            "Classifier": self.classifier["Name"],
            "Detectors": detectors,
            "SearchWindowSeconds": int(search_window_sec)
        }

        if self.audio_track:
            body["AudioTrack"] = self.audio_track

        # api_response = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(body))
        api_response = self.__segment_state_for_optimization_transformation(path,method,headers,body)
        
        return api_response
    
    # This is to prevent a breaking change for the addition of pagination
    def __segment_state_for_optimization_transformation(self,path,method,headers,body):
        api_response = []
        last_eval_keys = {}
        results = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(body)).json()
        if results and 'Segment' in results:
            segment = results['Segment']['Item']
            if 'LastEvaluatedKey' in results['Segment']:
                last_eval_keys = {self.classifier["Name"]:results['Segment']['LastEvaluatedKey']}
            dependent_detector_output = []
            process_dependent_detector_output(results,dependent_detector_output)
            new_body = {**{'LastEvaluatedKeys':last_eval_keys}, **body}
            api_response.append({'Segment':segment,'DependentDetectorsOutput': dependent_detector_output})
            while 'Segment' in results and 'LastEvaluatedKey' in results['Segment']:
                # Add keys to request to add
                results = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(new_body)).json()
                if results and 'Segment' in results:
                    segment = results['Segment']['Item']
                    if 'LastEvaluatedKey' in results['Segment']:
                        last_eval_keys = {self.classifier["Name"]:results['Segment']['LastEvaluatedKey']}
                    dependent_detector_output = []
                    process_dependent_detector_output(results,dependent_detector_output)
                    new_body = {**{'LastEvaluatedKeys':last_eval_keys}, **body}
                    api_response.append({'Segment':segment,'DependentDetectorsOutput': dependent_detector_output})
        return api_response

    def get_segments_for_clip_generation(self):
        """
        Method to retrieve non-optimized and optimized segments for a given program and event from the Data plane.

        :return: Data plane response
        """

        path = "/workflow/engine/clipgen/segments"
        method = "POST"
        headers = {
            "Content-Type": "application/json"
        }

        body = {
            "Program": self.program,
            "Event": self.event,
            "Classifier": self.classifier["Name"]
        }

        api_response = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(body))
        
        return api_response.json()

    def get_chunks_for_segment(self, start, end, program=None, event=None, profile_name=None):
        """
        Method to retrieve the filename, location and duration of all the chunks that contain the provided segment 
        start and end time from the Data plane.

        :param start: Start or OptoStart of the segment
        :param end: End or OptoEnd of the segment

        :return: Data plane response
        """

        program = program if program else self.program
        event = event if event else self.event
        profile_name = profile_name if profile_name else self.profile_name

        path = "/workflow/engine/clipgen/chunks"
        method = "POST"
        headers = {
            "Content-Type": "application/json"
        }

        body = {
            "Program": program,
            "Event": event,
            "Profile": profile_name,
            "Start": start,
            "End": end
        }

        api_response = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(body))
        
        return api_response.json()

    def save_clip_results(self, results):
        """
        Method to save one or more results of the MRE Clip Generation Engine in the Data plane.

        :param results: List containing one or more Clip Generation Engine results

        :return: Data plane response
        """

        if not results:
            print("Not saving the clip results as the 'results' list is empty")
            return

        path = "/clip/result"
        method = "POST"
        headers = {
            "Content-Type": "application/json"
        }

        body = {
            "Program": self.program,
            "Event": self.event,
            "Classifier": self.classifier["Name"],
            "Results": results
        }

        api_response = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(body))
        
        return api_response.json()
        
    def get_dependent_plugins_output(self, audio_track=1):
        """
        Method to retrieve the output of one or more dependent plugins of a plugin from 
        the Data plane.

        :return: Data plane response
        """

        path = "/plugin/dependentplugins/output"
        method = "POST"
        headers = {
            "Content-Type": "application/json"
        }

        dep_plugins_obj_list = []

        if self.plugin_class in ["Classifier", "Featurer"]:
            if "DependentPlugins" in self.classifier:
                for d_plugin in self.classifier["DependentPlugins"]:
                    if d_plugin["Name"] in self.dependent_plugins:
                        dep_plugins_obj_list.append(
                            {
                                "Name": d_plugin["Name"],
                                "SupportedMediaType": d_plugin["SupportedMediaType"]
                            }
                        )

        if not dep_plugins_obj_list and self.plugin_class in ["Optimizer", "Featurer"]:
            if "DependentPlugins" in self.optimizer:
                for d_plugin in self.optimizer["DependentPlugins"]:
                    if d_plugin["Name"] in self.dependent_plugins:
                        dep_plugins_obj_list.append(
                            {
                                "Name": d_plugin["Name"],
                                "SupportedMediaType": d_plugin["SupportedMediaType"]
                            }
                        )

        if not dep_plugins_obj_list and self.plugin_class in ["Labeler", "Featurer"]:
            if "DependentPlugins" in self.labeler:
                for d_plugin in self.labeler["DependentPlugins"]:
                    if d_plugin["Name"] in self.dependent_plugins:
                        dep_plugins_obj_list.append(
                            {
                                "Name": d_plugin["Name"],
                                "SupportedMediaType": d_plugin["SupportedMediaType"]
                            }
                        )
        
        if not dep_plugins_obj_list and self.plugin_class == "Featurer":
            for featurer in self.featurers:
                if "DependentPlugins" in featurer:
                    for d_plugin in featurer["DependentPlugins"]:
                        if d_plugin["Name"] in self.dependent_plugins:
                            dep_plugins_obj_list.append(
                                {
                                    "Name": d_plugin["Name"],
                                    "SupportedMediaType": d_plugin["SupportedMediaType"]
                                }
                            )

        body = {
            "Program": self.program,
            "Event": self.event,
            "ChunkNumber": self.get_chunk_number(self.filename),
            "DependentPlugins": dep_plugins_obj_list,
            "AudioTrack": self.audio_track if self.audio_track else int(audio_track)
        }

        return self.__dependent_plugin_output_transformation(path,method,headers,body)

    def __dependent_plugin_output_transformation(self,path,method,headers,body):
        api_response = {}
        results = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(body)).json()
        last_eval_keys ={}
        if results:
            for d_plugin_name, d_plugin_value in results.items():
                if 'Items' in d_plugin_value:
                    api_response[d_plugin_name] = d_plugin_value['Items']
                if 'LastEvaluatedKey' in d_plugin_value:
                    last_eval_keys[d_plugin_name] = d_plugin_value['LastEvaluatedKey']
            new_body = {**{'LastEvaluatedKeys':last_eval_keys}, **body}
            while last_eval_keys:
                results = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(new_body)).json()
                last_eval_keys ={}
                if results:
                    for d_plugin_name, d_plugin_value in results.items():
                        if 'Items' in d_plugin_value:
                            api_response[d_plugin_name] = d_plugin_value['Items']
                        if 'LastEvaluatedKey' in d_plugin_value:
                            last_eval_keys[d_plugin_name] = d_plugin_value['LastEvaluatedKey']
                    new_body = {**{'LastEvaluatedKeys':last_eval_keys}, **body}
        return api_response


    def _is_features_found_in_segment(self, program, event, starttime, pluginname, attrname, attrvalue, endtime):
        """
        Returns a bool indicating if a feature was found in the Plugin Results

        :return: True if a feature was found, False otherwise.
        """

        path = f"/feature/in/segment/program/{program}/event/{event}/plugin/{pluginname}/attrn/{attrname}/attrv/{attrvalue}/start/{starttime}/end/{endtime}"
        method = "GET"

        api_response = self.invoke_dataplane_api(path, method)

        #if 'Items' in api_response.json():
        #    return True if len(api_response.json()['Items']) > 0 else False

        return False if not api_response.json() else True


    def get_all_segments_for_event(self, program, event, classifier):
        """
        Returns all segments that match Event, Program and Classifier

        :return: List of Segments
        """

        path = f"/segments/all/program/{program}/event/{event}/classifier/{classifier}/replay"
        method = "GET"

        api_response = self.invoke_dataplane_api(path, method)

        return api_response.json()

    def update_replay_result(self, result_payload):
        """
        Updates the Replay Results everytime a Replay processes a Segment or End of Event

        :param result_payload: Replay result payload

        :return: None
        """

        path = "/replay/result"
        method = "POST"
        headers = {
            "Content-Type": "application/json"
        }
       
        return self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(result_payload))
        
    
    def get_all_segments_for_event_edl(self, program, event, classifier, tracknumber):
        """
        Returns all segments that match Event, Program and Classifier for generating an EDL

        :return: List of Segments
        """

        path = f"/event/{event}/program/{program}/profileClassifier/{classifier}/track/{tracknumber}/segments/for/edl"
        method = "GET"

        api_response = self.invoke_dataplane_api(path, method)

        return api_response.json()


    def get_all_segments_for_replay(self, program, event, replay_id):
        """
        Returns all replay segments that match Event, Program and ReplayId

        :return: List of Segments
        """

        path = f"/event/{event}/program/{program}/replay/{replay_id}/segments"
        method = "GET"

        api_response = self.invoke_dataplane_api(path, method)

        return api_response.json()

    
    def get_clip_preview_feedback(self, program, event, classifier, start_time, audio_track):
        """
        Returns Feedback information for a given Segment Clip

        :return: Feedback information for a Segment clip
        """

        path = f'/clip/preview/program/{program}/event/{event}/classifier/{classifier}/start/{start_time}/track/{audio_track}/feedback'
        method = "GET"

        api_response = self.invoke_dataplane_api(path, method)

        return api_response.json()

    def get_all_clip_preview_feedback(self, program, event, audio_track):
        """
        Returns all Feedback information for any Segment Clip in an event

        :return: Feedback information for segment clips
        """

        path = f'/clip/preview/program/{program}/event/{event}/track/{audio_track}/feedback'
        method = "GET"

        api_response = self.invoke_dataplane_api(path, method)

        return api_response.json()

    def get_all_event_segments_for_export(self, event, program, classifier, output_attributes, plugins_in_profile, last_start_time=None, limit=None):
        """
        Returns the Segment Metadata based on the segments found during Segmentation/Optimization process.

        :return: Data plane response
        """

        path = "/event/program/export/all/segments"
        method = "PUT"
        headers = {
            "Content-Type": "application/json"
        }
        body = {
                "Program": program,
                "Name": event,
                "Classifier": classifier,
                "OutputAttributes": output_attributes,
                "PluginsInProfile": plugins_in_profile
            }

        if last_start_time:
            body["LastStartValue"] = last_start_time
        
        if limit:
            body["Limit"] = limit

        api_response = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(body))
        
        return api_response.json()


    def save_media_convert_job_details(self, job_id) -> None:
        
        path = f"/job/create/{job_id}"
        method = "POST"
        headers = {
            "Content-Type": "application/json"
        }
        self.invoke_dataplane_api(path, method, headers=headers)

    def update_media_convert_job_status(self, job_id, status) -> None:
        
        path = f"/job/update/{job_id}/{status}"
        method = "POST"
        headers = {
            "Content-Type": "application/json"
        }
        self.invoke_dataplane_api(path, method, headers=headers)


    def get_media_convert_job_detail(self, job_id):
        
        path = f"/job/status/{job_id}"
        method = "GET"
        api_response = self.invoke_dataplane_api(path, method)
        return api_response.json()


    def get_replay_features_in_segment(self, program, event, plugin_name, output_attrs, starttime, endtime, audio_track=None):
        """
        Method to retrieve the value of all the output attributes stored by a plugin between segment start and end.

        :return: Data plane response
        """

        path = "/replay/feature/in/segment"
        method = "POST"
        headers = {
            "Content-Type": "application/json"
        }

        body = {
            "Program": program,
            "Event": event,
            "PluginName": plugin_name,
            "Start": starttime,
            "End": endtime,
            "OutputAttributes": output_attrs
        }

        if audio_track is not None:
            body["AudioTrack"] = int(audio_track)

        api_response = self.invoke_dataplane_api(path, method, headers=headers, body=json.dumps(body))

        return api_response.json()


    def add_attribute_to_existing_segment(self, program, event, classifier, start, attrName, attrVal):
        """
        Method to add a new attribute to an existing segment.

        :return: Data plane response
        """
        path = f"/event/{event}/program/{program}/classifier/{classifier}/start/{start}/attrName/{attrName}/attrVal/{attrVal}"
        method = "PUT"

        api_response = self.invoke_dataplane_api(path, method)

        return api_response.json()

    def get_replay_segments(self, name, program, replayId):
        """
        Gets Replay selected Segments

        :param name: Event name
        :param program: Program Name
        :param replayId: Replay Id
        
        :return: Replay Segments
        """
        path = f"/event/{name}/program/{program}/replay/{replayId}/segments"
        method = "GET"
        api_response = self.invoke_dataplane_api(path, method)
        return api_response.json()


def process_dependent_plugin_segments(results,api_response,body):
    last_eval_keys = {}
    for plugin_name, dependent_segment in results['DependentPluginResults'].items():
        if 'Items' in dependent_segment:
            if plugin_name in api_response[2]:
                api_response[2][plugin_name].extend(dependent_segment['Items'])
            else:
                api_response[2][plugin_name] = dependent_segment['Items']
        if 'LastEvaluatedKey' in dependent_segment:
            last_eval_keys[plugin_name] = dependent_segment['LastEvaluatedKey']
    new_body = {**{'LastEvaluatedKeys':last_eval_keys}, **body}
    return new_body, last_eval_keys

def process_label_plugin_output(results,last_eval_keys,dependent_plugin_output):
    if 'DependentPluginsOutput' in results:
# For each depedent plugin object is [{Segment: xxx, DependentPluginsOutput: {DependentPlugin: [items], DependentPlugin2: [items]}]
        for plugin_name, dependent_segment in results['DependentPluginsOutput'].items():
            if 'Items' in dependent_segment:
                dependent_plugin_output[plugin_name] = dependent_segment['Items']
            
            # Deal with the last eval keys    
            if 'LastEvaluatedKey' in dependent_segment:
                last_eval_keys[plugin_name] = dependent_segment['LastEvaluatedKey']
            else:
                last_eval_keys.pop(plugin_name,'n/a')

def process_dependent_detector_output(results,dependent_detector_output):
    if 'DependentDetectorsOutput' in results:
# For each depedent plugin object is [{Segment: xxx, DependentPluginsOutput: {DependentPlugin: [items], DependentPlugin2: [items]}]
        for dependent_detector in results['DependentDetectorsOutput']:
            dependent_detector_output.append(dependent_detector)

def get_controlplane_url():
     return _PARAM_CACHE.get("/MRE/ControlPlane/EndpointURL")

class ControlPlane:
    """
    Helper Class for interacting with the Control plane
    """    
    def __init__(self, event=None):
        self.endpoint_url = get_controlplane_url()
        self.auth = AWS4Auth(
            os.environ['AWS_ACCESS_KEY_ID'],
            os.environ['AWS_SECRET_ACCESS_KEY'],
            os.environ['AWS_REGION'],
            'execute-api',
            session_token=os.getenv('AWS_SESSION_TOKEN')
        )
        
        if event and "Event" in event:
            self.program = event["Event"]["Program"]
            self.event = event["Event"]["Name"]

    def invoke_controlplane_api(self, path, method, headers=None, body=None, params=None):
        """
        Method to invoke the Control plane REST API Endpoint.

        :param path: Path to the corresponding API resource
        :param method: REST API method
        :param headers: (optional) headers to include in the request
        :param body: (optional) data to send in the body of the request
        :param params: (optional) data to send in the request query string

        :return: Control plane API response object
        """

        print(f"{method} {path}")

        conn_max_retries = http_max_retries = 5
        backoff_secs = 0.3
        http_status_retry_list = [429, 500, 503, 504]

        while True:
            try:
                response = requests.request(
                    method=method,
                    url=self.endpoint_url + path,
                    params=params,
                    headers=headers,
                    data=body,
                    verify=False,
                    auth=self.auth
                )

                response.raise_for_status()

            except requests.exceptions.ConnectionError as e:
                print(f"Encountered a connection error while invoking the control plane api: {str(e)}")

                if conn_max_retries == 0:
                    raise Exception(e)

                backoff = backoff_secs * (2 ** (5 - conn_max_retries))
                print(f"Retrying after {backoff} seconds")
                sleep(backoff)
                conn_max_retries -= 1
                continue

            except requests.exceptions.HTTPError as e:
                print(f"Encountered an HTTP error while invoking the control plane api: {str(e)}")

                status_code = e.response.status_code
                print("HTTP status code:", status_code)

                if status_code in http_status_retry_list: # Retry only specific status codes
                    if http_max_retries == 0:
                        raise Exception(e)

                    backoff = backoff_secs * (2 ** (5 - http_max_retries))
                    print(f"Retrying after {backoff} seconds")
                    sleep(backoff)
                    http_max_retries -= 1
                    continue

                else:
                    print("Got a non-retryable HTTP status code")
                    raise Exception(e)

            except requests.exceptions.RequestException as e:
                print(f"Encountered an unknown error while invoking the control plane api: {str(e)}")
                raise Exception(e)

            else:
                return response

    def get_event_context_variables(self, program=None, event=None):
        """
        Gets event context variables

        :param event: Name of the Event
        :param program: Name of the Program
        
        :return: Event metadata
        """
        if not event:
            event = self.event

        if not program:
            program = self.program

        path = f"event/{event}/program/{program}/context-variables"
        method = "GET"
        api_response = self.invoke_controlplane_api(path, method)
        return api_response.json()
    
    def update_event_context_variables(self, body, program=None, event=None):
        """
        Updates entire event context variables

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        """
        if not event:
            event = self.event

        if not program:
            program = self.program

        path = f"event/{event}/program/{program}/context-variables"
        method = "PATCH"
        
        headers = {
            "Content-Type": "application/json"
        }

        self.invoke_controlplane_api(path, method, headers=headers, body=json.dumps(body))
