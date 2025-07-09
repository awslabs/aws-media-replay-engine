# Detect Sentiment #

**MRE Plugin Class**

- Featurer

**Description**:

This plugin uses Amazon Comprehend to perform sentiment analysis on the audio transcription outputted by a dependent plugin (i.e., DetectSpeech).

**Applies to Media Type**:

- Video
- Audio (In Development)

**Use Cases**:

- Can be used to identify the sentiment of different parts of the transcription such as positive, negative, mixed and neutral.
- These sentiment can then be used to determine what a particular entity (such as a person) feels about a particular topic.

**Dependencies**:

- MRE Helper libraries

**ML Model dependencies**:

- none

**Other plugin dependencies**:

- DetectSpeech

**Parameter inputs**:

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

- comprehend:DetectSentiment *

**Before you run**:

- Adjust the lambda function timeout setting to accommodate the size (length) of the chunk. Larger chunks have more audio to transcribe which takes longer to process.
