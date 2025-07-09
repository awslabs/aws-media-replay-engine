# DetectSceneLabels #

**MRE Plugin Class**

- Featurer

**Description**:

A plugin to detect scene labels using GenAI.

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

- bedrock_model_id >> model id in Bedrock to invoke (for example, anthropic.claude-3-haiku-20240307-v1:0)
- prompt_template_name >> name of the prompt template stored in the MRE PromptCatalog table (for example, scene-labels) to use during Bedrock model invoke
- sampling_seconds >> pick a frame every X second (for example, 2) for processing

**Output attributes**:

- Label >> List of labels found

**IAM permissions (least privilege)**:

- Bedrock
