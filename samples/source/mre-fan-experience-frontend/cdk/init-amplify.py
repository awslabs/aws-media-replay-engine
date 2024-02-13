# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import json
import sys


def main(region, profile=None):
    cdk_outputs = open('cdk-outputs.json', 'r')
    cdk_outputs_json = json.loads(cdk_outputs.read())

    amplify_app_id = cdk_outputs_json['mre-fan-experience-frontend-stack']['webAppId']
    user_pool_id = cdk_outputs_json['mre-fan-experience-frontend-stack']['userPoolId']
    identity_pool_id = cdk_outputs_json['mre-fan-experience-frontend-stack']['identityPoolId']
    app_client_id = cdk_outputs_json['mre-fan-experience-frontend-stack']['appClientId']
    web_url = cdk_outputs_json['mre-fan-experience-frontend-stack']['webAppURL']

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

    control_plain_endpoint_domain = '/'.join(control_plain_endpoint['Parameter']['Value'].split('/')[0:-2])
    data_plane_endpoint_domain = '/'.join(data_plane_endpoint['Parameter']['Value'].split('/')[0:-2])
    bucket_name = bucket_parameter['Parameter']['Value']

    media_output_distro = ssm_client.get_parameter(
         Name='/MRE/ControlPlane/MediaOutputDistribution',
         WithDecryption=False
     )

    cloudfront_url = f"https://{media_output_distro['Parameter']['Value']}"

    mre_amplify_build_image = "public.ecr.aws/codebuild/amazonlinux2-x86_64-standard:5.0"

    amplify_client = boto3.client('amplify', region_name=region)

    amplify_client.update_app(
        appId=amplify_app_id,
        customHeaders=f'''
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
                    default-src 'none'; style-src 'self' 'unsafe-inline';
                    connect-src
                    'self' https://cognito-idp.{region}.amazonaws.com
                    https://cognito-identity.{region}.amazonaws.com
                    {control_plain_endpoint_domain}
                    {data_plane_endpoint_domain}
                    {cloudfront_url}/;
                    script-src
                    blob: 'self' 'unsafe-inline'
                    https://{web_url}/
                    https://cdn.jsdelivr.net/
                    https://cognito-idp.{region}.amazonaws.com
                    https://cognito-identity.{region}.amazonaws.com
                    {control_plain_endpoint_domain}
                    {data_plane_endpoint_domain};
                    img-src 'self'
                    https://{bucket_name}.s3.amazonaws.com;
                    media-src 'self'
                    blob:
                    https://{web_url}/
                    {cloudfront_url}/
                    https://cdn.jsdelivr.net/
                    https://{bucket_name}.s3.amazonaws.com;
                    object-src 'none';frame-ancestors 'none';
                    font-src 'self'
                    https://{web_url}/;
                    manifest-src 'self'
            ''',
        environmentVariables={
            "REACT_APP_BASE_API": control_plain_endpoint['Parameter']["Value"],
            "REACT_APP_DATA_PLANE_API": data_plane_endpoint['Parameter']["Value"],
            "REACT_APP_REGION": region,
            "REACT_APP_USER_POOL_ID": user_pool_id,
            "REACT_APP_APP_CLIENT_ID": app_client_id,
            "REACT_APP_IDENTITY_POOL_ID": identity_pool_id,
            "REACT_APP_CLOUDFRONT_PREFIX": cloudfront_url,
            "_CUSTOM_IMAGE": mre_amplify_build_image
        },
        customRules=[
            {
                'source': '</^((?!\.(css|gif|ico|jpg|js|png|txt|svg|woff|ttf)$).)*$/>',
                'target': '/index.html',
                'status': '200'
            }
        ]
    )

    return 1


if __name__ == "__main__":
    if len(sys.argv) == 3:
        result = main(sys.argv[1], sys.argv[2])
    else:
        result = main(sys.argv[1])

    sys.exit(0) if result else sys.exit(1)
