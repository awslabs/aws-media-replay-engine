import os
import sys
from aws_cdk import (
    Duration,
    Stack,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as events_targets,
    lambda_layer_awscli as awscli
)

# Ask Python interpreter to search for modules in the topmost folder. This is required to access the shared.infrastructure.helpers module
sys.path.append('../../../')


from shared.infrastructure.helpers import common

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')


class MreDataExporter(Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Get the Existing MRE EventBus as IEventBus
        self.event_bus = common.MreCdkCommon.get_event_bus(self)

        # Get MediaConvert Bucket Name from SSM
        self.data_export_bucket_name = common.MreCdkCommon.get_data_export_bucket_name()
        self.segment_cache_bucket_name = common.MreCdkCommon.get_segment_cache_bucket_name(self)

        # Get Layers
        self.mre_workflow_helper_layer = common.MreCdkCommon.get_mre_workflow_helper_layer_from_arn(self)
        self.mre_plugin_helper_layer = common.MreCdkCommon.get_mre_plugin_helper_layer_from_arn(self)



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
                    f"arn:aws:events:*:*:event-bus/{self.event_bus.event_bus_name}"
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
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/lambda"),
            handler="mre_data_exporter.GenerateDataExport",
            role=self.event_data_export_lambda_role,
            memory_size=2096,
            timeout=Duration.minutes(15),
            environment={
                "ExportOutputBucket": self.data_export_bucket_name,
                "EB_EVENT_BUS_NAME": self.event_bus.event_bus_name,
                "CACHE_BUCKET_NAME": self.segment_cache_bucket_name,
            },
            layers=[self.mre_workflow_helper_layer, self.mre_plugin_helper_layer]
        )
        self.event_data_export_lambda.add_layers(awscli.AwsCliLayer(self, "AwsCliLayer"))


        
        ### END: event-data_export-generator LAMBDA ###

        self.mre_event_data_export_rule = events.Rule(
            self,
            "MREEventDataExportRule",
            description="Rule that captures the MRE Lifecycle Event CLIP_GEN_DONE, CLIP_GEN_DONE_WITH_CLIPS, REPLAY_PROCESSED_WITH_CLIP and REPLAY_PROCESSED - Data Export",
            enabled=True,
            event_bus=self.event_bus,
            event_pattern=events.EventPattern(
                source=["awsmre"],
                detail={
                    "State":  ["CLIP_GEN_DONE", "REPLAY_PROCESSED", "REPLAY_PROCESSED_WITH_CLIP"]
                }
            ),
            targets=[
                events_targets.LambdaFunction(
                    handler=self.event_data_export_lambda
                )
            ]
        )
        self.mre_event_data_export_rule.node.add_dependency(self.event_bus)
        self.mre_event_data_export_rule.node.add_dependency(self.event_data_export_lambda)

    