# DetectShotsByRekognitionVideo #

**MRE Plugin Class**
- Featurer

**Description**:

This plugin uses Amazon Rekognition Video API for shot detection. You can check out more details at [this link](https://docs.aws.amazon.com/rekognition/latest/dg/segments.html)

**Applies to Media Type**:
- Video

**Use Cases**:
- Any contents where shot detection is needed. Commerical detection is an example.

**Dependencies**:
- MRE Helper libraries
- ffmpeg convert video chunk from ts format to mp4

**ML Model dependencies**:
- None 

**Other plugin dependencies**:
- None

**Parameter inputs**:
- None
 
**Output attributes**:
- Label >> the scene classification tag

**IAM permissions (least privilege)**:
- s3:PutObject *
- s3:GetObject *
- rekognition:StartSegmentDetection
- rekognition:GetSegmentDetection
- sqs:RecieveMessage (Optional)
- sqs:DeleteMessage (Optional)
- sqs:CreateQueue (Optional)
- sqs:GetQueueAttributes (Optional)
- sqs:SetQueueAttributes (Optional)


**Before you run**:
- Adjust the lambda function timeout setting to accommodate the size (length) of the chunk. Larger chunks have more video to analyze which takes longer to process.
