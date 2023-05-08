# LabelTennisScore #

**MRE Plugin Class**
- Labeler 

**Description**:

This plugin extract score from the scorebox detection output.

**Applies to Media Type**:
- Video

**Use Cases**:
- Game point/Set point/Match point detection

**Dependencies**:
- MRE Helper libraries

**ML Model dependencies**:
- None

**Other plugin dependencies**:
- DetectTennisScoreBoxData

**Parameter inputs**:
- dependent_plugin_name >> Name if the plugin that this plugin is getting its score data from.

**Output attributes**:
- Label >> Name of the feature to be detected in this plugin.
- Score >> Score detected by plugin.
- BreakPoint >>  Boolean value for breakpoint.
- GamePoint >>  Boolean value for gamepoint.
- SetPoint >>  Boolean value for setpoint.
- MatchPoint >> Boolean value for matchpoint.

**IAM permissions (least privilege)**:
- None
