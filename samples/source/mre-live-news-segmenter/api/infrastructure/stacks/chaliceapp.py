# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os
import sys
from aws_cdk import (
    Fn,
    RemovalPolicy,
    Stack,
    aws_dynamodb as ddb,
    aws_iam as iam,
    aws_ssm as ssm,
    CfnOutput
)
from chalice.cdk import Chalice
from cdk_nag import NagSuppressions

sys.path.append("../")
from stacks.api_logging_construct import ApiGatewayLogging

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, "runtime"
)

class ChaliceApp(Stack):
    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.plugin_result_table_arn = Fn.import_value("mre-plugin-result-table-arn")
        self.plugin_result_table_name = Fn.import_value("mre-plugin-result-table-name")

        self.event_table_arn = Fn.import_value("mre-event-table-arn")
        self.event_table_name = Fn.import_value("mre-event-table-name")

        self.profile_table_arn = Fn.import_value("mre-profile-table-arn")
        self.profile_table_name = Fn.import_value("mre-profile-table-name")

        self.mre_api_gateway_logging_role_arn = Fn.import_value("mre-api-gateway-logging-role-arn")

        # Enable API Gateway logging through Custom Resources
        ApiGatewayLogging(
            self, 
            "LiveNewsApi",
            stack_name=self.stack_name,
            api_gateway_logging_role_arn=self.mre_api_gateway_logging_role_arn,
            rate_limit=25,
            burst_limit=15
        )
        # Define the User Favorites table
        self.user_favorites_table = ddb.Table(
            self,
            "UserFavorites",
            partition_key=ddb.Attribute(
                name="program-event-user", type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(name="start", type=ddb.AttributeType.NUMBER),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        # Chalice IAM Role
        self.chalice_role = iam.Role(
            self,
            "ChaliceRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE Live News Segmenter Chalice Lambda function",
        )

        # Chalice IAM Role: DynamoDB permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:Query",
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:PartiQLSelect",
                ],
                resources=[
                    self.plugin_result_table_arn,
                    f"{self.plugin_result_table_arn}/index/*",
                    self.event_table_arn,
                    f"{self.event_table_arn}/index/*",
                    self.profile_table_arn,
                    self.user_favorites_table.table_arn,
                ],
            )
        )

        # Chalice IAM Role: S3 permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject"],
                resources=["arn:aws:s3:::*mremediaoutputbucket*"],
            )
        )

        # Chalice IAM Role: CloudWatch Logs permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:CreateLogGroup",
                ],
                 resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:*"
                ],
            )
        )

        self.chalice = Chalice(
            self,
            "ChaliceApp",
            source_dir=RUNTIME_SOURCE_DIR,
            stage_config={
                "environment_variables": {
                    "PLUGIN_RESULT_TABLE_NAME": self.plugin_result_table_name,
                    "EVENT_TABLE_NAME": self.event_table_name,
                    "PROFILE_TABLE_NAME": self.profile_table_name,
                    "USER_FAVORITES_TABLE_NAME": self.user_favorites_table.table_name,
                },
                "tags": {"Project": "MRE Live News Segmenter"},
                "manage_iam_role": False,
                "iam_role_arn": self.chalice_role.role_arn,
                "lambda_memory_size": 512,
            },
        )

        # cdk-nag suppressions
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-DDB3",
                    "reason": "DynamoDB Point-in-time Recovery not required as the data stored is non-critical and can be recreated",
                },
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "CDK custom resource provider uses AWS Managed Policies",
                    "appliesTo": [
                        "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                    ],
                },
                {
                    "id": "AwsSolutions-S1",
                    "reason": "Logging can be enabled if required in production environments",
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "MRE internal lambda IAM role policies require wildcard permissions for CloudWatch and DynamoDB",
                    "appliesTo": [
                        "Action::s3:GetObject",
                        "Resource::arn:aws:s3:::*mremediaoutputbucket*",
                        "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:*",
                        {"regex": "/^Resource::<.*.+Arn>:\\*$/"},
                        {"regex": "/^Resource::.*/index/\\*$/"},
                    ],
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "MRE internal lambda functions do not require the latest runtime version as their dependencies have been tested only on Python 3.11",
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Chalice IAM role policy requires wildcard permissions for CloudWatch logging",
                    "appliesTo": [
                        "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group*",
                        f"Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/lambda/{Stack.of(self).stack_name}-*",
                        "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/lambda/*"
                    ],
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "MRE internal lambda functions do not require the latest runtime version as their dependencies have been tested only on Python 3.11",
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "API Gateway permissions require access to all APIs to find the one created by Chalice. This only runs during deployment.",
                    "appliesTo": ["Resource::*"]
                },
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AWS Lambda Basic Execution Role is required for Lambda function logging and is appropriately scoped.",
                    "appliesTo": ["Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Custom resource provider needs to invoke the target Lambda function.",
                    "appliesTo": ["Resource::<EventApiGatewayLoggingEnableLoggingHandler33B0CF1B.Arn>:*"]
                }
            ],
        )

        # Store the API Gateway endpoint output of Chalice in SSM Parameter Store
        ssm.StringParameter(
            self,
            "MRELiveNewsSegmenterParam",
            string_value=self.chalice.sam_template.get_output("EndpointURL").value,
            parameter_name="/MRE/Samples/LiveNewsSegmenter/EndpointURL",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the AWS MRE Live News Segmenter API Endpoint URL",
        )


        rest_api = self.chalice.sam_template.get_resource("RestAPI")

        CfnOutput(
            self,
            "mre-live-news-segmenter-api-id",
            value=rest_api.ref,  # This gives you the API ID
            description="MRE Live news segmenter REST API ID",
            export_name="mre-live-news-segmenter-rest-api-id",
        )