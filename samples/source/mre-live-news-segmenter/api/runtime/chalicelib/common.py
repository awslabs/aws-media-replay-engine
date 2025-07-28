# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from boto3.dynamodb.types import TypeDeserializer
import boto3
from chalice import ChaliceViewError

deserializer = TypeDeserializer()

s3_client = boto3.client("s3")


def udf(item):
    result = {}
    for k, v in item.items():
        if not v:
            result[k] = v
        else:
            try:
                # Check if value is already deserialized (not in DynamoDB format)
                if isinstance(v, dict) and len(v) == 1 and list(v.keys())[0] in ['S', 'N', 'B', 'SS', 'NS', 'BS', 'M', 'L', 'NULL', 'BOOL']:
                    result[k] = deserializer.deserialize(value=v)
                else:
                    result[k] = v
            except (TypeError, ValueError, AttributeError):
                result[k] = v
    return result


def create_presigned_url(s3_url, expiration=3600):
    thumbnail_location = s3_url.replace("s3://", "")
    chunks = thumbnail_location.split("/")
    s3_bucket = chunks.pop(0)
    s3_key = "/".join(chunks)

    # The response contains the presigned URL
    return _create_presigned_url(s3_bucket, s3_key, expiration)


def _create_presigned_url(s3_bucket, s3_key, expiration=3600):
    """Generate a presigned URL to share an S3 object

    :param bucket_name: string
    :param object_name: string
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """

    try:
        response = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": s3_bucket, "Key": s3_key},
            ExpiresIn=expiration,
        )
    except Exception as e:
        err_msg = f"Unable to generate presigned URL for bucket '{s3_bucket}' and key '{s3_key}' due to: {str(e)}.\n\nRefer to README to ensure proper permissions."
        print(err_msg)
        raise ChaliceViewError(err_msg)

    # The response contains the presigned URL
    return response
