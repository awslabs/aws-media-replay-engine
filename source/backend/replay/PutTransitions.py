'''
 Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 SPDX-License-Identifier: Apache-2.0
'''

import boto3



def put_transition_config(region):
    '''
        Adds custom Transition configuration into the DDB TransitionConfig Table.
    '''

    ssm_client = boto3.client('ssm', region_name=region)
    
    transition_clip_bucket_parameter = ssm_client.get_parameter(
        Name='/MRE/ControlPlane/TransitionClipBucket',
        WithDecryption=False
    )
    transition_clip_bucket_name = transition_clip_bucket_parameter['Parameter']['Value']


    ssm_client = boto3.client('ssm', region_name=region)
    transition_config_parameter = ssm_client.get_parameter(
        Name='/MRE/ControlPlane/TransitionConfigTableName',
        WithDecryption=False
    )

    transition_config = {
        "Name": %%UPDATE TRANSITION NAME%%,
        "Description": %%UPDATE DESCRIPTION%%,
        "IsDefault": False,
        "MediaType": "Video",
        "PreviewVideoLocation": f"s3://{transition_clip_bucket_name}/%%UPDATE MP4 location%%",
        "TransitionClipLocation": f"s3://{transition_clip_bucket_name}/%%UPDATE MP4 location%%"
    }

    
    ddb_resource = boto3.resource("dynamodb")
    transition_config_table = ddb_resource.Table(
        transition_config_parameter['Parameter']['Value'])

    transition_config_table.put_item(
        Item=transition_config
    )


if __name__ == "__main__":
    put_transition_config("%%AWS REGION%%")