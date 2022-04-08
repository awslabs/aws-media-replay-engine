#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import json
import uuid
import urllib.parse
import boto3
from decimal import Decimal
from datetime import datetime, timedelta
from chalice import Chalice, Response
from chalice import IAMAuthorizer
from chalice import ChaliceViewError, BadRequestError, ConflictError, NotFoundError
from boto3.dynamodb.types import TypeSerializer
from boto3.dynamodb.conditions import Key, Attr
from botocore.client import ClientError
from jsonschema import validate, ValidationError, FormatChecker
from chalicelib import DecimalEncoder
from chalicelib import helpers
from chalicelib import load_api_schema, replace_decimals, replace_floats
    


app = Chalice(app_name='aws-mre-controlplane-event-api')

API_VERSION = '1.0.0'
authorizer = IAMAuthorizer()
serializer = TypeSerializer()

ddb_resource = boto3.resource("dynamodb")
medialive_client = boto3.client("medialive")
eb_client = boto3.client("events")
s3_resource = boto3.resource("s3")
sm_client = boto3.client("secretsmanager")

API_SCHEMA = load_api_schema()

EVENT_TABLE_NAME = os.environ['EVENT_TABLE_NAME']
EVENT_PAGINATION_INDEX = os.environ['EVENT_PAGINATION_INDEX']
EVENT_PROGRAMID_INDEX = os.environ['EVENT_PROGRAMID_INDEX']
EVENT_CHANNEL_INDEX = os.environ['EVENT_CHANNEL_INDEX']
EB_EVENT_BUS_NAME = os.environ['EB_EVENT_BUS_NAME']
CURRENT_EVENTS_TABLE_NAME = os.environ['CURRENT_EVENTS_TABLE_NAME']

@app.route('/event', cors=True, methods=['POST'], authorizer=authorizer)
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
            "Archive": boolean
        }

    Parameters:

        - Name: Name of the Event
        - Program: Name of the Program
        - Description: Event Description 
        - Channel: Identifier of the AWS Elemental MediaLive Channel used for the Event
        - ProgramId: A Unique Identifier for the event being broadcasted.
        - SourceVideoUrl: VOD or Live Urls to help MRE to harvest the streams
        - SourceVideoAuth: A Dict which contains API Authorization payload to help MRE harvest VOD/Live streams
        - SourceVideoMetadata: A Dict of additional Event Metadata for reporting purposes.
        - BootstrapTimeInMinutes: Duration in Minutes which indicates the time it takes for the VOD/Live stream harvester to be initialized
        - Profile: Name of the MRE Profile to make use of for processing the event
        - ContentGroup: Name of the Content Group
        - Start: The Actual start DateTime of the event
        - DurationMinutes: The Total Event Duration
        - Archive: Backup the Source Video if true.

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

        validate(instance=event, schema=API_SCHEMA["create_event"], format_checker=FormatChecker())

        print("Got a valid event schema")

        name = event["Name"]
        program = event["Program"]

        is_vod_event = False

        start_utc_time = datetime.strptime(event["Start"], "%Y-%m-%dT%H:%M:%SZ")
        cur_utc_time = datetime.utcnow()

        event["BootstrapTimeInMinutes"] = event["BootstrapTimeInMinutes"] if "BootstrapTimeInMinutes" in event else 5
        event["Id"] = str(uuid.uuid4())
        event["Status"] = "Queued"
        event["Created"] = cur_utc_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        event["HlsMasterManifest"] = {}
        event["EdlLocation"] = {}
        event["PaginationPartition"] = "PAGINATION_PARTITION"
        event["StartFilter"] = event["Start"]

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        if "Channel" in event and event["Channel"]:
            # Check if the event start time is in the past
            if cur_utc_time >= start_utc_time:
                is_vod_event = True

            event["LastKnownMediaLiveConfig"] = helpers.add_or_update_medialive_output_group(name, program, event["Profile"],
                                                                                     event["Channel"])

            # Add or Update the CW Alarm for the MediaLive channel
            helpers.create_cloudwatch_alarm_for_channel(event["Channel"])

        if "SourceVideoAuth" in event:
            response = sm_client.create_secret(
                Name=f"/MRE/Event/{event['Id']}/SourceVideoAuth",
                SecretString=json.dumps(event["SourceVideoAuth"]),
                Tags=[
                    {
                        "Key": "Project",
                        "Value": "MRE"
                    },
                    {
                        "Key": "Program",
                        "Value": program
                    },
                    {
                        "Key": "Event",
                        "Value": name
                    }
                ]
            )

            event["SourceVideoAuthSecretARN"] = response["ARN"]
            event.pop("SourceVideoAuth", None)

        print(f"Creating the event '{name}' in program '{program}'")

        event_table.put_item(
            Item=replace_floats(event),
            ConditionExpression="attribute_not_exists(#Name) AND attribute_not_exists(#Program)",
            ExpressionAttributeNames={
                "#Name": "Name",
                "#Program": "Program"
            }
        )

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except ConflictError as e:
        print(f"Got chalice ConflictError: {str(e)}")
        raise

    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")

        if "LastKnownMediaLiveConfig" in event:
            medialive_client.update_channel(
                ChannelId=event["Channel"],
                Destinations=event["LastKnownMediaLiveConfig"]["Destinations"],
                EncoderSettings=event["LastKnownMediaLiveConfig"]["EncoderSettings"]
            )

        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ConflictError(f"Event '{name}' in program '{program}' already exists")
        else:
            raise

    except Exception as e:
        print(f"Unable to create the event '{name}' in program '{program}': {str(e)}")

        if "LastKnownMediaLiveConfig" in event:
            medialive_client.update_channel(
                ChannelId=event["Channel"],
                Destinations=event["LastKnownMediaLiveConfig"]["Destinations"],
                EncoderSettings=event["LastKnownMediaLiveConfig"]["EncoderSettings"]
            )

        raise ChaliceViewError(f"Unable to create the event '{name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully created the event: {json.dumps(event)}")

        if is_vod_event:
            channel_id = event["Channel"]
            print(f"Starting the MediaLive channel '{channel_id}' as the event is based on a VOD asset")

            try:
                medialive_client.start_channel(
                    ChannelId=channel_id
                )

            except Exception as e:
                print(
                    f"Creation of event '{name}' in program '{program}' is successful but unable to start the MediaLive channel '{channel_id}': {str(e)}")
                raise ChaliceViewError(
                    f"Creation of event '{name}' in program '{program}' is successful but unable to start the MediaLive channel '{channel_id}': {str(e)}")

        return {}


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
                    "ContentGroup: string
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
        # query_params = event["queryStringParameters"]
        limit = 100
        filter_expression = None
        last_evaluated_key = None
        projection_expression = None

        if query_params:
            if "limit" in query_params:
                limit = int(query_params.get("limit"))
            if "hasReplays" in query_params and query_params.get("hasReplays") == "true":
                filter_expression = Attr("hasReplays").eq(True)
            if "LastEvaluatedKey" in query_params:
                last_evaluated_key = query_params.get("LastEvaluatedKey")
            if "ProjectionExpression" in query_params:
                projection_expression = query_params.get("ProjectionExpression")
            if "fromFilter" in query_params:
                start = query_params.get("fromFilter")
                filter_expression = Attr("StartFilter").gte(start) if \
                    not filter_expression else filter_expression & Attr("StartFilter").gte(start)
            if "toFilter" in query_params:
                end = query_params.get("toFilter")
                filter_expression = Attr("StartFilter").lte(end) if \
                    not filter_expression else filter_expression & Attr("StartFilter").lte(end)
            if "ContentGroup" in query_params:
                content_group = query_params["ContentGroup"]
                filter_expression = Attr("ContentGroup").eq(content_group) if \
                    not filter_expression else filter_expression & Attr("ContentGroup").eq(content_group)
        if path_params:
            if list(path_params.keys())[0] == "ContentGroup":
                content_group = list(path_params.values())[0]
                filter_expression = Attr("ContentGroup").eq(content_group) if \
                    not filter_expression else filter_expression & Attr("ContentGroup").eq(content_group)

        print(f"Getting '{limit}' Events'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        query = {
            'IndexName': EVENT_PAGINATION_INDEX,
            'Limit': limit,
            'ScanIndexForward': False,  # descending
            'KeyConditionExpression': Key("PaginationPartition").eq("PAGINATION_PARTITION")
        }

        if filter_expression:
            query["FilterExpression"] = filter_expression
        if last_evaluated_key:
            query["ExclusiveStartKey"] = json.loads(last_evaluated_key)
        if projection_expression:
            query["ProjectionExpression"] = ", ".join(["#" + name for name in projection_expression.split(', ')])
            expression_attribute_names = {}
            for item in query["ProjectionExpression"].split(', '):
                expression_attribute_names[item] = item[1:]
            query["ExpressionAttributeNames"] = expression_attribute_names

        response = event_table.query(**query)
        events = response["Items"]

        while "LastEvaluatedKey" in response and (limit - len(events) > 0):
            query["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            query["Limit"] = limit - len(events)
            response = event_table.query(**query)
            events.extend(response["Items"])

    except Exception as e:
        print(f"Unable to get the Events")
        raise ChaliceViewError(f"Unable to get Events")

    else:
        ret_val = {
            "LastEvaluatedKey": response["LastEvaluatedKey"] if "LastEvaluatedKey" in response else "",
            "Items": replace_decimals(events)
        }

        return ret_val


@app.route('/event/contentgroup/{content_group}/all', cors=True, methods=['GET'], authorizer=authorizer)
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
                        "ContentGroup: string
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


@app.route('/event/all', cors=True, methods=['GET'], authorizer=authorizer)
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
                        "ContentGroup: string
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


@app.route('/event/{name}/program/{program}', cors=True, methods=['GET'], authorizer=authorizer)
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
                "Created": timestamp
            }

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)

        print(f"Getting the Event '{name}' in Program '{program}'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={
                "Name": name,
                "Program": program
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Event '{name}' in Program '{program}' not found")

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to get the Event '{name}' in Program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to get the Event '{name}' in Program '{program}': {str(e)}")

    else:
        return replace_decimals(response["Item"])


@app.route('/event/{name}/program/{program}', cors=True, methods=['PUT'], authorizer=authorizer)
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
            "BootstrapTimeInMinutes": integer,
            "Profile": string,
            "ContentGroup": string,
            "Start": timestamp,
            "DurationMinutes": integer,
            "Archive": boolean
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

        event = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=event, schema=API_SCHEMA["update_event"])

        print("Got a valid event schema")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={
                "Name": name,
                "Program": program
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Event '{name}' in Program '{program}' not found")

        print(f"Updating the event '{name}' in program '{program}'")

        if "ProgramId" in event and event["ProgramId"]:
            program_id = event["ProgramId"]
            existing_program_id = response["Item"]["ProgramId"] if "ProgramId" in response["Item"] else ""

            if program_id != existing_program_id:
                response = event_table.query(
                    IndexName=EVENT_PROGRAMID_INDEX,
                    KeyConditionExpression=Key("ProgramId").eq(program_id)
                )

                events = response["Items"]

                while "LastEvaluatedKey" in response:
                    response = event_table.query(
                        ExclusiveStartKey=response["LastEvaluatedKey"],
                        IndexName=EVENT_PROGRAMID_INDEX,
                        KeyConditionExpression=Key("ProgramId").eq(program_id)
                    )

                    events.extend(response["Items"])

                if len(events) > 0:
                    raise ConflictError(f"ProgramId '{program_id}' already exists in another event")

        if "SourceVideoAuth" in event:
            existing_auth_arn = response["Item"]["SourceVideoAuthSecretARN"] if "SourceVideoAuthSecretARN" in response[
                "Item"] else ""

            if existing_auth_arn:
                sm_client.update_secret(
                    SecretId=existing_auth_arn,
                    SecretString=json.dumps(event["SourceVideoAuth"])
                )

                event["SourceVideoAuthSecretARN"] = existing_auth_arn
                event.pop("SourceVideoAuth", None)

            else:
                response = sm_client.create_secret(
                    Name=f"/MRE/Event/{response['Item']['Id']}/SourceVideoAuth",
                    SecretString=json.dumps(event["SourceVideoAuth"]),
                    Tags=[
                        {
                            "Key": "Project",
                            "Value": "MRE"
                        },
                        {
                            "Key": "Program",
                            "Value": program
                        },
                        {
                            "Key": "Event",
                            "Value": name
                        }
                    ]
                )

                event["SourceVideoAuthSecretARN"] = response["ARN"]
                event.pop("SourceVideoAuth", None)

        update_expression = "SET #Description = :Description, #ProgramId = :ProgramId, #Profile = :Profile, #ContentGroup = :ContentGroup, #Start = :Start, #DurationMinutes = :DurationMinutes, #Archive = :Archive"

        expression_attribute_names = {
            "#Description": "Description",
            "#ProgramId": "ProgramId",
            "#Profile": "Profile",
            "#ContentGroup": "ContentGroup",
            "#Start": "Start",
            "#DurationMinutes": "DurationMinutes",
            "#Archive": "Archive"
        }

        expression_attribute_values = {
            ":Description": event["Description"] if "Description" in event else (
                response["Item"]["Description"] if "Description" in response["Item"] else ""),
            ":ProgramId": event["ProgramId"] if "ProgramId" in event else (
                response["Item"]["ProgramId"] if "ProgramId" in response["Item"] else ""),
            ":Profile": event["Profile"] if "Profile" in event else response["Item"]["Profile"],
            ":ContentGroup": event["ContentGroup"] if "ContentGroup" in event else response["Item"]["ContentGroup"],
            ":Start": event["Start"] if "Start" in event else response["Item"]["Start"],
            ":DurationMinutes": event["DurationMinutes"] if "DurationMinutes" in event else response["Item"][
                "DurationMinutes"],
            ":Archive": event["Archive"] if "Archive" in event else response["Item"]["Archive"]
        }

        if "Channel" not in response["Item"]:
            update_expression += ", #SourceVideoUrl = :SourceVideoUrl, #SourceVideoAuthSecretARN = :SourceVideoAuthSecretARN, #SourceVideoMetadata = :SourceVideoMetadata, #BootstrapTimeInMinutes = :BootstrapTimeInMinutes"

            expression_attribute_names["#SourceVideoUrl"] = "SourceVideoUrl"
            expression_attribute_names["#SourceVideoAuthSecretARN"] = "SourceVideoAuthSecretARN"
            expression_attribute_names["#SourceVideoMetadata"] = "SourceVideoMetadata"
            expression_attribute_names["#BootstrapTimeInMinutes"] = "BootstrapTimeInMinutes"

            expression_attribute_values[":SourceVideoUrl"] = event["SourceVideoUrl"] if "SourceVideoUrl" in event else \
                response["Item"]["SourceVideoUrl"]
            expression_attribute_values[":SourceVideoAuthSecretARN"] = event[
                "SourceVideoAuthSecretARN"] if "SourceVideoAuthSecretARN" in event else (
                response["Item"]["SourceVideoAuthSecretARN"] if "SourceVideoAuthSecretARN" in response["Item"] else "")
            expression_attribute_values[":SourceVideoMetadata"] = event[
                "SourceVideoMetadata"] if "SourceVideoMetadata" in event else (
                response["Item"]["SourceVideoMetadata"] if "SourceVideoMetadata" in response["Item"] else {})
            expression_attribute_values[":BootstrapTimeInMinutes"] = event[
                "BootstrapTimeInMinutes"] if "BootstrapTimeInMinutes" in event else response["Item"][
                "BootstrapTimeInMinutes"]

        event_table.update_item(
            Key={
                "Name": name,
                "Program": program
            },
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values
        )

    except ValidationError as e:
        print(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to update the event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to update the event '{name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully updated the event: {json.dumps(event, cls=DecimalEncoder)}")

        return {}

@app.route('/event/{name}/program/{program}', cors=True, methods=['DELETE'], authorizer=authorizer)
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

        query_params = app.current_request.query_params

        if query_params and query_params.get("force") == "true":
            force_delete = True
        else:
            force_delete = False

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={
                "Name": name,
                "Program": program
            },
            ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Event '{name}' in Program '{program}' not found")
        elif response["Item"]["Status"] == "In Progress":
            raise BadRequestError(f"Cannot delete Event '{name}' in Program '{program}' as it is currently in progress")

        channel_id = response["Item"]["Channel"] if "Channel" in response["Item"] else None
        profile = response["Item"]["Profile"]
        source_auth_secret_arn = response["Item"]["SourceVideoAuthSecretARN"] if "SourceVideoAuthSecretARN" in response[
            "Item"] else None

        if channel_id:
            print(
                f"Checking if MRE Destination and OutputGroup need to be deleted in the MediaLive channel '{channel_id}'")
            helpers.delete_medialive_output_group(name, program, profile, channel_id)

            print(
                f"Checking if the CloudWatch Alarm for 'InputVideoFrameRate' metric needs to be deleted for the MediaLive channel '{channel_id}'")

            response = event_table.query(
                IndexName=EVENT_CHANNEL_INDEX,
                KeyConditionExpression=Key("Channel").eq(channel_id)
            )

            events = response["Items"]

            while "LastEvaluatedKey" in response:
                response = event_table.query(
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                    IndexName=EVENT_CHANNEL_INDEX,
                    KeyConditionExpression=Key("Channel").eq(channel_id)
                )

                events.extend(response["Items"])

            if len(events) < 2:
                helpers.delete_cloudwatch_alarm_for_channel(channel_id)

        if source_auth_secret_arn:
            if force_delete:
                print(f"Deleting the secret '{source_auth_secret_arn}' immediately")

                sm_client.delete_secret(
                    SecretId=source_auth_secret_arn,
                    ForceDeleteWithoutRecovery=True
                )

            else:
                print(f"Deleting the secret '{source_auth_secret_arn}' with a recovery window of 7 days")

                sm_client.delete_secret(
                    SecretId=source_auth_secret_arn,
                    RecoveryWindowInDays=7
                )

        print(f"Deleting the Event '{name}' in Program '{program}'")

        response = event_table.delete_item(
            Key={
                "Name": name,
                "Program": program
            }
        )

        # Send a message to the Event Deletion SQS Queue to trigger the deletion of processing data in DynamoDB for the Event
        helpers.notify_event_deletion_queue(name, program, profile)

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except BadRequestError as e:
        print(f"Got chalice BadRequestError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to delete the Event '{name}' in Program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to delete the Event '{name}' in Program '{program}': {str(e)}")

    else:
        print(f"Deletion of Event '{name}' in Program '{program}' successful")
        return {}


@app.route('/event/{name}/program/{program}/timecode/firstpts/{first_pts}', cors=True, methods=['PUT'],
           authorizer=authorizer)
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

        print(
            f"Storing the first pts timecode '{first_pts}' of event '{name}' in program '{program}' in the DynamoDB table '{EVENT_TABLE_NAME}'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={
                "Name": name,
                "Program": program
            },
            UpdateExpression="SET #FirstPts = :FirstPts",
            ExpressionAttributeNames={
                "#FirstPts": "FirstPts"
            },
            ExpressionAttributeValues={
                ":FirstPts": Decimal(first_pts)
            }
        )

    except Exception as e:
        print(
            f"Unable to store the first pts timecode '{first_pts}' of event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to store the first pts timecode '{first_pts}' of event '{name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully stored the first pts timecode '{first_pts}' of event '{name}' in program '{program}'")

        return {}


@app.route('/event/{name}/program/{program}/timecode/firstpts', cors=True, methods=['GET'], authorizer=authorizer)
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

        print(f"Retrieving the first pts timecode of event '{name}' in program '{program}'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={
                "Name": name,
                "Program": program
            },
            ProjectionExpression="FirstPts"
        )

        if "Item" not in response or len(response["Item"]) < 1:
            print(f"First pts timecode of event '{name}' in program '{program}' not found")
            return None

    except Exception as e:
        print(f"Unable to retrieve the first pts timecode of event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to retrieve the first pts timecode of event '{name}' in program '{program}': {str(e)}")

    else:
        return replace_decimals(response["Item"]["FirstPts"])


@app.route('/event/{name}/program/{program}/framerate/{frame_rate}', cors=True, methods=['PUT'], authorizer=authorizer)
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

        print(
            f"Storing the frame rate '{frame_rate}' of event '{name}' in program '{program}' in the DynamoDB table '{EVENT_TABLE_NAME}'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={
                "Name": name,
                "Program": program
            },
            UpdateExpression="SET #FrameRate = :FrameRate",
            ExpressionAttributeNames={
                "#FrameRate": "FrameRate"
            },
            ExpressionAttributeValues={
                ":FrameRate": frame_rate
            }
        )

    except Exception as e:
        print(f"Unable to store the frame rate '{frame_rate}' of event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to store the frame rate '{frame_rate}' of event '{name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully stored the frame rate '{frame_rate}' of event '{name}' in program '{program}'")

        return {}


@app.route('/event/metadata/track/audio', cors=True, methods=['POST'], authorizer=authorizer)
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

        name = event["Name"]
        program = event["Program"]
        audio_tracks = event["AudioTracks"]

        print(
            f"Storing the audio tracks '{audio_tracks}' of event '{name}' in program '{program}' in the DynamoDB table '{EVENT_TABLE_NAME}'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={
                "Name": name,
                "Program": program
            },
            UpdateExpression="SET #AudioTracks = :AudioTracks",
            ExpressionAttributeNames={
                "#AudioTracks": "AudioTracks"
            },
            ExpressionAttributeValues={
                ":AudioTracks": audio_tracks
            }
        )

    except Exception as e:
        print(f"Unable to store the audio tracks '{audio_tracks}' of event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to store the audio tracks '{audio_tracks}' of event '{name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully stored the audio tracks '{audio_tracks}' of event '{name}' in program '{program}'")

        return {}


def put_events_to_event_bridge(name, program, status):
    try:
        print(f"Sending the event status to EventBridge for event '{name}' in program '{program}'")

        if status == "In Progress":
            state = "EVENT_START"
        elif status == "Complete":
            state = "EVENT_END"

        detail = {
            "State": state,
            "Event": {
                "Name": name,
                "Program": program
            }
        }

        response = eb_client.put_events(
            Entries=[
                {
                    "Source": "awsmre",
                    "DetailType": "Event Status",
                    "Detail": json.dumps(detail),
                    "EventBusName": EB_EVENT_BUS_NAME
                }
            ]
        )

        if response["FailedEntryCount"] > 0:
            print(
                f"Failed to send the event status to EventBridge for event '{name}' in program '{program}'. More details below:")
            print(response["Entries"])

    except Exception as e:
        print(f"Unable to send the event status to EventBridge for event '{name}' in program '{program}': {str(e)}")


@app.route('/event/{name}/program/{program}/status/{status}', cors=True, methods=['PUT'], authorizer=authorizer)
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

        print(f"Setting the status of event '{name}' in program '{program}' to '{status}'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={
                "Name": name,
                "Program": program
            },
            UpdateExpression="SET #Status = :Status",
            ExpressionAttributeNames={
                "#Status": "Status"
            },
            ExpressionAttributeValues={
                ":Status": status
            }
        )

        # Notify EventBridge of the Event status
        if status in ["In Progress", "Complete"]:
            put_events_to_event_bridge(name, program, status)

    except Exception as e:
        print(f"Unable to set the status of event '{name}' in program '{program}' to '{status}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to set the status of event '{name}' in program '{program}' to '{status}': {str(e)}")

    else:
        print(f"Successfully set the status of event '{name}' in program '{program}' to '{status}'")

        return {}


@app.route('/event/{name}/program/{program}/status', cors=True, methods=['GET'], authorizer=authorizer)
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

        print(f"Getting the status of event '{name}' in program '{program}'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={
                "Name": name,
                "Program": program
            },
            ProjectionExpression="#Status",
            ExpressionAttributeNames={
                "#Status": "Status"
            }
        )

        if "Item" not in response or len(response["Item"]) < 1:
            raise NotFoundError(f"Event '{name}' in program '{program}' not found")

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to get the status of event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to get the status of event '{name}' in program '{program}': {str(e)}")

    else:
        return response["Item"]["Status"]

@app.route('/event/program/hlslocation/update', cors=True, methods=['POST'], authorizer=authorizer)
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

        name = event["Name"]
        program = event["Program"]
        hls_location = event["HlsLocation"]
        audiotrack = event["AudioTrack"]

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={
                "Name": name,
                "Program": program
            },
            UpdateExpression="SET #HlsMasterManifest.#AudioTrack = :Manifest",
            ExpressionAttributeNames={
                "#HlsMasterManifest": "HlsMasterManifest",
                "#AudioTrack": audiotrack
            },
            ExpressionAttributeValues={
                ":Manifest": hls_location
            }
        )

    except Exception as e:
        print(f"Unable to update HLS Master Manifest for event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to update HLS Master Manifest for event '{name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully stored the HLS Master Manifest for event '{name}' in program '{program}'")

        return {}

@app.route('/event/program/edllocation/update', cors=True, methods=['POST'], authorizer=authorizer)
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

        name = event["Name"]
        program = event["Program"]
        edl_location = event["EdlLocation"]
        audiotrack = event["AudioTrack"]

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={
                "Name": name,
                "Program": program
            },
            UpdateExpression="SET #EdlLocation.#AudioTrack = :Manifest",
            ExpressionAttributeNames={
                "#EdlLocation": "EdlLocation",
                "#AudioTrack": audiotrack
            },
            ExpressionAttributeValues={
                ":Manifest": edl_location
            }
        )

    except Exception as e:
        print(f"Unable to update HLS Master Manifest for event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to update HLS Master Manifest for event '{name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully stored the HLS Master Manifest for event '{name}' in program '{program}'")

        return {}


@app.route('/event/all/external', cors=True, methods=['GET'], authorizer=authorizer)
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
        print("Listing all the events")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.scan(
            ConsistentRead=True
        )

        events = response["Items"]

        while "LastEvaluatedKey" in response:
            response = event_table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                ConsistentRead=True
            )

            events.extend(response["Items"])

        all_events = []
        for event in events:
            if 'LastKnownMediaLiveConfig' in event:
                event.pop('LastKnownMediaLiveConfig')
                all_events.append(event)


    except Exception as e:
        print(f"Unable to list all the events: {str(e)}")
        raise ChaliceViewError(f"Unable to list all the events: {str(e)}")

    else:
        return replace_decimals(all_events)


@app.route('/event/future/all', cors=True, methods=['GET'], authorizer=authorizer)
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

        filter_expression = Attr("Start").between(cur_utc_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                  future_time_one_hr_away.strftime("%Y-%m-%dT%H:%M:%SZ"))

        response = event_table.scan(
            FilterExpression=filter_expression,
            ConsistentRead=True,
            ProjectionExpression="Profile, #status, #program, #created, FrameRate, #eventId, #start, #eventname",
            ExpressionAttributeNames={'#status': 'Status', '#created': 'Created', '#program': 'Program',
                                      '#eventId': 'Id', '#start': 'Start', '#eventname': 'Name'}
        )

        future_events = response["Items"]
    except Exception as e:
        print(f"Unable to list future events: {str(e)}")
        raise ChaliceViewError(f"Unable to list future events: {str(e)}")

    else:
        return replace_decimals(future_events)


@app.route('/event/range/{fromDate}/{toDate}', cors=True, methods=['GET'], authorizer=authorizer)
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

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)
        filter_expression = Attr("Start").between(fromDate, toDate)

        response = event_table.scan(
            FilterExpression=filter_expression,
            ConsistentRead=True,
            ProjectionExpression="Profile, #status, #program, #created, FrameRate, #eventId, #start, #eventname",
            ExpressionAttributeNames={'#status': 'Status', '#created': 'Created', '#program': 'Program',
                                      '#eventId': 'Id', '#start': 'Start', '#eventname': 'Name'}
        )
        future_events = response["Items"]

    except Exception as e:
        print(f"Unable to list range based events: {str(e)}")
        raise ChaliceViewError(f"Unable to list range based events: {str(e)}")

    else:
        return replace_decimals(future_events)


@app.route('/event/queued/all/limit/{limit}/closestEventFirst/{closestEventFirst}', cors=True, methods=['GET'], authorizer=authorizer)
def get_all_queued_events(limit,closestEventFirst='Y'):
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

        if closestEventFirst.lower() not in ['y','n']:
            raise Exception(f"Invalid closestEventFirst parameter value specified. Valid values are Y/N")

        events_table = ddb_resource.Table(EVENT_TABLE_NAME)

        query = {
            'IndexName': EVENT_PAGINATION_INDEX,
            'Limit': limit,
            'ScanIndexForward': True if closestEventFirst == 'Y' else False,  # Get the closest events first by default
            'KeyConditionExpression': Key("PaginationPartition").eq("PAGINATION_PARTITION"),
            'FilterExpression': Attr("Status").eq('Queued'),
            'ProjectionExpression': "Profile, #status, #program, #created, FrameRate, #eventId, #start, #eventname, #programid, #srcvideoAuth, #srcvideoUrl, #bootstrapTimeInMinutes",
            'ExpressionAttributeNames': {'#status': 'Status', '#created': 'Created', '#program' : 'Program', '#eventId' : 'Id', '#start': 'Start', '#eventname' : 'Name',
                "#programid": "ProgramId", "#srcvideoAuth": "SourceVideoAuth", "#srcvideoUrl": "SourceVideoUrl", "#bootstrapTimeInMinutes" : "BootstrapTimeInMinutes"
            }
        }

        response = events_table.query(**query)
        queued_events = response["Items"]

        while "LastEvaluatedKey" in response and (limit - len(queued_events) > 0):
            query["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            query["Limit"] = limit - len(queued_events)
            response = events_table.query(**query)
            queued_events.extend(response["Items"])

    except Exception as e:
        print(f"Unable to get all Queued events: {str(e)}")
        raise ChaliceViewError(f"Unable to get count of current events: {str(e)}")

    else:
        return replace_decimals(queued_events)

@app.route('/event/processed/{id}', cors=True, methods=['DELETE'], authorizer=authorizer)
def delete_processed_events_from_control(id):
    """
    Deletes Events from the Control table used to track Event processing status

    Returns:

        None
    """

    event_id = urllib.parse.unquote(id)

    try:

        current_events_table = ddb_resource.Table(CURRENT_EVENTS_TABLE_NAME)

        current_events_table.delete_item(
                    Key={
                        "EventId": event_id
                    }
                )

    except NotFoundError as e:
        print(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        print(f"Unable to delete the event '{event_id}': {str(e)}")
        raise ChaliceViewError(f"Unable to delete the event '{event_id}': {str(e)}")

    else:
        print(f"Deletion of event '{event_id}' successful")
        return {}

@app.route('/event/{name}/program/{program}/hasreplays', cors=True, methods=['PUT'], authorizer=authorizer)
def update_event_with_replay(name, program):
    """
    Updates an event with a flag to indicate Replay creation.

    Returns:

        None
    """
    try:
        name = urllib.parse.unquote(name)
        program = urllib.parse.unquote(program)

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_table.update_item(
            Key={
                "Name": name,
                "Program": program
            },
            UpdateExpression="SET #hasreplays = :hasreplays",
            ExpressionAttributeNames={"#hasreplays": "hasReplays"},
            ExpressionAttributeValues={":hasreplays": True}
        )

    except Exception as e:
        print(f"Unable to update the event '{name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(f"Unable to update the event '{name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully updated the event")

        return {}


@app.route('/event/program/export_data', cors=True, methods=['PUT'],
           authorizer=authorizer)
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
        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        event_name = payload['Name']
        program = payload['Program']
        
        if 'IsBaseEvent' not in payload:
            raise Exception(f"Unable to determine the event type")

        if payload['IsBaseEvent'] not in ['Y', 'N']:
            raise Exception(f"Invalid base event type")

        if payload['IsBaseEvent'] == 'Y':
            updateExpression="SET #EventDataExportLocation = :EventDataExportLocation"
            expressionAttributeNames= { "#EventDataExportLocation": "EventDataExportLocation" }
            expressionAttributeValues= { ":EventDataExportLocation": payload['ExportDataLocation'] }
        else:
            updateExpression="SET #FinalEventDataExportLocation = :FinalEventDataExportLocation"
            expressionAttributeNames= { "#FinalEventDataExportLocation": "FinalEventDataExportLocation" }
            expressionAttributeValues= { ":FinalEventDataExportLocation": payload['ExportDataLocation'] }

        event_table.update_item(
            Key={
                "Name": event_name,
                "Program": program,
            },
            UpdateExpression=updateExpression,
            ExpressionAttributeNames=expressionAttributeNames,
            ExpressionAttributeValues=expressionAttributeValues
        )

    except Exception as e:
        print(
            f"Unable to store the Event data export of event '{event_name}' in program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to store the Event data export of event '{event_name}' in program '{program}': {str(e)}")

    else:
        print(f"Successfully stored the Event data export of event '{event_name}' in program '{program}'")

        return {}


@app.route('/event/{name}/export/data/program/{program}', cors=True, methods=['GET'],
           authorizer=authorizer)
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
    program = urllib.parse.unquote(program)
    event = urllib.parse.unquote(name)
    

    event_table = ddb_resource.Table(EVENT_TABLE_NAME)

    response = event_table.get_item(
        Key={
            "Name": event,
            "Program": program
        },
        ConsistentRead=True
    )
    if "Item" not in response:
        raise NotFoundError(f"Event '{event}' in Program '{program}' not found")

    if 'EventDataExportLocation' not in response['Item']:
        return {
            "BlobContent": "NA"
        }

    export_location = response['Item']['EventDataExportLocation']
    
    parts = export_location.split('/')
    bucket = parts[2]
    key = '/'.join(parts[-3:])

    export_filecontent = ""
    file_content = s3_resource.Object(bucket, key).get()['Body'].read().decode('utf-8').splitlines()
    for line in file_content:
        export_filecontent += str(line) + "\n"

    
    return {
            "BlobContent": export_filecontent
        }

@app.route('/event/{name}/edl/track/{audiotrack}/program/{program}', cors=True, methods=['GET'], authorizer=authorizer)
def get_edl_by_event(program, name, audiotrack):
    """
    Returns the EDL format of an MRE Event as a octet-stream

    Returns:

       EDL format of an MRE Event as a octet-stream

    Raises:
        404 - NotFoundError
    """
    program = urllib.parse.unquote(program)
    event = urllib.parse.unquote(name)
    audiotrack = urllib.parse.unquote(audiotrack)

    event_table = ddb_resource.Table(EVENT_TABLE_NAME)

    response = event_table.get_item(
        Key={
            "Name": event,
            "Program": program
        },
        ConsistentRead=True
    )
    if "Item" not in response:
        raise NotFoundError(f"Event '{event}' in Program '{program}' not found")

    if 'EdlLocation' not in response['Item']:
        return {"BlobContent": "No Content found"}

    edl = response['Item']['EdlLocation']
    if str(audiotrack) in edl.keys():

        s3_location = edl[str(audiotrack)]
        parts = s3_location.split('/')
        bucket = parts[2]
        key = '/'.join(parts[-4:])

        edlfilecontent = ""
        file_content = s3_resource.Object(bucket, key).get()['Body'].read().decode('utf-8').splitlines()
        for line in file_content:
            edlfilecontent += str(line) + "\n"

        return {
            "BlobContent": edlfilecontent
        }

    return {
        "BlobContent": "No Content found"
    }

@app.route('/event/{name}/hls/eventmanifest/program/{program}/track/{audiotrack}', cors=True, methods=['GET'],
           authorizer=authorizer)
def get_hls_manifest_by_event(program, name, audiotrack):
    """
    Returns the HLS format of an MRE Event as a octet-stream

    Returns:

       HLS format of an MRE Event as a octet-stream

    Raises:
        404 - NotFoundError
    """
    program = urllib.parse.unquote(program)
    event = urllib.parse.unquote(name)
    audiotrack = urllib.parse.unquote(audiotrack)

    event_table = ddb_resource.Table(EVENT_TABLE_NAME)

    response = event_table.get_item(
        Key={
            "Name": event,
            "Program": program
        },
        ConsistentRead=True
    )
    if "Item" not in response:
        raise NotFoundError(f"Event '{event}' in Program '{program}' not found")

    if 'HlsMasterManifest' not in response['Item']:
        return {
            "HlsMasterManifest": "No Content found"
        }

    master_manifest = response['Item']['HlsMasterManifest']

    if str(audiotrack) in master_manifest.keys():
        # url = create_signed_url(master_manifest[str(audiotrack)])
        s3_location = master_manifest[str(audiotrack)]
        parts = s3_location.split('/')
        bucket = parts[2]
        key = '/'.join(parts[-4:])

        hlsfilecontent = ""
        file_content = s3_resource.Object(bucket, key).get()['Body'].read().decode('utf-8').splitlines()
        for line in file_content:
            hlsfilecontent += str(line) + "\n"

        

        return {
            "BlobContent": hlsfilecontent
        }

    return {
        "BlobContent": "No Content found"
    }