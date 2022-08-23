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
        plugins_in_profile, all_plugin_output_attribute_names = self._get_all_plugin_info()
        print(event_name)
        print(program_name)
        print(classifier)
        print(json.dumps(all_plugin_output_attribute_names))
        print(json.dumps(plugins_in_profile))

        segments = []
        temp_segments_dict = self._dataplane.get_all_event_segments_for_export(event_name, program_name, classifier, list(all_plugin_output_attribute_names), list(plugins_in_profile))
        segments = temp_segments_dict['Segments']

        while temp_segments_dict['LastStartValue']:
            temp_segments_dict = self._dataplane.get_all_event_segments_for_export(event_name, program_name, classifier, list(all_plugin_output_attribute_names), list(plugins_in_profile), temp_segments_dict['LastStartValue'])
            segments.extend(temp_segments_dict['Segments'])

        return segments

    def _get_all_plugin_info(self):
        '''
            Gets all the Output Attributes from Plugins based on the Profile
        '''
        
        # Get Plugins Classifier/Labeller/Featurer
        # For each get Output Attributes including from their Dependent Plugins
        profile = self._event['detail']['Event']['EventInfo']['Profile']
        all_optimizer_plugins, all_optimizer_output_attributes = self.__get_optimizer_output_attributes(profile)
        all_classifier_plugins, all_classifier_output_attributes = self.__get_classifier_output_attributes(profile)
        all_labeler_plugins, all_labeler_output_attributes = self.__get_labeler_output_attributes(profile)
        all_featurer_plugins, all_featurer_output_attributes = self.__get_featurer_output_attributes(profile)

        all_output_attribute_names = []

        all_output_attribute_names.extend(all_optimizer_output_attributes)
        all_output_attribute_names.extend(all_labeler_output_attributes)
        all_output_attribute_names.extend(all_featurer_output_attributes)
        all_output_attribute_names.extend(all_classifier_output_attributes)

        all_plugins_in_profile = []
        all_plugins_in_profile.extend(all_optimizer_plugins)
        all_plugins_in_profile.extend(all_classifier_plugins)
        all_plugins_in_profile.extend(all_labeler_plugins)
        all_plugins_in_profile.extend(all_featurer_plugins)

        return all_plugins_in_profile, all_output_attribute_names

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
        all_classifier_plugins = []
        if 'Classifier' in profile:
            all_classifier_plugins = self.__get_classifier_plugin_names(profile)
            for plugin_name in all_classifier_plugins:
                plugin = self._controlplane.get_plugin_by_name(plugin_name)
                attrib_names = list(plugin['OutputAttributes'].keys())
                if 'Label' in attrib_names:
                    attrib_names.pop(attrib_names.index('Label'))
                all_classifier_output_attributes.extend(attrib_names)

        return all_classifier_plugins, all_classifier_output_attributes

    def __get_optimizer_plugin_names(self, profile):
        all_optimizer_plugins = []
        main_plugin = profile['Optimizer']['Name']
        all_optimizer_plugins.append(main_plugin)

        if 'DependentPlugins' in profile['Optimizer']:
            for dependent_plugin in profile['Optimizer']['DependentPlugins']:
                all_optimizer_plugins.append(dependent_plugin['Name'])

        return all_optimizer_plugins

    def __get_optimizer_output_attributes(self, profile):
        all_optimizer_output_attributes = []
        all_optimizer_plugins = []
        if 'Optimizer' in profile:
            all_optimizer_plugins = self.__get_optimizer_plugin_names(profile)
            for plugin_name in all_optimizer_plugins:
                plugin = self._controlplane.get_plugin_by_name(plugin_name)
                attrib_names = list(plugin['OutputAttributes'].keys())
                if 'Label' in attrib_names:
                    attrib_names.pop(attrib_names.index('Label'))
                all_optimizer_output_attributes.extend(attrib_names)

        return all_optimizer_plugins, all_optimizer_output_attributes

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
        all_labeler_plugins = []
        if 'Labeler' in profile:
            all_labeler_plugins = self.__get_labeler_plugin_names(profile)
            for plugin_name in all_labeler_plugins:
                plugin = self._controlplane.get_plugin_by_name(plugin_name)
                attrib_names = list(plugin['OutputAttributes'].keys())
                if 'Label' in attrib_names:
                    attrib_names.pop(attrib_names.index('Label'))
                all_labeler_output_attributes.extend(attrib_names)

        return all_labeler_plugins, all_labeler_output_attributes

    def __get_featurer_plugin_names(self, profile):
        all_featurer_plugins = []

        for featurer in profile['Featurers']:
            main_plugin = featurer['Name']
            all_featurer_plugins.append(main_plugin)

            if 'DependentPlugins' in featurer:
                for dependent_plugin in featurer['DependentPlugins']:
                    all_featurer_plugins.append(dependent_plugin['Name'])

        return all_featurer_plugins

    def __get_featurer_output_attributes(self, profile):
        
        all_featurer_output_attributes = []
        all_featurer_plugins = []
        if 'Featurers' in profile:
            all_featurer_plugins = self.__get_featurer_plugin_names(profile)
            for plugin_name in all_featurer_plugins:
                plugin = self._controlplane.get_plugin_by_name(plugin_name)
                attrib_names = list(plugin['OutputAttributes'].keys())
                if 'Label' in attrib_names:
                    attrib_names.pop(attrib_names.index('Label'))
                all_featurer_output_attributes.extend(attrib_names)

        return all_featurer_plugins, all_featurer_output_attributes
    

    def generate_event_data(self):
        '''
            Generates the Event Data Export in JSON format
        '''
        event_data_export = {}
        event_payload = self._build_event_data()

        # Get all segments which have Output Attributes based on the Plugin Config for the Event profile
        segment_payload = self._get_all_segments_for_event()

        event_data_export["Event"] = event_payload
        event_data_export["Segments"] = segment_payload

        return event_data_export
        
        
    def _build_event_data(self):

        event_info = self._get_additional_event_data()
        profile = self._get_profile()
        all_plugins_in_profile, all_plugin_output_attribute_names = self._get_all_plugin_info()

        event = {}

        event['Name'] = event_info['Name']
        event['Id'] = event_info['Id']
        event['Program'] = event_info['Program']
        event['Start'] = event_info['Start']
        event['AudioTracksFound'] = event_info['AudioTracks']
        event['AllOutputAttributes'] = all_plugin_output_attribute_names
        event['EmbeddedTimecodeSource'] = "NOT_EMBEDDED" if 'TimecodeSource' not in event_info else event_info['TimecodeSource']

        if 'ProgramId' in event_info:
            event['ProgramId'] = event_info['ProgramId']
        event['Profile'] = profile
        if 'SourceVideoMetadata' in event_info:
            event['SourceVideoMetadata'] = event_info['SourceVideoMetadata']
        
        return event