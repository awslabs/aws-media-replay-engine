# DetectTennisVolley #

**MRE Plugin Class**
- Featurer

**Description**:

This plugin detects a player is doing volley shots in the tennis match.

**Applies to Media Type**:
- Video

**Use Cases**:
- Volley shots detection
- Human enter/exit a bounded area detection

**Dependencies**:
- MRE Helper libraries
- Scipy
- OpenCV

**ML Model dependencies**:
- SceneClassificationModel

**Other plugin dependencies**:

**Parameter inputs**:
- minimum_confidence >> minimum confidence for classification
- vl  >> Left boundary of the volley zone
- vr  >> Right boundary of the volley zone
- vt  >> Top boundary of the volley zone
- vb  >> Bottom boundary of the volley zone

**Output attributes**:
- Label >> Name of the feature be detected in this plugin  
- Volley >> 1 if volley has been detected, 0 otherwise.  

**IAM permissions (least privilege)**:
- rekognition:DetectCustomLabels *
- rekognition:DetectLabels *
