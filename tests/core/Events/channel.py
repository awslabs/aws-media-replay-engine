
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0import pytest


import boto3
from filelock import FileLock

client = boto3.client('medialive')

def start_channel(channel_id):
    print(channel_id)
    client.start_channel(
        ChannelId=channel_id
    )

def stop_channel(channel_id):
    client.stop_channel(
        ChannelId=channel_id
    )

def get_channel_by_destination_bucket(bucket_name: str):
    response = client.list_channels()
    for channel in response['Channels']:
        if 'Destinations' in channel:
            for destination in channel['Destinations']:
                if 'Settings' in destination:
                    for setting in destination['Settings']:
                        if bucket_name in setting['Url']:
                            return channel['Id']

    return ""
