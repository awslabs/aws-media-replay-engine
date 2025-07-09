# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
from constructs import Construct
from aws_cdk import (
    CfnOutput,
    CfnParameter,
    Stack,
    Fn,
    aws_iam,
    aws_amplify_alpha as aws_amplify,
    aws_cognito,
    Duration
)
from cdk_nag import NagSuppressions

class MreFanExperienceFrontendStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # region Cognito
        user_pool = aws_cognito.UserPool(
            self, "MRE-fan-experience-frontend",
            user_pool_name="MRE-fan-experience-frontend"
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
            self, "MRE-fan-experience-frontend-UserPoolClient", user_pool=user_pool,
            # Set token validity durations
            access_token_validity=Duration.minutes(60),
            id_token_validity=Duration.minutes(60),
            refresh_token_validity=Duration.hours(10),
            # Enable token revocation
            enable_token_revocation=True,
        )

        identity_pool = aws_cognito.CfnIdentityPool(
            self, "MRE-fan-experience-frontend-IdentityPool",
            identity_pool_name="MRE-fan-experience-frontend-IdentityPool",
            cognito_identity_providers=[
                {
                    "clientId": user_pool_client.user_pool_client_id,
                    "providerName": user_pool.user_pool_provider_name,
                    "serverSideTokenCheck": True, #Amazon Cognito no longer accepts a signed-out user's ID token in a GetId request to an identity pool with ServerSideTokenCheck enabled for its user pool IdP configuration in CognitoIdentityProvider.
                }
            ],
            allow_unauthenticated_identities=False,
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
                    f"arn:aws:execute-api:{self.region}:{self.account}:{Fn.import_value('mre-dataplane-api-rest-id')}/*/GET/*",
                    f"arn:aws:execute-api:{self.region}:{self.account}:{Fn.import_value('mre-dataplane-api-rest-id')}/*/OPTIONS/*",
                    f"arn:aws:execute-api:{self.region}:{self.account}:{Fn.import_value('mre-dataplane-api-rest-id')}/*/@connections/*",
                    f"arn:aws:execute-api:{self.region}:{self.account}:{Fn.import_value('mre-default-api-gateway-rest-api-id')}/*/GET/*",
                    f"arn:aws:execute-api:{self.region}:{self.account}:{Fn.import_value('mre-default-api-gateway-rest-api-id')}/*/OPTIONS/*",
                    f"arn:aws:execute-api:{self.region}:{self.account}:{Fn.import_value('mre-default-api-gateway-rest-api-id')}/*/@connections/*"
                ],
                actions=["execute-api:Invoke", "execute-api:ManageConnections"],
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

        app = aws_amplify.App(self, "app", app_name="mre-fan-experience-frontend")

        app.add_branch("main", stage="PRODUCTION")

        # endregion App

        CfnOutput(self, "webAppURL", value="main." + app.default_domain)
        CfnOutput(self, "webAppId", value=app.app_id)
        CfnOutput(self, "region", value=self.region)
        CfnOutput(self, "userPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "appClientId", value=user_pool_client.user_pool_client_id)
        CfnOutput(self, "identityPoolId", value=identity_pool.ref)
        CfnOutput(self, "stagingBucketName", value=f'cdk-{self.synthesizer.bootstrap_qualifier}-assets-{self.account}-{self.region}')
        
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
                    "reason": "The fan experience frontend UI does not require MFA",
                },
                {
                    "id": "AwsSolutions-COG3",
                    "reason": "The fan experience frontend UI does not require AdvancedSecurityMode as it is a demo UI",
                },
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "CDK custom resource provider uses AWS Managed Policies",
                    "appliesTo": [
                        "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Cognito default authenticated role needs wildcard permissions to access the MRE API Gateway endpoints for GET, OPTIONS, and WebSocket connections",
                    "appliesTo": [
                        "Resource::arn:aws:execute-api:<AWS::Region>:<AWS::AccountId>:mre-dataplane-api-rest-id/*/GET/*",
                        "Resource::arn:aws:execute-api:<AWS::Region>:<AWS::AccountId>:mre-dataplane-api-rest-id/*/OPTIONS/*",
                        "Resource::arn:aws:execute-api:<AWS::Region>:<AWS::AccountId>:mre-dataplane-api-rest-id/*/@connections/*",
                        "Resource::arn:aws:execute-api:<AWS::Region>:<AWS::AccountId>:mre-default-api-gateway-rest-api-id/*/GET/*",
                        "Resource::arn:aws:execute-api:<AWS::Region>:<AWS::AccountId>:mre-default-api-gateway-rest-api-id/*/OPTIONS/*",
                        "Resource::arn:aws:execute-api:<AWS::Region>:<AWS::AccountId>:mre-default-api-gateway-rest-api-id/*/@connections/*"
                    ],
                },
            ],
        )