# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0


import urllib.parse
import boto3
from chalice import Chalice
from chalice import IAMAuthorizer
from chalice import ChaliceViewError
from botocore.config import Config
from botocore.client import ClientError

from chalicelib.plugin import plugin_api
from chalicelib.metadata import metadata_api
from chalicelib.replay import replay_api
from chalicelib.segment import segment_api
from chalicelib.workflow import workflow_api
from chalicelib.chunk import chunk_api
from aws_lambda_powertools import Logger

logger = Logger(service="aws-mre-dataplane-api")
app = Chalice(app_name='aws-mre-dataplane-api')

# Create middleware to inject request context
@app.middleware('all')
def inject_request_context(event, get_response):
    # event is a Chalice Request object
    request_id = event.context.get('requestId', 'N/A')
    
    # Add request ID to persistent logger context
    logger.append_keys(request_id=request_id)
    
    response = get_response(event)
    return response


app.register_blueprint(plugin_api)
app.register_blueprint(metadata_api)
app.register_blueprint(replay_api)
app.register_blueprint(segment_api)
app.register_blueprint(workflow_api)
app.register_blueprint(chunk_api)

API_VERSION = '1.0.0'
authorizer = IAMAuthorizer()

s3_client = boto3.client("s3")

@app.route('/version', cors=True, methods=['GET'], authorizer=authorizer)
def version():
    """
    Get the data plane api version number.

    Returns:

        Dictionary containing Data plane api version number.

        .. code-block:: python
        
            {
                "api_version": "x.x.x"
            }
            
    """
    return {
        "api_version": API_VERSION
    }


@app.route('/manifest/{bucket}/{key}/{version}', cors=True, methods=['GET'], authorizer=authorizer)
def get_manifest_content(bucket, key, version):
    """
    Get the content of the HLS Manifest (.m3u8) file from S3.

    Returns:

        Content of the HLS Manifest (.m3u8) file.
    
    Raises:
        500 - ChaliceViewError
    """
    bucket = urllib.parse.unquote(bucket)
    key = urllib.parse.unquote(key)
    version = urllib.parse.unquote(version)

    logger.info(f"Getting the HLS Manifest (.m3u8) file content from bucket={bucket} with key={key} and versionId={version}")

    try:
        response = s3_client.get_object(
            Bucket=bucket,
            Key=key,
            VersionId=version
        )

    except ClientError as e:
        error = e.response['Error']['Message']
        logger.info(f"Unable to get the HLS Manifest file content from S3: {str(error)}")
        raise ChaliceViewError(f"Unable to get the HLS Manifest file content from S3: {str(error)}")

    except Exception as e:
        logger.info(f"Unable to get the HLS Manifest file content from S3: {str(e)}")
        raise ChaliceViewError(f"Unable to get the HLS Manifest file content from S3: {str(e)}")

    else:
        return response['Body'].read().decode('utf-8')


@app.route('/media/{bucket}/{key}', cors=True, methods=['GET'], authorizer=authorizer)
def get_media_presigned_url(bucket, key):
    """
    Generate pre-signed URL for downloading the media (video) file from S3.

    Returns:

        S3 pre-signed URL for downloading the media (video) file.
    
    Raises:
        500 - ChaliceViewError
    """
    bucket = urllib.parse.unquote(bucket)
    key = urllib.parse.unquote(key)

    logger.info(
        f"Generating S3 pre-signed URL for downloading the media file content from bucket '{bucket}' with key '{key}'")

    s3 = boto3.client('s3', config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'}))

    try:
        response = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': bucket,
                'Key': key
            },
            ExpiresIn=300
        )

    except ClientError as e:
        logger.info(f"Got S3 ClientError: {str(e)}")
        error = e.response['Error']['Message']
        logger.info(f"Unable to generate S3 pre-signed URL for bucket '{bucket}' with key '{key}': {str(error)}")
        raise ChaliceViewError(
            f"Unable to generate S3 pre-signed URL for bucket '{bucket}' with key '{key}': {str(error)}")

    except Exception as e:
        logger.info(f"Unable to generate S3 pre-signed URL for bucket '{bucket}' with key '{key}': {str(e)}")
        raise ChaliceViewError(f"Unable to generate S3 pre-signed URL for bucket '{bucket}' with key '{key}': {str(e)}")

    else:
        return response


