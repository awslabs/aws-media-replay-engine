import os
import sys

from aws_cdk import (
    core as cdk,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_s3 as s3,
    aws_s3_notifications as s3n
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
        self.mre_media_source_bucket = common.MreCdkCommon.get_media_source_bucket(self)

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
            description="Execute MRE StepFunction workflow for every HLS video segment (.ts) file stored in S3",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/lambda"),
            handler="lambda_function.lambda_handler",
            role=self.trigger_mre_lambda_role,
            memory_size=128,
            timeout=cdk.Duration.minutes(1),
            layers=[self.mre_workflow_helper_layer]
        )

        # S3 Event Source for TriggerMREWorkflow Lambda
        self.mre_media_source_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(self.trigger_mre_workflow_lambda),
            s3.NotificationKeyFilter(suffix=".ts")
        )

        ### END: TriggerMREWorkflow LAMBDA ###
