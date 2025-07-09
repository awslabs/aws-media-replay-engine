# Detect Speech #

**MRE Plugin Class**

- Featurer

**Description**:

When optimizing in/out placement for segments/clips it's sometimes desirable to avoid interruption of the announcer. This plugin processes audio tracks to detect pauses in speech that may offer better location of in/out placement. It can be used with the general purposes MRE optimization plugin.

**Applies to Media Type**:

- Video
- Audio (In Development)

**Use Cases**:

- Can be used to generate data that gets used by an optimizer plugin to adjust the in/out times of a segment to avoid interrupting an announcer
- Could be enhanced/modified to detect specific words or phrases that could be leveraged in replay highlight priorities (weightings).
- Can be used to optionally identify the name of the speaker from their voice and include it as a label when storing the plugin results.

**Dependencies**:

- MRE Helper libraries
- ffmpeg >> we suggest using a custom ffmpeg Lambda Layer

**ML Model dependencies**:

- SpeakerIdentificationModel (optional)

**Other plugin dependencies**:

- none

**Parameter inputs**:

- TrackNumber >> Audio track from video that is being used for calculations.
- silence_duration_sec >> Pauses in speech longer than this value will be separated into separate detections.
- input_bucket_name >> just the bucket name itself: my-bucket. This is an intermediate storage location for the extracted audio file.
- output_bucket_name >> this is needed to have the Transcribe service write results out to.
- training_bucket_name >> name of the S3 bucket to store clip samples for training the speaker identification ML model.
- training_upload_enabled >> flag to enable/disable upload of the clip samples to S3 for training the speaker identification ML model.
- speaker_inference_enabled >> flag to enable/disable speaker identification logic using ML model within the plugin.
- show_speaker_labels >> flag to enable/disable speaker partitioning (diarization) in the transcription output.
- max_speaker_labels >> specifies the maximum number of speakers to be partitioned in the audio.
- transcribe_lang_code >> language code to use for generating transcription (<https://docs.aws.amazon.com/transcribe/latest/dg/supported-languages.html>).
- transcribe_identify_lang >> flag to enable/disable automatic language identification in the transcription job.

**Output attributes**:

- Label >> the value 'speech present' will appear when detected by the presence of a 'pronunciation' type result in the transcription
- Transcription >> raw Transcribe results
- Speaker >> name of the speaker (from speaker identification ML model if enabled)

**IAM permissions (least privilege)**:

- transcribe:StartTranscriptionJob *
- transcribe:GetTranscriptionJob *
- s3:GetObject *
- s3:PutObject *
- s3:ListBucket *
- sagemaker:InvokeEndpoint *

**Before you run**:

- Make sure you have S3 Buckets provisioned for storing the Amazon Transcribe output, the intermediary audio location and optionally, the clip samples for training the speaker identification model (all these can be the same bucket).
- Review the parameter input values and set accordingly (S3 bucket and region) as the default is not valid.
- Update the IAM Policy to reflect the S3 bucket permissions needed.
- Adjust the lambda function timeout setting to accommodate the size (length) of the chunk. Larger chunks have more audio to transcribe which takes longer to process.
