# SegmentPassThrough100 #

**MRE Plugin Class**
- Segmenter

**Description**:

This plugin is used to test MRE in a simple way by creating segments for each chunk based on time. It creates one segment for each chunk based on the ratio parameter value provided in the configuration. It has a different dependency than the original sample.

**Applies to Media Type**:
- Video

**Use Cases**:
- To perform very basic functional tests of the MRE control plane.

**Dependencies**:
- None

**ML Model dependencies**:
- None

**Other plugin dependencies**:
- None

**Parameter inputs**:
- chunk_to_segment_ratio >> What the approximate length the segment will be relative to the chunk length

**Output attributes**:
- None

**IAM permissions (least privilege)**:
- None
