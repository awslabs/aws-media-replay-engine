from aws_cdk import (
    aws_iam as iam,
    aws_logs as logs,
    aws_lambda as lambda_,
    custom_resources,
    RemovalPolicy,
    Duration,
    Stack,
    CustomResource,
    Fn
    
)
from constructs import Construct


class ApiGatewayLogging(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id)

        # Required parameters
        self.stack_name = kwargs.get('stack_name')
        self.api_gateway_logging_role_arn = kwargs.get('api_gateway_logging_role_arn')
        self.api_log_group_arn = Fn.import_value("mre-api-gateway-log-group-arn")
        self.rate_limit = kwargs.get('rate_limit')
        self.burst_limit = kwargs.get('burst_limit')
                    
        if not self.stack_name or not self.api_gateway_logging_role_arn:
            raise ValueError("stack_name and api_gateway_logging_role_arn are required parameters")


        # Create Lambda role for the custom resource
        enable_logging_role = iam.Role(
            self,
            "EnableLoggingRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for Lambda to enable API Gateway logging"
        )

        # Add API Gateway permissions
        enable_logging_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "apigateway:PUT",
                    "apigateway:GET",
                    "apigateway:PATCH",
                    "apigateway:POST"
                ],
                resources=["*"]
            )
        )

        # Add CloudWatch Logs permissions
        enable_logging_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/lambda/*"
                ]
            )
        )

        # Add IAM PassRole permission
        enable_logging_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["iam:PassRole"],
                resources=[self.api_gateway_logging_role_arn]
            )
        )

        # Create the custom resource provider
        provider = custom_resources.Provider(
            self,
            "EnableLoggingProvider",
            on_event_handler=lambda_.Function(
                self,
                "EnableLoggingHandler",
                runtime=lambda_.Runtime.PYTHON_3_12,
                memory_size=256,
                handler="index.handler",
                code=lambda_.Code.from_inline(self._get_lambda_code()),
                role=enable_logging_role,
                timeout=Duration.minutes(5)
            )
        )

        # Create the custom resource
        self.custom_resource = CustomResource(
            self,
            "EnableApiGatewayLogging",
            service_token=provider.service_token,
            properties={
                "StackName": "mre-live-news-segmenter-api",
                "CloudWatchRoleArn": self.api_gateway_logging_role_arn,
                "LogGrpArn": self.api_log_group_arn,
                "RateLimit": self.rate_limit,
                "BurstLimit": self.burst_limit
            },
            removal_policy=RemovalPolicy.DESTROY,
        )

    def _get_lambda_code(self) -> str:
        return """
import boto3
import cfnresponse
import time
import random
from botocore.exceptions import ClientError

def exponential_backoff(attempt, max_delay=80):
    #Implements exponential backoff with jitter
    delay = min(max_delay, (2 ** attempt) + random.uniform(0, 1))
    time.sleep(delay)

def retry_with_backoff(func, *args, max_attempts=5, **kwargs):
    #Retry function with exponential backoff
    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except ClientError as e:
            if e.response['Error']['Code'] == 'TooManyRequestsException':
                if attempt == max_attempts - 1:
                    raise
                exponential_backoff(attempt)
                continue
            raise
            
def handler(event, context):
    try:
        props = event.get('ResourceProperties', {})
        rate_limit = props.get('RateLimit', '25')
        burst_limit = props.get('BurstLimit', '15')
        if event['RequestType'] in ['Create', 'Update']:
            client = boto3.client('apigateway')
            apis = retry_with_backoff(client.get_rest_apis)
            
            api_id = None
            for item in apis['items']:
                if event['ResourceProperties']['StackName'] in item['name']:
                    api_id = item['id']
                    break
            
            if api_id:
                stages = retry_with_backoff(client.get_stages, restApiId=api_id)
                for stage in stages['item']:
                    retry_with_backoff(
                        client.update_stage,
                        restApiId=api_id,
                        stageName=stage['stageName'],
                        patchOperations=[
                            {
                                'op': 'replace',
                                'path': '/accessLogSettings/destinationArn',
                                'value': props['LogGrpArn'].replace(':*', '')
                            },
                            {
                                'op': 'replace',
                                'path': '/accessLogSettings/format',
                                'value': '$context.identity.sourceIp $context.identity.caller $context.identity.user [$context.requestTime] "$context.httpMethod $context.resourcePath $context.protocol" $context.status $context.responseLength $context.requestId'
                            },
                            {
                                'op': 'replace',
                                'path': '/*/*/logging/loglevel',
                                'value': 'INFO'
                            },
                            {
                                'op': 'replace',
                                'path': '/*/*/logging/dataTrace',
                                'value': 'true'
                            },
                            {
                                'op': 'replace',
                                'path': '/*/*/metrics/enabled',
                                'value': 'true'
                            },
                            {
                                'op': 'replace',
                                'path': '/*/*/throttling/rateLimit',
                                'value': rate_limit
                            },
                            {
                                'op': 'replace',
                                'path': '/*/*/throttling/burstLimit',
                                'value': burst_limit
                            }
                        ]
                    )
                    
                    deployment = retry_with_backoff(
                        client.create_deployment,
                        restApiId=api_id,
                        description='Deployment for enabling logging'
                    )
                    
                    retry_with_backoff(
                        client.update_stage,
                        restApiId=api_id,
                        stageName=stage['stageName'],
                        patchOperations=[
                            {
                                'op': 'replace',
                                'path': '/deploymentId',
                                'value': deployment['id']
                            }
                        ]
                    )
            
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
        else:
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
            
    except Exception as e:
        print(e)
        cfnresponse.send(event, context, cfnresponse.FAILED, {})
"""
