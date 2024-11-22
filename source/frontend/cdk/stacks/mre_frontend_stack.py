'''
 Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 SPDX-License-Identifier: Apache-2.0
'''
from constructs import Construct
from aws_cdk import (
    CfnOutput,
    CfnParameter,
    Stack,
    aws_iam,
    aws_cognito,
    aws_amplify_alpha as aws_amplify,
)
from cdk_nag import NagSuppressions


class MreFrontendStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # region Cognito
        user_pool = aws_cognito.UserPool(
            self, "MRE-frontend",
            user_pool_name="MRE-frontend"
        )

        admin_email = CfnParameter(self, "adminemail", type="String")

        aws_cognito.CfnUserPoolUser(
            self, "CognitoUser",
            user_pool_id=user_pool.user_pool_id,
            desired_delivery_mediums=["EMAIL"],
            user_attributes=[{
                "name": "email",
                "value": admin_email.value_as_string
            }],
            username="Admin"
        )

        user_pool_client = aws_cognito.UserPoolClient(
            self, "MRE-frontend-UserPoolClient",
            user_pool=user_pool
        )

        identity_pool = aws_cognito.CfnIdentityPool(
            self, "MRE-frontend-IdentityPool",
            identity_pool_name="MRE-frontend-IdentityPool",
            cognito_identity_providers=[{
                "clientId": user_pool_client.user_pool_client_id,
                "providerName": user_pool.user_pool_provider_name
            }],
            allow_unauthenticated_identities=False
        )

        unauthenticated_role = aws_iam.Role(
            self, 'CognitoDefaultUnauthenticatedRole',
            assumed_by=aws_iam.FederatedPrincipal(
                'cognito-identity.amazonaws.com',
                conditions={"StringEquals": {
                    "cognito-identity.amazonaws.com:aud": identity_pool.ref},
                    "ForAnyValue:StringLike": {
                        "cognito-identity.amazonaws.com:amr": "unauthenticated"}},
                assume_role_action="sts:AssumeRoleWithWebIdentity")
        )

        authenticated_role = aws_iam.Role(
            self, 'CognitoDefaultAuthenticatedRole',
            assumed_by=aws_iam.FederatedPrincipal(
                'cognito-identity.amazonaws.com',
                conditions={"StringEquals": {
                    "cognito-identity.amazonaws.com:aud": identity_pool.ref},
                    "ForAnyValue:StringLike": {"cognito-identity.amazonaws.com:amr": "authenticated"}},
                assume_role_action="sts:AssumeRoleWithWebIdentity")
        )

        authenticated_role.add_to_policy(
            aws_iam.PolicyStatement(
                effect=aws_iam.Effect.ALLOW,
                resources=[
                    f"arn:aws:execute-api:{Stack.of(self).region}:{Stack.of(self).account}:*"
                ],
                actions=["execute-api:Invoke", "execute-api:ManageConnections"],
            )
        )

        authenticated_role.add_to_policy(
            aws_iam.PolicyStatement(
                effect=aws_iam.Effect.ALLOW,
                resources=[
                    f"arn:aws:lambda:{Stack.of(self).region}:{Stack.of(self).account}:function:*"
                ],
                actions=["lambda:InvokeFunctionUrl"],
            )
        )

        aws_cognito.CfnIdentityPoolRoleAttachment(
            self, "DefaultValid",
            identity_pool_id=identity_pool.ref,
            roles={
                "unauthenticated": unauthenticated_role.role_arn,
                "authenticated": authenticated_role.role_arn
            }
        )

        # endregion

        # region App
        app = aws_amplify.App(self, "app", app_name="mre-frontend")

        app.add_branch("main", stage="PRODUCTION")
        # endregion App

        CfnOutput(self, "webAppURL", value="main." + app.default_domain)
        CfnOutput(self, "webAppId", value=app.app_id)
        CfnOutput(self, "region", value=self.region)
        CfnOutput(self, "userPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "appClientId", value=user_pool_client.user_pool_client_id)
        CfnOutput(self, "identityPoolId", value=identity_pool.ref)
        CfnOutput(
            self,
            "stagingBucketName",
            value=f"cdk-{self.synthesizer.bootstrap_qualifier}-assets-{self.account}-{self.region}",
        )

        # cdk-nag suppressions
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-COG1",
                    "reason": "CDK provisions a default password policy with a length of at least 8 characters, as well as requiring uppercase, numeric, and special characters",
                },
                {
                    "id": "AwsSolutions-COG2",
                    "reason": "The frontend UI does not require MFA",
                },
                {
                    "id": "AwsSolutions-COG3",
                    "reason": "The frontend UI does not require AdvancedSecurityMode as it is a demo UI",
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Cognito default authenticated role needs wildcard permissions to access the MRE API Gateway endpoint",
                    "appliesTo": [
                        "Resource::arn:aws:execute-api:<AWS::Region>:<AWS::AccountId>:*",
                        "Resource::arn:aws:lambda:<AWS::Region>:<AWS::AccountId>:function:*",
                    ],
                },
            ],
        )
