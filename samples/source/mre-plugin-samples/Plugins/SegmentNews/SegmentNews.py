# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
import os
import boto3
from boto3.dynamodb.conditions import Key, Attr
import json
from decimal import Decimal
from botocore.config import Config

from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane
from MediaReplayEnginePluginHelper import ControlPlane

config = Config(retries={"max_attempts": 20, "mode": "standard"})
brt = boto3.client(service_name="bedrock-runtime", config=config)
bedrock_client = boto3.client("bedrock")

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")
mre_plugin_result_table_env = os.environ["MRE_PLUGIN_RESULT_TABLE"]
mre_plugin_result_table = dynamodb.Table(mre_plugin_result_table_env)
pk_chunknumber_index = "PK_ChunkNumber-index"
transcription_dependent_plugin_name = "DetectSentiment"  # Modify as needed


# function to get record from dynamodb table
def get_transcript(
    a_program,
    a_event,
    a_start_chunk_number,
    a_end_chunk_number,
):
    # Specify the key condition expression for the query
    key_condition_expression = Key("PK").eq(
        a_program + "#" + a_event + "#" + transcription_dependent_plugin_name
    ) & Key("ChunkNumber").between(a_start_chunk_number, a_end_chunk_number)

    # Perform the query
    response = mre_plugin_result_table.query(
        IndexName=pk_chunknumber_index, KeyConditionExpression=key_condition_expression
    )
    trans = response["Items"]

    # Perform pagination
    while "LastEvaluatedKey" in response:
        response = mre_plugin_result_table.query(
            IndexName=pk_chunknumber_index,
            KeyConditionExpression=key_condition_expression,
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        trans.extend(response["Items"])

    if len(trans) == 0:
        return ""
    else:
        print("Found transcript history to assemble with")
        transcript = ""
        for chunk in trans:
            if chunk["Transcription"]:
                transcript += " " + f"[{chunk['Start']}] {chunk['Transcription']}"
        return transcript


def get_segments(a_program, a_event, a_segmenter, a_start):
    # Specify the key condition expression for the query
    key_condition_expression = Key("PK").eq(
        a_program + "#" + a_event + "#" + a_segmenter
    ) & Key("Start").eq(Decimal(str(a_start)))

    # Perform the query
    response = mre_plugin_result_table.query(
        KeyConditionExpression=key_condition_expression
    )
    return response["Items"]


def get_segments_by_label(a_program, a_event, a_segmenter, a_label):
    # Specify the key condition expression for the query
    key_condition_expression = Key("PK").eq(
        a_program + "#" + a_event + "#" + a_segmenter
    )
    filter_expression = Attr("Label").eq(a_label)

    # Perform the query
    response = mre_plugin_result_table.query(
        KeyConditionExpression=key_condition_expression,
        FilterExpression=filter_expression,
    )
    return response["Items"]


def delete_segment(a_program, a_event, a_segmenter, a_start):
    print(f"Deleting for start={str(a_start)}")

    segments = get_segments(a_program, a_event, a_segmenter, a_start)
    print(segments)

    mre_plugin_result_table.delete_item(
        Key={
            "PK": a_program + "#" + a_event + "#" + a_segmenter,
            "Start": Decimal(str(a_start)),
        }
    )

    print("delete successful")


# function to get plugin output attribute data
def get_plugin_data(a_program, a_event, a_plugin, a_start):
    # Specify the key condition expression for the query
    key_condition_expression = Key("PK").eq(
        a_program + "#" + a_event + "#" + a_plugin
    ) & Key("Start").gt(Decimal(str(a_start)))

    # Perform the query
    response = mre_plugin_result_table.query(
        KeyConditionExpression=key_condition_expression
    )
    if len(response["Items"]) == 0:
        return []
    else:
        return response["Items"]


# find celebs during the specified time span and dedup the list
def get_celebs_for_theme(a_celebs_list, a_start, a_end):
    new_celeb_list = []
    # many frames were checked for celebrities, lets process them one at a time
    for celeb_frame in a_celebs_list:
        if celeb_frame["Start"] >= a_start and celeb_frame["End"] <= a_end:
            # each item is a list of celebs in the frame at the single point in time
            celebs_in_a_frame = json.loads(celeb_frame["Celebrities_List"])
            for celeb in celebs_in_a_frame:
                # check for dups
                if new_celeb_list.count(celeb) == 0:
                    new_celeb_list.append(celeb)

    if len(new_celeb_list) > 0:
        a_result = ",".join(new_celeb_list)
    else:
        a_result = ""
    return a_result


# find sentiment during the specified time span and dedup the list
def get_sentiment_for_theme(a_sentiment_list, a_start, a_end):
    new_sentiment_list = []
    # many frames were checked for celebrities, lets process them one at a time
    for sentiment_frame in a_sentiment_list:
        if sentiment_frame["Start"] >= a_start and sentiment_frame["End"] <= a_end:
            new_sentiment_list.append(sentiment_frame["primary_sentiment"])

    if len(new_sentiment_list) > 0:
        a_result = ",".join(new_sentiment_list)
    else:
        a_result = ""
    return a_result


def get_image_description(a_scene_list, a_start, a_end):
    new_scene_labels_list = []
    # many frames were described using a LLM
    for scene_label in a_scene_list:
        if scene_label["Start"] >= a_start and scene_label["End"] <= a_end:
            astr = scene_label["Image_Summary"]
            labels_in_a_frame = json.loads(astr)
            for label in labels_in_a_frame:
                # check for dups
                if new_scene_labels_list.count(label) == 0:
                    new_scene_labels_list.append(label)

    if len(new_scene_labels_list) > 0:
        a_result = ",".join(new_scene_labels_list)
    else:
        a_result = ""
    return a_result


# clip out the transcript from start to end for a theme
def get_excerpt(a_transcript, a_start, a_end):
    pos_start = a_transcript.find(str(a_start))
    pos_end = a_transcript.find(str(a_end))
    if pos_end > 500:
        print("Truncated the transcription")
        pos_end = 500
    return a_transcript[pos_start - 1 : pos_end - 1]


def generate_bedrock_message(
    bedrock_runtime, model_id, messages, max_tokens, top_p, temp
):
    inference_config = {"maxTokens": max_tokens, "temperature": temp, "topP": top_p}

    response = bedrock_runtime.converse(
        modelId=model_id, messages=messages, inferenceConfig=inference_config
    )

    return response["output"]


def get_themes_from_transcript(
    model_id, a_transcription, a_last_theme, a_prompt_template, mre_controlplane
):
    """Sample response
    ' Here are the key themes in the speech with start and end timings:\n\n[{"Theme": "Greeting and thanking the audience", "Start": "1.69", "End": "43.789"}, {"Theme": "Congratulating new Congressional leadership", "Start": "51.21", "End": "160.009"}, {"Theme": "America\'s resilience and progress", "Start": "219.12", "End": "240.009"}, {"Theme": "Bipartisan accomplishments", "Start": "260.86", "End": "380.009"}, {"Theme": "Appealing for continued bipartisanship", "Start": "400.31", "End": "410.979"}]'
    """
    # The Start and End times are mandatory as floating point numbers.

    if a_last_theme != "none":
        a_theme_list = a_last_theme
    else:
        a_theme_list = ""

    prompt = mre_controlplane.get_prompt_template(a_prompt_template)["Template"]
    data = {"a_transcription": a_transcription, "a_theme_list": a_theme_list}
    prompt = prompt.format(**data)
    messages = [{"role": "user", "content": [{"text": prompt}]}]
    response_body = generate_bedrock_message(
        brt, model_id=model_id, messages=messages, max_tokens=2000, top_p=0.9, temp=0.1
    )

    print(response_body)
    response = response_body["message"]["content"][0]["text"]
    response = response.strip().replace("\n", "").strip()
    response = response.strip().replace("<answer>", "").replace("</answer>", "").strip()
    response = response.strip().replace("Decimal(", "").replace('"),', '",').strip()

    # response = response.replace("\'", "\"")
    print(f"LLM response: {response}")

    parsed_response = json.loads(response)
    return (
        parsed_response["Themes"]
        if isinstance(parsed_response, dict)
        else parsed_response
    )


def construct_segment(
    theme,
    new_transcript,
    leave_open_ended,
    celeb_plugin_data,
    sentiment_plugin_data,
    scene_plugin_data,
):

    result = {}
    result["Start"] = theme["Start"]
    if not leave_open_ended:
        result["End"] = theme["End"]
    result["Label"] = theme["Theme"]
    result["Desc"] = theme["Theme"]
    if theme["End"] is not None:
        celebs = get_celebs_for_theme(celeb_plugin_data, theme["Start"], theme["End"])
        print("final celebs list")
        print(celebs)

        sentiment = get_sentiment_for_theme(
            sentiment_plugin_data, theme["Start"], theme["End"]
        )
        print(sentiment)

        image_summary = get_image_description(
            scene_plugin_data, theme["Start"], theme["End"]
        )
        print(f"image_summary = {image_summary}")

        result["Transcript"] = get_excerpt(new_transcript, theme["Start"], theme["End"])
        result["Summary"] = theme["Summary"]
        result["Celebrities"] = celebs
        result["Sentiment"] = sentiment
        result["Image_Summary"] = image_summary
        print(result)

    return result


def get_bedrock_inference_profile_id(model_id):
    # Check if a cross-region inference profile id could be used instead of the given model_id
    # If not, then return the given model_id
    response = bedrock_client.list_inference_profiles(typeEquals="SYSTEM_DEFINED")
    profile_summaries = response["inferenceProfileSummaries"]

    while "nextToken" in response:
        response = bedrock_client.list_inference_profiles(
            typeEquals="SYSTEM_DEFINED", nextToken=response["nextToken"]
        )
        profile_summaries.extend(response["inferenceProfileSummaries"])

    for profile in profile_summaries:
        if (
            profile["inferenceProfileId"].endswith(model_id)
            and profile["status"] == "ACTIVE"
        ):
            print(f"Found inference profile: {profile['inferenceProfileId']}")
            return profile["inferenceProfileId"]

    return model_id


def lambda_handler(event, context):
    print(event)

    mre_dataplane = DataPlane(event)
    mre_outputhelper = OutputHelper(event)
    mre_controlplane = ControlPlane(event)

    results = []

    try:
        # get all dependent detector data
        depResults = mre_dataplane.get_dependent_plugins_output()
        print(depResults)

        # get all detector data since last start or end plus this current chunk
        state, segment, labels = mre_dataplane.get_segment_state()
        print("state: ", str(state))
        print("segment: ", segment)
        print("labels: ", labels)

        min_segment_length = int(event["Plugin"]["Configuration"]["min_segment_length"])
        search_window_seconds = int(
            event["Plugin"]["Configuration"]["search_window_seconds"]
        )
        bedrock_model_id = get_bedrock_inference_profile_id(
            event["Plugin"]["Configuration"]["bedrock_model_id"]
        )
        chunk_start = float(event["Input"]["Metadata"]["HLSSegment"]["StartTime"])
        chunk_duration = int(event["Input"]["Metadata"]["HLSSegment"]["Duration"])
        chunk_number = int((chunk_start + chunk_duration) / chunk_duration)
        chunk_window = int(search_window_seconds / chunk_duration)

        # get event level context variables
        context_vars = mre_controlplane.get_event_context_variables()
        print(context_vars)
        if "Last_Theme" in context_vars:
            last_theme = context_vars["Last_Theme"]
        else:
            last_theme = ""

        if "Prompt_Name" in context_vars:
            a_prompt_template = context_vars["Prompt_Name"]
        else:
            a_prompt_template = event["Plugin"]["Configuration"]["prompt_template_name"]

        # get all chunk vars within the search window to assemble the subset of the transcript looking back <search_window_seconds> ago. No negative values at the start.
        transcript = get_transcript(
            event["Event"]["Program"],
            event["Event"]["Name"],
            max(chunk_number - chunk_window, 0),
            max(chunk_number - 1, 0),  # since we're using DDB between condition
        )
        print(f"transcript: {transcript}")

        # append context variable with timecode and ensure they are sorted based on start time
        chunk_transcript = ""
        print(f"depResults for DetectSentiment: {depResults['DetectSentiment']}")
        sorted_transcriptions = sorted(
            depResults["DetectSentiment"], key=lambda d: d["Start"]
        )
        for _, result in enumerate(sorted_transcriptions):
            chunk_transcript += (
                " [" + str(result["Start"]) + "] " + result["Transcription"]
            )

        new_transcript = transcript + chunk_transcript
        print(f"new_transcript: {new_transcript}")
        if len(new_transcript.strip()) > 0:
            themes = get_themes_from_transcript(
                bedrock_model_id,
                new_transcript,
                last_theme,
                a_prompt_template,
                mre_controlplane,
            )
            print(themes)
            theme_count = len(themes)
            print(f"theme_count: {theme_count} themes: {themes}")
            sorted_themes = sorted(themes, key=lambda d: d["Start"])
            print(f"sorted_themes: {sorted_themes}")
        else:
            print("No transcript generated, skipping theme detection")
            sorted_themes = []

        # list of themes to save. it will appended as processing logic dictates
        themes_to_save = []

        # themes will overlap earlier clips/segments identified
        for theme in sorted_themes:
            print(theme)
            add_theme = False
            if theme["End"] is not None:
                if theme["End"] - theme["Start"] > min_segment_length:
                    # check for prior segments at this same start time
                    prior_segments = get_segments(
                        event["Event"]["Program"],
                        event["Event"]["Name"],
                        "SegmentNews",
                        theme["Start"],
                    )
                    if len(prior_segments) == 0:
                        print("no prior segments")
                        matching_theme_name_segments = get_segments_by_label(
                            event["Event"]["Program"],
                            event["Event"]["Name"],
                            "SegmentNews",
                            theme["Theme"],
                        )
                        if len(matching_theme_name_segments) == 0:
                            print("no dup themes found using a label search")
                            # add the new one
                            add_theme = True
                        else:
                            print("prior matches with theme name")
                            # loop through matching themes with the same name
                            for prior_matching_theme in matching_theme_name_segments:
                                # if match started earlier, keep that one with the greater end time of the two
                                if prior_matching_theme["Start"] < theme["Start"]:
                                    print(
                                        "prior match with theme name and start earlier than new theme"
                                    )

                                    # delete the shorter theme
                                    # TODO: May be redundant since the theme is yet to stored in DDB
                                    delete_segment(
                                        event["Event"]["Program"],
                                        event["Event"]["Name"],
                                        "SegmentNews",
                                        theme["Start"],
                                    )

                                    # add new theme with earlier start time
                                    theme["Start"] = prior_matching_theme["Start"]
                                    add_theme = True

                                    # add new theme with later end time
                                    if prior_matching_theme["End"] > theme["End"]:
                                        theme["End"] = prior_matching_theme["End"]
                                else:
                                    # delete the shorter theme that started after the new theme
                                    print(
                                        "deleting a shorter segment that started after the new theme"
                                    )
                                    delete_segment(
                                        event["Event"]["Program"],
                                        event["Event"]["Name"],
                                        "SegmentNews",
                                        prior_matching_theme["Start"],
                                    )

                    # there are prior segments at this start time
                    else:
                        print("prior segment at the start time")
                        # get max duration of prior segment
                        max_prior_segment_duration = 0
                        for segment in prior_segments:
                            if "End" in segment:
                                prior_segment_duration = (
                                    segment["End"] - segment["Start"]
                                )
                                if prior_segment_duration > max_prior_segment_duration:
                                    max_prior_segment_duration = prior_segment_duration

                        print(
                            "max prior seg duration: " + str(max_prior_segment_duration)
                        )
                        # is the new theme/segment longer than the prior segments that start at the same time. If not, skip it
                        if theme["End"] - theme["Start"] > max_prior_segment_duration:
                            # delete the old one
                            print("deleting shorter segment")
                            delete_segment(
                                event["Event"]["Program"],
                                event["Event"]["Name"],
                                "SegmentNews",
                                theme["Start"],
                            )

                            # add the new one
                            add_theme = True

            if add_theme:
                themes_to_save.append(theme)

        # figure out what the earliest theme is
        sorted_themes_to_save = sorted(themes_to_save, key=lambda d: d["Start"])
        earliest_start = -1
        theme_count = len(sorted_themes_to_save)
        if theme_count > 0:
            earliest_start = sorted_themes_to_save[0]["Start"]

        celeb_plugin_data = []
        scene_plugin_data = []
        sentiment_plugin_data = []
        if earliest_start > -1:
            print("getting dependent data")
            celeb_plugin_data = get_plugin_data(
                event["Event"]["Program"],
                event["Event"]["Name"],
                "DetectCelebrities",
                earliest_start,
            )
            sentiment_plugin_data = get_plugin_data(
                event["Event"]["Program"],
                event["Event"]["Name"],
                "DetectSentiment",
                earliest_start,
            )
            scene_plugin_data = get_plugin_data(
                event["Event"]["Program"],
                event["Event"]["Name"],
                "DetectSceneLabels",
                earliest_start,
            )

        for theme in sorted_themes_to_save:
            leave_open_ended = False
            # cleanup for erroneous Decimal() cast in the json output
            a_start = str(theme["Start"])
            a_start.strip().replace("Decimal(", "").replace('"),', '",').strip()
            theme["Start"] = float(a_start)

            a_end = str(theme["End"])
            a_end.strip().replace("Decimal(", "").replace('"),', '",').strip()
            theme["End"] = float(a_end)

            results.append(
                construct_segment(
                    theme,
                    new_transcript,
                    leave_open_ended,
                    celeb_plugin_data,
                    sentiment_plugin_data,
                    scene_plugin_data,
                )
            )
            last_theme = theme["Theme"]

        print(f"results:{results}")

        temp_vars = {}
        temp_vars["Last_Theme"] = last_theme
        mre_controlplane.update_event_context_variables(temp_vars)

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
