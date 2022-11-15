
import os
import sys
from aws_cdk import (
    Aws,
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_dynamodb as ddb,
    aws_events as events,
    aws_events_targets as events_targets,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_s3 as s3,
    aws_s3_deployment as s3_deploy,
    aws_sqs as sqs,
    aws_ssm as ssm,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins
)

# Ask Python interpreter to search for modules in the topmost folder. This is required to access the shared.infrastructure.helpers module
sys.path.append('../../')
import shared.infrastructure.helpers.constants as constants

LAYERS_DIR = os.path.join(os.path.dirname(
    os.path.dirname(__file__)), os.pardir, '../layers')
TRANSITION_PREVIEW_VIDEO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), os.pardir, '../frontend/src/assets/videos')
TRANSITION_FADE_IN_OUT_IMAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), os.pardir, '../frontend/src/assets/TransitionsImg')

class MreSharedResources(Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.create_mre_event_bus()
        self.create_s3_buckets()
        self.upload_mre_transition_sample_videos()
        self.upload_mre_transition_fade_in_out_image()
        self.create_lambda_layers()
        self.create_media_convert_role()
        self.create_event_table()
        self.create_current_events_table()
        self.create_plugin_table()
        self.create_profile_table()
        self.create_model_table()
        self.create_workflow_exec_table()
        self.create_program_table()
        self.create_content_group_table()
        self.create_system_table()
        self.create_sqs_queues()
        self.create_cloudfront_distro()

    def create_cloudfront_distro(self):
        # Cloudfront Distro for Media Output
        self.mre_media_output_distro=cloudfront.Distribution(
            self, "mre-media-output",
            default_behavior = cloudfront.BehaviorOptions(
                origin=origins.S3Origin(self.mre_media_output_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy(
                    self, id="mre-cache-policy",
                    cache_policy_name=f"mre-cache-policy-{Aws.ACCOUNT_ID}-{Aws.REGION}",
                    cookie_behavior=cloudfront.CacheCookieBehavior.all(),
                    query_string_behavior=cloudfront.CacheQueryStringBehavior.all(),
                    header_behavior=cloudfront.CacheHeaderBehavior.allow_list(
                        'Origin',
                        'Access-Control-Request-Method',
                        'Access-Control-Request-Headers'),
                    enable_accept_encoding_brotli=True,
                    enable_accept_encoding_gzip=True
                ),
                origin_request_policy=cloudfront.OriginRequestPolicy(
                    self, id="mre-origin-request-policy",
                    origin_request_policy_name=f"mre-origin-request-policy-{Aws.ACCOUNT_ID}-{Aws.REGION}",
                    cookie_behavior=cloudfront.OriginRequestCookieBehavior.all(),
                    query_string_behavior=cloudfront.OriginRequestQueryStringBehavior.all(),
                    header_behavior=cloudfront.OriginRequestHeaderBehavior.allow_list(
                        'Origin', 'Access-Control-Request-Method',
                        'Access-Control-Request-Headers')
                ),
                response_headers_policy=cloudfront.ResponseHeadersPolicy(
                    self, "MreResponseHeadersPolicy",
                    response_headers_policy_name=f"mre-response-headers-policy-{Aws.ACCOUNT_ID}-{Aws.REGION}",
                    cors_behavior=cloudfront.ResponseHeadersCorsBehavior(
                        access_control_allow_credentials=False,
                        access_control_allow_headers=["*"],
                        access_control_allow_methods=["ALL"],
                        access_control_allow_origins=["*"],
                        access_control_expose_headers=["*"],
                        access_control_max_age=Duration.seconds(600),
                        origin_override=True
                    )
                )
            )
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

        CfnOutput(self, "mre-media-output-distro", value=self.mre_media_output_distro.domain_name,
                      description="Name of the MRE media output domain", export_name="mre-media-output-distro-domain-name")

    def create_system_table(self):
        # System Configuration Table
        self.system_table = ddb.Table(
            self,
            "System",
            partition_key=ddb.Attribute(
                name="Name",
                type=ddb.AttributeType.STRING
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        CfnOutput(self, "mre-system-table-arn", value=self.content_group_table.table_arn,
                      description="Arn of the MRE System table", export_name="mre-system-table-arn")
        CfnOutput(self, "mre-system-table-name", value=self.content_group_table.table_name,
                      description="Name of the MRE System table", export_name="mre-system-table-name")

    def create_content_group_table(self):
        # ContentGroup Table
        self.content_group_table = ddb.Table(
            self,
            "ContentGroup",
            partition_key=ddb.Attribute(
                name="Name",
                type=ddb.AttributeType.STRING
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )
        CfnOutput(self, "mre-content-group-table-arn", value=self.content_group_table.table_arn,
                      description="Arn of the MRE Content Group table", export_name="mre-content-group-table-arn")
        CfnOutput(self, "mre-content-group-table-name", value=self.content_group_table.table_name,
                      description="Name of the MRE Content Group table", export_name="mre-content-group-table-name")

    def create_program_table(self):
        # Program Table
        self.program_table = ddb.Table(
            self,
            "Program",
            partition_key=ddb.Attribute(
                name="Name",
                type=ddb.AttributeType.STRING
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        CfnOutput(self, "mre-program-exec-table-arn", value=self.program_table.table_arn,
                      description="Arn of the MRE Program table", export_name="mre-program-table-arn")
        CfnOutput(self, "mre-program-exec-table-name", value=self.program_table.table_name,
                      description="Name of the MRE Program table", export_name="mre-program-table-name")

    def create_workflow_exec_table(self):
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
            removal_policy=RemovalPolicy.DESTROY
        )

        CfnOutput(self, "mre-workflow-exec-table-arn", value=self.workflow_exec_table.table_arn,
                      description="Arn of the MRE Workflow Exec table", export_name="mre-workflow-exec-table-arn")
        CfnOutput(self, "mre-workflow-exec-table-name", value=self.workflow_exec_table.table_name,
                      description="Name of the MRE Workflow Exec table", export_name="mre-workflow-exec-table-name")

        # Store the Workflow Execution DDB table ARN in SSM Parameter Store
        ssm.StringParameter(
            self,
            "MREWorkflowExecutionTableARN",
            string_value=self.workflow_exec_table.table_arn,
            parameter_name="/MRE/ControlPlane/WorkflowExecutionTableARN",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the ARN of the Workflow Execution DDB table used by the cleanup process following an Event deletion"
        )

    def create_model_table(self):
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
            removal_policy=RemovalPolicy.DESTROY
        )

        # Model Table: Name GSI
        self.model_table.add_global_secondary_index(
            index_name=constants.MODEL_NAME_INDEX,
            partition_key=ddb.Attribute(
                name="Name",
                type=ddb.AttributeType.STRING
            )
        )

        # Model Table: Version GSI
        self.model_table.add_global_secondary_index(
            index_name=constants.MODEL_VERSION_INDEX,
            partition_key=ddb.Attribute(
                name="Version",
                type=ddb.AttributeType.STRING
            )
        )

        CfnOutput(self, "mre-model-table-arn", value=self.model_table.table_arn,
                      description="Arn of the MRE Model table", export_name="mre-model-table-arn")
        CfnOutput(self, "mre-model-table-name", value=self.model_table.table_name,
                      description="Name of the MRE Model table", export_name="mre-model-table-name")

    def create_profile_table(self):
        # Profile Table
        self.profile_table = ddb.Table(
            self,
            "Profile",
            partition_key=ddb.Attribute(
                name="Name",
                type=ddb.AttributeType.STRING
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        CfnOutput(self, "mre-profile-table-arn", value=self.profile_table.table_arn,
                      description="Arn of the MRE Profile table", export_name="mre-profile-table-arn")
        CfnOutput(self, "mre-profile-table-name", value=self.profile_table.table_name,
                      description="Name of the MRE Profile table", export_name="mre-profile-table-name")

    def create_mre_event_bus(self):
        # EventBridge Event Bus for MRE
        self.eb_event_bus = events.EventBus(
            self,
            "AWSMREEventBus",
            event_bus_name="aws-mre-event-bus"
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

        CfnOutput(self, "mre-event-bus", value=self.eb_event_bus.event_bus_arn,
                      description="Arn of the MRE Event Bus", export_name="mre-event-bus-arn")

    def create_s3_buckets(self):
        ##### START: S3 BUCKETS #####

        
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

        # MRE Media Source Bucket
        self.mre_media_source_bucket = s3.Bucket(
            self,
            "MreMediaSourceBucket",
            enforce_ssl=True,
            server_access_logs_bucket=self.access_log_bucket,
            server_access_logs_prefix='mre-mediasource-logs',
            encryption=s3.BucketEncryption.S3_MANAGED
        )

        # MRE Transitions Clip Bucket
        self.mre_transition_clip_bucket = s3.Bucket(
            self,
            'MreTransitionsClipBucket',
            enforce_ssl=True,
            server_access_logs_bucket=self.access_log_bucket,
            server_access_logs_prefix='mre-transitions-clips-logs',
            encryption=s3.BucketEncryption.S3_MANAGED
        )

        # Required for Updating the Content Security Policy for MRE Frontend
        ssm.StringParameter(
            self,
            "MreTransitionsClipBucketName",
            string_value=self.mre_transition_clip_bucket.bucket_name,
            parameter_name="/MRE/ControlPlane/TransitionClipBucket",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the AWS MRE Transition Clip Bucket Name"
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

        # Bucket for caching segments and related features from MRE workflows
        self.mre_segment_cache_bucket = s3.Bucket(
            self,
            "MreSegmentCacheBucket",
            enforce_ssl=True,
            server_access_logs_bucket=self.access_log_bucket,
            server_access_logs_prefix='mre-segmentcache-logs',
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

        # Required for Updating the Content Security Policy for MRE Frontend
        ssm.StringParameter(
            self,
            "MREMediaOutputBucketName",
            string_value=self.mre_media_output_bucket.bucket_name,
            parameter_name="/MRE/ControlPlane/MediaOutputBucket",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the AWS MRE MediaOutput Bucket Name"
        )
        CfnOutput(self, "mre-media-output-bucket", value=self.mre_media_output_bucket.bucket_name,
                      description="Name of the S3 Bucket used by MRE for MediaConvert",
                      export_name="mre-media-output-bucket-name")
        CfnOutput(self, "mre-data-export-bucket", value=self.data_export_bucket.bucket_name,
                      description="Name of the S3 bucket used by MRE to store exported data",
                      export_name="mre-data-export-bucket-name")
        CfnOutput(self, "mre-media-source-bucket", value=self.mre_media_source_bucket.bucket_name,
                      description="Name of the S3 bucket used to store HLS chunks to trigger MRE workflows",
                      export_name="mre-media-source-bucket-name")
        CfnOutput(self, "mre-segment-cache-bucket", value=self.mre_segment_cache_bucket.bucket_name,
                      description="Name of the S3 bucket used to cache segments and related features from MRE workflows",
                      export_name="mre-segment-cache-bucket-name")
        CfnOutput(self, "mre-transition-clips-bucket", value=self.mre_transition_clip_bucket.bucket_name,
                      description="Name of the S3 bucket used to store Transition clips when creating replays",
                      export_name="mre-transition-clips-bucket-name")
    

    def upload_mre_transition_sample_videos(self):

        self.layer_deploy = s3_deploy.BucketDeployment(
            self,
            "TransitionPreviewVideoDeploy",
            destination_bucket=self.mre_transition_clip_bucket,
            destination_key_prefix='FadeInFadeOut/preview',
            sources=[
                s3_deploy.Source.asset(
                    path=TRANSITION_PREVIEW_VIDEO_DIR
                )
            ],
            memory_limit=256
        )

    def upload_mre_transition_fade_in_out_image(self):

        self.layer_deploy = s3_deploy.BucketDeployment(
            self,
            "TransitionFadeInOutImageDeploy",
            destination_bucket=self.mre_transition_clip_bucket,
            destination_key_prefix='FadeInFadeOut/transition_images',
            sources=[
                s3_deploy.Source.asset(
                    path=TRANSITION_FADE_IN_OUT_IMAGE_DIR
                )
            ],
            memory_limit=256
        )

    def create_lambda_layers(self):
        ##### START: LAMBDA LAYERS #####

        # Upload all the zipped Lambda Layers to S3
        self.layer_deploy = s3_deploy.BucketDeployment(
            self,
            "LambdaLayerZipDeploy",
            destination_bucket=self.lambda_layer_bucket,
            sources=[
                s3_deploy.Source.asset(
                    path=LAYERS_DIR
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
            description=f"Layer containing the helper library (and its runtime dependencies) used by the Media Replay Engine internal lambda functions to interact with the control plane.",
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
            description=f"Layer containing the helper library (and its runtime dependencies) to aid the development of custom plugins for the Media Replay Engine.",
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

        CfnOutput(self, "mre-timecode-layer", value=self.timecode_layer.layer_version_arn,
                      description="contains the Arn for TimeCode Lambda Layer", export_name="mre-timecode-layer-arn")
        CfnOutput(self, "mre-ffmpeg-layer", value=self.ffmpeg_layer.layer_version_arn,
                      description="contains the Arn for ffmpeg Lambda Layer", export_name="mre-ffmpeg-layer-arn")
        CfnOutput(self, "mre-ffprobe-layer", value=self.ffprobe_layer.layer_version_arn,
                      description="contains the Arn for ffprobe Lambda Layer", export_name="mre-ffprobe-layer-arn")
        CfnOutput(self, "mre-workflow-helper-layer", value=self.mre_workflow_helper_layer.layer_version_arn,
                      description="contains the Arn for mre_workflow_helper Lambda Layer",
                      export_name="mre-workflow-helper-layer-arn")
        CfnOutput(self, "mre-plugin-helper-layer", value=self.mre_plugin_helper_layer.layer_version_arn,
                      description="contains the Arn for mre_plugin_helper Lambda Layer",
                      export_name="mre-plugin-helper-layer-arn")

        ##### END: LAMBDA LAYERS #####

    def create_media_convert_role(self):
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

        CfnOutput(self, "mre-event-media-convert-role", value=self.event_media_convert_role.role_arn,
                      description="Contains MediaConvert IAM Role Arn", export_name="mre-event-media-convert-role-arn")

    def create_current_events_table(self):
        # CurrentEvents Table
        self.current_events_table = ddb.Table(
            self,
            "CurrentEvents",
            partition_key=ddb.Attribute(
                name="EventId",
                type=ddb.AttributeType.STRING
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        CfnOutput(self, "mre-current-event-table-arn", value=self.current_events_table.table_arn,
                      description="Arn of CurrentEvents table", export_name="mre-current-event-table-arn")
        CfnOutput(self, "mre-current-event-table-name", value=self.current_events_table.table_name,
                      description="Name of CurrentEvents table", export_name="mre-current-event-table-name")

    

    def create_event_table(self):
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
            removal_policy=RemovalPolicy.DESTROY
        )

        # Event Table: Channel GSI
        self.event_table.add_global_secondary_index(
            index_name=constants.EVENT_CHANNEL_INDEX,
            partition_key=ddb.Attribute(
                name="Channel",
                type=ddb.AttributeType.STRING
            ),
            projection_type=ddb.ProjectionType.KEYS_ONLY
        )

        # Event Table: ProgramId GSI
        self.event_table.add_global_secondary_index(
            index_name=constants.EVENT_PROGRAMID_INDEX,
            partition_key=ddb.Attribute(
                name="ProgramId",
                type=ddb.AttributeType.STRING
            ),
            projection_type=ddb.ProjectionType.KEYS_ONLY
        )

        # Event Table: Program GSI
        self.event_table.add_global_secondary_index(
            index_name=constants.EVENT_PROGRAM_INDEX,
            partition_key=ddb.Attribute(
                name="Program",
                type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(
                name="Start",
                type=ddb.AttributeType.STRING
            ),
            projection_type=ddb.ProjectionType.KEYS_ONLY
        )

        # Event Table: ContentGroup GSI
        self.event_table.add_global_secondary_index(
            index_name=constants.EVENT_CONTENT_GROUP_INDEX,
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
            index_name=constants.EVENT_PAGINATION_INDEX,
            partition_key=ddb.Attribute(
                name="PaginationPartition",
                type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(
                name="Start",
                type=ddb.AttributeType.STRING
            )
        )

        ## Allow us to query the events for cases where a 
        self.event_table.add_global_secondary_index(
            index_name=constants.EVENT_BYOB_NAME_INDEX,
            partition_key=ddb.Attribute(
                name="SourceVideoBucket",
                type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(
                name="Name",
                type=ddb.AttributeType.STRING
            ),
            projection_type=ddb.ProjectionType.KEYS_ONLY
        )

        CfnOutput(self, "mre-event-table-name", value=self.event_table.table_name, description="Event table name",
                      export_name="mre-event-table-name")
        CfnOutput(self, "mre-event-table-arn", value=self.event_table.table_arn, description="Event table Arn",
                      export_name="mre-event-table-arn")

    def create_plugin_table(self):
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
            removal_policy=RemovalPolicy.DESTROY
        )

        # Plugin Table: Name GSI
        self.plugin_table.add_global_secondary_index(
            index_name=constants.PLUGIN_NAME_INDEX,
            partition_key=ddb.Attribute(
                name="Name",
                type=ddb.AttributeType.STRING
            )
        )

        # Plugin Table: Version GSI
        self.plugin_table.add_global_secondary_index(
            index_name=constants.PLUGIN_VERSION_INDEX,
            partition_key=ddb.Attribute(
                name="Version",
                type=ddb.AttributeType.STRING
            )
        )

        CfnOutput(self, "mre-plugin-table-arn", value=self.plugin_table.table_arn,
                      description="Arn of the MRE Plugin table", export_name="mre-plugin-table-arn")
        CfnOutput(self, "mre-plugin-table-name", value=self.plugin_table.table_name,
                      description="Name of the MRE Plugin table", export_name="mre-plugin-table-name")

    def create_sqs_queues(self):
        # SQS Queue used to harvest HLS Streams
        self.sqs_event_to_harvest_queue = sqs.Queue(
            self,
            "MREEventHarvestingQueue",
            retention_period=Duration.days(7),
            visibility_timeout=Duration.minutes(5),
            encryption=sqs.QueueEncryption.KMS_MANAGED
        )

        # SQS Queue used to Notify when Resource allocation to Harvest HLS Streams
        self.sqs_event_harvest_failure_queue = sqs.Queue(
            self,
            "MREEventHarvestProcessFailureQueue",
            retention_period=Duration.days(7),
            visibility_timeout=Duration.minutes(5),
            encryption=sqs.QueueEncryption.KMS_MANAGED
        )

        # SQS Queue to capture MRE Event deletion notifications
        self.sqs_queue = sqs.Queue(
            self,
            "MREEventDeletionQueue",
            retention_period=Duration.days(7),
            visibility_timeout=Duration.minutes(20),
            encryption=sqs.QueueEncryption.KMS_MANAGED
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

        CfnOutput(self, "mre-harvest-queue-name", value=self.sqs_event_to_harvest_queue.queue_name,
                      description="Name of the MRE Event Harvest Queue", export_name="mre-harvest-queue-name")
        CfnOutput(self, "mre-harvest-queue-arn", value=self.sqs_event_to_harvest_queue.queue_arn,
                      description="ARN of the MRE Event Harvest Queue", export_name="mre-harvest-queue-arn")
        CfnOutput(self, "mre-harvest-failure-queue-name", value=self.sqs_event_harvest_failure_queue.queue_name,
                      description="Name of the MRE Event Harvest Failure Queue",
                      export_name="mre-harvest-failure-queue-name")
        CfnOutput(self, "mre-event-deletion-queue-name", value=self.sqs_queue.queue_name,
                      description="Name of the MRE Event Deletion Queue", export_name="mre-event-deletion-queue-name")

    def create_event_bridge_rules(self):
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


        
