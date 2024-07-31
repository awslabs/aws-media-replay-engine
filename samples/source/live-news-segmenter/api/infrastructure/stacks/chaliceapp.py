#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import sys

import aws_cdk as cdk
from aws_cdk import (
    Fn,
    CustomResource,
    RemovalPolicy,
    Stack,
    Duration,
    CfnOutput,
    aws_dynamodb as ddb,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_lambda_event_sources as _lambda_es,
    aws_sqs as sqs,
    aws_ssm as ssm,
    aws_s3 as s3,
    custom_resources as cr,
    aws_logs as logs,
)
from chalice.cdk import Chalice
from cdk_nag import NagSuppressions


RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')

class ChaliceApp(Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        self.result_table_arn = Fn.import_value("mre-plugin-result-table-arn")
        self.result_table_name = Fn.import_value("mre-plugin-result-table-name")
        
        self.event_table_arn = Fn.import_value("mre-event-table-arn")
        self.event_table_name = Fn.import_value("mre-event-table-name")

        self.gen_ai_prompt_templates_table_name = Fn.import_value("mre-gen-ai-prompt-templates-table-name")
        self.gen_ai_prompt_templates_table_arn = Fn.import_value("mre-gen-ai-prompt-templates-table-arn")
        
        # Define the Share Link S3 bucket
        # self.share_link_bucket = s3.Bucket(
        #     self,
        #     'WlMreShareLinkBucket',
        #     enforce_ssl=True,
        #     encryption=s3.BucketEncryption.S3_MANAGED
        # )
        
        # Define the User Favorites table
        self.user_favorites_table = ddb.Table(
            self,
            "UserFavorites",
            partition_key=ddb.Attribute(
                name="program-event-user",
                type=ddb.AttributeType.STRING
            ),
            sort_key=ddb.Attribute(
                name="start",
                type=ddb.AttributeType.NUMBER
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # Chalice IAM Role
        self.chalice_role = iam.Role(
            self,
            "ChaliceRole",
            assumed_by=iam.ServicePrincipal(service="lambda.amazonaws.com"),
            description="Role used by the MRE Custom Chalice Lambda function"
        )
        # Chalice IAM Role: DynamoDB permissions
        self.chalice_role.add_to_policy(
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
                    "dynamodb:DeleteItem",
                    "dynamodb:PartiQLSelect"
                ],
                resources=[
                    self.result_table_arn,
                    f"{self.result_table_arn}/index/*",
                    self.event_table_arn,
                    f"{self.event_table_arn}/index/*",
                    self.user_favorites_table.table_arn,
                    f"{self.user_favorites_table.table_arn}/index/*",
                    self.gen_ai_prompt_templates_table_arn,
                    f"{self.gen_ai_prompt_templates_table_arn}/index/*"
                ]
            )
        )
        
        # Chalice IAM Role: S3 Read permissions
        # self.chalice_role.add_to_policy(
        #     iam.PolicyStatement(
        #         effect=iam.Effect.ALLOW,
        #         actions=["s3:ListBucket", "s3:*Object"],
        #         resources=[
        #             f"arn:aws:s3:::{self.share_link_bucket.bucket_name}",
        #             f"arn:aws:s3:::{self.share_link_bucket.bucket_name}/*"
        #         ]
        #     )
        # )
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject"],
                resources=[f"arn:aws:s3:::*"]
            )
        )

        # Chalice IAM Role: medialive permissions
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "medialive:DescribeInput",
                    "medialive:DescribeChannel",
                    "medialive:DescribeInputDevice"
                ],
                resources=[
                    f"arn:aws:medialive:{Stack.of(self).region}:{Stack.of(self).account}:channel:*",
                    f"arn:aws:medialive:{Stack.of(self).region}:{Stack.of(self).account}:input:*",
                    f"arn:aws:medialive:{Stack.of(self).region}:{Stack.of(self).account}:input-device:*"
                ]
            )
        )
        
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{Stack.of(self).region}::foundation-model/cohere.embed-english-v3",
                    f"arn:aws:bedrock:{Stack.of(self).region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
                    f"arn:aws:bedrock:{Stack.of(self).region}::foundation-model/amazon.titan-embed-text-v2:0"
                ]
            )
        )
        
        # Create a log group
        # self.log_group = logs.LogGroup(
        #     self, 
        #     'LogGroup',
        #     log_group_name='/aws/lambda/wl-mre-custom-api-APIHandler-indgxS3MhQun',
        #     removal_policy=cdk.RemovalPolicy.DESTROY)
        
        self.chalice_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=['logs:CreateLogStream', 'logs:PutLogEvents', 'logs:CreateLogGroup'],
                resources=[self.log_group.log_group_arn]
            )
        )
        
        self.chalice = Chalice(
            self,
            "ChaliceApp",
            source_dir=RUNTIME_SOURCE_DIR,
            stage_config={
                "environment_variables": {
                    "PLUGIN_RESULT_TABLE_NAME": self.result_table_name,
                    "EVENTS_TABLE_NAME": self.event_table_name,
                    # "SHARE_LINK_BUCKET_NAME": self.share_link_bucket.bucket_name,
                    "USER_FAVORITES_TABLE_NAME": self.user_favorites_table.table_name,
                    "GEN_AI_TEMPLATES_TABLE_NAME": self.gen_ai_prompt_templates_table_name
                },
                "tags": {
                    "Project": "WL MRE"
                },
                "manage_iam_role": False,
                "iam_role_arn": self.chalice_role.role_arn,
                "lambda_memory_size": 512
            }
        )
                
        # cdk-nag suppressions
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-DDB3",
                    "reason": "DynamoDB Point-in-time Recovery not required as the data stored is non-critical and can be recreated"
                },
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "CDK custom resource provider uses AWS Managed Policies",
                    "appliesTo": [
                        "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                    ]
                },
                {
                    "id": "AwsSolutions-S1",
                    "reason": "Logging can be enabled if reqd in higher environments"
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "MRE internal lambda IAM role policies require wildcard permissions for CloudWatch, S3, DynamoDB and medialive",
                    "appliesTo": [
                        "Action::s3:GetObject*",
                        "Action::s3:GetBucket*",
                        "Action::s3:Describe*",
                        "Action::s3:List*",
                        "Action::s3:DeleteObject*",
                        "Action::s3:Abort*",
                        "Action::s3:Put*",
                        "Action::s3:Get*",
                        "Action::s3:*Object",
                        "Resource::arn:aws:s3:::*",
                        # "Resource::arn:aws:s3:::<WlMreShareLinkBucket95C286D2>/*",
                        "Resource::arn:aws:medialive:<AWS::Region>:<AWS::AccountId>:channel:*",
                        "Resource::arn:aws:medialive:<AWS::Region>:<AWS::AccountId>:input:*",
                        "Resource::arn:aws:medialive:<AWS::Region>:<AWS::AccountId>:input-device:*",
                        "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:*",
                        {
                            "regex": "/^Resource::<.*.+Arn>:\\*$/"
                        },
                        {
                            "regex": "/^Resource::.*/index/\\*$/"
                        }
                    ]
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "MRE internal lambda functions do not require the latest runtime version as their dependencies have been tested only on Python 3.11"
                }
            ]
        )
        
        CfnOutput(self, "mre-custom-api-url", value=self.chalice.sam_template.get_output("EndpointURL").value, description="MRE Custom  API Url", export_name="mre-custom-api-url" )