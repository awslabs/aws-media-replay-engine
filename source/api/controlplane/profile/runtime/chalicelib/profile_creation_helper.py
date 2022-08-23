import json
import os
import random
import string
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from chalice import BadRequestError, ConflictError, NotFoundError

PLUGIN_TABLE_NAME = os.environ['PLUGIN_TABLE_NAME']

ddb_resource = boto3.resource("dynamodb")

def get_plugin_configuration_ddb(plugin: dict) -> dict:
    if "Configuration" in plugin:
        return plugin['Configuration']
    try:
        plugin_table = ddb_resource.Table(PLUGIN_TABLE_NAME)
        get_key = {
            "Name": plugin["Name"],
            "Version": 'v0'
        }
        plugin_response = plugin_table.get_item(Key=get_key)
        if 'Item' in plugin_response: # Limit query to 1; make sure we have just 1 item
            default_plugin = plugin_response['Item']
            if 'Configuration' in default_plugin:
                return default_plugin['Configuration']
            return {}
        raise Exception("Plugin does not exist")
    except Exception as e:
        print(e)
        raise Exception("Unable to get default plugin configuration") from e
        
# TO DO Refactor logic to remove additional DB call and use config from plugin definitions
def get_plugin_configuration(plugin: dict, plugin_definitions: dict) -> dict:
    if "Configuration" in plugin and plugin['Configuration']:
        return plugin['Configuration']
    try:
        default_plugin = plugin_definitions[plugin['Name']]
        if 'Configuration' in default_plugin:
            print(f"Adding configuration for plugin {plugin['Name']}")
            return default_plugin['Configuration']
        return {}
    except Exception as e:
        print(e)
        raise Exception("Unable to get default plugin configuration") from e

# TO DO Refactor logic to add version and configuration in a loop
def get_plugin_version(plugin: dict, plugin_definitions: dict) -> dict:
    try:
        default_plugin = plugin_definitions[plugin['Name']]
        print(f"Adding version for plugin {plugin['Name']}")
        return default_plugin['Latest']
    except Exception as e:
        print(e)
        raise Exception("Unable to get default plugin configuration") from e

# TO DO Refactor logic to remove additional DB call and use config from plugin definitions
def enrich_plugin_from_plugin_definitions(parent_obj: dict, plugin_definitions: dict):
    parent_obj["Version"] = get_plugin_version(parent_obj,plugin_definitions)
    parent_obj["Configuration"] = get_plugin_configuration(parent_obj,plugin_definitions)
    if "DependentPlugins" in parent_obj:
        for i, d_plugin in enumerate(parent_obj["DependentPlugins"]):
            parent_obj["DependentPlugins"][i]["Version"] = get_plugin_version(d_plugin, plugin_definitions)
            parent_obj["DependentPlugins"][i]["Configuration"] = get_plugin_configuration(d_plugin, plugin_definitions)


def enrich_profile(profile: dict, plugin_definitions: dict):
    if "Classifier" in profile:
        enrich_plugin_from_plugin_definitions(profile["Classifier"], plugin_definitions)
    if "Optimizer" in profile:
        enrich_plugin_from_plugin_definitions(profile["Optimizer"], plugin_definitions)
    if "Labeler" in profile:
        enrich_plugin_from_plugin_definitions(profile["Labeler"], plugin_definitions)
    if "Featurers" in profile:
        for p_index, featurer in enumerate(profile["Featurers"]):
            enrich_plugin_from_plugin_definitions(profile["Featurers"][p_index],plugin_definitions)