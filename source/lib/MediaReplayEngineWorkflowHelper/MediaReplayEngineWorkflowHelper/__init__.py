# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

##############################################################################
#
# PURPOSE:
# Helper library used by the MRE internal lambda functions to interact with 
# the control plane
#
##############################################################################

import os
import re
import json
import urllib3
from time import sleep

import boto3
import requests
from requests_aws4auth import AWS4Auth

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

## Init dict for caching params
CP_PARAM_CACHE = {}

def get_controlplane_url():
     return CP_PARAM_CACHE.get("CONTROLPLANE_URL")

def get_controlplane_endpoint_url_from_ssm():
    ssm_client = boto3.client(
        'ssm',
        region_name=os.environ['AWS_REGION']
    )

    response = ssm_client.get_parameter(
        Name='/MRE/ControlPlane/EndpointURL',
        WithDecryption=True
    )

    assert "Parameter" in response

    endpoint_url = response["Parameter"]["Value"]
    endpoint_url_regex = ".*.execute-api."+os.environ['AWS_REGION']+".amazonaws.com/api/.*"

    assert re.match(endpoint_url_regex, endpoint_url)

    CP_PARAM_CACHE["CONTROLPLANE_URL"] = endpoint_url

get_controlplane_endpoint_url_from_ssm()

class ControlPlane:
    """
    Helper Class for interacting with the Control plane
    """
    def __init__(self):
        self.endpoint_url = get_controlplane_url()
        self.auth = AWS4Auth(
            os.environ['AWS_ACCESS_KEY_ID'],
            os.environ['AWS_SECRET_ACCESS_KEY'],
            os.environ['AWS_REGION'],
            'execute-api',
            session_token=os.getenv('AWS_SESSION_TOKEN')
        )

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

    def store_first_pts(self, event, program, first_pts):
        """
        Method to store the pts timecode of the first frame of the first HLS video segment in the Control plane.

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param first_pts: The pts timecode of the first frame of the first HLS video segment

        :return: Control plane response
        """

        path = f"/event/{event}/program/{program}/timecode/firstpts/{first_pts}"
        method = "PUT"

        api_response = self.invoke_controlplane_api(path, method)
        
        return api_response.json()

    def get_first_pts(self, event, program):
        """
        Method to get the pts timecode of the first frame of the first HLS video segment from the Control plane.

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda

        :return: Control plane response containing the pts timecode of the first frame of the first HLS video segment
        """

        path = f"/event/{event}/program/{program}/timecode/firstpts"
        method = "GET"

        api_response = self.invoke_controlplane_api(path, method)
        
        if api_response.text == "null":
            return None
            
        return api_response.text

    def store_frame_rate(self, event, program, frame_rate):
        """
        Method to store the frame rate identified after probing the first HLS video segment in the Control plane.

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param frame_rate: The frame rate identified from the first HLS video segment

        :return: Control plane response
        """

        path = f"/event/{event}/program/{program}/framerate/{frame_rate}"
        method = "PUT"

        api_response = self.invoke_controlplane_api(path, method)
        
        return api_response.json()

    def store_first_frame_embedded_timecode(self, event, program, embedded_timecode):
        """
        Method to store the embedded timecode of the first frame of the first HLS video segment in the Control plane.

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param embedded_timecode: Embedded timecode of the first frame of the first HLS video segment

        :return: Control plane response
        """

        path = f"/event/{event}/program/{program}/timecode/firstframe/{embedded_timecode}"
        method = "PUT"

        api_response = self.invoke_controlplane_api(path, method)

        return api_response.json()

    def store_audio_tracks(self, event, program, audio_tracks):
        """
        Method to store the audio track details identified after probing the first HLS video segment in the Control plane.

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param audio_tracks: List of audio tracks identified from the first HLS video segment

        :return: Control plane response
        """

        path = "/event/metadata/track/audio"
        method = "POST"

        headers = {
            "Content-Type": "application/json"
        }

        body = {
            "Name": event,
            "Program": program,
            "AudioTracks": audio_tracks
        }

        api_response = self.invoke_controlplane_api(path, method, headers=headers, body=json.dumps(body))

        return api_response.json()

    def get_chunk_number(self, filename):
        """
        Method to extract the chunk number from HLS segment filename.

        :param filename: Name of the HLS segment file

        :return: Chunk number as integer
        """

        root, _ = os.path.splitext(filename)

        return int(root.split("_")[-1].lstrip("0"))

    def record_execution_details(self, event, program, filename, execution_id):
        """
        Method to record the details of an AWS Step Function workflow execution in the Control plane.

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param filename: Filename of the HLS Segment (Chunk) being processed in the workflow execution
        :param execution_id: Execution ID of the Step Function workflow

        :return: Control plane response
        """

        path = "/workflow/execution"
        method = "POST"

        headers = {
            "Content-Type": "application/json"
        }

        body = {
            "Program": program,
            "Event": event,
            "ExecutionId": execution_id,
            "ChunkNumber": self.get_chunk_number(filename),
            "Filename": filename
        }

        api_response = self.invoke_controlplane_api(path, method, headers=headers, body=json.dumps(body))

        return api_response.json()

    def put_plugin_execution_status(self, event, program, filename, plugin_name, status):
        """
        Method to update the execution status of a plugin in an AWS Step Function workflow in the Control plane.

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param filename: Filename of the HLS Segment (Chunk) being processed in the workflow execution
        :param plugin_name: Name of the plugin for which the execution status update is needed
        :param status: Status of the plugin execution - Waiting, In Progress, Complete, Error

        :return: Control plane response
        """

        path = f"/workflow/execution/program/{program}/event/{event}/chunk/{self.get_chunk_number(filename)}/plugin/{plugin_name}/status/{status}"
        method = "PUT"

        api_response = self.invoke_controlplane_api(path, method)

        return api_response.json()

    def get_plugin_execution_status(self, event, program, filename, plugin_name):
        """
        Method to retrieve the execution status of a plugin in an AWS Step Function workflow in the Control plane.

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param filename: Filename of the HLS Segment (Chunk) being processed in the workflow execution
        :param plugin_name: Name of the plugin for which the execution status is to be retrieved

        :return: Control plane response
        """

        path = f"/workflow/execution/program/{program}/event/{event}/chunk/{self.get_chunk_number(filename)}/plugin/{plugin_name}/status"
        method = "GET"

        api_response = self.invoke_controlplane_api(path, method)

        if api_response.text == "null":
            return None
            
        return api_response.text

    def list_incomplete_executions(self, event, program, filename, plugin_name):
        """
        Method to list all the Classifiers/Optimizers that are either yet to start or currently in progress in any of 
        the workflow executions prior to the current execution.

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param filename: Filename of the HLS Segment (Chunk) being processed in the workflow execution
        :param plugin_name: Name of either the Classifier or the Optimizer plugin

        :return: Control plane response
        """

        path = f"/workflow/execution/program/{program}/event/{event}/chunk/{self.get_chunk_number(filename)}/plugin/{plugin_name}/status/incomplete"
        method = "GET"

        api_response = self.invoke_controlplane_api(path, method)
            
        return api_response.json()

    def get_profile(self, profile):
        """
        Method to retrieve the processing profile information from the Control plane.

        :param profile: Name of the processing profile to retrieve

        :return: Control plane response
        """

        path = f"/profile/{profile}"
        method = "GET"

        api_response = self.invoke_controlplane_api(path, method)
            
        return api_response.json()

    def put_event_status(self, event, program, status):
        """
        Method to update the status of an event in the Control plane.

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param status: Status to update for the event

        :return: Control plane response
        """

        path = f"/event/{event}/program/{program}/status/{status}"
        method = "PUT"

        api_response = self.invoke_controlplane_api(path, method)
        
        return api_response.json()

    def get_event_status(self, event, program):
        """
        Method to get the status of an event from the Control plane.

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda

        :return: Control plane response
        """

        path = f"/event/{event}/program/{program}/status"
        method = "GET"

        api_response = self.invoke_controlplane_api(path, method)
  
        return api_response.text

    #--------------- Replay Engine Changes Starts ----------------------------------------------------

    def update_event_has_replays(self, event, program):
        """
        Updates a flag on an event indicating that a replay has been created

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda

        :return: Control plane response
        """

        path = f"/event/{event}/program/{program}/hasreplays"
        method = "PUT"

        api_response = self.invoke_controlplane_api(path, method)
            
        return api_response.json()

    def get_event(self, event, program):
        """
        Gets an Event based on Event name and Program Name

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda

        :return: Control plane response
        """

        path = f"/event/{event}/program/{program}"
        method = "GET"

        api_response = self.invoke_controlplane_api(path, method)
            
        return api_response.json()

    def get_replay_request(self, event, program, replay_request_id):
        """
        Gets Replay Request based on Event name, Program Name and Id

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param replay_request_id: Replay Request Id present in the input payload passed to Lambda

        :return: Control plane response
        """

        path = f"/replay/program/{program}/event/{event}/replayid/{replay_request_id}"
        method = "GET"

        api_response = self.invoke_controlplane_api(path, method)
            
        return api_response.json()

    def get_custom_priorities_engine(self, name):
        """
        Gets Custom Priorities Engine based on name

        :param name: Name of Custom Priorities Engine

        :return: Control plane response
        """

        path = f"/custompriorities/{name}"
        method = "GET"

        api_response = self.invoke_controlplane_api(path, method)
        
        if api_response.status_code > 299:
            return None
        
        return api_response.json()

    def get_plugin_by_name(self, plugin_name):
        """
        Get the latest version of a plugin by name.

        :param plugin_name: Name of the Plugin 
        

        :return: Control plane response
        """

        path = f"/plugin/{plugin_name}"
        method = "GET"

        api_response = self.invoke_controlplane_api(path, method)
            
        return api_response.json()

    def update_replay_request_status(self, program, event, id, replaystatus):
        """
        Updates Reply Request Status Event based on Event name, Program Name and Replay Request Id

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param id: Replay Request Id
        :param replaystatus: Replay Request status to be updated

        :return: Update status
        """
        path = f"/replay/program/{program}/event/{event}/replayid/{id}/status/update/{replaystatus}"
        method = "PUT"

        api_response = self.invoke_controlplane_api(path, method)
        
        return api_response.json()

    def update_replay_request_with_mp4_location(self, event, program, id, mp4_location, thumbnail):
        """
        Updates the generated MP4 location with the replay request

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param program: Location of the MP4 Video and Thumbnail
        
        """
        path = f"/replay/mp4location/update"
        method = "POST"
        
        headers = {
            "Content-Type": "application/json"
        }

        body = {
            "Name": event,
            "Program": program,
            "ReplayRequestId": id,
            "Mp4Location": mp4_location,
            "Thumbnail": thumbnail
        }

        self.invoke_controlplane_api(path, method, headers=headers, body=json.dumps(body))

    
    def get_all_replay_requests_for_event_opto_segment_end(self, program, event, audioTrack):
        """
        Gets all Replay Requests matching program, event and the AudioTrack

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param audioTrack: AudioTrack configured within Replay Request

        :return: List of Replay Requests
        """
        path = f"/replay/track/{audioTrack}/program/{program}/event/{event}"

        method = "GET"

        api_response = self.invoke_controlplane_api(path, method)
        return api_response.json()

    def get_all_replay_requests_for_completed_events(self, program, event, audioTrack):
        """
        Gets all Replay Requests matching program, event and the AudioTrack

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param audioTrack: AudioTrack configured within Replay Request

        :return: List of Replay Requests
        """
        path = f"/replay/completed/events/track/{audioTrack}/program/{program}/event/{event}"

        method = "GET"

        api_response = self.invoke_controlplane_api(path, method)
        return api_response.json()


    def get_all_replays_for_segment_end(self, event, program):
        """
        Gets all Replay Requests matching program, event

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        

        :return: List of Replay Requests
        """
        path = f"/replay/program/{program}/event/{event}/segmentend"
        method = "GET"

        api_response = self.invoke_controlplane_api(path, method)
        return api_response.json()

#--------------- Replay Engine Changes Ends ----------------------------------------------------

    

    def update_hls_master_manifest_location(self, event, program, hls_location, audioTrack):
        """
        Updates the generated HLS Manifest s3 location with the event

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param program: Location of the HLS Manifest in S3
        
        """
        path = f"/event/program/hlslocation/update"
        method = "POST"
        
        headers = {
            "Content-Type": "application/json"
        }

        body = {
            "Name": event,
            "Program": program,
            "HlsLocation": hls_location,
            "AudioTrack": audioTrack
        }

        self.invoke_controlplane_api(path, method, headers=headers, body=json.dumps(body))


    def update_event_edl_location(self, event, program, edl_location, audioTrack):
        """
        Updates the generated EDL s3 location with the event

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param program: Location of the HLS Manifest in S3
        """
        path = f"/event/program/edllocation/update"
        method = "POST"
        
        headers = {
            "Content-Type": "application/json"
        }

        body = {
            "Name": event,
            "Program": program,
            "EdlLocation": edl_location,
            "AudioTrack": audioTrack
        }

        self.invoke_controlplane_api(path, method, headers=headers, body=json.dumps(body))

    def update_replay_request_with_hls_location(self, hls_location):
        """
        Updates the Replay request with location of the generated HLS primary Playlist manifest file in S3.

        :param hls_location: Location of the generated HLS primary Playlist manifest file.

        :return: None
        """

        path = "/replay/update/hls/manifest"
        method = "POST"
        headers = {
            "Content-Type": "application/json"
        }
       
        self.invoke_controlplane_api(path, method, headers=headers, body=json.dumps(hls_location))    



    def update_event_data_export_location(self, event, program, location, isBaseEvent="N"):
        """
        Updates the generated Event Export data s3 location with the event

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param location: Location of the Event Data Export in S3
        :param isBaseEvent: "Y" if the export is the default MRE Data export. "N" if the event data export is created by customer custom implementations
        
        """
        path = f"/event/program/export_data"
        method = "PUT"
        
        headers = {
            "Content-Type": "application/json"
        }

        body = {
            "Name": event,
            "Program": program,
            "ExportDataLocation": location,
            "IsBaseEvent": isBaseEvent
        }

        self.invoke_controlplane_api(path, method, headers=headers, body=json.dumps(body))


    def update_replay_data_export_location(self, event, program, replay_id, location, isBaseEvent="N"):
        """
        Updates the Replay Export data s3 location with the event

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param location: Location of the Replay Data Export in S3
        :param isBaseEvent: "Y" if the export is the default MRE Data export. "N" if the Replay data export is created by customer custom implementations
        
        """
        path = f"/replay/event/program/export_data"
        method = "PUT"
        
        headers = {
            "Content-Type": "application/json"
        }

        body = {
            "Name": event,
            "Program": program,
            "ExportDataLocation": location,
            "ReplayId": replay_id,
            "IsBaseEvent": isBaseEvent
        }

        self.invoke_controlplane_api(path, method, headers=headers, body=json.dumps(body))


    def update_segments_to_be_ignored(self, event, program, replay_id, segment_cache_file_name):
        """
        Updates the Replay Request with SegmentCache file names that need to be ignored

        :param event: Event present in the input payload passed to Lambda
        :param program: Program present in the input payload passed to Lambda
        :param replay_id: ID of the Replay request
        :param segment_cache_file_name: Name of the Segment to be Ignored Cache file name
        
        """
        path = f"/replay/update/ignore/segment/cache"
        method = "PUT"
        
        headers = {
            "Content-Type": "application/json"
        }

        body = {
            "Name": event,
            "Program": program,
            "SegmentCacheName": segment_cache_file_name,
            "ReplayId": replay_id
        }

        self.invoke_controlplane_api(path, method, headers=headers, body=json.dumps(body))


    def get_transitions_config(self, transition_name):
        """
        Gets Replay Transitions configuration

        :param transition_name: Name of the Transition
        
        :return: Transition configuration
        """
        path = f"/replay/transition/{transition_name}"
        method = "GET"
        api_response = self.invoke_controlplane_api(path, method)
        return api_response.json()
