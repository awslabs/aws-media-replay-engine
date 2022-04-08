#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import copy
import json
import os
import uuid
import boto3
from datetime import datetime
from botocore.config import Config

from MediaReplayEnginePluginHelper import DataPlane
from MediaReplayEngineWorkflowHelper import ControlPlane

class EventDataExporter:

    def __init__(self, event):
        self._event = event
        
        self._dataplane = DataPlane(event)
        self._controlplane = ControlPlane()

    def _get_profile(self):
        return self._event['detail']['Event']['EventInfo']['Profile']
        

    def _get_additional_event_data(self):
        '''
            Gets additional event data not received from the EventBridge Payload
        '''
        event_name = self._event['detail']['Event']['EventInfo']['Event']['Name']
        program_name = self._event['detail']['Event']['EventInfo']['Event']['Program']
        self.__orig_event_info = self._controlplane.get_event(event_name, program_name)
        return self.__orig_event_info
    

    def get_event_info(self):
        return self.__orig_event_info

    def _get_all_segments_for_event(self):
        '''
            Gets all Segments created for the event
        '''

        event_name = self._event['detail']['Event']['EventInfo']['Event']['Name']
        program_name = self._event['detail']['Event']['EventInfo']['Event']['Program']

        classifier = self._event['detail']['Event']['EventInfo']['Profile']['Classifier']['Name']
        all_plugin_output_attributes, all_plugin_output_attribute_names = self._get_all_plugin_output_attributes()
        print(event_name)
        print(program_name)
        print(classifier)
        print(json.dumps(all_plugin_output_attribute_names))

        return self._dataplane.get_all_event_segments_for_export(event_name, program_name, classifier, list(all_plugin_output_attribute_names))

    def _get_all_plugin_output_attributes(self):
        '''
            Gets all the Output Attributes from Plugins based on the Profile
        '''
        
        # Get Plugins Classifier/Labeller/Featurer
        # For each get Output Attributes including from their Dependent Plugins
        profile = self._event['detail']['Event']['EventInfo']['Profile']
        #all_classifier_output_attributes = self.__get_classifier_output_attributes(profile)
        all_labeler_output_attributes = self.__get_labeler_output_attributes(profile)
        #all_featurer_output_attributes = self.__get_featurer_output_attributes(profile)

        all_output_attribute_names = []

        result = {}
        #if len(all_classifier_output_attributes) > 0:
        #    result['Classifier'] = all_classifier_output_attributes
        if len(all_labeler_output_attributes) > 0:
            result['Labeler'] = all_labeler_output_attributes
        #elif len(all_featurer_output_attributes) > 0:
        #    result['Featurer'] = all_featurer_output_attributes


        all_output_attribute_names.extend(all_labeler_output_attributes)
        #all_output_attribute_names.extend(all_featurer_output_attributes)

        return result, all_output_attribute_names

    def __get_classifier_plugin_names(self, profile):
        all_classifier_plugins = []
        main_plugin = profile['Classifier']['Name']
        all_classifier_plugins.append(main_plugin)

        if 'DependentPlugins' in profile['Classifier']:
            for dependent_plugin in profile['Classifier']['DependentPlugins']:
                all_classifier_plugins.append(dependent_plugin['Name'])

        return all_classifier_plugins

    def __get_classifier_output_attributes(self, profile):
        all_classifier_output_attributes = []
        if 'Classifier' in profile:
            all_classifier_plugins = self.__get_classifier_plugin_names(profile)
            for plugin_name in all_classifier_plugins:
                plugin = self._controlplane.get_plugin_by_name(plugin_name)
                attrib_names = list(plugin['OutputAttributes'].keys())
                if 'Label' in attrib_names:
                    attrib_names.pop(attrib_names.index('Label'))
                all_classifier_output_attributes.extend(attrib_names)

        return all_classifier_output_attributes


    def __get_labeler_plugin_names(self, profile):
        all_labeler_plugins = []
        main_plugin = profile['Labeler']['Name']
        all_labeler_plugins.append(main_plugin)

        if 'DependentPlugins' in profile['Labeler']:
            for dependent_plugin in profile['Labeler']['DependentPlugins']:
                all_labeler_plugins.append(dependent_plugin['Name'])

        return all_labeler_plugins

    def __get_labeler_output_attributes(self, profile):
        
        all_labeler_output_attributes = []
        if 'Labeler' in profile:
            all_labeler_plugins = self.__get_labeler_plugin_names(profile)
            for plugin_name in all_labeler_plugins:
                plugin = self._controlplane.get_plugin_by_name(plugin_name)
                attrib_names = list(plugin['OutputAttributes'].keys())
                if 'Label' in attrib_names:
                    attrib_names.pop(attrib_names.index('Label'))
                all_labeler_output_attributes.extend(attrib_names)

        return all_labeler_output_attributes

    def __get_featurer_plugin_names(self, profile):
        all_featurer_plugins = []
        main_plugin = profile['Featurer']['Name']
        all_featurer_plugins.append(main_plugin)

        if 'DependentPlugins' in profile['Featurer']:
            for dependent_plugin in profile['Featurer']['DependentPlugins']:
                all_featurer_plugins.append(dependent_plugin['Name'])

        return all_featurer_plugins

    def __get_featurer_output_attributes(self, profile):
        
        all_featurer_output_attributes = []
        if 'Featurer' in profile:
            all_featurer_plugins = self.__get_featurer_plugin_names(profile)
            for plugin_name in all_featurer_plugins:
                plugin = self._controlplane.get_plugin_by_name(plugin_name)
                attrib_names = list(plugin['OutputAttributes'].keys())
                if 'Label' in attrib_names:
                    attrib_names.pop(attrib_names.index('Label'))
                all_featurer_output_attributes.extend(attrib_names)

        return all_featurer_output_attributes
    

    def generate_event_data(self):
        '''
            Generates the Event Data Export in JSON format
        '''
        event_data_export = {}
        event_payload = self._build_event_data()
        segment_payload = self._get_all_segments_for_event()
        event_data_export["Event"] = event_payload
        event_data_export["Segments"] = segment_payload

        return event_data_export
        
        
    def _build_event_data(self):

        event_info = self._get_additional_event_data()
        profile = self._get_profile()
        all_plugin_output_attributes, all_plugin_output_attribute_names = self._get_all_plugin_output_attributes()

        event = {}

        event['Name'] = event_info['Name']
        event['Id'] = event_info['Id']
        event['Program'] = event_info['Program']
        event['Start'] = event_info['Start']
        event['AudioTracksFound'] = event_info['AudioTracks']
        event['AllOutputAttributes'] = all_plugin_output_attributes

        if 'ProgramId' in event_info:
            event['ProgramId'] = event_info['ProgramId']
        event['Profile'] = profile
        if 'SourceVideoMetadata' in event_info:
            event['SourceVideoMetadata'] = event_info['SourceVideoMetadata']
        
        return event