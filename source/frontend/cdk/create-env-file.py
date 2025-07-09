# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import sys
import boto3


def get_stack_outputs(region, mode, include_gen_ai=True):
    """Get stack outputs either from CDK outputs file or CloudFormation"""
    output_map = {
        "userPoolId": "user_pool_id",
        "identityPoolId": "identity_pool_id",
        "appClientId": "app_client_id" "",
    }

    if mode == "New":
        with open("cdk-outputs.json", "r") as f:
            cdk_outputs = json.load(f)
            stack_data = cdk_outputs["mre-frontend-stack"]
            outputs = {
                output_map[k]: stack_data[k]
                for k in ["userPoolId", "identityPoolId", "appClientId"]
            }
    else:
        cfn_client = boto3.client("cloudformation", region_name=region)
        response = cfn_client.describe_stacks(StackName="mre-frontend-stack")
        stack_outputs = response["Stacks"][0]["Outputs"]
        outputs = {
            v: next(o["OutputValue"] for o in stack_outputs if k in o["OutputKey"])
            for k, v in output_map.items()
        }

    if include_gen_ai:
        try:
            cfn_client = boto3.client("cloudformation", region_name=region)
            response = cfn_client.describe_stacks(StackName="aws-mre-genai-search")
            stack_outputs = response["Stacks"][0]["Outputs"]
            outputs["search_url"] = next(
                o["OutputValue"]
                for o in stack_outputs
                if "MREGenAISearchFnUrl" in o["OutputKey"]
            )
        except cfn_client.exceptions.ClientError as e:
            outputs["search_url"] = None

    return outputs


def get_ssm_parameters(ssm_client):
    """Get required parameters from SSM"""
    params = {
        "control_plane": "/MRE/ControlPlane/EndpointURL",
        "data_plane": "/MRE/DataPlane/EndpointURL",
        "cloudfront": "/MRE/ControlPlane/MediaOutputDistribution",
    }

    return {
        k: ssm_client.get_parameter(Name=v, WithDecryption=False)["Parameter"]["Value"]
        for k, v in params.items()
    }


def main(region, mode, profile=None):
    print("Attempting to update Amplify config / custom headers ... ")

    if profile:
        boto3.setup_default_session(profile_name=profile)

    stack_outputs = get_stack_outputs(region, mode)
    ssm_client = boto3.client("ssm", region_name=region)
    ssm_params = get_ssm_parameters(ssm_client)

    environment_variables = {
        "REACT_APP_BASE_API": ssm_params["control_plane"],
        "REACT_APP_DATA_PLANE_API": ssm_params["data_plane"],
        "REACT_APP_REGION": region,
        "REACT_APP_USER_POOL_ID": stack_outputs["user_pool_id"],
        "REACT_APP_APP_CLIENT_ID": stack_outputs["app_client_id"],
        "REACT_APP_IDENTITY_POOL_ID": stack_outputs["identity_pool_id"],
        "REACT_APP_CLOUDFRONT_DOMAIN_NAME": ssm_params["cloudfront"],
    }

    if stack_outputs["search_url"]:
        environment_variables["REACT_APP_SEARCH_LAMBDA_URL"] = stack_outputs[
            "search_url"
        ]

    with open("../.env", "w") as f:
        for key, value in environment_variables.items():
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
