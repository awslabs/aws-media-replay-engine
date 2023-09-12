# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from aws_cdk import (
    Fn,
    Stack,
    Duration,
    CfnOutput,
    aws_medialive as medialive,
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment,
)
from constructs import Construct


class MediaLiveConstruct(Construct):

    def __init__(self, scope: Construct, 
                 construct_id: str,
                 channel_name: str, 
                 input_name: str, 
                 channel_index: str, 
                 medialive_source_bucket: s3.Bucket, 
                 medialive_role: iam.Role, 
                 byob_bucket_name: str="",
                 **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        self.channel_name = channel_name
        self.input_name = input_name
        self.channel_index = channel_index
        self.medialive_source_bucket = medialive_source_bucket
        self.medialive_role = medialive_role
        self.byob_bucket_name = byob_bucket_name
        

        # This forces the video files to be uploaded to the bucket before setting the bucket name
        self.medialive_source_bucket_name = self.medialive_source_bucket.bucket_name
        

        

        # MediaLive Input
        self.medialive_input = medialive.CfnInput(
            self,
            "S3Input",
            type="MP4_FILE",
            name=f"{self.input_name}_{self.channel_index}",
            sources=[
                medialive.CfnInput.InputSourceRequestProperty(
                    url=f"s3ssl://{self.medialive_source_bucket_name}/mre/testsuite/MRE-Sample.mp4"
                )
            ]
        )



        # MediaLive Channel
        self.medialive_channel = medialive.CfnChannel(
            self,
            "S3Channel",
            channel_class="SINGLE_PIPELINE",


            # Although we use the SourceBucket as the DestinationBucket, in reality when MRE executes,
            # it will dynamically change the output path to point it to the S3 Location 
            # corresponding to the Bucket that MRE creates.
            destinations=[
                medialive.CfnChannel.OutputDestinationProperty(
                    id="awsmre",
                    settings=[
                        medialive.CfnChannel.OutputDestinationSettingsProperty(
                            url=f"s3ssl://{self.medialive_source_bucket_name}/{self.channel_name}_{self.channel_index}/output" if not byob_bucket_name else f"s3ssl://{self.byob_bucket_name}/output"
                        )
                    ]
                )
            ],
            encoder_settings=medialive.CfnChannel.EncoderSettingsProperty(
                audio_descriptions=[
                    medialive.CfnChannel.AudioDescriptionProperty(
                        audio_selector_name="qis",
                        audio_type_control="FOLLOW_INPUT",
                        language_code_control="FOLLOW_INPUT",
                        name="audio_fi4cn"
                    )
                ],
                output_groups=[
                    medialive.CfnChannel.OutputGroupProperty(
                        output_group_settings=medialive.CfnChannel.OutputGroupSettingsProperty(
                            hls_group_settings=medialive.CfnChannel.HlsGroupSettingsProperty(
                                caption_language_setting="OMIT",
                                client_cache="ENABLED",
                                codec_specification="RFC_4281",
                                destination=medialive.CfnChannel.OutputLocationRefProperty(
                                    destination_ref_id="awsmre"
                                ),
                                directory_structure="SINGLE_DIRECTORY",
                                discontinuity_tags="INSERT",
                                hls_id3_segment_tagging="DISABLED",
                                i_frame_only_playlists="DISABLED",
                                incomplete_segment_behavior="AUTO",
                                index_n_segments=10,
                                input_loss_action="PAUSE_OUTPUT",
                                iv_in_manifest="INCLUDE",
                                iv_source="FOLLOWS_SEGMENT_NUMBER",
                                keep_segments=21,
                                manifest_compression="NONE",
                                manifest_duration_format="FLOATING_POINT",
                                mode="VOD",
                                output_selection="VARIANT_MANIFESTS_AND_SEGMENTS",
                                program_date_time="INCLUDE",
                                program_date_time_period=30,
                                redundant_manifest="DISABLED",
                                segment_length=10,
                                segmentation_mode="USE_SEGMENT_DURATION",
                                segments_per_subdirectory=10000,
                                stream_inf_resolution="INCLUDE",
                                timed_metadata_id3_frame="PRIV",
                                timed_metadata_id3_period=10,
                                ts_file_mode="SEGMENTED_FILES"
                            )
                        ),
                        outputs=[
                            medialive.CfnChannel.OutputProperty(
                                audio_description_names=["audio_fi4cn"],
                                output_name="awsmre",
                                output_settings=medialive.CfnChannel.OutputSettingsProperty(
                                    hls_output_settings=medialive.CfnChannel.HlsOutputSettingsProperty(
                                        h265_packaging_type="HVC1",
                                        hls_settings=medialive.CfnChannel.HlsSettingsProperty(
                                            standard_hls_settings=medialive.CfnChannel.StandardHlsSettingsProperty(
                                                audio_rendition_sets="program_audio",
                                                m3_u8_settings=medialive.CfnChannel.M3u8SettingsProperty(
                                                    audio_frames_per_pes=4,
                                                    audio_pids="492-498",
                                                    nielsen_id3_behavior="NO_PASSTHROUGH",
                                                    pcr_control="PCR_EVERY_PES_PACKET",
                                                    pmt_pid="480",
                                                    program_num=1,
                                                    scte35_behavior="NO_PASSTHROUGH",
                                                    scte35_pid="500",
                                                    timed_metadata_behavior="NO_PASSTHROUGH",
                                                    timed_metadata_pid="502",
                                                    video_pid="481"
                                                )
                                            )
                                        ),
                                        name_modifier="_1"
                                    )
                                ),
                                video_description_name="video_awsmre"
                            )
                        ]
                    )
                ],
                timecode_config=medialive.CfnChannel.TimecodeConfigProperty(
                    source="ZEROBASED"
                ),
                video_descriptions=[
                    medialive.CfnChannel.VideoDescriptionProperty(
                        codec_settings=medialive.CfnChannel.VideoCodecSettingsProperty(
                            h264_settings=medialive.CfnChannel.H264SettingsProperty(
                                adaptive_quantization="AUTO",
                                afd_signaling="NONE",
                                bitrate=5000000,
                                buf_size=5000000,
                                color_metadata="INSERT",
                                entropy_encoding="CABAC",
                                flicker_aq="ENABLED",
                                force_field_pictures="DISABLED",
                                framerate_control="INITIALIZE_FROM_SOURCE",
                                gop_b_reference="DISABLED",
                                gop_closed_cadence=1,
                                gop_num_b_frames=2,
                                gop_size=1,
                                gop_size_units="SECONDS",
                                level="H264_LEVEL_AUTO",
                                look_ahead_rate_control="MEDIUM",
                                max_bitrate=5000000,
                                num_ref_frames=1,
                                par_control="INITIALIZE_FROM_SOURCE",
                                profile="HIGH",
                                qvbr_quality_level=8,
                                rate_control_mode="QVBR",
                                scan_type="PROGRESSIVE",
                                scene_change_detect="DISABLED",
                                spatial_aq="ENABLED",
                                subgop_length="FIXED",
                                syntax="DEFAULT",
                                temporal_aq="ENABLED",
                                timecode_insertion="DISABLED"
                            )
                        ),
                        name="video_awsmre",
                        respond_to_afd="NONE",
                        scaling_behavior="DEFAULT",
                        sharpness=50
                    )
                ]
            ),
            input_attachments=[
                medialive.CfnChannel.InputAttachmentProperty(
                    input_attachment_name=self.medialive_input.name,
                    input_id=Fn.select(6, Fn.split(delimiter=":", source=self.medialive_input.attr_arn)),
                    input_settings=medialive.CfnChannel.InputSettingsProperty(
                        audio_selectors=[
                            medialive.CfnChannel.AudioSelectorProperty(
                                name="qis",
                                selector_settings=medialive.CfnChannel.AudioSelectorSettingsProperty(
                                    audio_track_selection=medialive.CfnChannel.AudioTrackSelectionProperty(
                                        tracks=[
                                            medialive.CfnChannel.AudioTrackProperty(
                                                track=1
                                            )
                                        ]
                                    )
                                )
                            )
                        ],
                        deblock_filter="DISABLED",
                        denoise_filter="DISABLED",
                        filter_strength=1,
                        input_filter="AUTO",
                        smpte2038_data_preference="IGNORE",
                        source_end_behavior="CONTINUE"
                    )
                )
            ],
            input_specification=medialive.CfnChannel.InputSpecificationProperty(
                codec="AVC",
                maximum_bitrate="MAX_20_MBPS",
                resolution="HD"
            ),
            log_level="DISABLED",
            name=f"{self.channel_name}_{self.channel_index}",
            role_arn=self.medialive_role.role_arn
        )

        self.medialive_channel.node.add_dependency(self.medialive_input, self.medialive_role)
