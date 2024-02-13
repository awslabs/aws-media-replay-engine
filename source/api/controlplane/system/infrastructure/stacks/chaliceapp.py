#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import os
import sys
from aws_cdk import (
    Stack,
    Fn,
    CfnOutput,
    aws_iam as iam,
    aws_ssm as ssm
)
from chalice.cdk import Chalice
from cdk_nag import NagSuppressions

# Ask Python interpreter to search for modules in the topmost folder. This is required to access the shared.infrastructure.helpers module
sys.path.append('../../../../')

import shared.infrastructure.helpers.constants as constants


RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')

class ChaliceApp(Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.system_table_arn = ssm.StringParameter.value_for_string_parameter(
            self,
            parameter_name="/MRE/ControlPlane/SystemTableArn"
        )
        self.system_table_name = ssm.StringParameter.value_for_string_parameter(
            self,
            parameter_name="/MRE/ControlPlane/SystemTableName"
        )
        
        self.create_chalice_role()

    
    def create_chalice_role(self):

        # Chalice IAM Role
        self.chalice_role = iam.Role(
            self,
            "ChaliceRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE System API Lambda function"
        )

        # Chalice IAM Role: CloudWatch Logs permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:*"
                ]
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
                    "dynamodb:DeleteItem"
                ],
                resources=[
                    self.system_table_arn
                ]
            )
        )

        # Chalice IAM Role: MediaLive permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "medialive:List*",
                    "medialive:Describe*",
                    "medialive:StartChannel",
                    "medialive:UpdateChannel"
                ],
                resources=[
                    "*"
                ]
            )
        )

        # Chalice IAM Role: MediaTailor permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "mediatailor:List*",
                    "mediatailor:Describe*"
                ],
                resources=[
                    "*"
                ]
            )
        )

        # Chalice IAM Role: S3 permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:List*Bucket*",
                    "s3:GetBucketLocation"
                ],
                resources=[
                    "*"
                ]
            )
        )

        self.chalice = Chalice(
            self,
            "ChaliceApp",
            source_dir=RUNTIME_SOURCE_DIR,
            stage_config={
                "environment_variables": {
                    "FRAMEWORK_VERSION": constants.FRAMEWORK_VERSION,
                    "SYSTEM_TABLE_NAME": self.system_table_name
                },
                "tags": {
                    "Project": "MRE"
                },
                "manage_iam_role": False,
                "iam_role_arn": self.chalice_role.role_arn
            }
        )

        # cdk-nag suppressions
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Chalice IAM role policy requires wildcard permissions for CloudWatch logging, MediaLive, MediaTailor and S3",
                    "appliesTo": [
                        "Action::medialive:List*",
                        "Action::medialive:Describe*",
                        "Action::mediatailor:List*",
                        "Action::mediatailor:Describe*",
                        "Action::s3:List*Bucket*",
                        "Resource::*",
                        "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:*"
                    ]
                }
            ]
        )

        CfnOutput(self, "mre-system-api-url", value=self.chalice.sam_template.get_output("EndpointURL").value, description="MRE System API Url", export_name="mre-system-api-url" )
        