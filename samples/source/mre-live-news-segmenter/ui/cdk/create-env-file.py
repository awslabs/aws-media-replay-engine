# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import json
import sys


def main(region, profile=None):
    cdk_outputs = open("cdk-outputs.json", "r")
    cdk_outputs_json = json.loads(cdk_outputs.read())

    user_pool_id = cdk_outputs_json["mre-live-news-segmenter-frontend-stack"][
        "userPoolId"
    ]
    identity_pool_id = cdk_outputs_json["mre-live-news-segmenter-frontend-stack"][
        "identityPoolId"
    ]
    app_client_id = cdk_outputs_json["mre-live-news-segmenter-frontend-stack"][
        "appClientId"
    ]

    if profile:
        boto3.setup_default_session(profile_name=profile)

    ssm_client = boto3.client("ssm", region_name=region)

    control_plane_endpoint = ssm_client.get_parameter(
        Name="/MRE/ControlPlane/EndpointURL", WithDecryption=False
    )

    data_plane_endpoint = ssm_client.get_parameter(
        Name="/MRE/DataPlane/EndpointURL", WithDecryption=False
    )

    search_streaming_endpoint = ssm_client.get_parameter(
        Name="/MRE/GenAISearch/EndpointURL", WithDecryption=False
    )["Parameter"]["Value"]

    live_news_segmenter_endpoint = ssm_client.get_parameter(
        Name="/MRE/Samples/LiveNewsSegmenter/EndpointURL", WithDecryption=False
    )

    media_output_distro = ssm_client.get_parameter(
        Name="/MRE/ControlPlane/MediaOutputDistribution", WithDecryption=False
    )

    cloudfront_url = f"https://{media_output_distro['Parameter']['Value']}"

    environmentVariables = {
        "VITE_CONTROL_PLANE_ENDPOINT": control_plane_endpoint["Parameter"]["Value"],
        "VITE_API_DATAPLANE": data_plane_endpoint["Parameter"]["Value"],
        "VITE_LIVE_NEWS_SEGMENTER_ENDPOINT": live_news_segmenter_endpoint["Parameter"][
            "Value"
        ],
        "VITE_APP_REGION": region,
        "VITE_APP_USER_POOL_ID": user_pool_id,
        "VITE_APP_CLIENT_ID": app_client_id,
        "VITE_APP_IDENTITY_POOL_ID": identity_pool_id,
        "VITE_CLOUDFRONT_DOMAIN_NAME": cloudfront_url,
        "VITE_API_STREAMING": search_streaming_endpoint,
    }

    with open("../.env", "w") as f:
        for key, value in environmentVariables.items():
            f.write(f"{key}={value}\n")

    return 1


if __name__ == "__main__":
    if len(sys.argv) == 3:
        result = main(sys.argv[1], sys.argv[2])
    else:
        result = main(sys.argv[1])

    sys.exit(0) if result else sys.exit(1)
