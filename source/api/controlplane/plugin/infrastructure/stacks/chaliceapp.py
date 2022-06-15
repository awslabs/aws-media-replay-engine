#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import os
import sys
from aws_cdk import (
    Fn,
    CfnOutput,
    Stack,
    aws_iam as iam
)
from chalice.cdk import Chalice

# Ask Python interpreter to search for modules in the topmost folder. This is required to access the shared.infrastructure.helpers module
sys.path.append('../../../../')

from shared.infrastructure.helpers import common
from shared.infrastructure.helpers import constants

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')


class ChaliceApp(Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.model_table_arn = Fn.import_value("mre-model-table-arn")
        self.model_table_name = Fn.import_value("mre-model-table-name")
        self.plugin_table_name = Fn.import_value("mre-plugin-table-name")
        self.plugin_table_arn = Fn.import_value("mre-plugin-table-arn")
        
        # Get the Existing MRE EventBus as IEventBus
        self.event_bus = common.MreCdkCommon.get_event_bus(self)

        self.create_chalice_role()

    
    def create_chalice_role(self):

        # Chalice IAM Role
        self.chalice_role = iam.Role(
            self,
            "ChaliceRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE Plugin API Lambda function"
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
                    self.model_table_arn,
                    f"{self.model_table_arn}/index/*",
                    self.plugin_table_arn,
                    f"{self.plugin_table_arn}/index/*",
                ]
            )
        )

        self.chalice = Chalice(
            self,
            "ChaliceApp",
            source_dir=RUNTIME_SOURCE_DIR,
            stage_config={
                "environment_variables": {
                    "MODEL_TABLE_NAME": self.model_table_name,
                    "PLUGIN_TABLE_NAME": self.plugin_table_name,
                    "FRAMEWORK_VERSION": constants.FRAMEWORK_VERSION,
                    "PLUGIN_VERSION_INDEX": constants.PLUGIN_VERSION_INDEX,
                    "PLUGIN_NAME_INDEX": constants.PLUGIN_NAME_INDEX
                },
                "tags": {
                    "Project": "MRE"
                },
                "manage_iam_role": False,
                "iam_role_arn": self.chalice_role.role_arn
            }
        )


        CfnOutput(self, "mre-plugin-api-url", value=self.chalice.sam_template.get_output("EndpointURL").value, description="MRE Plugin API Url", export_name="mre-plugin-api-url" )
        