import os
import sys
from aws_cdk import (
    core as cdk,
    aws_events as events,
    aws_events_targets as events_targets,
    aws_iam as iam,
    aws_lambda as _lambda
)


# Ask Python interpreter to search for modules in the topmost folder. This is required to access the shared.infrastructure.helpers module
sys.path.append('../../../')

import shared.infrastructure.helpers.constants as constants
from shared.infrastructure.helpers import common

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')


class EventSchedulerStack(cdk.Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Get the Existing MRE EventBus as IEventBus
        self.event_bus = common.MreCdkCommon.get_event_bus(self)

        self.sqs_event_to_harvest_queue = common.MreCdkCommon.get_mre_harvest_queue(self)
        
        self.create_lambda()

    def create_lambda(self):

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
                    cdk.Fn.import_value("mre-event-table-arn"),
                    f"{cdk.Fn.import_value('mre-event-table-arn')}/index/*",
                    cdk.Fn.import_value("mre-current-event-table-arn")
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
                    f"arn:aws:events:*:*:event-bus/{self.event_bus.event_bus_name}"
                ]
            )
        )

        # Function: MREEventScheduler
        self.event_scheduler_lambda = _lambda.Function(
            self,
            "MreEventScheduler",
            description="Schedules Past/Future events for processing based in the Event Start time",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}"),
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
                "CURRENT_EVENTS_TABLE_NAME": cdk.Fn.import_value("mre-current-event-table-name"),
                "EB_EVENT_BUS_NAME": self.event_bus.event_bus_name,
                "EVENT_TABLE_NAME": cdk.Fn.import_value("mre-event-table-name")
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

        # EventBridge: MRE Event Scheduler Events Rule
        self.mre_event_scheduler_events_rule1 = events.Rule(
            self,
            "MREEventSchedulerHarvestSoonRule",
            description="Rule that captures Event Scheduler events (PAST_EVENT_TO_BE_HARVESTED, FUTURE_EVENT_TO_BE_HARVESTED). Tie this to Event Processing logic.",
            enabled=True,
            event_bus=self.event_bus,
            event_pattern=events.EventPattern(
                source=["awsmre"],
                detail={
                    "State": ["PAST_EVENT_TO_BE_HARVESTED", "FUTURE_EVENT_TO_BE_HARVESTED"]
                }
            )
        )

        # EventBridge: MRE Event Scheduler Events Rule
        self.mre_event_scheduler_events_rule2 = events.Rule(
            self,
            "MREEventSchedulerHarvestNowRule",
            description="Rule that captures Event Scheduler events (FUTURE_EVENT_HARVEST_NOW, PAST_EVENT_HARVEST_NOW) and outputs them to sqs_event_to_harvest_queue",
            enabled=True,
            event_bus=self.event_bus,
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

        ### END: EventScheduler LAMBDA ###