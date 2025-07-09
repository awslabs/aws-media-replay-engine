# SegmentNews #

**MRE Plugin Class**

- Segmenter

**Description**:

This plugin is used to clip news topics from summarized transcriptions using an LLM.

**Applies to Media Type**:

- Video

**Use Cases**:

- Clip live or VOD news content using generative AI

**Dependencies**:

- MRE PluginResult table

**ML Model dependencies**:

- None

**Other plugin dependencies**:

- DetectSentiment
- DetectCelebrities
- DetectSceneLabels

**Parameter inputs**:

- min_segment_length >> minimum duration of the segment to create (30 seconds for example)
- search_window_seconds >> search window to look back for getting the transcription history (300 for example)
- bedrock_model_id >> model id in Bedrock to invoke (for example, anthropic.claude-3-haiku-20240307-v1:0)
- prompt_template_name >> name of the prompt template stored in the MRE PromptCatalog table (for example, news) to use during Bedrock model invoke

**Output attributes**:

- Label
- Desc >> used for the labeler plugin
- Summary
- Transcript
- Celebrities
- Sentiment
- Image_Summary

**IAM permissions (least privilege)**:

- Bedrock
- DynamoDB
