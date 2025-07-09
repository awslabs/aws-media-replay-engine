# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import math
import os
import threading
import urllib.parse
import uuid
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.config import Config
from chalice import BadRequestError, Blueprint, IAMAuthorizer
from chalicelib import load_api_schema
from jsonschema import ValidationError, validate
from aws_lambda_powertools import Logger

MAX_BATCH_SIZE = 8
CHUNK_TABLE_NAME = os.environ['CHUNK_TABLE_NAME']

authorizer = IAMAuthorizer()

ddb_resource = boto3.resource("dynamodb")
chunk_table = ddb_resource.Table(CHUNK_TABLE_NAME)

chunk_api = Blueprint(__name__)
s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')
API_SCHEMA = load_api_schema()

logger = Logger(service="aws-mre-dataplane-api")

@chunk_api.route('/chunk/thumbnails', cors=True, methods=['POST'], authorizer=authorizer)
def get_chunk_thumbnails():
    import ffmpeg

    """
    Returns a list of thumbnails for Chunks based on the Start and End time passed.
    
    Body:

    .. code-block:: python
        {
            "Program": string,
            "Event": string,
            "Profile": string,
            "Timings": list
        }
        

    Returns:

        List containing the thumbnail for each Chunks Start and End time combination.
    
    Raises:
        400 - BadRequestError
        500 - ChaliceViewError
    """
    thumbnails = []
    threads = []
    try:
        request = json.loads(chunk_api.current_app.current_request.raw_body.decode(), parse_float=Decimal)

        validate(instance=request, schema=API_SCHEMA["get_thumbnails"])

        program = request["Program"]
        event = request["Event"]
        profile = request["Profile"]
        timings = request["Timings"]

        # Create the Temp Dir for Frame Grabs
        input_chunk_video_dir = "/tmp/video"
        output_dir = "/tmp/imgs"

        

        if not os.path.exists(input_chunk_video_dir):
            os.makedirs(input_chunk_video_dir)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        def start_threads():
            for thread in threads:
                thread.start()

        def join_threads():
            for thread in threads:
                thread.join()
        
        def get_media_presigned_url(key, bucket):
            """
            Generate pre-signed URL for downloading the media (video) file from S3.

            Returns:

                S3 pre-signed URL for downloading the media (video) file.

            Raises:
                500 - ChaliceViewError
            """
            key = urllib.parse.unquote(key)

            s3 = boto3.client('s3', config=Config(
            signature_version='s3v4', s3={'addressing_style': 'virtual'}))
        
            response = s3.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': bucket,
                    'Key': key
                },
                ExpiresIn=86400  # 24Hrs
            )
            return response

        def get_chunks_from_times(program, event, profile, time_range):

            response = chunk_table.query(
                    KeyConditionExpression=Key("PK").eq(f"{program}#{event}") & Key("Start").between(time_range['Start'], time_range['End']),
                    ProjectionExpression="#Filename, #Duration, #S3Bucket, #S3Key",
                    FilterExpression=Attr("Profile").eq(profile),
                    ExpressionAttributeNames={
                        "#Filename": "Filename",
                        "#Duration": "Duration",
                        "#S3Bucket": "S3Bucket",
                        "#S3Key": "S3Key"
                    },
                    ScanIndexForward=True,
                    ConsistentRead=True
                )
            if response["Items"]:
                chunk_key = response["Items"][0]["S3Key"]
                chunk_bucket = response["Items"][0]["S3Bucket"]
                #first_chunk_video_location = f"s3://{response["Items"][0]["S3Bucket"]}/{response["Items"][0]["S3Key"]}" # S3 location to the Chunks TS file.
                thumbnail_s3_key_prefix = generate_thumbnail_image(chunk_bucket, chunk_key)
                thumbnail_url = get_media_presigned_url(thumbnail_s3_key_prefix, response["Items"][0]["S3Bucket"])

                thumbnails.append({
                    "Start": time_range['Start'],
                    "End": time_range['End'],
                    "ThumbnailLocation": thumbnail_url
                })

        def generate_thumbnail_image(chunk_bucket, chunk_key):
    
            logger.info(f"chunk_bucket={chunk_bucket}")
            logger.info(f"chunk_key={chunk_key}")
            temp_image_file_name = f"{str(uuid.uuid4())}"
            logger.info(f"temp_image_file_name={temp_image_file_name}")
            try:
                s3_resource.Bucket(chunk_bucket).download_file(chunk_key, f"{input_chunk_video_dir}/{temp_image_file_name}.ts")
            except Exception as e:
                logger.info("S3 Download File error")
                raise
            
            for f in os.listdir(input_chunk_video_dir):
                logger.info(f"TS Downloaded file: {f}")

            # Get Video Duration
            probe = ffmpeg.probe(f"{input_chunk_video_dir}/{temp_image_file_name}.ts", select_streams="v:0")
            duration = float(probe['format']['duration'])

            logger.info(f"duration={duration}")
            
            # Calculate the timestamp for the center frame
            center_timestamp = duration / 2
            # Extract the center frame as a JPEG image
            (
                ffmpeg
                .input(f"{input_chunk_video_dir}/{temp_image_file_name}.ts", ss=math.floor(center_timestamp))
                .filter('scale', 1920, -1)
                .output(f"{output_dir}/{temp_image_file_name}.jpeg", vframes=1)
                .run()
            )

            for f in os.listdir(output_dir):
                logger.info(f"Image file created: {f}")

            # Upload Thumbnail image to S3
            thumbnail_key_prefix = f"thumbnail/{str(uuid.uuid4())}/{str(uuid.uuid4())}.jpeg"
            s3_client.upload_file(f"{output_dir}/{temp_image_file_name}.jpeg", chunk_bucket, thumbnail_key_prefix)
            
            return thumbnail_key_prefix

        for timing in timings:
            threads.append(threading.Thread(target=get_chunks_from_times, args=(program, event, profile, timing,)))
        start_threads()
        join_threads()

    
        return thumbnails
    
    except ValidationError as e:
        logger.info(f"Got jsonschema ValidationError: {str(e)}")
        raise BadRequestError(e.message)