# DetectViaPrompt #

**MRE Plugin Class**
- Featurer

**Description**:

This plugin uses Amazon Bedrock to ddescribe the scene. The bedrock is given an even distribution of frames as prelude information for the prompt (maximum of 20 frames):

**Applies to Media Type**:
- Video

**Use Cases**:
- Video content that could be described using its visuals.

**Dependencies**:
- MRE Helper libraries
- OpenCV

**ML Model dependencies**:
- None
**Other plugin dependencies**:
- None

**Parameter inputs**:
- None

**Output attributes**:
- Label >> The description of the scene provided as a response by Amazon Bedrock.
- frameId >> Frame within the video chunk processed. This is for debugging.

**IAM permissions (least privilege)**:
- bedrock:invokeModel *
- bedrock:GetInferenceProfile *
