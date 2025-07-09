# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import io
import json
import os
import traceback
import urllib.parse
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.client import ClientError
from chalice import BadRequestError, Blueprint, ChaliceViewError, IAMAuthorizer
from chalicelib import load_api_schema, replace_decimals
from jsonschema import ValidationError, validate
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection
from opensearchpy.helpers.errors import BulkIndexError
from aws_lambda_powertools import Logger


PLUGIN_RESULT_TABLE_NAME = os.environ["PLUGIN_RESULT_TABLE_NAME"]
EB_EVENT_BUS_NAME = os.environ["EB_EVENT_BUS_NAME"]
PROGRAM_EVENT_INDEX = os.environ["PROGRAM_EVENT_INDEX"]
PROGRAM_EVENT_PLUGIN_INDEX = os.environ["PROGRAM_EVENT_PLUGIN_INDEX"]
PARTITION_KEY_CHUNK_NUMBER_INDEX = os.environ["PARTITION_KEY_CHUNK_NUMBER_INDEX"]
OPENSEARCH_ENDPOINT = os.getenv("OS_VECTORSEARCH_COLLECTION_EP")
OPENSEARCH_INDEX = os.getenv("AOSS_KNN_INDEX_NAME", "mre_knn_index")
BEDROCK_EMBEDDINGS_MODEL_ID = os.getenv(
    "BEDROCK_EMBEDDINGS_MODEL_ID", "amazon.titan-embed-text-v2:0"
)

logger = Logger(service="aws-mre-dataplane-api")

authorizer = IAMAuthorizer()
ddb_resource = boto3.resource("dynamodb")
eb_client = boto3.client("events")
if OPENSEARCH_ENDPOINT:
    credentials = boto3.Session().get_credentials()
    http_auth = AWSV4SignerAuth(
        credentials, os.getenv("AWS_REGION", "us-east-1"), "aoss"
    )
    aoss_client = OpenSearch(
        hosts=[{"host": OPENSEARCH_ENDPOINT.replace("https://", "", 1), "port": 443}],
        http_auth=http_auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        pool_maxsize=20,
    )
    bedrock_client = boto3.client(service_name="bedrock-runtime")

API_SCHEMA = load_api_schema()

plugin_api = Blueprint(__name__)


def generate_embeddings(body, model_id):
    response = bedrock_client.invoke_model(
        body=body,
        modelId=model_id,
        accept="application/json",
        contentType="application/json",
    )

    response_body = json.loads(response.get("body").read())

    return response_body


def add_to_opensearch_index(program, event, plugin_name, results):
    try:
        logger.info(f"Indexing {len(results)} results into OpenSearch")

        # Iterate through the plugin results and index into OpenSearch
        for i, item in enumerate(results):
            logger.info(f"Indexing item: {item}")
            start = round(item["Start"], 3)
            end = round(item["End"], 3) if "End" in item else start
            text_record = io.StringIO()
            text_record.write(f"Start:{start}\nEnd:{end}\n")

            # Convert each item in the results to XML format
            for k, v in item.items():
                if k != "Start" and k != "End":
                    text_record.write(f"{k}:{v}\n")

            text_record = text_record.getvalue()

            record = f"<Record>\n{text_record}</Record>"

            logger.info("Generating embeddings for text record:", text_record)

            body = json.dumps(
                {"inputText": text_record, "dimensions": 1024, "normalize": True}
            )

            # Generate embeddings for the item
            response = generate_embeddings(body, BEDROCK_EMBEDDINGS_MODEL_ID)

            doc = {
                "embedding": response["embedding"],
                "content": record,
                "Program": program,
                "Event": event,
                "PluginName": plugin_name,
                "Start": start,
                "End": end,
            }

            logger.info(f"Indexing item with {start=} and {end=}")

            i_response = aoss_client.index(
                index=OPENSEARCH_INDEX,
                body=doc,
            )

            results[i]["aoss_doc_id"] = i_response["_id"]

    except Exception as e:
        logger.info(f"Error while indexing into OpenSearch: {str(e)}")
        traceback.print_stack()
        raise e


@plugin_api.route("/plugin/result", cors=True, methods=["POST"], authorizer=authorizer)
def store_plugin_result():
    """
    Store the result of a plugin in a DynamoDB table.

    Body:

    .. code-block:: python

        {
            "Program": string,
            "Event": string,
            "ProfileName": string,
            "ChunkSize": integer,
            "ProcessingFrameRate": integer,
            "Classifier": string,
            "ExecutionId": string,
            "AudioTrack": integer,
            "Filename": string,
            "ChunkNumber": integer,
            "PluginName": string,
            "PluginClass": string,
            "ModelEndpoint": string,
            "OutputAttributesNameList": list,
            "Location": object,
            "Results": list
        }

    Returns:

        None
    
    Raises:
        400 - BadRequestError
        500 - ChaliceViewError
    """
    try:
        result = json.loads(plugin_api.current_app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=result, schema=API_SCHEMA["store_plugin_result"])

        logger.info("Got a valid plugin result schema")

        program = result["Program"]
        event = result["Event"]
        plugin_name = result["PluginName"]
        plugin_class = result["PluginClass"]
        audio_track = str(result["AudioTrack"]) if "AudioTrack" in result else None
        results = result["Results"]

        logger.info(
            f"Storing the result of program '{program}', event '{event}', plugin '{plugin_name}' in the DynamoDB table '{PLUGIN_RESULT_TABLE_NAME}'"
        )
        logger.info(f"Number of items to store: {len(results)}")

        plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

        # If the plugin class is Optimizer, append the results to existing items in DynamoDB
        if plugin_class == "Optimizer":
            classifier = result["Classifier"]
            opto_audio_track = audio_track if audio_track is not None else "1"

            for item in results:
                is_update_required = False
                update_expression = []
                expression_attribute_names = {}
                expression_attribute_values = {}

                if "OptoStartCode" in item:
                    is_update_required = True
                    update_expression.append("#OptoStartCode = :OptoStartCode")
                    expression_attribute_names["#OptoStartCode"] = "OptoStartCode"
                    expression_attribute_values[":OptoStartCode"] = item["OptoStartCode"]

                    if "OptoStart" in item:
                        update_expression.append("#OptoStart.#AudioTrack = :OptoStart")
                        expression_attribute_names["#OptoStart"] = "OptoStart"
                        expression_attribute_names["#AudioTrack"] = opto_audio_track
                        expression_attribute_values[":OptoStart"] = round(item["OptoStart"], 3)

                        if "OptoStartDescription" in item:
                            update_expression.append("#OptoStartDescription = :OptoStartDescription")
                            expression_attribute_names["#OptoStartDescription"] = "OptoStartDescription"
                            expression_attribute_values[":OptoStartDescription"] = item["OptoStartDescription"]

                        if "OptoStartDetectorResults" in item:
                            update_expression.append("#OptoStartDetectorResults = :OptoStartDetectorResults")
                            expression_attribute_names["#OptoStartDetectorResults"] = "OptoStartDetectorResults"
                            expression_attribute_values[":OptoStartDetectorResults"] = item["OptoStartDetectorResults"]

                if "OptoEndCode" in item:
                    is_update_required = True
                    update_expression.append("#OptoEndCode = :OptoEndCode")
                    expression_attribute_names["#OptoEndCode"] = "OptoEndCode"
                    expression_attribute_values[":OptoEndCode"] = item["OptoEndCode"]

                    if "OptoEnd" in item:
                        update_expression.append("#OptoEnd.#AudioTrack = :OptoEnd")
                        expression_attribute_names["#OptoEnd"] = "OptoEnd"
                        expression_attribute_names["#AudioTrack"] = opto_audio_track
                        expression_attribute_values[":OptoEnd"] = round(item["OptoEnd"], 3)

                        if "OptoEndDescription" in item:
                            update_expression.append("#OptoEndDescription = :OptoEndDescription")
                            expression_attribute_names["#OptoEndDescription"] = "OptoEndDescription"
                            expression_attribute_values[":OptoEndDescription"] = item["OptoEndDescription"]

                        if "OptoEndDetectorResults" in item:
                            update_expression.append("#OptoEndDetectorResults = :OptoEndDetectorResults")
                            expression_attribute_names["#OptoEndDetectorResults"] = "OptoEndDetectorResults"
                            expression_attribute_values[":OptoEndDetectorResults"] = item["OptoEndDetectorResults"]

                if is_update_required:
                    logger.info(
                        f"Updating existing segment having Start={item['Start']} with the Optimizer plugin result"
                    )

                    plugin_result_table.update_item(
                        Key={
                            "PK": f"{program}#{event}#{classifier}",
                            "Start": item["Start"]
                        },
                        ## TODO: Modify Update Expression to remove 'NonOptChunkNumber' when it's been optimized
                        UpdateExpression="REMOVE NonOptoChunkNumber SET " + ", ".join(update_expression),
                        ExpressionAttributeNames=expression_attribute_names,
                        ExpressionAttributeValues=expression_attribute_values
                    )

                    item["Program"] = program
                    item["Event"] = event
                    item["ProfileName"] = result["ProfileName"]
                    item["PluginClass"] = result["PluginClass"]
                    item["Classifier"] = classifier
                    item["AudioTrack"] = opto_audio_track

                    # Send the Optimization status to EventBridge
                    put_events_to_event_bridge(plugin_class, item)

        # If the plugin class is Labeler, append the results to existing items in DynamoDB
        elif plugin_class == "Labeler":
            classifier = result["Classifier"]

            for item in results:
                update_expression = []
                expression_attribute_names = {}
                expression_attribute_values = {}

                if "LabelCode" in item:
                    update_expression.append("#LabelCode = :LabelCode")
                    expression_attribute_names["#LabelCode"] = "LabelCode"
                    expression_attribute_values[":LabelCode"] = item["LabelCode"]

                    if "Label" in item:
                        update_expression.append("#Label = :Label")
                        expression_attribute_names["#Label"] = "Label"
                        expression_attribute_values[":Label"] = item["Label"]

                    if "OutputAttributesNameList" in result:
                        for index, output_attribute in enumerate(result["OutputAttributesNameList"]):
                            if output_attribute in item and output_attribute != "Label":
                                update_expression.append(f"#OutAttr{index} = :OutAttr{index}")
                                expression_attribute_names[f"#OutAttr{index}"] = output_attribute
                                expression_attribute_values[f":OutAttr{index}"] = item[output_attribute]

                    logger.info(
                        f"Updating existing segment having Start={item['Start']} with the Labeler plugin result"
                    )

                    plugin_result_table.update_item(
                        Key={
                            "PK": f"{program}#{event}#{classifier}",
                            "Start": item["Start"]
                        },
                        UpdateExpression="SET " + ", ".join(update_expression),
                        ExpressionAttributeNames=expression_attribute_names,
                        ExpressionAttributeValues=expression_attribute_values
                    )

        else:
            # Index the results into OpenSearch for enabling GenAI search
            if plugin_class == "Classifier" and OPENSEARCH_ENDPOINT:
                add_to_opensearch_index(program, event, plugin_name, results)

            with plugin_result_table.batch_writer() as batch:
                if audio_track is not None:
                    pk = f"{program}#{event}#{plugin_name}#{audio_track}"
                else:
                    pk = f"{program}#{event}#{plugin_name}"

                for item in results:
                    
                    item["PK"] = pk
                    item["Start"] = round(item["Start"], 3)
                    item["End"] = round(item["End"], 3) if "End" in item else item["Start"]

                    if plugin_class == "Classifier":
                        if "OptoStartCode" not in item:
                            item["OptoStartCode"] = "Not Attempted"
                            item["OptoStart"] = {}
                            item["OriginalClipStatus"] = {}
                            item["OriginalClipLocation"] = {}
                            item["OptimizedClipStatus"] = {}
                            item["OptimizedClipLocation"] = {}

                        if "End" in item and "OptoEndCode" not in item:
                            item["OptoEndCode"] = "Not Attempted"
                            item["OptoEnd"] = {}
                            item["LabelCode"] = "Not Attempted"
                            item["Label"] = ""
                        
                        ## TODO: Add new attribute of NonOptChunkNumber if Start and End are not equal (complete segments)
                        if item["End"] != item["Start"]:
                            item["NonOptoChunkNumber"] = result["ChunkNumber"]
                        ## TODO: Add new attribute of NonOptChunkNumber

                    item["ProgramEvent"] = f"{program}#{event}"
                    item["ProgramEventPluginName"] = f"{program}#{event}#{plugin_name}"
                    item["Program"] = program
                    item["Event"] = event
                    item["ProfileName"] = result["ProfileName"]
                    item["ChunkSize"] = result["ChunkSize"]
                    item["ProcessingFrameRate"] = result["ProcessingFrameRate"]
                    item["ExecutionId"] = result["ExecutionId"]
                    item["PluginName"] = plugin_name
                    item["Filename"] = result["Filename"]
                    item["ChunkNumber"] = result["ChunkNumber"]
                    item["PluginClass"] = result["PluginClass"]
                    item["ModelEndpoint"] = result["ModelEndpoint"] if "ModelEndpoint" in result else ""
                    item["Location"] = result["Location"]

                    if audio_track is not None:
                        item["AudioTrack"] = audio_track

                    batch.put_item(
                        Item=item
                    )

                    # Send the Segmentation status to EventBridge
                    if plugin_class == "Classifier":
                        put_events_to_event_bridge(plugin_class, item)

    except ValidationError as e:
        logger.info(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except BulkIndexError as e:
        logger.info(f"Got OpenSearch BulkIndexError: {str(e)}")
        raise ChaliceViewError(e.message)

    except ClientError as e:
        logger.info(f"Got DynamoDB ClientError: {str(e)}")
        error = e.response["Error"]["Message"]
        logger.info(
            f"Unable to store the result of program '{program}', event '{event}', plugin '{plugin_name}' in the DynamoDB table '{PLUGIN_RESULT_TABLE_NAME}': {str(error)}"
        )
        raise ChaliceViewError(
            f"Unable to store the result of program '{program}', event '{event}', plugin '{plugin_name}' in the DynamoDB table '{PLUGIN_RESULT_TABLE_NAME}': {str(error)}")

    except Exception as e:
        logger.info(
            f"Unable to store the result of program '{program}', event '{event}', plugin '{plugin_name}' in the DynamoDB table '{PLUGIN_RESULT_TABLE_NAME}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to store the result of program '{program}', event '{event}', plugin '{plugin_name}' in the DynamoDB table '{PLUGIN_RESULT_TABLE_NAME}': {str(e)}")

    else:
        return {}

@plugin_api.route('/plugin/dependentplugins/output', cors=True, methods=['POST'], authorizer=authorizer)
def get_dependent_plugins_output():
    """
    Retrieve the output of one or more dependent plugins of a plugin for a given chunk number.

    Body:
    
    .. code-block:: python

        {
            "Program": string,
            "Event": string,
            "ChunkNumber": integer,
            "DependentPlugins": list,
            "AudioTrack": integer
        }

    Returns:

        Dictionary containing the output of one or more dependent plugins
    
    Raises:
        400 - BadRequestError
        500 - ChaliceViewError
    """
    try:
        request = json.loads(plugin_api.current_app.current_request.raw_body.decode())

        validate(instance=request, schema=API_SCHEMA["get_dependent_plugins_output"])

        logger.info("Got a valid schema")

        program = request["Program"]
        event = request["Event"]
        chunk_number = request["ChunkNumber"]
        dependent_plugins = request["DependentPlugins"]
        audio_track = str(request["AudioTrack"]) if "AudioTrack" in request else None
        last_evaluated_keys = request['LastEvaluatedKeys'] if 'LastEvaluatedKeys' in request else {}

        plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

        output = {}

        for d_plugin in dependent_plugins:

            d_plugin_name = d_plugin["Name"]
            d_plugin_media_type = d_plugin["SupportedMediaType"]

            if last_evaluated_keys and d_plugin_name not in last_evaluated_keys:
                continue

            logger.info(
                f"Getting the output of dependent plugin '{d_plugin_name}' for program '{program}', event '{event}' and chunk number '{chunk_number}'"
            )

            if d_plugin_media_type == "Audio":
                if audio_track is None:
                    raise BadRequestError(
                        f"Unable to get the output of dependent plugin '{d_plugin_name}' with an audio track of 'None'")

                pk = f"{program}#{event}#{d_plugin_name}#{audio_track}"
            else:
                pk = f"{program}#{event}#{d_plugin_name}"

            query_params ={
                "IndexName":PARTITION_KEY_CHUNK_NUMBER_INDEX,
                "KeyConditionExpression": Key("PK").eq(pk) & Key("ChunkNumber").eq(chunk_number),
            }

            if d_plugin_name in last_evaluated_keys:
                logger.info(f"Using LastEvaluatedKey '{last_evaluated_keys[d_plugin_name]}'")
                query_params["ExclusiveStartKey"] = last_evaluated_keys[d_plugin_name]

            response = plugin_result_table.query(**query_params)

            output[d_plugin_name] = {'Items': response["Items"]}

            if "LastEvaluatedKey" in response and response["LastEvaluatedKey"]:
                output[d_plugin_name]['LastEvaluatedKey'] = response["LastEvaluatedKey"]

    except BadRequestError as e:
        logger.info(f"Got chalice BadRequestError: {str(e)}")
        raise
    
    except ValidationError as e:
        logger.info(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except Exception as e:
        logger.info(
            f"Unable to get the output of one or more dependent plugins for program '{program}', event '{event}' and chunk number '{chunk_number}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to get the output of one or more dependent plugins for program '{program}', event '{event}' and chunk number '{chunk_number}': {str(e)}")

    else:
        return replace_decimals(output)


def put_events_to_event_bridge(plugin_class, segment):
    try:
        segment = replace_decimals(segment)

        if plugin_class == "Classifier":
            segment_start = segment["Start"]
            segment_end = segment["End"] if "End" in segment else None
            detail_type = "Segmentation Status"

            if segment_end is None or segment_start == segment_end:
                state = "SEGMENT_START"
            else:
                state = "SEGMENT_END"

        elif plugin_class == "Optimizer":
            detail_type = "Optimization Status"

            if "OptoEnd" in segment and segment["OptoEnd"]:
                state = "OPTIMIZED_SEGMENT_END"
            elif "OptoStart" in segment and segment["OptoStart"]:
                state = "OPTIMIZED_SEGMENT_START"

        logger.info(
            f"Sending an event for '{detail_type}' to EventBridge with state '{state}' for the segment '{segment}'"
        )

        detail = {
            "State": state,
            "Segment": segment
        }

        response = eb_client.put_events(
            Entries=[
                {
                    "Source": "awsmre",
                    "DetailType": detail_type,
                    "Detail": json.dumps(detail),
                    "EventBusName": EB_EVENT_BUS_NAME
                }
            ]
        )

        if response["FailedEntryCount"] > 0:
            logger.info(
                f"Failed to send an event for '{detail_type}' to EventBridge with state '{state}' for the segment '{segment}'. More details below:"
            )
            logger.info(response["Entries"])

    except Exception as e:
        logger.info(
            f"Unable to send an event to EventBridge for the segment '{segment}': {str(e)}"
        )


@plugin_api.route('/replay/feature/program/{program}/event/{event}/outputattribute/{pluginattribute}/plugin/{pluginname}',
           cors=True, methods=['GET'], authorizer=authorizer)
def get_plugin_output_attributes_values(program, event, pluginattribute, pluginname):
    """
    Gets a list of Unique Plugin output attribute values for a Plugin and Output Attribute

    Returns:

        A list of Unique Plugin output attribute values for a Plugin and Output Attribute
    """
    event = urllib.parse.unquote(event)
    program = urllib.parse.unquote(program)
    pluginattribute = urllib.parse.unquote(pluginattribute)
    pluginname = urllib.parse.unquote(pluginname)

    plugin_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

    # Get all Plugin results for the current clip's Start and End times.
    # We will end up getting data from other clips which will be filtered out downstream    
    # response = plugin_table.query(
    #     KeyConditionExpression=Key("ProgramEvent").eq(f"{program}#{event}"),
    #     FilterExpression=Attr('PluginName').eq(pluginname) & Attr('PluginClass').is_in(
    #         ['Featurer', 'Labeler', 'Classifier']),
    #     ScanIndexForward=True,
    #     IndexName='ProgramEvent_Start-index'
    # )
    response = plugin_table.query(
        KeyConditionExpression=Key("ProgramEventPluginName").eq(f"{program}#{event}#{pluginname}"),
        FilterExpression=Attr('PluginClass').is_in(['Featurer', 'Labeler', 'Classifier']),
        ScanIndexForward=True,
        IndexName=PROGRAM_EVENT_PLUGIN_INDEX
    )

    clips_info = response["Items"]

    unique_values = []
    for item in clips_info:
        # Only consider Items which match the Plugin Name and has the Attribute 
        if pluginattribute in item:
            if item[pluginattribute] not in unique_values:
                unique_values.append(item[pluginattribute])

    return {
        pluginname + " | " + pluginattribute: unique_values
    }


@plugin_api.route('/feature/in/segment/program/{program}/event/{event}/plugin/{pluginname}/attrn/{attrname}/attrv/{attrvalue}/start/{starttime}/end/{endtime}',
    cors=True, methods=['GET'], authorizer=authorizer)
def get_feature_in_segment(program, event, starttime, pluginname, attrname, attrvalue, endtime):
    """
    Gets the plugin result for a Plugin Output attribute based on the output attribute name and value

    Returns:

        Plugin result, if the feature (output attribute) exists in any segment
    """
    event = urllib.parse.unquote(event)
    program = urllib.parse.unquote(program)
    starttime = Decimal(urllib.parse.unquote(starttime))
    pluginname = urllib.parse.unquote(pluginname)
    attrname = urllib.parse.unquote(attrname)
    attrvalue = urllib.parse.unquote(attrvalue)
    endtime = Decimal(urllib.parse.unquote(endtime))

    plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

    # We dont need to get all the attributes to find if a feature exists in segment or not.
    response = plugin_result_table.query(
        ProjectionExpression="#start, #optoStart, #end, #optoEnd, #outputAttribute",
        ExpressionAttributeNames={'#start': 'Start', '#optoStart': 'OptoStart',
                                  '#end': 'End', '#optoEnd': 'OptoEnd', '#outputAttribute': attrname},
        IndexName=PROGRAM_EVENT_PLUGIN_INDEX,
        ScanIndexForward=True,
        KeyConditionExpression=Key("ProgramEventPluginName").eq(f"{program}#{event}#{pluginname}") & Key('Start').between(round(starttime, 3), round(endtime, 3))
    )

    feature_items = response["Items"]
    while "LastEvaluatedKey" in response:
        response = plugin_result_table.query(
            IndexName=PROGRAM_EVENT_PLUGIN_INDEX,
            ProjectionExpression="#start, #optoStart, #end, #optoEnd, #outputAttribute",
            ExpressionAttributeNames={'#start': 'Start', '#optoStart': 'OptoStart',
                                  '#end': 'End', '#optoEnd': 'OptoEnd', '#outputAttribute': attrname},
            ScanIndexForward=True,
            ExclusiveStartKey=response["LastEvaluatedKey"],
            KeyConditionExpression=Key("ProgramEventPluginName").eq(f"{program}#{event}#{pluginname}") & Key('Start').between(round(starttime, 3), round(endtime, 3))
        )
    feature_items.extend(response["Items"])

    # Convert Param into bool since all plugins store the Output Attrib values as bool.
    attribValueInBool = True if attrvalue == "True" else False

    # Check if the Segment returned has the Output Attribute and the value being asked for
    for item in feature_items:
        if attrname in item:
            if item[attrname] == attribValueInBool:
                return item

    return {}


@plugin_api.route('/segments/all/program/{program}/event/{event}/classifier/{classifier}/replay', cors=True, methods=['GET'],
           authorizer=authorizer)
def get_segments_for_event(program, event, classifier):
    """
    Gets all segments created for an event.

    Returns:

        All segments created for an event.
    """
    event = urllib.parse.unquote(event)
    program = urllib.parse.unquote(program)
    classifier = urllib.parse.unquote(classifier)

    plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)

    response = plugin_result_table.query(
        ProjectionExpression="#start, #originalClipLocation, #optimizedClipLocation, #optoStart, #pluginClass, #end, #optoEnd, #hourElapsed",
        ExpressionAttributeNames={'#start': 'Start', '#originalClipLocation': 'OriginalClipLocation',
                                  '#optimizedClipLocation': 'OptimizedClipLocation', '#optoStart': 'OptoStart',
                                  '#pluginClass': 'PluginClass', '#end': 'End', '#optoEnd': 'OptoEnd', '#hourElapsed': 'HourElapsed'},
        KeyConditionExpression=Key("PK").eq(f"{program}#{event}#{classifier}"),
        ScanIndexForward=True
    )

    segments = response["Items"]

    while "LastEvaluatedKey" in response:
        response = plugin_result_table.query(
            ProjectionExpression="#start, #originalClipLocation, #optimizedClipLocation, #optoStart, #pluginClass, #end, #optoEnd, #hourElapsed",
            ExpressionAttributeNames={'#start': 'Start', '#originalClipLocation': 'OriginalClipLocation',
                                      '#optimizedClipLocation': 'OptimizedClipLocation', '#optoStart': 'OptoStart',
                                      '#pluginClass': 'PluginClass', '#end': 'End', '#optoEnd': 'OptoEnd', '#hourElapsed': 'HourElapsed'},
            ExclusiveStartKey=response["LastEvaluatedKey"],
            KeyConditionExpression=Key("PK").eq(f"{program}#{event}#{classifier}"),
            ScanIndexForward=True
        )

        segments.extend(response["Items"])
    
    return replace_decimals(segments)


@plugin_api.route(
    "/program/{program}/event/{event}/start/{start}/end/{end}/plugins/output/attributes",
    cors=True,
    methods=["POST"],
    authorizer=authorizer,
)
def get_plugins_output_filtered_by_attributes(program, event, start, end):
    """
    Gets all plugins output for an event segment.

    Returns:

        All plugins output for an event segment
    """
    try:
        request = json.loads(plugin_api.current_app.current_request.raw_body.decode())

        ## Make sure our schema is correct (just a plugin_attribute list of strings)
        validate(instance=request, schema=API_SCHEMA["get_plugin_outputs"])

        logger.info("Got a valid schema")

        ## We pass in event, program, start, & end
        event = urllib.parse.unquote(event)
        program = urllib.parse.unquote(program)
        start = Decimal(urllib.parse.unquote(start))
        end = Decimal(urllib.parse.unquote(end))

        ## We want to include PluginName & Start as well as all the passed in attributes (we want these from the DB)
        plugin_output_attributes = ["Start", "PluginName"] + request["pluginAttributes"]

        ## Build key condition expression
        keyConditionExpression = Key("ProgramEvent").eq(f"{program}#{event}") & Key(
            "Start"
        ).between(start, end)

        ## Dynamic Expression Lists (we avoid using any text that is restricted)
        projection_expression = ", ".join([f"#{i}" for i in plugin_output_attributes])
        expression_attribute_names = {f"#{i}": i for i in plugin_output_attributes}

        ## Query the DB for all PluginResults for the given event, program, start, & end time.
        plugin_result_table = ddb_resource.Table(PLUGIN_RESULT_TABLE_NAME)
        response = plugin_result_table.query(
            IndexName=PROGRAM_EVENT_INDEX,
            KeyConditionExpression=keyConditionExpression,
            ProjectionExpression=projection_expression,
            ExpressionAttributeNames=expression_attribute_names,
        )
        result_items = response["Items"] if "Items" in response else []

        ## Paginate for additional items
        while "LastEvaluatedKey" in response:
            response = plugin_result_table.query(
                IndexName=PROGRAM_EVENT_INDEX,
                KeyConditionExpression=keyConditionExpression,
                ProjectionExpression=projection_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            if "Items" in response:
                result_items.extend(response["Items"])

        ## We build a dictionary grouped by PluginName and list of corresponding output attributes
        pluginResultDict = {}

        ## We create a list of attributes we want to return (i.e. we want all except for PluginName)
        return_attributes = ["Start"] + request["pluginAttributes"]

        ## Iterate to get the proper format
        for plugin_result in result_items:
            if plugin_result["PluginName"] in pluginResultDict:
                ## Include all attributes except plugin name
                pluginResultDict[plugin_result["PluginName"]].append(
                    {k: v for k, v in plugin_result.items() if k in return_attributes}
                )
                continue
            pluginResultDict[plugin_result["PluginName"]] = [
                {k: v for k, v in plugin_result.items() if k in return_attributes}
            ]
        output = pluginResultDict

    except BadRequestError as e:
        logger.info(f"Got chalice BadRequestError: {str(e)}")
        raise

    except ValidationError as e:
        logger.info(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except Exception as e:
        logger.info(f"Unable to get plugin output attributes: {str(e)}")
        raise ChaliceViewError(f"Unable to get plugin output attributes: {str(e)}")

    else:
        return replace_decimals(output)
