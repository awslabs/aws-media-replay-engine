import os
import sys
from aws_cdk import (
    Stack,
    Duration,
    aws_events as events,
    aws_events_targets as events_targets,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_mediaconvert as media_convert,
    lambda_layer_awscli as awscli
)

# Ask Python interpreter to search for modules in the topmost folder. This is required to access the shared.infrastructure.helpers module
sys.path.append('../../../')

from shared.infrastructure.helpers import common

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')


MRE_EVENT_BUS = "aws-mre-event-bus"

class ReplayStack(Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Get the Existing MRE EventBus as IEventBus
        self.event_bus = common.MreCdkCommon.get_event_bus(self)

        # Get the MediaConvert Regional endpoint
        self.media_convert_endpoint = common.MreCdkCommon.get_media_convert_endpoint(self)

        self.event_media_convert_role_arn = common.MreCdkCommon.get_media_convert_role_arn()

        self.media_convert_output_bucket_name = common.MreCdkCommon.get_media_convert_output_bucket_name(self)
        self.data_export_bucket_name = common.MreCdkCommon.get_data_export_bucket_name()
        self.segment_cache_bucket_name = common.MreCdkCommon.get_segment_cache_bucket_name(self)

        # Get Layers
        self.mre_workflow_helper_layer = common.MreCdkCommon.get_mre_workflow_helper_layer_from_arn(self)
        self.mre_plugin_helper_layer = common.MreCdkCommon.get_mre_plugin_helper_layer_from_arn(self)

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
                    f"arn:aws:events:*:*:event-bus/{self.event_bus.event_bus_name}"
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
                    "s3:List*",
                    "cloudwatch:PutMetricData"
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
                    self.event_media_convert_role_arn
                ]
            )
        )

        self.replay_media_convert_accelerated_queue = media_convert.CfnQueue(
            self,
            "mre-replay-hls-accelerated-queue",
            description="Accelerated queue for MRE Replay HLS jobs",
            name="mre-replay-hls-accelerated-queue")

        self.replay_environment_config = {
            "MediaConvertRole": self.event_media_convert_role_arn,
            "OutputBucket": self.media_convert_output_bucket_name,
            "MediaConvertMaxInputJobs": "150",
            "MediaConvertAcceleratorQueueArn": self.replay_media_convert_accelerated_queue.attr_arn,
            "EB_EVENT_BUS_NAME": self.event_bus.event_bus_name,
            "CACHE_BUCKET_NAME": self.segment_cache_bucket_name,
            "ENABLE_CUSTOM_METRICS": "Y",
            "CATCHUP_NUMBER_OF_LATEST_SEGMENTS_TO_FIND_FEATURES_IN": "20",
            "MAX_NUMBER_OF_THREADS": "50",
            "MEDIA_CONVERT_ENDPOINT": self.media_convert_endpoint
        }

        # Function: CreateReplay
        self.create_replay_lambda = _lambda.Function(
            self,
            "MRE-replay-CreateReplay",
            description="MRE - Creates Replay for MRE events",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/"),
            handler="replay_lambda.CreateReplay",
            role=self.replay_lambda_role,
            memory_size=10240,
            timeout=Duration.minutes(15),
            environment=self.replay_environment_config,
            layers=[self.mre_workflow_helper_layer,
                    self.mre_plugin_helper_layer
                    ]
        )
        self.create_replay_lambda.add_layers(awscli.AwsCliLayer(self, "AwsCliLayer"))



        # Function: GetEligibleReplays
        self.get_eligible_replays_lambda = _lambda.Function(
            self,
            "MRE-replay-GetEligibleReplays",
            description="MRE - Gets eligible replays for an MRE event",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/"),
            handler="replay_lambda.GetEligibleReplays",
            role=self.replay_lambda_role,
            memory_size=256,
            timeout=Duration.minutes(6),
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
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/"),
            handler="replay_lambda.mark_replay_complete",
            role=self.replay_lambda_role,
            memory_size=256,
            timeout=Duration.minutes(6),
            environment=self.replay_environment_config,
            layers=[self.mre_workflow_helper_layer,
                    self.mre_plugin_helper_layer
                    ]
        )


        # Function: MarkReplayError
        self.mark_replay_error_lambda = _lambda.Function(
            self,
            "MRE-replay-MarkReplayError",
            description="MRE - Mark a Replay status as Error",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/"),
            handler="replay_lambda.mark_replay_error",
            role=self.replay_lambda_role,
            memory_size=256,
            timeout=Duration.minutes(6),
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
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/"),
            handler="replay_lambda.generate_master_playlist",
            role=self.replay_lambda_role,
            memory_size=256,
            timeout=Duration.minutes(14),
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
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/"),
            handler="replay_lambda.generate_hls_clips",
            role=self.replay_lambda_role,
            memory_size=256,
            timeout=Duration.minutes(14),
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
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/"),
            handler="replay_lambda.check_Hls_job_status",
            role=self.replay_lambda_role,
            memory_size=256,
            timeout=Duration.minutes(14),
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
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/"),
            handler="replay_lambda.generate_mp4_clips",
            role=self.replay_lambda_role,
            memory_size=4096,
            timeout=Duration.minutes(15),
            environment=self.replay_environment_config,
            layers=[self.mre_workflow_helper_layer,
                    self.mre_plugin_helper_layer
                    ]
        )

        # Function: UodateMediaConvertJobStatusInDDB
        self.update_media_convert_job_in_ddb = _lambda.Function(
            self,
            "MRE-replay-UpdateMediaConvertJobStatusInDDB",
            description="MRE - Replay - Updates Status of Media Convert Jobs in DDB based on event received from EventBridge",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/"),
            handler="replay_lambda.update_job_status",
            role=self.replay_lambda_role,
            memory_size=256,
            timeout=Duration.minutes(1),
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
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/"),
            handler="replay_lambda.check_mp4_job_status",
            role=self.replay_lambda_role,
            memory_size=256,
            timeout=Duration.minutes(15),
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
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/"),
            handler="replay_lambda.update_replay_with_mp4_location",
            role=self.replay_lambda_role,
            memory_size=256,
            timeout=Duration.minutes(5),
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
            result_path="$.ReplayResult",

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
            time=sfn.WaitTime.duration(Duration.seconds(5))
        )

        waitFiveSecondsTaskMp4 = sfn.Wait(
            self,
            "wait_5_seconds_mp4",
            time=sfn.WaitTime.duration(Duration.seconds(5))
        )

        allOkTask = sfn.Pass(
            self,
            "NoVideoToBeGenerated",
        )

        doneTask = sfn.Pass(
            self,
            "Done",
        )

        noSupportedTask = sfn.Pass(
            self,
            "OutputTypeNotSupported",
        )

        ignoreTask = sfn.Pass(
            self,
            "ReplayProcessingIgnored",
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
                    self, "ShouldCatchupReplayBeSkipped?")
                .when(
                    sfn.Condition.string_equals("$.CurrentReplayResult.Payload.Status",
                                                                "Replay Not Processed"),ignoreTask)
                    .otherwise(
                        sfn.Choice(self,"GenerateReplayVideoOutput?")
                        .when(
                            sfn.Condition.and_(sfn.Condition.boolean_equals("$.ReplayRequest.CreateHls", True),
                                            sfn.Condition.string_equals("$.CurrentReplayResult.Payload.Status",
                                                                        "Replay Processed")),
                            generateHlsClipsTask.next(
                                checkHlsJobStatusTask.next(
                                    sfn.Choice(self, "AreAllHlsJobsComplete?")
                                        .when(
                                        sfn.Condition.string_equals("$.CheckHlsJobStatusResult.Payload.Status", "Complete"),
                                        generateMasterPlaylistTask)
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
                                        updateReplayWithMp4Task)
                                        .otherwise(waitFiveSecondsTaskMp4.next(checkMp4JobStatusTask)))))
                        .otherwise(allOkTask)
                    )
            )
        ).next(completeReplayTask))



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
            event_bus=self.event_bus,
            event_pattern=events.EventPattern(
                source=["awsmre"],
                detail={
                    "State":  ["OPTIMIZED_SEGMENT_CACHED", "SEGMENT_CACHED", "EVENT_END", "REPLAY_CREATED"]
                }
            ),
            targets=[
                events_targets.SfnStateMachine(
                    machine=self.replay_state_machine
                )
            ]
        )

        self.mre_replay_events_rule.node.add_dependency(self.event_bus)
        self.mre_replay_events_rule.node.add_dependency(self.replay_state_machine)


        self.mre_replay_media_convert_job_update_rule = events.Rule(
            self,
            "MREReplayMediaConvertJobRule",
            description="MRE Replay - Rule that captures Event sent from MediaConvert for Replay Video Jobs and updates DDB with Job status.",
            enabled=True,
            event_pattern=events.EventPattern(
                source=["aws.mediaconvert"],
                detail={
                    "status": [
                        "COMPLETE","ERROR"
                    ],
                    "userMetadata": {"Source":["Replay"]}
                }
            ),
            targets=[
                events_targets.LambdaFunction(
                    handler=self.update_media_convert_job_in_ddb
                )
            ]
        )

        self.mre_replay_media_convert_job_update_rule.node.add_dependency(self.update_media_convert_job_in_ddb)

        