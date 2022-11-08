#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import boto3

ddb_client = boto3.client('dynamodb')


def is_complete(event, context):
    print(event)
    physical_id = event['PhysicalResourceId']
    request_type = event['RequestType']
    is_ready = False

    props = event['ResourceProperties']
    table_name = props['table_name']
    index_name = props['index_name']

    print(f'IsComplete handler with {physical_id=} and {props=}')
    print('Request type:', request_type)

    response = ddb_client.describe_table(
        TableName=table_name
    )

    if request_type != 'Delete':
        for gsi in response['Table']['GlobalSecondaryIndexes']:
            if gsi['IndexName'] == index_name:
                is_ready = True if gsi['IndexStatus'] == 'ACTIVE' else False
                break

    else:
        if 'GlobalSecondaryIndexes' not in response['Table'] or len(response['Table']['GlobalSecondaryIndexes']) < 1:
            is_ready = True

        else:
            is_ready = all([gsi['IndexName'] != index_name for gsi in response['Table']['GlobalSecondaryIndexes']])

    return { 'IsComplete': is_ready }
