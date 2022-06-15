#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import os
import sys
from aws_cdk import (
    Stack,
    Fn,
    CfnOutput,
    aws_iam as iam
)
from chalice.cdk import Chalice

# Ask Python interpreter to search for modules in the topmost folder. This is required to access the shared.infrastructure.helpers module
sys.path.append('../../../../')

import shared.infrastructure.helpers.constants as constants


RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')

class ChaliceApp(Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.system_table_arn = Fn.import_value("mre-system-table-arn")
        self.system_table_name = Fn.import_value("mre-system-table-name")
        
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
                    "arn:*:logs:*:*:*"
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


        CfnOutput(self, "mre-system-api-url", value=self.chalice.sam_template.get_output("EndpointURL").value, description="MRE System API Url", export_name="mre-system-api-url" )
        