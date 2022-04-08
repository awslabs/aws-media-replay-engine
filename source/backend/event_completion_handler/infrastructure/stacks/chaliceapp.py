import os
import sys

from aws_cdk import (
    core as cdk,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as events_targets
)

# Ask Python interpreter to search for modules in the topmost folder. This is required to access the shared.infrastructure.helpers module
sys.path.append('../../../')

from shared.infrastructure.helpers import common

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')


class ChaliceApp(cdk.Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.mre_workflow_helper_layer = common.MreCdkCommon.get_mre_workflow_helper_layer_from_arn(self)

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
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/lambda"),
            handler="lambda_function.lambda_handler",
            role=self.event_completion_handler_role,
            memory_size=128,
            timeout=cdk.Duration.minutes(1),
            layers=[self.mre_workflow_helper_layer]
        )

        ### END: EventCompletionHandler LAMBDA ###

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
