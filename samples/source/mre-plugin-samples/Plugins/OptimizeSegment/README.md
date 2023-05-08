# OptimizeSegment #

**MRE Plugin Class**
- Optimizer

**Description**:

This plugin is useful to perform general purpose segmentation where scene pattern changes can reliably indicate the start and end of a segment/clip. For example, a near camera shot followed by a far camera shot can reliably mark the start of a segment in tennis tournament video.

**Applies to Media Type**:
- Video

**Use Cases**:
- Any segment that can benefit from refinement of the in/out placement.

**Dependencies**:
- MRE Helper libraries

**ML Model dependencies**:
- none

**Other plugin dependencies**:
- One or many featurer detector plugins that detect the presence of something in the audio or video that should either be in a 'safe range' or 'unsafe range'

The dependent plugins you choose need to implement an output attribute called **bias** and indicate one of two values:
'safe range' or 'unsafe range'. This is used by this plugin to know if the detector data is describing a location in the segment that should be avoided or is a good/safe place for a in/out.

**Parameter inputs**:
- optimization_search_window_sec >> number of seconds to work within when attempting to adjust the in/out placement. Should be > 0 seconds.

**Output attributes**:
- None

**IAM permissions (least privilege)**:
- None
