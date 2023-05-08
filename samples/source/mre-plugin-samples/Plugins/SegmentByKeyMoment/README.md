# LabelTennisScore #

**MRE Plugin Class**
- Segmenter

**Description**:

"This plugin attempts to segment footage by key moments by using data taken from the detector and adding a buffer to detected moments"

**Applies to Media Type**:
- Video

**Use Cases**:
- Goal Scored/Game point/Set point/Match point detection

**Dependencies**:
- Dependencies are required for this plugin due to the nature of the framework. Whichever detector you want to segment by, use that as the dependency

**ML Model dependencies**:
- None 

**Other plugin dependencies**:
- A detection plugin (featurer class) for your content, for example, DetectSceneChange.

**Parameter inputs**:
- chunk_to_segment_ratio >> Used to calculate how much footage is added before and after the key moment as a buffer for the viewer.

**Output attributes**:
- Label >> Name of the feature to be detected in this plugin.

**IAM permissions (least privilege)**:
- None
