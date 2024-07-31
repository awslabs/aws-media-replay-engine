from boto3.dynamodb.types import TypeDeserializer
import boto3
from chalice import ChaliceViewError
from botocore.client import ClientError

deserializer = TypeDeserializer()

s3_client = boto3.client("s3")
ddb_resource = boto3.resource("dynamodb")

def udf(item):
   return {k: deserializer.deserialize(value=v) for k, v in item.items()}

def create_presigned_url(s3_url, expiration=60000):
    
    thumbnail_location = s3_url.replace('s3://', '')
    chunks = thumbnail_location.split('/')
    s3_bucket = chunks.pop(0)
    s3_key = '/'.join(chunks)
    
    # The response contains the presigned URL
    return  _create_presigned_url(s3_bucket, s3_key, expiration)

def _create_presigned_url(s3_bucket, s3_key, expiration=3600):
    """Generate a presigned URL to share an S3 object

    :param bucket_name: string
    :param object_name: string
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """

    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': s3_bucket,
                                                            'Key': s3_key},
                                                    ExpiresIn=expiration)
    except Exception as e:
        err_msg = f"Unable to generate presigned URL for: Bucket: {s3_bucket}, key:{s3_key}. Refer to README to ensure proper permissions."
        print(err_msg)
        raise ChaliceViewError(err_msg)

    # The response contains the presigned URL
    return response