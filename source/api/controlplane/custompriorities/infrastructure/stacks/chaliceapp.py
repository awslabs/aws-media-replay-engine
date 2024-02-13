#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import os
import sys
from aws_cdk import (
    CfnOutput,
    Fn,
    Stack,
    aws_iam as iam
)
from chalice.cdk import Chalice
from cdk_nag import NagSuppressions

# Ask Python interpreter to search for modules in the topmost folder. This is required to access the shared.infrastructure.helpers module
sys.path.append('../../../../')

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')

class ChaliceApp(Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.custom_priorities_table_arn = Fn.import_value("mre-custom-priorities-table-arn")
        self.custom_priorities_table_name = Fn.import_value("mre-custom-priorities-table-name")
        
        self.create_chalice_role()

    
    def create_chalice_role(self):

        # Chalice IAM Role
        self.chalice_role = iam.Role(
            self,
            "ChaliceRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE Custom Priorities API Lambda function"
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
                    "dynamodb:Query",
                    "dynamodb:GetItem",
                    "dynamodb:Scan",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem"
                ],
                resources=[
                    self.custom_priorities_table_arn
                ]
            )
        )

        self.chalice = Chalice(
            self,
            "ChaliceApp",
            source_dir=RUNTIME_SOURCE_DIR,
            stage_config={
                "environment_variables": {
                    "CUSTOM_PRIORITIES_TABLE_NAME": self.custom_priorities_table_name
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
                    "reason": "Chalice IAM role policy requires wildcard permissions for CloudWatch logging",
                    "appliesTo": [
                        "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:*"
                    ]
                }
            ]
        )

        CfnOutput(self, "mre-custompriorities-api-url", value=self.chalice.sam_template.get_output("EndpointURL").value, description="MRE Custom Priorities API Url", export_name="mre-custompriorities-api-url" )
        