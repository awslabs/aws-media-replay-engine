import os
import sys
from aws_cdk import (
    Aws,
    CfnOutput,
    Duration,
    CustomResource,
    custom_resources as cr,
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
    aws_cloudfront_origins as origins,
    aws_secretsmanager as secret_mgr,
    SecretValue,
    aws_logs as logs
)
from cdk_nag import NagSuppressions

# Ask Python interpreter to search for modules in the topmost folder. This is required to access the shared.infrastructure.helpers module
sys.path.append("../../")
import shared.infrastructure.helpers.constants as constants

LAYERS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, "../layers"
)
TRANSITION_PREVIEW_VIDEO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    os.pardir,
    "../frontend/src/assets/videos",
)
TRANSITION_FADE_IN_OUT_IMAGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    os.pardir,
    "../frontend/src/assets/TransitionsImg",
)


class MreSharedResources(Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.create_hls_streaming_secrets()
        self.create_mre_event_bus()
        self.create_eb_schedule_execution_role()
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
        self.create_metadata_table()
        self.create_custom_priorities_table()

        # API Gateway - To write to CloudWatch logs in your account, create an Identity and Access Management (IAM) role and add the required permissions for CloudWatch.
        self.create_api_gateway_logging_role()

        # generative AI components
        if self.node.try_get_context("GENERATIVE_AI"):
            self.create_prompt_catalog_table()
            # Add more as required

        self.apply_cdk_nags()
    
    def create_api_gateway_logging_role(self):

        api_log_group = logs.LogGroup(
                self,
                "ApiGatewayLogGroup",
                log_group_name="/aws/apigateway/aws-mre-api-logs",
                removal_policy=RemovalPolicy.DESTROY
            )
        
        # Create IAM role for API Gateway logging
        api_gateway_log_role = iam.Role(
            self,
            "ApiGatewayLoggingRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
            description="Role for API Gateway to push logs to CloudWatch"
        )

        # Add permissions to write logs
        api_gateway_log_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                    "logs:PutLogEvents",
                    "logs:GetLogEvents",
                    "logs:FilterLogEvents"
                ],
                resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/apigateway/*",
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/apigateway/*:*"
                ]
            )
        )

        # Create Lambda function for the custom resource
        enable_logging_role = iam.Role(
            self,
            "EnableLoggingRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for Lambda to enable API Gateway logging"
        )
        enable_logging_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "apigateway:PUT",
                    "apigateway:GET",
                    "apigateway:PATCH",
                    "apigateway:POST"
                ],
                resources=["*"]
            )
        )
         # Add CloudWatch Logs permissions for Lambda
        enable_logging_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/lambda/*"
                ]
            )
        )

        enable_logging_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["iam:PassRole"],
                resources=[api_gateway_log_role.role_arn]  # Scope to specific role ARN
            )
        )

        # Create the custom resource provider
        provider = cr.Provider(
            self,
            "sharedEnableLoggingProvider2",
            on_event_handler=_lambda.Function(
                self,
                "SharedEnableApiLoggingHandler",
                runtime=_lambda.Runtime.PYTHON_3_12,
                memory_size=256,
                handler="index.handler",
                code=_lambda.Code.from_inline("""
import boto3
import cfnresponse
import time

def handler(event, context):
    try:
        
        props = event.get('ResourceProperties', {})
        if event['RequestType'] in ['Create', 'Update']:
            client = boto3.client('apigateway')
            account = client.get_account()
                                              
            # Check if CloudWatch role is already set
            if 'cloudwatchRoleArn' not in account:
                # Set the CloudWatch role ARN at account level
                client.update_account(
                    patchOperations=[
                        {
                            'op': 'replace',
                            'path': '/cloudwatchRoleArn',
                            'value': props['CloudWatchRoleArn']
                        }
                    ]
                )
                # Wait for the role to propagate
                print("Waiting for cloudwatchRoleArn to proporate in account ...")
                time.sleep(30)
                print("Waiting for cloudwatchRoleArn to proporate in account ...Done")
                                              
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
        else:
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
            
    except Exception as e:
        print(e)
        cfnresponse.send(event, context, cfnresponse.FAILED, {})
"""),
                role=enable_logging_role,
                timeout=Duration.minutes(5)
            )
        )
        # Create the custom resource
        CustomResource(
            self,
            "EnableApiGatewayLogging2",
            service_token=provider.service_token,
            properties={
                "CloudWatchRoleArn": api_gateway_log_role.role_arn
            },
            removal_policy=RemovalPolicy.DESTROY,
        )

        CfnOutput(
            self,
            "mre-api-gateway-log-group",
            value=api_log_group.log_group_arn,
            description="Arn of the Log Group tp configure API Gateway with",
            export_name="mre-api-gateway-log-group-arn",
        )

        CfnOutput(
            self,
            "mre-api-gateway-logging-role",
            value=api_gateway_log_role.role_arn,
            description="Name of the IAM Role used to configure API Gateway with for logging",
            export_name="mre-api-gateway-logging-role-arn",
        )

    def create_hls_streaming_secrets(self):

        stream_auth_key_provider_lambda_role = iam.Role(
            self,
            "stream_auth_key_provider_lambda_role",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE Custom Resource Lambda function to generate RSA Keys",
        )

        stream_auth_key_provider_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/lambda/{Stack.of(self).stack_name}-*",
                ],
            )
        )

        stream_auth_key_provider_lambda_role.add_to_policy(
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

        stream_auth_key_provider_lambda = _lambda.DockerImageFunction(
            self,
            "stream_auth_key_handler",
            description="Creates RSA 2048 bit keys for signing CFN Cookies",
            code=_lambda.DockerImageCode.from_image_asset("./stacks"),
            timeout=Duration.seconds(120),
            role=stream_auth_key_provider_lambda_role,
            memory_size=512,
        )

        stream_auth_key_provider = cr.Provider(
            self,
            "stream_auth_key_provider",
            on_event_handler=stream_auth_key_provider_lambda,
            log_retention=logs.RetentionDays.TEN_YEARS
        )

        self.stream_auth_key_cr = CustomResource(
            self,
            "stream_auth_key_cr",
            service_token=stream_auth_key_provider.service_token,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.secret_event_hls_stream_private_key = secret_mgr.Secret(
            self,
            "MRE_EVENT_HLS_STREAMING_PRIVATE_KEY",
            secret_name="MRE_event_hls_streaming_private_key",
            secret_string_value=SecretValue.plain_text(
                self.stream_auth_key_cr.get_att("EncodedPrivateKey").to_string()
            ),
        )

    def create_cloudfront_distro(self):

        cors_behavior = cloudfront.ResponseHeadersCorsBehavior(
            access_control_allow_credentials=False,
            access_control_allow_headers=["*"],
            access_control_allow_methods=["ALL"],
            access_control_allow_origins=["*"],
            access_control_expose_headers=["*"],
            access_control_max_age=Duration.seconds(600),
            origin_override=True,
        )

        response_headers_policy = cloudfront.ResponseHeadersPolicy(
            self,
            "Additional;MreResponseHeadersPolicy0",
            response_headers_policy_name=f"mre-ad-response-headers-policy-{Aws.ACCOUNT_ID}-{Aws.REGION}",
            cors_behavior=cors_behavior,
        )

        # Create a CloudFront public key
        public_key = cloudfront.CfnPublicKey(
            self,
            "MreCfnStreamingPublicKey",
            public_key_config=cloudfront.CfnPublicKey.PublicKeyConfigProperty(
                caller_reference=f"callerReference-{Stack.of(self).region}",
                encoded_key=self.stream_auth_key_cr.get_att(
                    "EncodedPublicKey"
                ).to_string(),
                name=f"awsmresharedresourcesMreCfnStreamingPublicKey-{Stack.of(self).region}",
                comment="MRE HLS Streaming Public Key",
            ),
        )

        self.secret_event_hls_stream_key_pair_id = secret_mgr.Secret(
            self,
            "MRE_EVENT_HLS_STREAMING_PUBLIC_KEY",
            secret_name="MRE_event_hls_streaming_public_key",
            secret_string_value=SecretValue.plain_text(
                self.stream_auth_key_cr.get_att("EncodedPublicKey").to_string()
            ),
        )

        self.secret_event_hls_stream_key_pair_id = secret_mgr.Secret(
            self,
            "MRE_EVENT_HLS_STREAMING_KEY_PAIR_ID",
            secret_name="MRE_event_hls_streaming_private_key_pair_id",
            secret_string_value=SecretValue.plain_text(public_key.attr_id),
        )

        # Create a key group with the public key
        cfn_key_group = cloudfront.CfnKeyGroup(
            self,
            "MreCfnStreamingKeyGroup",
            key_group_config=cloudfront.CfnKeyGroup.KeyGroupConfigProperty(
                items=[public_key.attr_id],
                comment="MRE HLS Streaming Key Group",
                name=f"awsmresharedresourcesMreCfnStreamingKeyGroup-{Stack.of(self).region}",
            ),
        )
        cfn_key_group.node.add_dependency(public_key)

        key_group = cloudfront.KeyGroup.from_key_group_id(
            self, "MreStreamingKeyGroup", cfn_key_group.attr_id
        )
        key_group.node.add_dependency(cfn_key_group)

        oac = cloudfront.S3OriginAccessControl(self, 'MyOAC', signing=cloudfront.Signing.SIGV4_NO_OVERRIDE)

        # Cloudfront Distro for Media Output
        self.mre_media_output_distro = cloudfront.Distribution(
            self,
            "mre-media-output",
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,  # TLSv1.2
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(self.mre_media_output_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy(
                    self,
                    id="mre-cache-policy",
                    cache_policy_name=f"mre-cache-policy-{Aws.ACCOUNT_ID}-{Aws.REGION}",
                    cookie_behavior=cloudfront.CacheCookieBehavior.all(),
                    query_string_behavior=cloudfront.CacheQueryStringBehavior.all(),
                    header_behavior=cloudfront.CacheHeaderBehavior.allow_list(
                        "Origin",
                        "Access-Control-Request-Method",
                        "Access-Control-Request-Headers",
                    ),
                    enable_accept_encoding_brotli=True,
                    enable_accept_encoding_gzip=True,
                ),
                origin_request_policy=cloudfront.OriginRequestPolicy(
                    self,
                    id="mre-origin-request-policy",
                    origin_request_policy_name=f"mre-origin-request-policy-{Aws.ACCOUNT_ID}-{Aws.REGION}",
                    cookie_behavior=cloudfront.OriginRequestCookieBehavior.all(),
                    query_string_behavior=cloudfront.OriginRequestQueryStringBehavior.all(),
                    header_behavior=cloudfront.OriginRequestHeaderBehavior.allow_list(
                        "Origin",
                        "Access-Control-Request-Method",
                        "Access-Control-Request-Headers",
                    ),
                ),
                response_headers_policy=cloudfront.ResponseHeadersPolicy(
                    self,
                    "MreResponseHeadersPolicy",
                    response_headers_policy_name=f"mre-response-headers-policy-{Aws.ACCOUNT_ID}-{Aws.REGION}",
                    cors_behavior=cors_behavior,
                ),
            ),
            additional_behaviors={  # These origins are to enable HLS streams from media output bucket
                "/0*/*": cloudfront.BehaviorOptions(
                    origin=origins.S3BucketOrigin.with_origin_access_control(self.mre_media_source_bucket, 
                        origin_access_control=oac
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    response_headers_policy=response_headers_policy,
                    trusted_key_groups=[key_group],
                ),
                "/1*/*": cloudfront.BehaviorOptions(
                    origin=origins.S3BucketOrigin.with_origin_access_control(self.mre_media_source_bucket, 
                        origin_access_control=oac
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    response_headers_policy=response_headers_policy,
                    trusted_key_groups=[key_group],
                ),
                "/2*/*": cloudfront.BehaviorOptions(
                    origin=origins.S3BucketOrigin.with_origin_access_control(self.mre_media_source_bucket, 
                        origin_access_control=oac
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    response_headers_policy=response_headers_policy,
                    trusted_key_groups=[key_group],
                ),
                "/3*/*": cloudfront.BehaviorOptions(
                    origin=origins.S3BucketOrigin.with_origin_access_control(self.mre_media_source_bucket, 
                        origin_access_control=oac
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    response_headers_policy=response_headers_policy,
                    trusted_key_groups=[key_group],
                ),
                "/4*/*": cloudfront.BehaviorOptions(
                    origin=origins.S3BucketOrigin.with_origin_access_control(self.mre_media_source_bucket, 
                        origin_access_control=oac
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    response_headers_policy=response_headers_policy,
                    trusted_key_groups=[key_group],
                ),
                "/5*/*": cloudfront.BehaviorOptions(
                    origin=origins.S3BucketOrigin.with_origin_access_control(self.mre_media_source_bucket, 
                        origin_access_control=oac
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    response_headers_policy=response_headers_policy,
                    trusted_key_groups=[key_group],
                ),
                "/6*/*": cloudfront.BehaviorOptions(
                    origin=origins.S3BucketOrigin.with_origin_access_control(self.mre_media_source_bucket, 
                        origin_access_control=oac
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    response_headers_policy=response_headers_policy,
                    trusted_key_groups=[key_group],
                ),
                "/7*/*": cloudfront.BehaviorOptions(
                    origin=origins.S3BucketOrigin.with_origin_access_control(self.mre_media_source_bucket, 
                        origin_access_control=oac
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    response_headers_policy=response_headers_policy,
                    trusted_key_groups=[key_group],
                ),
                "/8*/*": cloudfront.BehaviorOptions(
                    origin=origins.S3BucketOrigin.with_origin_access_control(self.mre_media_source_bucket, 
                        origin_access_control=oac
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    response_headers_policy=response_headers_policy,
                    trusted_key_groups=[key_group],
                ),
                "/9*/*": cloudfront.BehaviorOptions(
                    origin=origins.S3BucketOrigin.with_origin_access_control(self.mre_media_source_bucket, 
                        origin_access_control=oac
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    response_headers_policy=response_headers_policy,
                    trusted_key_groups=[key_group],
                ),
                "/HLS/*": cloudfront.BehaviorOptions( # used for HLS replays
                    origin=origins.S3BucketOrigin.with_origin_access_control(self.mre_media_output_bucket, 
                        origin_access_control=oac
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    response_headers_policy=response_headers_policy,
                    trusted_key_groups=[key_group],
                )
            },
        )

        # add permissions for OAC to access the output bucket
        self.mre_media_output_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[self.mre_media_output_bucket.arn_for_objects("*")],
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                conditions={
                    "StringEquals": {
                        "AWS:SourceArn": f"arn:aws:cloudfront::{Aws.ACCOUNT_ID}:distribution/{self.mre_media_output_distro.distribution_id}"
                    }
                }
            )
        )

        # add permissions for OAC to access the source bucket
        self.mre_media_source_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[self.mre_media_source_bucket.arn_for_objects("*")],
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                conditions={
                    "StringEquals": {
                        "AWS:SourceArn": f"arn:aws:cloudfront::{Aws.ACCOUNT_ID}:distribution/{self.mre_media_output_distro.distribution_id}"
                    }
                }
            )
        )

        self.mre_media_output_distro.node.add_dependency(key_group)
        # Required for the Fan Experience Frontend
        ssm.StringParameter(
            self,
            "MREMediaOutputDistribution",
            string_value=self.mre_media_output_distro.domain_name,
            parameter_name="/MRE/ControlPlane/MediaOutputDistribution",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the AWS MRE MediaOutput CloudFront Distribution domain name",
        )

        CfnOutput(
            self,
            "mre-media-output-distro",
            value=self.mre_media_output_distro.domain_name,
            description="Name of the MRE media output domain",
            export_name="mre-media-output-distro-domain-name",
        )

    def create_system_table(self):
        # System Configuration Table
        self.system_table = ddb.Table(
            self,
            "System",
            partition_key=ddb.Attribute(name="Name", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        ssm.StringParameter(
            self,
            "MRESystemTableArn",
            string_value=self.system_table.table_arn,
            parameter_name="/MRE/ControlPlane/SystemTableArn",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the Arn of the MRE System table",
        )
        ssm.StringParameter(
            self,
            "MRESystemTableName",
            string_value=self.system_table.table_name,
            parameter_name="/MRE/ControlPlane/SystemTableName",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the Name of the MRE System table",
        )

    def create_content_group_table(self):
        # ContentGroup Table
        self.content_group_table = ddb.Table(
            self,
            "ContentGroup",
            partition_key=ddb.Attribute(name="Name", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )
        CfnOutput(
            self,
            "mre-content-group-table-arn",
            value=self.content_group_table.table_arn,
            description="Arn of the MRE Content Group table",
            export_name="mre-content-group-table-arn",
        )
        CfnOutput(
            self,
            "mre-content-group-table-name",
            value=self.content_group_table.table_name,
            description="Name of the MRE Content Group table",
            export_name="mre-content-group-table-name",
        )

    def create_program_table(self):
        # Program Table
        self.program_table = ddb.Table(
            self,
            "Program",
            partition_key=ddb.Attribute(name="Name", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        CfnOutput(
            self,
            "mre-program-exec-table-arn",
            value=self.program_table.table_arn,
            description="Arn of the MRE Program table",
            export_name="mre-program-table-arn",
        )
        CfnOutput(
            self,
            "mre-program-exec-table-name",
            value=self.program_table.table_name,
            description="Name of the MRE Program table",
            export_name="mre-program-table-name",
        )

    def create_workflow_exec_table(self):
        # WorkflowExecution Table
        self.workflow_exec_table = ddb.Table(
            self,
            "WorkflowExecution",
            partition_key=ddb.Attribute(name="PK", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="ChunkNumber", type=ddb.AttributeType.NUMBER),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        CfnOutput(
            self,
            "mre-workflow-exec-table-arn",
            value=self.workflow_exec_table.table_arn,
            description="Arn of the MRE Workflow Exec table",
            export_name="mre-workflow-exec-table-arn",
        )
        CfnOutput(
            self,
            "mre-workflow-exec-table-name",
            value=self.workflow_exec_table.table_name,
            description="Name of the MRE Workflow Exec table",
            export_name="mre-workflow-exec-table-name",
        )

        # Store the Workflow Execution DDB table ARN in SSM Parameter Store
        ssm.StringParameter(
            self,
            "MREWorkflowExecutionTableARN",
            string_value=self.workflow_exec_table.table_arn,
            parameter_name="/MRE/ControlPlane/WorkflowExecutionTableARN",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the ARN of the Workflow Execution DDB table used by the cleanup process following an Event deletion",
        )

    def create_model_table(self):
        # Model Table
        self.model_table = ddb.Table(
            self,
            "Model",
            partition_key=ddb.Attribute(name="Name", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="Version", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        # Model Table: Name GSI
        self.model_table.add_global_secondary_index(
            index_name=constants.MODEL_NAME_INDEX,
            partition_key=ddb.Attribute(name="Name", type=ddb.AttributeType.STRING),
        )

        # Model Table: Version GSI
        self.model_table.add_global_secondary_index(
            index_name=constants.MODEL_VERSION_INDEX,
            partition_key=ddb.Attribute(name="Version", type=ddb.AttributeType.STRING),
        )

        CfnOutput(
            self,
            "mre-model-table-arn",
            value=self.model_table.table_arn,
            description="Arn of the MRE Model table",
            export_name="mre-model-table-arn",
        )
        CfnOutput(
            self,
            "mre-model-table-name",
            value=self.model_table.table_name,
            description="Name of the MRE Model table",
            export_name="mre-model-table-name",
        )

    def create_prompt_catalog_table(self):
        # PromptCatalog Table
        self.prompt_catalog_table = ddb.Table(
            self,
            "PromptCatalog",
            partition_key=ddb.Attribute(name="Name", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="Version", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        # PromptCatalog Table: Name GSI
        self.prompt_catalog_table.add_global_secondary_index(
            index_name=constants.PROMPT_CATALOG_NAME_INDEX,
            partition_key=ddb.Attribute(name="Name", type=ddb.AttributeType.STRING),
        )

        # PromptCatalog Table: Version GSI
        self.prompt_catalog_table.add_global_secondary_index(
            index_name=constants.PROMPT_CATALOG_VERSION_INDEX,
            partition_key=ddb.Attribute(name="Version", type=ddb.AttributeType.STRING),
        )

        CfnOutput(
            self,
            "mre-prompt-catalog-table-arn",
            value=self.prompt_catalog_table.table_arn,
            description="Arn of the MRE PromptCatalog table",
            export_name="mre-prompt-catalog-table-arn",
        )
        CfnOutput(
            self,
            "mre-prompt-catalog-table-name",
            value=self.prompt_catalog_table.table_name,
            description="Name of the MRE PromptCatalog table",
            export_name="mre-prompt-catalog-table-name",
        )

    def create_profile_table(self):
        # Profile Table
        self.profile_table = ddb.Table(
            self,
            "Profile",
            partition_key=ddb.Attribute(name="Name", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        CfnOutput(
            self,
            "mre-profile-table-arn",
            value=self.profile_table.table_arn,
            description="Arn of the MRE Profile table",
            export_name="mre-profile-table-arn",
        )
        CfnOutput(
            self,
            "mre-profile-table-name",
            value=self.profile_table.table_name,
            description="Name of the MRE Profile table",
            export_name="mre-profile-table-name",
        )

    def create_mre_event_bus(self):
        # EventBridge Event Bus for MRE
        self.eb_event_bus = events.EventBus(
            self, "AWSMREEventBus", event_bus_name="aws-mre-event-bus"
        )

        # Store the EventBridge Event Bus name in SSM Parameter Store
        ssm.StringParameter(
            self,
            "MREEventBridgeBusName",
            string_value=self.eb_event_bus.event_bus_name,
            parameter_name="/MRE/EventBridge/EventBusName",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the Amazon EventBridge Event Bus name used by AWS MRE",
        )

        CfnOutput(
            self,
            "mre-event-bus",
            value=self.eb_event_bus.event_bus_arn,
            description="Arn of the MRE Event Bus",
            export_name="mre-event-bus-arn",
        )

    def create_eb_schedule_execution_role(self):

        self.eb_schedule_role = iam.Role(
            self,
            "MreScheduleRole",
            assumed_by=iam.ServicePrincipal(
                service="scheduler.amazonaws.com",
                conditions={
                    "StringEquals": {
                        "aws:SourceAccount": f"{Aws.ACCOUNT_ID}",
                        "aws:SourceArn": f"arn:aws:scheduler:{Aws.REGION}:{Aws.ACCOUNT_ID}:schedule-group/default",
                    }
                },
            ),
            description="Role used by MRE to create EB Schedules",
        )

        # Allows a Schedule Push events to EventBridge
        self.eb_schedule_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["events:PutEvents"],
                resources=[self.eb_event_bus.event_bus_arn],
            )
        )

        CfnOutput(
            self,
            "mre-eb-schedule-role-arn",
            value=self.eb_schedule_role.role_arn,
            description="Arn of the MRE Schedule Role",
            export_name="mre-eb-schedule-role-arn",
        )

    def create_s3_buckets(self):
        ##### START: S3 BUCKETS #####

        # MRE Access Log Bucket
        self.access_log_bucket = s3.Bucket(
            self,
            "MreAccessLogsBucket",
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True
        )

        # MRE Data Export Bucket
        self.data_export_bucket = s3.Bucket(
            self,
            "MreDataExportBucket",
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=self.access_log_bucket,
            server_access_logs_prefix="mre-data-export-logs",
            versioned=True,  # Enable versioning
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(360),
                    noncurrent_version_expiration=Duration.days(360),
                    enabled=True
                )
            ]
        )

        # MRE Media Source Bucket
        self.mre_media_source_bucket = s3.Bucket(
            self,
            "MreMediaSourceBucket",
            enforce_ssl=True,
            server_access_logs_bucket=self.access_log_bucket,
            server_access_logs_prefix="mre-mediasource-logs",
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,  # Enable versioning
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(360),
                    noncurrent_version_expiration=Duration.days(360),
                    enabled=True
                )
            ]
        )

        # MRE Transitions Clip Bucket
        self.mre_transition_clip_bucket = s3.Bucket(
            self,
            "MreTransitionsClipBucket",
            enforce_ssl=True,
            server_access_logs_bucket=self.access_log_bucket,
            server_access_logs_prefix="mre-transitions-clips-logs",
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,  # Enable versioning
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(360),
                    noncurrent_version_expiration=Duration.days(360),
                    enabled=True
                )
            ]
        )

        # Required for Updating the Content Security Policy for MRE Frontend
        ssm.StringParameter(
            self,
            "MreTransitionsClipBucketName",
            string_value=self.mre_transition_clip_bucket.bucket_name,
            parameter_name="/MRE/ControlPlane/TransitionClipBucket",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the AWS MRE Transition Clip Bucket Name",
        )

        # Lambda Layer S3 bucket
        self.lambda_layer_bucket = s3.Bucket(
            self,
            "LambdaLayerBucket",
            enforce_ssl=True,
            server_access_logs_bucket=self.access_log_bucket,
            server_access_logs_prefix="mre-lambdalayer-logs",
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,  # Enable versioning
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(360),
                    noncurrent_version_expiration=Duration.days(360),
                    enabled=True
                )
            ]
        )

        # Bucket for caching segments and related features from MRE workflows
        self.mre_segment_cache_bucket = s3.Bucket(
            self,
            "MreSegmentCacheBucket",
            enforce_ssl=True,
            server_access_logs_bucket=self.access_log_bucket,
            server_access_logs_prefix="mre-segmentcache-logs",
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,  # Enable versioning
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(360),
                    noncurrent_version_expiration=Duration.days(360),
                    enabled=True
                )
            ]
        )

        # Bucket for housing output artifacts such as HLS manifests, MP4, HLS clips etc.
        self.mre_media_output_bucket = s3.Bucket(
            self,
            "MreMediaOutputBucket",
            enforce_ssl=True,
            server_access_logs_bucket=self.access_log_bucket,
            server_access_logs_prefix="mre-mediaconvert-logs",
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,  # Enable versioning
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(360),
                    noncurrent_version_expiration=Duration.days(360),
                    enabled=True
                )
            ],
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.GET],
                    allowed_origins=[
                        "http://localhost:*",        # Local development
                        "https://localhost:*",       # Local development
                        "https://*.amplifyapp.com",  # Amplify apps
                        "https://*.cloudfront.net"   # CloudFront distributions
                    ],
                    allowed_headers=[],
                    max_age=3000,
                )
            ],
        )

        # Required for Updating the Content Security Policy for MRE Frontend
        ssm.StringParameter(
            self,
            "MREMediaOutputBucketName",
            string_value=self.mre_media_output_bucket.bucket_name,
            parameter_name="/MRE/ControlPlane/MediaOutputBucket",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the AWS MRE MediaOutput Bucket Name",
        )
        CfnOutput(
            self,
            "mre-media-output-bucket",
            value=self.mre_media_output_bucket.bucket_name,
            description="Name of the S3 Bucket used by MRE for MediaConvert",
            export_name="mre-media-output-bucket-name",
        )
        CfnOutput(
            self,
            "mre-data-export-bucket",
            value=self.data_export_bucket.bucket_name,
            description="Name of the S3 bucket used by MRE to store exported data",
            export_name="mre-data-export-bucket-name",
        )
        CfnOutput(
            self,
            "mre-media-source-bucket",
            value=self.mre_media_source_bucket.bucket_name,
            description="Name of the S3 bucket used to store HLS chunks to trigger MRE workflows",
            export_name="mre-media-source-bucket-name",
        )
        CfnOutput(
            self,
            "mre-segment-cache-bucket",
            value=self.mre_segment_cache_bucket.bucket_name,
            description="Name of the S3 bucket used to cache segments and related features from MRE workflows",
            export_name="mre-segment-cache-bucket-name",
        )
        CfnOutput(
            self,
            "mre-transition-clips-bucket",
            value=self.mre_transition_clip_bucket.bucket_name,
            description="Name of the S3 bucket used to store Transition clips when creating replays",
            export_name="mre-transition-clips-bucket-name",
        )

    def upload_mre_transition_sample_videos(self):

        self.layer_deploy = s3_deploy.BucketDeployment(
            self,
            "TransitionPreviewVideoDeploy",
            destination_bucket=self.mre_transition_clip_bucket,
            destination_key_prefix="FadeInFadeOut/preview",
            sources=[s3_deploy.Source.asset(path=TRANSITION_PREVIEW_VIDEO_DIR)],
            memory_limit=256,
        )

    def upload_mre_transition_fade_in_out_image(self):

        self.layer_deploy = s3_deploy.BucketDeployment(
            self,
            "TransitionFadeInOutImageDeploy",
            destination_bucket=self.mre_transition_clip_bucket,
            destination_key_prefix="FadeInFadeOut/transition_images",
            sources=[s3_deploy.Source.asset(path=TRANSITION_FADE_IN_OUT_IMAGE_DIR)],
            memory_limit=256,
        )

    def create_lambda_layers(self):
        ##### START: LAMBDA LAYERS #####

        # Upload all the zipped Lambda Layers to S3
        self.layer_deploy = s3_deploy.BucketDeployment(
            self,
            "LambdaLayerZipDeploy",
            destination_bucket=self.lambda_layer_bucket,
            sources=[s3_deploy.Source.asset(path=LAYERS_DIR)],
            memory_limit=512,
        )

        # timecode Layer
        self.timecode_layer = _lambda.LayerVersion(
            self,
            "TimeCodeLayer",
            layer_version_name="aws_mre_timecode",
            description="Layer containing the TimeCode Lib",
            code=_lambda.Code.from_bucket(
                bucket=self.lambda_layer_bucket, key="timecode/timecode.zip"
            ),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
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
                bucket=self.lambda_layer_bucket, key="ffmpeg/ffmpeg.zip"
            ),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
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
                bucket=self.lambda_layer_bucket, key="ffprobe/ffprobe.zip"
            ),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
        )

        # Deploy ffprobe_layer after layers_deploy
        self.ffprobe_layer.node.add_dependency(self.layer_deploy)

        # MediaReplayEngineWorkflowHelper Layer
        self.mre_workflow_helper_layer = _lambda.LayerVersion(
            self,
            "MediaReplayEngineWorkflowHelperLayer",
            layer_version_name="MediaReplayEngineWorkflowHelper",
            description="Layer containing the helper library (and its runtime dependencies) used by the Media Replay Engine internal lambda functions to interact with the control plane.",
            code=_lambda.Code.from_bucket(
                bucket=self.lambda_layer_bucket,
                key="MediaReplayEngineWorkflowHelper/MediaReplayEngineWorkflowHelper.zip",
            ),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
        )

        # Deploy MediaReplayEngineWorkflowHelper after layers_deploy
        self.mre_workflow_helper_layer.node.add_dependency(self.layer_deploy)

        # MediaReplayEnginePluginHelper Layer
        self.mre_plugin_helper_layer = _lambda.LayerVersion(
            self,
            "MediaReplayEnginePluginHelperLayer",
            layer_version_name="MediaReplayEnginePluginHelper",
            description="Layer containing the helper library (and its runtime dependencies) to aid the development of custom plugins for the Media Replay Engine.",
            code=_lambda.Code.from_bucket(
                bucket=self.lambda_layer_bucket,
                key="MediaReplayEnginePluginHelper/MediaReplayEnginePluginHelper.zip",
            ),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
        )

        # Deploy MediaReplayEnginePluginHelper after layers_deploy
        self.mre_plugin_helper_layer.node.add_dependency(self.layer_deploy)

        ssm.StringParameter(
            self,
            "MRETimecodeLambdaLayerArn",
            string_value=self.timecode_layer.layer_version_arn,
            parameter_name="/MRE/TimecodeLambdaLayerArn",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the Arn for timecode Lambda Layer",
        )
        ssm.StringParameter(
            self,
            "MREFfmpegLambdaLayerArn",
            string_value=self.ffmpeg_layer.layer_version_arn,
            parameter_name="/MRE/FfmpegLambdaLayerArn",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the Arn for ffmpeg Lambda Layer",
        )
        ssm.StringParameter(
            self,
            "MREFfprobeLambdaLayerArn",
            string_value=self.ffprobe_layer.layer_version_arn,
            parameter_name="/MRE/FfprobeLambdaLayerArn",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the Arn for ffprobe Lambda Layer",
        )
        ssm.StringParameter(
            self,
            "MREWorkflowHelperLambdaLayerArn",
            string_value=self.mre_workflow_helper_layer.layer_version_arn,
            parameter_name="/MRE/WorkflowHelperLambdaLayerArn",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the Arn for MediaReplayEngineWorkflowHelper Lambda Layer",
        )
        ssm.StringParameter(
            self,
            "MREPluginHelperLambdaLayerArn",
            string_value=self.mre_plugin_helper_layer.layer_version_arn,
            parameter_name="/MRE/PluginHelperLambdaLayerArn",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the Arn for MediaReplayEnginePluginHelper Lambda Layer",
        )

        ##### END: LAMBDA LAYERS #####

    def create_media_convert_role(self):
        self.event_media_convert_role = iam.Role(
            self,
            "MREMediaConvertIamRole",
            assumed_by=iam.ServicePrincipal("mediaconvert.amazonaws.com"),
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
                    "autoscaling:Describe*",
                ],
                resources=["*"],
            )
        )

        CfnOutput(
            self,
            "mre-event-media-convert-role",
            value=self.event_media_convert_role.role_arn,
            description="Contains MediaConvert IAM Role Arn",
            export_name="mre-event-media-convert-role-arn",
        )

    def create_current_events_table(self):
        # CurrentEvents Table
        self.current_events_table = ddb.Table(
            self,
            "CurrentEvents",
            partition_key=ddb.Attribute(name="EventId", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        CfnOutput(
            self,
            "mre-current-event-table-arn",
            value=self.current_events_table.table_arn,
            description="Arn of CurrentEvents table",
            export_name="mre-current-event-table-arn",
        )
        CfnOutput(
            self,
            "mre-current-event-table-name",
            value=self.current_events_table.table_name,
            description="Name of CurrentEvents table",
            export_name="mre-current-event-table-name",
        )

    def create_event_table(self):
        # Event Table
        self.event_table = ddb.Table(
            self,
            "Event",
            partition_key=ddb.Attribute(name="Name", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="Program", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        # Event Table: Channel GSI
        self.event_table.add_global_secondary_index(
            index_name=constants.EVENT_CHANNEL_INDEX,
            partition_key=ddb.Attribute(name="Channel", type=ddb.AttributeType.STRING),
            projection_type=ddb.ProjectionType.KEYS_ONLY,
        )

        # Event Table: ProgramId GSI
        self.event_table.add_global_secondary_index(
            index_name=constants.EVENT_PROGRAMID_INDEX,
            partition_key=ddb.Attribute(
                name="ProgramId", type=ddb.AttributeType.STRING
            ),
            projection_type=ddb.ProjectionType.KEYS_ONLY,
        )

        # Event Table: Program GSI
        self.event_table.add_global_secondary_index(
            index_name=constants.EVENT_PROGRAM_INDEX,
            partition_key=ddb.Attribute(name="Program", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="Start", type=ddb.AttributeType.STRING),
            projection_type=ddb.ProjectionType.KEYS_ONLY,
        )

        # Event Table: ContentGroup GSI
        self.event_table.add_global_secondary_index(
            index_name=constants.EVENT_CONTENT_GROUP_INDEX,
            partition_key=ddb.Attribute(
                name="ContentGroup", type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(name="Start", type=ddb.AttributeType.STRING),
        )

        # Event Table: Pagination key
        self.event_table.add_global_secondary_index(
            index_name=constants.EVENT_PAGINATION_INDEX,
            partition_key=ddb.Attribute(
                name="PaginationPartition", type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(name="Start", type=ddb.AttributeType.STRING),
        )

        ## Allow us to query the events for cases where a
        self.event_table.add_global_secondary_index(
            index_name=constants.EVENT_BYOB_NAME_INDEX,
            partition_key=ddb.Attribute(
                name="SourceVideoBucket", type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(name="Name", type=ddb.AttributeType.STRING),
            projection_type=ddb.ProjectionType.KEYS_ONLY,
        )

        CfnOutput(
            self,
            "mre-event-table-name",
            value=self.event_table.table_name,
            description="Event table name",
            export_name="mre-event-table-name",
        )
        CfnOutput(
            self,
            "mre-event-table-arn",
            value=self.event_table.table_arn,
            description="Event table Arn",
            export_name="mre-event-table-arn",
        )

    def create_plugin_table(self):
        self.plugin_table = ddb.Table(
            self,
            "Plugin",
            partition_key=ddb.Attribute(name="Name", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="Version", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        # Plugin Table: Name GSI
        self.plugin_table.add_global_secondary_index(
            index_name=constants.PLUGIN_NAME_INDEX,
            partition_key=ddb.Attribute(name="Name", type=ddb.AttributeType.STRING),
        )

        # Plugin Table: Version GSI
        self.plugin_table.add_global_secondary_index(
            index_name=constants.PLUGIN_VERSION_INDEX,
            partition_key=ddb.Attribute(name="Version", type=ddb.AttributeType.STRING),
        )

        CfnOutput(
            self,
            "mre-plugin-table-arn",
            value=self.plugin_table.table_arn,
            description="Arn of the MRE Plugin table",
            export_name="mre-plugin-table-arn",
        )
        CfnOutput(
            self,
            "mre-plugin-table-name",
            value=self.plugin_table.table_name,
            description="Name of the MRE Plugin table",
            export_name="mre-plugin-table-name",
        )

    def create_sqs_queues(self):

        ## Create shared DLQ:
        dlq = sqs.Queue(
            self,
            "MREEventDLQ",
            encryption=sqs.QueueEncryption.KMS_MANAGED,
            enforce_ssl=True,
        )

        self.sqs_dlq = sqs.DeadLetterQueue(max_receive_count=20, queue=dlq)

        # SQS Queue used to harvest HLS Streams
        self.sqs_event_to_harvest_queue = sqs.Queue(
            self,
            "MREEventHarvestingQueue",
            retention_period=Duration.days(7),
            visibility_timeout=Duration.minutes(5),
            encryption=sqs.QueueEncryption.KMS_MANAGED,
            enforce_ssl=True,
            dead_letter_queue=self.sqs_dlq,
        )

        # SQS Queue used to Notify when Resource allocation to Harvest HLS Streams
        self.sqs_event_harvest_failure_queue = sqs.Queue(
            self,
            "MREEventHarvestProcessFailureQueue",
            retention_period=Duration.days(7),
            visibility_timeout=Duration.minutes(5),
            encryption=sqs.QueueEncryption.KMS_MANAGED,
            enforce_ssl=True,
            dead_letter_queue=self.sqs_dlq,
        )

        # SQS Queue to capture MRE Event deletion notifications
        self.sqs_queue = sqs.Queue(
            self,
            "MREEventDeletionQueue",
            retention_period=Duration.days(7),
            visibility_timeout=Duration.minutes(20),
            encryption=sqs.QueueEncryption.KMS_MANAGED,
            enforce_ssl=True,
            dead_letter_queue=self.sqs_dlq,
        )

        # Store the SQS Queue ARN in SSM Parameter Store
        ssm.StringParameter(
            self,
            "MREEventDeletionQueueARN",
            string_value=self.sqs_queue.queue_arn,
            parameter_name="/MRE/ControlPlane/EventDeletionQueueARN",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the ARN of SQS Queue used by AWS MRE to send Event deletion notifications",
        )

        CfnOutput(
            self,
            "mre-harvest-queue-name",
            value=self.sqs_event_to_harvest_queue.queue_name,
            description="Name of the MRE Event Harvest Queue",
            export_name="mre-harvest-queue-name",
        )
        CfnOutput(
            self,
            "mre-harvest-queue-arn",
            value=self.sqs_event_to_harvest_queue.queue_arn,
            description="ARN of the MRE Event Harvest Queue",
            export_name="mre-harvest-queue-arn",
        )
        CfnOutput(
            self,
            "mre-harvest-failure-queue-name",
            value=self.sqs_event_harvest_failure_queue.queue_name,
            description="Name of the MRE Event Harvest Failure Queue",
            export_name="mre-harvest-failure-queue-name",
        )
        CfnOutput(
            self,
            "mre-event-deletion-queue-name",
            value=self.sqs_queue.queue_name,
            description="Name of the MRE Event Deletion Queue",
            export_name="mre-event-deletion-queue-name",
        )

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
                    "State": [
                        "PAST_EVENT_TO_BE_HARVESTED",
                        "FUTURE_EVENT_TO_BE_HARVESTED",
                    ]
                },
            ),
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
                },
            ),
            targets=[events_targets.SqsQueue(queue=self.sqs_event_to_harvest_queue)],
        )

    def create_metadata_table(self):
        self.metadata_table = ddb.Table(
            self,
            "Metadata",
            partition_key=ddb.Attribute(name="pk", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        CfnOutput(
            self,
            "mre-metadata-table-arn",
            value=self.metadata_table.table_arn,
            description="Arn of the MRE Metadata table",
            export_name="mre-metadata-table-arn",
        )

        CfnOutput(
            self,
            "mre-metadata-table-name",
            value=self.metadata_table.table_name,
            description="Name of the MRE Metadata table",
            export_name="mre-metadata-table-name",
        )

    def create_custom_priorities_table(self):
        # Custom Priorities Table
        self.custom_priorities_table = ddb.Table(
            self,
            "CustomPriorities",
            partition_key=ddb.Attribute(name="Name", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )
        CfnOutput(
            self,
            "mre-custom-priorities-table-arn",
            value=self.custom_priorities_table.table_arn,
            description="Arn of the MRE Custom Priorities table",
            export_name="mre-custom-priorities-table-arn",
        )
        CfnOutput(
            self,
            "mre-custom-priorities-table-name",
            value=self.custom_priorities_table.table_name,
            description="Name of the MRE Custom Priorities table",
            export_name="mre-custom-priorities-table-name",
        )

    def apply_cdk_nags(self):
        # cdk-nag suppressions
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-DDB3",
                    "reason": "DynamoDB Point-in-time Recovery not required in the default deployment mode. Customers can turn it on if required",
                },
                {
                    "id": "AwsSolutions-KMS5",
                    "reason": "The KMS Symmetric key will have automatic key rotation enabled in production.",
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Custom resource Lambda need to be on the latest version",
                },
                {
                    "id": "AwsSolutions-SMG4",
                    "reason": "Custom resource Lambda need to be on the latest version",
                },
                {
                    "id": "AwsSolutions-CFR3",
                    "reason": "Logging is not deemed important for lower environments.",
                },
                {
                    "id": "AwsSolutions-CFR4",
                    "reason": "Custom certificate required for enabling this rule.  Can be enabled in Higher environments",
                },
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AWS managed policies allowed",
                    "appliesTo": [
                        "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "S3 bucket operations require wildcard permissions for object manipulation",
                    "appliesTo": [
                        "Action::s3:GetObject*",
                        "Action::s3:GetBucket*",
                        "Action::s3:Put*",
                        "Action::s3:Get*",
                        "Action::s3:DeleteObject*",
                        "Action::s3:Abort*",
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "S3 bucket listing and description operations require wildcard permissions",
                    "appliesTo": ["Action::s3:Describe*", "Action::s3:List*"],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "AutoScaling describe operations require wildcard permissions",
                    "appliesTo": ["Action::autoscaling:Describe*"],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Resource wildcards required for dynamic resource creation",
                    "appliesTo": [
                        "Resource::*",
                        {
                            "regex": "/^Resource::arn:aws:ssm:<AWS::Region>:<AWS::AccountId>:parameter/MRE*\/*/",
                        },
                        {
                            "regex": "/^Resource::arn:aws:s3:::mre*\/*/",
                        },
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "MediaConvert needs wildcard policy",
                    "appliesTo": [
                        "Resource::*",
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Lambda logging requires access to CloudWatch log groups",
                    "appliesTo": [
                        f"Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:*",
                        f"Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/lambda/{Stack.of(self).stack_name}-*",
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Resource wildcards required for key handling",
                    "appliesTo": [
                        {
                            "regex": "/^Resource::<streamauthkeyhandler*.+.Arn>:*/",
                        },
                        {
                            "regex": "/^Resource::arn:aws:kms:<AWS::Region>:<AWS::AccountId>:key/*\/*/",
                        },
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Resource wildcards required for S3 bucket access",
                    "appliesTo": [
                        {
                            "regex": "/^Resource::arn:aws:s3:::aws-mre-shared*\/*/",
                        },
                        {
                            "regex": "/^Resource::arn:<AWS::Partition>:s3:::cdk-*\/*/",
                        },
                        {"regex": "/^Resource::<MreTransitionsClipBucket*.+Arn>:*/"},
                        {"regex": "/^Resource::<LambdaLayerBucket*.+Arn>:*/"},
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Custom resource provider needs to invoke the target Lambda function.",
                    "appliesTo": ["Resource::<SharedEnableApiLoggingHandler39332882.Arn>:*"]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Chalice IAM role policy requires wildcard permissions for CloudWatch logging",
                    "appliesTo": [
                        f"Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/apigateway/*",
                        f"Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/apigateway/*:*",
                        "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/lambda/*"
                    ],
                },
            ],
            True,
        )
