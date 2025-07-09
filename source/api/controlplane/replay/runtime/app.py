#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import functools
import json
import os
import urllib.parse
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import boto3
import rsa
from aws_lambda_powertools.utilities.validation import (SchemaValidationError,
                                                        validate)
from aws_lambda_powertools import Logger
from boto3.dynamodb.conditions import Attr, Key
from datetime import datetime, timedelta, timezone
from boto3.dynamodb.types import TypeSerializer
from botocore.client import ClientError
from botocore.config import Config
from botocore.signers import CloudFrontSigner
from chalice import (BadRequestError, Chalice, ChaliceViewError, ConflictError,
                     IAMAuthorizer, NotFoundError)
from chalicelib import load_api_schema, replace_decimals
import calendar

app = Chalice(app_name="aws-mre-controlplane-replay-api")
logger = Logger(service="aws-mre-controlplane-replay-api")

REPLAY_REQUEST_TABLE_NAME = os.environ["REPLAY_REQUEST_TABLE_NAME"]
EB_EVENT_BUS_NAME = os.environ["EB_EVENT_BUS_NAME"]
HLS_HS256_API_AUTH_SECRET_KEY_NAME = os.environ["HLS_HS256_API_AUTH_SECRET_KEY_NAME"]
CLOUDFRONT_COOKIE_PRIVATE_KEY_FROM_SECRET_MGR = os.environ[
    "CLOUDFRONT_COOKIE_PRIVATE_KEY_NAME"
]
CLOUDFRONT_COOKIE_KEY_PAIR_ID_FROM_SECRET_MGR = os.environ[
    "CLOUDFRONT_COOKIE_KEY_PAIR_ID_NAME"
]
HLS_STREAM_CLOUDFRONT_DISTRO = os.environ["HLS_STREAM_CLOUDFRONT_DISTRO"]
PLUGIN_TABLE_NAME = os.environ["PLUGIN_TABLE_NAME"]
PROFILE_TABLE_NAME = os.environ["PROFILE_TABLE_NAME"]
EVENT_TABLE_NAME = os.environ["EVENT_TABLE_NAME"]
TRANSITION_CLIP_S3_BUCKET = os.environ["TRANSITION_CLIP_S3_BUCKET"]
TRANSITIONS_CONFIG_TABLE_NAME = os.environ["TRANSITIONS_CONFIG_TABLE_NAME"]
MEDIA_OUTPUT_BUCKET_NAME = os.environ["MEDIA_OUTPUT_BUCKET_NAME"]
HLS_STREAMING_SIGNED_URL_EXPIRATION_HRS = os.environ[
    "HLS_STREAMING_SIGNED_URL_EXPIRATION_HRS"
]

authorizer = IAMAuthorizer()
serializer = TypeSerializer()

ddb_resource = boto3.resource("dynamodb")
eb_client = boto3.client("events")
s3_resource = boto3.resource("s3")
sm_client = boto3.client("secretsmanager")

API_SCHEMA = load_api_schema()

# Create middleware to inject request context
@app.middleware('all')
def inject_request_context(event, get_response):
    # event is a Chalice Request object
    request_id = event.context.get('requestId', 'N/A')
    
    # Add request ID to persistent logger context
    logger.append_keys(request_id=request_id)
    
    response = get_response(event)
    return response

@app.route("/replay", cors=True, methods=["POST"], authorizer=authorizer)
def add_replay():
    """
    Add a new Replay Summarization to the system.

    Body:

    .. code-block:: python

        {
            "Program": string,
            "Event": string,
            "AudioTrack": string,
            "Description": string,
            "Requester": string,
            "UxLabel": "",
            "DurationbasedSummarization": {
                "Duration": number,
                "FillToExact": boolean,
                "EqualDistribution": boolean,
                "ToleranceMaxLimitInSecs": number
            },
            "SpecifiedTimestamps": string,
            "Priorities":{
                "CustomPrioritiesEngine": {
                    "CustomPrioritiesEngineEnabled": boolean,
                    "CustomPrioritiesEngineEndpointSsmParam": string,
                    "CustomPrioritiesEngineApiKeyArn": string,
                    "CustomPrioritiesEngineEndpointPathVariables": map
                },
                "Clips": [
                    {
                        "Name": string,
                        "Weight": number,
                        "Include": boolean,
                        "Duration": string,
                        "StartTime": number,
                        "EndTime": number,
                        "AttribValue": string,
                        "AttribName": string,
                        "PluginName": string
                    }
                ]
            }
            "ClipfeaturebasedSummarization": boolean,
            "Catchup": boolean,
            "Resolutions": list,
            "CreateHls": boolean,
            "CreateMp4": boolean,
            "TransitionName": string,
            "TransitionOverride": {
                "FadeInMs": number,
                "FadeOutMs": number,
            },
            "IgnoreDislikedSegments": boolean,
            "IncludeLikedSegments": boolean,
            "DisregardZeroWeightSegments": boolean
        }

    Parameters:

        - Program: Name of the Program
        - Event: Name of the Event
        - AudioTrack: AudioTrack number which helps MRE support regional audience needs
        - Description: Description of the Replay being created
        - Requester: Requester of the Replay
        - DurationbasedSummarization:  A Dict capturing the Duration of the Replay to be created. Duration in Secs. ToleranceMaxLimitInSecs is defaulted to 30 Secs if not specified.
        - SpecifiedTimestamps: A List of clips to be included in the Replay defined by starting and ending timestamps.
        - Priorities.CustomPrioritiesEngine: Details of the Custom Priorities Engine API endpoint, Secret ARN and a dict of path variables and their corresponding values.
        - Priorities.Clips: A List of dict. Each Dict represents the Weight of the Output Attribute which needs to be included in the Replay
        - ClipfeaturebasedSummarization: Set to True if a Duration based replay is not reqd. False, otherwise.
        - Catchup: True if a CatchUp replay is to be created, False otherwise.
        - CreateHls: True if HLS replay output is to be created
        - Resolutions: List of replay Resolutions to be created. Supported values ["4K (3840 x 2160)","2K (2560 x 1440)","16:9 (1920 x 1080)","16:9 (1920 x 1080)","16:9 (1920 x 1080)","1:1 (1080 x 1080)","4:5 (864 x 1080)","9:16 (608 x 1080)","720p (1280 x 720)","480p (854 x 480)","360p (640 x 360)"]
        - CreateMp4:True if MP4 replay output is to be created
        - TransitionName: Optional. Name of the Transition to be used when Creating Replay clips.
        - TransitionOverride: Optional. Objects represents additional Transition configuration that can be overwritten during Replay creation.
        - IgnoreDislikedSegments: Optional. Ignores segments which have been disliked (thumbs down) when reviewing the Segment clip. Default False.
        - IncludeLikedSegments: Optional. If True, segments which have been liked (thumbs up) when reviewing the Segment clip will be included in Replay. Default False.
        - DisregardZeroWeightSegments: Optional. If True, Segments with total feature weights of 0 are disregarded for replay clip

    Returns:

        None

    Raises:
        400 - BadRequestError
        409 - ConflictError
        500 - ChaliceViewError
    """
    try:
        model = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(event=model, schema=API_SCHEMA["add_replay"])

        # Validate that an Event is Valid - If a Event does not belong to a Program, error out
        event_table = ddb_resource.Table(EVENT_TABLE_NAME)
        response = event_table.get_item(
            Key={"Name": model["Event"], "Program": model["Program"]}
        )
        if "Item" not in response:
            raise ConflictError(
                f"Event '{model['Event']}' not found in Program '{model['Program']}'"
            )

        model["PK"] = f"{model['Program']}#{model['Event']}"
        model["ReplayId"] = str(uuid.uuid4())

        model["Created"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        model["LastModified"] = model["Created"]
        model["Status"] = "Queued"
        model["Enabled"] = True
        model["HlsLocation"] = "-"
        model["EdlLocation"] = "-"
        model["HlsThumbnailLoc"] = "-"
        model["Mp4Location"] = {}
        model["Mp4ThumbnailLocation"] = {}
        model["IgnoredSegments"] = []
        model["TransitionName"] = (
            "None" if "TransitionName" not in model else model["TransitionName"]
        )
        model["IgnoreDislikedSegments"] = (
            False
            if "IgnoreDislikedSegments" not in model
            else model["IgnoreDislikedSegments"]
        )
        model["IncludeLikedSegments"] = (
            False
            if "IncludeLikedSegments" not in model
            else model["IncludeLikedSegments"]
        )

        # Default ToleranceMaxLimitInSecs to 30 Secs if its not a part of Payload
        if "DurationbasedSummarization" in model:
            if "ToleranceMaxLimitInSecs" not in model["DurationbasedSummarization"]:
                model["DurationbasedSummarization"]["ToleranceMaxLimitInSecs"] = 30

        logger.info(f"Adding the Replay Request '{model['Program']}#{model['Event']}'")

        replay_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        replay_table.put_item(Item=model)

        # Publish to event bridge that a new Replay was Created
        detail = {
            "State": "REPLAY_CREATED",
            "Event": {
                "Name": model["Event"],
                "Program": model["Program"],
                "ReplayId": model["ReplayId"],
            },
        }

        eb_client.put_events(
            Entries=[
                {
                    "Source": "awsmre",
                    "DetailType": "Replay Created Status",
                    "Detail": json.dumps(detail),
                    "EventBusName": EB_EVENT_BUS_NAME,
                }
            ]
        )

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except ClientError as e:
        logger.info(f"Got DynamoDB ClientError: {str(e)}")
        raise

    except ConflictError as e:
        logger.info(
            f"Event '{model['Event']}' not found in Program '{model['Program']}': {str(e)}"
        )
        raise

    except Exception as e:
        logger.info(f"Unable to add a new Replay Request: {str(e)}")
        raise ChaliceViewError(f"Unable to add a new Replay Request: {str(e)}")

    else:
        logger.info(
            f"Successfully added a new Replay Request: {app.current_request.raw_body.decode()}"
        )

        return {}


@app.route("/replay/all", cors=True, methods=["GET"], authorizer=authorizer)
def get_all_replays():
    """
    Gets all the replay requests

    Returns:

        All Replay requests

    Raises:
        500 - ChaliceViewError
    """
    replays = []
    replay_request_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

    response = replay_request_table.scan()
    replayInfo = response["Items"]

    projection_expression = "PK, Requester, DurationbasedSummarization, ClipfeaturebasedSummarization, SpecifiedTimestamps, AudioTrack, Catchup, #st, MediaTailorChannel, ReplayId, Description, EdlLocation, HlsLocation, UxLabel, TransitionName, TransitionOverride, Created"
    expression_attribute_names = {"#st": "Status"}
    while "LastEvaluatedKey" in response:
        response = replay_request_table.scan(
            ProjectionExpression=projection_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        replayInfo.extend(response["Items"])

    sorted_replayInfo = sorted(replayInfo, key=lambda x: x["Created"], reverse=True)

    for item in sorted_replayInfo:
        replays.append(
            {
                "Program": item["PK"].split("#")[0],
                "Event": item["PK"].split("#")[1],
                "Requester": item["Requester"],
                "Duration": (
                    item["DurationbasedSummarization"]["Duration"]
                    if "DurationbasedSummarization" in item
                    else "N/A"
                ),
                "Mode": (
                    "DURATION"
                    if "DurationbasedSummarization" in item
                    else (
                        "FEATURES"
                        if item["ClipfeaturebasedSummarization"]
                        else (
                            "TIMESTAMPS" if "SpecifiedTimestamps" in item else "Error"
                        )
                    )
                ),
                "AudioTrack": item["AudioTrack"] if "AudioTrack" in item else "",
                "CatchUp": item["Catchup"],
                "Status": item["Status"],
                "DTC": True if "MediaTailorChannel" in item else False,
                "ReplayId": item["ReplayId"],
                "Description": item["Description"],
                "EdlLocation": item["EdlLocation"] if "EdlLocation" in item else "-",
                "HlsLocation": item["HlsLocation"] if "HlsLocation" in item else "-",
                "UxLabel": item["UxLabel"] if "UxLabel" in item else "",
                "TransitionName": (
                    item["TransitionName"] if "TransitionName" in item else ""
                ),
                "TransitionOverride": (
                    item["TransitionOverride"] if "TransitionOverride" in item else ""
                ),
            }
        )

    return {"Items": replace_decimals(replays)}

@app.route(
    "/replay/program/{program}/event/{event}/all",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def listreplay_by_program_event(program, event):
    """
    Gets all the replay requests based on Program and Event

    Returns:

        Replay requests based on Program and Event

    Raises:
        500 - ChaliceViewError
    """
    replays = []
    try:
        program = urllib.parse.unquote(program)
        event = urllib.parse.unquote(event)

        validate_path_parameters({"Program": program, "Event": event})

        event_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        response = event_table.query(
            KeyConditionExpression=Key("PK").eq(f"{program}#{event}"),
            ConsistentRead=True,
        )

        replayInfo = response["Items"]

        sorted_replayInfo = sorted(replayInfo, key=lambda x: x["Created"], reverse=True)

        for item in sorted_replayInfo:
            logger.info(f"listreplay_by_program_event(): item: {item}")
            replay = {
                "Program": program,
                "Event": event,
                "Duration": (
                    item["DurationbasedSummarization"]["Duration"]
                    if "DurationbasedSummarization" in item
                    else "N/A"
                ),
                "Requester": item["Requester"],
                "AudioTrack": item["AudioTrack"] if "AudioTrack" in item else "",
                "CatchUp": item["Catchup"],
                "Status": item["Status"],
                "DTC": True if "MediaTailorChannel" in item else False,
                "ReplayId": item["ReplayId"],
                "Description": item["Description"],
                "UxLabel": item["UxLabel"] if "UxLabel" in item else "",
                "EdlLocation": (
                    item["EdlLocation"] if "EdlLocation" in item else "-"
                ),
                "HlsLocation": (
                    item["HlsLocation"] if "HlsLocation" in item else "-"
                ),
                "TransitionName": (
                    item["TransitionName"] if "TransitionName" in item else ""
                ),
                "TransitionOverride": (
                    item["TransitionOverride"]
                    if "TransitionOverride" in item
                    else ""
                ),
            }
            replays.append(replay)

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except Exception as e:
        logger.info(replays)
        logger.info(f"Unable to get replays for Program and Event: {str(e)}")
        raise ChaliceViewError(f"Unable to get replays for Program and Event: {str(e)}")

    return replace_decimals(replays)

@app.route(
    "/replay/all/contentgroup/{contentGrp}",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def listreplay_by_content_group(contentGrp):
    """
    Get all the replay requests based on Content Group

    Returns:

        Replay requests based on Content Group

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    replays = []
    try:

        contentGroup = urllib.parse.unquote(contentGrp)

        validate_path_parameters({"ContentGroup": contentGroup})

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)
        event_response = event_table.scan()

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)
        profileresponse = profile_table.scan()

        for event in event_response["Items"]:
            profile = event["Profile"]

            profile_obj = None
            for profileItem in profileresponse["Items"]:
                if profileItem["Name"] == profile:
                    profile_obj = profileItem
                    break

            if profile_obj is None:
                continue

            if "ContentGroups" in profile_obj:

                # If the Profile has the Content Group, return the replays associated with the
                # Program and Event
                if contentGroup in profile_obj["ContentGroups"]:

                    replay_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)
                    replayresponse = replay_table.query(
                        KeyConditionExpression=Key("PK").eq(
                            f"{event['Program']}#{event['Name']}"
                        ),
                        ConsistentRead=True,
                    )

                    for item in replayresponse["Items"]:
                        replays.append(
                            {
                                "Program": event["Program"],
                                "Event": event["Name"],
                                "Duration": (
                                    item["DurationbasedSummarization"]["Duration"]
                                    if "DurationbasedSummarization" in item
                                    else "N/A"
                                ),
                                "Requester": item["Requester"],
                                "AudioTrack": (
                                    item["AudioTrack"] if "AudioTrack" in item else ""
                                ),
                                "CatchUp": item["Catchup"],
                                "Status": item["Status"],
                                "DTC": True if "MediaTailorChannel" in item else False,
                                "UxLabel": item["UxLabel"] if "UxLabel" in item else "",
                                "ReplayId": item["ReplayId"],
                                "Created": item["Created"],
                                "EdlLocation": (
                                    item["EdlLocation"]
                                    if "EdlLocation" in item
                                    else "-"
                                ),
                                "HlsLocation": (
                                    item["HlsLocation"]
                                    if "HlsLocation" in item
                                    else "-"
                                ),
                                "TransitionName": (
                                    item["TransitionName"]
                                    if "TransitionName" in item
                                    else ""
                                ),
                                "TransitionOverride": (
                                    item["TransitionOverride"]
                                    if "TransitionOverride" in item
                                    else ""
                                ),
                            }
                        )

        sorted_replayInfo = sorted(replays, key=lambda x: x["Created"], reverse=True)

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except Exception as e:
        logger.info(f"Unable to get replays for Program and Event: {str(e)}")
        raise ChaliceViewError(f"Unable to get replays for Program and Event: {str(e)}")

    return replace_decimals(sorted_replayInfo)

@app.route(
    "/replay/program/{program}/event/{event}/replayid/{id}",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_replay_by_program_event_id(program, event, id):
    """
    Gets the replay request based on event, program and replayId

    Returns:

        Replay Request

    Raises:
        404 - NotFoundError
    """
    try:
        eventname = urllib.parse.unquote(event)
        program = urllib.parse.unquote(program)

        validate_path_parameters({"Program": program, "Event": event, "ReplayId": id})

        replay_request_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        response = replay_request_table.get_item(
            Key={"PK": f"{program}#{eventname}", "ReplayId": id}, ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError("Replay settings not found")

        replay_request = response["Item"]
        replay_request["PreviewVideoUrls"] = []

        if "Mp4Location" in replay_request and len(replay_request["Mp4Location"].keys()) > 0:
            resolutions = replay_request["Mp4Location"].keys()
            for resolution in resolutions:
                chosen_mp4_loc = replay_request["Mp4Location"][resolution]
                if "ReplayClips" in chosen_mp4_loc:
                    if chosen_mp4_loc["ReplayClips"]:
                        mp4_loc = chosen_mp4_loc["ReplayClips"][0].split("/")
                        key = "/".join(mp4_loc[3:])
                        replay_request["Mp4Location"][resolution]["PreviewVideoUrl"] = get_media_presigned_url(
                            key, MEDIA_OUTPUT_BUCKET_NAME, False
                        )
        elif "HlsLocation" in replay_request and replay_request["HlsLocation"] != "-": 
            replay_request["HlsVideoUrl"] = get_event_hls_stream(eventname, program, id).get("ManifestUrl")
        else:
            raise NotFoundError("Replay settings misconfigured, no HLS or MP4 location found")

    except Exception as e:
        logger.info(f"Error while generating PreviewVideoUrls: {str(e)}")

    return replace_decimals(replay_request)

@app.route(
    "/replay/{event_name}/hls/stream/program/{program}",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_event_hls_stream(name, program, id):
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
        logger.info("in get_event_hls_stream")
        logger.info(f"Getting the Event '{name}' in Program '{program}'")

        requests_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        response = requests_table.get_item(
            Key={"PK": f"{program}#{name}", "ReplayId": id}, ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Event '{name}' in Program '{program}' not found")

    except NotFoundError as e:
        logger.info(f"Got chalice NotFoundError: {str(e)}")
        raise

    except Exception as e:
        logger.info(f"Unable to get the Event '{name}' in Program '{program}': {str(e)}")
        raise ChaliceViewError(
            f"Unable to get the Event '{name}' in Program '{program}': {str(e)}"
        )

    event_info = replace_decimals(response["Item"])
    logger.info(f"in get_event_hls_stream - event_info {event_info}")
    return {"ManifestUrl": rewrite_transient_hls_manifest(event_info)}

s3 = boto3.resource("s3")

def recursively_sign_m3u8_files(root_location, manifest_location, bucket, expiration_epoc, signature_64, key_pair_id, policy_64):
    logger.info(f"in recursively_sign_m3u8_files - manifest_location {manifest_location}")
    # Read the HLS Manifest file and rewrite the content

    manifest_content = (
        s3.Object(bucket, f"{root_location+manifest_location}")
        .get()["Body"]
        .read()
        .decode("utf-8")
        .splitlines()
    )

    new_manifest_content = []

    for i in range(len(manifest_content)):
        line = manifest_content[i]
        # Replace existing ts files with signed urls
        if ".ts" in line:
            signed_ts_location = create_cloudfront_signed_url(
                line.split("?")[0], expiration_epoc, signature_64, key_pair_id, policy_64, False
            )
            new_manifest_content.append(signed_ts_location)
        elif ".m3u8" in line:
            # sign line in current file. then open .m3u8 file and recursively sign all the m3u8 files in that manifest
            # sign the m3u8 file
            signed_m3u8_location = create_cloudfront_signed_url(
                line, expiration_epoc, signature_64, key_pair_id, policy_64, False
            )
            new_manifest_content.append(signed_m3u8_location)

            # recursively sign the m3u8 file
            signed_child_m3u8_content = recursively_sign_m3u8_files(root_location, line.split("?")[0], bucket, expiration_epoc, signature_64, key_pair_id, policy_64)
            
            new_manifest_file_location = f"{root_location}{line}"
            logger.info(f"rewrote manifest: {new_manifest_file_location}")
            s3.Object(bucket, new_manifest_file_location).put(Body="\n".join(signed_child_m3u8_content))
        else:
            new_manifest_content.append(line)

    return new_manifest_content

def rewrite_transient_hls_manifest(event):
    """
    Creates a new HLS Manifest and returns a signed url for it.
    """
    logger.info(f"in rewrite_transient_hls_manifest - event {event}")
    key_parts = event[
        "HlsLocation" # change this 
    ]  # Location to HLS Manifest m3u8 - s3ssl://BUCKET/x/x.m3u8
    bucket = key_parts.split("/")[2]

    manifest_location = get_hls_manifest_location(event)
    manifest_parent_location = "/".join(manifest_location.split("/")[:-1]) +"/"
    manifest_name = manifest_location.split("/")[-1]
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
        f"https://{HLS_STREAM_CLOUDFRONT_DISTRO}/*", expiry
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

    logger.info(f"Bucket: {bucket}")
    logger.info(f"Key Pair ID: {key_pair_id}")
    logger.info(f"Policy: {policy_64}")
    logger.info(f"Signature: {signature_64}")
    logger.info(f"Expiration Time: {expiration_epoc}")

    # Read the HLS Manifest file and rewrite the content
    manifest_content = recursively_sign_m3u8_files(manifest_parent_location, manifest_name, bucket, expiration_epoc, signature_64, key_pair_id, policy_64)

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
    response =  (
        f"https://{HLS_STREAM_CLOUDFRONT_DISTRO}/{object_location}?Expires={expiration_epoc}&Signature={signature_64}&Policy={policy_64}&Key-Pair-Id={key_pair_id}"
        if is_manifest_file
        else f"{object_location}?Expires={expiration_epoc}&Signature={signature_64}&Policy={policy_64}&Key-Pair-Id={key_pair_id}"
    )

    logger.info(f"Signed URL: {response}")
    return response


def get_hls_manifest_s3_key_prefix(event):
    logger.info(f"in get_hls_manifest_s3_key_prefix - event {event}")
    key_parts = event[
        "HlsLocation"
    ]  # Location to HLS Manifest m3u8 - s3ssl://BUCKET/x/x.m3u8

    # Get the key prefix from the s3ssl://BUCKET/x/x.m3u8
    key_prefix = key_parts.split("/")[:-1]
    key_prefix = "/".join(key_prefix)  # Remove Object name
    key_prefix = key_prefix.split("/")
    s3_key_prefix = "/".join(key_prefix[3:])  # Remove s3ssl, '', BUCKET_NAME
    return s3_key_prefix  # Without Object Name


def get_hls_manifest_location(event):
    logger.info(f"in get_hls_manifest_location - event {event}")
    key_parts = event[
        "HlsLocation"
    ]  # Location to HLS Manifest m3u8 - s3ssl://BUCKET/x/x.m3u8
    manifest_name = key_parts.split("/")[-1:][0]

    key_prefix = get_hls_manifest_s3_key_prefix(event)
    logger.info(f"Manifest file location -  {key_prefix}/{manifest_name}")
    return f"{key_prefix}/{manifest_name}"


########################## Replay Changes Starts ######################
@app.route(
    "/replay/program/{program}/event/{event}/replayid/{id}/status/update/{replaystatus}",
    cors=True,
    methods=["PUT"],
    authorizer=authorizer,
)
def update_replay_request_status(program, event, id, replaystatus):
    """
    Updates the status of a Replay

    Returns:

        None
    """
    try:
        eventname = urllib.parse.unquote(event)
        program = urllib.parse.unquote(program)
        replay_id = urllib.parse.unquote(id)
        replaystatus = urllib.parse.unquote(replaystatus)

        validate_path_parameters(
            {
                "Program": program,
                "Event": event,
                "ReplayId": id,
                "ReplayStatus": replaystatus,
            }
        )

        replay_request_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        replay_request_table.update_item(
            Key={"PK": f"{program}#{eventname}", "ReplayId": replay_id},
            UpdateExpression="SET #Status = :status",
            ExpressionAttributeNames={"#Status": "Status"},
            ExpressionAttributeValues={":status": replaystatus},
        )

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    return {"Status": "Replay request status updated"}

@app.route(
    "/replay/completed/events/track/{audioTrack}/program/{program}/event/{event}",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_all_replay_requests_for_completed_event(event, program, audioTrack):
    """
    Returns Queued Replay Requests for the Program/Event and Audio Track only if the Event is Complete

    Returns:

        Replay Request based on Event, Program and AudioTrack

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        eventname = urllib.parse.unquote(event)
        program = urllib.parse.unquote(program)
        audioTrack = urllib.parse.unquote(audioTrack)

        validate_path_parameters(
            {"Event": event, "Program": program, "AudioTrack": audioTrack}
        )

        # Check if Event is Complete
        event_obj = get_event(eventname, program)
        if event_obj["Status"] == "Complete":
            replay_request_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)
            response = replay_request_table.query(
                KeyConditionExpression=Key("PK").eq(f"{program}#{eventname}"),
                FilterExpression=Attr("Status").eq("Queued")
                & Attr("AudioTrack").eq(int(audioTrack)),
                ConsistentRead=True,
            )

            if "Items" not in response:
                raise NotFoundError(
                    f"No Replay Requests found for program '{program}' and {eventname}"
                )

            return replace_decimals(response["Items"])

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    return []

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

        logger.info(f"Getting the Event '{name}' in Program '{program}'")

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={"Name": name, "Program": program}, ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Event '{name}' in Program '{program}' not found")

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
    "/replay/track/{audioTrack}/program/{program}/event/{event}",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_all_replay_requests_for_event_optosegment_end(event, program, audioTrack):
    """
    Returns all Queued Replay Requests for the Program/Event and Audio Track

    Returns:

        Replay Request based on Event, Program and AudioTrack

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    eventname = urllib.parse.unquote(event)
    program = urllib.parse.unquote(program)
    audioTrack = urllib.parse.unquote(audioTrack)

    validate_path_parameters(
        {"Event": event, "Program": program, "AudioTrack": audioTrack}
    )

    replay_request_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

    response = replay_request_table.query(
        KeyConditionExpression=Key("PK").eq(f"{program}#{eventname}"),
        FilterExpression=Attr("Status").ne("Complete")
        & Attr("Status").ne("Error")
        & Attr("AudioTrack").eq(int(audioTrack)),
        ConsistentRead=True,
    )

    if "Items" not in response:
        raise NotFoundError(
            f"No Replay Requests found for program '{program}' and {eventname}"
        )

    return replace_decimals(response["Items"])

@app.route(
    "/replay/program/{program}/event/{event}/segmentend",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_all_replays_for_segment_end(event, program):
    """
    Get all Queued,InProgress Replay Requests for the Program/Event

    Returns:

        Replay Request based on Event and Program

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    try:
        eventname = urllib.parse.unquote(event)
        program = urllib.parse.unquote(program)

        validate_path_parameters({"Event": event, "Program": program})

        replay_request_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        response = replay_request_table.query(
            KeyConditionExpression=Key("PK").eq(f"{program}#{eventname}"),
            FilterExpression=Attr("Status").ne("Complete") & Attr("Status").ne("Error"),
            ConsistentRead=True,
        )

        if "Items" not in response:
            raise NotFoundError(
                f"No Replay Requests found for program '{program}' and {eventname}"
            )

        return replace_decimals(response["Items"])

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

@app.route(
    "/replay/program/{program}/event/{event}/features",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def getfeatures_by_program_event(program, event):
    """
    Get all the Features (as defined in plugin output attributes) based on Program and Event

    Returns:

        A list of Feature Names

    Raises:
        404 - NotFoundError
        500 - ChaliceViewError
    """
    features = []
    try:
        program = urllib.parse.unquote(program)
        event = urllib.parse.unquote(event)

        validate_path_parameters({"Program": program, "Event": event})

        event_table = ddb_resource.Table(EVENT_TABLE_NAME)

        response = event_table.get_item(
            Key={"Name": event, "Program": program}, ConsistentRead=True
        )
        if "Item" not in response:
            raise NotFoundError(f"Event '{event}' in Program '{program}' not found")

        profile = response["Item"]["Profile"]

        profile_table = ddb_resource.Table(PROFILE_TABLE_NAME)
        profile_response = profile_table.get_item(
            Key={"Name": profile}, ConsistentRead=True
        )

        if "Item" not in profile_response:
            raise NotFoundError(f"Profile '{profile}' not found")

        plugin_table = ddb_resource.Table(PLUGIN_TABLE_NAME)

        if "Featurers" in profile_response["Item"]:
            for feature in profile_response["Item"]["Featurers"]:
                response = plugin_table.get_item(
                    Key={"Name": feature["Name"], "Version": "v0"}, ConsistentRead=True
                )

                # if "Item" not in response:
                #    raise NotFoundError(f"Plugin '{feature['Name']}' not found")
                if "Item" in response:
                    if "OutputAttributes" in response["Item"]:
                        for key in response["Item"]["OutputAttributes"].keys():
                            features.append(f"{feature['Name']} | {key}")

                dependent_plugin_features = get_features_from_dependent_plugins(feature)
                features.extend(dependent_plugin_features)

        if "Classifier" in profile_response["Item"]:
            # for feature in profile_response['Item']['Classifier']:
            response = plugin_table.get_item(
                Key={
                    "Name": profile_response["Item"]["Classifier"]["Name"],
                    "Version": "v0",
                },
                ConsistentRead=True,
            )
            if "Item" in response:
                if "OutputAttributes" in response["Item"]:
                    for key in response["Item"]["OutputAttributes"].keys():
                        features.append(
                            f"{profile_response['Item']['Classifier']['Name']} | {key}"
                        )

                dependent_plugin_features = get_features_from_dependent_plugins(
                    profile_response["Item"]["Classifier"]
                )
                features.extend(dependent_plugin_features)

        if "Labeler" in profile_response["Item"]:
            # for feature in profile_response['Item']['Classifier']:
            response = plugin_table.get_item(
                Key={
                    "Name": profile_response["Item"]["Labeler"]["Name"],
                    "Version": "v0",
                },
                ConsistentRead=True,
            )
            if "Item" in response:
                if "OutputAttributes" in response["Item"]:
                    for key in response["Item"]["OutputAttributes"].keys():
                        features.append(
                            f"{profile_response['Item']['Labeler']['Name']} | {key}"
                        )

                dependent_plugin_features = get_features_from_dependent_plugins(
                    profile_response["Item"]["Labeler"]
                )
                features.extend(dependent_plugin_features)

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except Exception as e:
        logger.info(f"Unable to get replays for Program and Event: {str(e)}")
        raise ChaliceViewError(f"Unable to get replays for Program and Event: {str(e)}")

    return replace_decimals(features)

def get_features_from_dependent_plugins(pluginType):
    plugin_table = ddb_resource.Table(PLUGIN_TABLE_NAME)
    features = []

    if "DependentPlugins" in pluginType:
        for dependent_plugin in pluginType["DependentPlugins"]:
            response = plugin_table.get_item(
                Key={
                    "Name": dependent_plugin["Name"],
                    "Version": dependent_plugin["Version"],
                },
                ConsistentRead=True,
            )
            if "Item" in response:
                if "OutputAttributes" in response["Item"]:
                    for key in response["Item"]["OutputAttributes"].keys():
                        features.append(f"{dependent_plugin['Name']} | {key}")

    return features

@app.route(
    "/replay/program/{program}/event/{event}/hls/replaymanifest/replayid/{replayid}",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_hls_manifest_by_replayid(program, event, replayid):
    """
    Returns the HLS format of an MRE Replay as a octet-stream

    Returns:

       HLS format of an MRE Replay as a octet-stream

    Raises:
        404 - NotFoundError
    """
    try:
        program = urllib.parse.unquote(program)
        event = urllib.parse.unquote(event)
        replayid = urllib.parse.unquote(replayid)

        validate_path_parameters(
            {"Program": program, "Event": event, "ReplayId": replayid}
        )

        replay_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        response = replay_table.get_item(
            Key={"PK": f"{program}#{event}", "ReplayId": replayid}, ConsistentRead=True
        )
        if "Item" not in response:
            raise NotFoundError(f"Event '{event}' in Program '{program}' not found")

        if "HlsLocation" not in response["Item"]:
            return {"BlobContent": "No Content found"}

        master_manifest = response["Item"]["HlsLocation"]

        # Every Replay request has this Attribute with a default value of '-'
        # If this has been updated with a s3 location, create the master manifest content to be sent back
        if master_manifest != "-":

            parts = master_manifest.replace(":", "").split("/")
            logger.info(parts)
            bucket = parts[2]
            key = "/".join(parts[-3:])

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

        else:
            return {"BlobContent": "No Content found"}

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

@app.route(
    "/replay/mp4location/update", cors=True, methods=["POST"], authorizer=authorizer
)
def update_mp4_for_replay_request():
    """
    Updates MP4 file location with the Replay Request

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        event = json.loads(app.current_request.raw_body.decode())

        validate(event=event, schema=API_SCHEMA["update_mp4_file"])

        event_name = event["Name"]
        program_name = event["Program"]
        replay_request_id = event["ReplayRequestId"]
        mp4_location = event["Mp4Location"]
        thumbnail_location = event["Thumbnail"]

        event_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        event_table.update_item(
            Key={"PK": f"{program_name}#{event_name}", "ReplayId": replay_request_id},
            UpdateExpression="SET #mp4Location = :location, #Mp4ThumbnailLoc = :thumbnail",
            ExpressionAttributeNames={
                "#mp4Location": "Mp4Location",
                "#Mp4ThumbnailLoc": "Mp4ThumbnailLocation",
            },
            ExpressionAttributeValues={
                ":location": mp4_location,
                ":thumbnail": thumbnail_location,
            },
        )

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except Exception as e:
        logger.info(
            f"Unable to update MP4 location for replay request {replay_request_id} and event '{event_name}' in program '{program_name}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to update MP4 location  for replay request {replay_request_id} and event '{event_name}' in program '{program_name}': {str(e)}"
        )

    else:
        logger.info(
            f"Successfully stored the MP4 location for replay request {replay_request_id} and event '{event_name}' in program '{program_name}'"
        )

        return {}

@app.route(
    "/replay/update/hls/manifest", cors=True, methods=["POST"], authorizer=authorizer
)
def update_hls_for_replay_request():
    """
    Updates HLS S3 manifest file location with the Replay Request

    Returns:

        None

    Raises:
        500 - ChaliceViewError
    """
    try:
        event = json.loads(app.current_request.raw_body.decode())

        validate(event=event, schema=API_SCHEMA["update_hls_manifest"])

        event_name = event["Event"]
        program_name = event["Program"]
        replay_request_id = event["ReplayRequestId"]
        hls_location = event["HlsLocation"]
        thumbnail_location = event["Thumbnail"]

        event_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        event_table.update_item(
            Key={"PK": f"{program_name}#{event_name}", "ReplayId": replay_request_id},
            UpdateExpression="SET #HlsLocation = :location, #HlsThumbnailLoc = :thumbnail",
            ExpressionAttributeNames={
                "#HlsLocation": "HlsLocation",
                "#HlsThumbnailLoc": "HlsThumbnailLoc",
            },
            ExpressionAttributeValues={
                ":location": hls_location,
                ":thumbnail": thumbnail_location,
            },
        )
    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except Exception as e:
        logger.info(
            f"Unable to update HLS Master Manifest for replay request {replay_request_id} and event '{event_name}' in program '{program_name}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to update HLS Master Manifest for replay request {replay_request_id} and event '{event_name}' in program '{program_name}': {str(e)}"
        )

    else:
        logger.info(
            f"Successfully stored the HLS Master Manifest for replay request {replay_request_id} and event '{event_name}' in program '{program_name}'"
        )

        return {}

def get_cloudfront_security_credentials():
    """
    Generates Cloudfront Signed Cookie creds which are valid for 1 day.
    """

    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager")

    private_key_secret = client.get_secret_value(
        SecretId=CLOUDFRONT_COOKIE_PRIVATE_KEY_FROM_SECRET_MGR
    )
    privateKey = private_key_secret["SecretString"]
    privateKey = rsa.PrivateKey.load_pkcs1(privateKey)

    key_pair_id_secret = client.get_secret_value(
        SecretId=CLOUDFRONT_COOKIE_KEY_PAIR_ID_FROM_SECRET_MGR
    )
    key_pair_id = key_pair_id_secret["SecretString"]

    expiry = datetime.now() + timedelta(days=1)

    rsa_signer = functools.partial(rsa.sign, priv_key=privateKey, hash_method="SHA-1")
    cf_signer = CloudFrontSigner(key_pair_id, rsa_signer)
    policy = cf_signer.build_policy(
        f"https://{HLS_STREAM_CLOUDFRONT_DISTRO}/*", expiry
    ).encode("utf8")
    policy_64 = cf_signer._url_b64encode(policy).decode("utf8")
    signature = rsa_signer(policy)
    signature_64 = cf_signer._url_b64encode(signature).decode("utf8")

    return {
        "CloudFront-Policy": policy_64,
        "CloudFront-Signature": signature_64,
        "CloudFront-Key-Pair-Id": key_pair_id,
    }

@app.route(
    "/replay/mre/streaming/auth", cors=True, methods=["GET"], authorizer=authorizer
)
def get_mre_stream_auth():
    """
    Returns Cloudfront Signed Cookie creds which are valid for 1 day.
    Clients can use these creds to cache locally and make subsequent calls to
    Cloudfront URLs (for HLS Streaming and rendering thumbnails)

    Returns:

        .. code-block:: python

            {
                "CloudFront-Policy": "",
                "CloudFront-Signature": "",
                "CloudFront-Key-Pair-Id": ""
            }
    """
    return get_cloudfront_security_credentials()

@app.route(
    "/replay/program/{program}/gameid/{event}/hls/stream/locations",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_replay_hls_locations(program, event):
    """
    Returns Cloudfront links for Replay HLS streams, thumbnails along with Cloudfront Signed Cookie Creds.
    Clients first Authorize with this API using JWT tokens and use the Cloudfront Signed Cookie Creds
    to make calls to the Cloudfront URLs to stream HLS

    Returns:

        .. code-block:: python

            {
                "Replays": ",
                "AuthInfo": {
                    "Policy": "",
                    "Signature": "",
                    "KeyPaidId": ""
                }
            }
    """
    try:
        program = urllib.parse.unquote(program)
        event = urllib.parse.unquote(event)

        validate_path_parameters({"Program": program, "Event": event})

        cfn_credentials = get_cloudfront_security_credentials()

        replay_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        replays = replay_table.query(
            KeyConditionExpression=Key("PK").eq(f"{program}#{event}")
        )
        logger.info("--------replays--------")
        logger.info(replays)

        all_replays = []

        if "Items" in replays:
            for replay in replays["Items"]:
                temp_replay = {}
                if "DurationbasedSummarization" in replay:
                    temp_replay["DurationMinutes"] = replay[
                        "DurationbasedSummarization"
                    ]["Duration"]

                if "HlsLocation" in replay:
                    s3_hls_location = replay["HlsLocation"]

                    if s3_hls_location != "-":
                        s3_hls_location = s3_hls_location.replace(":", "").split("/")

                        # ['s3', '', 'aws-mre-clip-gen-output', 'HLS', 'ak555-testprogram', '4K', '']
                        keyprefix = f"{s3_hls_location[3]}/{s3_hls_location[4]}/{s3_hls_location[5]}"
                        temp_replay["HLSLocation"] = (
                            f"https://{HLS_STREAM_CLOUDFRONT_DISTRO}/{keyprefix}"
                        )
                    else:
                        temp_replay["HLSLocation"] = s3_hls_location
                else:
                    temp_replay["HLSLocation"] = ""

                if "HlsThumbnailLoc" in replay:
                    hls_thumbnail_location = replay["HlsThumbnailLoc"]
                    if hls_thumbnail_location != "-":
                        tmp_loc = hls_thumbnail_location.replace(":", "").split("/")

                        # ['s3', '', 'bucket_name', 'HLS', 'UUID', 'thumbnails', '4K', '']
                        key_prefix = f"{tmp_loc[3]}/{tmp_loc[4]}/{tmp_loc[5]}/{tmp_loc[6]}/{tmp_loc[7]}"
                        temp_replay["ThumbnailLocation"] = (
                            f"https://{HLS_STREAM_CLOUDFRONT_DISTRO}/{key_prefix}"
                        )
                    else:
                        temp_replay["ThumbnailLocation"] = hls_thumbnail_location
                else:
                    temp_replay["ThumbnailLocation"] = ""

                # Only include replays that have HLS clips generated
                if "HlsLocation" in replay:
                    s3_hls_location = replay["HlsLocation"]
                    if s3_hls_location != "-":
                        all_replays.append(temp_replay)

        return {
            "Replays": all_replays,
            "AuthInfo": {
                "Policy": cfn_credentials["CloudFront-Policy"],
                "Signature": cfn_credentials["CloudFront-Signature"],
                "KeyPaidId": cfn_credentials["CloudFront-Key-Pair-Id"],
            },
        }

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

@app.route(
    "/replay/event/{name}/program/{program}/id/{replayid}",
    cors=True,
    methods=["DELETE"],
    authorizer=authorizer,
)
def delete_replay(name, program, replayid):
    """
    Deletes an event by name, program and ReplayId.

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
        replayid = urllib.parse.unquote(replayid)

        validate_path_parameters(
            {"Name": name, "Program": program, "ReplayId": replayid}
        )

        replay_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        response = replay_table.get_item(
            Key={"PK": program + "#" + name, "ReplayId": replayid}, ConsistentRead=True
        )

        if "Item" not in response:
            raise NotFoundError(f"Event '{name}' in Program '{program}' not found")
        elif response["Item"]["Status"] == "In Progress":
            raise BadRequestError("Cannot delete Replay as it is currently in progress")

        logger.info("Deleting the Replay")

        response = replay_table.delete_item(
            Key={"PK": program + "#" + name, "ReplayId": replayid}
        )

        # Are there any Replay Requests in Completed Status for this Event ?
        # If no, Update the hasReplays attribute to False

        response = replay_table.query(
            KeyConditionExpression=Key("PK").eq(f"{program}#{name}"),
            ConsistentRead=True,
        )
        rep_req_exists = False
        if "Items" in response:
            for rep_req in response["Items"]:
                if rep_req["Status"] == "Complete":
                    rep_req_exists = True
                    break

        if not rep_req_exists:
            event_table = ddb_resource.Table(EVENT_TABLE_NAME)
            event_table.update_item(
                Key={"Name": name, "Program": program},
                UpdateExpression="SET #hasreplays = :hasreplays",
                ExpressionAttributeNames={"#hasreplays": "hasReplays"},
                ExpressionAttributeValues={":hasreplays": False},
            )

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
        logger.info(f"Unable to delete the Replay: {str(e)}")
        raise ChaliceViewError(f"Unable to delete the Replay: {str(e)}")

    else:
        logger.info("Deletion of Replay successful")
        return {}

@app.route(
    "/replay/event/program/export_data",
    cors=True,
    methods=["PUT"],
    authorizer=authorizer,
)
def store_replay_export_data():
    """
    Store the Export data generated for the Replay

    Returns:

        None

    Raises:
        500 - ChaliceViewError

    """
    try:
        payload = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(event=payload, schema=API_SCHEMA["export_data"])

        event_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        event_name = payload["Name"]
        program = payload["Program"]

        validate_path_parameters({"Event": event_name, "Program": program})

        if payload["IsBaseEvent"] == "Y":
            updateExpression = (
                "SET #ReplayDataExportLocation = :ReplayDataExportLocation"
            )
            expressionAttributeNames = {
                "#ReplayDataExportLocation": "ReplayDataExportLocation"
            }
            expressionAttributeValues = {
                ":ReplayDataExportLocation": payload["ExportDataLocation"]
            }
        else:
            updateExpression = (
                "SET #FinalReplayDataExportLocation = :FinalReplayDataExportLocation"
            )
            expressionAttributeNames = {
                "#FinalReplayDataExportLocation": "FinalReplayDataExportLocation"
            }
            expressionAttributeValues = {
                ":FinalReplayDataExportLocation": payload["ExportDataLocation"]
            }

        event_table.update_item(
            Key={"PK": f"{program}#{event_name}", "ReplayId": payload["ReplayId"]},
            UpdateExpression=updateExpression,
            ExpressionAttributeNames=expressionAttributeNames,
            ExpressionAttributeValues=expressionAttributeValues,
        )
    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

    except Exception as e:
        logger.info(
            f"Unable to store the Replay data export of event '{event_name}' in program '{program}': {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to store the Replay data export of event '{event_name}' in program '{program}': {str(e)}"
        )

    else:
        logger.info(
            f"Successfully stored the Replay data export of event '{event_name}' in program '{program}'"
        )

        return {}

@app.route(
    "/replay/update/ignore/segment/cache",
    cors=True,
    methods=["PUT"],
    authorizer=authorizer,
)
def update_segments_to_be_ignored():
    """
    Updates name of segment cache files which do not have matching Features configured for a Replay

    Returns:

        None

    """
    try:
        payload = json.loads(app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(event=payload, schema=API_SCHEMA["segment_cache"])

        event = payload["Name"]
        program = payload["Program"]
        segment_cache_name = payload["SegmentCacheName"]
        replay_id = payload["ReplayId"]

        replay_request_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        update_expression = []
        expression_attribute_names = {}
        expression_attribute_values = {}

        update_expression.append(
            "#IgnoredSegments = list_append(if_not_exists(#IgnoredSegments, :initialIgnoredSegments), :IgnoredSegments)"
        )
        expression_attribute_names["#IgnoredSegments"] = "IgnoredSegments"
        expression_attribute_values[":IgnoredSegments"] = [segment_cache_name]
        expression_attribute_values[":initialIgnoredSegments"] = []

        replay_request_table.update_item(
            Key={"PK": f"{program}#{event}", "ReplayId": replay_id},
            UpdateExpression="SET " + ", ".join(update_expression),
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
        )
    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

@app.route(
    "/replay/export/data/{id}/event/{event}/program/{program}",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_replay_export_data(program, event, id):
    """
    Returns the Replay Export Data as octet-stream

    Returns:

        Replay Export Data as octet-stream

    Raises:
        400 - BadRequestError
        404 - NotFoundError
    """
    try:
        program = urllib.parse.unquote(program)
        event = urllib.parse.unquote(event)
        replay_id = urllib.parse.unquote(id)

        validate_path_parameters(
            {"Program": program, "Event": event, "ReplayId": replay_id}
        )

        replay_table = ddb_resource.Table(REPLAY_REQUEST_TABLE_NAME)

        response = replay_table.get_item(
            Key={"PK": f"{program}#{event}", "ReplayId": replay_id}, ConsistentRead=True
        )
        if "Item" not in response:
            raise NotFoundError(f"Event '{event}' in Program '{program}' not found")

        if "ReplayDataExportLocation" not in response["Item"]:
            return {"BlobContent": "NA"}

        export_location = response["Item"]["ReplayDataExportLocation"]

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
    "/replay/transition/{transition_name}",
    cors=True,
    methods=["GET"],
    authorizer=authorizer,
)
def get_transitions_config(transition_name):
    """
    Get a Clip Transition Configuration

    Returns:
        .. code-block:: python

            {
                "ImageLocations": [
                {
                    "1080p": "",
                    "2k": "",
                    "720p": "",
                    "4k": ""
                }
                ],
                "PreviewVideoLocation": "",
                "IsDefault": false,
                "Config": {
                "FadeOutMs": ,
                "FadeInMs": ,
                },
                "Description": "",
                "VideoLocations": [
                {
                    "1080p": "",
                    "2k": "",
                    "720p": "",
                    "4k": ""
                }
                ],
                "MediaType": "Video/Image",
                "Name": ""
            }

    Raises:
        500 - ChaliceViewError
    """
    try:
        transition_name = urllib.parse.unquote(transition_name)

        validate_path_parameters({"TransitionName": transition_name})

        transitions_config_table = ddb_resource.Table(TRANSITIONS_CONFIG_TABLE_NAME)

        response = transitions_config_table.get_item(
            Key={"Name": transition_name}, ConsistentRead=True
        )
        if "Item" not in response:
            raise NotFoundError(f"Transition '{transition_name}' not found")
        else:
            config = response["Item"]
            try:
                if "PreviewVideoLocation" in config:
                    full_s3_path = config["PreviewVideoLocation"].split("/")
                    key = "/".join(full_s3_path[3:])
                    config["PreviewVideoUrls"] = get_media_presigned_url(
                        key, TRANSITION_CLIP_S3_BUCKET, False
                    )
            except Exception as e:
                logger.info(
                    f"Error when creating PreSigned Url for Transition - {transition_name}. Error details - {e}"
                )
                raise ChaliceViewError(
                    f"Error when creating PreSigned Url for Transition - {transition_name}"
                )

            return replace_decimals(config)

    except SchemaValidationError as e:
        logger.info(f"ValidationError: {e.validation_message}")
        raise BadRequestError(f"ValidationError: {str(e.validation_message)}")

@app.route("/replay/transitions/all", cors=True, methods=["GET"], authorizer=authorizer)
def list_all_transitions_config():
    """
    List all Clip Transitions Configurations

    Returns:
        .. code-block:: python

            {
            "Items":
                [
                    {
                        "ImageLocations": [
                        {
                            "1080p": "",
                            "2k": "",
                            "720p": "",
                            "4k": ""
                        }
                        ],
                        "PreviewVideoLocation": "",
                        "IsDefault": false,
                        "Config": {
                        "FadeOutMs": ,
                        "FadeInMs": ,
                        },
                        "Description": "",
                        "VideoLocations": [
                        {
                            "1080p": "",
                            "2k": "",
                            "720p": "",
                            "4k": ""
                        }
                        ],
                        "MediaType": "Video/Image",
                        "Name": ""
                    },,
                    ...
                ]
            }

    Raises:
        500 - ChaliceViewError
    """

    try:
        logger.info("Listing all the programs")

        transitions_config_table = ddb_resource.Table(TRANSITIONS_CONFIG_TABLE_NAME)

        response = transitions_config_table.scan(ConsistentRead=True)

        trans_config = response["Items"]

        while "LastEvaluatedKey" in response:
            response = transitions_config_table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"], ConsistentRead=True
            )

            trans_config.extend(response["Items"])

    except Exception as e:
        logger.info(
            f"Unable to list all the Transitions Config stored in the system: {str(e)}"
        )
        raise ChaliceViewError(
            f"Unable to list all the Transitions Config stored in the system: {str(e)}"
        )

    else:
        return trans_config

def get_media_presigned_url(key, bucket, is_hls=False):
    """
    Generate pre-signed URL for downloading the media (video) file from S3.

    Returns:

        S3 pre-signed URL for downloading the media (video) file.

    Raises:
        500 - ChaliceViewError
    """
    if key == "-":
        return
    logger.info(f"getting get_media_presigned_url for {key} in {bucket}")
    key = urllib.parse.unquote(key)
    logger.info(f"updated key {key}")

    s3 = boto3.client(
        "s3",
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )

    try:
        response = ""
        if is_hls:
            response = s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": bucket, "Key": key, "ResponseContentType": "application/x-mpegURL"},
                ExpiresIn=86400,  # 24Hrs
            )
        else:
            response = s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=86400,  # 24Hrs
            )

    except ClientError as e:
        logger.info(f"Got S3 ClientError: {str(e)}")
        error = e.response["Error"]["Message"]
        logger.info(f"Unable to generate S3 pre-signed URL: {str(error)}")
        raise ChaliceViewError(f"Unable to generate S3 pre-signed URL: {str(error)}")

    except Exception as e:
        logger.info(f"Unable to generate S3 pre-signed URL: {str(e)}")
        raise ChaliceViewError(f"Unable to generate S3 pre-signed URL: {str(e)}")

    else:
        logger.info(f"end get_media_presigned_url: {response}")
        return response

def validate_path_parameters(params: dict):
    validate(event=params, schema=API_SCHEMA["replay_path_validation"])
