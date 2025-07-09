import os
import sys
from aws_cdk import (
    Duration,
    Stack,
    Fn,
    aws_events as events,
    aws_events_targets as events_targets,
    aws_iam as iam,
    aws_lambda as _lambda,
)
from cdk_nag import NagSuppressions

# Ask Python interpreter to search for modules in the topmost folder. This is required to access the shared.infrastructure.helpers module
sys.path.append("../../../")

from shared.infrastructure.helpers import common

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, "runtime"
)


class ChaliceApp(Stack):

    def __init__(self, scope, id, **kwargs):

        super().__init__(scope, id, **kwargs)

        # Get the Existing MRE EventBus as IEventBus
        self.event_bus = common.MreCdkCommon.get_event_bus(self)

        # Get the existing MRE Segment Cache bucket
        self.segment_cache_bucket_name = (
            common.MreCdkCommon.get_segment_cache_bucket_name(self)
        )

        # Get Layers
        self.mre_workflow_helper_layer = (
            common.MreCdkCommon.get_mre_workflow_helper_layer_from_arn(self)
        )
        self.mre_plugin_helper_layer = (
            common.MreCdkCommon.get_mre_plugin_helper_layer_from_arn(self)
        )

        # Configure Lambda function and associated IAM permissions
        self.configure_segment_caching_lambda()

    def configure_segment_caching_lambda(self):

        self.segment_caching_lambda_role = iam.Role(
            self,
            "MRESegmentCachingIamRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        self.segment_caching_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/lambda/{Stack.of(self).stack_name}-*",
                ],
            )
        )

        self.segment_caching_lambda_role.add_to_policy(
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

        self.segment_caching_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["events:DescribeEventBus", "events:PutEvents"],
                resources=[
                    f"arn:aws:events:{Stack.of(self).region}:{Stack.of(self).account}:event-bus/{self.event_bus.event_bus_name}"
                ],
            )
        )

        self.segment_caching_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["execute-api:Invoke", "execute-api:ManageConnections"],
                resources=[
                    f"arn:aws:execute-api:{Stack.of(self).region}:{Stack.of(self).account}:*"
                ],
            )
        )

        self.segment_caching_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
                resources=[
                    f"arn:aws:s3:::{self.segment_cache_bucket_name}",
                    f"arn:aws:s3:::{self.segment_cache_bucket_name}/*",
                ],
            )
        )

        self.segment_caching_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["dynamodb:GetItem"],
                resources=[Fn.import_value("mre-plugin-table-arn")],
            )
        )

        self.segment_caching_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:DescribeParameters",
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                ],
                resources=[
                    f"arn:aws:ssm:{Stack.of(self).region}:{Stack.of(self).account}:parameter/MRE*"
                ],
            )
        )

        self.segment_caching_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={"StringEquals": {"cloudwatch:namespace": "MRE"}},
            )
        )

        # Function: SegmentCaching
        self.segment_caching_lambda = _lambda.Function(
            self,
            "Mre-SegmentCaching",
            description="Caches segments and related features outputted by MRE workflows in S3",
            runtime=_lambda.Runtime.PYTHON_3_11,
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/lambda/SegmentCaching"),
            handler="mre-segment-caching.lambda_handler",
            role=self.segment_caching_lambda_role,
            memory_size=10240,
            timeout=Duration.minutes(15),
            environment={
                "PLUGIN_TABLE": Fn.import_value("mre-plugin-table-name"),
                "SEGMENT_CACHE_BUCKET": self.segment_cache_bucket_name,
                "EB_EVENT_BUS_NAME": self.event_bus.event_bus_name,
                "ENABLE_CUSTOM_METRICS": "Y",
                "MAX_NUMBER_OF_THREADS": "10",
            },
            layers=[self.mre_workflow_helper_layer, self.mre_plugin_helper_layer],
        )

        self.mre_caching_events_rule = events.Rule(
            self,
            "MRESegmentEndRule",
            description="Rule that captures the MRE Lifecycle Event SEGMENT_END, OPTIMIZED_SEGMENT_END - Used for Segment Caching",
            enabled=True,
            event_bus=self.event_bus,
            event_pattern=events.EventPattern(
                source=["awsmre"],
                detail={"State": ["OPTIMIZED_SEGMENT_END", "SEGMENT_END"]},
            ),
            targets=[
                events_targets.LambdaFunction(handler=self.segment_caching_lambda)
            ],
        )
        self.mre_caching_events_rule.node.add_dependency(self.event_bus)
        self.mre_caching_events_rule.node.add_dependency(self.segment_caching_lambda)

        # cdk-nag suppressions
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-DDB3",
                    "reason": "DynamoDB Point-in-time Recovery not required in the default deployment mode. Customers can turn it on if required",
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
                    "reason": "SSM parameter access requires MRE parameter prefix wildcard",
                    "appliesTo": [
                        "Resource::arn:aws:ssm:<AWS::Region>:<AWS::AccountId>:parameter/MRE*"
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "EventBridge requires event bus ARN access",
                    "appliesTo": [
                        f"Resource::arn:aws:events:*:*:event-bus/{self.event_bus.event_bus_name}"
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "API Gateway execution requires regional wildcard permissions",
                    "appliesTo": [
                        "Resource::arn:aws:execute-api:<AWS::Region>:<AWS::AccountId>:*"
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "CloudWatch metrics require namespace-restricted wildcard",
                    "appliesTo": ["Resource::*"],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "S3 access requires bucket name pattern matching",
                    "appliesTo": [
                        {
                            "regex": "/^Resource::arn:aws:s3:::mre*\/*/",
                        },
                        {
                            "regex": "/^Resource::arn:aws:s3:::aws-mre-shared*\/*/",
                        },
                    ],
                },
            ],
        )

        NagSuppressions.add_resource_suppressions(
            self.segment_caching_lambda,
            [
                {
                    "id": "AwsSolutions-L1",
                    "reason": f"{Stack.of(self).stack_name} lambda function does not require the latest runtime version",
                }
            ],
        )
