#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import json
import traceback
import time

import boto3

from boto3.dynamodb.conditions import Key
from botocore.client import ClientError

PLUGIN_RESULT_TABLE_NAME = os.environ["PLUGIN_RESULT_TABLE_NAME"]
PLUGIN_RESULT_PROGRAM_EVENT_INDEX = os.environ["PLUGIN_RESULT_PROGRAM_EVENT_INDEX"]
FRAME_TABLE_NAME = os.environ["FRAME_TABLE_NAME"]
FRAME_PROGRAM_EVENT_INDEX = os.environ["FRAME_PROGRAM_EVENT_INDEX"]
CHUNK_TABLE_NAME = os.environ["CHUNK_TABLE_NAME"]
WORKFLOW_EXECUTION_TABLE_NAME = os.environ["WORKFLOW_EXECUTION_TABLE_ARN"].split(":table/")[-1]
REPLAY_REQUEST_TABLE_NAME = os.environ["REPLAY_REQUEST_TABLE_NAME"]
REPLAY_RESULT_TABLE_NAME = os.environ["REPLAY_RESULT_TABLE_NAME"]
REPLAY_RESULT_PROGRAM_EVENT_INDEX = os.environ["REPLAY_RESULT_PROGRAM_EVENT_INDEX"]
SEGMENT_CACHE_BUCKET = os.environ["SEGMENT_CACHE_BUCKET"]

BACKOFF_TIME_SECS = 0.2
MAX_RETRY_COUNT = 5

ddb_resource = boto3.resource("dynamodb")
s3_resource = boto3.resource("s3")


def segment_chunks(arr, length):
    for i in range(0, len(arr), length): 
        yield arr[i:i + length]

def build_request_items(table_name, keys, items):
    requests = []

    for item in items:
        ddb_keys = {}

        for key in keys:
            ddb_keys[key] = item[key]

        requests.append(
            {
                "DeleteRequest": {
                    "Key": ddb_keys
                }
            }
        )

    return {
        table_name: requests
    }

def batch_delete(items, retry_count=0):
    try:
        response = ddb_resource.batch_write_item(RequestItems=items)
    
    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")
        error = e.response["Error"]["Message"]
        print(f"Error in performing the DynamoDB batch_write_item operation: {str(error)}")

        if retry_count > MAX_RETRY_COUNT:
            raise Exception("Exceeded the maximum number of allowed retries when retrying the BatchWriteItem operation")

        time.sleep((2 ** retry_count) * BACKOFF_TIME_SECS)
        return batch_delete(items, retry_count + 1)

    except Exception:
        print("Encountered an unknown exception when performing the BatchWriteItem operation")
        raise

    else:
        if "UnprocessedItems" in response and len(response["UnprocessedItems"]) > 0:
            if retry_count > MAX_RETRY_COUNT:
                raise Exception("Exceeded the maximum number of allowed retries when processing the BatchWriteItem UnprocessedItems")

            time.sleep((2 ** retry_count) * BACKOFF_TIME_SECS)
            return batch_delete(response["UnprocessedItems"], retry_count + 1)

def delete_ddb_items(event, program, table_name, keys, index_name=None, retry_count=0):
    try:
        ddb_table = ddb_resource.Table(table_name)

        # Query and delete items in the table
        if index_name:
            if "ReplayResults" in table_name: # Applies only to the ReplayResults table
                response = ddb_table.query(
                    IndexName=index_name,
                    KeyConditionExpression=Key("Program").eq(program) & Key("Event").eq(event),
                    ProjectionExpression=f"#{keys[0]}",
                    ExpressionAttributeNames={
                        f"#{keys[0]}": keys[0]
                    }
                )

            else: # Applies only to the PluginResult and Frame tables
                response = ddb_table.query(
                    IndexName=index_name,
                    KeyConditionExpression=Key("ProgramEvent").eq(f"{program}#{event}"),
                    ProjectionExpression=f"#{keys[0]}, #{keys[1]}",
                    ExpressionAttributeNames={
                        f"#{keys[0]}": keys[0],
                        f"#{keys[1]}": keys[1]
                    }
                )

        else:
            response = ddb_table.query(
                KeyConditionExpression=Key(keys[0]).eq(f"{program}#{event}"),
                ProjectionExpression=f"#{keys[0]}, #{keys[1]}",
                ExpressionAttributeNames={
                    f"#{keys[0]}": keys[0],
                    f"#{keys[1]}": keys[1]
                }
            )

        print(f"Query returned {len(response['Items'])} items")

        cur_items = 0
        total_items = len(response["Items"])

        for segment_list in segment_chunks(response["Items"], 25):
            cur_items += len(segment_list)
            print(f"Deleting {cur_items} of {total_items} items")
            batch_delete(build_request_items(table_name, keys, segment_list), 0)

        while "LastEvaluatedKey" in response:
            if index_name:
                if "ReplayResults" in table_name:
                    response = ddb_table.query(
                        ExclusiveStartKey=response["LastEvaluatedKey"],
                        IndexName=index_name,
                        KeyConditionExpression=Key("Program").eq(program) & Key("Event").eq(event),
                        ProjectionExpression=f"#{keys[0]}",
                        ExpressionAttributeNames={
                            f"#{keys[0]}": keys[0]
                        }
                    )

                else:
                    response = ddb_table.query(
                        ExclusiveStartKey=response["LastEvaluatedKey"],
                        IndexName=index_name,
                        KeyConditionExpression=Key("ProgramEvent").eq(f"{program}#{event}"),
                        ProjectionExpression=f"#{keys[0]}, #{keys[1]}",
                        ExpressionAttributeNames={
                            f"#{keys[0]}": keys[0],
                            f"#{keys[1]}": keys[1]
                        }
                    )

            else:
                response = ddb_table.query(
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                    KeyConditionExpression=Key(keys[0]).eq(f"{program}#{event}"),
                    ProjectionExpression=f"#{keys[0]}, #{keys[1]}",
                    ExpressionAttributeNames={
                        f"#{keys[0]}": keys[0],
                        f"#{keys[1]}": keys[1]
                    }
                )

            print(f"Query pagination returned {len(response['Items'])} items")

            total_items += len(response["Items"])

            for segment_list in segment_chunks(response["Items"], 25):
                cur_items += len(segment_list)
                print(f"Deleting {cur_items} of {total_items} items")
                batch_delete(build_request_items(table_name, keys, segment_list), 0)

    except ClientError as e:
        print(f"Got DynamoDB ClientError: {str(e)}")
        error = e.response["Error"]["Message"]
        print(f"Error in querying the items to delete from '{table_name}' for Event '{event}' and Program '{program}': {str(error)}")

        if retry_count > MAX_RETRY_COUNT:
            raise Exception("Exceeded the maximum number of allowed retries when retrying the Query operation")

        time.sleep((2 ** retry_count) * BACKOFF_TIME_SECS)
        return delete_ddb_items(event, program, table_name, keys, index_name, retry_count + 1)

    except Exception:
        print(f"Encountered an unknown exception when querying and deleting the items from '{table_name}' for Event '{event}' and Program '{program}'")
        raise

    else:
        print(f"Successfully deleted all the items in '{table_name}' table for Event '{event}' and Program '{program}'")

def batch_delete_objects(obj_collection, retry_count=0):
    try:
        response = obj_collection.delete()

    except ClientError as e:
        print(f"Got S3 ClientError: {str(e)}")
        error = e.response["Error"]["Message"]
        print(f"Error in performing the S3 Delete operation: {str(error)}")

        if retry_count > MAX_RETRY_COUNT:
            raise Exception("Exceeded the maximum number of allowed retries when retrying the S3 Delete operation")

        time.sleep((2 ** retry_count) * BACKOFF_TIME_SECS)
        return batch_delete_objects(obj_collection, retry_count + 1)

    except Exception as e:
        print(f"Encountered an unknown exception when performing the S3 Delete operation")
        raise

    else:
        if "Errors" in response and len(response["Errors"]) > 0:
            if retry_count > MAX_RETRY_COUNT:
                raise Exception("Exceeded the maximum number of allowed retries when retrying the failed S3 Delete objects")

            time.sleep((2 ** retry_count) * BACKOFF_TIME_SECS)
            return batch_delete_objects(obj_collection, retry_count + 1)

def find_and_delete_s3_objects(event, program, bucket_name, retry_count=0):
    try:
        bucket = s3_resource.Bucket(bucket_name)

        obj_collection = bucket.objects.filter(Prefix=f"{program}/{event}/")
        obj_collection_len = sum(1 for _ in obj_collection)

        while obj_collection_len > 0:
            print(f"Deleting {obj_collection_len} cached objects in S3")
            batch_delete_objects(obj_collection, 0)
            obj_collection = bucket.objects.filter(Prefix=f"{program}/{event}/")
            obj_collection_len = sum(1 for _ in obj_collection)

    except ClientError as e:
        print(f"Got S3 ClientError: {str(e)}")
        error = e.response["Error"]["Message"]
        print(f"Error in finding and deleting cached objects in S3 for Event '{event}' and Program '{program}': {str(error)}")

        if retry_count > MAX_RETRY_COUNT:
            raise Exception("Exceeded the maximum number of allowed retries when retrying the Find and Delete operation")

        time.sleep((2 ** retry_count) * BACKOFF_TIME_SECS)
        return find_and_delete_s3_objects(event, program, bucket_name, retry_count + 1)

    except Exception as e:
        print(f"Encountered an unknown exception while finding and deleting cached objects in S3 for Event '{event}' and Program '{program}'")
        raise

    else:
        print(f"Successfully deleted all the cached objects from S3 for Event '{event}' and Program '{program}'")

def lambda_handler(event, context):
    print("Lambda got the following event:\n", event)

    print(f"Processing {len(event['Records'])} records retrieved from the SQS queue")

    for record in event["Records"]:
        try:
            message = json.loads(record["body"])

            p_event = message["Event"]
            program = message["Program"]

            print(f"Got the deletion notification for Event '{p_event}' and Program '{program}'. Starting the cleanup process.")

            print(f"Deleting all the items in '{PLUGIN_RESULT_TABLE_NAME}' table for Event '{p_event}' and Program '{program}'")
            delete_ddb_items(p_event, program, PLUGIN_RESULT_TABLE_NAME, ["PK", "Start"], index_name=PLUGIN_RESULT_PROGRAM_EVENT_INDEX, retry_count=0)

            print(f"Deleting all the items in '{FRAME_TABLE_NAME}' table for Event '{p_event}' and Program '{program}'")
            delete_ddb_items(p_event, program, FRAME_TABLE_NAME, ["Id", "FrameNumber"], index_name=FRAME_PROGRAM_EVENT_INDEX, retry_count=0)

            print(f"Deleting all the items in '{CHUNK_TABLE_NAME}' table for Event '{p_event}' and Program '{program}'")
            delete_ddb_items(p_event, program, CHUNK_TABLE_NAME, ["PK", "Start"], retry_count=0)

            print(f"Deleting all the items in '{WORKFLOW_EXECUTION_TABLE_NAME}' table for Event '{p_event}' and Program '{program}'")
            delete_ddb_items(p_event, program, WORKFLOW_EXECUTION_TABLE_NAME, ["PK", "ChunkNumber"], retry_count=0)

            print(f"Deleting all the items in '{REPLAY_REQUEST_TABLE_NAME}' table for Event '{p_event}' and Program '{program}'")
            delete_ddb_items(p_event, program, REPLAY_REQUEST_TABLE_NAME, ["PK", "ReplayId"], retry_count=0)

            print(f"Deleting all the items in '{REPLAY_RESULT_TABLE_NAME}' table for Event '{p_event}' and Program '{program}'")
            delete_ddb_items(p_event, program, REPLAY_RESULT_TABLE_NAME, ["ProgramEventReplayId"], index_name=REPLAY_RESULT_PROGRAM_EVENT_INDEX, retry_count=0)

            print(f"Deleting all the cached objects in '{SEGMENT_CACHE_BUCKET}' bucket for Event '{p_event}' and Program '{program}'")
            find_and_delete_s3_objects(p_event, program, SEGMENT_CACHE_BUCKET, retry_count=0)

            print(f"Successfully completed the cleanup process for Event '{p_event}' and Program '{program}'")

        except Exception as e:
            print(f"Encountered an exception while performing the cleanup process for Event '{p_event}' and Program '{program}': {str(e)}")
            print(traceback.format_exc())
            raise
    
    print(f"Completed processing {len(event['Records'])} records")
