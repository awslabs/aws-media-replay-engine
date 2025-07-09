#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import os
import sys
from aws_cdk import CfnOutput, Fn, Stack, aws_lambda as aws_lambda, aws_iam as iam
from chalice.cdk import Chalice
from cdk_nag import NagSuppressions

# Ask Python interpreter to search for modules in the topmost folder. This is required to access the shared.infrastructure.helpers module
sys.path.append("../../../../")

from shared.infrastructure.helpers import common, api_logging_construct
from shared.infrastructure.helpers import constants

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, "runtime"
)


class ChaliceApp(Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.program_table_arn = Fn.import_value("mre-program-table-arn")
        self.program_table_name = Fn.import_value("mre-program-table-name")
        self.event_table_arn = Fn.import_value("mre-event-table-arn")
        self.event_table_name = Fn.import_value("mre-event-table-name")
        self.profile_table_arn = Fn.import_value("mre-profile-table-arn")
        self.current_event_table_arn = Fn.import_value("mre-current-event-table-arn")
        self.metadata_table_arn = Fn.import_value("mre-metadata-table-arn")
        self.metadata_table_name = Fn.import_value("mre-metadata-table-name")
        self.cloudfront_domain_name = Fn.import_value(
            "mre-media-output-distro-domain-name"
        )
        self.mre_api_gateway_logging_role_arn = Fn.import_value("mre-api-gateway-logging-role-arn")
        self.powertools_layer = common.MreCdkCommon.get_powertools_layer_from_arn(self)

        # Get the Existing MRE EventBus as IEventBus
        self.event_bus = common.MreCdkCommon.get_event_bus(self)
        self.eb_schedule_role_arn = common.MreCdkCommon.get_eb_schedule_role_arn(self)

        self.create_medialive_access_role()
        self.create_chalice_role()

        # Enable API Gateway logging through Custom Resources
        api_logging_construct.ApiGatewayLogging(
            self, 
            "EventApiGatewayLogging",
            stack_name=self.stack_name,
            api_gateway_logging_role_arn=self.mre_api_gateway_logging_role_arn,
            rate_limit = 25, # 25 requests per second
            burst_limit = 15 # up to 15 concurrent requests
        )

        

    def create_medialive_access_role(self):
        # Create a MediaLive Access Role
        self.medialive_access_role = iam.Role(
            self,
            "MediaLiveAccessRole",
            assumed_by=iam.ServicePrincipal(service="medialive.amazonaws.com"),
            description="Role used by the AWS Elemental MediaLive service to access other AWS resources",
        )

        # MediaLive Access Role: SSM permissions
        self.medialive_access_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:DescribeParameters",
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "ssm:GetParametersByPath",
                    "ssm:GetParameterHistory",
                ],
                resources=[
                    f"arn:aws:ssm:{Stack.of(self).region}:{Stack.of(self).account}:parameter/*"
                ],
            )
        )

        # MediaLive Access Role: CloudWatch Logs permissions
        self.medialive_access_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogStreams",
                    "logs:DescribeLogGroups",
                ],
                resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:*"
                ],
            )
        )

        # MediaLive Access Role: S3 permissions
        self.medialive_access_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:ListBucket",
                    "s3:PutObject",
                    "s3:GetObject",
                    "s3:DeleteObject",
                ],
                resources=["*"],
            )
        )

        # MediaLive Access Role: MediaStore permissions
        self.medialive_access_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "mediastore:ListContainers",
                    "mediastore:PutObject",
                    "mediastore:GetObject",
                    "mediastore:DeleteObject",
                    "mediastore:DescribeObject",
                ],
                resources=[
                    f"arn:aws:mediastore:{Stack.of(self).region}:{Stack.of(self).account}:container/*",
                    f"arn:aws:mediastore:{Stack.of(self).region}:{Stack.of(self).account}:container/*/*",
                ],
            )
        )

        # MediaLive Access Role: MediaConnect permissions
        self.medialive_access_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "mediaconnect:ManagedDescribeFlow",
                    "mediaconnect:ManagedAddOutput",
                    "mediaconnect:ManagedRemoveOutput",
                ],
                resources=["*"],
            )
        )

        # MediaLive Access Role: EC2 permissions
        self.medialive_access_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ec2:describeSubnets",
                    "ec2:describeNetworkInterfaces",
                    "ec2:createNetworkInterface",
                    "ec2:createNetworkInterfacePermission",
                    "ec2:deleteNetworkInterface",
                    "ec2:deleteNetworkInterfacePermission",
                    "ec2:describeSecurityGroups",
                    "ec2:describeAddresses",
                    "ec2:associateAddress",
                ],
                resources=["*"],
            )
        )

        # MediaLive Access Role: MediaPackage permissions
        self.medialive_access_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["mediapackage:DescribeChannel", "mediapackagev2:PutObject"],
                resources=["*"],
            )
        )

        # MediaLive Access Role: KMS permissions
        self.medialive_access_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["kms:GenerateDataKey"],
                resources=["*"],
            )
        )

    def create_chalice_role(self):

        # Chalice IAM Role
        self.chalice_role = iam.Role(
            self,
            "ChaliceRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE Event API Lambda function",
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
                resources=[
                    self.program_table_arn,
                    self.event_table_arn,
                    f"{self.event_table_arn}/index/*",
                    self.profile_table_arn,
                    self.current_event_table_arn,
                    self.metadata_table_arn,
                    f"{self.metadata_table_arn}/index/*",
                ],
            )
        )

        # Chalice IAM Role: CloudWatch Alarms permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cloudwatch:PutMetricAlarm", "cloudwatch:DeleteAlarms"],
                resources=[
                    f"arn:aws:cloudwatch:{Stack.of(self).region}:{Stack.of(self).account}:alarm:AWS_MRE*"
                ],
            )
        )

        # Chalice IAM Role: S3 Read permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectVersion",
                    "s3:GetObjectAttributes",
                    "s3:ListBucket",
                ],
                resources=["arn:aws:s3:::*", "arn:aws:s3:::*/*"],
            )
        )
        # To enable event video preview in the Live News Segmenter
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:PutObject",
                ],
                resources=["arn:aws:s3:::*/*.m3u8"],
            )
        )

        # Chalice IAM Role: MediaLive permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "medialive:DescribeChannel",
                    "medialive:CreateInput",
                    "medialive:CreateChannel",
                    "medialive:StartChannel",
                    "medialive:UpdateChannel",
                ],
                resources=[
                    f"arn:aws:medialive:{Stack.of(self).region}:{Stack.of(self).account}:channel:*",
                    f"arn:aws:medialive:{Stack.of(self).region}:{Stack.of(self).account}:input:*",
                ],
            )
        )

        # Chalice IAM Role: EventBridge permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["events:DescribeEventBus", "events:PutEvents"],
                resources=[
                    f"arn:aws:events:{Stack.of(self).region}:{Stack.of(self).account}:event-bus/{self.event_bus.event_bus_name}"
                ],
            )
        )

        # Chalice IAM Role: SQS permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sqs:SendMessage"],
                resources=[
                    f"arn:aws:sqs:{Stack.of(self).region}:{Stack.of(self).account}:{Fn.import_value('mre-event-deletion-queue-name')}"
                ],
            )
        )

        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:CreateSecret",
                    "secretsmanager:UpdateSecret",
                    "secretsmanager:DeleteSecret",
                    "secretsmanager:TagResource",
                    "secretsmanager:GetSecretValue",
                ],
                resources=[
                    f"arn:aws:secretsmanager:{Stack.of(self).region}:{Stack.of(self).account}:secret:/MRE*",
                    f"arn:aws:secretsmanager:{Stack.of(self).region}:{Stack.of(self).account}:secret:MRE*",
                ],
            )
        )

        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetBucketNotification", "s3:PutBucketNotification"],
                resources=["arn:aws:s3:::*"],
            )
        )

        # Chalice IAM Role: Schedule permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "scheduler:CreateSchedule",
                    "scheduler:UpdateSchedule",
                    "scheduler:DeleteSchedule",
                ],
                resources=[
                    f"arn:aws:scheduler:{Stack.of(self).region}:{Stack.of(self).account}:schedule/default/mre*"
                ],
            )
        )

        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["iam:PassRole"],
                resources=[
                    self.eb_schedule_role_arn,
                    self.medialive_access_role.role_arn,
                ],
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
                    "EB_EVENT_BUS_ARN": self.event_bus.event_bus_arn,
                    "CURRENT_EVENTS_TABLE_NAME": Fn.import_value(
                        "mre-current-event-table-name"
                    ),
                    "PROFILE_TABLE_NAME": Fn.import_value("mre-profile-table-name"),
                    "MEDIASOURCE_S3_BUCKET": Fn.import_value(
                        "mre-media-source-bucket-name"
                    ),
                    "SQS_QUEUE_URL": Fn.import_value("mre-event-deletion-queue-name"),
                    "TRIGGER_LAMBDA_ARN": Fn.import_value(
                        "mre-trigger-workflow-lambda-arn"
                    ),
                    "EB_SCHEDULE_ROLE_ARN": self.eb_schedule_role_arn,
                    "METADATA_TABLE_NAME": self.metadata_table_name,
                    "MEDIALIVE_ACCESS_ROLE": self.medialive_access_role.role_arn,
                    "CLOUDFRONT_DOMAIN_NAME": self.cloudfront_domain_name,
                    "HLS_STREAMING_SIGNED_URL_EXPIRATION_HRS": "48",
                },
                "tags": {"Project": "MRE"},
                "manage_iam_role": False,
                "iam_role_arn": self.chalice_role.role_arn,
                "layers": [self.powertools_layer.layer_version_arn]
            },
        )

        # cdk-nag suppressions
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "S3 bucket operations require wildcard permissions for bucket notifications and object access",
                    "appliesTo": [
                        "Action::s3:GetBucketNotification",
                        "Action::s3:PutBucketNotification",
                        "Resource::arn:aws:s3:::*",
                        "Resource::arn:aws:s3:::*/*",
                        "Resource::arn:aws:s3:::*/*.m3u8",
                    ],
                },
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
                    "reason": "DynamoDB GSI access pattern requires index wildcards",
                    "appliesTo": [{"regex": "/^Resource::.*/index/\\*$/"}],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "MediaLive channel, input, & log management requires wildcards",
                    "appliesTo": [
                        "Resource::arn:aws:medialive:<AWS::Region>:<AWS::AccountId>:channel:*",
                        "Resource::arn:aws:medialive:<AWS::Region>:<AWS::AccountId>:input:*",
                        "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:*",
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "CloudWatch alarms for MRE resources",
                    "appliesTo": [
                        "Resource::arn:aws:cloudwatch:<AWS::Region>:<AWS::AccountId>:alarm:AWS_MRE*"
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "EventBridge scheduler access for MRE schedules",
                    "appliesTo": [
                        "Resource::arn:aws:scheduler:<AWS::Region>:<AWS::AccountId>:schedule/default/mre*"
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Secrets Manager access for MRE secrets",
                    "appliesTo": [
                        "Resource::arn:aws:secretsmanager:<AWS::Region>:<AWS::AccountId>:secret:/MRE*",
                        "Resource::arn:aws:secretsmanager:<AWS::Region>:<AWS::AccountId>:secret:MRE*",
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
                    "appliesTo": ["Resource::<EventApiGatewayLoggingEnableLoggingHandler33B0CF1B.Arn>:*"]
                }
            ],
        )

        NagSuppressions.add_resource_suppressions(
            self.medialive_access_role,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Required MediaLive IAM permissions for trusted entity access as documented in AWS MediaLive user guide )https://docs.aws.amazon.com/medialive/latest/ug/trusted-entity-requirements.html)",
                    "appliesTo": [
                        "Resource::*",
                        "Action::s3:Get*",
                        "Action::s3:Put*",
                        "Action::s3:List*",
                        "Resource::arn:aws:ssm:<AWS::Region>:<AWS::AccountId>:parameter/*",
                        "Resource::arn:aws:mediastore:<AWS::Region>:<AWS::AccountId>:container/*/*",
                        "Resource::arn:aws:mediastore:<AWS::Region>:<AWS::AccountId>:container/*",
                    ],
                },
            ],
            True,
        )
        CfnOutput(
            self,
            "mre-event-api-url",
            value=self.chalice.sam_template.get_output("EndpointURL").value,
            description="MRE Event API Url",
            export_name="mre-event-api-url",
        )
