#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import sys

from aws_cdk import (
    Fn,
    CustomResource,
    RemovalPolicy,
    Stack,
    Duration,
    aws_dynamodb as ddb,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_lambda_event_sources as _lambda_es,
    aws_lambda_python_alpha as _lambdapython,
    aws_opensearchserverless as opensearchserverless,
    aws_sqs as sqs,
    aws_ssm as ssm,
    custom_resources as cr,
    CfnOutput,
    aws_logs as logs
)
from chalice.cdk import Chalice
from cdk_nag import NagSuppressions
import json

CHUNK_STARTPTS_INDEX = "StartPts-index"
PROGRAM_EVENT_INDEX = "ProgramEvent_Start-index"
PROGRAM_EVENT_PLUGIN_INDEX = "ProgramEventPluginName_Start-index"
PARTITION_KEY_END_INDEX = "PK_End-index"
PARTITION_KEY_CHUNK_NUMBER_INDEX = "PK_ChunkNumber-index"
FRAME_PROGRAM_EVENT_INDEX = "ProgramEvent-index"
CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_TRACK_INDEX = "ProgramEventTrack-index"
CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_CLASSIFIER_START_INDEX = (
    "ProgramEventClassifierStart-index"
)
PROGRAM_EVENT_LABEL_INDEX = "ProgramEvent_Label-index"
NON_OPT_SEG_INDEX = "NonOptoSegments-index"
REPLAY_RESULT_PROGRAM_EVENT_INDEX = "Program_Event-index"
AOSS_KNN_INDEX_NAME = "mre-knn-index"
AOSS_EVENT_INDEX_NAME = "mre-event-summary-index"
AOSS_PROGRAM_INDEX_NAME = "mre-program-summary-index"

# Ask Python interpreter to search for modules in the topmost folder. This is required to access the shared.infrastructure.helpers module
sys.path.append("../../../")

from shared.infrastructure.helpers import common, api_logging_construct

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, "runtime"
)


class ChaliceApp(Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Get the existing MRE Segment Cache bucket
        self.segment_cache_bucket_name = (
            common.MreCdkCommon.get_segment_cache_bucket_name(self)
        )
        self.ffmpeg_layer = common.MreCdkCommon.get_ffmpeg_layer_from_arn(self)
        self.ffprobe_layer = common.MreCdkCommon.get_ffprobe_layer_from_arn(self)
        self.mre_api_gateway_logging_role_arn = Fn.import_value("mre-api-gateway-logging-role-arn")
        self.powertools_layer = common.MreCdkCommon.get_powertools_layer_from_arn(self)

        # Enable API Gateway logging through Custom Resources
        api_logging_construct.ApiGatewayLogging(
            self, 
            "DataPlaneApi",
            stack_name=self.stack_name,
            api_gateway_logging_role_arn=self.mre_api_gateway_logging_role_arn,
            rate_limit = 30, # 30 requests per second
            burst_limit = 20 # up to 20 concurrent requests
        )

        # JobTracking Table
        self.job_tracking_table = ddb.Table(
            self,
            "JobTracker",
            partition_key=ddb.Attribute(name="JobId", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl",
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        # Frame Table
        self.frame_table = ddb.Table(
            self,
            "Frame",
            partition_key=ddb.Attribute(name="Id", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="FrameNumber", type=ddb.AttributeType.NUMBER),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        # Frame Table: ProgramEvent GSI
        self.frame_table.add_global_secondary_index(
            index_name=FRAME_PROGRAM_EVENT_INDEX,
            partition_key=ddb.Attribute(
                name="ProgramEvent", type=ddb.AttributeType.STRING
            ),
            projection_type=ddb.ProjectionType.KEYS_ONLY,
        )

        # Chunk Table
        self.chunk_table = ddb.Table(
            self,
            "Chunk",
            partition_key=ddb.Attribute(name="PK", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="Start", type=ddb.AttributeType.NUMBER),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        # Chunk Table: StartPts LSI
        self.chunk_table.add_local_secondary_index(
            index_name=CHUNK_STARTPTS_INDEX,
            sort_key=ddb.Attribute(name="StartPts", type=ddb.AttributeType.NUMBER),
        )

        # PluginResult Table
        self.plugin_result_table = ddb.Table(
            self,
            "PluginResult",
            partition_key=ddb.Attribute(name="PK", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="Start", type=ddb.AttributeType.NUMBER),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        CfnOutput(
            self,
            "mre-plugin-result-table-arn",
            value=self.plugin_result_table.table_arn,
            description="Arn of the MRE plugin-result table",
            export_name="mre-plugin-result-table-arn",
        )
        CfnOutput(
            self,
            "mre-plugin-result-table-name",
            value=self.plugin_result_table.table_name,
            description="Name of the MRE plugin-result table",
            export_name="mre-plugin-result-table-name",
        )

        # PluginResults Table: ProgramEventPluginName_Start GSI
        self.plugin_result_table.add_global_secondary_index(
            index_name=PROGRAM_EVENT_PLUGIN_INDEX,
            partition_key=ddb.Attribute(
                name="ProgramEventPluginName", type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(name="Start", type=ddb.AttributeType.NUMBER),
        )

        # PluginResults Table: ProgramEvent_Start GSI
        self.plugin_result_table.add_global_secondary_index(
            index_name=PROGRAM_EVENT_INDEX,
            partition_key=ddb.Attribute(
                name="ProgramEvent", type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(name="Start", type=ddb.AttributeType.NUMBER),
        )

        # DynamoDB GSI Handler Lambda IAM Role
        self.gsi_handler_lambda_role = iam.Role(
            self,
            "DynamoGSIHandlerLambdaRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE DynamoDB GSI Handler Lambda function",
        )

        # DynamoDB GSI Handler Lambda IAM Role: DynamoDB permissions
        self.gsi_handler_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:DescribeTable", "dynamodb:UpdateTable"],
                resources=[self.plugin_result_table.table_arn],
            )
        )

        # DynamoDB GSI Handler Lambda IAM Role: CloudWatch Logs permissions
        self.gsi_handler_lambda_role.add_to_policy(self.get_default_cw_log_policy())
        self.gsi_handler_lambda_role.add_to_policy(
            self.get_function_specific_cw_log_policy("DynamoGSIHandler")
        )

        # Lambda function: DynamoDB GSI Handler
        self.gsi_handler_lambda = _lambda.Function(
            self,
            "DynamoGSIHandler",
            description="Create or Delete GSI from a MRE managed DynamoDB table",
            code=_lambda.Code.from_asset("lambda/DynamoGSIHandler"),
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.on_event",
            role=self.gsi_handler_lambda_role,
            memory_size=128,
            timeout=Duration.minutes(5),
        )

        # GSI Custom Resource IsComplete Handler Lambda IAM Role
        self.gsi_is_complete_handler_lambda_role = iam.Role(
            self,
            "CRIsCompleteHandlerLambdaRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE Custom Resource IsComplete Handler Lambda function",
        )

        # GSI Custom Resource IsComplete Handler Lambda IAM Role: DynamoDB permissions
        self.gsi_is_complete_handler_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:DescribeTable"],
                resources=[self.plugin_result_table.table_arn],
            )
        )

        # GSI Custom Resource IsComplete Handler Lambda IAM Role: CloudWatch Logs permissions
        self.gsi_is_complete_handler_lambda_role.add_to_policy(
            self.get_default_cw_log_policy()
        )
        self.gsi_is_complete_handler_lambda_role.add_to_policy(
            self.get_function_specific_cw_log_policy("CRIsCompleteHandler")
        )

        # Lambda function: GSI Custom Resource IsComplete Handler
        self.gsi_is_complete_handler_lambda = _lambda.Function(
            self,
            "CRIsCompleteHandler",
            description="Check the current status of the DynamoDB GSI created via a Custom Resource",
            code=_lambda.Code.from_asset("lambda/DynamoIsCompleteHandler"),
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.is_complete",
            role=self.gsi_is_complete_handler_lambda_role,
            memory_size=128,
            timeout=Duration.minutes(5),
        )

        # GSI Custom Resource Provider
        self.gsi_cr_provider = cr.Provider(
            self,
            "GSI_CR_Provider",
            on_event_handler=self.gsi_handler_lambda,
            is_complete_handler=self.gsi_is_complete_handler_lambda,
            query_interval=Duration.minutes(1),
            total_timeout=Duration.hours(2),
            log_retention=logs.RetentionDays.TEN_YEARS
        )

        # PluginResults Table: ProgramEvent_Label GSI via Custom Resource
        self.programevent_label_gsi_cr = CustomResource(
            self,
            "ProgramEvent_Label_GSI_CR",
            service_token=self.gsi_cr_provider.service_token,
            removal_policy=RemovalPolicy.DESTROY,
            properties={
                "table_name": self.plugin_result_table.table_name,
                "index_name": PROGRAM_EVENT_LABEL_INDEX,
                "partition_key": {"Name": "PK", "Type": "S"},
                "sort_key": {"Name": "LabelCode", "Type": "S"},
            },
        )

        self.programevent_label_gsi_cr.node.add_dependency(self.plugin_result_table)

        # PluginResults Table: NonOptoSegments GSI via Custom Resource
        self.non_opto_segments_gsi_cr = CustomResource(
            self,
            "NonOptoSegments_GSI_CR",
            service_token=self.gsi_cr_provider.service_token,
            removal_policy=RemovalPolicy.DESTROY,
            properties={
                "table_name": self.plugin_result_table.table_name,
                "index_name": NON_OPT_SEG_INDEX,
                "partition_key": {"Name": "PK", "Type": "S"},
                "sort_key": {"Name": "NonOptoChunkNumber", "Type": "N"},
            },
        )

        self.non_opto_segments_gsi_cr.node.add_dependency(
            self.programevent_label_gsi_cr
        )

        # PluginResults Table: PK_End GSI via Custom Resource
        self.pk_end_gsi_cr = CustomResource(
            self,
            "PK_End_GSI_CR",
            service_token=self.gsi_cr_provider.service_token,
            removal_policy=RemovalPolicy.DESTROY,
            properties={
                "table_name": self.plugin_result_table.table_name,
                "index_name": PARTITION_KEY_END_INDEX,
                "partition_key": {"Name": "PK", "Type": "S"},
                "sort_key": {"Name": "End", "Type": "N"},
            },
        )

        self.pk_end_gsi_cr.node.add_dependency(
            self.non_opto_segments_gsi_cr
        )

        # PluginResults Table: PK_ChunkNumber GSI via Custom Resource
        self.pk_chunknumber_gsi_cr = CustomResource(
            self,
            "PK_ChunkNumber_GSI_CR",
            service_token=self.gsi_cr_provider.service_token,
            removal_policy=RemovalPolicy.DESTROY,
            properties={
                "table_name": self.plugin_result_table.table_name,
                "index_name": PARTITION_KEY_CHUNK_NUMBER_INDEX,
                "partition_key": {"Name": "PK", "Type": "S"},
                "sort_key": {"Name": "ChunkNumber", "Type": "N"},
            },
        )

        self.pk_chunknumber_gsi_cr.node.add_dependency(self.pk_end_gsi_cr)

        # ClipPreviewFeedback Table
        self.clip_preview_feedback_table = ddb.Table(
            self,
            "ClipReviewFeedback",
            partition_key=ddb.Attribute(name="PK", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        # ClipPreviewFeedback Table: Name GSI
        self.clip_preview_feedback_table.add_global_secondary_index(
            index_name=CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_TRACK_INDEX,
            partition_key=ddb.Attribute(
                name="ProgramEventTrack", type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(name="Start", type=ddb.AttributeType.NUMBER),
        )

        # ClipPreviewFeedback Table: program#{name}#{classifier}#Start GSI
        self.clip_preview_feedback_table.add_global_secondary_index(
            index_name=CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_CLASSIFIER_START_INDEX,
            partition_key=ddb.Attribute(
                name="ProgramEventClassifierStart", type=ddb.AttributeType.STRING
            ),
        )

        # ReplayResults Table
        self.replay_results_table = ddb.Table(
            self,
            "ReplayResults",
            partition_key=ddb.Attribute(
                name="ProgramEventReplayId", type=ddb.AttributeType.STRING
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        # ReplayResults Table: ProgramEvent GSI
        self.replay_results_table.add_global_secondary_index(
            index_name=REPLAY_RESULT_PROGRAM_EVENT_INDEX,
            partition_key=ddb.Attribute(name="Program", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="Event", type=ddb.AttributeType.STRING),
            projection_type=ddb.ProjectionType.KEYS_ONLY,
        )

        # Get the EventBridge Event Bus name for MRE from SSM Parameter Store
        self.eb_event_bus_name = ssm.StringParameter.value_for_string_parameter(
            self, parameter_name="/MRE/EventBridge/EventBusName"
        )

        # Get the Event Deletion SQS Queue ARN from SSM Parameter Store
        self.sqs_queue_arn = ssm.StringParameter.value_for_string_parameter(
            self, parameter_name="/MRE/ControlPlane/EventDeletionQueueARN"
        )

        # Get the Control plane Workflow Execution DDB table ARN from SSM Parameter Store
        self.workflow_execution_table_arn = (
            ssm.StringParameter.value_for_string_parameter(
                self, parameter_name="/MRE/ControlPlane/WorkflowExecutionTableARN"
            )
        )

        # Get the ReplayRequest table ARN from CfnOutput
        self.replay_request_table_arn = Fn.import_value("mre-replayrequest-table-arn")

        # Get the ReplayRequest table name from CfnOutput
        self.replay_request_table_name = Fn.import_value("mre-replayrequest-table-name")

        # Chalice IAM Role
        self.chalice_role = iam.Role(
            self,
            "ChaliceRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE Data Plane Chalice Lambda function",
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
                    self.frame_table.table_arn,
                    f"{self.frame_table.table_arn}/index/*",
                    self.chunk_table.table_arn,
                    self.replay_results_table.table_arn,
                    f"{self.chunk_table.table_arn}/index/*",
                    self.plugin_result_table.table_arn,
                    f"{self.plugin_result_table.table_arn}/index/*",
                    self.clip_preview_feedback_table.table_arn,
                    f"{self.clip_preview_feedback_table.table_arn}/index/*",
                    self.job_tracking_table.table_arn,
                    f"{self.job_tracking_table.table_arn}/index/*",
                ],
            )
        )

        # Chalice IAM Role: S3 Read permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject","s3:ListBucketVersions", 
                    "s3:GetBucketVersioning",
                    "s3:GetObjectVersion",
                ],
                resources=[f"arn:aws:s3:::*/*", f"arn:aws:s3:::*"],
            )
        )

        # Chalice IAM Role: CloudWatch Logs permissions
        self.chalice_role.add_to_policy(self.get_function_specific_cw_log_policy())
        self.chalice_role.add_to_policy(self.get_default_cw_log_policy())

        # Chalice IAM Role: EventBridge permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["events:DescribeEventBus", "events:PutEvents"],
                resources=[
                    f"arn:aws:events:{Stack.of(self).region}:{Stack.of(self).account}:event-bus/{self.eb_event_bus_name}"
                ],
            )
        )

        # Chalice IAM Role: Bedrock permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                ],
                resources=[
                    f"arn:aws:bedrock:{Stack.of(self).region}::foundation-model/amazon.titan-embed-text-v2:0",
                ],
            )
        )

        # Chalice IAM Role: OpenSearch Serverless permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["aoss:APIAccessAll"],
                resources=[
                    f"arn:aws:aoss:{Stack.of(self).region}:{Stack.of(self).account}:collection/*"
                ],
            )
        )

        # Event Deletion Handler Lambda IAM Role
        self.event_deletion_lambda_role = iam.Role(
            self,
            "EventDeletionHandlerLambdaRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE Event Deletion Handler Lambda function",
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
                    "dynamodb:DeleteItem",
                ],
                resources=[
                    self.plugin_result_table.table_arn,
                    f"{self.plugin_result_table.table_arn}/index/*",
                    self.frame_table.table_arn,
                    f"{self.frame_table.table_arn}/index/*",
                    self.chunk_table.table_arn,
                    self.workflow_execution_table_arn,
                    self.replay_request_table_arn,
                    self.replay_results_table.table_arn,
                    f"{self.replay_results_table.table_arn}/index/*",
                ],
            )
        )

        # Event Deletion Handler Lambda IAM Role: S3 permissions
        self.event_deletion_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:DeleteObject",
                    "s3:DeleteObjectVersion",
                    "s3:ListBucket",
                    "s3:ListObjects",
                    "s3:ListObjectsV2",
                ],
                resources=[
                    f"arn:aws:s3:::{self.segment_cache_bucket_name}",
                    f"arn:aws:s3:::{self.segment_cache_bucket_name}/*",
                ],
            )
        )

        # Event Deletion Handler Lambda IAM Role: CloudWatch Logs permissions
        self.event_deletion_lambda_role.add_to_policy(
            self.get_function_specific_cw_log_policy("EventDeletionHandler")
        )
        self.event_deletion_lambda_role.add_to_policy(self.get_default_cw_log_policy())

        # Event Deletion Handler Lambda function
        self.event_deletion_handler_lambda = _lambda.Function(
            self,
            "EventDeletionHandler",
            description="Delete all the processing data stored in DynamoDB for a given Event and Program based on the notification sent to the Event Deletion SQS queue",
            code=_lambda.Code.from_asset("lambda/EventDeletionHandler"),
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            role=self.event_deletion_lambda_role,
            memory_size=256,
            timeout=Duration.minutes(15),
            environment={
                "PLUGIN_RESULT_TABLE_NAME": self.plugin_result_table.table_name,
                "PLUGIN_RESULT_PROGRAM_EVENT_INDEX": PROGRAM_EVENT_INDEX,
                "FRAME_TABLE_NAME": self.frame_table.table_name,
                "FRAME_PROGRAM_EVENT_INDEX": FRAME_PROGRAM_EVENT_INDEX,
                "CHUNK_TABLE_NAME": self.chunk_table.table_name,
                "WORKFLOW_EXECUTION_TABLE_ARN": self.workflow_execution_table_arn,
                "SEGMENT_CACHE_BUCKET": self.segment_cache_bucket_name,
                "REPLAY_REQUEST_TABLE_NAME": self.replay_request_table_name,
                "REPLAY_RESULT_TABLE_NAME": self.replay_results_table.table_name,
                "REPLAY_RESULT_PROGRAM_EVENT_INDEX": REPLAY_RESULT_PROGRAM_EVENT_INDEX,
            },
        )

        # Event Deletion Handler Lambda: SQS Event Source
        self.event_deletion_handler_lambda.add_event_source(
            _lambda_es.SqsEventSource(
                queue=sqs.Queue.from_queue_arn(
                    self, "EventDeletionQueue", queue_arn=self.sqs_queue_arn
                ),
                batch_size=1,
            )
        )

        ffmpeg_layer_arn = ssm.StringParameter.value_for_string_parameter(
            self, parameter_name="/MRE/FfmpegLambdaLayerArn"
        )
        ffprobe_layer_arn = ssm.StringParameter.value_for_string_parameter(
            self, parameter_name="/MRE/FfprobeLambdaLayerArn"
        )

        # region AOSS
        # Amazon OpenSearch Collection if the --enable-generative-ai flag is set in the build-and-deploy script

        if self.node.try_get_context("GENERATIVE_AI"):
            self.vectorsearch_collection_name = "mre-vectorsearch-collection"
            self.summary_collection_name = "mre-summary-collection"

            # Encryption Policy for OpenSearch Serverless Collection
            self.encryption_policy_json = {
                "Rules": [
                    {
                        "ResourceType": "collection",
                        "Resource": [
                            f"collection/{self.vectorsearch_collection_name}",
                            f"collection/{self.summary_collection_name}",
                        ],
                    }
                ],
                "AWSOwnedKey": True,
            }

            self.aoss_encryption_policy = opensearchserverless.CfnSecurityPolicy(
                self,
                "AossEncryptionPolicy",
                name="mre-aoss-encryption-policy",
                policy=json.dumps(self.encryption_policy_json),
                type="encryption",
                description="Encryption policy for AOSS collections",
            )

            self.network_policy = [
                {
                    "Rules": [
                        {
                            "Resource": [
                                f"collection/{self.vectorsearch_collection_name}",
                                f"collection/{self.summary_collection_name}",
                            ],
                            "ResourceType": "dashboard",
                        },
                        {
                            "Resource": [
                                f"collection/{self.vectorsearch_collection_name}",
                                f"collection/{self.summary_collection_name}",
                            ],
                            "ResourceType": "collection",
                        },
                    ],
                    "AllowFromPublic": True,
                }
            ]

            self.aoss_network_access_policy = opensearchserverless.CfnSecurityPolicy(
                self,
                "AossNetworkPolicy",
                name="mre-aoss-network-policy",
                policy=json.dumps(self.network_policy),
                type="network",
                description="Network policy for AOSS collections",
            )

            self.opensearch_policy = iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["aoss:APIAccessAll"],
                resources=[
                    f"arn:aws:aoss:{Stack.of(self).region}:{Stack.of(self).account}:collection/{self.vectorsearch_collection_name}",
                    f"arn:aws:aoss:{Stack.of(self).region}:{Stack.of(self).account}:collection/{self.summary_collection_name}",
                ],
            )
            self.chalice_role.add_to_policy(self.opensearch_policy)

            # OpenSearch Serverless Collection of type vectorsearch

            self.vectorsearch_collection = opensearchserverless.CfnCollection(
                self,
                "VectorSearchCollection",
                name=self.vectorsearch_collection_name,
                description="Vector search index for search across events and programs",
                type="VECTORSEARCH",
            )

            # Chalice IAM Role: OpenSearch Serverless permissions
            self.chalice_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["aoss:APIAccessAll"],
                    resources=[self.vectorsearch_collection.attr_arn],
                )
            )

            self.vectorsearch_collection.add_dependency(self.aoss_encryption_policy)
            self.vectorsearch_collection.add_dependency(self.aoss_network_access_policy)

            # OpenSearch Serverless Collection of type search for 'summary' based index
            self.summary_search_collection = opensearchserverless.CfnCollection(
                self,
                "SearchCollection",
                name=self.summary_collection_name,
                description="Full-text search that enables summary based questions on events and programs",
                type="SEARCH",
            )

            self.summary_search_collection.add_dependency(self.aoss_encryption_policy)
            self.summary_search_collection.add_dependency(
                self.aoss_network_access_policy
            )

            self.event_index_name = "mre-event-summary-index"
            self.program_index_name = "mre-program-summary-index"
            self.knn_index_name = "mre-knn-index"

            self.index_creation_function_role = iam.Role(
                self,
                "IndexCreationFunctionRole",
                assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
                description="Role used by the MRE Index Creation Lambda function",
            )

            # Lambda function for creating indexes
            self.index_creation_function = _lambdapython.PythonFunction(
                self,
                "IndexCreationFunction",
                description="Craete AOSS index under summary and vectorsearch collections",
                runtime=_lambda.Runtime.PYTHON_3_11,
                index="lambda_function.py",
                handler="handler",
                entry="lambda/AossIndexCreationHandler",
                environment={
                    "KNN_INDEX_NAME": AOSS_KNN_INDEX_NAME,
                    "EVENT_INDEX_NAME": AOSS_EVENT_INDEX_NAME,
                    "PROGRAM_INDEX_NAME": AOSS_PROGRAM_INDEX_NAME,
                    "OPENSEARCH_REGION": Stack.of(self).region,
                    "SUMMARY_SEARCH_COLLECTION": self.summary_search_collection.name,
                    "VECTORSEARCH_COLLECTION": self.vectorsearch_collection.name,
                },
                memory_size=256,
                timeout=Duration.minutes(5),
                role=self.index_creation_function_role,
            )

            self.index_creation_function_role.add_to_policy(
                self.get_default_cw_log_policy()
            )

            self.index_creation_function_role.add_to_policy(
                self.get_function_specific_cw_log_policy("IndexCreationFunction")
            )

            # Grant the Lambda function permissions to create and delete indexes
            self.index_creation_function_role.add_to_policy(
                iam.PolicyStatement(
                    resources=[
                        f"arn:aws:aoss:{Stack.of(self).region}:{Stack.of(self).account}:collection/*"
                    ],
                    actions=[
                        "aoss:CreateCollection",
                        "aoss:DeleteCollection",
                        "aoss:UpdateCollection",
                        "aoss:APIAccessAll",
                        "aoss:CreateAccessPolicy",
                        "aoss:CreateLifecyclePolicy",
                        "aoss:CreateSecurityConfig",
                        "aoss:CreateSecurityPolicy",
                        "aoss:CreateVpcEndpoint",
                        "aoss:GetAccessPolicy",
                        "aoss:GetSecurityConfig",
                        "aoss:GetSecurityPolicy",
                        "aoss:BatchGetCollection",
                        "aoss:ListCollections",
                        "aoss:ListAccessPolicies",
                    ],
                )
            )

            self.index_creation_function_role.add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "aoss:BatchGetCollection",
                        "aoss:ListCollections",
                        "aoss:CreateAccessPolicy",
                        "aoss:CreateSecurityPolicy",
                        "aoss:ListAccessPolicies",
                        "aoss:APIAccessAll",
                    ],
                    resources=["*"],
                )
            )

            # Custom resource to create indexes
            self.custom_resource_provider = cr.Provider(
                self,
                "CustomResourceProvider",
                on_event_handler=self.index_creation_function,
                log_retention=logs.RetentionDays.TEN_YEARS
            )

            self.create_index_cr = CustomResource(
                self,
                "CustomResource",
                service_token=self.custom_resource_provider.service_token,
            )

            self.create_index_cr.node.add_dependency(self.index_creation_function)
            self.create_index_cr.node.add_dependency(self.vectorsearch_collection)
            self.create_index_cr.node.add_dependency(self.summary_search_collection)
            self.create_index_cr.node.add_dependency(self.aoss_network_access_policy)

            # Data Access policy for OpenSearch Serverless Collection
            # TODO: should include all roles in the principal for the streaming function
            self.access_policy_json = [
                {
                    "Rules": [
                        {
                            "Resource": [
                                f"collection/{self.vectorsearch_collection_name}",
                                f"collection/{self.summary_collection_name}",
                            ],
                            "Permission": [
                                "aoss:CreateCollectionItems",
                                "aoss:DeleteCollectionItems",
                                "aoss:UpdateCollectionItems",
                                "aoss:DescribeCollectionItems",
                            ],
                            "ResourceType": "collection",
                        },
                        {
                            "Resource": [
                                f"index/{self.vectorsearch_collection_name}/*",
                                f"index/{self.summary_collection_name}/*",
                            ],
                            "Permission": [
                                "aoss:CreateIndex",
                                "aoss:DeleteIndex",
                                "aoss:UpdateIndex",
                                "aoss:DescribeIndex",
                                "aoss:ReadDocument",
                                "aoss:WriteDocument",
                            ],
                            "ResourceType": "index",
                        },
                    ],
                    "Principal": [
                        self.chalice_role.role_arn,
                        self.index_creation_function.role.role_arn,
                    ],
                }
            ]

            self.aoss_data_access_policy = opensearchserverless.CfnAccessPolicy(
                self,
                "AossDataAccessPolicy",
                name="mre-aoss-data-access-policy",
                policy=json.dumps(self.access_policy_json),
                type="data",
                description="Data Access Policy for Amazon OpenSearch Serverless",
            )

            self.create_index_cr.node.add_dependency(self.aoss_data_access_policy)
            ssm.StringParameter(
                self,
                "MREDataPlaneAossDetailSearchEP",
                string_value=self.vectorsearch_collection.attr_collection_endpoint,
                parameter_name="/MRE/DataPlane/AossDetailSearchEndpointURL",
                tier=ssm.ParameterTier.INTELLIGENT_TIERING,
                description="[DO NOT DELETE] Parameter contains the AWS MRE DataPlane OpenSearch Endpoint URL for detailed searches, used by the MRE Plugin helper library",
            )

            ssm.StringParameter(
                self,
                "MREDataPlaneAossSummarySearchEP",
                string_value=self.summary_search_collection.attr_collection_endpoint,
                parameter_name="/MRE/DataPlane/AossSummarySearchEndpointURL",
                tier=ssm.ParameterTier.INTELLIGENT_TIERING,
                description="[DO NOT DELETE] Parameter contains the AWS MRE DataPlane OpenSearch Endpoint URL for summary based searches, used by the MRE Plugin helper library",
            )

            ssm.StringParameter(
                self,
                "MREDataPlaneAossDetailedSearchIndex",
                string_value=AOSS_KNN_INDEX_NAME,
                parameter_name="/MRE/DataPlane/AossDetailedSearchIndex",
                tier=ssm.ParameterTier.INTELLIGENT_TIERING,
                description="[DO NOT DELETE] Parameter contains the AWS MRE DataPlane OpenSearch Index name for KNN based similarity searches for detailed answers",
            )

            ssm.StringParameter(
                self,
                "MREDataPlaneAossEventIndex",
                string_value=AOSS_EVENT_INDEX_NAME,
                parameter_name="/MRE/DataPlane/AossEventIndex",
                tier=ssm.ParameterTier.INTELLIGENT_TIERING,
                description="[DO NOT DELETE] Parameter contains the AWS MRE DataPlane OpenSearch Index name for event related summary based searches",
            )

            ssm.StringParameter(
                self,
                "MREDataPlaneAossProgramIndex",
                string_value=AOSS_PROGRAM_INDEX_NAME,
                parameter_name="/MRE/DataPlane/AossProgramIndex",
                tier=ssm.ParameterTier.INTELLIGENT_TIERING,
                description="[DO NOT DELETE] Parameter contains the AWS MRE DataPlane OpenSearch Index name for program related summary based searches",
            )

        # endregion End of AOSS resources creation

        stage_config = {
            "environment_variables": {
                "FRAME_TABLE_NAME": self.frame_table.table_name,
                "CHUNK_TABLE_NAME": self.chunk_table.table_name,
                "CHUNK_STARTPTS_INDEX": CHUNK_STARTPTS_INDEX,
                "PLUGIN_RESULT_TABLE_NAME": self.plugin_result_table.table_name,
                "CLIP_PREVIEW_FEEDBACK_TABLE_NAME": self.clip_preview_feedback_table.table_name,
                "EB_EVENT_BUS_NAME": self.eb_event_bus_name,
                "REPLAY_RESULT_TABLE_NAME": self.replay_results_table.table_name,
                "PROGRAM_EVENT_INDEX": PROGRAM_EVENT_INDEX,
                "PROGRAM_EVENT_PLUGIN_INDEX": PROGRAM_EVENT_PLUGIN_INDEX,
                "PARTITION_KEY_END_INDEX": PARTITION_KEY_END_INDEX,
                "CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_TRACK_INDEX": CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_TRACK_INDEX,
                "CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_CLASSIFIER_START_INDEX": CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_CLASSIFIER_START_INDEX,
                "PROGRAM_EVENT_LABEL_INDEX": PROGRAM_EVENT_LABEL_INDEX,
                "JOB_TRACKER_TABLE_NAME": self.job_tracking_table.table_name,
                "NON_OPTO_SEGMENTS_INDEX": NON_OPT_SEG_INDEX,
                "PARTITION_KEY_CHUNK_NUMBER_INDEX": PARTITION_KEY_CHUNK_NUMBER_INDEX,
                "MAX_DETECTOR_QUERY_WINDOW_SECS": "60",
                "AOSS_KNN_INDEX_NAME": AOSS_KNN_INDEX_NAME,
                "AOSS_EVENT_INDEX_NAME": AOSS_EVENT_INDEX_NAME,
                "AOSS_PROGRAM_INDEX_NAME": AOSS_PROGRAM_INDEX_NAME,
                "OPENSEARCH_REGION": Stack.of(self).region,
            },
            "tags": {"Project": "MRE"},
            "manage_iam_role": False,
            "iam_role_arn": self.chalice_role.role_arn,
            "lambda_memory_size": 2048,
            "layers": [ffmpeg_layer_arn, ffprobe_layer_arn, self.powertools_layer.layer_version_arn],
        }

        ## Determine if we need environment variables related to vector store
        if self.node.try_get_context("GENERATIVE_AI"):
            stage_config["environment_variables"][
                "OS_SUMMARY_SEARCH_COLLECTION_EP"
            ] = self.summary_search_collection.attr_collection_endpoint
            stage_config["environment_variables"][
                "OS_VECTORSEARCH_COLLECTION_EP"
            ] = self.vectorsearch_collection.attr_collection_endpoint

        self.chalice = Chalice(
            self,
            "ChaliceApp",
            source_dir=RUNTIME_SOURCE_DIR,
            stage_config=stage_config,
        )

        CfnOutput(
            self,
            "mre-dataplane-api-id",
            value=self.chalice.get_resource("RestAPI").ref,
            description="MRE Dataplane REST API Rest ID",
            export_name="mre-dataplane-api-rest-id",
        )

        # Store the API Gateway endpoint output of Chalice in SSM Parameter Store
        ssm.StringParameter(
            self,
            "MREDataPlaneEndpointParam",
            string_value=self.chalice.sam_template.get_output("EndpointURL").value,
            parameter_name="/MRE/DataPlane/EndpointURL",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the AWS MRE DataPlane APIEndpoint URL used by the MRE Plugin helper library",
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
                    "id": "AwsSolutions-IAM5",
                    "reason": "MRE internal lambda IAM role policies require wildcard permissions for S3 bucket access",
                    "appliesTo": [
                        "Resource::arn:aws:s3:::*/*",
                        "Resource::arn:aws:s3:::*",
                        "Resource::arn:aws:s3:::mre-segment-cache-bucket-name/*",
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Lambda logging requires access to CloudWatch log groups",
                    "appliesTo": [
                        {
                            "regex": f"/^Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:\/aws\/lambda\/{Stack.of(self).stack_name}-.+$/"
                        },
                        "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:*",
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "MRE internal lambda IAM role policies require wildcard permissions for OpenSearch collections",
                    "appliesTo": [
                        "Resource::arn:aws:aoss:<AWS::Region>:<AWS::AccountId>:collection/*",
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "MRE internal lambda IAM role policies require dynamic ARN patterns for resource access",
                    "appliesTo": [
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
                    "appliesTo": ["Resource::<DataPlaneApiEnableLoggingHandler0808D4A7.Arn>:*"]
                }
            ],
        )

        NagSuppressions.add_resource_suppressions(
            self.gsi_cr_provider,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "CloudWatch Logs IAM policies follow AWS Step Functions documentation for logging permissions; https://docs.aws.amazon.com/step-functions/latest/dg/cw-logs.html",
                    "appliesTo": [
                        "Resource::*",
                    ],
                },
                {
                    "id": "AwsSolutions-SF1",
                    "reason": "ALL logging level unnecessary for Custom Resource Waiter Step Function functionality",
                },
                {
                    "id": "AwsSolutions-SF2",
                    "reason": "X-Ray tracing unnecessary for Custom Resource Waiter Step Function functionality",
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Custom Resource Waiter Step Function needs access to handler Lambda ARNs",
                    "appliesTo": [
                        {"regex": "/^Resource::<.*.+Arn>:\\*$/"},
                    ],
                },
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "CDK custom resource provider uses AWS Managed Policies for handler lambda",
                    "appliesTo": [
                        "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                    ],
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "MRE internal lambda functions do not require the latest runtime version as their dependencies have been tested only on Python 3.11",
                },
            ],
            True,
        )
        if self.node.try_get_context("GENERATIVE_AI"):
            NagSuppressions.add_resource_suppressions(
                self.custom_resource_provider,
                [
                    {
                        "id": "AwsSolutions-IAM5",
                        "reason": "Custom Resource Waiter Step Function needs access to handler Lambda ARNs",
                        "appliesTo": [
                            {"regex": "/^Resource::<.*.+Arn>:\\*$/"},
                        ],
                    },
                    {
                        "id": "AwsSolutions-IAM4",
                        "reason": "CDK custom resource provider uses AWS Managed Policies for handler lambda",
                        "appliesTo": [
                            "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                        ],
                    },
                ],
                True,
            )

            NagSuppressions.add_resource_suppressions(
                self.index_creation_function_role,
                [
                    {
                        "id": "AwsSolutions-IAM5",
                        "reason": "OpenSearch Serverless requires some wildcarded resources; https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonopensearchserverless.html#amazonopensearchserverless-actions-as-permissions",
                        "appliesTo": ["Resource::*"],
                    },
                ],
                True,
            )

    def get_default_cw_log_policy(self):
        return iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogGroup",
            ],
            resources=[
                f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:*"
            ],
        )

    def get_function_specific_cw_log_policy(self, function_name: str = None):
        return iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["logs:CreateLogStream", "logs:PutLogEvents"],
            resources=[
                (
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/lambda/{Stack.of(self).stack_name}-{function_name}*"
                    if function_name
                    else f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/lambda/{Stack.of(self).stack_name}-*"
                ),
            ],
        )
