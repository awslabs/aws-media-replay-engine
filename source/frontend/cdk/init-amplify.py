'''
 Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 SPDX-License-Identifier: Apache-2.0
'''

import boto3
from botocore.config import Config
import json
import sys


def get_stack_outputs(region, mode):
    if mode == "New":
        with open("cdk-outputs.json", "r") as cdk_outputs:
            cdk_outputs_json = json.loads(cdk_outputs.read())
            return {
                "amplify_app_id": cdk_outputs_json["mre-frontend-stack"]["webAppId"],
                "web_url": cdk_outputs_json["mre-frontend-stack"]["webAppURL"],
                "staging_bucket_name": cdk_outputs_json["mre-frontend-stack"][
                    "stagingBucketName"
                ],
            }
    else:
        cfn_client = boto3.client("cloudformation", region_name=region)
        response = cfn_client.describe_stacks(StackName="mre-frontend-stack")
        stack_outputs = response["Stacks"][0]["Outputs"]
        output_dict = {}
        for output in stack_outputs:
            if "webAppId" in output["OutputKey"]:
                output_dict["amplify_app_id"] = output["OutputValue"]
            if "webAppURL" in output["OutputKey"]:
                output_dict["web_url"] = output["OutputValue"]
            if "stagingBucketName" in output["OutputKey"]:
                output_dict["staging_bucket_name"] = output["OutputValue"]
        return output_dict


def get_ssm_parameters(ssm_client):
    params = {}
    param_names = [
        "/MRE/ControlPlane/EndpointURL",
        "/MRE/DataPlane/EndpointURL",
        "/MRE/ControlPlane/MediaOutputBucket",
        "/MRE/ControlPlane/TransitionClipBucket",
        "/MRE/ControlPlane/MediaOutputDistribution",
    ]

    for param_name in param_names:
        params[param_name] = ssm_client.get_parameter(
            Name=param_name, WithDecryption=False
        )["Parameter"]["Value"]

    try:
        params["/MRE/GenAISearch/EndpointURL"] = ssm_client.get_parameter(
            Name="/MRE/GenAISearch/EndpointURL", WithDecryption=False
        )["Parameter"]["Value"]
    except ssm_client.exceptions.ParameterNotFound:
        params["/MRE/GenAISearch/EndpointURL"] = None

    return params


def main(region, mode, profile=None):
    print("Attempting to update Amplify config / custom headers ... ")

    if profile:
        boto3.setup_default_session(profile_name=profile)

    stack_outputs = get_stack_outputs(region, mode)
    ssm_client = boto3.client("ssm", region_name=region)
    params = get_ssm_parameters(ssm_client)

    control_plain_endpoint_domain = "/".join(
        params["/MRE/ControlPlane/EndpointURL"].split("/")[0:-2]
    )
    data_plane_endpoint_domain = "/".join(
        params["/MRE/DataPlane/EndpointURL"].split("/")[0:-2]
    )
    bucket_name = params["/MRE/ControlPlane/MediaOutputBucket"]
    transition_clip_bucket_name = params["/MRE/ControlPlane/TransitionClipBucket"]
    mre_cloudfront_domain_name = params["/MRE/ControlPlane/MediaOutputDistribution"]
    search_streaming_endpoint = params.get("/MRE/GenAISearch/EndpointURL", "")


    amplify_client = boto3.client("amplify", region_name=region)

    amplify_client.update_app(
        appId=stack_outputs["amplify_app_id"],
        customHeaders=f"""
        customHeaders:
          - pattern: '**/*'
            headers:
              - key: 'Strict-Transport-Security'
                value: 'max-age=31536000; includeSubDomains'
              - key: 'Cache-Control'
                value: 'no-store, no-cache'
              - key: 'Pragma'
                value: 'no-cache'  
              - key: 'X-Frame-Options'
                value: 'DENY'
              - key: 'X-XSS-Protection'
                value: '1; mode=block'
              - key: 'X-Content-Type-Options'
                value: 'nosniff'
              - key: 'Content-Security-Policy'
                value: >-
                    default-src 'none'; upgrade-insecure-requests; style-src 'self' 'unsafe-inline'; connect-src
                    'self' https://cognito-idp.{region}.amazonaws.com/
                    https://cognito-identity.{region}.amazonaws.com
                    {control_plain_endpoint_domain}
                    {search_streaming_endpoint or ''}
                    {data_plane_endpoint_domain}; script-src
                    https://{stack_outputs["web_url"]} 'self'
                    https://cognito-idp.{region}.amazonaws.com/
                    https://cognito-identity.{region}.amazonaws.com
                    {control_plain_endpoint_domain}
                    {search_streaming_endpoint or ''}
                    {data_plane_endpoint_domain}; img-src 'self'
                    https://{bucket_name}.s3.amazonaws.com;
                    media-src 'self'
                    https://{bucket_name}.s3.amazonaws.com
                    https://{transition_clip_bucket_name}.s3.amazonaws.com
                    https://{mre_cloudfront_domain_name};
                    object-src 'none';frame-ancestors 'none'; font-src 'self'
                    https://{stack_outputs["web_url"]}; manifest-src 'self'
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
    s3_client.upload_file(
        f"../build/{asset_key}", stack_outputs["staging_bucket_name"], asset_key
    )
    source_url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": stack_outputs["staging_bucket_name"], "Key": asset_key},
        ExpiresIn=300,
    )
    amplify_client.start_deployment(
        appId=stack_outputs["amplify_app_id"], branchName="main", sourceUrl=source_url
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
