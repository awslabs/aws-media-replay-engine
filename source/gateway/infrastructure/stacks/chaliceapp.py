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
                    "arn:*:logs:*:*:*"
                ]
            )
        )

        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:DescribeParameters",
                    "ssm:GetParameter*"
                ],
                resources=["arn:aws:ssm:*:*:parameter/MRE*"]
            )
        )

        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "execute-api:Invoke",
                    "execute-api:ManageConnections"
                ],
                resources=["arn:aws:execute-api:*:*:*"]
            )
        )

        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "servicediscovery:ListInstances"
                ],
                resources=["arn:aws:servicediscovery:*:*:*"]
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
                    "arn:aws:secretsmanager:*:*:secret:/MRE*"
                ]
            )
        )

        self.chalice = Chalice(
            self,
            "MreApiChaliceApp",
            source_dir=RUNTIME_SOURCE_DIR,
            stage_config={
                "environment_variables": {
                    "SERVICE_DISC_SERVICE_ID": Fn.import_value("mre-service-disc-service-id"),
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