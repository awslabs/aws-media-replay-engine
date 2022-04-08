import os
import sys
from aws_cdk import (
    core as cdk,
    aws_events as events,
    aws_events_targets as events_targets,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_ssm as ssm,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks
)

# Ask Python interpreter to search for modules in the topmost folder. This is required to access the shared.infrastructure.helpers module
sys.path.append('../../../')

from shared.infrastructure.helpers import common

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')


MRE_EVENT_BUS = "aws-mre-event-bus"

class ClipGenStack(cdk.Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Store the MediaConvert Regional endpoint in SSM Parameter Store
        common.MreCdkCommon.store_media_convert_endpoint(self)

        # Get the Existing MRE EventBus as IEventBus
        self.event_bus = common.MreCdkCommon.get_event_bus(self)

        # Get MediaConvert Bucket Name from SSM
        self.media_convert_output_bucket_name = common.MreCdkCommon.get_media_convert_output_bucket_name(self)

        self.event_media_convert_role_arn = common.MreCdkCommon.get_media_convert_role_arn()

        # Get Layers
        self.mre_workflow_helper_layer = common.MreCdkCommon.get_mre_workflow_helper_layer_from_arn(self)
        self.mre_plugin_helper_layer = common.MreCdkCommon.get_mre_plugin_helper_layer_from_arn(self)
        self.timecode_layer = common.MreCdkCommon.get_timecode_layer_from_arn(self)


        # Configure all Lambdas and Step Functions for Clip Gen
        self.configure_clip_gen_lambda()

    

        
    def configure_clip_gen_lambda(self):

        
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
                    f"arn:aws:events:*:*:event-bus/{MRE_EVENT_BUS}"
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
                    self.event_media_convert_role_arn
                ]
            )
        )
        
        # Function: ClipGen
        self.event_clip_generator_lambda = _lambda.Function(
            self,
            "Mre-ClipGenEventClipGenerator",
            description="Generates Clips for MRE events",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/lambda/EventClipGenerator"),
            handler="mre-event-clip-generator.GenerateClips",
            role=self.event_clip_gen_lambda_role,
            memory_size=512,
            timeout=cdk.Duration.minutes(15),
            environment={
                "MediaConvertRole": self.event_media_convert_role_arn,
                #"OutputBucket": "" if not isinstance(self.media_convert_output_bucket_name, str) else self.media_convert_output_bucket_name,
                "OutputBucket": self.media_convert_output_bucket_name,
                "MediaConvertMaxInputJobs": "150",
                "EB_EVENT_BUS_NAME": MRE_EVENT_BUS
            },
            layers=[self.mre_workflow_helper_layer,
                     self.mre_plugin_helper_layer
                     ]
        )

        ## END: event-clip-generator LAMBDA ###

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
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/lambda/EventHlsManifestGenerator"),
            handler="event_hls_manifest_gen.create_hls_manifest",
            role=self.event_hls_gen_lambda_role,
            memory_size=512,
            timeout=cdk.Duration.minutes(15),
            environment={
                "MediaConvertRole": self.event_media_convert_role_arn,
                #"OutputBucket": "" if not isinstance(self.media_convert_output_bucket_name, str) else self.media_convert_output_bucket_name,
                "OutputBucket": self.media_convert_output_bucket_name,
                "MediaConvertMaxInputJobs": "150"
            },
            layers=[self.mre_workflow_helper_layer]
        )

        self.event_hls_media_convert_job_status_lambda = _lambda.Function(
            self,
            "MreEventHlsMediaConvertJobStatus",
            description="Checks if all MRE Media Convert Jobs for an event are complete",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/lambda/EventHlsManifestGenerator"),
            handler="event_hls_manifest_gen.media_convert_job_status",
            role=self.event_hls_gen_lambda_role,
            memory_size=256,
            timeout=cdk.Duration.minutes(5),
            environment={
                "MediaConvertRole": self.event_media_convert_role_arn,
                #"OutputBucket": "" if not isinstance(self.media_convert_output_bucket_name, str) else self.media_convert_output_bucket_name,
                "OutputBucket": self.media_convert_output_bucket_name,
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
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/lambda/EventEdlGenerator"),
            handler="mre_event_edl_gen.generate_edl",
            role=self.event_hls_gen_lambda_role,
            memory_size=256,
            timeout=cdk.Duration.minutes(10),
            environment={
                #"OutputBucket": "" if not isinstance(self.media_convert_output_bucket_name, str) else self.media_convert_output_bucket_name,
                "OutputBucket": self.media_convert_output_bucket_name,
            },
            layers=[self.mre_workflow_helper_layer,
                    self.mre_plugin_helper_layer,
                    self.timecode_layer
                    ]

        )

        ### END: EventEdlGenerator LAMBDA ###

        
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
                    self.event_media_convert_role_arn
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
            event_bus=self.event_bus,
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
        self.mre_edlgen_events_rule.node.add_dependency(self.event_bus)
        self.mre_edlgen_events_rule.node.add_dependency(self.event_edl_gen_lambda)


        
        # Store the Clip Gen State Machine ARN
        ssm.StringParameter(
            self,
            "ClipGenStateMachineArn",
            string_value=self.state_machine.state_machine_arn,
            parameter_name="/MRE/ClipGen/StateMachineArn",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Contains MRE Clip Generation State Machine Arn"
        )

        cdk.CfnOutput(self, "mre-clip-gen", value=self.state_machine.state_machine_arn, description="Contains MRE Clip Generation State Machine Arn", export_name="mre-clip-gen-arn" )