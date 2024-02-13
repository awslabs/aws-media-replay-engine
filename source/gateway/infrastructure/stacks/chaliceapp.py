import os

from aws_cdk import (
    CfnOutput,
    Fn,
    Stack,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_secretsmanager as secret_mgr
)
from chalice.cdk import Chalice
from cdk_nag import NagSuppressions

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')

class ChaliceApp(Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # Chalice IAM Role
        self.chalice_role = iam.Role(
            self,
            "MreApiChaliceRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE API Gateway Lambda Function"
        )
        
        # Chalice IAM Role: CloudWatch Logs permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:*"
                ]
            )
        )

        self.chalice_role.add_to_policy(
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

        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "execute-api:Invoke",
                    "execute-api:ManageConnections"
                ],
                resources=[f"arn:aws:execute-api:{Stack.of(self).region}:{Stack.of(self).account}:*"]
            )
        )

        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "servicediscovery:ListInstances"
                ],
                resources=["*"]     #Selected actions only support the all resources wildcard('*').
            )
        )

        self.hsa_api_auth_secret = secret_mgr.Secret(self, "MRE_HSA_API_AUTH_SECRET", secret_name="mre_hsa_api_auth_secret")
        self.hsa_api_auth_secret.grant_read(self.chalice_role)

        # Chalice IAM Role: Secrets Manager permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret"
                ],
                resources=[
                    self.hsa_api_auth_secret.secret_arn
                ]
            )
        )

        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:CreateSecret",
                    "secretsmanager:UpdateSecret",
                    "secretsmanager:DeleteSecret",
                    "secretsmanager:TagResource"
                ],
                resources=[
                    f"arn:aws:secretsmanager:{Stack.of(self).region}:{Stack.of(self).account}:secret:/MRE*"
                ]
            )
        )

        self.chalice = Chalice(
            self,
            "MreApiChaliceApp",
            source_dir=RUNTIME_SOURCE_DIR,
            stage_config={
                "environment_variables": {
                    "PLUGIN_URL": Fn.import_value("mre-plugin-api-url"),
                    "MODEL_URL" : Fn.import_value("mre-model-api-url"),
                    "CONTENT_GROUP_URL" : Fn.import_value("mre-contentgroup-api-url"),
                    "EVENT_URL": Fn.import_value("mre-event-api-url"),
                    "PROFILE_URL" : Fn.import_value("mre-profile-api-url"),
                    "PROGRAM_URL" : Fn.import_value("mre-program-api-url"),
                    "REPLAY_URL" : Fn.import_value("mre-replay-api-url"),
                    "SYSTEM_URL" : Fn.import_value("mre-system-api-url"),
                    "WORKFLOW_URL" : Fn.import_value("mre-workflow-api-url"),
                    "CUSTOM_PRIORITIES_URL": Fn.import_value("mre-custompriorities-api-url"),
                    "API_AUTH_SECRET_KEY_NAME": "mre_hsa_api_auth_secret"
                },
                "tags": {
                    "Project": "MRE"
                },
                "manage_iam_role": False,
                "iam_role_arn": self.chalice_role.role_arn
            }
        )

        

        # Store the API Gateway endpoint output of Chalice in SSM Parameter Store
        ssm.StringParameter(
            self,
            "MREGatewayEndpointParam",
            string_value=self.chalice.sam_template.get_output("EndpointURL").value,
            parameter_name="/MRE/ControlPlane/EndpointURL",
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
            description="[DO NOT DELETE] Parameter contains the AWS MRE Gateway API Endpoint URL"
        )


        CfnOutput(self, "mre-default-api-gateway", value=self.chalice.sam_template.get_output("EndpointURL").value, description="MRE default API Gateway Url", export_name="mre-default-api-gateway-url" )


        # cdk-nag suppressions
        NagSuppressions.add_stack_suppressions(
            self,
            [
                
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Chalice role policy requires wildcard permissions for CloudWatch logging, mediaconvert, eventbus, s3",
                    "appliesTo": [
                        "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:*",
                        "Resource::arn:aws:ssm:<AWS::Region>:<AWS::AccountId>:parameter/MRE*",
                        "Resource::arn:aws:execute-api:<AWS::Region>:<AWS::AccountId>:*",
                        "Resource::arn:aws:secretsmanager:<AWS::Region>:<AWS::AccountId>:secret:/MRE*",
                        "Resource::*"
                    ]
                },
                {
                    "id": "AwsSolutions-SMG4",
                    "reason": "By default no Secrets are created although the keys are created. Customers have to define these if the feature is being used."
                }
            ]
        )