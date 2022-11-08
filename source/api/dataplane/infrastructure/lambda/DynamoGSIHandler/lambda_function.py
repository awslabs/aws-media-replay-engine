#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import boto3

ddb_client = boto3.client('dynamodb')


def on_event(event, context):
    print(event)
    request_type = event['RequestType']

    if request_type == 'Create':
        return on_create(event)
    if request_type == 'Update':
        return on_update(event)
    if request_type == 'Delete':
        return on_delete(event)

    raise Exception(f'Invalid request type: {request_type}')


def on_create(event):
    props = event['ResourceProperties']
    print(f'Create new resource with {props=}')

    create_gsi(table_name=props['table_name'], index_name=props['index_name'], partition_key_attr=props['partition_key'], sort_key_attr=props['sort_key'] if 'sort_key' in props else {})
    physical_id = generate_physical_id_for_index(props['index_name'])
    return {'PhysicalResourceId': physical_id}


def on_update(event):
    props = event['ResourceProperties']
    print(f'Update resource with {props=}')

    table_name = props['table_name']
    index_name = props['index_name']

    if not is_index_in_table(table_name, index_name):
        on_create(event)
    else:
        print(f"No action needed as index '{index_name}' is already present in table '{table_name}'")


def on_delete(event):
    props = event['ResourceProperties']
    print(f'Delete resource with {props=}')

    physical_id = event['PhysicalResourceId'] if 'PhysicalResourceId' in event and event['PhysicalResourceId'] else None

    if physical_id:
        delete_gsi(table_name=props['table_name'], index_name=props['index_name'])
    else:
        print('No action needed as PhysicalResourceId is missing in the event')


def generate_physical_id_for_index(index_name):
    return f'CustomGSI{index_name}'


def is_index_in_table(table_name, index_name):
    response = ddb_client.describe_table(
        TableName=table_name
    )

    if 'GlobalSecondaryIndexes' not in response['Table'] or len(response['Table']['GlobalSecondaryIndexes']) < 1:
        return False

    for gsi in response['Table']['GlobalSecondaryIndexes']:
        if gsi['IndexName'] == index_name:
            return True

    return False


def create_gsi(table_name, index_name, partition_key_attr, sort_key_attr={}):
    attribute_definitions = [
        {
            'AttributeName': partition_key_attr['Name'],
            'AttributeType': partition_key_attr['Type']
        }
    ]

    key_schema = [
        {
            'AttributeName': partition_key_attr['Name'],
            'KeyType': 'HASH'
        }
    ]

    if sort_key_attr:
        attribute_definitions.append(
            {
                'AttributeName': sort_key_attr['Name'],
                'AttributeType': sort_key_attr['Type']
            }
        )

        key_schema.append(
            {
                'AttributeName': sort_key_attr['Name'],
                'KeyType': 'RANGE'
            },
        )

    ddb_client.update_table(
        TableName=table_name,
        AttributeDefinitions=attribute_definitions,
        GlobalSecondaryIndexUpdates=[
            {
                'Create': {
                    'IndexName': index_name,
                    'KeySchema': key_schema,
                    'Projection': {
                        'ProjectionType': 'ALL'
                    }
                }
            }
        ]
    )

    print(f"Created GSI '{index_name}' in table '{table_name}'")


def delete_gsi(table_name, index_name):
    ddb_client.update_table(
        TableName=table_name,
        GlobalSecondaryIndexUpdates=[
            {
                'Delete': {
                    'IndexName': index_name
                }
            }
        ]
    )

    print(f"Deleted GSI '{index_name}' in table '{table_name}'")
