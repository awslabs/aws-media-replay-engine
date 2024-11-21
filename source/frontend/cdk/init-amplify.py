'''
 Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 SPDX-License-Identifier: Apache-2.0
'''

import boto3
from botocore.config import Config
import json
import sys


def main(region, mode, profile=None):
    print("Attempting to update Amplify config / custom headers ... ")
    if mode == "New":
        cdk_outputs = open('cdk-outputs.json', 'r')
        cdk_outputs_json = json.loads(cdk_outputs.read())

        amplify_app_id = cdk_outputs_json["mre-frontend-stack"]["webAppId"]
        web_url = cdk_outputs_json["mre-frontend-stack"]["webAppURL"]
        staging_bucket_name = cdk_outputs_json["mre-frontend-stack"][
            "stagingBucketName"
        ]
    else:
        cfn_client = boto3.client("cloudformation", region_name=region)
        response = cfn_client.describe_stacks(StackName="mre-frontend-stack")
        stack_outputs = response["Stacks"][0]["Outputs"]
        for stack_output in stack_outputs:
            if "webAppId" in stack_output["OutputKey"]:
                amplify_app_id = stack_output["OutputValue"]
            if "webAppURL" in stack_output["OutputKey"]:
                web_url = stack_output["OutputValue"]
            if "stagingBucketName" in stack_output["OutputKey"]:
                staging_bucket_name = stack_output["OutputValue"]

    if profile:
        boto3.setup_default_session(profile_name=profile)

    ssm_client = boto3.client('ssm', region_name=region)

    control_plain_endpoint = ssm_client.get_parameter(
        Name='/MRE/ControlPlane/EndpointURL',
        WithDecryption=False
    )

    data_plane_endpoint = ssm_client.get_parameter(
        Name='/MRE/DataPlane/EndpointURL',
        WithDecryption=False
    )

    bucket_parameter = ssm_client.get_parameter(
        Name='/MRE/ControlPlane/MediaOutputBucket',
        WithDecryption=False
    )

    transition_clip_bucket_parameter = ssm_client.get_parameter(
        Name='/MRE/ControlPlane/TransitionClipBucket',
        WithDecryption=False
    )

    mre_cloudfront_domain_name_parameter = ssm_client.get_parameter(
        Name='/MRE/ControlPlane/MediaOutputDistribution',
        WithDecryption=False
    )

    mre_cloudfront_domain_name = mre_cloudfront_domain_name_parameter["Parameter"][
        "Value"
    ]

    control_plain_endpoint_domain = '/'.join(
        control_plain_endpoint['Parameter']['Value'].split('/')[0:-2])
    data_plane_endpoint_domain = '/'.join(
        data_plane_endpoint['Parameter']['Value'].split('/')[0:-2])
    bucket_name = bucket_parameter['Parameter']['Value']

    transition_clip_bucket_name = transition_clip_bucket_parameter['Parameter']['Value']

    amplify_client = boto3.client('amplify', region_name=region)

    amplify_client.update_app(
        appId=amplify_app_id,
        customHeaders=f"""
        customHeaders:
          - pattern: '**/*'
            headers:
              - key: 'Strict-Transport-Security'
                value: 'max-age=31536000; includeSubDomains'
              - key: 'X-Frame-Options'
                value: 'SAMEORIGIN'
              - key: 'X-XSS-Protection'
                value: '1; mode=block'
              - key: 'X-Content-Type-Options'
                value: 'nosniff'
              - key: 'Content-Security-Policy'
                value: >-
                    default-src 'none'; style-src 'self' 'unsafe-inline'; connect-src
                    'self' https://cognito-idp.{region}.amazonaws.com/
                    https://cognito-identity.{region}.amazonaws.com
                    {control_plain_endpoint_domain}
                    {data_plane_endpoint_domain}; script-src
                    https://{web_url} 'self'
                    https://cognito-idp.{region}.amazonaws.com/
                    https://cognito-identity.{region}.amazonaws.com
                    {control_plain_endpoint_domain}
                    {data_plane_endpoint_domain}; img-src 'self'
                    https://{bucket_name}.s3.amazonaws.com;
                    media-src 'self'
                    https://{bucket_name}.s3.amazonaws.com
                    https://{transition_clip_bucket_name}.s3.amazonaws.com
                    https://{mre_cloudfront_domain_name};
                    object-src 'none';frame-ancestors 'none'; font-src 'self'
                    https://{web_url}; manifest-src 'self'
            """,
        customRules=[
            {
                'source': '</^((?!\.(css|gif|ico|jpg|js|png|txt|svg|woff|ttf)$).)*$/>',
                'target': '/index.html',
                'status': '200'
            }
        ]
    )

    print("Updated Amplify config / custom headers.")
    print("Hydrating Transition Config table ...")
    put_default_transition_config(transition_clip_bucket_name, region)
    print("Hydrating Transition Config table ...Done")

    s3_client = boto3.client(
        "s3", region_name=region, config=Config(signature_version="s3v4")
    )

    asset_key = "build.zip"
    s3_client.upload_file(f"../build/{asset_key}", staging_bucket_name, asset_key)
    source_url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": staging_bucket_name, "Key": asset_key},
        ExpiresIn=300,
    )
    amplify_client.start_deployment(
        appId=amplify_app_id, branchName="main", sourceUrl=source_url
    )

    return 1


def put_default_transition_config(transition_clip_bucket_name, region):

    ssm_client = boto3.client('ssm', region_name=region)
    transition_config_parameter = ssm_client.get_parameter(
        Name='/MRE/ControlPlane/TransitionConfigTableName',
        WithDecryption=False
    )


    model = {
        "Name": "FadeInFadeOut",
        "Config": {
            "FadeInMs": 500,
            "FadeOutMs": 500
        },
        "Description": "Black Fade in and Fade Out. This is the default Transition.",
        "ImageLocation": f"s3://{transition_clip_bucket_name}/FadeInFadeOut/transition_images/BlackFadeInFadeOut.png",
        "IsDefault": True,
        "MediaType": "Image",
        "PreviewVideoLocation": f"s3://{transition_clip_bucket_name}/FadeInFadeOut/preview/FadeInOutSample.mp4"
    }
    ddb_resource = boto3.resource("dynamodb", region_name=region)
    transition_config_table = ddb_resource.Table(
        transition_config_parameter['Parameter']['Value'])

    transition_config_table.put_item(
        Item=model
    )


if __name__ == "__main__":
    if len(sys.argv) == 4:
        result = main(sys.argv[1], sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3:
        result = main(sys.argv[1], sys.argv[2])
    else:
        result = main(sys.argv[1])

    sys.exit(0) if result else sys.exit(1)
