#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import os
import sys

from aws_cdk import CfnOutput, Duration, Fn, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from cdk_nag import NagSuppressions
from chalice.cdk import Chalice

# Ask Python interpreter to search for modules in the topmost folder. This is required to access the shared.infrastructure.helpers module
sys.path.append("../../../../")

from shared.infrastructure.helpers import common, constants, api_logging_construct

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, "runtime"
)


class ChaliceApp(Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Get the Existing MRE EventBus as IEventBus
        self.event_bus = common.MreCdkCommon.get_event_bus(self)

        self.content_group_table_arn = Fn.import_value("mre-content-group-table-arn")
        self.content_group_table_name = Fn.import_value("mre-content-group-table-name")
        self.profile_table_arn = Fn.import_value("mre-profile-table-arn")
        self.profile_table_name = Fn.import_value("mre-profile-table-name")
        self.model_table_arn = Fn.import_value("mre-model-table-arn")
        self.model_table_name = Fn.import_value("mre-model-table-name")
        self.prompt_catalog_table_arn = Fn.import_value("mre-prompt-catalog-table-arn")
        self.prompt_catalog_table_name = Fn.import_value(
            "mre-prompt-catalog-table-name"
        )
        self.plugin_table_arn = Fn.import_value("mre-plugin-table-arn")
        self.plugin_table_name = Fn.import_value("mre-plugin-table-name")
        self.metadata_table_arn = Fn.import_value("mre-metadata-table-arn")
        self.metadata_table_name = Fn.import_value("mre-metadata-table-name")
        self.mre_api_gateway_logging_role_arn = Fn.import_value("mre-api-gateway-logging-role-arn")

        # Get Layers
        self.mre_workflow_helper_layer = (
            common.MreCdkCommon.get_mre_workflow_helper_layer_from_arn(self)
        )
        self.mre_plugin_helper_layer = (
            common.MreCdkCommon.get_mre_plugin_helper_layer_from_arn(self)
        )
        self.ffmpeg_layer = common.MreCdkCommon.get_ffmpeg_layer_from_arn(self)
        self.ffprobe_layer = common.MreCdkCommon.get_ffprobe_layer_from_arn(self)

        self.powertools_layer = common.MreCdkCommon.get_powertools_layer_from_arn(self)

        ## Create internal SF lambdas
        self.create_probe_video_lambda()
        self.create_multi_chunker_helper_lambda()
        self.create_plugin_output_handler_lambda()
        self.create_workflow_error_handler_lambda()
        ## Create SF role (uses Lambda ARNs)
        self.create_sfn_role()
        self.create_chalice_role()

        # Enable API Gateway logging through Custom Resources
        api_logging_construct.ApiGatewayLogging(
            self, 
            "ProfileApi",
            stack_name=self.stack_name,
            api_gateway_logging_role_arn=self.mre_api_gateway_logging_role_arn,
            rate_limit = 25, # 25 requests per second
            burst_limit = 15 # up to 15 concurrent requests
        )

        

    def get_default_cw_log_policy(self):
        return iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogGroup",
            ],
            resources=[
                f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group*"
            ],
        )

    def get_function_specific_cw_log_policy(self, function_name: str):
        return iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogGroup",
            ],
            resources=[
                f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/lambda/{Stack.of(self).stack_name}-{function_name}*",
            ],
        )

    def get_ssm_policy(self):
        return iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ssm:DescribeParameters",
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:GetParametersByPath",
            ],
            resources=[
                f"arn:aws:ssm:{Stack.of(self).region}:{Stack.of(self).account}:parameter/MRE*"
            ],
        )

    def create_workflow_error_handler_lambda(self):
        ### START: WorkflowErrorHandler LAMBDA ###

        # Role: WorkflowErrorHandlerLambdaRole
        self.workflow_error_handler_lambda_role = iam.Role(
            self,
            "WorkflowErrorHandlerLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        # WorkflowErrorHandlerLambdaRole: CloudWatch Logs permissions
        self.workflow_error_handler_lambda_role.add_to_policy(
            self.get_default_cw_log_policy()
        )
        self.workflow_error_handler_lambda_role.add_to_policy(
            self.get_function_specific_cw_log_policy("WorkflowErrorHandler")
        )

        # WorkflowErrorHandlerLambdaRole: SSM Parameter Store permissions
        self.workflow_error_handler_lambda_role.add_to_policy(self.get_ssm_policy())

        # WorkflowErrorHandlerLambdaRole: API Gateway Invoke permissions
        self.workflow_error_handler_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["execute-api:Invoke", "execute-api:ManageConnections"],
                resources=[
                    f"arn:aws:execute-api:{Stack.of(self).region}:{Stack.of(self).account}:*"
                ],
            )
        )

        # WorkflowErrorHandlerLambdaRole: EventBridge permissions
        self.workflow_error_handler_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["events:DescribeEventBus", "events:PutEvents"],
                resources=[
                    f"arn:aws:events:{Stack.of(self).region}:{Stack.of(self).account}:event-bus/{self.event_bus.event_bus_name}"
                ],
            )
        )

        # Function: WorkflowErrorHandler
        self.workflow_error_handler_lambda = _lambda.Function(
            self,
            "WorkflowErrorHandler",
            description="Handle exceptions caught by the AWS Step Function workflow and optionally update the execution status of the Classifier plugin",
            runtime=_lambda.Runtime.PYTHON_3_11,
            code=_lambda.Code.from_asset("lambda/WorkflowErrorHandler"),
            handler="lambda_function.lambda_handler",
            role=self.workflow_error_handler_lambda_role,
            memory_size=128,
            timeout=Duration.minutes(1),
            layers=[self.mre_workflow_helper_layer, self.mre_plugin_helper_layer],
            environment={"EB_EVENT_BUS_NAME": self.event_bus.event_bus_name},
        )

        ### END: WorkflowErrorHandler LAMBDA ###

    def create_plugin_output_handler_lambda(self):

        ### START: PluginOutputHandler LAMBDA ###

        # Role: PluginOutputHandlerLambdaRole
        self.plugin_output_handler_lambda_role = iam.Role(
            self,
            "PluginOutputHandlerLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        # PluginOutputHandlerLambdaRole: CloudWatch Logs permissions
        self.plugin_output_handler_lambda_role.add_to_policy(
            self.get_default_cw_log_policy()
        )
        self.plugin_output_handler_lambda_role.add_to_policy(
            self.get_function_specific_cw_log_policy("PluginOutputHandler")
        )

        # PluginOutputHandlerLambdaRole: SSM Parameter Store permissions
        self.plugin_output_handler_lambda_role.add_to_policy(self.get_ssm_policy())

        # PluginOutputHandlerLambdaRole: API Gateway Invoke permissions
        self.plugin_output_handler_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["execute-api:Invoke", "execute-api:ManageConnections"],
                resources=[
                    f"arn:aws:execute-api:{Stack.of(self).region}:{Stack.of(self).account}:*"
                ],
            )
        )

        # Function: PluginOutputHandler
        self.plugin_output_handler_lambda = _lambda.Function(
            self,
            "PluginOutputHandler",
            description="Handle the output of a plugin based on its execution status",
            runtime=_lambda.Runtime.PYTHON_3_11,
            code=_lambda.Code.from_asset("lambda/PluginOutputHandler"),
            handler="lambda_function.lambda_handler",
            role=self.plugin_output_handler_lambda_role,
            memory_size=128,
            timeout=Duration.minutes(1),
            layers=[self.mre_workflow_helper_layer, self.mre_plugin_helper_layer],
        )

        ### END: PluginOutputHandler LAMBDA ###

    def create_multi_chunker_helper_lambda(self):
        ### START: MultiChunkHelper LAMBDA ###

        # Role: MultiChunkHelperLambdaRole
        self.multi_chunk_helper_lambda_role = iam.Role(
            self,
            "MultiChunkHelperLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        # MultiChunkHelperLambdaRole: CloudWatch Logs permissions
        self.multi_chunk_helper_lambda_role.add_to_policy(
            self.get_default_cw_log_policy()
        )
        self.multi_chunk_helper_lambda_role.add_to_policy(
            self.get_function_specific_cw_log_policy("MultiChunkHelper")
        )

        # MultiChunkHelperLambdaRole: SSM Parameter Store permissions
        self.multi_chunk_helper_lambda_role.add_to_policy(self.get_ssm_policy())

        # MultiChunkHelperLambdaRole: API Gateway Invoke permissions
        self.multi_chunk_helper_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["execute-api:Invoke", "execute-api:ManageConnections"],
                resources=[
                    f"arn:aws:execute-api:{Stack.of(self).region}:{Stack.of(self).account}:*"
                ],
            )
        )

        # Function: MultiChunkHelper
        self.multi_chunk_helper_lambda = _lambda.Function(
            self,
            "MultiChunkHelper",
            description="Check the completion status of a Classifier/Optimizer plugin in the prior AWS Step Function workflow executions",
            runtime=_lambda.Runtime.PYTHON_3_11,
            code=_lambda.Code.from_asset("lambda/MultiChunkHelper"),
            handler="lambda_function.lambda_handler",
            role=self.multi_chunk_helper_lambda_role,
            memory_size=128,
            timeout=Duration.minutes(1),
            layers=[self.mre_workflow_helper_layer, self.mre_plugin_helper_layer],
        )

        ### END: MultiChunkHelper LAMBDA ###

    def create_sfn_role(self):

        # Step Function IAM Role
        self.sfn_role = iam.Role(
            self,
            "StepFunctionRole",
            assumed_by=iam.ServicePrincipal(service="states.amazonaws.com"),
            description="Service role for the AWS MRE Step Functions",
        )

        # Step Function IAM Role: X-Ray permissions
        self.sfn_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                ],
                resources=[
                    f"arn:aws:xray:*:{Stack.of(self).account}:group/*/*",
                ],
            )
        )

        # Step Function IAM Role: Lambda permissions
        self.sfn_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[
                    self.plugin_output_handler_lambda.function_arn,
                    self.multi_chunk_helper_lambda.function_arn,
                    self.probe_video_lambda.function_arn,
                    self.workflow_error_handler_lambda.function_arn,
                    f"arn:aws:lambda:{Stack.of(self).region}:{Stack.of(self).account}:function:*",
                ],
            )
        )

        # Step Function IAM Role: State Machine execute permissions
        self.sfn_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["states:StartExecution"],
                conditions={
                    "StringEquals": {"aws:ResourceTag/Project": "MRE"},
                    "Null": {"aws:ResourceTag/Profile": "false"},
                },
                resources=[
                    f"arn:aws:states:{Stack.of(self).region}:{Stack.of(self).account}:stateMachine:aws-mre-*-state-machine",
                ],
            )
        )

        ## This allows clip generation to happen
        self.sfn_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["states:StartExecution"],
                resources=[
                    f"arn:aws:states:{Stack.of(self).region}:{Stack.of(self).account}:stateMachine:mreEventClipGeneratorStateMachine*"
                ],
            )
        )

    def create_probe_video_lambda(self):
        ### START: ProbeVideo LAMBDA ###

        # Role: ProbeVideoLambdaRole
        self.probe_video_lambda_role = iam.Role(
            self,
            "ProbeVideoLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        # ProbeVideoLambdaRole: CloudWatch Logs permissions
        self.probe_video_lambda_role.add_to_policy(self.get_default_cw_log_policy())
        self.probe_video_lambda_role.add_to_policy(
            self.get_function_specific_cw_log_policy("ProbeVideo")
        )

        # ProbeVideoLambdaRole: SSM Parameter Store permissions
        self.probe_video_lambda_role.add_to_policy(self.get_ssm_policy())

        # ProbeVideoLambdaRole: API Gateway Invoke permissions
        self.probe_video_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["execute-api:Invoke", "execute-api:ManageConnections"],
                resources=[
                    f"arn:aws:execute-api:{Stack.of(self).region}:{Stack.of(self).account}:*"
                ],
            )
        )

        # Function: ProbeVideo
        self.probe_video_lambda = _lambda.Function(
            self,
            "ProbeVideo",
            description="Probe the HLS video segment (.ts) file to extract metadata about the video segment and all the key frames in it",
            runtime=_lambda.Runtime.PYTHON_3_11,
            code=_lambda.Code.from_asset("lambda/ProbeVideo"),
            handler="lambda_function.lambda_handler",
            role=self.probe_video_lambda_role,
            memory_size=1024,
            timeout=Duration.minutes(15),
            layers=[
                self.ffmpeg_layer,
                self.ffprobe_layer,
                self.mre_workflow_helper_layer,
                self.mre_plugin_helper_layer,
            ],
        )

        ### END: ProbeVideo LAMBDA ###

    def create_chalice_role(self):

        # Chalice IAM Role
        self.chalice_role = iam.Role(
            self,
            "ChaliceRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE Profile API Lambda function",
        )

        # Chalice IAM Role: CloudWatch Logs permissions
        self.chalice_role.add_to_policy(self.get_default_cw_log_policy())

        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/lambda/{Stack.of(self).stack_name}-*",
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
                    self.content_group_table_arn,
                    self.plugin_table_arn,
                    f"{self.plugin_table_arn}/index/*",
                    self.profile_table_arn,
                    self.model_table_arn,
                    f"{self.model_table_arn}/index/*",
                    self.prompt_catalog_table_arn,
                    f"{self.prompt_catalog_table_arn}/index/*",
                    self.metadata_table_arn,
                    f"{self.metadata_table_arn}/index/*",
                ],
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
                    "states:TagResource",
                ],
                conditions={
                    "StringEquals": {"aws:ResourceTag/Project": "MRE"},
                    "Null": {"aws:ResourceTag/Profile": "false"},
                },
                resources=[
                    f"arn:aws:states:{Stack.of(self).region}:{Stack.of(self).account}:stateMachine:aws-mre-*-state-machine"
                ],
            )
        )

        # Chalice IAM Role: Step Function PassRole permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["iam:PassRole"],
                resources=[self.sfn_role.role_arn],
            )
        )

        self.chalice = Chalice(
            self,
            "ChaliceApp",
            source_dir=RUNTIME_SOURCE_DIR,
            stage_config={
                "environment_variables": {
                    "SFN_ROLE_ARN": self.sfn_role.role_arn,
                    "CONTENT_GROUP_TABLE_NAME": self.content_group_table_name,
                    "PROFILE_TABLE_NAME": self.profile_table_name,
                    "PROBE_VIDEO_LAMBDA_ARN": self.probe_video_lambda.function_arn,
                    "MULTI_CHUNK_HELPER_LAMBDA_ARN": self.multi_chunk_helper_lambda.function_arn,
                    "PLUGIN_OUTPUT_HANDLER_LAMBDA_ARN": self.plugin_output_handler_lambda.function_arn,
                    "WORKFLOW_ERROR_HANDLER_LAMBDA_ARN": self.workflow_error_handler_lambda.function_arn,
                    "MODEL_TABLE_NAME": self.model_table_name,
                    "PROMPT_CATALOG_TABLE_NAME": self.prompt_catalog_table_name,
                    "PLUGIN_TABLE_NAME": self.plugin_table_name,
                    "CLIP_GENERATION_STATE_MACHINE_ARN": Fn.import_value(
                        "mre-clip-gen-arn"
                    ),
                    "METADATA_TABLE_NAME": self.metadata_table_name,
                },
                "tags": {"Project": "MRE"},
                "manage_iam_role": False,
                "iam_role_arn": self.chalice_role.role_arn,
                "layers": [
                    self.powertools_layer.layer_version_arn,
                ],
            },
        )

        # cdk-nag suppressions
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Lambda logging requires access to CloudWatch log groups",
                    "appliesTo": [
                        "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group*",
                        {
                            "regex": f"/^Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:\/aws\/lambda\/{Stack.of(self).stack_name}-.+$/"
                        },
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "SSM parameter store access needed for MRE configuration parameters",
                    "appliesTo": [
                        "Resource::arn:aws:ssm:<AWS::Region>:<AWS::AccountId>:parameter/MRE*"
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "API Gateway requires permissions to invoke and manage connections",
                    "appliesTo": [
                        "Resource::arn:aws:execute-api:<AWS::Region>:<AWS::AccountId>:*"
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Lambda function invocation permissions needed for StepFunction orchestration",
                    "appliesTo": [
                        "Resource::arn:aws:lambda:<AWS::Region>:<AWS::AccountId>:function:*"
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "X-Ray tracing requires access for groups, sampling rules and general service functionality",
                    "appliesTo": [
                        "Resource::arn:aws:xray:*:<AWS::AccountId>:group/*/*",
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "DynamoDB GSI access needed for table queries",
                    "appliesTo": [{"regex": "/^Resource::.*/index/\\*$/"}],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Step Functions state machine access required for workflow execution",
                    "appliesTo": [
                        "Resource::arn:aws:states:<AWS::Region>:<AWS::AccountId>:stateMachine:aws-mre-*-state-machine",
                        "Resource::arn:aws:states:<AWS::Region>:<AWS::AccountId>:stateMachine:mreEventClipGeneratorStateMachine*"
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
                    "appliesTo": ["Resource::<ProfileApiEnableLoggingHandler079F930B.Arn>:*"]
                }
            ],
        )

        CfnOutput(
            self,
            "mre-profile-api-url",
            value=self.chalice.sam_template.get_output("EndpointURL").value,
            description="MRE Profile API Url",
            export_name="mre-profile-api-url",
        )
