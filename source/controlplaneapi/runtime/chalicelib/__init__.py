#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import json
import random
import string
from decimal import Decimal

CLIP_GENERATION_STATE_MACHINE_ARN = os.environ['CLIP_GENERATION_STATE_MACHINE_ARN']

def generate_plugin_state_definition(execution_type):
    if execution_type == "Sync":
        state_definition = {
            "Type": "Task",
            "Resource":"arn:aws:states:::lambda:invoke",
            "Parameters": {
                "FunctionName": "%%PLUGIN_EXECUTE_LAMBDA_ARN%%",
                "Payload": {
                    "Plugin": {
                        "Name": "%%PLUGIN_NAME%%",
                        "Class": "%%PLUGIN_CLASS%%",
                        "ExecutionType": "%%PLUGIN_EXECUTION_TYPE%%",
                        "DependentPlugins": "%%PLUGIN_DEPENDENT_PLUGINS%%",
                        "Configuration": "%%PLUGIN_CONFIGURATION%%",
                        "OutputAttributes": "%%PLUGIN_OUTPUT_ATTRIBUTES%%"
                    },
                    "Profile": "%%SHORTENED_PROFILE%%",
                    "Event.$": "$.Event",
                    "Input.$": "$.Input",
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
            "End": True
        }

    elif execution_type == "SyncModel":
        state_definition = {
            "Type": "Task",
            "Resource":"arn:aws:states:::lambda:invoke",
            "Parameters": {
                "FunctionName": "%%PLUGIN_EXECUTE_LAMBDA_ARN%%",
                "Payload": {
                    "Plugin": {
                        "Name": "%%PLUGIN_NAME%%",
                        "Class": "%%PLUGIN_CLASS%%",
                        "ExecutionType": "%%PLUGIN_EXECUTION_TYPE%%",
                        "ModelEndpoint": "%%PLUGIN_MODEL_ENDPOINT%%",
                        "DependentPlugins": "%%PLUGIN_DEPENDENT_PLUGINS%%",
                        "Configuration": "%%PLUGIN_CONFIGURATION%%",
                        "OutputAttributes": "%%PLUGIN_OUTPUT_ATTRIBUTES%%"
                    },
                    "Profile": "%%SHORTENED_PROFILE%%",
                    "Event.$": "$.Event",
                    "Input.$": "$.Input",
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
            "End": True
        }

    return state_definition

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

def get_plugin_state_definition_branch_list(plugins_list, expected_class, plugin_definitions, is_dependent_plugins, shortened_profile):
    branch_list = []
    is_audio_media_type = False

    for plugin in plugins_list:
        plugin_name = plugin["Name"]
        plugin_definition = get_plugin_state_definition(plugin, expected_class, plugin_definitions[plugin_name], shortened_profile)
        plugin_supported_media_type = plugin_definitions[plugin_name]["SupportedMediaType"]

        if "DependentPlugins" in plugin:
            print(f"DependentPlugins state machine generation for plugin '{plugin_name}' in progress..")

            d_plugins_branch_list = get_plugin_state_definition_branch_list(plugin["DependentPlugins"], None, plugin_definitions, True, shortened_profile)[0]

            random_string = "_" + "".join(random.choices(string.ascii_letters + string.digits, k = 5))

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
                is_audio_media_type = True

                plugin_definition_parameters = plugin_definition.pop("Parameters", None)
                plugin_lambda_function = plugin_definition_parameters["FunctionName"]
                plugin_definition["Resource"] = plugin_lambda_function
                plugin_definition.pop("OutputPath", None)

                map_parameters = plugin_definition_parameters["Payload"]
                map_parameters["TrackNumber.$"] = "$$.Map.Item.Value"

                child_branch = {
                    "StartAt": f"{plugin_name}MapTask{random_string}",
                    "States": {
                        f"{plugin_name}MapTask{random_string}": {
                            "Type": "Map",
                            "ItemsPath": "$.Event.AudioTracks",
                            "Parameters": map_parameters,
                            "Iterator": {
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
                            },
                            "End": True
                        }
                    }
                }

        else:
            random_string = "_" + "".join(random.choices(string.ascii_letters + string.digits, k = 5))

            if is_dependent_plugins or plugin_supported_media_type == "Video":
                child_branch = {
                    "StartAt": f"{plugin_name}{random_string}",
                    "States": {
                        f"{plugin_name}{random_string}": plugin_definition
                    }
                }

            elif plugin_supported_media_type == "Audio":
                is_audio_media_type = True

                plugin_definition_parameters = plugin_definition.pop("Parameters", None)
                plugin_lambda_function = plugin_definition_parameters["FunctionName"]
                plugin_definition["Resource"] = plugin_lambda_function
                plugin_definition.pop("OutputPath", None)

                map_parameters = plugin_definition_parameters["Payload"]
                map_parameters["TrackNumber.$"] = "$$.Map.Item.Value"

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
    
    return (branch_list, is_audio_media_type)

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
        dependent_plugins = []

        if "DependentPlugins" in classifier:
            print(f"DependentPlugins State machine generation for the Classifier plugin '{classifier_plugin_name}' in progress.")
            dependent_plugins += classifier["DependentPlugins"]

        if is_labeler_dependent_present:
            print(f"DependentPlugins State machine generation for the Labeler plugin '{labeler_plugin_name}' in progress.")
            dependent_plugins += labeler["DependentPlugins"]

        d_plugins_branch_list = get_plugin_state_definition_branch_list(dependent_plugins, None, plugin_definitions, True, shortened_profile)[0]

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

            d_plugins_branch_list, is_audio_media_type = get_plugin_state_definition_branch_list(optimizer["DependentPlugins"], None, plugin_definitions, False, shortened_profile)

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

        featurers_branch_list, is_audio_media_type = get_plugin_state_definition_branch_list(featurers, "Featurer", plugin_definitions, False, shortened_profile)

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

def load_api_schema():
    api_schema = {}
    schema_dir = os.path.dirname(__file__) + "/apischema/"

    for file in os.listdir(schema_dir):
        with open(schema_dir + file) as schema_file:
            schema = json.load(schema_file)
            schema_title = schema["title"]
            api_schema[schema_title] = schema
            print(f"Loaded schema: {schema_title}")

    return api_schema

def replace_decimals(obj):
    if isinstance(obj, list):
        return [replace_decimals(o) for o in obj]
    elif isinstance(obj, dict):
        return {k: replace_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    else:
        return obj

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        if isinstance(obj, set):
            return list(obj)
        
        return super(DecimalEncoder, self).default(obj)
