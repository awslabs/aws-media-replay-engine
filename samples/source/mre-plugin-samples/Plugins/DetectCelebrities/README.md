# DetectCelebrities #

**MRE Plugin Class**

- Featurer

**Description**:

A plugin to detect celebrities using either Amazon Rekognition or Amazon Bedrock.

**Applies to Media Type**:

- Video

**Use Cases**:

- News, Sports or other presenter detection.

**Dependencies**:

- MRE Helper libraries
- av
- pillow

**ML Model dependencies**:

- None

**Other plugin dependencies**:

- None

**Parameter inputs**:

- minimum_confidence >> 60 for example
- celebrity_list >> an ordered string list that matches the output attribute mapping you want. 5 in the default example ["Joe Biden","Donald Trump","Tom Cruise","Kamala Harris","Kevin McCarthy"]
- mode >> whether to use Amazon Rekognition or Amazon Bedrock for detecting celebrities
- bedrock_model_id >> model id in Bedrock to invoke (for example, anthropic.claude-3-haiku-20240307-v1:0)
- prompt_template_name >> name of the prompt template stored in the MRE PromptCatalog table (for example, celebs) to use during Bedrock model invoke

**Output attributes**:

- Label >> List of any celebs found
- flag_celebrity1 >> boolean indicating whether celebrity1 was found
- flag_celebrity2 >> boolean indicating whether celebrity2 was found
- flag_celebrity3 >> boolean indicating whether celebrity3 was found
- flag_celebrity4 >> boolean indicating whether celebrity4 was found
- flag_celebrity5 >> boolean indicating whether celebrity5 was found

**IAM permissions (least privilege)**:

- Rekognition
- Bedrock
