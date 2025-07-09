#  Copyright 2024 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ddb_resource = boto3.resource("dynamodb")


def on_event(event, context):
    print("Lambda got the following event:\n", json.dumps(event))

    request_type = event["RequestType"]

    if request_type == "Create":
        return on_create(event)
    if request_type == "Update":
        return on_update(event)
    if request_type == "Delete":
        return on_delete(event)

    raise Exception(f"Invalid request type: {request_type}")


def on_create(event):
    props = event["ResourceProperties"]
    print(f"Create new resource with {props=}")

    system_table_name = props["system_table_name"]
    genai_search_prompt_name = props["genai_search_prompt_name"]
    genai_search_prompt = props["genai_search_prompt"]

    system_table = ddb_resource.Table(system_table_name)

    # PutItem to DynamoDB
    system_table.put_item(
        Item={
            "Name": genai_search_prompt_name,
            "Description": "[DO NOT DELETE] Prompt used by the MRE framework for generative AI search",
            "Value": genai_search_prompt,
        }
    )

    logger.info(f"PutItem to {system_table_name} successful")

    physical_id = generate_physical_id(system_table_name)
    return {"PhysicalResourceId": physical_id}


def on_update(event):
    props = event["ResourceProperties"]
    print(f"Update resource with {props=}")

    system_table_name = props["system_table_name"]
    genai_search_prompt_name = props["genai_search_prompt_name"]
    genai_search_prompt = props["genai_search_prompt"]

    system_table = ddb_resource.Table(system_table_name)

    # Conditional PutItem to DynamoDB
    try:
        system_table.put_item(
            Item={
                "Name": genai_search_prompt_name,
                "Description": "[DO NOT DELETE] Prompt used by the MRE framework for generative AI search",
                "Value": genai_search_prompt,
            },
            ConditionExpression="attribute_not_exists(#n)",
            ExpressionAttributeNames={"#n": "Name"},
        )
        logger.info(f"Conditional PutItem to {system_table_name} successful")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.info(f"Item already exists in {system_table_name}")
        else:
            raise e
    except Exception as e:
        raise e


def on_delete(event):
    pass


def generate_physical_id(table_name):
    return f"CustomPutItem{table_name}"
