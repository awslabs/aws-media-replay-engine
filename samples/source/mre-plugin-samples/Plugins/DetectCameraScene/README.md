# DetectCameraScene #

**MRE Plugin Class**
- Featurer

**Description**:

This plugin uses a model (of your chosing) to determine what the camera scene is. Models that have been tested with it used labels such as the following for a tennis context:
- near >> camera is close up on a single player
- far >> camera angle is from afar - wide view
- topview >> camera angle is from above
- replay >> event logo present indicating an instant replay is present

**Applies to Media Type**:
- Video

**Use Cases**:
- Tennis specific content where the camera angle / scene is needed. Scene classification for segmentation is an example.

**Dependencies**:
- MRE Helper libraries
- OpenCV >> provide as a Lambda Layer

**ML Model dependencies**:
- Requires a ML Model that performs scene classification using Amazon Rekognition Custom Labels.

**Other plugin dependencies**:
- None

**Parameter inputs**:
- minimum_confidence >> threshold for confidence in the ML result. 0 would include anything.

**Output attributes**:
- Label >> The scene classification tag.
- Confidence >> The inference confidence from the ML endpoint.
- frameId >> Frame within the video chunk processed. This is for debugging.

**IAM permissions (least privilege)**:
- rekognition:DetectCustomLabels *
