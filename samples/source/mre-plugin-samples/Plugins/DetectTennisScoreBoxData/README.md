# DetectTennisScoreBoxData #

**MRE Plugin Class**
- Featurer

**Description**:

This plugin detects scorebox from the frame images.

**Applies to Media Type**:
- Video

**Use Cases**:
- Score detection
- Game point/Set point/Match point detection
- Serving player detection

**Dependencies**:
- MRE Helper libraries
- Numpy
- OpenCV

**ML Model dependencies**:
- ScoreBoxDectionModel

**Other plugin dependencies**:
- None

**Parameter inputs**:
- minimum_monfidence >> Minimum Confidence for keypoints extraction.


**Output attributes**:
- Label >> Name of the plugin.
- Server >> The server player's name in tennis demo.
- Score >> The raw score read from the score box.

**IAM permissions (least privilege)**:
- rekognition:DetectCustomLabels *
- rekognition:DetectText *
