#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import json
import uuid
import urllib.parse
import boto3
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from chalice import Chalice
from chalice import IAMAuthorizer
from chalice import ChaliceViewError, BadRequestError, ConflictError, NotFoundError
from boto3.dynamodb.types import TypeSerializer
from boto3.dynamodb.conditions import Key, Attr
from botocore.client import ClientError
from jsonschema import ValidationError, FormatChecker
from chalicelib import DecimalEncoder
from chalicelib import helpers
from chalicelib import load_api_schema, replace_decimals, replace_floats
from chalicelib.Schedule import Schedule
from chalicelib.EventScheduler import EventScheduler
from botocore.signers import CloudFrontSigner
import rsa
import functools
import calendar
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.validation import (SchemaValidationError,
                                                        validate)

app = Chalice(app_name="aws-mre-controlplane-event-api")
logger = Logger(service="aws-mre-controlplane-event-api")

API_VERSION = "1.0.0"
authorizer = IAMAuthorizer()
serializer = TypeSerializer()

ddb_resource = boto3.resource("dynamodb")
medialive_client = boto3.client("medialive")
eb_client = boto3.client("events")
s3_resource = boto3.resource("s3")
sm_client = boto3.client("secretsmanager")

API_SCHEMA = load_api_schema()

PROGRAM_TABLE_NAME = os.environ["PROGRAM_TABLE_NAME"]
EVENT_TABLE_NAME = os.environ["EVENT_TABLE_NAME"]
EVENT_PAGINATION_INDEX = os.environ["EVENT_PAGINATION_INDEX"]
EVENT_PROGRAMID_INDEX = os.environ["EVENT_PROGRAMID_INDEX"]
EVENT_PROGRAM_INDEX = os.environ["EVENT_PROGRAM_INDEX"]
EVENT_CHANNEL_INDEX = os.environ["EVENT_CHANNEL_INDEX"]
EB_EVENT_BUS_NAME = os.environ["EB_EVENT_BUS_NAME"]
EB_EVENT_BUS_ARN = os.environ["EB_EVENT_BUS_ARN"]
CURRENT_EVENTS_TABLE_NAME = os.environ["CURRENT_EVENTS_TABLE_NAME"]
EB_SCHEDULE_ROLE_ARN = os.environ["EB_SCHEDULE_ROLE_ARN"]
CLOUDFRONT_DOMAIN_NAME = os.environ["CLOUDFRONT_DOMAIN_NAME"]
METADATA_TABLE_NAME = os.environ["METADATA_TABLE_NAME"]
HLS_STREAMING_SIGNED_URL_EXPIRATION_HRS = os.environ[
    "HLS_STREAMING_SIGNED_URL_EXPIRATION_HRS"
]

metadata_table = ddb_resource.Table(METADATA_TABLE_NAME)

# Create middleware to inject request context
@app.middleware('all')
def inject_request_context(event, get_response):
    # event is a Chalice Request object
    request_id = event.context.get('requestId', 'N/A')
    
    # Add request ID to persistent logger context
    logger.append_keys(request_id=request_id)
    
    response = get_response(event)
    return response

@app.route("/event", cors=True, methods=["POST"], authorizer=authorizer)
def create_event():
    """
    Creates a new event in MRE.

    Body:

    .. code-block:: python

        {
            "Name": string,
            "Program": string,
            "Description": string,
            "Channel": string,
            "ProgramId": string,
            "SourceVideoUrl": string,
            "SourceVideoAuth": object,
            "SourceVideoMetadata": object,
            "BootstrapTimeInMinutes": integer,
            "Profile": string,
            "ContentGroup": string,
            "Start": timestamp,
            "DurationMinutes": integer,
            "Archive": boolean,
            "SourceVideoBucket": string,
            "GenerateOrigClips": boolean,
            "GenerateOptoClips": boolean,
            "GenerateOrigThumbNails": boolean,
            "GenerateOptoThumbNails": boolean,
            "TimecodeSource": string,
            "StopMediaLiveChannel: boolean
            "Variables": object
        }

    Parameters:

        - Name: [REQUIRED] Name of the Event.
        - Program: [REQUIRED] Name of the Program.
        - Description: Event Description.
        - Channel: Identifier of the AWS Elemental MediaLive Channel used for the Event
        - ProgramId: A Unique Identifier for the event being broadcasted.
        - SourceVideoUrl: VOD or Live Urls to help MRE to harvest the streams.
        - SourceVideoAuth: A Dict which contains API Authorization payload to help MRE harvest VOD/Live streams.
        - SourceVideoMetadata: A Dict of additional Event Metadata for reporting purposes.
        - BootstrapTimeInMinutes: [REQUIRED] Default value 0. Duration in Minutes which indicates the time it takes for the Source video process to be initialized.
        - Profile: [REQUIRED] Name of the MRE Profile to make use of for processing the event.
        - ContentGroup: [REQUIRED] Name of the Content Group.
        - Start: [REQUIRED] The Actual start DateTime of the event (in UTC).
        - DurationMinutes: [REQUIRED] The Total Event Duration.
        - Archive: [REQUIRED] Backup the Source Video if true.
        - SourceVideoBucket: S3 Bucket where Live or VOD video chunks would land to trigger the Event.
        - GenerateOrigClips: Generate Original segment clips if true (Default is true).
        - GenerateOptoClips: Generate Optimized segment clips if true (Default is true).
        - GenerateOrigThumbNails: Generate Original segment thumbnail if true (Default is true),
        - GenerateOptoThumbNails: Generate Original segment thumbnail if true (Default is true)
        - TimeCodeSource: Source of the embedded TimeCode in the Event video frames (Default is NOT_EMBEDDED).
        - StopMediaLiveChannel: False by default. When MediaLive is the Video chunk source, setting this attribute to True lets MRE stop the channel when the event ends.
        - Variables: Context Variables (key/value pairs) used to share data across plugin exections

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        409 - ConflictError
        500 - ChaliceViewError
    """
    try:
        event = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(
            event=event,
            schema=API_SCHEMA["create_event"]
        )

        # Validate that the Event Duration is not Negative
        if "DurationMinutes" in event:
            if event["DurationMinutes"] < 0:
                raise ValidationError("Event duration cannot be a negative value.")

        logger.info("Got a valid event schema")

        name = event["Name"]
        program = event["Program"]

        program_table = ddb_resource.Table(PROGRAM_TABLE_NAME)

        # Add the program to Program DDB table
        program_table.put_item(Item={"Name": program})

        is_vod_event = False

        # The API caller sends the Start time in UTC format
        start_utc_time = datetime.strptime(event["Start"], "%Y-%m-%dT%H:%M:%SZ")
        logger.info(f"start_utc_time={start_utc_time}")

        cur_utc_time = datetime.utcnow()

        event["BootstrapTimeInMinutes"] = (
            event["BootstrapTimeInMinutes"] if "BootstrapTimeInMinutes" in event else 0
        )
        event["Id"] = str(uuid.uuid4())
        event["Status"] = "Queued"
        event["Created"] = cur_utc_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        event["HlsMasterManifest"] = {}
        event["EdlLocation"] = {}
        event["PaginationPartition"] = "PAGINATION_PARTITION"
        event["StartFilter"] = event["Start"]

        event["GenerateOrigClips"] = (
            True if "GenerateOrigClips" not in event else event["GenerateOrigClips"]
        )
        event["GenerateOptoClips"] = (
            True if "GenerateOptoClips" not in event else event["GenerateOptoClips"]
        )
        event["GenerateOrigThumbNails"] = (
            True
            if "GenerateOrigThumbNails" not in event
            else event["GenerateOrigThumbNails"]
        )
        event["GenerateOptoThumbNails"] = (
            True
            if "GenerateOptoThumbNails" not in event
            else event["GenerateOptoThumbNails"]
        )

        event["TimecodeSource"] = (
            "NOT_EMBEDDED" if "TimecodeSource" not in event else event["TimecodeSource"]
        )
        event["StopMediaLiveChannel"] = (
            event["StopMediaLiveChannel"] if "StopMediaLiveChannel" in event else False
        )

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        # Check if the event start time is in the past
        if cur_utc_time >= start_utc_time:
            is_vod_event = True

        # These are required to be passed to EventBridge for Event Life Cycle Management
        if is_vod_event:
            vod_schedule_id = f"mre-vod-end-{str(uuid.uuid4())}"
            event["vod_schedule_id"] = vod_schedule_id
        else:
            live_start_schedule_id = f"mre-live-{str(uuid.uuid4())}-event-start"
            live_end_schedule_id = f"mre-live-{str(uuid.uuid4())}-event-end"
            event["live_start_schedule_id"] = live_start_schedule_id
            event["live_end_schedule_id"] = live_end_schedule_id

        # MediaLive
        if "Channel" in event and event["Channel"]:
            last_known_medialive_config, source_hls_manifest_location = (
                helpers.add_or_update_medialive_output_group(
                    name, program, event["Profile"], event["Channel"]
                )
            )
            event["LastKnownMediaLiveConfig"] = last_known_medialive_config
            event["SourceHlsMasterManifest"] = source_hls_manifest_location

            # Add or Update the CW Alarm for the MediaLive channel
            # helpers.create_cloudwatch_alarm_for_channel(event["Channel"])

        # Harvester
        if "SourceVideoAuth" in event:
            response = sm_client.create_secret(
                Name=f"/MRE/Event/{event['Id']}/SourceVideoAuth",
                SecretString=json.dumps(event["SourceVideoAuth"]),
                Tags=[
                    {"Key": "Project", "Value": "MRE"},
                    {"Key": "Program", "Value": program},
                    {"Key": "Event", "Value": name},
                ],
            )

            event["SourceVideoAuthSecretARN"] = response["ARN"]
            event.pop("SourceVideoAuth", None)

        # S3 bucket source
        if "SourceVideoBucket" in event and event["SourceVideoBucket"]:
            helpers.create_s3_bucket_trigger(event["SourceVideoBucket"])

        logger.info(f"Creating the event '{name}' in program '{program}'")

        event_table.put_item(
            Item=replace_floats(event),
            ConditionExpression="attribute_not_exists(#Name) AND attribute_not_exists(#Program)",
            ExpressionAttributeNames={"#Name": "Name", "#Program": "Program"},
        )

        # If we have variables in the event, persist in the metadata table
        if "Variables" in event and event["Variables"]:
            metadata_table.put_item(
                Item={"pk": f"EVENT#{program}#{name}", "data": event["Variables"]}
            )

    except NotFoundError as e:
        logger.info(f"Got chalice NotFoundError: {str(e)}")
        raise

    except ValidationError as e:
        logger.info(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except ConflictError as e:
        logger.info(f"Got chalice ConflictError: {str(e)}")
        raise

    except ClientError as e:
        logger.info(f"Got DynamoDB ClientError: {str(e)}")

        if "LastKnownMediaLiveConfig" in event:
            medialive_client.update_channel(
                ChannelId=event["Channel"],
                Destinations=event["LastKnownMediaLiveConfig"]["Destinations"],
                EncoderSettings=event["LastKnownMediaLiveConfig"]["EncoderSettings"],
            )

        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ConflictError(f"Event '{name}' in program '{program}' already exists")
        else:
            raise

    except Exception as e:
        logger.info(f"Unable to create the event '{name}' in program '{program}': {str(e)}")

        if "LastKnownMediaLiveConfig" in event:
            medialive_client.update_channel(
                ChannelId=event["Channel"],
                Destinations=event["LastKnownMediaLiveConfig"]["Destinations"],
                EncoderSettings=event["LastKnownMediaLiveConfig"]["EncoderSettings"],
            )

        raise ChaliceViewError(
            f"Unable to create the event '{name}' in program '{program}': {str(e)}"
        )

    else:
        logger.info(f"Successfully created the event: {json.dumps(event)}")

        try:
            # HANDLE VOD EVENTS
            if is_vod_event:

                # Attempting to Start MediaLive Channel
                start_medialive_channel(event, name, program)

                # Create a EB Schedule for Ending this VOD Event
                cur_utc_time = datetime.utcnow()
                event_start_time = cur_utc_time.strftime("%Y-%m-%dT%H:%M:%S")
                schedule = Schedule(
                    schedule_name=vod_schedule_id,
                    event_name=name,
                    program_name=program,
                    event_start_time=event_start_time,
                    is_vod_event=True,
                    bootstrap_time_in_mins=event["BootstrapTimeInMinutes"],
                    event_duration_in_mins=event["DurationMinutes"],
                    resource_arn=EB_EVENT_BUS_ARN,
                    execution_role=EB_SCHEDULE_ROLE_ARN,
                    input_payload="",
                    stop_channel=(
                        event["StopMediaLiveChannel"]
                        if "StopMediaLiveChannel" in event
                        else False
                    ),
                )
                # Schedule with a Message Status of VOD_EVENT_END
                EventScheduler().create_schedule_event_bridge_target(
                    schedule, get_chunk_source_details(event)
                )
                logger.info(f"Created Schedule for VOD event {name}")

            else:
                eventScheduler = EventScheduler()
                # HANDLE LIVE EVENTS
                event_start_time_utc = datetime.strptime(
                    event["Start"], "%Y-%m-%dT%H:%M:%SZ"
                )

                # Create two EB Schedules. One for Starting the Live Event and another to End it
                schedule = Schedule(
                    schedule_name=live_start_schedule_id,
                    event_name=name,
                    program_name=program,
                    event_start_time=event_start_time_utc,
                    is_vod_event=False,
                    bootstrap_time_in_mins=event["BootstrapTimeInMinutes"],
                    event_duration_in_mins=event["DurationMinutes"],
                    resource_arn=EB_EVENT_BUS_ARN,
                    execution_role=EB_SCHEDULE_ROLE_ARN,
                    input_payload="",
                    schedule_name_prefix="event-start",
                    stop_channel=(
                        event["StopMediaLiveChannel"]
                        if "StopMediaLiveChannel" in event
                        else False
                    ),
                )

                eventScheduler.create_schedule_event_bridge_target(
                    schedule, get_chunk_source_details(event)
                )

                # Create a EB Schedule for Ending this VOD Event
                schedule = Schedule(
                    schedule_name=live_end_schedule_id,
                    event_name=name,
                    program_name=program,
                    event_start_time=event_start_time_utc,
                    is_vod_event=False,
                    bootstrap_time_in_mins=event["BootstrapTimeInMinutes"],
                    event_duration_in_mins=event["DurationMinutes"],
                    resource_arn=EB_EVENT_BUS_ARN,
                    execution_role=EB_SCHEDULE_ROLE_ARN,
                    input_payload="",
                    schedule_name_prefix="event-end",
                    stop_channel=(
                        event["StopMediaLiveChannel"]
                        if "StopMediaLiveChannel" in event
                        else False
                    ),
                )

                eventScheduler.create_schedule_event_bridge_target(
                    schedule, get_chunk_source_details(event)
                )

                logger.info(f"Created Schedules for LIVE event {name}")

            # Publishing message VOD_EVENT_START to Event Bridge.
            # LIVE_EVENT_START events are sent via the Event Start EB Schedule when it gets triggered.
            if is_vod_event:
                put_event_start_to_event_bus(is_vod_event, name, program, event)

        except Exception as e:
            logger.info(
                f"Error creating Schedules for event '{name}' in program '{program}': {str(e)}"
            )
            raise ChaliceViewError(
                f"Error creating Schedules for event '{name}' in program '{program}': {str(e)}"
            )

        return {}


def start_medialive_channel(event, name, program):
    # Attempting to Start MediaLive Channel
    if "Channel" in event:
        channel_id = event["Channel"]
        try:
            medialive_client.start_channel(ChannelId=channel_id)
        except Exception as e:

            logger.info(
                f"Creation of event '{name}' in program '{program}' is successful but unable to start the MediaLive channel '{channel_id}': {str(e)}"
            )
            raise ChaliceViewError(
                f"Creation of event '{name}' in program '{program}' is successful but unable to start the MediaLive channel '{channel_id}': {str(e)}"
            )


def get_chunk_source_details(event):
    chunk_source_details = {}
    if "Channel" in event:
        chunk_source_details["ChannelId"] = event["Channel"]
    elif "SourceVideoAuth" in event:
        chunk_source_details["SourceVideoAuthSecretARN"] = event[
            "SourceVideoAuthSecretARN"
        ]
    elif "SourceVideoBucket" in event:
        chunk_source_details["SourceVideoBucket"] = event["SourceVideoBucket"]

    return chunk_source_details


def put_event_start_to_event_bus(is_vod, event_name, program_name, event):

    chunk_source_details = get_chunk_source_details(event)
    detail = {
        "State": "VOD_EVENT_START",
        "Event": event_name,
        "Program": program_name,
        "ChunkSource": chunk_source_details,
        "IsVOD": is_vod,
    }
    eb_client.put_events(
        Entries=[
            {
                "Source": "awsmre",
                "DetailType": "Either a VOD/LIVE event has been created. Use this to Start event processing",
                "Detail": json.dumps(detail),
                "EventBusName": EB_EVENT_BUS_NAME,
            }
        ]
    )


# List events
def list_events(path_params):
    """
    List all events filtered by content_group with pagination and more filters

    Returns:
    .. code-block:: python
        {
        "Items":
            [
                {
                    "Name": string,
                    "Program": string,
                    "Description": string,
                    "Channel": string,
                    "ProgramId": string,
                    "SourceVideoUrl": string,
                    "SourceVideoAuth": object,
                    "SourceVideoMetadata": object,
                    "SourceVideoBucket": string,
                    "BootstrapTimeInMinutes": integer,
                    "Profile": string,
                    "ContentGroup": string,
                    "Start": timestamp,
                    "DurationMinutes": integer,
                    "Archive": boolean,
                    "FirstPts": number,
                    "FrameRate": number,
                    "AudioTracks": list,
                    "Status": string,
                    "Id": uuid,
                    "Created": timestamp,
                    "ContentGroup: string,
                    "GenerateOrigClips": boolean,
                    "GenerateOptoClips": boolean,
                    "GenerateOrigThumbNails: boolean,
                    "GenerateOptoThumbNails: boolean,
                    "TimecodeSource": string
                },
                ...
            ]
        "LastEvaluatedKey":
            {
                Obj
            }
        }

    Raises:
        500 - ChaliceViewError
    """
    try:
        query_params = app.current_request.query_params
        limit = 100
        filter_expression = None
        last_evaluated_key = None
        projection_expression = None

        if query_params:
            if "limit" in query_params:
                limit = int(query_params.get("limit"))
            if (
                "hasReplays" in query_params
                and query_params.get("hasReplays") == "true"
            ):
                filter_expression = Attr("hasReplays").eq(True)
            if "LastEvaluatedKey" in query_params:
                last_evaluated_key = query_params.get("LastEvaluatedKey")
            if "ProjectionExpression" in query_params:
                projection_expression = query_params.get("ProjectionExpression")
            if "timeFilterStart" in query_params and "timeFilterEnd" in query_params:
                end = query_params.get("timeFilterEnd")
                start = query_params.get("timeFilterStart")
                filter_expression = (
                    Attr("StartFilter").lte(end) & Attr("StartFilter").gte(start)
                    if not filter_expression
                    else filter_expression
                    & Attr("StartFilter").lte(end)
                    & Attr("StartFilter").gte(start)
                )
            if "ContentGroup" in query_params:
                content_group = query_params["ContentGroup"]
                filter_expression = (
                    Attr("ContentGroup").eq(content_group)
                    if not filter_expression
                    else filter_expression & Attr("ContentGroup").eq(content_group)
                )
            if "Program" in query_params:
                program = query_params["Program"]
                filter_expression = (
                    Attr("Program").eq(program)
                    if not filter_expression
                    else filter_expression & Attr("Program").eq(program)
                )
        if path_params:
            if list(path_params.keys())[0] == "ContentGroup":
                content_group = list(path_params.values())[0]
                validate_path_parameters({"ContentGroup": content_group})
                filter_expression = (
                    Attr("ContentGroup").eq(content_group)
                    if not filter_expression
                    else filter_expression & Attr("ContentGroup").eq(content_group)
                )

        logger.info(f"Getting '{limit}' Events'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        query = {
            "IndexName": EVENT_PAGINATION_INDEX,
            "Limit": limit,
            "ScanIndexForward": False,  # descending
            "KeyConditionExpression": Key("PaginationPartition").eq(
                "PAGINATION_PARTITION"
            ),
        }

        if filter_expression:
            query["FilterExpression"] = filter_expression
        if last_evaluated_key:
            query["ExclusiveStartKey"] = json.loads(last_evaluated_key)
        if projection_expression:
            query["ProjectionExpression"] = ", ".join(
                ["#" + name for name in projection_expression.split(", ")]
            )
            expression_attribute_names = {}
            for item in query["ProjectionExpression"].split(", "):
                expression_attribute_names[item] = item[1:]
            query["ExpressionAttributeNames"] = expression_attribute_names

        response = event_table.query(**query)
        events = response["Items"]

        while "LastEvaluatedKey" in response and (limit - len(events) > 0):
            query["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            query["Limit"] = limit - len(events)
            response = event_table.query(**query)
            events.extend(response["Items"])
    
    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    
    except Exception as e:
        logger.info(f"Unable to get the Events: {str(e)}")
        raise ChaliceViewError("Unable to get the Events")

    else:
        ret_val = {
            "LastEvaluatedKey": (
                response["LastEvaluatedKey"] if "LastEvaluatedKey" in response else ""
            ),
            "Items": replace_decimals(events),
        }

        return ret_val


@app.route(
    "/event/contentgroup/{content_group}/all",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def list_events_by_content_group(content_group):
    """
    List all events filtered by content_group with pagination and more filters

    Returns:

        .. code-block:: python

            {
            "Items":
                [
                    {
                        "Name": string,
                        "Program": string,
                        "Description": string,
                        "Channel": string,
                        "ProgramId": string,
                        "SourceVideoUrl": string,
                        "SourceVideoAuth": object,
                        "SourceVideoMetadata": object,
                        "SourceVideoBucket": string,
                        "BootstrapTimeInMinutes": integer,
                        "Profile": string,
                        "ContentGroup": string,
                        "Start": timestamp,
                        "DurationMinutes": integer,
                        "Archive": boolean,
                        "FirstPts": number,
                        "FrameRate": number,
                        "AudioTracks": list,
                        "Status": string,
                        "Id": uuid,
                        "Created": timestamp,
                        "ContentGroup: string,
                        "GenerateOrigClips": boolean,
                        "GenerateOptoClips": boolean,
                        "GenerateOrigThumbNails: boolean,
                        "GenerateOptoThumbNails: boolean,
                        "TimecodeSource": string
                    },
                    ...
                ]
            "LastEvaluatedKey":
                {
                    Obj
                }
            }

    Raises:
        500 - ChaliceViewError
    """
    content_group = urllib.parse.unquote(content_group)
    return list_events({"ContentGroup": content_group})


@app.route("/event/by/{program}", cors=True, methods=["GET"], authorizer=authorizer)
def list_events_by_program(program):
    """
    List all events in MRE for a Program. Supports pagination and filters.

    Returns:

        .. code-block:: python

            {
            "Items":
                [
                    {
                        "Name": string,
                        "Program": string,
                        "Description": string,
                        "Channel": string,
                        "ProgramId": string,
                        "SourceVideoUrl": string,
                        "SourceVideoAuth": object,
                        "SourceVideoMetadata": object,
                        "SourceVideoBucket": string,
                        "BootstrapTimeInMinutes": integer,
                        "Profile": string,
                        "ContentGroup": string,
                        "Start": timestamp,
                        "DurationMinutes": integer,
                        "Archive": boolean,
                        "FirstPts": number,
                        "FrameRate": number,
                        "AudioTracks": list,
                        "Status": string,
                        "Id": uuid,
                        "Created": timestamp,
                        "ContentGroup: string,
                        "GenerateOrigClips": boolean,
                        "GenerateOptoClips": boolean,
                        "GenerateOrigThumbNails: boolean,
                        "GenerateOptoThumbNails: boolean,
                        "TimecodeSource": string
                    },
                    ...
                ]
            "LastEvaluatedKey":
                {
                    Obj
                }
            }

    Raises:
        500 - ChaliceViewError
    """

    try:
        program = urllib.parse.unquote(program)
        validate_path_parameters({"Program": program})
        query_params = app.current_request.query_params
        limit = 100
        filter_expression = None
        last_evaluated_key = None
        projection_expression = None

        if query_params:
            if "limit" in query_params:
                limit = int(query_params.get("limit"))
            if "LastEvaluatedKey" in query_params:
                last_evaluated_key = query_params.get("LastEvaluatedKey")
            if "ProjectionExpression" in query_params:
                projection_expression = query_params.get("ProjectionExpression")
            if "timeFilterStart" in query_params and "timeFilterEnd" in query_params:
                end = query_params.get("timeFilterEnd")
                start = query_params.get("timeFilterStart")
                filter_expression = (
                    Attr("StartFilter").lte(end) & Attr("StartFilter").gte(start)
                    if not filter_expression
                    else filter_expression
                    & Attr("StartFilter").lte(end)
                    & Attr("StartFilter").gte(start)
                )

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        query = {
            "IndexName": EVENT_PROGRAM_INDEX,
            "Limit": limit,
            "ScanIndexForward": False,  # descending
            "KeyConditionExpression": Key("Program").eq(program),
        }

        if filter_expression:
            query["FilterExpression"] = filter_expression
        if last_evaluated_key:
            query["ExclusiveStartKey"] = json.loads(last_evaluated_key)
        if projection_expression:
            query["ProjectionExpression"] = ", ".join(
                ["#" + name for name in projection_expression.split(", ")]
            )
            expression_attribute_names = {}
            for item in query["ProjectionExpression"].split(", "):
                expression_attribute_names[item] = item[1:]
            query["ExpressionAttributeNames"] = expression_attribute_names

        response = event_table.query(**query)
        events = response["Items"]

        while "LastEvaluatedKey" in response and (limit - len(events) > 0):
            query["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            query["Limit"] = limit - len(events)
            response = event_table.query(**query)
            events.extend(response["Items"])

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    
    except Exception as e:
        logger.info(e)
        logger.info("Unable to get the Events")
        raise ChaliceViewError("Unable to get Events")

    else:
        ret_val = {
            "LastEvaluatedKey": (
                response["LastEvaluatedKey"] if "LastEvaluatedKey" in response else ""
            ),
            "Items": replace_decimals(events),
        }

        return ret_val


@app.route("/event/all", cors=True, methods=["GET"], authorizer=authorizer)
def list_events_all():
    """
    List all events in MRE. Supports pagination and filters.

    Returns:

        .. code-block:: python

            {
            "Items":
                [
                    {
                        "Name": string,
                        "Program": string,
                        "Description": string,
                        "Channel": string,
                        "ProgramId": string,
                        "SourceVideoUrl": string,
                        "SourceVideoAuth": object,
                        "SourceVideoMetadata": object,
                        "SourceVideoBucket": string,
                        "BootstrapTimeInMinutes": integer,
                        "Profile": string,
                        "ContentGroup": string,
                        "Start": timestamp,
                        "DurationMinutes": integer,
                        "Archive": boolean,
                        "FirstPts": number,
                        "FrameRate": number,
                        "AudioTracks": list,
                        "Status": string,
                        "Id": uuid,
                        "Created": timestamp,
                        "ContentGroup: string,
                        "GenerateOrigClips": boolean,
                        "GenerateOptoClips": boolean,
                        "GenerateOrigThumbNails: boolean,
                        "GenerateOptoThumbNails: boolean,
                        "TimecodeSource": string
                    },
                    ...
                ]
            "LastEvaluatedKey":
                {
                    Obj
                }
            }

    Raises:
        500 - ChaliceViewError
    """

    return list_events(None)


@app.route(
    "/event/{name}/program/{program}", cors=True, methods=["GET"], authorizer=authorizer
)
def get_event(name, program):
    """
    Get an event by name and program.

    Returns:

        .. code-block:: python

            {
                "Name": string,
                "Program": string,
                "Description": string,
                "Channel": string,
                "ProgramId": string,
                "SourceVideoUrl": string,
                "SourceVideoAuth": object,
                "SourceVideoMetadata": object,
                "SourceVideoBucket": string,
                "BootstrapTimeInMinutes": integer,
                "Profile": string,
                "ContentGroup": string,
                "Start": timestamp,
                "DurationMinutes": integer,
                "Archive": boolean,
                "FirstPts": number,
                "FrameRate": number,
                "AudioTracks": list,
                "Status": string,
                "Id": uuid,
                "Created": timestamp,
                "GenerateOrigClips": boolean,
                "GenerateOptoClips": boolean,
                "GenerateOrigThumbNails: boolean,
                "GenerateOptoThumbNails: boolean,
                "TimecodeSource": string
            }

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)
        validate_path_parameters({"Program": program, "Name": name})

        logger.info(f"Getting the Event '{name}' in Program '{program}'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={"Name": name, "Program": program}, ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Event '{name}' in Program '{program}' not found")

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    
    except NotFoundError as e:
        logger.info(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        logger.info(f"Unable to get the Event '{name}' in Program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to get the Event '{name}' in Program '{program}': {str(e)}"
        )

    else:
        return replace_decimals(response["Item"])


@app.route(
    "/event/{name}/program/{program}", cors=True, methods=["PUT"], authorizer=authorizer
)
def update_event(name, program):
    """
    Update an event by name and program.

    Body:

    .. code-block:: python

        {
            "Description": string,
            "ProgramId": string,
            "SourceVideoUrl": string,
            "SourceVideoAuth": object,
            "SourceVideoMetadata": object,
            "SourceVideoBucket": string,
            "BootstrapTimeInMinutes": integer,
            "Profile": string,
            "ContentGroup": string,
            "Start": timestamp,
            "DurationMinutes": integer,
            "Archive": boolean,
            "GenerateOrigClips": boolean,
            "GenerateOptoClips": boolean,
            "GenerateOrigThumbNails: boolean,
            "GenerateOptoThumbNails: boolean,
            "TimecodeSource": string
            "Variables": object
        }

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        409 - ConflictError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)
        validate_path_parameters({"Program": program, "Name": name})

        event = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=event, schema=API_SCHEMA["update_event"])

        logger.info("Got a valid event schema")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={"Name": name, "Program": program}, ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Event '{name}' in Program '{program}' not found")

        response["Item"] = replace_decimals(response["Item"])
        logger.info(f"Updating the event '{name}' in program '{program}'")

        if "ProgramId" in event and event["ProgramId"]:
            program_id = event["ProgramId"]
            existing_program_id = (
                response["Item"]["ProgramId"] if "ProgramId" in response["Item"] else ""
            )

            if program_id != existing_program_id:
                response = event_table.query(
                    IndexName=EVENT_PROGRAMID_INDEX,
                    KeyConditionExpression=Key("ProgramId").eq(program_id),
                )

                events = replace_decimals(response["Items"])

                while "LastEvaluatedKey" in response:
                    response = event_table.query(
                        ExclusiveStartKey=response["LastEvaluatedKey"],
                        IndexName=EVENT_PROGRAMID_INDEX,
                        KeyConditionExpression=Key("ProgramId").eq(program_id),
                    )

                    events.extend(replace_decimals(response["Items"]))

                if len(events) > 0:
                    raise ConflictError(
                        f"ProgramId '{program_id}' already exists in another event"
                    )

        if "SourceVideoAuth" in event:
            existing_auth_arn = (
                response["Item"]["SourceVideoAuthSecretARN"]
                if "SourceVideoAuthSecretARN" in response["Item"]
                else ""
            )

            if existing_auth_arn:
                sm_client.update_secret(
                    SecretId=existing_auth_arn,
                    SecretString=json.dumps(event["SourceVideoAuth"]),
                )

                event["SourceVideoAuthSecretARN"] = existing_auth_arn
                event.pop("SourceVideoAuth", None)

            else:
                response = sm_client.create_secret(
                    Name=f"/MRE/Event/{response['Item']['Id']}/SourceVideoAuth",
                    SecretString=json.dumps(event["SourceVideoAuth"]),
                    Tags=[
                        {"Key": "Project", "Value": "MRE"},
                        {"Key": "Program", "Value": program},
                        {"Key": "Event", "Value": name},
                    ],
                )

                event["SourceVideoAuthSecretARN"] = response["ARN"]
                event.pop("SourceVideoAuth", None)

        ## S3 bucket source
        if "SourceVideoBucket" in event and event["SourceVideoBucket"]:
            ## Get current bucket
            if "SourceVideoBucket" in response["Item"]:
                existing_bucket = response["Item"]["SourceVideoBucket"]
                ## Get current path of the prefix for BYOB
                ## Remove trigger from bucket (if not used by other events)
                helpers.delete_s3_bucket_trigger(existing_bucket)
            ## Add trigger to updated bucket
            helpers.create_s3_bucket_trigger(event["SourceVideoBucket"])

        update_expression = "SET #Description = :Description, #Profile = :Profile, #ContentGroup = :ContentGroup, #Start = :Start, \
        #DurationMinutes = :DurationMinutes, #Archive = :Archive, #GenerateOrigClips = :GenerateOrigClips, #GenerateOptoClips = :GenerateOptoClips, \
         #TimecodeSource = :TimecodeSource, #StartFilter = :StartFilter, #GenerateOrigThumbNails = :GenerateOrigThumbNails, #GenerateOptoThumbNails = :GenerateOptoThumbNails"

        expression_attribute_names = {
            "#Description": "Description",
            "#Profile": "Profile",
            "#ContentGroup": "ContentGroup",
            "#Start": "Start",
            "#DurationMinutes": "DurationMinutes",
            "#Archive": "Archive",
            "#GenerateOrigClips": "GenerateOrigClips",
            "#GenerateOptoClips": "GenerateOptoClips",
            "#GenerateOrigThumbNails": "GenerateOrigThumbNails",
            "#GenerateOptoThumbNails": "GenerateOptoThumbNails",
            "#TimecodeSource": "TimecodeSource",
            "#StartFilter": "StartFilter",
        }

        expression_attribute_values = {
            ":Description": (
                event["Description"]
                if "Description" in event
                else (
                    response["Item"]["Description"]
                    if "Description" in response["Item"]
                    else ""
                )
            ),
            ":Profile": (
                event["Profile"] if "Profile" in event else response["Item"]["Profile"]
            ),
            ":ContentGroup": (
                event["ContentGroup"]
                if "ContentGroup" in event
                else response["Item"]["ContentGroup"]
            ),
            ":Start": event["Start"] if "Start" in event else response["Item"]["Start"],
            ":DurationMinutes": (
                event["DurationMinutes"]
                if "DurationMinutes" in event
                else response["Item"]["DurationMinutes"]
            ),
            ":Archive": (
                event["Archive"] if "Archive" in event else response["Item"]["Archive"]
            ),
            ":GenerateOrigClips": (
                event["GenerateOrigClips"]
                if "GenerateOrigClips" in event
                else (
                    response["Item"]["GenerateOrigClips"]
                    if "GenerateOrigClips" in response["Item"]
                    else True
                )
            ),
            ":GenerateOptoClips": (
                event["GenerateOptoClips"]
                if "GenerateOptoClips" in event
                else (
                    response["Item"]["GenerateOptoClips"]
                    if "GenerateOptoClips" in response["Item"]
                    else True
                )
            ),
            ":GenerateOrigThumbNails": (
                event["GenerateOrigThumbNails"]
                if "GenerateOrigThumbNails" in event
                else (
                    response["Item"]["GenerateOrigThumbNails"]
                    if "GenerateOrigThumbNails" in response["Item"]
                    else True
                )
            ),
            ":GenerateOptoThumbNails": (
                event["GenerateOptoThumbNails"]
                if "GenerateOptoThumbNails" in event
                else (
                    response["Item"]["GenerateOptoThumbNails"]
                    if "GenerateOptoThumbNails" in response["Item"]
                    else True
                )
            ),
            ":TimecodeSource": (
                event["TimecodeSource"]
                if "TimecodeSource" in event
                else (
                    response["Item"]["TimecodeSource"]
                    if "TimecodeSource" in response["Item"]
                    else "NOT_EMBEDDED"
                )
            ),
            ":StartFilter": (
                event["Start"] if "Start" in event else response["Item"]["Start"]
            ),
        }

        # For MediaLive Channels, Update the Bootstrap time
        if "Channel" in response["Item"]:
            if response["Item"]["Channel"] != "":
                update_expression += (
                    ", #BootstrapTimeInMinutes = :BootstrapTimeInMinutes"
                )
                expression_attribute_names["#BootstrapTimeInMinutes"] = (
                    "BootstrapTimeInMinutes"
                )

                expression_attribute_values[":BootstrapTimeInMinutes"] = (
                    event["BootstrapTimeInMinutes"]
                    if "BootstrapTimeInMinutes" in event
                    else response["Item"]["BootstrapTimeInMinutes"]
                )

        ## BYOB events do not have ProgramId
        if "ProgramId" in response["Item"]:
            update_expression += ", #ProgramId = :ProgramId"
            expression_attribute_names["#ProgramId"] = "ProgramId"
            ## Since this is a GSI we cannot have a null string
            expression_attribute_values[":ProgramId"] = (
                event["ProgramId"]
                if "ProgramId" in event
                else response["Item"]["ProgramId"]
            )

        if "SourceVideoAuth" in response["Item"]:
            # if "Channel" not in response["Item"]:
            update_expression += ", #SourceVideoUrl = :SourceVideoUrl, #SourceVideoAuthSecretARN = :SourceVideoAuthSecretARN, #SourceVideoMetadata = :SourceVideoMetadata, #BootstrapTimeInMinutes = :BootstrapTimeInMinutes"

            expression_attribute_names["#SourceVideoUrl"] = "SourceVideoUrl"
            expression_attribute_names["#SourceVideoAuthSecretARN"] = (
                "SourceVideoAuthSecretARN"
            )
            expression_attribute_names["#SourceVideoMetadata"] = "SourceVideoMetadata"
            expression_attribute_names["#BootstrapTimeInMinutes"] = (
                "BootstrapTimeInMinutes"
            )

            expression_attribute_values[":SourceVideoUrl"] = (
                event["SourceVideoUrl"]
                if "SourceVideoUrl" in event
                else response["Item"]["SourceVideoUrl"]
            )
            expression_attribute_values[":SourceVideoAuthSecretARN"] = (
                event["SourceVideoAuthSecretARN"]
                if "SourceVideoAuthSecretARN" in event
                else (
                    response["Item"]["SourceVideoAuthSecretARN"]
                    if "SourceVideoAuthSecretARN" in response["Item"]
                    else ""
                )
            )
            expression_attribute_values[":SourceVideoMetadata"] = (
                event["SourceVideoMetadata"]
                if "SourceVideoMetadata" in event
                else (
                    response["Item"]["SourceVideoMetadata"]
                    if "SourceVideoMetadata" in response["Item"]
                    else {}
                )
            )
            expression_attribute_values[":BootstrapTimeInMinutes"] = (
                event["BootstrapTimeInMinutes"]
                if "BootstrapTimeInMinutes" in event
                else response["Item"]["BootstrapTimeInMinutes"]
            )

        ## If BYOB
        if "SourceVideoBucket" in response["Item"]:
            update_expression += ", #SourceVideoBucket = :SourceVideoBucket, #BootstrapTimeInMinutes = :BootstrapTimeInMinutes"
            expression_attribute_names["#SourceVideoBucket"] = "SourceVideoBucket"
            expression_attribute_names["#BootstrapTimeInMinutes"] = (
                "BootstrapTimeInMinutes"
            )

            expression_attribute_values[":BootstrapTimeInMinutes"] = (
                event["BootstrapTimeInMinutes"]
                if "BootstrapTimeInMinutes" in event
                else response["Item"]["BootstrapTimeInMinutes"]
            )
            expression_attribute_values[":SourceVideoBucket"] = (
                event["SourceVideoBucket"]
                if "SourceVideoBucket" in event
                else response["Item"]["SourceVideoBucket"]
            )

        event_table.update_item(
            Key={"Name": name, "Program": program},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
        )

        if "Variables" in event and event["Variables"]:
            expression_attribute_names = {"#data": "data"}
            expression_attribute_values = {}
            update_expression = []

            ## Iterate through items
            for key, value in event["Variables"].items():
                expression_attribute_names[f"#k{key}"] = key
                expression_attribute_values[f":v{value}"] = value
                update_expression.append(f"#data.#k{key} = :v{value}")

            if update_expression:
                ## Send update expression
                metadata_table.update_item(
                    Key={
                        "pk": f"EVENT#{program}#{name}",
                    },
                    ExpressionAttributeNames=expression_attribute_names,
                    ExpressionAttributeValues=expression_attribute_values,
                    UpdateExpression=f"SET {', '.join(update_expression)}",
                )

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except NotFoundError as e:
        logger.info(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        logger.info(f"Unable to update the event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to update the event '{name}' in program '{program}': {str(e)}"
        )

    else:
        logger.info(
            f"Successfully updated the event: {json.dumps(event, cls=DecimalEncoder)}"
        )

        new_event_start = (
            event["Start"] if "Start" in event else response["Item"]["Start"]
        )
        new_event_duration_in_mins = (
            event["DurationMinutes"]
            if "DurationMinutes" in event
            else response["Item"]["DurationMinutes"]
        )
        new_event_start = datetime.strptime(new_event_start, "%Y-%m-%dT%H:%M:%SZ")
        logger.info(f"new_event_start={new_event_start}")
        logger.info(f"new_event_duration_in_mins={new_event_duration_in_mins}")

        cur_utc_time = datetime.utcnow()
        eventScheduler = EventScheduler()
        # Only update Schedules for LIVE Events
        if cur_utc_time < new_event_start:

            # Create two EB Schedules. One for Starting the Live Event and another to End it
            schedule = Schedule(
                schedule_name=(
                    event["live_start_schedule_id"]
                    if "live_start_schedule_id" in event
                    else (
                        response["Item"]["live_start_schedule_id"]
                        if "live_start_schedule_id" in response["Item"]
                        else ""
                    )
                ),
                event_name=name,
                program_name=program,
                event_start_time=new_event_start,
                is_vod_event=False,
                bootstrap_time_in_mins=(
                    event["BootstrapTimeInMinutes"]
                    if "BootstrapTimeInMinutes" in event
                    else response["Item"]["BootstrapTimeInMinutes"]
                ),
                event_duration_in_mins=new_event_duration_in_mins,
                resource_arn=EB_EVENT_BUS_ARN,
                execution_role=EB_SCHEDULE_ROLE_ARN,
                input_payload="",
                schedule_name_prefix="event-start",
                stop_channel=(
                    event["StopMediaLiveChannel"]
                    if "StopMediaLiveChannel" in event
                    else (
                        response["Item"]["StopMediaLiveChannel"]
                        if "StopMediaLiveChannel" in response["Item"]
                        else False
                    )
                ),
            )

            eventScheduler.update_schedule_event_bridge_target(
                schedule, get_chunk_source_details(response["Item"])
            )

            # Create a EB Schedule for Ending this LIVE Event
            schedule = Schedule(
                schedule_name=(
                    event["live_end_schedule_id"]
                    if "live_end_schedule_id" in event
                    else (
                        response["Item"]["live_end_schedule_id"]
                        if "live_end_schedule_id" in response["Item"]
                        else ""
                    )
                ),
                event_name=name,
                program_name=program,
                event_start_time=new_event_start,
                is_vod_event=False,
                bootstrap_time_in_mins=(
                    event["BootstrapTimeInMinutes"]
                    if "BootstrapTimeInMinutes" in event
                    else response["Item"]["BootstrapTimeInMinutes"]
                ),
                event_duration_in_mins=new_event_duration_in_mins,
                resource_arn=EB_EVENT_BUS_ARN,
                execution_role=EB_SCHEDULE_ROLE_ARN,
                input_payload="",
                schedule_name_prefix="event-end",
                stop_channel=(
                    event["StopMediaLiveChannel"]
                    if "StopMediaLiveChannel" in event
                    else (
                        response["Item"]["StopMediaLiveChannel"]
                        if "StopMediaLiveChannel" in response["Item"]
                        else False
                    )
                ),
            )

            eventScheduler.update_schedule_event_bridge_target(
                schedule, get_chunk_source_details(response["Item"])
            )

            logger.info(f"Updated Schedules for LIVE event {name}")

        return {}


@app.route(
    "/event/{name}/program/{program}",
    cors=True,
    methods=["DELETE"],
    authorizer=authorizer,
)
def delete_event(name, program):
    """
    Delete an event by name and program.

    Returns:

        None

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)
        validate_path_parameters({"Program": program, "Name": name})

        query_params = app.current_request.query_params

        if query_params and query_params.get("force") == "true":
            force_delete = True
        else:
            force_delete = False

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={"Name": name, "Program": program}, ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Event '{name}' in Program '{program}' not found")
        elif response["Item"]["Status"] == "In Progress":
            raise BadRequestError(
                f"Cannot delete Event '{name}' in Program '{program}' as it is currently in progress"
            )

        existing_event = response["Item"]

        channel_id = (
            response["Item"]["Channel"] if "Channel" in response["Item"] else None
        )
        profile = response["Item"]["Profile"]
        source_auth_secret_arn = (
            response["Item"]["SourceVideoAuthSecretARN"]
            if "SourceVideoAuthSecretARN" in response["Item"]
            else None
        )
        source_bucket = (
            response["Item"]["SourceVideoBucket"]
            if "SourceVideoBucket" in response["Item"]
            else None
        )

        if channel_id:
            logger.info(
                f"Checking if MRE Destination and OutputGroup need to be deleted in the MediaLive channel '{channel_id}'"
            )
            helpers.delete_medialive_output_group(name, program, profile, channel_id)

            logger.info(
                f"Checking if the CloudWatch Alarm for 'InputVideoFrameRate' metric needs to be deleted for the MediaLive channel '{channel_id}'"
            )

            response = event_table.query(
                IndexName=EVENT_CHANNEL_INDEX,
                KeyConditionExpression=Key("Channel").eq(channel_id),
            )

            events = response["Items"]

            while "LastEvaluatedKey" in response:
                response = event_table.query(
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                    IndexName=EVENT_CHANNEL_INDEX,
                    KeyConditionExpression=Key("Channel").eq(channel_id),
                )

                events.extend(response["Items"])

            if len(events) < 2:
                helpers.delete_cloudwatch_alarm_for_channel(channel_id)

        if source_auth_secret_arn:
            if force_delete:
                logger.info(f"Deleting the secret '{source_auth_secret_arn}' immediately")

                sm_client.delete_secret(
                    SecretId=source_auth_secret_arn, ForceDeleteWithoutRecovery=True
                )

            else:
                logger.info(
                    f"Deleting the secret '{source_auth_secret_arn}' with a recovery window of 7 days"
                )

                sm_client.delete_secret(
                    SecretId=source_auth_secret_arn, RecoveryWindowInDays=7
                )

        if source_bucket:
            ## Remove trigger from bucket
            helpers.delete_s3_bucket_trigger(source_bucket)

        # Delete EB Schedules for an Event. Either the VOD or LIVE event schedule gets deleted here
        eventScheduler = EventScheduler()
        if "vod_schedule_id" in existing_event:
            eventScheduler.delete_schedule(existing_event["vod_schedule_id"])

        if "live_start_schedule_id" in existing_event:
            eventScheduler.delete_schedule(existing_event["live_start_schedule_id"])

        if "live_end_schedule_id" in existing_event:
            eventScheduler.delete_schedule(existing_event["live_end_schedule_id"])

        logger.info(f"Deleting the Event '{name}' in Program '{program}'")

        response = event_table.delete_item(Key={"Name": name, "Program": program})

        response = metadata_table.delete_item(Key={"pk": f"EVENT#{program}#{name}"})

        # Send a message to the Event Deletion SQS Queue to trigger the deletion of processing data in DynamoDB for the Event
        helpers.notify_event_deletion_queue(name, program, profile)

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    
    except NotFoundError as e:
        logger.info(f"Got chalice NotFoundError: {str(e)}")
        raise

    except BadRequestError as e:
        logger.info(f"Got chalice BadRequestError: {str(e)}")
        raise

    except Exception as e:
        logger.info(f"Unable to delete the Event '{name}' in Program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to delete the Event '{name}' in Program '{program}': {str(e)}"
        )

    else:
        logger.info(f"Deletion of Event '{name}' in Program '{program}' successful")
        return {}


@app.route(
    "/event/{name}/program/{program}/timecode/firstpts/{first_pts}",
    cors=True,
    methods=["PUT"],
    authorizer=authorizer,
)
def store_first_pts(name, program, first_pts):
    """
    Store the pts timecode of the first frame of the first HLS video segment.

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)
        first_pts = urllib.parse.unquote(first_pts)

        validate_path_parameters(
            {"Program": program, "Name": name, "FirstPts": first_pts}
        )

        logger.info(
            f"Storing the first pts timecode '{first_pts}' of event '{name}' in program '{program}' in the DynamoDB table '{EVENT_TABLE_NAME}'"
        )

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={"Name": name, "Program": program},
            UpdateExpression="SET #FirstPts = :FirstPts",
            ExpressionAttributeNames={"#FirstPts": "FirstPts"},
            ExpressionAttributeValues={":FirstPts": Decimal(first_pts)},
        )

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    except Exception as e:
        logger.info(
            f"Unable to store the first pts timecode '{first_pts}' of event '{name}' in program '{program}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to store the first pts timecode '{first_pts}' of event '{name}' in program '{program}': {str(e)}"
        )

    else:
        logger.info(
            f"Successfully stored the first pts timecode '{first_pts}' of event '{name}' in program '{program}'"
        )

        return {}


@app.route(
    "/event/{name}/program/{program}/timecode/firstpts",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_first_pts(name, program):
    """
    Retrieve the pts timecode of the first frame of the first HLS video segment.

    Returns:

        The pts timecode of the first frame of the first HLS video segment if it exists. Else, None.

    Raises:
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)
        validate_path_parameters({"Program": program, "Name": name})

        logger.info(
            f"Retrieving the first pts timecode of event '{name}' in program '{program}'"
        )

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={"Name": name, "Program": program}, ProjectionExpression="FirstPts"
        )

        if "Item" not in response or len(response["Item"]) < 1:
            logger.info(
                f"First pts timecode of event '{name}' in program '{program}' not found"
            )
            return None

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    
    except Exception as e:
        logger.info(
            f"Unable to retrieve the first pts timecode of event '{name}' in program '{program}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to retrieve the first pts timecode of event '{name}' in program '{program}': {str(e)}"
        )

    else:
        return replace_decimals(response["Item"]["FirstPts"])


@app.route(
    "/event/{name}/program/{program}/framerate/{frame_rate}",
    cors=True,
    methods=["PUT"],
    authorizer=authorizer,
)
def store_frame_rate(name, program, frame_rate):
    """
    Store the frame rate identified after probing the first HLS video segment.

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)
        frame_rate = urllib.parse.unquote(frame_rate)
        validate_path_parameters({"Program": program, "Name": name, "FrameRate": frame_rate})

        logger.info(
            f"Storing the frame rate '{frame_rate}' of event '{name}' in program '{program}' in the DynamoDB table '{EVENT_TABLE_NAME}'"
        )

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={"Name": name, "Program": program},
            UpdateExpression="SET #FrameRate = :FrameRate",
            ExpressionAttributeNames={"#FrameRate": "FrameRate"},
            ExpressionAttributeValues={":FrameRate": frame_rate},
        )

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except Exception as e:
        logger.info(
            f"Unable to store the frame rate '{frame_rate}' of event '{name}' in program '{program}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to store the frame rate '{frame_rate}' of event '{name}' in program '{program}': {str(e)}"
        )

    else:
        logger.info(
            f"Successfully stored the frame rate '{frame_rate}' of event '{name}' in program '{program}'"
        )

        return {}


@app.route(
    "/event/{name}/program/{program}/timecode/firstframe/{embedded_timecode}",
    cors=True,
    methods=["PUT"],
    authorizer=authorizer,
)
def store_first_frame_embedded_timecode(name, program, embedded_timecode):
    """
    Store the embedded timecode of the first frame of the first HLS video segment.

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)
        embedded_timecode = urllib.parse.unquote(embedded_timecode)
        validate_path_parameters(
            {"Program": program, "Name": name, "EmbeddedTimecode": embedded_timecode}
        )

        logger.info(
            f"Storing the first frame embedded timecode '{embedded_timecode}' of event '{name}' in program '{program}' in the DynamoDB table '{EVENT_TABLE_NAME}'"
        )

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={"Name": name, "Program": program},
            UpdateExpression="SET #FirstEmbeddedTimecode = :FirstEmbeddedTimecode",
            ExpressionAttributeNames={
                "#FirstEmbeddedTimecode": "FirstEmbeddedTimecode"
            },
            ExpressionAttributeValues={
                ":FirstEmbeddedTimecode": str(embedded_timecode)
            },
        )

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    
    except Exception as e:
        logger.info(
            f"Unable to store the first frame embedded timecode '{embedded_timecode}' of event '{name}' in program '{program}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to store the first frame embedded timecode '{embedded_timecode}' of event '{name}' in program '{program}': {str(e)}"
        )

    else:
        logger.info(
            f"Successfully stored the first frame embedded timecode '{embedded_timecode}' of event '{name}' in program '{program}'"
        )

        return {}


@app.route(
    "/event/metadata/track/audio", cors=True, methods=["POST"], authorizer=authorizer
)
def store_audio_tracks():
    """
    Store the audio tracks of an event identified after probing the first HLS video segment.

    Body:

    .. code-block:: python

        {
            "Name": string,
            "Program": string,
            "AudioTracks": list
        }

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        event = json.loads(app.current_request.raw_body.decode())
        validate(event=event, schema=API_SCHEMA["create_audio_tracks"])

        name = event["Name"]
        program = event["Program"]
        audio_tracks = event["AudioTracks"]

        logger.info(
            f"Storing the audio tracks '{audio_tracks}' of event '{name}' in program '{program}' in the DynamoDB table '{EVENT_TABLE_NAME}'"
        )

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={"Name": name, "Program": program},
            UpdateExpression="SET #AudioTracks = :AudioTracks",
            ExpressionAttributeNames={"#AudioTracks": "AudioTracks"},
            ExpressionAttributeValues={":AudioTracks": audio_tracks},
        )
    
    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except Exception as e:
        logger.info(
            f"Unable to store the audio tracks '{audio_tracks}' of event '{name}' in program '{program}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to store the audio tracks '{audio_tracks}' of event '{name}' in program '{program}': {str(e)}"
        )

    else:
        logger.info(
            f"Successfully stored the audio tracks '{audio_tracks}' of event '{name}' in program '{program}'"
        )

        return {}


def put_events_to_event_bridge(name, program, status):
    try:
        logger.info(
            f"Sending the event status to EventBridge for event '{name}' in program '{program}'"
        )

        if status == "In Progress":
            state = "EVENT_START"
        elif status == "Complete":
            state = "EVENT_END"

        detail = {"State": state, "Event": {"Name": name, "Program": program}}

        response = eb_client.put_events(
            Entries=[
                {
                    "Source": "awsmre",
                    "DetailType": "Event Status",
                    "Detail": json.dumps(detail),
                    "EventBusName": EB_EVENT_BUS_NAME,
                }
            ]
        )

        if response["FailedEntryCount"] > 0:
            logger.info(
                f"Failed to send the event status to EventBridge for event '{name}' in program '{program}'. More details below:"
            )
            logger.info(response["Entries"])

    except Exception as e:
        logger.info(
            f"Unable to send the event status to EventBridge for event '{name}' in program '{program}': {str(e)}"
        )


@app.route(
    "/event/{name}/program/{program}/status/{status}",
    cors=True,
    methods=["PUT"],
    authorizer=authorizer,
)
def put_event_status(name, program, status):
    """
    Update the status of an event.

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)
        status = urllib.parse.unquote(status)
        validate_path_parameters({"Program": program, "Name": name, "Status": status})

        logger.info(
            f"Setting the status of event '{name}' in program '{program}' to '{status}'"
        )

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={"Name": name, "Program": program},
            UpdateExpression="SET #Status = :Status",
            ExpressionAttributeNames={"#Status": "Status"},
            ExpressionAttributeValues={":Status": status},
        )

        # Notify EventBridge of the Event status
        if status in ["In Progress", "Complete"]:
            put_events_to_event_bridge(name, program, status)

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    
    except Exception as e:
        logger.info(
            f"Unable to set the status of event '{name}' in program '{program}' to '{status}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to set the status of event '{name}' in program '{program}' to '{status}': {str(e)}"
        )

    else:
        logger.info(
            f"Successfully set the status of event '{name}' in program '{program}' to '{status}'"
        )

        return {}


@app.route(
    "/event/{name}/program/{program}/status",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_event_status(name, program):
    """
    Get the status of an event.

    Returns:

        Status of the event

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)
        validate_path_parameters({"Program": program, "Name": name})

        logger.info(f"Getting the status of event '{name}' in program '{program}'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={"Name": name, "Program": program},
            ProjectionExpression="#Status",
            ExpressionAttributeNames={"#Status": "Status"},
            ConsistentRead=True,
        )

        if "Item" not in response or len(response["Item"]) < 1:
            raise NotFoundError(f"Event '{name}' in program '{program}' not found")

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    except NotFoundError as e:
        logger.info(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        logger.info(
            f"Unable to get the status of event '{name}' in program '{program}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to get the status of event '{name}' in program '{program}': {str(e)}"
        )

    else:
        return response["Item"]["Status"]


@app.route(
    "/event/program/hlslocation/update",
    cors=True,
    methods=["POST"],
    authorizer=authorizer,
)
def update_hls_manifest_for_event():
    """
    Updates HLS Manifest S3 location with the event

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        event = json.loads(app.current_request.raw_body.decode())
        validate(event=event, schema=API_SCHEMA["update_hls_manifest"])

        name = event["Name"]
        program = event["Program"]
        hls_location = event["HlsLocation"]
        audiotrack = event["AudioTrack"]

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={"Name": name, "Program": program},
            UpdateExpression="SET #HlsMasterManifest.#AudioTrack = :Manifest",
            ExpressionAttributeNames={
                "#HlsMasterManifest": "HlsMasterManifest",
                "#AudioTrack": audiotrack,
            },
            ExpressionAttributeValues={":Manifest": hls_location},
        )
    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    except Exception as e:
        logger.info(
            f"Unable to update HLS Master Manifest for event '{name}' in program '{program}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to update HLS Master Manifest for event '{name}' in program '{program}': {str(e)}"
        )

    else:
        logger.info(
            f"Successfully stored the HLS Master Manifest for event '{name}' in program '{program}'"
        )

        return {}


@app.route(
    "/event/program/edllocation/update",
    cors=True,
    methods=["POST"],
    authorizer=authorizer,
)
def update_edl_for_event():
    """
    Updates EDL S3 location with the event

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        event = json.loads(app.current_request.raw_body.decode())
        validate(event=event, schema=API_SCHEMA["update_edl_location"])

        name = event["Name"]
        program = event["Program"]
        edl_location = event["EdlLocation"]
        audiotrack = event["AudioTrack"]

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={"Name": name, "Program": program},
            UpdateExpression="SET #EdlLocation.#AudioTrack = :Manifest",
            ExpressionAttributeNames={
                "#EdlLocation": "EdlLocation",
                "#AudioTrack": audiotrack,
            },
            ExpressionAttributeValues={":Manifest": edl_location},
        )
    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    except Exception as e:
        logger.info(
            f"Unable to update HLS Master Manifest for event '{name}' in program '{program}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to update HLS Master Manifest for event '{name}' in program '{program}': {str(e)}"
        )

    else:
        logger.info(
            f"Successfully stored the HLS Master Manifest for event '{name}' in program '{program}'"
        )

        return {}


@app.route("/event/all/external", cors=True, methods=["GET"], authorizer=authorizer)
def list_events_external():
    """
    List all the events for integrating with external systems.

    Returns:

        .. code-block:: python

            [
                {
                    Event
                }
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        logger.info("Listing all the events")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.scan(ConsistentRead=True)

        events = response["Items"]

        while "LastEvaluatedKey" in response:
            response = event_table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"], ConsistentRead=True
            )

            events.extend(response["Items"])

        all_events = []
        for event in events:
            if "LastKnownMediaLiveConfig" in event:
                event.pop("LastKnownMediaLiveConfig")
                all_events.append(event)

    except Exception as e:
        logger.info(f"Unable to list all the events: {str(e)}")
        raise ChaliceViewError(f"Unable to list all the events: {str(e)}")

    else:
        return replace_decimals(all_events)


@app.route("/event/future/all", cors=True, methods=["GET"], authorizer=authorizer)
def list_future_events():
    """
    List all the events scheduled in the future in the next 1 Hr.

    Returns:

        .. code-block:: python

            [
                {
                    Event
                }
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)
        cur_utc_time = datetime.utcnow()

        # Look for Events scheduled in the next 1 Hr
        future_time_one_hr_away = cur_utc_time + timedelta(hours=1)

        filter_expression = Attr("Start").between(
            cur_utc_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            future_time_one_hr_away.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

        response = event_table.scan(
            FilterExpression=filter_expression,
            ConsistentRead=True,
            ProjectionExpression="Profile, #status, #program, #created, FrameRate, #eventId, #start, #eventname",
            ExpressionAttributeNames={
                "#status": "Status",
                "#created": "Created",
                "#program": "Program",
                "#eventId": "Id",
                "#start": "Start",
                "#eventname": "Name",
            },
        )

        future_events = response["Items"]
    except Exception as e:
        logger.info(f"Unable to list future events: {str(e)}")
        raise ChaliceViewError(f"Unable to list future events: {str(e)}")

    else:
        return replace_decimals(future_events)


@app.route(
    "/event/range/{fromDate}/{toDate}",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def list_range_based_events(fromDate, toDate):
    """
    List all the events based on Date Range which is in UTC format

    Returns:

        .. code-block:: python

            [
                {
                    Event
                }
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:

        validate_path_parameters({"FromDate": fromDate, "ToDate": toDate})

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)
        filter_expression = Attr("Start").between(fromDate, toDate)

        response = event_table.scan(
            FilterExpression=filter_expression,
            ConsistentRead=True,
            ProjectionExpression="Profile, #status, #program, #created, FrameRate, #eventId, #start, #eventname",
            ExpressionAttributeNames={
                "#status": "Status",
                "#created": "Created",
                "#program": "Program",
                "#eventId": "Id",
                "#start": "Start",
                "#eventname": "Name",
            },
        )
        future_events = response["Items"]

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    except Exception as e:
        logger.info(f"Unable to list range based events: {str(e)}")
        raise ChaliceViewError(f"Unable to list range based events: {str(e)}")

    else:
        return replace_decimals(future_events)


@app.route(
    "/event/queued/all/limit/{limit}/closestEventFirst/{closestEventFirst}",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_all_queued_events(limit, closestEventFirst="Y"):
    """
    Gets all Queued Events for processing.

    Returns:

        .. code-block:: python

            [
                {
                    Event
                }
                ...
            ]

    Raises:
        500 - ChaliceViewError
    """
    try:
        limit = urllib.parse.unquote(limit)
        closestEventFirst = urllib.parse.unquote(closestEventFirst)
        validate_path_parameters({"Limit": limit, "ClosestEventFirst": closestEventFirst})

        if closestEventFirst.lower() not in ["y", "n"]:
            raise Exception(
                "Invalid closestEventFirst parameter value specified. Valid values are Y/N"
            )

        events_table = ddb_resource.Table(EVENT_TABLE_NAME)

        query = {
            "IndexName": EVENT_PAGINATION_INDEX,
            "Limit": limit,
            "ScanIndexForward": (
                True if closestEventFirst == "Y" else False
            ),  # Get the closest events first by default
            "KeyConditionExpression": Key("PaginationPartition").eq(
                "PAGINATION_PARTITION"
            ),
            "FilterExpression": Attr("Status").eq("Queued"),
            "ProjectionExpression": "Profile, #status, #program, #created, FrameRate, #eventId, #start, #eventname, #programid, #srcvideoAuth, #srcvideoUrl, #bootstrapTimeInMinutes",
            "ExpressionAttributeNames": {
                "#status": "Status",
                "#created": "Created",
                "#program": "Program",
                "#eventId": "Id",
                "#start": "Start",
                "#eventname": "Name",
                "#programid": "ProgramId",
                "#srcvideoAuth": "SourceVideoAuth",
                "#srcvideoUrl": "SourceVideoUrl",
                "#bootstrapTimeInMinutes": "BootstrapTimeInMinutes",
            },
        }

        response = events_table.query(**query)
        queued_events = response["Items"]

        while "LastEvaluatedKey" in response and (limit - len(queued_events) > 0):
            query["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            query["Limit"] = limit - len(queued_events)
            response = events_table.query(**query)
            queued_events.extend(response["Items"])

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    except Exception as e:
        logger.info(f"Unable to get all Queued events: {str(e)}")
        raise ChaliceViewError(f"Unable to get count of current events: {str(e)}")

    else:
        return replace_decimals(queued_events)


@app.route(
    "/event/processed/{id}", cors=True, methods=["DELETE"], authorizer=authorizer
)
def delete_processed_events_from_control(id):
    """
    Deletes Events from the Control table used to track Event processing status

    Returns:

        None
    """

    event_id = urllib.parse.unquote(id)
    

    try:
        validate_path_parameters({"Id": id})

        current_events_table = ddb_resource.Table(CURRENT_EVENTS_TABLE_NAME)

        current_events_table.delete_item(Key={"EventId": event_id})

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    
    except NotFoundError as e:
        logger.info(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        logger.info(f"Unable to delete the event '{event_id}': {str(e)}")
        raise ChaliceViewError(f"Unable to delete the event '{event_id}': {str(e)}")

    else:
        logger.info(f"Deletion of event '{event_id}' successful")
        return {}


@app.route(
    "/event/{name}/program/{program}/hasreplays",
    cors=True,
    methods=["PUT"],
    authorizer=authorizer,
)
def update_event_with_replay(name, program):
    """
    Updates an event with a flag to indicate Replay creation.

    Parameters:
        - name: Name of the Event.
        - program: Name of the Program.

    Returns:

        None
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)
        validate_path_parameters({"Name": name, "Program": program})

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={"Name": name, "Program": program},
            UpdateExpression="SET #hasreplays = :hasreplays",
            ExpressionAttributeNames={"#hasreplays": "hasReplays"},
            ExpressionAttributeValues={":hasreplays": True},
        )
    
    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except Exception as e:
        logger.info(f"Unable to update the event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to update the event '{name}' in program '{program}': {str(e)}"
        )

    else:
        logger.info("Successfully updated the event")

        return {}


@app.route(
    "/event/program/export_data", cors=True, methods=["PUT"], authorizer=authorizer
)
def store_event_export_data():
    """
    Store the Export data generated for the Event as a S3 Location

    Returns:

        None

    Raises:
        500 - ChaliceViewError

    """
    try:
        payload = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)
        validate(event=payload, schema=API_SCHEMA["export_data"])

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)
        event_name = payload["Name"]
        program = payload["Program"]

        if "IsBaseEvent" not in payload:
            raise Exception("Unable to determine the event type")

        if payload["IsBaseEvent"] not in ["Y", "N"]:
            raise Exception("Invalid base event type")

        if payload["IsBaseEvent"] == "Y":
            updateExpression = "SET #EventDataExportLocation = :EventDataExportLocation"
            expressionAttributeNames = {
                "#EventDataExportLocation": "EventDataExportLocation"
            }
            expressionAttributeValues = {
                ":EventDataExportLocation": payload["ExportDataLocation"]
            }
        else:
            updateExpression = (
                "SET #FinalEventDataExportLocation = :FinalEventDataExportLocation"
            )
            expressionAttributeNames = {
                "#FinalEventDataExportLocation": "FinalEventDataExportLocation"
            }
            expressionAttributeValues = {
                ":FinalEventDataExportLocation": payload["ExportDataLocation"]
            }

        event_table.update_item(
            Key={
                "Name": event_name,
                "Program": program,
            },
            UpdateExpression=updateExpression,
            ExpressionAttributeNames=expressionAttributeNames,
            ExpressionAttributeValues=expressionAttributeValues,
        )
    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    except Exception as e:
        logger.info(
            f"Unable to store the Event data export of event '{event_name}' in program '{program}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to store the Event data export of event '{event_name}' in program '{program}': {str(e)}"
        )

    else:
        logger.info(
            f"Successfully stored the Event data export of event '{event_name}' in program '{program}'"
        )

        return {}


@app.route(
    "/event/{name}/export/data/program/{program}",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_event_export_data(program, name):
    """
    Returns the export data for an event as a octet-stream

    Returns:

        Event export data as octet-stream

    Raises:
        400 - BadRequestError
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        program = urllib.parse.unquote(program)
        event = urllib.parse.unquote(name)
        validate_path_parameters({"Name": event, "Program": program})

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={"Name": event, "Program": program}, ConsistentRead=True
        )
        if "Item" not in response:
            raise NotFoundError(f"Event '{event}' in Program '{program}' not found")

        if "EventDataExportLocation" not in response["Item"]:
            return {"BlobContent": "NA"}

        export_location = response["Item"]["EventDataExportLocation"]

        parts = export_location.split("/")
        bucket = parts[2]
        key = "/".join(parts[-3:])

        export_filecontent = ""
        file_content = (
            s3_resource.Object(bucket, key)
            .get()["Body"]
            .read()
            .decode("utf-8")
            .splitlines()
        )
        for line in file_content:
            export_filecontent += str(line) + "\n"

        return {"BlobContent": export_filecontent}
    
    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")


@app.route(
    "/event/{name}/edl/program/{program}/track/{audiotrack}",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_edl_by_event(program, name, audiotrack):
    """
    Returns the EDL format of an MRE Event as a octet-stream

    Returns:

       EDL format of an MRE Event as a octet-stream

    Raises:
        404 - NotFoundError
    """
    try:
        program = urllib.parse.unquote(program)
        event = urllib.parse.unquote(name)
        audiotrack = urllib.parse.unquote(audiotrack)
        validate_path_parameters(
                {"Name": event, "Program": program, "AudioTrack": audiotrack}
            )

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={"Name": event, "Program": program}, ConsistentRead=True
        )
        if "Item" not in response:
            raise NotFoundError(f"Event '{event}' in Program '{program}' not found")

        if "EdlLocation" not in response["Item"]:
            return {"BlobContent": "No Content found"}

        edl = response["Item"]["EdlLocation"]
        if str(audiotrack) in edl.keys():

            s3_location = edl[str(audiotrack)]
            parts = s3_location.split("/")
            bucket = parts[2]
            key = "/".join(parts[-4:])

            edlfilecontent = ""
            file_content = (
                s3_resource.Object(bucket, key)
                .get()["Body"]
                .read()
                .decode("utf-8")
                .splitlines()
            )
            for line in file_content:
                edlfilecontent += str(line) + "\n"

            return {"BlobContent": edlfilecontent}

        return {"BlobContent": "No Content found"}
    
    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")


@app.route(
    "/event/{name}/hls/eventmanifest/program/{program}/track/{audiotrack}",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_hls_manifest_by_event(program, name, audiotrack):
    """
    Returns the HLS format of an MRE Event as a octet-stream

    Returns:

       HLS format of an MRE Event as a octet-stream

    Raises:
        404 - NotFoundError
    """
    try:
        program = urllib.parse.unquote(program)
        event = urllib.parse.unquote(name)
        audiotrack = urllib.parse.unquote(audiotrack)

        validate_path_parameters(
                {"Name": event, "Program": program, "AudioTrack": audiotrack}
            )

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={"Name": event, "Program": program}, ConsistentRead=True
        )
        if "Item" not in response:
            raise NotFoundError(f"Event '{event}' in Program '{program}' not found")

        if "HlsMasterManifest" not in response["Item"]:
            return {"HlsMasterManifest": "No Content found"}

        master_manifest = response["Item"]["HlsMasterManifest"]

        if str(audiotrack) in master_manifest.keys():
            # url = create_signed_url(master_manifest[str(audiotrack)])
            s3_location = master_manifest[str(audiotrack)]
            parts = s3_location.split("/")
            bucket = parts[2]
            key = "/".join(parts[-4:])

            hlsfilecontent = ""
            file_content = (
                s3_resource.Object(bucket, key)
                .get()["Body"]
                .read()
                .decode("utf-8")
                .splitlines()
            )
            for line in file_content:
                hlsfilecontent += str(line) + "\n"

            return {"BlobContent": hlsfilecontent}

        return {"BlobContent": "No Content found"}
    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

@app.route(
    "/event/{name}/program/{program}/context-variables",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_event_context_variables(program, name):
    """
    Get a metadata of event by name.

    Returns:

        .. code-block:: python

            {
                "KEY1": string,
                "KEY2": string,
                ...
                "KEY10": string
            }

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)
        validate_path_parameters({"Name": name, "Program": program})

        logger.info(f"Getting the event context variables for '{name}'")

        response = metadata_table.get_item(
            Key={"pk": f"EVENT#{program}#{name}"},
            ConsistentRead=True,
        )

        ## We don't want to return an ERROR if there is no metadata
        if "Item" not in response:
            return {}
        if "data" not in response["Item"]:
            return {}
    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    except Exception as e:
        logger.info(f"Unable to get event context variables '{name}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to get the event context variables '{name}': {str(e)}"
        )

    else:
        return replace_decimals(response["Item"]["data"])


@app.route(
    "/event/{name}/program/{program}/context-variables",
    cors=True,
    methods=["PATCH"],
    authorizer=authorizer,
)
def update_event_context_variables(program, name):
    """
    Replace a key/value pair of context variables of event by name.

    Returns:

        .. code-block:: python

            {
                "KEY1": string,
                "KEY2": string,
                ...
                "KEY10": string
            }

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)
        validate_path_parameters({"Name": name, "Program": program})

        event_metadata = json.loads(
            app.current_request.raw_body.decode(), parse_float=Decimal
        )
        validate(event=event_metadata, schema=API_SCHEMA["update_context_variables"])

        logger.info(f"Updating the event context variables for '{name}'")

        ## Create key/value pairs for update expression
        expression_attribute_names = {"#data": "data"}
        expression_attribute_values = {}
        update_expression = []

        ## Iterate through items
        item_count = 0
        for key, value in event_metadata.items():
            expression_attribute_names[f"#k{item_count}"] = key
            expression_attribute_values[f":v{item_count}"] = value
            update_expression.append(f"#data.#k{item_count} = :v{item_count}")
            item_count += 1

        if update_expression:
            ## Send update expression
            metadata_table.update_item(
                Key={
                    "pk": f"EVENT#{program}#{name}",
                },
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                UpdateExpression=f"SET {', '.join(update_expression)}",
            )

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    
    except Exception as e:
        logger.info(f"Unable to update event context variables '{name}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to update the event context variables '{name}': {str(e)}"
        )

    else:
        return {}


@app.route(
    "/event/{name}/hls/stream/program/{program}",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_event_hls_stream(name, program):
    """
    Returns a Cloudfront Signed Url for the main HLS manifest file associated with the event.

    Returns:

        .. code-block:: python

            {
                "SignedManifestUrl": ""
            }
    """

    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)
        validate_path_parameters({"Name": name, "Program": program})

        logger.info(f"Getting the Event '{name}' in Program '{program}'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={"Name": name, "Program": program}, ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Event '{name}' in Program '{program}' not found")

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    
    except NotFoundError as e:
        logger.info(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        logger.info(f"Unable to get the Event '{name}' in Program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to get the Event '{name}' in Program '{program}': {str(e)}"
        )

    event_info = replace_decimals(response["Item"])
    return {"ManifestUrl": rewrite_transient_hls_manifest(event_info)}


def rewrite_transient_hls_manifest(event):
    """
    Creates a new HLS Manifest and returns a signed url for it.
    """
    key_parts = event[
        "SourceHlsMasterManifest"
    ]  # Location to HLS Manifest m3u8 - s3ssl://BUCKET/x/x.m3u8
    bucket = key_parts.split("/")[2]

    manifest_location = get_hls_manifest_location(event)
    logger.info(f"Bucket={bucket}")

    manifest_content = []
    s3 = boto3.resource("s3")

    private_key_secret = sm_client.get_secret_value(
        SecretId="MRE_event_hls_streaming_private_key"
    )
    privateKey = private_key_secret["SecretString"]

    key_pair_id_secret = sm_client.get_secret_value(
        SecretId="MRE_event_hls_streaming_public_key"
    )
    public_key = key_pair_id_secret["SecretString"]

    privateKey = rsa.PrivateKey.load_pkcs1(privateKey)
    expiry = datetime.now() + timedelta(
        hours=int(HLS_STREAMING_SIGNED_URL_EXPIRATION_HRS)
    )
    rsa_signer = functools.partial(rsa.sign, priv_key=privateKey, hash_method="SHA-1")

    cf_signer = CloudFrontSigner(public_key, rsa_signer)
    policy = cf_signer.build_policy(
        f"https://{CLOUDFRONT_DOMAIN_NAME}/*", expiry
    ).encode("utf8")
    policy_64 = cf_signer._url_b64encode(policy).decode("utf8")
    signature = rsa_signer(policy)
    signature_64 = cf_signer._url_b64encode(signature).decode("utf8")
    key_pair_id = sm_client.get_secret_value(
        SecretId="MRE_event_hls_streaming_private_key_pair_id"
    )["SecretString"]

    # Generate a future datetime 48 hrs
    cur_utc_time = datetime.now(timezone.utc)
    expire_date = cur_utc_time + timedelta(
        hours=int(HLS_STREAMING_SIGNED_URL_EXPIRATION_HRS)
    )
    expiration_epoc = calendar.timegm(expire_date.timetuple())

    # Read the HLS Manifest file and rewrite the content
    first_manifest_content = (
        s3.Object(bucket, f"{manifest_location}")
        .get()["Body"]
        .read()
        .decode("utf-8")
        .splitlines()
    )
    for line in first_manifest_content:
        # Replace existing ts files with signed urls
        if ".ts" in line:
            ts_location = create_cloudfront_signed_url(
                line, expiration_epoc, signature_64, key_pair_id, policy_64, False
            )
            manifest_content.append(ts_location)
        else:
            manifest_content.append(line)

    key_prefix = get_hls_manifest_s3_key_prefix(event)

    # Write the new HLS Manifest file
    new_manifest_file_location = f"{key_prefix}/_{str(uuid.uuid4())}.m3u8"
    s3.Object(bucket, new_manifest_file_location).put(Body="\n".join(manifest_content))

    # Sign the new m3u8 manifest file and return
    return create_cloudfront_signed_url(
        new_manifest_file_location,
        expiration_epoc,
        signature_64,
        key_pair_id,
        policy_64,
    )


def create_cloudfront_signed_url(
    object_location,
    expiration_epoc,
    signature_64,
    key_pair_id,
    policy_64,
    is_manifest_file=True,
):
    return (
        f"https://{CLOUDFRONT_DOMAIN_NAME}/{object_location}?Expires={expiration_epoc}&Signature={signature_64}&Policy={policy_64}&Key-Pair-Id={key_pair_id}"
        if is_manifest_file
        else f"{object_location}?Expires={expiration_epoc}&Signature={signature_64}&Policy={policy_64}&Key-Pair-Id={key_pair_id}"
    )


def get_hls_manifest_s3_key_prefix(event):
    key_parts = event[
        "SourceHlsMasterManifest"
    ]  # Location to HLS Manifest m3u8 - s3ssl://BUCKET/x/x.m3u8

    # Get the key prefix from the s3ssl://BUCKET/x/x.m3u8
    key_prefix = key_parts.split("/")[:-1]
    key_prefix = "/".join(key_prefix)  # Remove Object name
    key_prefix = key_prefix.split("/")
    s3_key_prefix = "/".join(key_prefix[3:])  # Remove s3ssl, '', BUCKET_NAME
    return s3_key_prefix  # Without Object Name


def get_hls_manifest_location(event):
    key_parts = event[
        "SourceHlsMasterManifest"
    ]  # Location to HLS Manifest m3u8 - s3ssl://BUCKET/x/x.m3u8
    manifest_name = key_parts.split("/")[-1:][0]

    key_prefix = get_hls_manifest_s3_key_prefix(event)
    logger.info(f"Manifest file location -  {key_prefix}/{manifest_name}")
    return f"{key_prefix}/{manifest_name}"


@app.route(
    "/event/medialive/channel/create",
    cors=True,
    methods=["POST"],
    authorizer=authorizer,
)
def create_medialive_channel():
    """
    Creates a MediaLive channel with the given S3 source video URI (MP4) as input

    Body:

    .. code-block:: python

        {
            "Name": string,
            "Program": string,
            "Profile": string,
            "S3Uri": string
        }

    Parameters:

        - Name: [REQUIRED] Name of the Event.
        - Program: [REQUIRED] Name of the Program.
        - Profile: [REQUIRED] Name of the MRE Profile to make use of for processing the event.
        - S3Uri: [REQUIRED] URI of the source MP4 video file in S3.

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        payload = json.loads(app.current_request.raw_body.decode())

        validate(event=payload, schema=API_SCHEMA["create_media_live_channel"])

        name = payload["Name"]
        program = payload["Program"]
        profile = payload["Profile"]
        s3uri = payload["S3Uri"]

        logger.info(
            f"Creating a MediaLive Input for event '{name}', program '{program}', profile '{profile}' and S3 URI '{s3uri}'"
        )
        ml_input = helpers.create_medialive_input(s3uri)

        logger.info(
            f"Creating a MediaLive Channel for event '{name}', program '{program}', profile '{profile}' and S3 URI '{s3uri}'"
        )
        ml_channel = helpers.create_medialive_channel(ml_input, name, program, profile)

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")
    
    except Exception as e:
        logger.info(
            f"Unable to create a MediaLive channel for event '{name}', program '{program}', profile '{profile}' and S3 URI '{s3uri}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to create a MediaLive channel for event '{name}', program '{program}', profile '{profile}' and S3 URI '{s3uri}': {str(e)}"
        )

    else:
        logger.info(
            f"Successfully created a MediaLive channel for event '{name}', program '{program}', profile '{profile}' and S3 URI '{s3uri}'"
        )
        return {"Channel": ml_channel["Id"]}

def validate_path_parameters(params: dict):
    validate(event=params, schema=API_SCHEMA["event_path_validation"])
