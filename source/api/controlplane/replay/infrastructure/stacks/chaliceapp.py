#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import sys

from aws_cdk import CfnOutput, Fn, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as ddb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secret_mgr
from aws_cdk import aws_ssm as ssm
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

        # Get the Existing MRE EventBus as IEventBus
        self.event_bus = common.MreCdkCommon.get_event_bus(self)

        # TBD
        self.plugin_table_arn = Fn.import_value("mre-plugin-table-arn")
        self.profile_table_arn = Fn.import_value("mre-profile-table-arn")
        self.event_table_arn = Fn.import_value("mre-event-table-arn")
        self.plugin_table_name = Fn.import_value("mre-plugin-table-name")
        self.profile_table_name = Fn.import_value("mre-profile-table-name")
        self.event_table_name = Fn.import_value("mre-event-table-name")
        self.media_output_domain_name = Fn.import_value(
            "mre-media-output-distro-domain-name"
        )
        self.media_output_bucket_name = Fn.import_value("mre-media-output-bucket-name")
        self.mre_api_gateway_logging_role_arn = Fn.import_value("mre-api-gateway-logging-role-arn")

        self.create_cloudfront_secrets()
        self.create_replay_dynamodb_table()
        self.create_transitions_config_table()

        self.powertools_layer = common.MreCdkCommon.get_powertools_layer_from_arn(self)

        self.create_chalice_role()

        # Enable API Gateway logging through Custom Resources
        api_logging_construct.ApiGatewayLogging(
            self, 
            "ReplayApi",
            stack_name=self.stack_name,
            api_gateway_logging_role_arn=self.mre_api_gateway_logging_role_arn,
            rate_limit = 25, # 25 requests per second
            burst_limit = 15 # up to 15 concurrent requests
        )

    def create_transitions_config_table(self):
        # Transitions Config Table
        self.transitions_config_table = ddb.Table(
            self,
            "TransitionsConfig",
            partition_key=ddb.Attribute(name="Name", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        CfnOutput(
            self,
            "mre-transitions-config-table-arn",
            value=self.transitions_config_table.table_arn,
            description="Arn of Transitions Config table",
            export_name="mre-transitions-config-table-arn",
        )
        CfnOutput(
            self,
            "mre-transitions-config-table-name",
            value=self.transitions_config_table.table_name,
            description="Name of Transitions Config table",
            export_name="mre-transitions-config-table-name",
        )

        # Required for Hydrating the table with default Replay Transition data
        # Data is pushed from init-amplify.py
        ssm.StringParameter(
            self,
            "MRETransitionConfigTable",
            string_value=self.transitions_config_table.table_name,
            parameter_name="/MRE/ControlPlane/TransitionConfigTableName",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the AWS MRE Transition Config Table Name",
        )

    def create_replay_dynamodb_table(self):
        # ReplayRequest Table
        self.replayrequest_table = ddb.Table(
            self,
            "ReplayRequest",
            partition_key=ddb.Attribute(name="PK", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="ReplayId", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        CfnOutput(
            self,
            "mre-replayrequest-table-arn",
            value=self.replayrequest_table.table_arn,
            description="Arn of the MRE ReplayRequest table",
            export_name="mre-replayrequest-table-arn",
        )
        CfnOutput(
            self,
            "mre-replayrequest-table-name",
            value=self.replayrequest_table.table_name,
            description="Name of the MRE ReplayRequest table",
            export_name="mre-replayrequest-table-name",
        )

    def create_cloudfront_secrets(self):
        self.secret_cloudfront_private_key = secret_mgr.Secret(
            self,
            "MRE_CLOUDFRONT_COOKIE_PRIVATE_KEY",
            secret_name="mre_cloudfront_cookie_private_key",
        )

        self.secret_cloudfront_key_pair_id = secret_mgr.Secret(
            self, "MRE_CLOUDFRONT_KEY_PAIR_ID", secret_name="mre_cloudfront_key_pair_id"
        )

    def create_chalice_role(self):
        # Chalice IAM Role
        self.chalice_role = iam.Role(
            self,
            "ChaliceRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE Replay API Lambda function",
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
                    self.replayrequest_table.table_arn,
                    self.transitions_config_table.table_arn,
                    self.plugin_table_arn,
                    self.profile_table_arn,
                    self.event_table_arn,
                ],
            )
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
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:*"
                ],
            )
        )

        # Chalice IAM Role: S3 Read permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject", "s3:ListBucket", "s3:PutObject"],
                resources=[f"arn:aws:s3:::aws-mre*/*"],
            )
        )

        # Chalice IAM Role: Secrets Manager permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=[
                    self.secret_cloudfront_private_key.secret_arn,
                    self.secret_cloudfront_key_pair_id.secret_arn,
                    f"arn:aws:secretsmanager:{Stack.of(self).region}:{Stack.of(self).account}:secret:MRE_event_hls_streaming_private_key-*",
                    f"arn:aws:secretsmanager:{Stack.of(self).region}:{Stack.of(self).account}:secret:MRE_event_hls_streaming_public_key-*",
                    f"arn:aws:secretsmanager:{Stack.of(self).region}:{Stack.of(self).account}:secret:MRE_event_hls_streaming_private_key_pair_id-*",
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
                ],
                resources=["arn:aws:secretsmanager:*:*:secret:/MRE*"],
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

        self.secret_cloudfront_private_key.grant_read(self.chalice_role)
        self.secret_cloudfront_key_pair_id.grant_read(self.chalice_role)

        self.chalice = Chalice(
            self,
            "ChaliceApp",
            source_dir=RUNTIME_SOURCE_DIR,
            stage_config={
                "environment_variables": {
                    "PLUGIN_TABLE_NAME": self.plugin_table_name,
                    "PROFILE_TABLE_NAME": self.profile_table_name,
                    "EVENT_TABLE_NAME": self.event_table_name,
                    "REPLAY_REQUEST_TABLE_NAME": self.replayrequest_table.table_name,
                    "EB_EVENT_BUS_NAME": self.event_bus.event_bus_name,
                    "HLS_HS256_API_AUTH_SECRET_KEY_NAME": "mre_hsa_api_auth_secret",
                    "CLOUDFRONT_COOKIE_PRIVATE_KEY_NAME": "mre_cloudfront_cookie_private_key",
                    "CLOUDFRONT_COOKIE_KEY_PAIR_ID_NAME": "mre_cloudfront_key_pair_id",
                    "HLS_STREAM_CLOUDFRONT_DISTRO": self.media_output_domain_name,
                    "TRANSITION_CLIP_S3_BUCKET": Fn.import_value(
                        "mre-transition-clips-bucket-name"
                    ),
                    "TRANSITIONS_CONFIG_TABLE_NAME": self.transitions_config_table.table_name,
                    "MEDIA_OUTPUT_BUCKET_NAME": self.media_output_bucket_name,
                    "HLS_STREAMING_SIGNED_URL_EXPIRATION_HRS": "48",
                },
                "tags": {"Project": "MRE"},
                "manage_iam_role": False,
                "iam_role_arn": self.chalice_role.role_arn,
                "layers": [self.powertools_layer.layer_version_arn],
            },
        )

        CfnOutput(
            self,
            "mre-replay-api-url",
            value=self.chalice.sam_template.get_output("EndpointURL").value,
            description="MRE Replay API Url",
            export_name="mre-replay-api-url",
        )

        # cdk-nag suppressions
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-DDB3",
                    "reason": "DynamoDB Point-in-time Recovery not required in the default deployment mode. Customers can turn it on if required",
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Lambda logging requires access to CloudWatch log groups",
                    "appliesTo": [
                        f"Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/lambda/{Stack.of(self).stack_name}-*",
                        "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:*",
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Chalice role policy requires wildcard permissions for S3 MRE buckets",
                    "appliesTo": ["Resource::arn:aws:s3:::aws-mre*/*"],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Chalice role policy requires wildcard permissions for MRE secrets",
                    "appliesTo": ["Resource::arn:aws:secretsmanager:*:*:secret:/MRE*"],
                },
                {
                    "id": "AwsSolutions-SMG4",
                    "reason": "By default no Secrets are created although the keys are created. Customers have to define these if the feature is being used.",
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
                    "id": "AwsSolutions-IAM5",
                    "reason": "Chalice IAM role policy requires wildcard permissions for Secrets Manager",
                    "appliesTo": [
                        "Resource::arn:aws:secretsmanager:<AWS::Region>:<AWS::AccountId>:secret:MRE_event_hls_streaming_private_key_pair_id-*",
                        "Resource::arn:aws:secretsmanager:<AWS::Region>:<AWS::AccountId>:secret:MRE_event_hls_streaming_private_key-*",
                        "Resource::arn:aws:secretsmanager:<AWS::Region>:<AWS::AccountId>:secret:MRE_event_hls_streaming_public_key-*",
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
                    "appliesTo": ["Resource::<ReplayApiEnableLoggingHandler11C33B7B.Arn>:*"]
                }
            ],
        )
