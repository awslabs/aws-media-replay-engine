# DetectPose #

**MRE Plugin Class**
- Featurer

**Description**:

This plugin classifier pose keypoints into predefined classes.

**Applies to Media Type**:
- Video

**Use Cases**:
- Trick shot detection (behind the back tennis shot).
- Player excitement (hands up in the air).
- Thrilling action of a soccer goalie blocking a shot flying in the air.
- Tennis player serving pose.

**Dependencies**:
- MRE Helper libraries
- Scipy
- OpenCV

**ML Model dependencies**:
- PoseClassificationModel

**Other plugin dependencies**:
- DetectPoseKeypoints

**Parameter inputs**:
- minimum_confidence >> minimum confidence for classification.
- KeypointList >> list of keypoints will be used for the classification.

**Output attributes**:
- Label >> Name of the feature be detected in this plugin.
- PoseDetection >> Detected pose class.

**IAM permissions (least privilege)**:
- sagemaker:InvokeEndpoint *
