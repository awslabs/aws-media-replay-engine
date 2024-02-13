import os
from aws_cdk import (
    Fn,
    Aws,
    custom_resources as cr,
    aws_events as events,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_lambda as _lambda,
    aws_s3 as s3,
    aws_sqs as sqs
)
from aws_cdk.aws_lambda import ILayerVersion


RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')


MRE_EVENT_BUS = "aws-mre-event-bus"

class MreCdkCommon():
    
    @staticmethod
    def get_media_convert_endpoint(this):
        # Get MediaConvert Regional Endpoint via an AWS SDK call
        mediaconvert_endpoints = cr.AwsCustomResource(
            this,
            "MediaConvertCustomResource",
            policy=cr.AwsCustomResourcePolicy.from_statements(
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=["mediaconvert:DescribeEndpoints"],
                        resources=["arn:aws:mediaconvert:*:*:*"]
                    )
                ]
            ),
            on_create=cr.AwsSdkCall(
                action="describeEndpoints",
                service="MediaConvert",
                physical_resource_id=cr.PhysicalResourceId.of(id="MediaConvertCustomResourceAwsSdkCall")
            ),
            on_update=cr.AwsSdkCall(
                action="describeEndpoints",
                service="MediaConvert",
                physical_resource_id=cr.PhysicalResourceId.of(id="MediaConvertCustomResourceAwsSdkCall")
            )
        )
        return mediaconvert_endpoints.get_response_field(data_path="Endpoints.0.Url")

        # # Store the MediaConvert Regional endpoint in SSM Parameter Store
        # ssm.StringParameter(
        #     this,
        #     "MediaConvertRegionalEndpoint",
        #     string_value=mediaconvert_endpoints.get_response_field(data_path="Endpoints.0.Url"),
        #     parameter_name="/MRE/ClipGen/MediaConvertEndpoint",
        #     tier=ssm.ParameterTier.INTELLIGENT_TIERING,
        #     description="[DO NOT DELETE] Contains Media Convert Endpoint required for MRE Clip Generation"
        # )


    @staticmethod
    def get_event_bus(this) -> events.IEventBus:
        # Get the IEventBus Object back from the Event Bus Arn
        return events.EventBus.from_event_bus_arn(this, "ImportedEventBus", Fn.import_value("mre-event-bus-arn"))

    @staticmethod
    def get_eb_schedule_role_arn(this):
        return Fn.import_value("mre-eb-schedule-role-arn")

    @staticmethod
    def get_media_convert_output_bucket_name(this):
        return Fn.import_value("mre-media-output-bucket-name")
    
    @staticmethod
    def get_transitions_clips_bucket(this):
        return s3.Bucket.from_bucket_name(this, "MreTransitionsClipsBucketName",Fn.import_value("mre-transition-clips-bucket-name"))

    @staticmethod
    def get_media_convert_output_bucket(this):
        return s3.Bucket.from_bucket_name(this, "MreMediaOutputBucketName",Fn.import_value("mre-media-output-bucket-name"))

    @staticmethod
    def get_media_source_bucket(this):
        return s3.Bucket.from_bucket_name(this, "MreMediaSourceBucketName",Fn.import_value("mre-media-source-bucket-name"))

    @staticmethod
    def get_segment_cache_bucket_name(this):
        return Fn.import_value("mre-segment-cache-bucket-name")

    @staticmethod
    def get_segment_cache_bucket(this):
        return s3.Bucket.from_bucket_name(this, "MreSegmentCacheBucketName",Fn.import_value("mre-segment-cache-bucket-name"))

    @staticmethod
    def get_data_export_bucket_name():
        return Fn.import_value("mre-data-export-bucket-name")


    @staticmethod    
    def get_powertools_layer_from_arn(this) -> ILayerVersion:
        return _lambda.LayerVersion.from_layer_version_arn(this, "PowerToolsLayerFromArn", f"arn:aws:lambda:{Aws.REGION}:017000801446:layer:AWSLambdaPowertoolsPythonV2:58")

    @staticmethod    
    def get_timecode_layer_from_arn(this) -> ILayerVersion:
        timecode_layer_arn = ssm.StringParameter.value_for_string_parameter(
            this,
            parameter_name="/MRE/TimecodeLambdaLayerArn"
        )
        return _lambda.LayerVersion.from_layer_version_arn(this, "TimeCodeLayerFromArn", timecode_layer_arn)

    @staticmethod
    def get_ffmpeg_layer_from_arn(this) -> ILayerVersion:
        ffmpeg_layer_arn = ssm.StringParameter.value_for_string_parameter(
            this,
            parameter_name="/MRE/FfmpegLambdaLayerArn"
        )
        return _lambda.LayerVersion.from_layer_version_arn(this, "ffmpegLayerFromArn", ffmpeg_layer_arn)

    @staticmethod
    def get_ffprobe_layer_from_arn(this) -> ILayerVersion:
        ffprobe_layer_arn = ssm.StringParameter.value_for_string_parameter(
            this,
            parameter_name="/MRE/FfprobeLambdaLayerArn"
        )
        return _lambda.LayerVersion.from_layer_version_arn(this, "ffprobeLayerFromArn", ffprobe_layer_arn)

    @staticmethod
    def get_mre_workflow_helper_layer_from_arn(this) -> ILayerVersion:
        mre_workflow_helper_layer_arn = ssm.StringParameter.value_for_string_parameter(
            this,
            parameter_name="/MRE/WorkflowHelperLambdaLayerArn"
        )
        return _lambda.LayerVersion.from_layer_version_arn(this, "workflowHelperLayerFromArn", mre_workflow_helper_layer_arn)

    @staticmethod
    def get_mre_plugin_helper_layer_from_arn(this) -> ILayerVersion:
        mre_plugin_helper_layer_arn = ssm.StringParameter.value_for_string_parameter(
            this,
            parameter_name="/MRE/PluginHelperLambdaLayerArn"
        )
        return _lambda.LayerVersion.from_layer_version_arn(this, "pluginHelperLayerFromArn", mre_plugin_helper_layer_arn)

    @staticmethod
    def get_media_convert_role_arn():
        return Fn.import_value("mre-event-media-convert-role-arn")
    
    @staticmethod
    def get_mre_harvest_queue(this) -> sqs.IQueue:
        return sqs.Queue.from_queue_arn(this, "harvestQueueFromArn", Fn.import_value("mre-harvest-queue-arn"))