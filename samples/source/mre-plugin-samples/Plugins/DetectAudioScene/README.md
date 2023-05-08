# DetectAudioScene #

**MRE Plugin Class**
- Featurer

**Description**:

This plugin detects different audio scenes in tennis match.

**Applies to Media Type**:
- Video
- Audio (In Development)

**Use Cases**:
- Detect crowd noise/commentator talk/ball hitting/quite scence in tennis match.
- Detect any audio distinguishable scenarios in the video.

**Dependencies**:
- MRE Helper libraries  
- ffmpeg
- numpy
- audio2numpy

**ML Model dependencies**:
- AudioSpetrumClassificationModel

**Other plugin dependencies**:
- None

**Parameter inputs**:
- TrackNumber >> Audio track from video that is being used for calculations.
- minimum_confidence >> Minimum confidence for classification.
- TimeWindowLength >> Length of time window.
- filter_lowcut >>  Low critical frequency for Butterworth digital and analog filter.
- filter_highcut >> High critical frequency for Butterworth digital and analog filter.

**Output attributes**:
- Label >> Name of the feature to be detected in this plugin.
- AudioScene >> Name of the audio scene.

**IAM permissions (least privilege)**:
- sagemaker:InvokeEndpoint *
