#  Copyright 2024 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json
from aws_cdk import (
    Duration,
    Stack,
    RemovalPolicy,
    CfnOutput as cfn_output,
    aws_dynamodb as ddb,
    aws_lambda as lambda_,
    aws_opensearchserverless as opensearchserverless,
    aws_iam as iam,
    aws_lambda_nodejs as lambda_nodejs,
    aws_ssm as ssm,
    custom_resources as cr,
    CustomResource,
    aws_lambda_python_alpha as _lambdapython,
    aws_logs as logs,
)
from constructs import Construct
from cdk_nag import NagSuppressions

GENAI_SEARCH_PROMPT_NAME = "MRE_GENAI_SEARCH_PROMPT"
GENAI_SEARCH_PROMPT = """<context>
{context}
</context>

<instructions>
Using the provided context and if applicable, the chat history, answer the question listed in the <question> tags. Follow these guidelines:

1. Think step-by-step within <thinking></thinking> tags.
2. Ignore overlapping or duplicate information in the context.
3. Provide your output in JSON format. Skip the preamble.
4. Include a 'Summary' key with a concise summary of the relevant context provided to you for answering the question.
5. Group your responses into sentence groups and associate each sentence group with the 'Content' key. Do not include timestamps in the 'Content' text.
6. Include the estimated start and end timings for each sentence group under the 'Start' and 'End' keys. You should estimate the start and end timings using the timestamps available in the context. Use the calculator and/or number_compare tools for accurate estimation.
7. If the question asks for a specific duration, you would need to calculate the duration of each sentence group by subtracting the respective 'Start' timing from the 'End' timing (i.e., End - Start) using the calculator tool. Then, find and include sentence groups most relevant to the question as long as the sum of all their duration (calculated using the calculator tool) does not exceed the requested duration.
8. For each sentence group, create a short title and include it under the 'Title' key.
9. Create a list of JSON objects with each sentence group being an object in the list. Sort the JSON list in ascending order based on the 'Start' key using the sort_list_by_key tool. The expected output of the sorted list should be: [{'Start': 10, 'End': 25, 'Title': 'ABC', 'Content': 'XYZ'}, {'Start': 30, 'End': 45, 'Title': 'DEF', 'Content': 'XYZ'}, ... ].
10. Add the sorted list of JSON objects under the key 'Details'.
11. Include both the 'Summary' and 'Details' keys in your final JSON output.
12. If you cannot answer the question from the context, please say so in your response under the 'Summary' key. Also, include a new key called 'OutOfContext' and do not include the 'Details' key.
13. The text content of 'Summary', 'Title' and 'Content' keys should be translated to the same language as the question unless the question requests for a specific language translation. If you can neither understand the language of the question nor the language translation requested in the question, generate the text content for the aforementioned keys in English.
14. Put your overall JSON response within <response></response> XML tags and do not output any other text before or after the XML tags.
</instructions>

<question>
{question}
</question>

Assistant: <"""


class GenAISearchStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vectorsearch_collection_name = "mre-vectorsearch-collection"
        self.summary_collection_name = "mre-summary-collection"
        # Get AOSS parameters from SSM
        self.aoss_detail_search_endpoint = ssm.StringParameter.value_from_lookup(
            self, "/MRE/DataPlane/AossDetailSearchEndpointURL"
        )
        self.aoss_detail_search_index = ssm.StringParameter.value_from_lookup(
            self, "/MRE/DataPlane/AossDetailedSearchIndex"
        )
        # Get System DDB table name and arn from SSM
        self.system_table_name = ssm.StringParameter.value_from_lookup(
            self, "/MRE/ControlPlane/SystemTableName"
        )
        self.system_table_arn = ssm.StringParameter.value_from_lookup(
            self, "/MRE/ControlPlane/SystemTableArn"
        )

        # Lambda function to store the Gen AI search prompt in the System DDB table
        self.store_search_prompt_lambda = _lambdapython.PythonFunction(
            self,
            "SearchPromptInsertFunction",
            description="Insert the default Gen AI search prompt into the System DDB table",
            runtime=lambda_.Runtime.PYTHON_3_11,
            index="lambda_function.py",
            handler="on_event",
            entry="lambda/SearchPromptInsertHandler",
            memory_size=256,
            timeout=Duration.minutes(1),
        )

        # Grant DDB permissions to the SearchPromptInsertFunction
        self.store_search_prompt_lambda.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:PutItem",
                    "dynamodb:ConditionCheckItem",
                ],
                resources=[self.system_table_arn],
            )
        )

        # Store Search Prompt Custom Resource Provider
        self.store_search_prompt_cr_provider = cr.Provider(
            self,
            "StoreSearchPromptCRProvider",
            on_event_handler=self.store_search_prompt_lambda,
            log_retention=logs.RetentionDays.TEN_YEARS
        )

        # Store Search Prompt Custom Resource
        self.store_search_prompt_cr = CustomResource(
            self,
            "StoreSearchPromptCR",
            service_token=self.store_search_prompt_cr_provider.service_token,
            removal_policy=RemovalPolicy.DESTROY,
            properties={
                "system_table_name": self.system_table_name,
                "genai_search_prompt_name": GENAI_SEARCH_PROMPT_NAME,
                "genai_search_prompt": GENAI_SEARCH_PROMPT,
                "version": "v1",  # Dummy property to force CDK to invoke the CR during redeployment
            },
        )

        # DynamoDB table to store conversation history
        self.conversation_history_table = ddb.Table(
            self,
            "ConversationHistoryTable",
            partition_key=ddb.Attribute(
                name="SessionId", type=ddb.AttributeType.STRING
            ),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
            point_in_time_recovery=True  # Enables point-in-time recovery
        )

        # Lambda function to perform the GenAI Search
        self.genai_search_fn = lambda_nodejs.NodejsFunction(
            self,
            "GenAISearchFn",
            entry="lambda/GenAISearchHandler/index.mjs",
            bundling=lambda_nodejs.BundlingOptions(
                node_modules=[
                    "@aws-sdk/client-bedrock",
                    "@aws-sdk/client-bedrock-runtime",
                    "@aws-sdk/client-dynamodb",
                    "@opensearch-project/opensearch",
                    "@langchain/core",
                    "@langchain/community",
                    "@langchain/aws",
                ],
                force_docker_bundling=True,
            ),
            deps_lock_file_path="lambda/GenAISearchHandler/package-lock.json",
            handler="handler",
            runtime=lambda_.Runtime.NODEJS_20_X,
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                "GENAI_SEARCH_PROMPT_NAME": GENAI_SEARCH_PROMPT_NAME,
                "OPENSEARCH_DETAILSEARCH_ENDPOINT": self.aoss_detail_search_endpoint,
                "OPENSEARCH_DETAILSEARCH_INDEX": self.aoss_detail_search_index,
                "SYSTEM_TABLE_NAME": self.system_table_name,
                "CONVERSATION_HISTORY_TABLE_NAME": self.conversation_history_table.table_name,
                "OSS_QUERY_SIZE": "30",
                "OSS_QUERY_K_VALUE": "20",
            },
        )

        # GenAISearchFn - AOSS Permissions
        self.genai_search_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["aoss:APIAccessAll"],
                resources=[
                    f"arn:aws:aoss:{Stack.of(self).region}:{Stack.of(self).account}:collection/{self.aoss_detail_search_endpoint.split('https://')[-1].split('.')[0]}",
                ],
            )
        )

        # GenAISearchFn - Bedrock Permissions
        self.genai_search_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:ListInferenceProfiles",
                ],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/*",  # Using * for region to support cross-region invocation
                    f"arn:aws:bedrock:{Stack.of(self).region}:{Stack.of(self).account}:inference-profile/*",
                ],
            )
        )

        # GenAISearchFn - DynamoDB Permissions
        self.genai_search_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:DescribeTable",
                    "dynamodb:Query",
                    "dynamodb:BatchGetItem",
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                ],
                resources=[
                    self.system_table_arn,
                    self.conversation_history_table.table_arn,
                ],
            )
        )

        # Function URL for GenAISearchFn
        self.genai_search_fn_url = self.genai_search_fn.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.AWS_IAM,
            invoke_mode=lambda_.InvokeMode.RESPONSE_STREAM,
            cors=lambda_.FunctionUrlCorsOptions(
                allowed_origins=["*"],
                allowed_methods=[lambda_.HttpMethod.POST],
                allowed_headers=["*"],
                exposed_headers=["*"],
                allow_credentials=False,
                max_age=Duration.minutes(10),
            ),
        )
        # Add the Function URL to CloudFormation Output
        cfn_output(self, "MREGenAISearchFnUrl", value=self.genai_search_fn_url.url, description="MRE Natural language search API Url", export_name="mre-genai-search-url",)
        cfn_output(self, "MREGenAISearchFnArn", value=self.genai_search_fn.function_arn, description="MRE Natural language search API Arn", export_name="mre-genai-search-arn",)

        # Store the Function URL in SSM
        ssm.StringParameter(
            self,
            "mre-genai-search-fn-url-param",
            parameter_name="/MRE/GenAISearch/EndpointURL",
            string_value=self.genai_search_fn_url.url,
        )

        self.access_policy_json = [
            {
                "Rules": [
                    {
                        "Resource": [
                            f"collection/{self.vectorsearch_collection_name}",
                            f"collection/{self.summary_collection_name}",
                        ],
                        "Permission": [
                            "aoss:DescribeCollectionItems",
                        ],
                        "ResourceType": "collection",
                    },
                    {
                        "Resource": [
                            f"index/{self.vectorsearch_collection_name}/*",
                            f"index/{self.summary_collection_name}/*",
                        ],
                        "Permission": [
                            "aoss:DescribeIndex",
                            "aoss:ReadDocument",
                        ],
                        "ResourceType": "index",
                    },
                ],
                "Principal": [
                    self.genai_search_fn.role.role_arn,
                ],
            }
        ]

        # Create a new AOSS Access Policy for GenAISearchFn
        opensearchserverless.CfnAccessPolicy(
            self,
            "OpenSearchAccessPolicy",
            name="mre-genai-search-access-policy",
            description="Access policy for the MRE GenAI Search Lambda function",
            type="data",
            policy=json.dumps(self.access_policy_json),
        )

        # cdk-nag suppressions
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-DDB3",
                    "reason": "DynamoDB Point-in-time Recovery not required as the data stored is non-critical and can be recreated",
                },
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AWS managed policies allowed",
                    "appliesTo": [
                        "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Wildcard permissions are allowed for GenAI Search Lambda function to support the Bedrock Converse API and cross-region inference profiles",
                    "appliesTo": [
                        "Resource::arn:aws:bedrock:*::foundation-model/*",
                        f"Resource::arn:aws:bedrock:{Stack.of(self).region}:{Stack.of(self).account}:inference-profile/*",
                        "Resource::<SearchPromptInsertFunction6CC4C639.Arn>:*",
                        "Resource::*",
                    ],
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "MRE internal lambda functions do not require the latest runtime version as their dependencies have been tested only on Python 3.11",
                },
            ],
        )
