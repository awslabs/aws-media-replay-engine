#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import os
import sys

from aws_cdk import CfnOutput, Fn, Stack
from aws_cdk import aws_iam as iam
from cdk_nag import NagSuppressions
from chalice.cdk import Chalice

# Ask Python interpreter to search for modules in the topmost folder. This is required to access the shared.infrastructure.helpers module
sys.path.append("../../../../")

from shared.infrastructure.helpers import common, api_logging_construct

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, "runtime"
)


class ChaliceApp(Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.program_table_arn = Fn.import_value("mre-program-table-arn")
        self.program_table_name = Fn.import_value("mre-program-table-name")

        self.powertools_layer = common.MreCdkCommon.get_powertools_layer_from_arn(self)
        self.mre_api_gateway_logging_role_arn = Fn.import_value("mre-api-gateway-logging-role-arn")

        self.create_chalice_role()
        # Enable API Gateway logging through Custom Resources
        api_logging_construct.ApiGatewayLogging(
            self, 
            "ProgramApi",
            stack_name=self.stack_name,
            api_gateway_logging_role_arn=self.mre_api_gateway_logging_role_arn,
            rate_limit = 25, # 25 requests per second
            burst_limit = 15 # up to 15 concurrent requests
        )

       
    def create_chalice_role(self):

        # Chalice IAM Role
        self.chalice_role = iam.Role(
            self,
            "ChaliceRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE Workflow API Lambda function",
        )

        # Chalice IAM Role: CloudWatch Logs permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/lambda/{Stack.of(self).stack_name}-*",
                ],
            )
        )
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                ],
                resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group*"
                ],
            )
        )

        # Chalice IAM Role: DynamoDB permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:BatchGetItem",
                    "dynamodb:GetRecords",
                    "dynamodb:GetShardIterator",
                    "dynamodb:Query",
                    "dynamodb:GetItem",
                    "dynamodb:Scan",
                    "dynamodb:ConditionCheckItem",
                    "dynamodb:BatchWriteItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                ],
                resources=[self.program_table_arn],
            )
        )

        self.chalice = Chalice(
            self,
            "ChaliceApp",
            source_dir=RUNTIME_SOURCE_DIR,
            stage_config={
                "environment_variables": {
                    "PROGRAM_TABLE_NAME": self.program_table_name
                },
                "tags": {"Project": "MRE"},
                "manage_iam_role": False,
                "iam_role_arn": self.chalice_role.role_arn,
                "layers": [
                    self.powertools_layer.layer_version_arn,
                ],
            },
        )

        # cdk-nag suppressions
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Lambda logging requires access to CloudWatch log groups",
                    "appliesTo": [
                        f"Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/lambda/{Stack.of(self).stack_name}-*",
                        "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group*",
                    ],
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
                    "appliesTo": ["Resource::<ProgramApiEnableLoggingHandler9930FDE8.Arn>:*"]
                }
            ],
        )

        CfnOutput(
            self,
            "mre-program-api-url",
            value=self.chalice.sam_template.get_output("EndpointURL").value,
            description="MRE Program API Url",
            export_name="mre-program-api-url",
        )
