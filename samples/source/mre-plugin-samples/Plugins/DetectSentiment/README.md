# Detect Sentiment #

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

**Dependencies**:
- MRE Helper libraries

**ML Model dependencies**:
- none

**Other plugin dependencies**:
- DetectSpeech

**Parameter inputs**:
- TrackNumber >> Audio track from video that is being used for calculations.
- text_attribute >> The attribute containing the text to analyze. Note this usually comes from the output attribute of the dependent plugin. the default is set to "Transcription" because that is a key in the output of DetectSpeech, the default dependency for this plugin.
- text_language_code >> This is the language code for the comprehend API.

**Output attributes**:
- Label >> the primary sentiment
- Primary_Sentiment >> the primary sentiment
- positive_score >> The level of confidence that Amazon Comprehend has in the accuracy of its detection of the POSITIVE sentiment.
- neutral_score >> The level of confidence that Amazon Comprehend has in the accuracy of its detection of the NEUTRAL sentiment.
- negative_score >> The level of confidence that Amazon Comprehend has in the accuracy of its detection of the NEGATIVE sentiment.
- mixed_score >> The level of confidence that Amazon Comprehend has in the accuracy of its detection of the MIXED sentiment.
- positive_flag >> Flag indicating whether the sentiment was > 0.75 confidence.
- neutral_flag >> Flag indicating whether the sentiment was > 0.75 confidence.
- negative_flag >> Flag indicating whether the sentiment was > 0.75 confidence.
- mixed_flag >> Flag indicating whether the sentiment was > 0.75 confidence.

**IAM permissions (least privilege)**:
- transcribe:StartTranscriptionJob *
- transcribe:GetTranscriptionJob *
- comprehend:DetectSentiment *

**Before you run**:
- Adjust the lambda function timeout setting to accommodate the size (length) of the chunk. Larger chunks have more audio to transcribe which takes longer to process.
