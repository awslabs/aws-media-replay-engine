# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import json
import sys


def main(region, mode, profile=None):
    print("Attempting to update Amplify config / custom headers ... ")
    if mode == "New":
        cdk_outputs = open('cdk-outputs.json', 'r')
        cdk_outputs_json = json.loads(cdk_outputs.read())
        user_pool_id = cdk_outputs_json['mre-frontend-stack']['userPoolId']
        identity_pool_id = cdk_outputs_json['mre-frontend-stack']['identityPoolId']
        app_client_id = cdk_outputs_json['mre-frontend-stack']['appClientId']
    else:
        cfn_client = boto3.client('cloudformation', region_name=region)
        response = cfn_client.describe_stacks(
            StackName='mre-frontend-stack'
        )
        stack_outputs = response['Stacks'][0]['Outputs']
        for stack_output in stack_outputs:
            if 'appClientId' in stack_output['OutputKey']:
                app_client_id = stack_output['OutputValue']
            if 'identityPoolId' in stack_output['OutputKey']:
                identity_pool_id = stack_output['OutputValue']
            if 'userPoolId' in stack_output['OutputKey']:
                user_pool_id = stack_output['OutputValue']

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

    mre_cloudfront_domain_name_parameter = ssm_client.get_parameter(
        Name='/MRE/ControlPlane/MediaOutputDistribution',
        WithDecryption=False
    )

    mre_cloudfront_domain_name = mre_cloudfront_domain_name_parameter['Parameter']['Value']

    environmentVariables = {
        "REACT_APP_BASE_API": control_plain_endpoint["Parameter"]["Value"],
        "REACT_APP_DATA_PLANE_API": data_plane_endpoint["Parameter"]["Value"],
        "REACT_APP_REGION": region,
        "REACT_APP_USER_POOL_ID": user_pool_id,
        "REACT_APP_APP_CLIENT_ID": app_client_id,
        "REACT_APP_IDENTITY_POOL_ID": identity_pool_id,
        "REACT_APP_CLOUDFRONT_DOMAIN_NAME": mre_cloudfront_domain_name,
        "REACT_APP_SEARCH_LAMBDA_URL": "",
    }

    with open("../.env", "w") as f:
        for key, value in environmentVariables.items():
            f.write(f"{key}={value}\n")

    return 1


if __name__ == "__main__":
    if len(sys.argv) == 4:
        result = main(sys.argv[1], sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3:
        result = main(sys.argv[1], sys.argv[2])
    else:
        result = main(sys.argv[1])

    sys.exit(0) if result else sys.exit(1)