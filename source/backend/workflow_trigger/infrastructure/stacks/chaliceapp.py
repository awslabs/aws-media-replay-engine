import os
import sys
from aws_cdk import (
    CfnOutput,
    Aws,
    Stack,
    Duration,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_s3 as s3,
    aws_s3_notifications as s3n
)
from cdk_nag import NagSuppressions

# Ask Python interpreter to search for modules in the topmost folder. This is required to access the shared.infrastructure.helpers module
sys.path.append('../../../')

from shared.infrastructure.helpers import common

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')


class ChaliceApp(Stack):

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
                resources=[f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:*"]
            )
        )

        # TriggerMREWorkflowLambdaRole: SSM Parameter Store permissions
        self.trigger_mre_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:DescribeParameters",
                    "ssm:GetParameter",
                    "ssm:GetParameters"
                ],
                resources=[f"arn:aws:ssm:{Stack.of(self).region}:{Stack.of(self).account}:parameter/MRE*"]
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
                resources=[f"arn:aws:execute-api:{Stack.of(self).region}:{Stack.of(self).account}:*"]
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
                    f"arn:aws:states:{Stack.of(self).region}:{Stack.of(self).account}:stateMachine:*"
                ]
            )
        )

        # Function: TriggerMREWorkflow
        self.trigger_mre_workflow_lambda = _lambda.Function(
            self,
            "TriggerMREWorkflow",
            description="Execute MRE StepFunction workflow for every HLS video segment (.ts) file stored in S3",
            runtime=_lambda.Runtime.PYTHON_3_11,
            code=_lambda.Code.from_asset(f"{RUNTIME_SOURCE_DIR}/lambda"),
            handler="lambda_function.lambda_handler",
            role=self.trigger_mre_lambda_role,
            memory_size=128,
            timeout=Duration.minutes(1),
            layers=[self.mre_workflow_helper_layer]
        )

        # S3 Event Source for TriggerMREWorkflow Lambda
        self.mre_media_source_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(self.trigger_mre_workflow_lambda),
            s3.NotificationKeyFilter(suffix=".ts")
        )

        # BYOB permissions to allow S3 buckets to invoke SF
        byob_permission = _lambda.CfnPermission(
            self,
            "s3_invocation",
            action="lambda:InvokeFunction",
            function_name=self.trigger_mre_workflow_lambda.function_name,
            source_arn=f"arn:aws:s3:::*",
            source_account=Aws.ACCOUNT_ID,
            principal="s3.amazonaws.com",
        )

        CfnOutput(self, "mre-trigger-workflow-lambda-arn", value=self.trigger_mre_workflow_lambda.function_arn,
                      description="ARN of the Lambda function to invoke with S3 Trigger",
                      export_name="mre-trigger-workflow-lambda-arn")

        ### END: TriggerMREWorkflow LAMBDA ###

        NagSuppressions.add_stack_suppressions(
            self,
            [
                
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AWS managed policies allowed",
                    "appliesTo": [
                        "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                    ]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Role policy requires wildcard permissions for CloudWatch logging, mediaconvert, eventbus, s3",
                    "appliesTo": [
                        f"Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:*",
                        "Resource::arn:aws:ssm:<AWS::Region>:<AWS::AccountId>:parameter/MRE*",
                        "Resource::arn:aws:execute-api:<AWS::Region>:<AWS::AccountId>:*",
                        "Resource::arn:aws:lambda:<AWS::Region>:<AWS::AccountId>:function:*",
                        "Resource::arn:aws:states:<AWS::Region>:<AWS::AccountId>:stateMachine:*",
                        "Resource::*"
                    ]
                },
            ]
        )
        NagSuppressions.add_resource_suppressions_by_path(
            self,
            "aws-mre-workflow-trigger/TriggerMREWorkflow/Resource",
            [
                {
                    "id": "AwsSolutions-L1",
                    "reason": "TriggerMREWorkflow lambda function does not require the latest runtime version"
                }
            ]
        )