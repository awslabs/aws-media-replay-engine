#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import uuid

from aws_cdk import (
    core as cdk,
    custom_resources as cr,
    aws_dynamodb as ddb,
    aws_events as events,
    aws_events_targets as events_targets,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_lambda_event_sources as _lambda_es,
    aws_s3 as s3,
    aws_s3_deployment as s3_deploy,
    aws_sns as sns,
    aws_sqs as sqs,
    aws_ssm as ssm,
    aws_secretsmanager as secret_mgr,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_mediaconvert as media_convert,
    aws_kms as kms
)
from chalice.cdk import Chalice

FRAMEWORK_VERSION = "%%FRAMEWORK_VERSION%%"
PLUGIN_NAME_INDEX = "Name-index"
PLUGIN_VERSION_INDEX = "Version-index"
MODEL_NAME_INDEX = "Name-index"
MODEL_VERSION_INDEX = "Version-index"
EVENT_CHANNEL_INDEX = "Channel-index"
EVENT_PROGRAMID_INDEX = "ProgramId-index"
EVENT_CONTENT_GROUP_INDEX = "ContentGroup-index"
EVENT_PAGINATION_INDEX = "Pagination-index"
RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')


class ChaliceApp(cdk.Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        ##### START: DYNAMODB TABLES AND INDEXES #####

        # System Configuration Table
        self.system_table = ddb.Table(
            self,
            "System",
            partition_key=ddb.Attribute(
                name="Name",
                type=ddb.AttributeType.STRING
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        # ContentGroup Table
        self.content_group_table = ddb.Table(
            self,
            "ContentGroup",
            partition_key=ddb.Attribute(
                name="Name",
                type=ddb.AttributeType.STRING
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        # Program Table
        self.program_table = ddb.Table(
            self,
            "Program",
            partition_key=ddb.Attribute(
                name="Name",
                type=ddb.AttributeType.STRING
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        # Plugin Table
        self.plugin_table = ddb.Table(
            self,
            "Plugin",
            partition_key=ddb.Attribute(
                name="Name",
                type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(
                name="Version",
                type=ddb.AttributeType.STRING
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        # ReplayRequest Table
        self.replayrequest_table = ddb.Table(
            self,
            "ReplayRequest",
            partition_key=ddb.Attribute(
                name="PK",
                type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(
                name="ReplayId",
                type=ddb.AttributeType.STRING
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        # Plugin Table: Name GSI
        self.plugin_table.add_global_secondary_index(
            index_name=PLUGIN_NAME_INDEX,
            partition_key=ddb.Attribute(
                name="Name",
                type=ddb.AttributeType.STRING
            )
        )

        # Plugin Table: Version GSI
        self.plugin_table.add_global_secondary_index(
            index_name=PLUGIN_VERSION_INDEX,
            partition_key=ddb.Attribute(
                name="Version",
                type=ddb.AttributeType.STRING
            )
        )

        # Profile Table
        self.profile_table = ddb.Table(
            self,
            "Profile",
            partition_key=ddb.Attribute(
                name="Name",
                type=ddb.AttributeType.STRING
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        # Model Table
        self.model_table = ddb.Table(
            self,
            "Model",
            partition_key=ddb.Attribute(
                name="Name",
                type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(
                name="Version",
                type=ddb.AttributeType.STRING
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        # Model Table: Name GSI
        self.model_table.add_global_secondary_index(
            index_name=MODEL_NAME_INDEX,
            partition_key=ddb.Attribute(
                name="Name",
                type=ddb.AttributeType.STRING
            )
        )

        # Model Table: Version GSI
        self.model_table.add_global_secondary_index(
            index_name=MODEL_VERSION_INDEX,
            partition_key=ddb.Attribute(
                name="Version",
                type=ddb.AttributeType.STRING
            )
        )

        # Event Table
        self.event_table = ddb.Table(
            self,
            "Event",
            partition_key=ddb.Attribute(
                name="Name",
                type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(
                name="Program",
                type=ddb.AttributeType.STRING
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        # Event Table: Channel GSI
        self.event_table.add_global_secondary_index(
            index_name=EVENT_CHANNEL_INDEX,
            partition_key=ddb.Attribute(
                name="Channel",
                type=ddb.AttributeType.STRING
            ),
            projection_type=ddb.ProjectionType.KEYS_ONLY
        )

        # Event Table: ProgramId GSI
        self.event_table.add_global_secondary_index(
            index_name=EVENT_PROGRAMID_INDEX,
            partition_key=ddb.Attribute(
                name="ProgramId",
                type=ddb.AttributeType.STRING
            ),
            projection_type=ddb.ProjectionType.KEYS_ONLY
        )

        # Event Table: ContentGroup GSI
        self.event_table.add_global_secondary_index(
            index_name=EVENT_CONTENT_GROUP_INDEX,
            partition_key=ddb.Attribute(
                name="ContentGroup",
                type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(
                name="Start",
                type=ddb.AttributeType.STRING
            )
        )

        # Event Table: Pagination key
        self.event_table.add_global_secondary_index(
            index_name=EVENT_PAGINATION_INDEX,
            partition_key=ddb.Attribute(
                name="PaginationPartition",
                type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(
                name="Start",
                type=ddb.AttributeType.STRING
            )
        )

        # WorkflowExecution Table
        self.workflow_exec_table = ddb.Table(
            self,
            "WorkflowExecution",
            partition_key=ddb.Attribute(
                name="PK",
                type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(
                name="ChunkNumber",
                type=ddb.AttributeType.NUMBER
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        # CurrentEvents Table
        self.current_events_table = ddb.Table(
            self,
            "CurrentEvents",
            partition_key=ddb.Attribute(
                name="EventId",
                type=ddb.AttributeType.STRING
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        ##### END: DYNAMODB TABLES AND INDEXES #####

        ##### START: S3 BUCKETS AND CF DISTRIBUTION #####

        # MRE Access Log Bucket
        self.access_log_bucket = s3.Bucket(
            self, 
            'MreAccessLogsBucket',
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED
        )

        # MRE Data Export Bucket
        self.data_export_bucket = s3.Bucket(
            self, 
            'MreDataExportBucket',
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED
        )

        # MediaLive S3 Destination Bucket
        self.medialive_s3_dest_bucket = s3.Bucket(
            self,
            "MediaLiveDestinationBucket",
            enforce_ssl=True,
            server_access_logs_bucket=self.access_log_bucket,
            server_access_logs_prefix='mre-medialive-logs',
            encryption=s3.BucketEncryption.S3_MANAGED
        )

        # Lambda Layer S3 bucket
        self.lambda_layer_bucket = s3.Bucket(
            self,
            "LambdaLayerBucket",
            enforce_ssl=True,
            server_access_logs_bucket=self.access_log_bucket,
            server_access_logs_prefix='mre-lambdalayer-logs',
            encryption=s3.BucketEncryption.S3_MANAGED
        )

        # Bucket for housing output artifacts such as HLS manifests, MP4, HLS clips etc.
        self.mre_media_output_bucket = s3.Bucket(
            self,
            "MreMediaOutputBucket",
            enforce_ssl=True,
            server_access_logs_bucket=self.access_log_bucket,
            server_access_logs_prefix='mre-mediaconvert-logs',
            encryption=s3.BucketEncryption.S3_MANAGED
        )

        # Cloudfront Distro for Media Output
        self.mre_media_output_distro = cloudfront.Distribution(self, "mre-media-output",
                                                               default_behavior={
                                                                   "origin": origins.S3Origin(
                                                                       self.mre_media_output_bucket),
                                                                   "viewer_protocol_policy": cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                                                                   "cache_policy": cloudfront.CachePolicy(self,
                                                                                                          id="mre-cache-policy",
                                                                                                          cache_policy_name=f"mre-cache-policy-{cdk.Aws.ACCOUNT_ID}-{cdk.Aws.REGION}",
                                                                                                          cookie_behavior=cloudfront.CacheCookieBehavior.all(),
                                                                                                          query_string_behavior=cloudfront.CacheQueryStringBehavior.all(),
                                                                                                          header_behavior=cloudfront.CacheHeaderBehavior.allow_list(
                                                                                                              'Origin',
                                                                                                              'Access-Control-Request-Method',
                                                                                                              'Access-Control-Request-Headers'),
                                                                                                          enable_accept_encoding_brotli=True,
                                                                                                          enable_accept_encoding_gzip=True
                                                                                                          ),
                                                                   "origin_request_policy": cloudfront.OriginRequestPolicy(
                                                                       self, id="mre-origin-request-policy",
                                                                       origin_request_policy_name=f"mre-origin-request-policy-{cdk.Aws.ACCOUNT_ID}-{cdk.Aws.REGION}",
                                                                       cookie_behavior=cloudfront.OriginRequestCookieBehavior.all(),
                                                                       query_string_behavior=cloudfront.OriginRequestQueryStringBehavior.all(),
                                                                       header_behavior=cloudfront.OriginRequestHeaderBehavior.allow_list(
                                                                           'Origin', 'Access-Control-Request-Method',
                                                                           'Access-Control-Request-Headers')
                                                                       )
                                                               }
                                                               )

        ##### END: S3 BUCKETS AND CF DISTRIBUTION #####

        ##### START: LAMBDA LAYERS #####

        # Upload all the zipped Lambda Layers to S3
        self.layer_deploy = s3_deploy.BucketDeployment(
            self,
            "LambdaLayerZipDeploy",
            destination_bucket=self.lambda_layer_bucket,
            sources=[
                s3_deploy.Source.asset(
                    path="lambda_layers"
                )
            ],
            memory_limit=512
        )

        # timecode Layer
        self.timecode_layer = _lambda.LayerVersion(
            self,
            "TimeCodeLayer",
            layer_version_name="aws_mre_timecode",
            description="Layer containing the TimeCode Lib",
            code=_lambda.Code.from_bucket(
                bucket=self.lambda_layer_bucket,
                key="timecode/timecode.zip"
            ),
            compatible_runtimes=[
                _lambda.Runtime.PYTHON_3_6,
                _lambda.Runtime.PYTHON_3_7,
                _lambda.Runtime.PYTHON_3_8
            ]
        )

        # Deploy timecode_layer after layers_deploy
        self.timecode_layer.node.add_dependency(self.layer_deploy)

        # ffmpeg Layer
        self.ffmpeg_layer = _lambda.LayerVersion(
            self,
            "FFMpegLayer",
            layer_version_name="aws_mre_ffmpeg",
            description="Layer containing the ffmpeg binary and ffmpeg-python library",
            code=_lambda.Code.from_bucket(
                bucket=self.lambda_layer_bucket,
                key="ffmpeg/ffmpeg.zip"
            ),
            compatible_runtimes=[
                _lambda.Runtime.PYTHON_3_6,
                _lambda.Runtime.PYTHON_3_7,
                _lambda.Runtime.PYTHON_3_8
            ]
        )

        # Deploy ffmpeg_layer after layers_deploy
        self.ffmpeg_layer.node.add_dependency(self.layer_deploy)

        # ffprobe Layer
        self.ffprobe_layer = _lambda.LayerVersion(
            self,
            "FFProbeLayer",
            layer_version_name="aws_mre_ffprobe",
            description="Layer containing the ffprobe binary",
            code=_lambda.Code.from_bucket(
                bucket=self.lambda_layer_bucket,
                key="ffprobe/ffprobe.zip"
            ),
            compatible_runtimes=[
                _lambda.Runtime.PYTHON_3_6,
                _lambda.Runtime.PYTHON_3_7,
                _lambda.Runtime.PYTHON_3_8
            ]
        )

        # Deploy ffprobe_layer after layers_deploy
        self.ffprobe_layer.node.add_dependency(self.layer_deploy)

        # MediaReplayEngineWorkflowHelper Layer
        self.mre_workflow_helper_layer = _lambda.LayerVersion(
            self,
            "MediaReplayEngineWorkflowHelperLayer",
            layer_version_name="MediaReplayEngineWorkflowHelper",
            description="Layer containing the helper library (and its runtime dependencies) used by the Media Replay Engine internal lambda functions to interact with the control plane",
            code=_lambda.Code.from_bucket(
                bucket=self.lambda_layer_bucket,
                key="MediaReplayEngineWorkflowHelper/MediaReplayEngineWorkflowHelper.zip"
            ),
            compatible_runtimes=[
                _lambda.Runtime.PYTHON_3_8
            ]
        )

        # Deploy MediaReplayEngineWorkflowHelper after layers_deploy
        self.mre_workflow_helper_layer.node.add_dependency(self.layer_deploy)

        # MediaReplayEnginePluginHelper Layer
        self.mre_plugin_helper_layer = _lambda.LayerVersion(
            self,
            "MediaReplayEnginePluginHelperLayer",
            layer_version_name="MediaReplayEnginePluginHelper",
            description="Layer containing the helper library (and its runtime dependencies) to aid the development of custom plugins for the Media Replay Engine",
            code=_lambda.Code.from_bucket(
                bucket=self.lambda_layer_bucket,
                key="MediaReplayEnginePluginHelper/MediaReplayEnginePluginHelper.zip"
            ),
            compatible_runtimes=[
                _lambda.Runtime.PYTHON_3_8
            ]
        )

        # Deploy MediaReplayEnginePluginHelper after layers_deploy
        self.mre_plugin_helper_layer.node.add_dependency(self.layer_deploy)

        ##### END: LAMBDA LAYERS #####

        # EventBridge Event Bus for MRE
        self.eb_event_bus = events.EventBus(
            self,
            "AWSMREEventBus",
            event_bus_name="aws-mre-event-bus"
        )

        ##### START: LAMBDA FUNCTIONS AND ASSOCIATED IAM ROLES #####

        ### START: event-clip-generator LAMBDA ###

        self.event_media_convert_role = iam.Role(
            self,
            "MREMediaConvertIamRole",
            assumed_by=iam.ServicePrincipal("mediaconvert.amazonaws.com")
        )

        self.event_media_convert_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:Get*",
                    "s3:Describe*",
                    "s3:List*",
                    "s3:Put*",
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "cloudwatch:PutMetricAlarm",
                    "cloudwatch:DeleteAlarms",
                    "autoscaling:Describe*"
                ],
                resources=["*"]
            )
        )

        self.event_clip_gen_lambda_role = iam.Role(
            self,
            "MREEventClipGenIamRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        self.event_clip_gen_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "mediaconvert:Describe*",
                    "mediaconvert:Get*",
                    "mediaconvert:Create*"
                ],
                resources=["*"]
            )
        )

        self.event_clip_gen_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "events:DescribeEventBus",
                    "events:PutEvents"
                ],
                resources=[
                    f"arn:aws:events:*:*:event-bus/{self.eb_event_bus.event_bus_name}"
                ]
            )
        )

        self.event_clip_gen_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "execute-api:Invoke",
                    "execute-api:ManageConnections"
                ],
                resources=["arn:aws:execute-api:*:*:*"]
            )
        )

        self.event_clip_gen_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:DescribeParameters",
                    "ssm:GetParameter*"
                ],
                resources=["arn:aws:ssm:*:*:parameter/MRE*"]
            )
        )

        self.event_clip_gen_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:PassRole"
                ],
                resources=[
                    self.event_media_convert_role.role_arn
                ]
            )
        )

        # Function: ClipGen
        self.event_clip_generator_lambda = _lambda.Function(
            self,
            "Mre-ClipGenEventClipGenerator",
            description="Generates Clips for MRE events",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/EventClipGenerator"),
            handler="mre-event-clip-generator.GenerateClips",
            role=self.event_clip_gen_lambda_role,
            memory_size=512,
            timeout=cdk.Duration.minutes(15),
            environment={
                "MediaConvertRole": self.event_media_convert_role.role_arn,
                "OutputBucket": self.mre_media_output_bucket.bucket_name,
                "MediaConvertMaxInputJobs": "150",
                "EB_EVENT_BUS_NAME": self.eb_event_bus.event_bus_name
            },
            layers=[self.mre_workflow_helper_layer,
                    self.mre_plugin_helper_layer
                    ]
        )

        ### END: event-clip-generator LAMBDA ###

        ### START: event-data_export-generator LAMBDA ###
        self.event_data_export_lambda_role = iam.Role(
            self,
            "MREEventDataExportIamRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        self.event_data_export_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "events:DescribeEventBus",
                    "events:PutEvents"
                ],
                resources=[
                    f"arn:aws:events:*:*:event-bus/{self.eb_event_bus.event_bus_name}"
                ]
            )
        )

        self.event_data_export_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "s3:Get*",
                    "s3:Put*",
                    "s3:List*"
                ],
                resources=["*"]
            )
        )

        self.event_data_export_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "execute-api:Invoke",
                    "execute-api:ManageConnections"
                ],
                resources=["arn:aws:execute-api:*:*:*"]
            )
        )

        self.event_data_export_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:DescribeParameters",
                    "ssm:GetParameter*"
                ],
                resources=["arn:aws:ssm:*:*:parameter/MRE*"]
            )
        )

        self.event_data_export_lambda = _lambda.Function(
            self,
            "Mre-EventDataExportGenerator",
            description="Generates Mre data export",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/MreDataExport"),
            handler="mre_data_exporter.GenerateDataExport",
            role=self.event_data_export_lambda_role,
            memory_size=256,
            timeout=cdk.Duration.minutes(15),
            environment={
                "ExportOutputBucket": self.data_export_bucket.bucket_name,
                "EB_EVENT_BUS_NAME": self.eb_event_bus.event_bus_name
            },
            layers=[self.mre_workflow_helper_layer, self.mre_plugin_helper_layer]
        )

        
        ### END: event-data_export-generator LAMBDA ###

        ### START: EventHlsGenerator LAMBDA ###

        self.event_hls_gen_lambda_role = iam.Role(
            self,
            "MREEventHlsGeneratorIamRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        self.event_hls_gen_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "mediaconvert:Describe*",
                    "mediaconvert:Get*",
                    "mediaconvert:Create*",
                    "s3:Get*",
                    "s3:Put*",
                    "s3:List*"
                ],
                resources=["*"]
            )
        )

        self.event_hls_gen_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "execute-api:Invoke",
                    "execute-api:ManageConnections"
                ],
                resources=["arn:aws:execute-api:*:*:*"]
            )
        )

        self.event_hls_gen_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:DescribeParameters",
                    "ssm:GetParameter*"
                ],
                resources=["arn:aws:ssm:*:*:parameter/MRE*"]
            )
        )

        self.event_hls_create_manifest_lambda = _lambda.Function(
            self,
            "Mre-ClipGenEventHlsGenerator",
            description="Generates Hls Manifest for MRE events",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/EventHlsManifestGenerator"),
            handler="event_hls_manifest_gen.create_hls_manifest",
            role=self.event_hls_gen_lambda_role,
            memory_size=512,
            timeout=cdk.Duration.minutes(15),
            environment={
                "MediaConvertRole": self.event_media_convert_role.role_arn,
                "OutputBucket": self.mre_media_output_bucket.bucket_name,
                "MediaConvertMaxInputJobs": "150"
            },
            layers=[self.mre_workflow_helper_layer]
        )

        self.event_hls_media_convert_job_status_lambda = _lambda.Function(
            self,
            "MreEventHlsMediaConvertJobStatus",
            description="Checks if all MRE Media Convert Jobs for an event are complete",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/EventHlsManifestGenerator"),
            handler="event_hls_manifest_gen.media_convert_job_status",
            role=self.event_hls_gen_lambda_role,
            memory_size=256,
            timeout=cdk.Duration.minutes(5),
            environment={
                "MediaConvertRole": self.event_media_convert_role.role_arn,
                "OutputBucket": self.mre_media_output_bucket.bucket_name,
                "MediaConvertMaxInputJobs": "150"
            },
            layers=[self.mre_workflow_helper_layer]
        )

        ### END: EventHlsGenerator LAMBDA ###

        ### START: EventEdlGenerator LAMBDA ###

        self.event_edl_gen_lambda_role = iam.Role(
            self,
            "MREEventEdlGeneratorIamRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        self.event_edl_gen_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "s3:Get*",
                    "s3:Put*",
                    "s3:List*"
                ],
                resources=["*"]
            )
        )

        self.event_edl_gen_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "execute-api:Invoke",
                    "execute-api:ManageConnections"
                ],
                resources=["arn:aws:execute-api:*:*:*"]
            )
        )

        self.event_edl_gen_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:DescribeParameters",
                    "ssm:GetParameter*"
                ],
                resources=["arn:aws:ssm:*:*:parameter/MRE*"]
            )
        )

        self.event_edl_gen_lambda = _lambda.Function(
            self,
            "Mre-ClipGenEventEdlGenerator",
            description="Generates EDL representation for Mre Event",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/EventEdlGenerator"),
            handler="mre_event_edl_gen.generate_edl",
            role=self.event_hls_gen_lambda_role,
            memory_size=256,
            timeout=cdk.Duration.minutes(10),
            environment={
                "OutputBucket": self.mre_media_output_bucket.bucket_name
            },
            layers=[self.mre_workflow_helper_layer,
                    self.mre_plugin_helper_layer,
                    self.timecode_layer
                    ]

        )

        ### END: EventEdlGenerator LAMBDA ###

        ### START: EventScheduler LAMBDA ###

        # MREEventSchedulerIamRole
        self.event_scheduler_lambda_role = iam.Role(
            self,
            "MREEventSchedulerIamRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # MREEventSchedulerIamRole: CloudWatch Logs permissions
        self.event_scheduler_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=["*"]
            )
        )

        self.event_scheduler_lambda_role.add_to_policy(
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
                    self.event_table.table_arn,
                    f"{self.event_table.table_arn}/index/*",
                    self.current_events_table.table_arn
                ]
            )
        )

        self.event_scheduler_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "events:DescribeEventBus",
                    "events:PutEvents"
                ],
                resources=[
                    f"arn:aws:events:*:*:event-bus/{self.eb_event_bus.event_bus_name}"
                ]
            )
        )

        # Function: TriggerMREWorkflow
        self.event_scheduler_lambda = _lambda.Function(
            self,
            "MreEventScheduler",
            description="Schedules Past/Future events for processing based in the Event Start time",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/EventScheduler"),
            handler="mre_event_scheduler.schedule_events_for_processing",
            role=self.event_scheduler_lambda_role,
            memory_size=256,
            timeout=cdk.Duration.minutes(5),
            environment={
                "EVENT_SCHEDULER_BOOTSTRAP_TIME_IN_MINS": "5",
                "EVENT_SCHEDULER_BUFFER_TIME_IN_MINS": "5",
                "EVENT_SCHEDULER_TIME_TO_LIVE_STREAM_IN_MINS": "1",
                "EVENT_SCHEDULER_PAST_EVENTS_IN_SCOPE": "TRUE",
                "EVENT_SCHEDULER_FUTURE_EVENTS_IN_SCOPE": "FALSE",
                "EVENT_SCHEDULER_PAST_EVENT_START_DATE_UTC": "%Y-%m-%d",
                "EVENT_SCHEDULER_PAST_EVENT_END_DATE_UTC": "%Y-%m-%d",
                "EVENT_SCHEDULER_CONCURRENT_EVENTS": "1",
                "CURRENT_EVENTS_TABLE_NAME": self.current_events_table.table_name,
                "EB_EVENT_BUS_NAME": self.eb_event_bus.event_bus_name,
                "EVENT_TABLE_NAME": self.event_table.table_name
            }
        )

        self.event_scheduler_lambda_cloudwatch_event = events.Rule(
            self,
            "Event-Scheduler-Lambda-Rule",
            description=
            "CloudWatch event trigger for MRE's Event Scheduler Lambda. Triggers every 1 Minute.",
            enabled=True,
            schedule=events.Schedule.rate(cdk.Duration.minutes(1)),
            targets=[events_targets.LambdaFunction(handler=self.event_scheduler_lambda)])

        ### END: EventScheduler LAMBDA ###

        ### START: TriggerMREWorkflow LAMBDA ###

        # Role: TriggerMREWorkflowLambdaRole
        self.trigger_mre_lambda_role = iam.Role(
            self,
            "TriggerMREWorkflowLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # TriggerMREWorkflowLambdaRole: CloudWatch Logs permissions
        self.trigger_mre_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=["*"]
            )
        )

        # TriggerMREWorkflowLambdaRole: SSM Parameter Store permissions
        self.trigger_mre_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:DescribeParameters",
                    "ssm:GetParameter*"
                ],
                resources=["arn:aws:ssm:*:*:parameter/MRE*"]
            )
        )

        # TriggerMREWorkflowLambdaRole: API Gateway Invoke permissions
        self.trigger_mre_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "execute-api:Invoke",
                    "execute-api:ManageConnections"
                ],
                resources=["arn:aws:execute-api:*:*:*"]
            )
        )

        # TriggerMREWorkflowLambdaRole: State Machine execute permissions
        self.trigger_mre_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "states:StartExecution"
                ],
                resources=[
                    "arn:aws:states:*:*:stateMachine:*"
                ]
            )
        )

        # Function: TriggerMREWorkflow
        self.trigger_mre_workflow_lambda = _lambda.Function(
            self,
            "TriggerMREWorkflow",
            description="Execute MRE StepFunction workflow for every HLS video segment (.ts) file stored by MediaLive in S3",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/TriggerMREWorkflow"),
            handler="lambda_function.lambda_handler",
            role=self.trigger_mre_lambda_role,
            memory_size=128,
            timeout=cdk.Duration.minutes(1),
            layers=[self.mre_workflow_helper_layer]
        )

        # S3 Event Source for TriggerMREWorkflow Lambda
        self.s3_event_source = _lambda_es.S3EventSource(
            bucket=self.medialive_s3_dest_bucket,
            events=[s3.EventType.OBJECT_CREATED],
            filters=[s3.NotificationKeyFilter(suffix=".ts")]
        )

        # Map the S3 Event Source with TriggerMREWorkflow Lambda
        self.trigger_mre_workflow_lambda.add_event_source(self.s3_event_source)

        ### END: TriggerMREWorkflow LAMBDA ###

        ### START: ProbeVideo LAMBDA ###

        # Role: ProbeVideoLambdaRole
        self.probe_video_lambda_role = iam.Role(
            self,
            "ProbeVideoLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # ProbeVideoLambdaRole: CloudWatch Logs permissions
        self.probe_video_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=["*"]
            )
        )

        # ProbeVideoLambdaRole: SSM Parameter Store permissions
        self.probe_video_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:DescribeParameters",
                    "ssm:GetParameter*"
                ],
                resources=["arn:aws:ssm:*:*:parameter/MRE*"]
            )
        )

        # ProbeVideoLambdaRole: API Gateway Invoke permissions
        self.probe_video_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "execute-api:Invoke",
                    "execute-api:ManageConnections"
                ],
                resources=["arn:aws:execute-api:*:*:*"]
            )
        )

        # Function: ProbeVideo
        self.probe_video_lambda = _lambda.Function(
            self,
            "ProbeVideo",
            description="Probe the HLS video segment (.ts) file to extract metadata about the video segment and all the key frames in it",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/ProbeVideo"),
            handler="lambda_function.lambda_handler",
            role=self.probe_video_lambda_role,
            memory_size=1024,
            timeout=cdk.Duration.minutes(15),
            layers=[
                self.ffmpeg_layer,
                self.ffprobe_layer,
                self.mre_workflow_helper_layer,
                self.mre_plugin_helper_layer
            ]
        )

        ### END: ProbeVideo LAMBDA ###

        ### START: MultiChunkHelper LAMBDA ###

        # Role: MultiChunkHelperLambdaRole
        self.multi_chunk_helper_lambda_role = iam.Role(
            self,
            "MultiChunkHelperLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # MultiChunkHelperLambdaRole: CloudWatch Logs permissions
        self.multi_chunk_helper_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=["*"]
            )
        )

        # MultiChunkHelperLambdaRole: SSM Parameter Store permissions
        self.multi_chunk_helper_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:DescribeParameters",
                    "ssm:GetParameter*"
                ],
                resources=["arn:aws:ssm:*:*:parameter/MRE*"]
            )
        )

        # MultiChunkHelperLambdaRole: API Gateway Invoke permissions
        self.multi_chunk_helper_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "execute-api:Invoke",
                    "execute-api:ManageConnections"
                ],
                resources=["arn:aws:execute-api:*:*:*"]
            )
        )

        # Function: MultiChunkHelper
        self.multi_chunk_helper_lambda = _lambda.Function(
            self,
            "MultiChunkHelper",
            description="Check the completion status of a Classifier/Optimizer plugin in the prior AWS Step Function workflow executions",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/MultiChunkHelper"),
            handler="lambda_function.lambda_handler",
            role=self.multi_chunk_helper_lambda_role,
            memory_size=128,
            timeout=cdk.Duration.minutes(1),
            layers=[
                self.mre_workflow_helper_layer,
                self.mre_plugin_helper_layer
            ]
        )

        ### END: MultiChunkHelper LAMBDA ###

        ### START: PluginOutputHandler LAMBDA ###

        # Role: PluginOutputHandlerLambdaRole
        self.plugin_output_handler_lambda_role = iam.Role(
            self,
            "PluginOutputHandlerLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # PluginOutputHandlerLambdaRole: CloudWatch Logs permissions
        self.plugin_output_handler_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=["*"]
            )
        )

        # PluginOutputHandlerLambdaRole: SSM Parameter Store permissions
        self.plugin_output_handler_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:DescribeParameters",
                    "ssm:GetParameter*"
                ],
                resources=["arn:aws:ssm:*:*:parameter/MRE*"]
            )
        )

        # PluginOutputHandlerLambdaRole: API Gateway Invoke permissions
        self.plugin_output_handler_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "execute-api:Invoke",
                    "execute-api:ManageConnections"
                ],
                resources=["arn:aws:execute-api:*:*:*"]
            )
        )

        # Function: PluginOutputHandler
        self.plugin_output_handler_lambda = _lambda.Function(
            self,
            "PluginOutputHandler",
            description="Handle the output of a plugin based on its execution status",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/PluginOutputHandler"),
            handler="lambda_function.lambda_handler",
            role=self.plugin_output_handler_lambda_role,
            memory_size=128,
            timeout=cdk.Duration.minutes(1),
            layers=[
                self.mre_workflow_helper_layer,
                self.mre_plugin_helper_layer
            ]
        )

        ### END: PluginOutputHandler LAMBDA ###

        ### START: WorkflowErrorHandler LAMBDA ###

        # Role: WorkflowErrorHandlerLambdaRole
        self.workflow_error_handler_lambda_role = iam.Role(
            self,
            "WorkflowErrorHandlerLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # WorkflowErrorHandlerLambdaRole: CloudWatch Logs permissions
        self.workflow_error_handler_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=["*"]
            )
        )

        # WorkflowErrorHandlerLambdaRole: SSM Parameter Store permissions
        self.workflow_error_handler_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:DescribeParameters",
                    "ssm:GetParameter*"
                ],
                resources=["arn:aws:ssm:*:*:parameter/MRE*"]
            )
        )

        # WorkflowErrorHandlerLambdaRole: API Gateway Invoke permissions
        self.workflow_error_handler_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "execute-api:Invoke",
                    "execute-api:ManageConnections"
                ],
                resources=["arn:aws:execute-api:*:*:*"]
            )
        )

        # WorkflowErrorHandlerLambdaRole: EventBridge permissions
        self.workflow_error_handler_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "events:DescribeEventBus",
                    "events:PutEvents"
                ],
                resources=[
                    f"arn:aws:events:*:*:event-bus/{self.eb_event_bus.event_bus_name}"
                ]
            )
        )

        # Function: WorkflowErrorHandler
        self.workflow_error_handler_lambda = _lambda.Function(
            self,
            "WorkflowErrorHandler",
            description="Handle exceptions caught by the AWS Step Function workflow and optionally update the execution status of the Classifier plugin",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/WorkflowErrorHandler"),
            handler="lambda_function.lambda_handler",
            role=self.workflow_error_handler_lambda_role,
            memory_size=128,
            timeout=cdk.Duration.minutes(1),
            layers=[
                self.mre_workflow_helper_layer,
                self.mre_plugin_helper_layer
            ],
            environment={
                "EB_EVENT_BUS_NAME": self.eb_event_bus.event_bus_name
            }
        )

        ### END: WorkflowErrorHandler LAMBDA ###

        ### START: EventCompletionHandler LAMBDA ###

        # Role: EventCompletionHandlerLambdaRole
        self.event_completion_handler_role = iam.Role(
            self,
            "EventCompletionHandlerLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # EventCompletionHandlerLambdaRole: CloudWatch Logs permissions
        self.event_completion_handler_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=["*"]
            )
        )

        # EventCompletionHandlerLambdaRole: SSM Parameter Store permissions
        self.event_completion_handler_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:DescribeParameters",
                    "ssm:GetParameter*"
                ],
                resources=["arn:aws:ssm:*:*:parameter/MRE*"]
            )
        )

        # EventCompletionHandlerLambdaRole: API Gateway Invoke permissions
        self.event_completion_handler_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "execute-api:Invoke",
                    "execute-api:ManageConnections"
                ],
                resources=["arn:aws:execute-api:*:*:*"]
            )
        )

        # EventCompletionHandlerLambdaRole: MediaLive permissions
        self.event_completion_handler_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "medialive:List*",
                    "medialive:Describe*",
                    "medialive:Stop*"
                ],
                resources=["*"]
            )
        )

        # Function: EventCompletionHandler
        self.event_completion_handler_lambda = _lambda.Function(
            self,
            "EventCompletionHandler",
            description="Update the status of an MRE event to Complete based on the configured CloudWatch EventBridge triggers",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/EventCompletionHandler"),
            handler="lambda_function.lambda_handler",
            role=self.event_completion_handler_role,
            memory_size=128,
            timeout=cdk.Duration.minutes(1),
            layers=[self.mre_workflow_helper_layer]
        )

        ### END: EventCompletionHandler LAMBDA ###

        ##### END: LAMBDA FUNCTIONS AND ASSOCIATED IAM ROLES #####

        # Step Function IAM Role
        self.sfn_role = iam.Role(
            self,
            "StepFunctionRole",
            assumed_by=iam.ServicePrincipal(service="states.amazonaws.com"),
            description="Service role for the AWS MRE Step Functions"
        )

        # Step Function IAM Role: X-Ray permissions
        self.sfn_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets"
                ],
                resources=[
                    "*"
                ]
            )
        )

        # Step Function IAM Role: Lambda permissions
        self.sfn_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "lambda:InvokeFunction"
                ],
                resources=[
                    "*"
                ]
            )
        )

        # Step Function IAM Role: State Machine execute permissions
        self.sfn_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "states:StartExecution"
                ],
                resources=[
                    "arn:aws:states:*:*:stateMachine:*"
                ]
            )
        )

        # Chalice IAM Role
        self.chalice_role = iam.Role(
            self,
            "ChaliceRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE Control Plane Chalice Lambda function"
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
                    self.replayrequest_table.table_arn,
                    self.system_table.table_arn,
                    self.content_group_table.table_arn,
                    self.program_table.table_arn,
                    self.plugin_table.table_arn,
                    f"{self.plugin_table.table_arn}/index/*",
                    self.profile_table.table_arn,
                    self.model_table.table_arn,
                    f"{self.model_table.table_arn}/index/*",
                    self.event_table.table_arn,
                    f"{self.event_table.table_arn}/index/*",
                    self.workflow_exec_table.table_arn,
                    self.current_events_table.table_arn
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

        # Chalice IAM Role: Step Function permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "states:CreateStateMachine",
                    "states:ListStateMachines",
                    "states:UpdateStateMachine",
                    "states:DeleteStateMachine",
                    "states:TagResource"
                ],
                resources=[
                    "arn:aws:states:*:*:*"
                ]
            )
        )

        # Chalice IAM Role: Step Function PassRole permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:PassRole"
                ],
                resources=[
                    self.sfn_role.role_arn
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

        # Chalice IAM Role: EventBridge permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "events:DescribeEventBus",
                    "events:PutEvents"
                ],
                resources=[
                    f"arn:aws:events:*:*:event-bus/{self.eb_event_bus.event_bus_name}"
                ]
            )
        )

       

        # SQS Queue used to harvest HLS Streams
        self.sqs_event_to_harvest_queue = sqs.Queue(
            self,
            "MREEventHarvestingQueue",
            retention_period=cdk.Duration.days(7),
            visibility_timeout=cdk.Duration.minutes(5),
            encryption=sqs.QueueEncryption.KMS_MANAGED
        )

        # SQS Queue used to Notify when Resource allocation to Harvest HLS Streams
        self.sqs_event_harvest_failure_queue = sqs.Queue(
            self,
            "MREEventHarvestProcessFailureQueue",
            retention_period=cdk.Duration.days(7),
            visibility_timeout=cdk.Duration.minutes(5),
            encryption=sqs.QueueEncryption.KMS_MANAGED
        )

        # EventBridge: MRE Event Scheduler Events Rule
        self.mre_event_scheduler_events_rule = events.Rule(
            self,
            "MREEventSchedulerHarvestSoonRule",
            description="Rule that captures Event Scheduler events (PAST_EVENT_TO_BE_HARVESTED, FUTURE_EVENT_TO_BE_HARVESTED). Tie this to Event Processing logic.",
            enabled=True,
            event_bus=self.eb_event_bus,
            event_pattern=events.EventPattern(
                source=["awsmre"],
                detail={
                    "State": ["PAST_EVENT_TO_BE_HARVESTED", "FUTURE_EVENT_TO_BE_HARVESTED"]
                }
            )
        )

        # EventBridge: MRE Event Scheduler Events Rule
        self.mre_event_scheduler_events_rule = events.Rule(
            self,
            "MREEventSchedulerHarvestNowRule",
            description="Rule that captures Event Scheduler events (FUTURE_EVENT_HARVEST_NOW, PAST_EVENT_HARVEST_NOW) and outputs them to sqs_event_to_harvest_queue",
            enabled=True,
            event_bus=self.eb_event_bus,
            event_pattern=events.EventPattern(
                source=["awsmre"],
                detail={
                    "State": ["FUTURE_EVENT_HARVEST_NOW", "PAST_EVENT_HARVEST_NOW"]
                }
            ),
            targets=[
                events_targets.SqsQueue(
                    queue=self.sqs_event_to_harvest_queue
                )
            ]
        )

        # Store the EventBridge Event Bus name in SSM Parameter Store
        ssm.StringParameter(
            self,
            "MREEventBridgeBusName",
            string_value=self.eb_event_bus.event_bus_name,
            parameter_name="/MRE/EventBridge/EventBusName",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the Amazon EventBridge Event Bus name used by AWS MRE"
        )

        # SQS Queue to capture MRE Event deletion notifications
        self.sqs_queue = sqs.Queue(
            self,
            "MREEventDeletionQueue",
            retention_period=cdk.Duration.days(7),
            visibility_timeout=cdk.Duration.minutes(20),
            encryption=sqs.QueueEncryption.KMS_MANAGED
        )

        # Chalice IAM Role: SQS permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sqs:SendMessage"
                ],
                resources=[
                    f"arn:aws:sqs:*:*:{self.sqs_queue.queue_name}"
                ]
            )
        )

        # Store the SQS Queue ARN in SSM Parameter Store
        ssm.StringParameter(
            self,
            "MREEventDeletionQueueARN",
            string_value=self.sqs_queue.queue_arn,
            parameter_name="/MRE/ControlPlane/EventDeletionQueueARN",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the ARN of SQS Queue used by AWS MRE to send Event deletion notifications"
        )

        secret_cloudfront_private_key = secret_mgr.Secret(self, "MRE_CLOUDFRONT_COOKIE_PRIVATE_KEY",
                                                          secret_name="mre_cloudfront_cookie_private_key")
        secret_cloudfront_private_key.grant_read(self.chalice_role)

        secret_cloudfront_key_pair_id = secret_mgr.Secret(self, "MRE_CLOUDFRONT_KEY_PAIR_ID",
                                                          secret_name="mre_cloudfront_key_pair_id")
        secret_cloudfront_key_pair_id.grant_read(self.chalice_role)

        hsa_api_auth_secret = secret_mgr.Secret(self, "MRE_HSA_API_AUTH_SECRET", secret_name="mre_hsa_api_auth_secret")
        hsa_api_auth_secret.grant_read(self.chalice_role)

        # Chalice IAM Role: Secrets Manager permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret"
                ],
                resources=[
                    secret_cloudfront_private_key.secret_arn,
                    secret_cloudfront_key_pair_id.secret_arn,
                    hsa_api_auth_secret.secret_arn
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

        # EventBridge: MediaLive STOPPED State Change Rule
        self.medialive_eb_rule = events.Rule(
            self,
            "MediaLiveStoppedStateChangeRule",
            description="Rule used by AWS MRE to update the status of an Event to Complete when the MediaLive channel is stopped",
            enabled=True,
            event_pattern=events.EventPattern(
                source=["aws.medialive"],
                detail_type=["MediaLive Channel State Change"],
                detail={
                    "state": ["STOPPED"]
                }
            ),
            targets=[
                events_targets.LambdaFunction(
                    handler=self.event_completion_handler_lambda
                )
            ]
        )

        # EventBridge: MediaLive InputVideoFrameRate Metric Alarm Rule
        self.medialive_alarm_rule = events.Rule(
            self,
            "MediaLiveMetricAlarmRule",
            description="Rule used by AWS MRE to update the status of an Event to Complete based on the MediaLive InputVideoFrameRate CloudWatch metric alarm",
            enabled=True,
            event_pattern=events.EventPattern(
                source=["aws.cloudwatch"],
                detail_type=["CloudWatch Alarm State Change"],
                detail={
                    "alarmName": [
                        {
                            "prefix": "AWS_MRE"
                        }
                    ],
                    "state": {
                        "value": ["ALARM"]
                    }
                }
            ),
            targets=[
                events_targets.LambdaFunction(
                    handler=self.event_completion_handler_lambda
                )
            ]
        )

        # Get MediaConvert Regional Endpoint via an AWS SDK call
        self.mediaconvert_endpoints = cr.AwsCustomResource(
            self,
            "MediaConvertCustomResource",
            policy=cr.AwsCustomResourcePolicy.from_statements(
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=["mediaconvert:DescribeEndpoints"],
                        resources=["arn:aws:mediaconvert:*:*:*"]
                    )
                ]
            ),
            on_create=cr.AwsSdkCall(
                action="describeEndpoints",
                service="MediaConvert",
                physical_resource_id=cr.PhysicalResourceId.of(id="MediaConvertCustomResourceAwsSdkCall")
            ),
            on_update=cr.AwsSdkCall(
                action="describeEndpoints",
                service="MediaConvert",
                physical_resource_id=cr.PhysicalResourceId.of(id="MediaConvertCustomResourceAwsSdkCall")
            )
        )

        # Store the MediaConvert Regional endpoint in SSM Parameter Store
        ssm.StringParameter(
            self,
            "MediaConvertRegionalEndpoint",
            string_value=self.mediaconvert_endpoints.get_response_field(data_path="Endpoints.0.Url"),
            parameter_name="/MRE/ClipGen/MediaConvertEndpoint",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Contains Media Convert Endpoint required for MRE Clip Generation"
        )

        # START: Step function definition for ClipGeneration

        # Step Function IAM Role
        self.sfn_clip_gen_role = iam.Role(
            self,
            "EventClipGenerationStepFunctionRole",
            assumed_by=iam.ServicePrincipal(service="states.amazonaws.com"),
            description="Service role for MRE Clip Generation Step Functions"
        )

        # Step Function IAM Role: X-Ray permissions
        self.sfn_clip_gen_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets"
                ],
                resources=[
                    "*"
                ]
            )
        )

        # Step Function IAM Role: Lambda permissions
        self.sfn_clip_gen_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "lambda:InvokeFunction",
                    "lambda:List*",
                    "lambda:Read*",
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=[
                    "*"
                ]
            )
        )

        self.sfn_clip_gen_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:PassRole"
                ],
                resources=[
                    self.event_media_convert_role.role_arn
                ]
            )
        )

        generateClipsTask = tasks.LambdaInvoke(
            self,
            "GenerateClips",
            lambda_function=_lambda.Function.from_function_arn(self, 'GenerateClipsLambda',
                                                               self.event_clip_generator_lambda.function_arn),
            retry_on_service_exceptions=True,
            result_path="$.ClipGen"
        )

        getJobStatusTask = tasks.LambdaInvoke(
            self,
            "GetJobStatus",
            lambda_function=_lambda.Function.from_function_arn(self, 'GetJobStatusLambda',
                                                               self.event_hls_media_convert_job_status_lambda.function_arn),
            result_path="$.JobStatus"
        )

        createHlsManifestTask = tasks.LambdaInvoke(
            self,
            "CreateHlsManifest",
            lambda_function=_lambda.Function.from_function_arn(self, 'CreateHlsManifestLambda',
                                                               self.event_hls_create_manifest_lambda.function_arn),
            result_path="$.ClipsGenerated"
        )

        waitTenSecondsTask = sfn.Wait(
            self,
            "wait_10_seconds",
            time=sfn.WaitTime.duration(cdk.Duration.seconds(10))
        )

        doneTask = sfn.Pass(
            self,
            "Done",
        )

        definition = generateClipsTask.next(getJobStatusTask.next(sfn.Choice(
            self,
            "AreAllHLSJobsComplete"
        ).when(sfn.Condition.string_equals("$.JobStatus.Payload.Status", "Complete"),
               createHlsManifestTask.next(doneTask)).otherwise(waitTenSecondsTask.next(getJobStatusTask))))

        self.state_machine = sfn.StateMachine(
            self,
            'mre-Event-Clip-Generator-StateMachine',
            definition=definition,
            role=self.sfn_clip_gen_role
        )


        #self.event_edl_gen_lambda
        self.mre_edlgen_events_rule = events.Rule(
            self,
            "MREEventEndRule",
            description="Rule that captures the MRE Lifecycle Event EVENT_END",
            enabled=True,
            event_bus=self.eb_event_bus,
            event_pattern=events.EventPattern(
                source=["awsmre"],
                detail={
                    "State":  ["EVENT_END"]
                }
            ),
            targets=[
                events_targets.LambdaFunction(
                    handler=self.event_edl_gen_lambda
                )
            ]
        )
        self.mre_edlgen_events_rule.node.add_dependency(self.eb_event_bus)
        self.mre_edlgen_events_rule.node.add_dependency(self.event_edl_gen_lambda)


        #self.event_edl_gen_lambda
        self.mre_event_data_export_rule = events.Rule(
            self,
            "MREEventDataExportRule",
            description="Rule that captures the MRE Lifecycle Event CLIP_GEN_DONE and REPLAY_PROCESSED - Data Export",
            enabled=True,
            event_bus=self.eb_event_bus,
            event_pattern=events.EventPattern(
                source=["awsmre"],
                detail={
                    "State":  ["CLIP_GEN_DONE", "REPLAY_PROCESSED"]
                }
            ),
            targets=[
                events_targets.LambdaFunction(
                    handler=self.event_data_export_lambda
                )
            ]
        )
        self.mre_event_data_export_rule.node.add_dependency(self.eb_event_bus)
        self.mre_event_data_export_rule.node.add_dependency(self.event_data_export_lambda)


        


        # END: Step function definition for ClipGeneration

        ### START: CreateReplay LAMBDA ###

        self.replay_lambda_role = iam.Role(
            self,
            "MREReplayIamRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        self.replay_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "events:DescribeEventBus",
                    "events:PutEvents"
                ],
                resources=[
                    f"arn:aws:events:*:*:event-bus/{self.eb_event_bus.event_bus_name}"
                ]
            )
        )

        self.replay_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "mediaconvert:Describe*",
                    "mediaconvert:Get*",
                    "mediaconvert:Create*",
                    "s3:Get*",
                    "s3:Put*",
                    "s3:List*"
                ],
                resources=["*"]
            )
        )

        self.replay_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "execute-api:Invoke",
                    "execute-api:ManageConnections"
                ],
                resources=["arn:aws:execute-api:*:*:*"]
            )
        )

        self.replay_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:DescribeParameters",
                    "ssm:GetParameter*"
                ],
                resources=["arn:aws:ssm:*:*:parameter/MRE*"]
            )
        )

        self.replay_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:PassRole"
                ],
                resources=[
                    self.event_media_convert_role.role_arn
                ]
            )
        )

        self.replay_media_convert_accelerated_queue = media_convert.CfnQueue(
            self,
            "mre-replay-hls-accelerated-queue",
            description="Accelerated queue for MRE Replay HLS jobs",
            name="mre-replay-hls-accelerated-queue")

        self.replay_environment_config = {
            "MediaConvertRole": self.event_media_convert_role.role_arn,
            "OutputBucket": self.mre_media_output_bucket.bucket_name,
            "MediaConvertMaxInputJobs": "150",
            "MediaConvertAcceleratorQueueArn": self.replay_media_convert_accelerated_queue.attr_arn,
            "EB_EVENT_BUS_NAME": self.eb_event_bus.event_bus_name
        }

        # Function: CreateReplay
        self.create_replay_lambda = _lambda.Function(
            self,
            "MRE-replay-CreateReplay",
            description="MRE - Creates Replay for MRE events",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/Replay"),
            handler="replay_lambda.CreateReplay",
            role=self.replay_lambda_role,
            memory_size=256,
            timeout=cdk.Duration.minutes(15),
            environment=self.replay_environment_config,
            layers=[self.mre_workflow_helper_layer,
                    self.mre_plugin_helper_layer
                    ]
        )

        # Function: GetEligibleReplays
        self.get_eligible_replays_lambda = _lambda.Function(
            self,
            "MRE-replay-GetEligibleReplays",
            description="MRE - Gets eligible replays for an MRE event",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/Replay"),
            handler="replay_lambda.GetEligibleReplays",
            role=self.replay_lambda_role,
            memory_size=256,
            timeout=cdk.Duration.minutes(6),
            environment=self.replay_environment_config,
            layers=[self.mre_workflow_helper_layer,
                    self.mre_plugin_helper_layer
                    ]
        )

        # Function: MarkReplayComplete
        self.mark_replay_complete_lambda = _lambda.Function(
            self,
            "MRE-replay-MarkReplayComplete",
            description="MRE - Mark a Replay status as Complete",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/Replay"),
            handler="replay_lambda.mark_replay_complete",
            role=self.replay_lambda_role,
            memory_size=256,
            timeout=cdk.Duration.minutes(6),
            environment=self.replay_environment_config,
            layers=[self.mre_workflow_helper_layer,
                    self.mre_plugin_helper_layer
                    ]
        )

        # Function: GenerateMasterPlaylist
        self.generate_master_playlist_lambda = _lambda.Function(
            self,
            "MRE-replay-GenerateMasterPlaylist",
            description="MRE - Creates a HLS Master Playlist manifest",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/Replay"),
            handler="replay_lambda.generate_master_playlist",
            role=self.replay_lambda_role,
            memory_size=256,
            timeout=cdk.Duration.minutes(14),
            environment=self.replay_environment_config,
            layers=[self.mre_workflow_helper_layer,
                    self.mre_plugin_helper_layer
                    ]
        )

        # Function: GenerateHlsClips
        self.generate_hls_clips_lambda = _lambda.Function(
            self,
            "MRE-replay-GenerateHlsClips",
            description="MRE - Creates HLS Clips",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/Replay"),
            handler="replay_lambda.generate_hls_clips",
            role=self.replay_lambda_role,
            memory_size=256,
            timeout=cdk.Duration.minutes(14),
            environment=self.replay_environment_config,
            layers=[self.mre_workflow_helper_layer,
                    self.mre_plugin_helper_layer
                    ]
        )

        # Function: check_Hls_job_status
        self.check_Hls_job_status_lambda = _lambda.Function(
            self,
            "MRE-replay-CheckHlsJobsStatus",
            description="MRE - Checks ths status of HLS Jobs",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/Replay"),
            handler="replay_lambda.check_Hls_job_status",
            role=self.replay_lambda_role,
            memory_size=256,
            timeout=cdk.Duration.minutes(14),
            environment=self.replay_environment_config,
            layers=[self.mre_workflow_helper_layer,
                    self.mre_plugin_helper_layer
                    ]
        )

        # Function: GenerateHlsClips
        self.generate_mp4_clips_lambda = _lambda.Function(
            self,
            "MRE-replay-GenerateMp4Clips",
            description="MRE - Creates MP4 replay Clips",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/Replay"),
            handler="replay_lambda.generate_mp4_clips",
            role=self.replay_lambda_role,
            memory_size=256,
            timeout=cdk.Duration.minutes(15),
            environment=self.replay_environment_config,
            layers=[self.mre_workflow_helper_layer,
                    self.mre_plugin_helper_layer
                    ]
        )

        # Function: check_mp4_job_status
        self.check_mp4_job_status_lambda = _lambda.Function(
            self,
            "MRE-replay-CheckMp4JobsStatus",
            description="MRE - Checks the status of Mp4 replay Jobs",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/Replay"),
            handler="replay_lambda.check_mp4_job_status",
            role=self.replay_lambda_role,
            memory_size=256,
            timeout=cdk.Duration.minutes(15),
            environment=self.replay_environment_config,
            layers=[self.mre_workflow_helper_layer,
                    self.mre_plugin_helper_layer
                    ]
        )

        # Function: Update replay with MP4 location
        self.update_replay_with_mp4_loc_lambda = _lambda.Function(
            self,
            "MRE-replay-UpdateReplayWithMp4Loc",
            description="MRE - Updates the replay request with the location of MP4 video",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset("lambda/Replay"),
            handler="replay_lambda.update_replay_with_mp4_location",
            role=self.replay_lambda_role,
            memory_size=256,
            timeout=cdk.Duration.minutes(5),
            environment=self.replay_environment_config,
            layers=[self.mre_workflow_helper_layer,
                    self.mre_plugin_helper_layer
                    ]
        )

        # Start: MRE Replay generation Step Function Definition

        self.replay_sfn_role = iam.Role(
            self,
            "ReplayGenStepFunctionRole",
            assumed_by=iam.ServicePrincipal(service="states.amazonaws.com"),
            description="Service role for the Replay Generation Step Functions"
        )

        # Step Function IAM Role: X-Ray permissions
        self.replay_sfn_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets"
                ],
                resources=[
                    "*"
                ]
            )
        )

        # Step Function IAM Role: Lambda permissions
        self.replay_sfn_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "lambda:InvokeFunction"
                ],
                resources=[
                    "*"
                ]
            )
        )

        getEligibleReplaysTask = tasks.LambdaInvoke(
            self,
            "GetEligibleReplays",
            lambda_function=_lambda.Function.from_function_arn(self, 'GetEligibleReplaysLambda',
                                                               self.get_eligible_replays_lambda.function_arn),
            retry_on_service_exceptions=True,
            result_path="$.ReplayResult"
        )

        createReplayTask = tasks.LambdaInvoke(
            self,
            "CreateReplay",
            lambda_function=_lambda.Function.from_function_arn(self, 'CreateReplayLambda',
                                                               self.create_replay_lambda.function_arn),
            retry_on_service_exceptions=True,
            result_path="$.CurrentReplayResult"
        )
        generateHlsClipsTask = tasks.LambdaInvoke(
            self,
            "CreateHlsJobs",
            lambda_function=_lambda.Function.from_function_arn(self, 'GenerateHlsClipsLambda',
                                                               self.generate_hls_clips_lambda.function_arn),
            result_path="$.CreateHlsJobsResult",
            retry_on_service_exceptions=True
        )

        checkHlsJobStatusTask = tasks.LambdaInvoke(
            self,
            "CheckHlsJobStatus",
            lambda_function=_lambda.Function.from_function_arn(self, 'CheckHlsJobStatusLambda',
                                                               self.check_Hls_job_status_lambda.function_arn),
            result_path="$.CheckHlsJobStatusResult",
            retry_on_service_exceptions=True
        )

        generateMasterPlaylistTask = tasks.LambdaInvoke(
            self,
            "GenerateMasterPlaylist",
            lambda_function=_lambda.Function.from_function_arn(self, 'GenerateMasterPlaylistLambda',
                                                               self.generate_master_playlist_lambda.function_arn),
            retry_on_service_exceptions=True
        )

        completeReplayTask = tasks.LambdaInvoke(
            self,
            "CompleteReplay",
            lambda_function=_lambda.Function.from_function_arn(self, 'MarkReplayCompleteLambda',
                                                               self.mark_replay_complete_lambda.function_arn),
            retry_on_service_exceptions=True
        )

        updateReplayWithMp4Task = tasks.LambdaInvoke(
            self,
            "UpdateReplayWithMp4Loc",
            lambda_function=_lambda.Function.from_function_arn(self, 'UpdateReplayWithMp4LocLambda',
                                                               self.update_replay_with_mp4_loc_lambda.function_arn),
            retry_on_service_exceptions=True
        )

        waitFiveSecondsTask = sfn.Wait(
            self,
            "wait_5_seconds",
            time=sfn.WaitTime.duration(cdk.Duration.seconds(5))
        )

        waitFiveSecondsTaskMp4 = sfn.Wait(
            self,
            "wait_5_seconds_mp4",
            time=sfn.WaitTime.duration(cdk.Duration.seconds(5))
        )

        allOkTask = sfn.Pass(
            self,
            "AllOk",
        )

        generateMp4ClipsTask = tasks.LambdaInvoke(
            self,
            "CreateMp4Jobs",
            lambda_function=_lambda.Function.from_function_arn(self, 'GenerateMp4ClipsLambda',
                                                               self.generate_mp4_clips_lambda.function_arn),
            result_path="$.CreateMp4JobsResult",
            retry_on_service_exceptions=True
        )

        checkMp4JobStatusTask = tasks.LambdaInvoke(
            self,
            "CheckMp4JobStatus",
            lambda_function=_lambda.Function.from_function_arn(self, 'CheckMp4JobStatusLambda',
                                                               self.check_mp4_job_status_lambda.function_arn),
            result_path="$.CheckMp4JobStatusResult",
            retry_on_service_exceptions=True
        )

        mapTask = sfn.Map(
            self,
            "Map",
            parameters={
                "detail.$": "$.detail",
                "ReplayRequest.$": "$$.Map.Item.Value"
            },
            items_path="$.ReplayResult.Payload.AllReplays",
            result_path="$.MapResult"
        )
        replay_definition = getEligibleReplaysTask.next(
            mapTask.iterator(
                createReplayTask.next(sfn.Choice(
                    self,
                    "GenerateReplayVideoOutput?"
                ).when(
                    sfn.Condition.and_(sfn.Condition.boolean_equals("$.ReplayRequest.CreateHls", True),
                                       sfn.Condition.string_equals("$.CurrentReplayResult.Payload.Status",
                                                                   "Replay Processed")),
                    generateHlsClipsTask.next(
                        checkHlsJobStatusTask.next(
                            sfn.Choice(self, "AreAllHlsJobsComplete?")
                                .when(
                                sfn.Condition.string_equals("$.CheckHlsJobStatusResult.Payload.Status", "Complete"),
                                generateMasterPlaylistTask.next(allOkTask))
                                .otherwise(waitFiveSecondsTask.next(checkHlsJobStatusTask)))))
                                      .when(
                    sfn.Condition.and_(sfn.Condition.boolean_equals("$.ReplayRequest.CreateMp4", True),
                                       sfn.Condition.string_equals("$.CurrentReplayResult.Payload.Status",
                                                                   "Replay Processed")),
                    generateMp4ClipsTask.next(
                        checkMp4JobStatusTask.next(
                            sfn.Choice(self, "AreAllMp4JobsComplete?")
                                .when(
                                sfn.Condition.string_equals("$.CheckMp4JobStatusResult.Payload.Status", "Complete"),
                                updateReplayWithMp4Task.next(allOkTask))
                                .otherwise(waitFiveSecondsTaskMp4.next(checkMp4JobStatusTask)))))
                                      .otherwise(allOkTask)
                                      )
            ).next(completeReplayTask)
        )

        self.replay_state_machine = sfn.StateMachine(
            self,
            'MRE-ReplayGenerationStateMachine',
            definition=replay_definition,
            role=self.replay_sfn_role
        )

        # EventBridge: ClipGen Events Rule
        self.mre_replay_events_rule = events.Rule(
            self,
            "MREReplayLifecycleEventsRule",
            description="Rule that captures all the MRE Lifecycle Events (Segmentation Status, Optimization Status, Event Status) and outputs them to Replay StateFunction",
            enabled=True,
            event_bus=self.eb_event_bus,
            event_pattern=events.EventPattern(
                source=["awsmre"],
                detail={
                    "State":  ["OPTIMIZED_SEGMENT_END", "SEGMENT_END", "EVENT_END", "REPLAY_CREATED"]
                }
            ),
            targets=[
                events_targets.SfnStateMachine(
                    machine=self.replay_state_machine
                )
            ]
        )

        self.mre_replay_events_rule.node.add_dependency(self.eb_event_bus)
        self.mre_replay_events_rule.node.add_dependency(self.replay_state_machine)

        # End: MRE Replay Step Function Definition

        self.chalice = Chalice(
            self,
            "ChaliceApp",
            source_dir=RUNTIME_SOURCE_DIR,
            stage_config={
                "environment_variables": {
                    "FRAMEWORK_VERSION": FRAMEWORK_VERSION,
                    "SYSTEM_TABLE_NAME": self.system_table.table_name,
                    "CONTENT_GROUP_TABLE_NAME": self.content_group_table.table_name,
                    "PROGRAM_TABLE_NAME": self.program_table.table_name,
                    "PLUGIN_TABLE_NAME": self.plugin_table.table_name,
                    "PLUGIN_NAME_INDEX": PLUGIN_NAME_INDEX,
                    "PLUGIN_VERSION_INDEX": PLUGIN_VERSION_INDEX,
                    "PROFILE_TABLE_NAME": self.profile_table.table_name,
                    "MODEL_TABLE_NAME": self.model_table.table_name,
                    "MODEL_NAME_INDEX": MODEL_NAME_INDEX,
                    "MODEL_VERSION_INDEX": MODEL_VERSION_INDEX,
                    "EVENT_TABLE_NAME": self.event_table.table_name,
                    "EVENT_CHANNEL_INDEX": EVENT_CHANNEL_INDEX,
                    "EVENT_CONTENT_GROUP_INDEX": EVENT_CONTENT_GROUP_INDEX,
                    "EVENT_PAGINATION_INDEX": EVENT_PAGINATION_INDEX,
                    "EVENT_PROGRAMID_INDEX": EVENT_PROGRAMID_INDEX,
                    "WORKFLOW_EXECUTION_TABLE_NAME": self.workflow_exec_table.table_name,
                    "REPLAY_REQUEST_TABLE_NAME": self.replayrequest_table.table_name,
                    "MEDIALIVE_S3_BUCKET": self.medialive_s3_dest_bucket.bucket_name,
                    "PROBE_VIDEO_LAMBDA_ARN": self.probe_video_lambda.function_arn,
                    "MULTI_CHUNK_HELPER_LAMBDA_ARN": self.multi_chunk_helper_lambda.function_arn,
                    "PLUGIN_OUTPUT_HANDLER_LAMBDA_ARN": self.plugin_output_handler_lambda.function_arn,
                    "WORKFLOW_ERROR_HANDLER_LAMBDA_ARN": self.workflow_error_handler_lambda.function_arn,
                    "SFN_ROLE_ARN": self.sfn_role.role_arn,
                    "EB_EVENT_BUS_NAME": self.eb_event_bus.event_bus_name,
                    "SQS_QUEUE_URL": self.sqs_queue.queue_url,
                    "HLS_HS256_API_AUTH_SECRET_KEY_NAME": "mre_hsa_api_auth_secret",
                    "CLOUDFRONT_COOKIE_PRIVATE_KEY_NAME": "mre_cloudfront_cookie_private_key",
                    "CLOUDFRONT_COOKIE_KEY_PAIR_ID_NAME": "mre_cloudfront_key_pair_id",
                    "HLS_STREAM_CLOUDFRONT_DISTRO": self.mre_media_output_distro.domain_name,
                    "CURRENT_EVENTS_TABLE_NAME": self.current_events_table.table_name,
                    "CLIP_GENERATION_STATE_MACHINE_ARN": self.state_machine.state_machine_arn

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
            "MREControlPlaneEndpointParam",
            string_value=self.chalice.sam_template.get_output("EndpointURL").value,
            parameter_name="/MRE/ControlPlane/EndpointURL",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the AWS MRE ControlPlane APIEndpoint URL used by the MRE Workflow helper library"
        )

        # Store the Workflow Execution DDB table ARN in SSM Parameter Store
        ssm.StringParameter(
            self,
            "MREWorkflowExecutionTableARN",
            string_value=self.workflow_exec_table.table_arn,
            parameter_name="/MRE/ControlPlane/WorkflowExecutionTableARN",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the ARN of the Workflow Execution DDB table used by the cleanup process following an Event deletion"
        )

        # Required for Updating the Content Security Policy for MRE Frontend
        ssm.StringParameter(
            self,
            "MREMediaOutputBucketName",
            string_value=self.mre_media_output_bucket.bucket_name,
            parameter_name="/MRE/ControlPlane/MediaOutputBucket",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the AWS MRE MediaOutput Bucket Name"
        )

        # Required for the Fan Experience Frontend
        ssm.StringParameter(
            self,
            "MREMediaOutputDistribution",
            string_value=self.mre_media_output_distro.domain_name,
            parameter_name="/MRE/ControlPlane/MediaOutputDistribution",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the AWS MRE MediaOutput CloudFront Distribution domain name"
        )
