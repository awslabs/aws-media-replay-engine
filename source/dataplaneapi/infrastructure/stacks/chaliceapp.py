#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os

from aws_cdk import (
    core as cdk,
    aws_dynamodb as ddb,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_lambda_event_sources as _lambda_es,
    aws_s3 as s3,
    aws_sqs as sqs,
    aws_ssm as ssm
)
from chalice.cdk import Chalice

CHUNK_STARTPTS_INDEX = "StartPts-index"
PROGRAM_EVENT_INDEX  = "ProgramEvent_Start-index"
FRAME_PROGRAM_EVENT_INDEX = "ProgramEvent-index"
CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_TRACK_INDEX  = "ProgramEventTrack-index"
CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_CLASSIFIER_START_INDEX = "ProgramEventClassifierStart-index"

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')


class ChaliceApp(cdk.Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Frame Table
        self.frame_table = ddb.Table(
            self,
            "Frame",
            partition_key=ddb.Attribute(
                name="Id",
                type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(
                name="FrameNumber",
                type=ddb.AttributeType.NUMBER
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        # Frame Table: ProgramEvent GSI
        self.frame_table.add_global_secondary_index(
            index_name=FRAME_PROGRAM_EVENT_INDEX,
            partition_key=ddb.Attribute(
                name="ProgramEvent",
                type=ddb.AttributeType.STRING
            ),
            projection_type=ddb.ProjectionType.KEYS_ONLY
        )

        # Chunk Table
        self.chunk_table = ddb.Table(
            self,
            "Chunk",
            partition_key=ddb.Attribute(
                name="PK",
                type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(
                name="Start",
                type=ddb.AttributeType.NUMBER
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        # Chunk Table: StartPts LSI
        self.chunk_table.add_local_secondary_index(
            index_name=CHUNK_STARTPTS_INDEX,
            sort_key=ddb.Attribute(
                name="StartPts",
                type=ddb.AttributeType.NUMBER
            )
        )

        # PluginResult Table
        self.plugin_result_table = ddb.Table(
            self,
            "PluginResult",
            partition_key=ddb.Attribute(
                name="PK",
                type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(
                name="Start",
                type=ddb.AttributeType.NUMBER
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        # PluginResults Table: ProgramEvent_Start GSI
        self.plugin_result_table.add_global_secondary_index(
            index_name=PROGRAM_EVENT_INDEX,
            partition_key=ddb.Attribute(
                name="ProgramEvent",
                type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(
                name="Start",
                type=ddb.AttributeType.NUMBER
            )
        )

        # ClipPreviewFeedback Table
        self.clip_preview_feedback_table = ddb.Table(
            self,
            "ClipReviewFeedback",
            partition_key=ddb.Attribute(
                name="PK",
                type=ddb.AttributeType.STRING
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        # ClipPreviewFeedback Table: Name GSI
        self.clip_preview_feedback_table.add_global_secondary_index(
            index_name=CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_TRACK_INDEX,
            partition_key=ddb.Attribute(
                name="ProgramEventTrack",
                type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(
                name="Start",
                type=ddb.AttributeType.NUMBER
            )
        )

        # ClipPreviewFeedback Table: program#{name}#{classifier}#Start GSI
        self.clip_preview_feedback_table.add_global_secondary_index(
            index_name=CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_CLASSIFIER_START_INDEX,
            partition_key=ddb.Attribute(
                name="ProgramEventClassifierStart",
                type=ddb.AttributeType.STRING
            )
        )

        # ReplayResults Table
        self.replay_results_table = ddb.Table(
            self,
            "ReplayResults",
            partition_key=ddb.Attribute(
                name="ProgramEventReplayId",
                type=ddb.AttributeType.STRING
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        # Get the EventBridge Event Bus name for MRE from SSM Parameter Store
        self.eb_event_bus_name = ssm.StringParameter.value_for_string_parameter(
            self,
            parameter_name="/MRE/EventBridge/EventBusName"
        )

        # Get the Event Deletion SQS Queue ARN from SSM Parameter Store
        self.sqs_queue_arn = ssm.StringParameter.value_for_string_parameter(
            self,
            parameter_name="/MRE/ControlPlane/EventDeletionQueueARN"
        )

        # Get the Control plane Workflow Execution DDB table ARN from SSM Parameter Store
        self.workflow_execution_table_arn = ssm.StringParameter.value_for_string_parameter(
            self,
            parameter_name="/MRE/ControlPlane/WorkflowExecutionTableARN"
        )

        # Chalice IAM Role
        self.chalice_role = iam.Role(
            self,
            "ChaliceRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE Data Plane Chalice Lambda function"
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
                    self.frame_table.table_arn,
                    f"{self.frame_table.table_arn}/index/*",
                    self.chunk_table.table_arn,
                    self.replay_results_table.table_arn,
                    f"{self.chunk_table.table_arn}/index/*",
                    self.plugin_result_table.table_arn,
                    f"{self.plugin_result_table.table_arn}/index/*",
                    self.clip_preview_feedback_table.table_arn,
                    f"{self.clip_preview_feedback_table.table_arn}/index/*"
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

        # Chalice IAM Role: EventBridge permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "events:DescribeEventBus",
                    "events:PutEvents"
                ],
                resources=[
                    f"arn:aws:events:*:*:event-bus/{self.eb_event_bus_name}"
                ]
            )
        )

        # Event Deletion Handler Lambda IAM Role
        self.event_deletion_lambda_role = iam.Role(
            self,
            "EventDeletionHandlerLambdaRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE Event Deletion Handler Lambda function"
        )

        # Event Deletion Handler Lambda IAM Role: DynamoDB permissions
        self.event_deletion_lambda_role.add_to_policy(
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
                    self.plugin_result_table.table_arn,
                    f"{self.plugin_result_table.table_arn}/index/*",
                    self.frame_table.table_arn,
                    f"{self.frame_table.table_arn}/index/*",
                    self.chunk_table.table_arn,
                    self.workflow_execution_table_arn
                ]
            )
        )

        # Event Deletion Handler Lambda IAM Role: CloudWatch Logs permissions
        self.event_deletion_lambda_role.add_to_policy(
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

        # Event Deletion Handler Lambda function
        self.event_deletion_handler_lambda = _lambda.Function(
            self,
            "EventDeletionHandler",
            description="Delete all the processing data stored in DynamoDB for a given Event and Program based on the notification sent to the Event Deletion SQS queue",
            code=_lambda.Code.asset("lambda/EventDeletionHandler"),
            runtime=_lambda.Runtime.PYTHON_3_8,
            handler="lambda_function.lambda_handler",
            role=self.event_deletion_lambda_role,
            memory_size=256,
            timeout=cdk.Duration.minutes(15),
            environment={
                "PLUGIN_RESULT_TABLE_NAME": self.plugin_result_table.table_name,
                "PLUGIN_RESULT_PROGRAM_EVENT_INDEX": PROGRAM_EVENT_INDEX,
                "FRAME_TABLE_NAME": self.frame_table.table_name,
                "FRAME_PROGRAM_EVENT_INDEX": FRAME_PROGRAM_EVENT_INDEX,
                "CHUNK_TABLE_NAME": self.chunk_table.table_name,
                "WORKFLOW_EXECUTION_TABLE_ARN": self.workflow_execution_table_arn
            }
        )

        # Event Deletion Handler Lambda: SQS Event Source
        self.event_deletion_handler_lambda.add_event_source(
            _lambda_es.SqsEventSource(
                queue=sqs.Queue.from_queue_arn(
                    self,
                    "EventDeletionQueue",
                    queue_arn=self.sqs_queue_arn
                ),
                batch_size=1
            )
        )

        self.chalice = Chalice(
            self,
            "ChaliceApp",
            source_dir=RUNTIME_SOURCE_DIR,
            stage_config={
                "environment_variables": {
                    "FRAME_TABLE_NAME": self.frame_table.table_name,
                    "CHUNK_TABLE_NAME": self.chunk_table.table_name,
                    "CHUNK_STARTPTS_INDEX": CHUNK_STARTPTS_INDEX,
                    "PLUGIN_RESULT_TABLE_NAME": self.plugin_result_table.table_name,
                    "CLIP_PREVIEW_FEEDBACK_TABLE_NAME": self.clip_preview_feedback_table.table_name,
                    "EB_EVENT_BUS_NAME": self.eb_event_bus_name,
                    "REPLAY_RESULT_TABLE_NAME": self.replay_results_table.table_name,
                    "PROGRAM_EVENT_INDEX": PROGRAM_EVENT_INDEX,
                    "CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_TRACK_INDEX": CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_TRACK_INDEX,
                    "CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_CLASSIFIER_START_INDEX": CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_CLASSIFIER_START_INDEX
                },
                "tags": {
                    "Project": "MRE"
                },
                "manage_iam_role": False,
                "iam_role_arn": self.chalice_role.role_arn
            }
        )

        # Store the API Gateway endpoint output of Chalice in SSM Parameter Store
        ssm.StringParameter(
            self,
            "MREDataPlaneEndpointParam",
            string_value=self.chalice.sam_template.get_output("EndpointURL").value,
            parameter_name="/MRE/DataPlane/EndpointURL",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the AWS MRE DataPlane APIEndpoint URL used by the MRE Plugin helper library"
        )
