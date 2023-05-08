# SegmentByCommercials #

**MRE Plugin Class**
- Segmenter

**Description**:

This plugin segments the video by commercial breaks. It uses the results from shot detection and applies an average filter on shot length. Based on the threshold value set by the user, the plugin will filter out segments with shorter shot length, which are commercials.

**Applies to Media Type**:
- Video

**Use Cases**:
- Interviews, keynotes, or sports that has commercials in it.

**Dependencies**:
- MRE Helper libraries

**ML Model dependencies**:
- None

**Other plugin dependencies**:
- A shot detection plugin (featurer class) for your content, for example, DetectShotsByRekognitionVideo.

**Parameter inputs**:
- MIN_DURATION: Minimun length of a shot.
- WINDOW_SIZE: The window size used to run average filter.
- THRESHOLD_VAL: The threshold value to detect commercials.
- THRESHOLD_LEN: The threshold length to identify commercials.

**Output attributes**:
- None

**IAM permissions (least privilege)**:
- None
