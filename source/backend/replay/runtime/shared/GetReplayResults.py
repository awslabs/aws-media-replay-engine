#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import gzip
import json
import boto3
from boto3.dynamodb.conditions import Key

#TODO: Replace the following Values as per your Env
REPLAY_RESULTS_TABLE_NAME = ""
PK_VALUE = ""


ddb_resource = boto3.resource("dynamodb")
replay_results_table = ddb_resource.Table(REPLAY_RESULTS_TABLE_NAME)
replay_results_query = replay_results_table.query(
            KeyConditionExpression=Key("ProgramEventReplayId").eq(PK_VALUE)
        )
replay_results = gzip.decompress(bytes(replay_results_query['Items'][0]['ReplayResults'])).decode('utf-8')
results = json.loads(replay_results)
print(json.dumps([x for x in results]))
