#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

##############################################################################
#
# PURPOSE:
# Starts a Media Live Channel
#
##############################################################################

import boto3
import traceback
import json

medialive_client = boto3.client("medialive")
def lambda_handler(event, context):

    print(f"Lambda got the following event:\n{json.dumps(event)}")
    try:
        if 'ChunkSourceDetail' in event['detail']:
            if 'ChannelId' in event['detail']['ChunkSourceDetail']:
                channel_id = event['detail']['ChunkSourceDetail']['ChannelId']
                response = medialive_client.describe_channel(
                                ChannelId=channel_id
                            )

                # Only start the channel if its Idle
                if response['State'] == 'IDLE':
                    medialive_client.start_channel(
                        ChannelId=channel_id
                    )
                    print(f"Started Channel = {channel_id}")
                else:
                    print(f"Channel = {channel_id} in Running State. Ignoring.")
    except Exception as e:
        print(f"Encountered an exception while starting MediaLive channel {str(e)}")
        print(traceback.format_exc())
        raise
    