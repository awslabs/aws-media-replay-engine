#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import json
import random
import boto3
import string
from decimal import Decimal
from chalice import BadRequestError, NotFoundError, ConflictError

PROBE_VIDEO_LAMBDA_ARN = os.environ['PROBE_VIDEO_LAMBDA_ARN']
MULTI_CHUNK_HELPER_LAMBDA_ARN = os.environ['MULTI_CHUNK_HELPER_LAMBDA_ARN']
PLUGIN_OUTPUT_HANDLER_LAMBDA_ARN = os.environ['PLUGIN_OUTPUT_HANDLER_LAMBDA_ARN']
WORKFLOW_ERROR_HANDLER_LAMBDA_ARN = os.environ['WORKFLOW_ERROR_HANDLER_LAMBDA_ARN']
MODEL_TABLE_NAME = os.environ['MODEL_TABLE_NAME']
PLUGIN_TABLE_NAME = os.environ['PLUGIN_TABLE_NAME']
CLIP_GENERATION_STATE_MACHINE_ARN = os.environ['CLIP_GENERATION_STATE_MACHINE_ARN']

ddb_resource = boto3.resource("dynamodb")


def get_multi_level_d_plugins(level, p_plugins, d_plugins, plugins_level_list, d_plugins_def_dict, plugin_class={}, shortened_plugin_class={}, d_plugins_list=[], batch_get_keys=[]):
    print(f"Collecting dependent plugins for level '{level}' with parent plugin(s) '{p_plugins}'")

    items = []
    d_plugin_obj_list = []

    for d_plugin in d_plugins:
        if plugin_class:
            d_plugin_obj = {
                "Name": d_plugin["Name"],
                "Configuration": d_plugin["Configuration"] if "Configuration" in d_plugin else {},
                "DependentFor": d_plugin["DependentFor"]
            }

            if "ModelEndpoint" in d_plugin and isinstance(d_plugin["ModelEndpoint"], dict):
                d_plugin_obj["ModelEndpoint"] = get_model_endpoint_from_ddb(d_plugin["ModelEndpoint"])

            if d_plugin["Name"] not in d_plugins_def_dict:
                d_plugins_def_dict[d_plugin["Name"]] = d_plugin_obj
                shortened_plugin_class["DependentPlugins"].append(d_plugins_def_dict[d_plugin["Name"]])
            else:
                d_plugins_def_dict[d_plugin["Name"]]["DependentFor"].extend(item for item in d_plugin_obj["DependentFor"] if item not in d_plugins_def_dict[d_plugin["Name"]]["DependentFor"])
            
            if d_plugin["Name"] not in d_plugins_list:
                d_plugins_list.append(d_plugin["Name"])
                batch_get_keys.append({"Name": d_plugin["Name"], "Version": "v0"})

        is_contains = any(item in d_plugin["DependentFor"] for item in p_plugins)

        '''
        if is_contains and d_plugin["Name"] not in items:
            items.append(d_plugin["Name"])
            d_plugin_obj_list.append(d_plugins_def_dict[d_plugin["Name"]])
        '''

        if is_contains:
            if not plugin_class:
                for p_plugin in p_plugins: # Check for circular dependency
                    if "Level" not in d_plugins_def_dict[p_plugin]:
                        d_plugins_def_dict[p_plugin]["Level"] = level - 1
                    elif (level - 1) != d_plugins_def_dict[p_plugin]["Level"]:
                        raise Exception(f"Possible circular dependency found between the dependent plugins '{p_plugin}' and '{d_plugin['Name']}'")

            if d_plugin["Name"] not in items:
                if "Level" not in d_plugins_def_dict[d_plugin["Name"]]:
                    d_plugins_def_dict[d_plugin["Name"]]["Level"] = level

                items.append(d_plugin["Name"])
                d_plugin_obj_list.append(d_plugins_def_dict[d_plugin["Name"]])

    if items:
        plugins_level_list.append(d_plugin_obj_list)
        return get_multi_level_d_plugins(level + 1, items, d_plugins, plugins_level_list, d_plugins_def_dict)

    return plugins_level_list


def profile_state_definition_helper(name, profile):
    plugins_list = []
    d_plugins_list = []
    batch_get_keys = []

    internal_lambda_arns = {
        "ProbeVideo": PROBE_VIDEO_LAMBDA_ARN,
        "MultiChunkHelper": MULTI_CHUNK_HELPER_LAMBDA_ARN,
        "PluginOutputHandler": PLUGIN_OUTPUT_HANDLER_LAMBDA_ARN,
        "WorkflowErrorHandler": WORKFLOW_ERROR_HANDLER_LAMBDA_ARN
    }

    shortened_profile = {
        "Name": name,
        "ChunkSize": profile["ChunkSize"],
        "MaxSegmentLengthSeconds": profile["MaxSegmentLengthSeconds"],
        "ProcessingFrameRate": profile["ProcessingFrameRate"]
    }

    # Classifier
    classifier = profile["Classifier"]

    if "ModelEndpoint" in classifier and isinstance(classifier["ModelEndpoint"], dict):
        classifier["ModelEndpoint"] = get_model_endpoint_from_ddb(classifier["ModelEndpoint"])

    shortened_classifier = {
        "Name": classifier["Name"],
        "Configuration": classifier["Configuration"] if "Configuration" in classifier else {},
        "DependentPlugins": []
    }
    plugins_list.append(classifier["Name"])
    batch_get_keys.append({"Name": classifier["Name"], "Version": "v0"})

    if "DependentPlugins" in classifier:
        classifier["DependentPlugins"] = get_multi_level_d_plugins(1, [classifier["Name"]], classifier["DependentPlugins"], [], {}, classifier, shortened_classifier, d_plugins_list, batch_get_keys)
    
    shortened_profile["Classifier"] = shortened_classifier

    # Optimizer
    optimizer = {}
    if "Optimizer" in profile and profile["Optimizer"]:
        optimizer = profile["Optimizer"]

        if "ModelEndpoint" in optimizer and isinstance(optimizer["ModelEndpoint"], dict):
            optimizer["ModelEndpoint"] = get_model_endpoint_from_ddb(optimizer["ModelEndpoint"])

        shortened_optimizer = {
            "Name": optimizer["Name"],
            "Configuration": optimizer["Configuration"] if "Configuration" in optimizer else {},
            "DependentPlugins": []
        }
        plugins_list.append(optimizer["Name"])
        batch_get_keys.append({"Name": optimizer["Name"], "Version": "v0"})

        if "DependentPlugins" in optimizer:
            optimizer["DependentPlugins"] = get_multi_level_d_plugins(1, [optimizer["Name"]], optimizer["DependentPlugins"], [], {}, optimizer, shortened_optimizer, d_plugins_list, batch_get_keys)

        shortened_profile["Optimizer"] = shortened_optimizer

    # Labeler
    labeler = {}
    if "Labeler" in profile and profile["Labeler"]:
        labeler = profile["Labeler"]

        if "ModelEndpoint" in labeler and isinstance(labeler["ModelEndpoint"], dict):
            labeler["ModelEndpoint"] = get_model_endpoint_from_ddb(labeler["ModelEndpoint"])

        shortened_labeler = {
            "Name": labeler["Name"],
            "Configuration": labeler["Configuration"] if "Configuration" in labeler else {},
            "DependentPlugins": []
        }
        plugins_list.append(labeler["Name"])
        batch_get_keys.append({"Name": labeler["Name"], "Version": "v0"})

        if "DependentPlugins" in labeler:
            labeler["DependentPlugins"] = get_multi_level_d_plugins(1, [labeler["Name"]], labeler["DependentPlugins"], [], {}, labeler, shortened_labeler, d_plugins_list, batch_get_keys)

        shortened_profile["Labeler"] = shortened_labeler

    # Featurers
    featurers = []
    if "Featurers" in profile and profile["Featurers"]:
        shortened_profile["Featurers"] = []

        featurers = profile["Featurers"]

        for index, featurer in enumerate(featurers):
            if featurer["Name"] in plugins_list:
                raise ConflictError(
                    f"Unable to create profile '{name}': Provided list of Featurers contains duplicates")

            if "ModelEndpoint" in featurer and isinstance(featurer["ModelEndpoint"], dict):
                featurers[index]["ModelEndpoint"] = get_model_endpoint_from_ddb(featurer["ModelEndpoint"])

            shortened_featurer = {
                "Name": featurer["Name"],
                "Configuration": featurer["Configuration"] if "Configuration" in featurer else {},
                "DependentPlugins": []
            }
            plugins_list.append(featurer["Name"])

            if featurer["Name"] not in d_plugins_list:
                batch_get_keys.append({"Name": featurer["Name"], "Version": "v0"})

            if "DependentPlugins" in featurer:
                featurer["DependentPlugins"] = get_multi_level_d_plugins(1, [featurer["Name"]], featurer["DependentPlugins"], [], {}, featurer, shortened_featurer, d_plugins_list, batch_get_keys)

            shortened_profile["Featurers"].append(shortened_featurer)

    # Retrieve the state machine definition of all the plugins present in the request
    response = ddb_resource.batch_get_item(
        RequestItems={
            PLUGIN_TABLE_NAME: {
                "Keys": batch_get_keys,
                "ConsistentRead": True,
                "ProjectionExpression": "#Name, #Class, #ExecutionType, #SupportedMediaType, #StateDefinition, #DependentPlugins, #Enabled, #Latest",
                "ExpressionAttributeNames": {
                    "#Name": "Name",
                    "#Class": "Class",
                    "#ExecutionType": "ExecutionType",
                    "#SupportedMediaType": "SupportedMediaType",
                    "#StateDefinition": "StateDefinition",
                    "#DependentPlugins": "DependentPlugins",
                    "#Enabled": "Enabled",
                    "#Latest": "Latest"
                }
            }
        }
    )

    responses = response["Responses"][PLUGIN_TABLE_NAME]

    while "UnprocessedKeys" in responses:
        response = ddb_resource.batch_get_item(
            RequestItems=responses["UnprocessedKeys"]
        )

        responses.extend(response["Responses"][PLUGIN_TABLE_NAME])

    plugin_definitions = {}

    for item in responses:
        plugin_definitions[item["Name"]] = {
            "Class": item["Class"],
            "ExecutionType": item["ExecutionType"],
            "SupportedMediaType": item["SupportedMediaType"],
            "StateDefinition": item["StateDefinition"],
            "DependentPlugins": item["DependentPlugins"] if "DependentPlugins" in item else [],
            "Enabled": item["Enabled"],
            "Latest": f"v{item['Latest']}"
        }

    # Check if any of the plugins present in the request does not exist or is disabled in the system
    for plugin in plugins_list:
        if plugin not in plugin_definitions:
            raise NotFoundError(f"Unable to create profile '{name}': Plugin '{plugin}' not found in the system")

        elif not plugin_definitions[plugin]["Enabled"]:
            raise BadRequestError(f"Unable to create profile '{name}': Plugin '{plugin}' is disabled in the system")

        else:
            for d_plugin in plugin_definitions[plugin]["DependentPlugins"]:
                if d_plugin not in d_plugins_list:
                    raise BadRequestError(
                        f"Unable to create profile '{name}': Required Dependent plugin '{d_plugin}' for plugin '{plugin}' not present in the request")

                elif d_plugin not in plugin_definitions:
                    raise NotFoundError(
                        f"Unable to create profile '{name}': Dependent plugin '{d_plugin}' for plugin '{plugin}' not found in the system")

                elif not plugin_definitions[d_plugin]["Enabled"]:
                    raise BadRequestError(
                        f"Unable to create profile '{name}': Dependent plugin '{d_plugin}' for plugin '{plugin}' is disabled in the system")

    # Add SupportedMediaType to all the DependentPlugins in the shortened_profile
    for index, d_plugin in enumerate(shortened_profile["Classifier"]["DependentPlugins"]):
        shortened_profile["Classifier"]["DependentPlugins"][index]["SupportedMediaType"] = \
            plugin_definitions[d_plugin["Name"]]["SupportedMediaType"]

    if "Optimizer" in shortened_profile:
        for index, d_plugin in enumerate(shortened_profile["Optimizer"]["DependentPlugins"]):
            shortened_profile["Optimizer"]["DependentPlugins"][index]["SupportedMediaType"] = \
                plugin_definitions[d_plugin["Name"]]["SupportedMediaType"]

    if "Labeler" in shortened_profile:
        for index, d_plugin in enumerate(shortened_profile["Labeler"]["DependentPlugins"]):
            shortened_profile["Labeler"]["DependentPlugins"][index]["SupportedMediaType"] = \
                plugin_definitions[d_plugin["Name"]]["SupportedMediaType"]

    if "Featurers" in shortened_profile:
        for p_index in range(len(shortened_profile["Featurers"])):
            for c_index, d_plugin in enumerate(shortened_profile["Featurers"][p_index]["DependentPlugins"]):
                shortened_profile["Featurers"][p_index]["DependentPlugins"][c_index]["SupportedMediaType"] = \
                    plugin_definitions[d_plugin["Name"]]["SupportedMediaType"]

    return (json.dumps(
        generate_profile_state_definition(name, classifier, optimizer, labeler, featurers, plugin_definitions,
                                          shortened_profile, internal_lambda_arns)), plugin_definitions)


def get_model_endpoint_from_ddb(model):
    model_name = model["Name"]
    model_version = model["Version"]

    model_table = ddb_resource.Table(MODEL_TABLE_NAME)

    response = model_table.get_item(
        Key={
            "Name": model_name,
            "Version": model_version
        },
        ConsistentRead=True
    )

    if "Item" not in response:
        raise NotFoundError(f"Model endpoint '{model_name}' with version '{model_version}' not found")

    elif not response["Item"]["Enabled"]:
        raise BadRequestError(f"Model endpoint '{model_name}' with version '{model_version}' is disabled in the system")

    return response["Item"]["Endpoint"]


def generate_profile_state_definition(profile_name, classifier, optimizer, labeler, featurers, plugin_definitions, shortened_profile, internal_lambda_arns):
    print(f"Generating state machine definition for profile '{profile_name}'")
    
    main_branch_list = []
    classifier_labeler_optimizer_branch_list = []

    is_labeler_present = False
    is_labeler_dependent_present = False

    # Check if Labeler (and its dependencies) is present in the profile
    if labeler:
        is_labeler_present = True
        labeler_plugin_name = labeler["Name"]

        if "DependentPlugins" in labeler:
            is_labeler_dependent_present = True

    # Classifier
    classifier_plugin_name = classifier["Name"]
    print(f"State machine generation for the Classifier plugin '{classifier_plugin_name}' in progress.")
    classifier_plugin_definition = get_plugin_state_definition(classifier, "Classifier", plugin_definitions[classifier_plugin_name], shortened_profile)
    
    # Remove the 'End' key and add the 'Next' key in the state definition
    classifier_plugin_definition.pop("End", None)
    classifier_plugin_definition["Next"] = "PluginOutputHandler"

    multi_chunk_helper_task = {
        "Type": "Task",
        "Resource": "arn:aws:states:::lambda:invoke",
        "Parameters": {
            "FunctionName": internal_lambda_arns["MultiChunkHelper"],
            "Payload": {
                "Event.$": "$.Event",
                "Input.$": "$.Input",
                "Profile": shortened_profile,
                "MultiChunk": {
                    "PluginClass": "Classifier",
                    "WaitFactor": 5
                }
            }
        },
        "OutputPath": "$.Payload",
        "Retry": [
            {
                "ErrorEquals": [
                    "Lambda.ServiceException",
                    "Lambda.AWSLambdaException",
                    "Lambda.SdkClientException",
                    "Lambda.Unknown",
                    "MREExecutionError"
                ],
                "IntervalSeconds": 2,
                "MaxAttempts": 6,
                "BackoffRate": 2
            }
        ],
        "Next": "CheckMultiChunkStatus"
    }

    plugin_output_handler_task = {
        "Type": "Task",
        "Resource": "arn:aws:states:::lambda:invoke",
        "Parameters": {
            "FunctionName": internal_lambda_arns["PluginOutputHandler"],
            "Payload": {
                "Event.$": "$.Event",
                "Input.$": "$.Input",
                "Profile": shortened_profile,
                "Output.$": "$.Output"
            }
        },
        "ResultPath": None,
        "Retry": [
            {
                "ErrorEquals": [
                    "Lambda.ServiceException",
                    "Lambda.AWSLambdaException",
                    "Lambda.SdkClientException",
                    "Lambda.Unknown",
                    "MREExecutionError"
                ],
                "IntervalSeconds": 2,
                "MaxAttempts": 6,
                "BackoffRate": 2
            }
        ],
        "Next": "GenerateOriginalClips"
    }

    # Classifier and/or Labeler DependentPlugins
    if "DependentPlugins" in classifier or is_labeler_dependent_present:
        d_plugins_branch_list = []

        if "DependentPlugins" in classifier:
            print(f"DependentPlugins State machine generation for the Classifier plugin '{classifier_plugin_name}' in progress.")
            d_plugins_branch_list.extend(get_multi_level_state_definition_branch_list(classifier["DependentPlugins"], "Featurer", plugin_definitions, shortened_profile))

        if is_labeler_dependent_present:
            print(f"DependentPlugins State machine generation for the Labeler plugin '{labeler_plugin_name}' in progress.")
            d_plugins_branch_list.extend(get_multi_level_state_definition_branch_list(labeler["DependentPlugins"], "Featurer", plugin_definitions, shortened_profile))

        classifier_labeler_branch = {
            "StartAt": "ClassifierLabelerDependentPluginsTask",
            "States": {
                "ClassifierLabelerDependentPluginsTask": {
                    "Type": "Parallel",
                    "Branches": d_plugins_branch_list,
                    "Next": "ClassifierLabelerCollectDependentPluginsResult"
                },
                "ClassifierLabelerCollectDependentPluginsResult": {
                    "Type": "Pass",
                    "Parameters": {
                        "Event.$": "$[0].Event",
                        "Input.$": "$[0].Input"
                    },
                    "Next": "MultiChunkHelper"
                },
                "MultiChunkHelper": multi_chunk_helper_task,
                "CheckMultiChunkStatus": {
                    "Type": "Choice",
                    "Choices": [
                        {
                            "Variable": "$.MultiChunk.IsCompleted",
                            "BooleanEquals": False,
                            "Next": "Wait"
                        }
                    ],
                    "Default": classifier_plugin_name
                },
                "Wait": {
                    "Type": "Wait",
                    "SecondsPath": "$.MultiChunk.WaitSeconds",
                    "Next": "MultiChunkHelper"
                },
                classifier_plugin_name: classifier_plugin_definition,
                "PluginOutputHandler": plugin_output_handler_task,
                "GenerateOriginalClips": {
                    "Type": "Task",
                    "Resource": "arn:aws:states:::states:startExecution",
                    "Parameters": {
                        "StateMachineArn": CLIP_GENERATION_STATE_MACHINE_ARN,
                        "Input": {
                            "GenerateOriginal": True,
                            "Event.$": "$.Event",
                            "Input.$": "$.Input",
                            "Segments.$": "$.Output.Results",
                            "Profile": shortened_profile
                        }
                    },
                    "ResultPath": None,
                    "End": True
                }
            }
        }

    else:
        classifier_labeler_branch = {
            "StartAt": "MultiChunkHelper",
            "States": {
                "MultiChunkHelper": multi_chunk_helper_task,
                "CheckMultiChunkStatus": {
                    "Type": "Choice",
                    "Choices": [
                        {
                            "Variable": "$.MultiChunk.IsCompleted",
                            "BooleanEquals": False,
                            "Next": "Wait"
                        }
                    ],
                    "Default": classifier_plugin_name
                },
                "Wait": {
                    "Type": "Wait",
                    "SecondsPath": "$.MultiChunk.WaitSeconds",
                    "Next": "MultiChunkHelper"
                },
                classifier_plugin_name: classifier_plugin_definition,
                "PluginOutputHandler": plugin_output_handler_task,
                "GenerateOriginalClips": {
                    "Type": "Task",
                    "Resource": "arn:aws:states:::states:startExecution",
                    "Parameters": {
                        "StateMachineArn": CLIP_GENERATION_STATE_MACHINE_ARN,
                        "Input": {
                            "GenerateOriginal": True,
                            "Event.$": "$.Event",
                            "Input.$": "$.Input",
                            "Segments.$": "$.Output.Results",
                            "Profile": shortened_profile
                        }
                    },
                    "ResultPath": None,
                    "End": True
                }
            }
        }

    if is_labeler_present:
        print(f"State machine generation for the Labeler plugin '{labeler_plugin_name}' in progress.")

        labeler_plugin_definition = get_plugin_state_definition(labeler, "Labeler", plugin_definitions[labeler_plugin_name], shortened_profile)
    
        # Remove the 'End' key and add the 'Next' key in the GenerateOriginalClips state definition
        classifier_labeler_branch["States"]["GenerateOriginalClips"].pop("End", None)
        classifier_labeler_branch["States"]["GenerateOriginalClips"]["Next"] = labeler_plugin_name

        classifier_labeler_branch["States"][labeler_plugin_name] = labeler_plugin_definition

    else:
        print("Skipping state machine generation for Labeler as it is not included in the profile")

    classifier_labeler_optimizer_branch_list.append(classifier_labeler_branch)

    # Optimizer
    if optimizer:
        optimizer_plugin_name = optimizer["Name"]
        print(f"State machine generation for the Optimizer plugin '{optimizer_plugin_name}' in progress.")
        optimizer_plugin_definition = get_plugin_state_definition(optimizer, "Optimizer", plugin_definitions[optimizer_plugin_name], shortened_profile)
        is_audio_media_type = True if plugin_definitions[optimizer_plugin_name]["SupportedMediaType"] == "Audio" else False

        # Remove the 'End' key and add the 'Next' key in the state definition
        optimizer_plugin_definition.pop("End", None)
        optimizer_plugin_definition["Next"] = "GenerateOptimizedClips"

        # Optimizer DependentPlugins
        if "DependentPlugins" in optimizer:
            print(f"DependentPlugins State machine generation for the Optimizer plugin '{optimizer_plugin_name}' in progress.")

            d_plugins_branch_list = get_multi_level_state_definition_branch_list(optimizer["DependentPlugins"], "Featurer", plugin_definitions, shortened_profile)

            optimizer_d_branch = {
                "StartAt": "OptimizerDependentPluginsTask",
                "States": {
                    "OptimizerDependentPluginsTask": {
                        "Type": "Parallel",
                        "Branches": d_plugins_branch_list,
                        "End": True
                    }
                }
            }

            classifier_labeler_optimizer_branch_list.append(optimizer_d_branch)

        if is_audio_media_type:
            plugin_definition_parameters = optimizer_plugin_definition.pop("Parameters", None)
            plugin_lambda_function = plugin_definition_parameters["FunctionName"]
            optimizer_plugin_definition["Resource"] = plugin_lambda_function
            optimizer_plugin_definition["ResultSelector"] = {
                "PluginName.$": "$.Output.PluginName",
                "PluginClass.$": "$.Output.PluginClass",
                "ExecutionType.$": "$.Output.ExecutionType",
                "DependentPlugins.$": "$.Output.DependentPlugins",
                "ModelEndpoint.$": "$.Output.ModelEndpoint",
                "Configuration.$": "$.Output.Configuration",
                "Results.$": "$.Output.Results"
            }
            optimizer_plugin_definition["ResultPath"] = "$.Output"
            optimizer_plugin_definition.pop("OutputPath", None)

            map_parameters = plugin_definition_parameters["Payload"]
            map_parameters["TrackNumber.$"] = "$$.Map.Item.Value"

            optimize_segment_task = {
                "Type": "Map",
                "ItemsPath": "$.Event.AudioTracks",
                "Parameters": map_parameters,
                "Iterator": {
                    "StartAt": optimizer_plugin_name,
                    "States": {
                        optimizer_plugin_name: optimizer_plugin_definition,
                        "GenerateOptimizedClips": {
                            "Type": "Task",
                            "Resource": "arn:aws:states:::states:startExecution",
                            "Parameters": {
                                "StateMachineArn": CLIP_GENERATION_STATE_MACHINE_ARN,
                                "Input": {
                                    "GenerateOriginal": False,
                                    "Event.$": "$.Event",
                                    "Input.$": "$.Input",
                                    "Segments.$": "$.Output.Results",
                                    "Profile": shortened_profile,
                                    "TrackNumber.$": "$.TrackNumber"
                                }
                            },
                            "ResultPath": None,
                            "End": True
                        }
                    }
                },
                "End": True
            }

            classifier_labeler_optimizer_branch = {
                "StartAt": "ClassifierLabelerOptimizerParallelTask",
                "States": {
                    "ClassifierLabelerOptimizerParallelTask": {
                        "Type": "Parallel",
                        "Branches": classifier_labeler_optimizer_branch_list,
                        "Next": "CollectClassifierLabelerOptimizerParallelTaskResult"
                    },
                    "CollectClassifierLabelerOptimizerParallelTaskResult": {
                        "Type": "Pass",
                        "Parameters": {
                            "Event.$": "$[0].Event",
                            "Input.$": "$[0].Input"
                        },
                        "Next": "OptimizeSegmentTask"
                    },
                    "OptimizeSegmentTask": optimize_segment_task
                }
            }
        
        else:
            classifier_labeler_optimizer_branch = {
                "StartAt": "ClassifierLabelerOptimizerParallelTask",
                "States": {
                    "ClassifierLabelerOptimizerParallelTask": {
                        "Type": "Parallel",
                        "Branches": classifier_labeler_optimizer_branch_list,
                        "Next": "CollectClassifierLabelerOptimizerParallelTaskResult"
                    },
                    "CollectClassifierLabelerOptimizerParallelTaskResult": {
                        "Type": "Pass",
                        "Parameters": {
                            "Event.$": "$[0].Event",
                            "Input.$": "$[0].Input"
                        },
                        "Next": optimizer_plugin_name
                    },
                    optimizer_plugin_name: optimizer_plugin_definition,
                    "GenerateOptimizedClips": {
                        "Type": "Task",
                        "Resource": "arn:aws:states:::states:startExecution",
                        "Parameters": {
                            "StateMachineArn": CLIP_GENERATION_STATE_MACHINE_ARN,
                            "Input": {
                                "GenerateOriginal": False,
                                "Event.$": "$.Event",
                                "Input.$": "$.Input",
                                "Segments.$": "$.Output.Results",
                                "Profile": shortened_profile
                            }
                        },
                        "ResultPath": None,
                        "End": True
                    }
                }
            }

    else:
        print("Skipping the State machine generation for Optimizer as it is not included in the profile")

        classifier_labeler_optimizer_branch = {
            "StartAt": "ClassifierLabelerOptimizerParallelTask",
            "States": {
                "ClassifierLabelerOptimizerParallelTask": {
                    "Type": "Parallel",
                    "Branches": classifier_labeler_optimizer_branch_list,
                    "End": True
                }
            }
        }

    main_branch_list.append(classifier_labeler_optimizer_branch)

    # Featurers
    if featurers:
        print("Featurers state machine generation in progress.")

        featurers_branch_list = get_featurers_state_definition_branch_list(featurers, "Featurer", plugin_definitions, shortened_profile)

        featurers_branch = {
            "StartAt": "FeaturersParallelTask",
            "States": {
                "FeaturersParallelTask": {
                    "Type": "Parallel",
                    "Branches": featurers_branch_list,
                    "End": True
                }
            }
        }

        main_branch_list.append(featurers_branch)

    else:
        print("Skipping state machine generation for Featurers as it is not included in the profile")

    main_state_definition = {
        "Comment": f"AWS MRE Processing Pipeline for profile {profile_name}",
        "StartAt": "ProbeVideo",
        "States": {
            "ProbeVideo": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": internal_lambda_arns["ProbeVideo"],
                    "Payload": {
                        "Event.$": "$.Event",
                        "Input.$": "$.Input",
                        "Profile": shortened_profile
                    }
                },
                "OutputPath": "$.Payload",
                "Retry": [
                    {
                    "ErrorEquals": [
                        "Lambda.ServiceException",
                        "Lambda.AWSLambdaException",
                        "Lambda.SdkClientException",
                        "Lambda.Unknown"
                    ],
                    "IntervalSeconds": 2,
                    "MaxAttempts": 6,
                    "BackoffRate": 2
                    }
                ],
                "Catch": [
                    {
                        "ErrorEquals": [
                            "States.ALL"
                        ],
                        "Next": "WorkflowErrorHandler",
                        "ResultPath": "$.Error"
                    }
                ],
                "Next": "MainParallelTask"
            },
            "MainParallelTask": {
                "Type": "Parallel",
                "Branches": main_branch_list,
                "Catch": [
                    {
                        "ErrorEquals": [
                            "States.ALL"
                        ],
                        "Next": "WorkflowErrorHandler",
                        "ResultPath": "$.Error"
                    }
                ],
                "End": True
            },
            "WorkflowErrorHandler": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": internal_lambda_arns["WorkflowErrorHandler"],
                    "Payload": {
                        "Event.$": "$.Event",
                        "Input.$": "$.Input",
                        "Profile": shortened_profile,
                        "Error.$": "$.Error"
                    }
                },
                "OutputPath": "$.Payload",
                "Retry": [
                    {
                    "ErrorEquals": [
                        "Lambda.ServiceException",
                        "Lambda.AWSLambdaException",
                        "Lambda.SdkClientException",
                        "Lambda.Unknown"
                    ],
                    "IntervalSeconds": 2,
                    "MaxAttempts": 6,
                    "BackoffRate": 2
                    }
                ],
                "End": True
            }
        }
    }

    return main_state_definition

def get_plugin_state_definition(plugin, expected_class, plugin_definition, shortened_profile):
    plugin_class = plugin_definition["Class"]
    plugin_execution_type = plugin_definition["ExecutionType"]
    plugin_state_definition = plugin_definition["StateDefinition"]

    plugin_name = plugin["Name"]
    model_endpoint = plugin["ModelEndpoint"] if "ModelEndpoint" in plugin else ""
    configuration = plugin["Configuration"] if "Configuration" in plugin else {}

    if expected_class and plugin_class != expected_class:
        raise Exception(f"Plugin '{plugin_name}' is not of class '{expected_class}'")

    if plugin_execution_type == "SyncModel" and len(model_endpoint.strip()) < 1:
        raise Exception(f"A valid 'ModelEndpoint' is required for plugin '{plugin_name}' as it belongs to the 'SyncModel' execution type")

    plugin_state_definition = plugin_state_definition.replace("%%PLUGIN_MODEL_ENDPOINT%%", model_endpoint)
    plugin_state_definition = plugin_state_definition.replace("\"%%PLUGIN_CONFIGURATION%%\"", json.dumps(configuration))
    plugin_state_definition = plugin_state_definition.replace("\"%%SHORTENED_PROFILE%%\"", json.dumps(shortened_profile))

    return json.loads(plugin_state_definition)


def get_multi_level_state_definition_branch_list(d_levels_list, expected_class, plugin_definitions, shortened_profile):
    multi_level_branch_list = []
    multi_level_random_string = "_" + "".join(random.choices(string.ascii_letters + string.digits, k = 5))

    parent_branch = {
        "States": {}
    }
    
    for index, level in zip(reversed(range(len(d_levels_list))), reversed(d_levels_list)):
        single_level_branch_list = []
        is_first_plugin_audio = False

        for p_index, plugin in enumerate(level):
            plugin_name = plugin["Name"]
            plugin_definition = get_plugin_state_definition(plugin, expected_class, plugin_definitions[plugin_name], shortened_profile)
            plugin_supported_media_type = plugin_definitions[plugin_name]["SupportedMediaType"]

            random_string = "_" + "".join(random.choices(string.ascii_letters + string.digits, k = 5))

            if plugin_supported_media_type == "Video":
                child_branch = {
                    "StartAt": f"{plugin_name}{random_string}",
                    "States": {
                        f"{plugin_name}{random_string}": plugin_definition
                    }
                }

            elif plugin_supported_media_type == "Audio":
                if p_index == 0:
                    is_first_plugin_audio = True

                map_parameters = {
                    "Event.$": "$.Event",
                    "Input.$": "$.Input",
                    "TrackNumber.$": "$$.Map.Item.Value"
                }

                plugin_definition["Parameters"]["Payload"]["TrackNumber.$"] = "$.TrackNumber"

                child_branch = {
                    "StartAt": f"{plugin_name}MapTask{random_string}",
                    "States": {
                        f"{plugin_name}MapTask{random_string}": {
                            "Type": "Map",
                            "ItemsPath": "$.Event.AudioTracks",
                            "Parameters": map_parameters,
                            "Iterator": {
                                "StartAt": f"{plugin_name}{random_string}",
                                "States": {
                                    f"{plugin_name}{random_string}": plugin_definition
                                }
                            },
                            "End": True
                        }
                    }
                }

            single_level_branch_list.append(child_branch)

        if index == len(d_levels_list) - 1:
            parent_branch["StartAt"] = f"Level{index + 1}DependentPluginsTask{multi_level_random_string}"

        else:
            parent_branch["States"][f"Level{index + 2}CollectDependentPluginsResult{multi_level_random_string}"].pop("End", None)
            parent_branch["States"][f"Level{index + 2}CollectDependentPluginsResult{multi_level_random_string}"]["Next"] = f"Level{index + 1}DependentPluginsTask{multi_level_random_string}"
        
        parent_branch["States"][f"Level{index + 1}DependentPluginsTask{multi_level_random_string}"] = {
            "Type": "Parallel",
            "Branches": single_level_branch_list,
            "Next": f"Level{index + 1}CollectDependentPluginsResult{multi_level_random_string}"
        }

        if is_first_plugin_audio:
            parent_branch["States"][f"Level{index + 1}CollectDependentPluginsResult{multi_level_random_string}"] = {
                "Type": "Pass",
                "Parameters": {
                    "Event.$": "$[0][0].Event",
                    "Input.$": "$[0][0].Input"
                },
                "End": True
            }

        else:
            parent_branch["States"][f"Level{index + 1}CollectDependentPluginsResult{multi_level_random_string}"] = {
                "Type": "Pass",
                "Parameters": {
                    "Event.$": "$[0].Event",
                    "Input.$": "$[0].Input"
                },
                "End": True
            }
        
    multi_level_branch_list.append(parent_branch)

    return multi_level_branch_list


def get_featurers_state_definition_branch_list(plugins_list, expected_class, plugin_definitions, shortened_profile):
    branch_list = []

    for plugin in plugins_list:
        plugin_name = plugin["Name"]
        plugin_definition = get_plugin_state_definition(plugin, expected_class, plugin_definitions[plugin_name], shortened_profile)
        plugin_supported_media_type = plugin_definitions[plugin_name]["SupportedMediaType"]

        random_string = "_" + "".join(random.choices(string.ascii_letters + string.digits, k = 5))

        if "DependentPlugins" in plugin:
            print(f"DependentPlugins State machine generation for the Featurer plugin '{plugin_name}' in progress.")

            d_plugins_branch_list = get_multi_level_state_definition_branch_list(plugin["DependentPlugins"], "Featurer", plugin_definitions, shortened_profile)

            if plugin_supported_media_type == "Video":
                child_branch = {
                    "StartAt": f"{plugin_name}DependentPluginsTask{random_string}",
                    "States": {
                        f"{plugin_name}DependentPluginsTask{random_string}": {
                            "Type": "Parallel",
                            "Branches": d_plugins_branch_list,
                            "Next": f"{plugin_name}CollectDependentPluginsResult{random_string}"
                        },
                        f"{plugin_name}CollectDependentPluginsResult{random_string}": {
                            "Type": "Pass",
                            "Parameters": {
                                "Event.$": "$[0].Event",
                                "Input.$": "$[0].Input"
                            },
                            "Next": f"{plugin_name}{random_string}"
                        },
                        f"{plugin_name}{random_string}": plugin_definition
                    }
                }

            elif plugin_supported_media_type == "Audio":
                map_parameters = {
                    "Event.$": "$.Event",
                    "Input.$": "$.Input",
                    "TrackNumber.$": "$$.Map.Item.Value"
                }

                plugin_definition["Parameters"]["Payload"]["TrackNumber.$"] = "$.TrackNumber"

                child_branch = {
                    "StartAt": f"{plugin_name}DependentPluginsTask{random_string}",
                    "States": {
                        f"{plugin_name}DependentPluginsTask{random_string}": {
                            "Type": "Parallel",
                            "Branches": d_plugins_branch_list,
                            "Next": f"{plugin_name}CollectDependentPluginsResult{random_string}"
                        },
                        f"{plugin_name}CollectDependentPluginsResult{random_string}": {
                            "Type": "Pass",
                            "Parameters": {
                                "Event.$": "$[0].Event",
                                "Input.$": "$[0].Input"
                            },
                            "Next": f"{plugin_name}MapTask{random_string}"
                        },
                        f"{plugin_name}MapTask{random_string}": {
                            "Type": "Map",
                            "ItemsPath": "$.Event.AudioTracks",
                            "Parameters": map_parameters,
                            "Iterator": {
                                "StartAt": f"{plugin_name}{random_string}",
                                "States": {
                                    f"{plugin_name}{random_string}": plugin_definition
                                }
                            },
                            "End": True
                        }
                    }
                }

        else:
            if plugin_supported_media_type == "Video":
                child_branch = {
                    "StartAt": f"{plugin_name}{random_string}",
                    "States": {
                        f"{plugin_name}{random_string}": plugin_definition
                    }
                }

            elif plugin_supported_media_type == "Audio":
                map_parameters = {
                    "Event.$": "$.Event",
                    "Input.$": "$.Input",
                    "TrackNumber.$": "$$.Map.Item.Value"
                }

                plugin_definition["Parameters"]["Payload"]["TrackNumber.$"] = "$.TrackNumber"

                child_branch = {
                    "StartAt": f"{plugin_name}MapTask{random_string}",
                    "States": {
                        f"{plugin_name}MapTask{random_string}": {
                            "Type": "Map",
                            "ItemsPath": "$.Event.AudioTracks",
                            "Parameters": map_parameters,
                            "Iterator": {
                                "StartAt": f"{plugin_name}{random_string}",
                                "States": {
                                    f"{plugin_name}{random_string}": plugin_definition
                                }
                            },
                            "End": True
                        }
                    }
                }

        branch_list.append(child_branch)
    
    return branch_list
