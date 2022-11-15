#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import os
import sys
from aws_cdk import (
    CfnOutput,
    Fn,
    Stack,
    aws_lambda as aws_lambda,
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
        self.program_table_arn = Fn.import_value("mre-program-table-arn")
        self.program_table_name = Fn.import_value("mre-program-table-name")
        self.event_table_arn = Fn.import_value("mre-event-table-arn")
        self.event_table_name = Fn.import_value("mre-event-table-name")
        self.profile_table_arn = Fn.import_value("mre-profile-table-arn")
        self.current_event_table_arn = Fn.import_value("mre-current-event-table-arn")
        
        # Get the Existing MRE EventBus as IEventBus
        self.event_bus = common.MreCdkCommon.get_event_bus(self)

        self.create_chalice_role()

    
    def create_chalice_role(self):

        # Chalice IAM Role
        self.chalice_role = iam.Role(
            self,
            "ChaliceRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE Event API Lambda function"
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
                    self.program_table_arn,
                    self.event_table_arn,
                    f"{self.event_table_arn}/index/*",
                    self.profile_table_arn,
                    self.current_event_table_arn
                ]
            )
        )

        # Chalice IAM Role: CloudWatch Alarms permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudwatch:PutMetricAlarm",
                    "cloudwatch:DeleteAlarms"
                ],
                resources=[
                    f"arn:aws:cloudwatch:*:*:alarm:AWS_MRE*"
                ]
            )
        )

        # Chalice IAM Role: S3 Read permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:Get*",
                    "s3:List*"
                ],
                resources=[
                    "*"
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

        # Chalice IAM Role: EventBridge permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "events:DescribeEventBus",
                    "events:PutEvents"
                ],
                resources=[
                    f"arn:aws:events:*:*:event-bus/{self.event_bus.event_bus_name}"
                ]
            )
        )

        # Chalice IAM Role: SQS permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sqs:SendMessage"
                ],
                resources=[
                    f"arn:aws:sqs:*:*:{Fn.import_value('mre-event-deletion-queue-name')}"
                ]
            )
        )

        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:CreateSecret",
                    "secretsmanager:UpdateSecret",
                    "secretsmanager:DeleteSecret",
                    "secretsmanager:TagResource"
                ],
                resources=[
                    "arn:aws:secretsmanager:*:*:secret:/MRE*"
                ]
            )
        )

        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:*BucketNotification*"
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
                    "PROGRAM_TABLE_NAME": self.program_table_name,
                    "EVENT_TABLE_NAME": self.event_table_name,
                    "EVENT_PAGINATION_INDEX": constants.EVENT_PAGINATION_INDEX,
                    "EVENT_PROGRAMID_INDEX": constants.EVENT_PROGRAMID_INDEX,
                    "EVENT_PROGRAM_INDEX": constants.EVENT_PROGRAM_INDEX,
                    "EVENT_CHANNEL_INDEX": constants.EVENT_CHANNEL_INDEX,
                    "EVENT_BYOB_NAME_INDEX": constants.EVENT_BYOB_NAME_INDEX,
                    "EB_EVENT_BUS_NAME": self.event_bus.event_bus_name,
                    "CURRENT_EVENTS_TABLE_NAME": Fn.import_value("mre-current-event-table-name"),
                    "PROFILE_TABLE_NAME": Fn.import_value("mre-profile-table-name"),
                    "MEDIASOURCE_S3_BUCKET": Fn.import_value("mre-media-source-bucket-name"),
                    "SQS_QUEUE_URL": Fn.import_value("mre-event-deletion-queue-name"),
                    "TRIGGER_LAMBDA_ARN": Fn.import_value("mre-trigger-workflow-lambda-arn")
                },
                "tags": {
                    "Project": "MRE"
                },
                "manage_iam_role": False,
                "iam_role_arn": self.chalice_role.role_arn
            }
        )

        CfnOutput(self, "mre-event-api-url", value=self.chalice.sam_template.get_output("EndpointURL").value, description="MRE Event API Url", export_name="mre-event-api-url" )
        