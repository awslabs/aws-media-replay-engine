import os
import sys
from aws_cdk import (
    CfnOutput,
    Fn,
    Stack,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_secretsmanager as secret_mgr,
)
from chalice.cdk import Chalice
from cdk_nag import NagSuppressions

# Ask Python interpreter to search for modules in the topmost folder. This is required to access the shared.infrastructure.helpers module
sys.path.append("../../")
from shared.infrastructure.helpers import common, api_logging_construct


RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, "runtime"
)


class ChaliceApp(Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.mre_api_gateway_logging_role_arn = Fn.import_value("mre-api-gateway-logging-role-arn")
        self.powertools_layer = common.MreCdkCommon.get_powertools_layer_from_arn(self)

        # Enable API Gateway logging through Custom Resources
        api_logging_construct.ApiGatewayLogging(
            self, 
            "GatewayApi",
            stack_name=self.stack_name,
            api_gateway_logging_role_arn=self.mre_api_gateway_logging_role_arn,
            rate_limit=25,
            burst_limit=15
        )

        # Chalice IAM Role
        self.chalice_role = iam.Role(
            self,
            "MreApiChaliceRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE API Gateway Lambda Function",
        )

        # Chalice IAM Role: CloudWatch Logs permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/lambda/{Stack.of(self).stack_name}-*",
                ],
            )
        )
        self.chalice_role.add_to_policy(
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

        self.chalice_role.add_to_policy(
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

        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["execute-api:Invoke", "execute-api:ManageConnections"],
                resources=[
                    f"arn:aws:execute-api:{Stack.of(self).region}:{Stack.of(self).account}:*"
                ],
            )
        )

        self.hsa_api_auth_secret = secret_mgr.Secret(
            self, "MRE_HSA_API_AUTH_SECRET", secret_name="mre_hsa_api_auth_secret"
        )
        self.hsa_api_auth_secret.grant_read(self.chalice_role)

        self.jwt_issuer = secret_mgr.Secret(
            self, "MRE_JWT_ISSUER", secret_name="mre_jwt_issuer"
        )
        self.jwt_issuer.grant_read(self.chalice_role)

        # Chalice IAM Role: Secrets Manager permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=[self.hsa_api_auth_secret.secret_arn, self.jwt_issuer.secret_arn]
            )
        )

        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:CreateSecret",
                    "secretsmanager:UpdateSecret",
                    "secretsmanager:DeleteSecret",
                    "secretsmanager:TagResource",
                ],
                resources=[
                    f"arn:aws:secretsmanager:{Stack.of(self).region}:{Stack.of(self).account}:secret:/MRE*"
                ],
            )
        )

        stage_config = {
            "environment_variables": {
                "PLUGIN_URL": Fn.import_value("mre-plugin-api-url"),
                "MODEL_URL": Fn.import_value("mre-model-api-url"),
                "PROMPT_CATALOG_URL": Fn.import_value("mre-prompt-catalog-api-url"),
                "CONTENT_GROUP_URL": Fn.import_value("mre-contentgroup-api-url"),
                "EVENT_URL": Fn.import_value("mre-event-api-url"),
                "PROFILE_URL": Fn.import_value("mre-profile-api-url"),
                "PROGRAM_URL": Fn.import_value("mre-program-api-url"),
                "REPLAY_URL": Fn.import_value("mre-replay-api-url"),
                "SYSTEM_URL": Fn.import_value("mre-system-api-url"),
                "WORKFLOW_URL": Fn.import_value("mre-workflow-api-url"),
                "CUSTOM_PRIORITIES_URL": Fn.import_value(
                    "mre-custompriorities-api-url"
                ),
                "API_AUTH_SECRET_KEY_NAME": "mre_hsa_api_auth_secret",
                "MRE_JWT_ISSUER": "mre_jwt_issuer"
            },
            "tags": {"Project": "MRE"},
            "manage_iam_role": False,
            "iam_role_arn": self.chalice_role.role_arn,
            "layers": [self.powertools_layer.layer_version_arn]
        }

        if self.node.try_get_context("GENERATIVE_AI"):
            stage_config["environment_variables"]["PROMPT_CATALOG_URL"] = (
                Fn.import_value("mre-prompt-catalog-api-url")
            )

        self.chalice = Chalice(
            self,
            "MreApiChaliceApp",
            source_dir=RUNTIME_SOURCE_DIR,
            stage_config=stage_config,
        )

        # Store the API Gateway endpoint output of Chalice in SSM Parameter Store
        ssm.StringParameter(
            self,
            "MREGatewayEndpointParam",
            string_value=self.chalice.sam_template.get_output("EndpointURL").value,
            parameter_name="/MRE/ControlPlane/EndpointURL",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the AWS MRE Gateway API Endpoint URL",
        )

        CfnOutput(
            self,
            "mre-default-api-gateway",
            value=self.chalice.sam_template.get_output("EndpointURL").value,
            description="MRE default API Gateway Url",
            export_name="mre-default-api-gateway-url",
        )

        CfnOutput(
            self,
            "mre-default-api-gateway-api-id",
            value=self.chalice.get_resource("RestAPI").ref,
            description="MRE default API Gateway REST API ID",
            export_name="mre-default-api-gateway-rest-api-id",
        )

        # cdk-nag suppressions
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Chalice role policy requires wildcard permissions for CloudWatch logging, mediaconvert, eventbus, s3",
                    "appliesTo": [
                        "Resource::arn:aws:ssm:<AWS::Region>:<AWS::AccountId>:parameter/MRE*",
                        "Resource::arn:aws:execute-api:<AWS::Region>:<AWS::AccountId>:*",
                        "Resource::arn:aws:secretsmanager:<AWS::Region>:<AWS::AccountId>:secret:/MRE*",
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Lambda logging requires access to CloudWatch log groups",
                    "appliesTo": [
                        f"Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/lambda/{Stack.of(self).stack_name}-*",
                        "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:*",
                    ],
                },
                {
                    "id": "AwsSolutions-SMG4",
                    "reason": "By default no Secrets are created although the keys are created. Customers have to define these if the feature is being used.",
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
                    "appliesTo": ["Resource::<GatewayApiEnableLoggingHandlerFAA2D1E0.Arn>:*"]
                }
            ],
        )
