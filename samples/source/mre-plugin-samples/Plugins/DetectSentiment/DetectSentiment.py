# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3

from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import PluginHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane

comp_client = boto3.client("comprehend")


def consolidate_comprehend_results(depResult, comprehend_results):
    result = {}

    result["Start"] = depResult["Start"]
    result["End"] = depResult["End"]
    result["Label"] = comprehend_results["Sentiment"]
    result["Transcription"] = depResult["Transcription"]
    result["primary_sentiment"] = result["Label"]
    result["positive_score"] = comprehend_results["SentimentScore"]["Positive"]
    result["negative_score"] = comprehend_results["SentimentScore"]["Negative"]
    result["neutral_score"] = comprehend_results["SentimentScore"]["Neutral"]
    result["mixed_score"] = comprehend_results["SentimentScore"]["Mixed"]

    if result["positive_score"] > 0.75:
        result["positive_flag"] = True
    else:
        result["positive_flag"] = False

    if result["negative_score"] > 0.75:
        result["negative_flag"] = True
    else:
        result["negative_flag"] = False

    if result["neutral_score"] > 0.75:
        result["neutral_flag"] = True
    else:
        result["neutral_flag"] = False

    if result["mixed_score"] > 0.75:
        result["mixed_flag"] = True
    else:
        result["mixed_flag"] = False

    return result


def lambda_handler(event, context):

    print(event)

    results = []
    mre_dataplane = DataPlane(event)

    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)
    mre_pluginhelper = PluginHelper(event)

    try:

        # process chunk with ffmpeg using options provided
        text_attribute = event["Plugin"]["Configuration"]["text_attribute"]
        text_language_code = event["Plugin"]["Configuration"]["text_language_code"]

        # this plugin expects the dependent plugin to provide the text data to analyze with Amazon Comprehend
        dep_plugin = event["Plugin"]["DependentPlugins"][0]
        print("dep_plugin: " + dep_plugin)

        # get all dependent detector data
        depResults = mre_dataplane.get_dependent_plugins_output()
        print(depResults)

        # execute a comprehend job to detect sentiment for each transciption or whatever the designated text attribute is
        #'Sentiment': 'POSITIVE'|'NEGATIVE'|'NEUTRAL'|'MIXED'
        for depResult in depResults[dep_plugin]:
            response = comp_client.detect_sentiment(
                Text=depResult[text_attribute], LanguageCode=text_language_code
            )
            print(response)

            # process results
            result = consolidate_comprehend_results(depResult, response)
            results.append(result)

        print(f"results: {results}")

        # Add the results of the plugin to the payload (required if the plugin status is "complete"; Optional if the plugin has any errors)
        mre_outputhelper.add_results_to_output(results)

        # Persist plugin results for later use
        mre_dataplane.save_plugin_results(results)

        # Update the processing status of the plugin (required)
        mre_outputhelper.update_plugin_status(Status.PLUGIN_COMPLETE)

        # Returns expected payload built by MRE helper library
        return mre_outputhelper.get_output_object()

    except Exception as e:
        print(e)

        # Update the processing status of the plugin (required)
        mre_outputhelper.update_plugin_status(Status.PLUGIN_ERROR)

        # Re-raise the exception to MRE processing where it will be handled
        raise
