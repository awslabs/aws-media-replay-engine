# SegmentBySceneChange #

**MRE Plugin Class**
- Segmenter

**Description**:

This plugin is useful to perform general purpose segmentation where scene pattern changes can reliably indicate the start and end of a segment/clip. For example, a near camera shot followed by a far camera shot can reliably mark the start of a segment in tennis tournament video.

The featurer class plugin that detects the scene may be configured to process all frames, or sample at a lower rate using the specified MRE profile frame per second (FPS) parameter. This can be set so that for example only 1 frame per second is assessed which speeds up processing. In either case, the sequence of labels for the frames is du-dupped in this plugin to simplify the configuration.

An example follows:

- frame 1 >> scene1
- frame 2 >> scene1
- frame 3 >> scene1
- frame 4 >> scene2
- frame 5 >> scene2
- frame 6 >> scene3
- frame 7 >> scene3
- frame 8 >> scene1

when de-dupped becomes:
- scene1
- scene2
- scene3
- scene1

**Applies to Media Type**:
- Video

**Use Cases**:
- Sports programming including tennis and soccer have been successfully tested with this methodology to detect both the start and end of a clip.

**Dependencies**:
- MRE Helper libraries

**ML Model dependencies**:
- none

**Other plugin dependencies**:
- A scene detection plugin (featurer class) for your content trained to a list of labels that represent the different views in your video, For example: DetectCameraScene with your own model attached to it.

**Parameter inputs**:
- start_seq >> array of string sequences in this format: [['scene1','scene2']]
- stop_seq >> array of string sequences in this format: [['scene2','scene1']]
- padding_seconds >> Padding to put at the beginning and end of each clip returned.

Multiple string sequences can be provided as needed like this:
[['scene1','scene2'],['scene3','scene2']]

A sequence can be any length:
[['scene1','scene2','scene3']]

**Output attributes**:
- None

**IAM permissions (least privilege)**:
- None
