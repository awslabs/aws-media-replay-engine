# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from aws_cdk import (
    aws_lambda as lambda_,
    aws_dynamodb as ddb,
    Fn,
    Stack,
    RemovalPolicy,
    Duration,
    CfnOutput,
    aws_events as events,
    aws_events_targets as events_targets,
    aws_s3 as s3,
    aws_iam as iam,
    aws_s3_deployment as s3_deployment,
)
from aws_cdk.aws_lambda_event_sources import SqsEventSource
from cdk_nag import NagSuppressions
from constructs import Construct
from medialive_construct import MediaLiveConstruct


class MreTestSuiteStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.event_bus = MreTestSuiteStack.get_event_bus(self)
        self.create_ddb_table()
        self.create_event_recorder_lambda()
        
        # MRE Access Log Bucket
        self.access_log_bucket = s3.Bucket(
            self,
            "AwsMreTestSuiteAccessLogsBucket",
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,  # Enable versioning
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(91),  # Delete current version after 91 days
                    noncurrent_version_expiration=Duration.days(91),  # Delete old versions after 91 days
                    enabled=True
                )
            ]
        )

        self.medialive_source_bucket = s3.Bucket(
            self,
            'AwsMreTestSuiteMediaLiveSourceBucket',
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=self.access_log_bucket,
            server_access_logs_prefix="mre-medialive-logs",
            versioned=True,  # Enable versioning
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(91),  # Delete current version after 91 days
                    noncurrent_version_expiration=Duration.days(91),  # Delete old versions after 91 days
                    enabled=True
                )
            ]
        )

        self.mre_byob_source_bucket1 = s3.Bucket(
            self,
            'AwsMreTestSuite-Byob-Bucket1',
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=self.access_log_bucket,
            server_access_logs_prefix="mre-byob1-logs",
            versioned=True,  # Enable versioning
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(91),  # Delete current version after 91 days
                    noncurrent_version_expiration=Duration.days(91),  # Delete old versions after 91 days
                    enabled=True
                )
            ]
        )
        self.mre_byob_source_bucket2 = s3.Bucket(
            self,
            'AwsMreTestSuite-Byob-Bucket2',
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=self.access_log_bucket,
            server_access_logs_prefix="mre-byob2-logs",
            versioned=True,  # Enable versioning
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(91),  # Delete current version after 91 days
                    noncurrent_version_expiration=Duration.days(91),  # Delete old versions after 91 days
                    enabled=True
                )
            ]
        )
        self.mre_byob_source_bucket3 = s3.Bucket(
            self,
            'AwsMreTestSuite-Byob-Bucket3',
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=self.access_log_bucket,
            server_access_logs_prefix="mre-byob3-logs",
            versioned=True,  # Enable versioning
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(91),  # Delete current version after 91 days
                    noncurrent_version_expiration=Duration.days(91),  # Delete old versions after 91 days
                    enabled=True
                )
            ]
        )
        self.mre_byob_source_bucket4 = s3.Bucket(
            self,
            'AwsMreTestSuite-Byob-Bucket4',
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=self.access_log_bucket,
            server_access_logs_prefix="mre-byob4-logs",
            versioned=True,  # Enable versioning
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(91),  # Delete current version after 91 days
                    noncurrent_version_expiration=Duration.days(91),  # Delete old versions after 91 days
                    enabled=True
                )
            ]
        )


        self.video_deploy = s3_deployment.BucketDeployment(self, "DeploySampleVideo",
            sources=[s3_deployment.Source.asset("./sample_video/")],
            destination_bucket=self.medialive_source_bucket,
            destination_key_prefix="mre/testsuite",
            memory_limit=512
        )

        self.create_medialive_role()


        self.channel1 = MediaLiveConstruct(self, "mre-medialive-channel-1",  
                                           channel_name="MRE_TESTSUITE_CHANNEL", 
                                           channel_index="1", 
                                           input_name="Mre_TestSuite_Input",
                                           #medialive_source_bucket=self.medialive_source_bucket,
                                           medialive_source_bucket=self.video_deploy.deployed_bucket,
                                           medialive_role=self.medialive_role)
        

        self.channel2 = MediaLiveConstruct(self, "mre-medialive-channel-2",  
                                           channel_name="MRE_TESTSUITE_CHANNEL", 
                                           channel_index="2", 
                                           input_name="Mre_TestSuite_Input",
                                           #medialive_source_bucket=self.medialive_source_bucket,
                                           medialive_source_bucket=self.video_deploy.deployed_bucket,
                                           medialive_role=self.medialive_role)
        
        self.channel3 = MediaLiveConstruct(self, "mre-medialive-channel-3",  
                                           channel_name="MRE_TESTSUITE_CHANNEL", 
                                           channel_index="3", 
                                           input_name="Mre_TestSuite_Input",
                                           #medialive_source_bucket=self.medialive_source_bucket,
                                           medialive_source_bucket=self.video_deploy.deployed_bucket,
                                           medialive_role=self.medialive_role)
        
        self.channel4 = MediaLiveConstruct(self, "mre-medialive-channel-4",  
                                           channel_name="MRE_TESTSUITE_CHANNEL", 
                                           channel_index="4", 
                                           input_name="Mre_TestSuite_Input",
                                           #medialive_source_bucket=self.medialive_source_bucket,
                                           medialive_source_bucket=self.video_deploy.deployed_bucket,
                                           medialive_role=self.medialive_role)
        
        ###### BYOB ########
        self.channel5 = MediaLiveConstruct(self, "mre-medialive-byob-channel-1",  
                                           channel_name="MRE_BYOB_TESTSUITE_CHANNEL", 
                                           channel_index="1", 
                                           input_name="Mre_TestSuite_Input",
                                           #medialive_source_bucket=self.medialive_source_bucket,
                                           medialive_source_bucket=self.video_deploy.deployed_bucket,
                                           byob_bucket_name=self.mre_byob_source_bucket1.bucket_name,
                                           medialive_role=self.medialive_role)

        self.channel6 = MediaLiveConstruct(self, "mre-medialive-byob-channel-2",  
                                           channel_name="MRE_BYOB_TESTSUITE_CHANNEL", 
                                           channel_index="2", 
                                           input_name="Mre_TestSuite_Input",
                                           #medialive_source_bucket=self.medialive_source_bucket,
                                           medialive_source_bucket=self.video_deploy.deployed_bucket,
                                           byob_bucket_name=self.mre_byob_source_bucket2.bucket_name,
                                           medialive_role=self.medialive_role)
        
        self.channel7 = MediaLiveConstruct(self, "mre-medialive-byob-channel-3",  
                                           channel_name="MRE_BYOB_TESTSUITE_CHANNEL", 
                                           channel_index="3", 
                                           input_name="Mre_TestSuite_Input",
                                           #medialive_source_bucket=self.medialive_source_bucket,
                                           medialive_source_bucket=self.video_deploy.deployed_bucket,
                                           byob_bucket_name=self.mre_byob_source_bucket3.bucket_name,
                                           medialive_role=self.medialive_role)
        
        self.channel8 = MediaLiveConstruct(self, "mre-medialive-byob-channel-4",  
                                           channel_name="MRE_BYOB_TESTSUITE_CHANNEL", 
                                           channel_index="4", 
                                           input_name="Mre_TestSuite_Input",
                                           #medialive_source_bucket=self.medialive_source_bucket,
                                           medialive_source_bucket=self.video_deploy.deployed_bucket,
                                           byob_bucket_name=self.mre_byob_source_bucket4.bucket_name,
                                           medialive_role=self.medialive_role)
        
        self.create_rule_for_segment_start()
        self.create_rule_for_segment_end()
        

        CfnOutput(self, "mreTestAutomationMediaLiveSourceBucket", value=self.medialive_source_bucket.bucket_name, description="Name of MRE TestSuite MediaLive Source Bucket", export_name="mreTestAutomationMediaLiveSourceBucket" )
        CfnOutput(self, "mreTestAutomationBYOB1", value=self.mre_byob_source_bucket1.bucket_name, description="Name of MRE TestSuite BYOB Bucket 1", export_name="mreTestAutomationBYOB1" )
        CfnOutput(self, "mreTestAutomationBYOB2", value=self.mre_byob_source_bucket2.bucket_name, description="Name of MRE TestSuite BYOB Bucket 2", export_name="mreTestAutomationBYOB2" )
        CfnOutput(self, "mreTestAutomationBYOB3", value=self.mre_byob_source_bucket3.bucket_name, description="Name of MRE TestSuite BYOB Bucket 3", export_name="mreTestAutomationBYOB3" )
        CfnOutput(self, "mreTestAutomationBYOB4", value=self.mre_byob_source_bucket4.bucket_name, description="Name of MRE TestSuite BYOB Bucket 4", export_name="mreTestAutomationBYOB4" )


        # cdk-nag suppressions
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-S1",
                    "reason": "Logging can be enabled if reqd in higher environments"
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "The non-container Lambda function does not require latest runtime"
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Chalice role policy requires wildcard permissions for CloudWatch logging, mediaconvert, eventbus, s3",
                    "appliesTo": [
                        "Action::s3:GetObject*",
                        "Action::s3:GetBucket*",
                        "Action::s3:Describe*",
                        "Action::s3:List*",
                        "Action::s3:DeleteObject*",
                        "Action::s3:Abort*",
                        "Action::s3:Put*",
                        "Action::s3:Get*",
                        "Resource::arn:aws:mediapackage:<AWS::Region>:<AWS::AccountId>:channels/*",
                        "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:*",
                        "Resource::arn:aws:s3:::aws-mre*/*",
                        "Resource::arn:aws:s3:::aws-mre*",
                        {
                            "regex": "/^Resource::arn:aws:s3:::<AwsMreTestSuiteMediaLiveSourceBucket*\/*/",
                        },
                        {
                            "regex": "/^Resource::<AwsMreTestSuiteMediaLiveSourceBucket*.+Arn>\/*/",
                        },
                        {
                            "regex": "/^Resource::arn:aws:s3:::<AwsMreTestSuiteByobBucket*\/*/",
                        },
                        {
                            "regex": "/^Resource::arn:<AWS::Partition>:s3:::cdk*\/*/",
                        }
                    ]
                },
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AWS managed policies allowed",
                    "appliesTo": [
                        "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                    ]
                }
            ]
        )

        NagSuppressions.add_resource_suppressions_by_path(
            self,
            "aws-mre-test-suite/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C512MiB/Resource",
            [
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Custom Resource lambda function does not require the latest runtime version"
                }
            ]
        )


    def create_medialive_role(self):

         # IAM Role for MediaLive
        self.medialive_role = iam.Role(
            self,
            "MediaLiveTestSuiteRole",
            assumed_by=iam.ServicePrincipal("medialive.amazonaws.com")
        )

        """  
        self.medialive_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ssm:Describe*",
                    "ssm:Get*",
                    "ssm:List*"
                ],
                effect=iam.Effect.ALLOW,
                resources=["*"]
            )
        ) 
        """

        self.medialive_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:PutObject",
                    "s3:GetObject",
                    "s3:DeleteObject"
                ],
                effect=iam.Effect.ALLOW,
                resources=[
                     f"arn:aws:s3:::{self.mre_byob_source_bucket1.bucket_name}/*",
                     f"arn:aws:s3:::{self.mre_byob_source_bucket2.bucket_name}/*",
                     f"arn:aws:s3:::{self.mre_byob_source_bucket3.bucket_name}/*",
                     f"arn:aws:s3:::{self.mre_byob_source_bucket4.bucket_name}/*",
                     f"arn:aws:s3:::{self.medialive_source_bucket.bucket_name}/*",
                     f"arn:aws:s3:::aws-mre*/*"
                ]
            )
        )

        self.medialive_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:ListBucket"
                ],
                effect=iam.Effect.ALLOW,
                resources=[
                     f"arn:aws:s3:::{self.mre_byob_source_bucket1.bucket_name}",
                     f"arn:aws:s3:::{self.mre_byob_source_bucket2.bucket_name}",
                     f"arn:aws:s3:::{self.mre_byob_source_bucket3.bucket_name}",
                     f"arn:aws:s3:::{self.mre_byob_source_bucket4.bucket_name}",
                     f"arn:aws:s3:::{self.medialive_source_bucket.bucket_name}",
                     f"arn:aws:s3:::aws-mre*"
                ]
            )
        )

        self.medialive_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogStreams",
                    "logs:DescribeLogGroups"
                ],
                effect=iam.Effect.ALLOW,
                resources=[f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:*"]
            )
        )

        self.medialive_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "mediapackage:DescribeChannel"
                ],
                effect=iam.Effect.ALLOW,
                resources=[f"arn:aws:mediapackage:{Stack.of(self).region}:{Stack.of(self).account}:channels/*"]
            )
        )

    def create_ddb_table(self) -> None:
        # Create DynamoDB table with partition key as imageKey
            self.table = ddb.Table(
                self,
                "mre-TestSuite-EventStateRecorder",
                partition_key=ddb.Attribute(name="EventName", type=ddb.AttributeType.STRING),
                sort_key=ddb.Attribute(
                    name="SegmentTypeStartTime",
                    type=ddb.AttributeType.STRING
                ),
                billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
                removal_policy=RemovalPolicy.DESTROY,
                encryption=ddb.TableEncryption.AWS_MANAGED,  # Enables server-side encryption with AWS managed key
                point_in_time_recovery=True  # Enables point-in-time recovery
            )
            
            CfnOutput(self, "mre-TestSuite-EventStateRecorder-Table-output", value=self.table.table_name,
                      description="Name of the DynamoDB Table to store the EB event Payload for Segment Start and Segment End Events", export_name="mre-TestSuite-EventStateRecorder-Table")
        
    def create_event_recorder_lambda(self) -> None:
        self.event_recorder_lambda = lambda_.Function(
            self,
            "mre-TestSuite-EventRecorderLambda",
            function_name="mre-TestSuite-EventRecorderLambda",
            runtime=lambda_.Runtime.PYTHON_3_11,
            code=lambda_.Code.from_asset("./lambdas"),
            handler="event_recorder.handler",
            environment={"EVENT_RECORDER_TABLE_NAME": self.table.table_name},
            timeout = Duration.seconds(120)
        )
        self.table.grant_read_write_data(self.event_recorder_lambda)
        

    @staticmethod
    def get_event_bus(self) -> events.IEventBus:
        # Get the IEventBus Object back from the Event Bus Arn
        return events.EventBus.from_event_bus_name(self, "ImportedEventBusName", "aws-mre-event-bus")
    

    def create_rule_for_segment_start(self):
        self.mre_segment_start_rule = events.Rule(
            self,
            "create_rule_for_segment_Start",
            description="Rule that captures SEGMENT_START and OPTIMIZED_SEGMENT_START = Used by MRE TestSuite ONLY",
            enabled=True,
            event_bus=self.event_bus,
            event_pattern=events.EventPattern(
                source=["awsmre"],
                detail={
                    "State":  ["OPTIMIZED_SEGMENT_START", "SEGMENT_START"]
                }
            ),
            targets=[
                events_targets.LambdaFunction(
                    handler=self.event_recorder_lambda
                )
            ]
        )


    def create_rule_for_segment_end(self):
        self.mre_segment_start_rule = events.Rule(
            self,
            "create_rule_for_segment_end",
            description="Rule that captures SEGMENT_END and OPTIMIZED_SEGMENT_END = Used by MRE TestSuite ONLY",
            enabled=True,
            event_bus=self.event_bus,
            event_pattern=events.EventPattern(
                source=["awsmre"],
                detail={
                    "State":  ["OPTIMIZED_SEGMENT_END", "SEGMENT_END"]
                }
            ),
            targets=[
                events_targets.LambdaFunction(
                    handler=self.event_recorder_lambda
                )
            ]
        )

