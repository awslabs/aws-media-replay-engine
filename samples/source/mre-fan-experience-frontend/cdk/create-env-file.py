# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import json
import sys


def main(region, profile=None):
    cdk_outputs = open('cdk-outputs.json', 'r')
    cdk_outputs_json = json.loads(cdk_outputs.read())

    user_pool_id = cdk_outputs_json['mre-fan-experience-frontend-stack']['userPoolId']
    identity_pool_id = cdk_outputs_json['mre-fan-experience-frontend-stack']['identityPoolId']
    app_client_id = cdk_outputs_json['mre-fan-experience-frontend-stack']['appClientId']

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

    media_output_distro = ssm_client.get_parameter(
         Name='/MRE/ControlPlane/MediaOutputDistribution',
         WithDecryption=False
     )

    cloudfront_url = f"https://{media_output_distro['Parameter']['Value']}"


    environmentVariables={
            "REACT_APP_BASE_API": control_plain_endpoint['Parameter']["Value"],
            "REACT_APP_DATA_PLANE_API": data_plane_endpoint['Parameter']["Value"],
            "REACT_APP_REGION": region,
            "REACT_APP_USER_POOL_ID": user_pool_id,
            "REACT_APP_APP_CLIENT_ID": app_client_id,
            "REACT_APP_IDENTITY_POOL_ID": identity_pool_id,
            "REACT_APP_CLOUDFRONT_PREFIX": cloudfront_url,
        }
           
    with open('../.env', 'w') as f:
        for key, value in environmentVariables.items():
            f.write(f'{key}={value}\n')

    return 1


if __name__ == "__main__":
    if len(sys.argv) == 3:
        result = main(sys.argv[1], sys.argv[2])
    else:
        result = main(sys.argv[1])

    sys.exit(0) if result else sys.exit(1)
