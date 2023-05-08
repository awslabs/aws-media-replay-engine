# SegmentBySceneChangeWithOffset #

**MRE Plugin Class**
- Segmenter

**Description**:

This plugin is advanced version of SegmentByScene plugin which can work with different offset to find the end of a sequence.
More details of offset usage can be found below in the "Parameter inputs" session  

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
- frame 1 >> scene1
- frame 4 >> scene2
- frame 6 >> scene3
- frame 8 >> scene1

**Applies to Media Type**:
- Video

**Use Cases**:
- Sports programming including tennis and soccer have been successfully tested with this methodology to detect both the start and end of a clip.

**Dependencies**:
- MRE Helper libraries

**ML Model dependencies**:
- none

**Other plugin dependencies**:
- A scene detection plugin (featurer class) for your content trained to a list of labels that represent the different views in your video

**Parameter inputs**:
- start_seq >> array of dictionary in this format: {'offset':offset_number, 'patter':[['scene1','scene2']]}
- stop_seq >> array of dictionary in this format: {'offset':offset_number, 'patter':[['scene2','scene1']]}  
- padding_seconds >> Padding to put at the beginning and end of each clip returned.
- offset >> The offset to move the searching pointer right after the start_seq match.   
 
*** offset = 1 example  
start_seq = {'offset': 1, 'patter':[['scene1','scene2']]}  
end_seq =   {'offset': 1, 'patter':[['scene2','scene1']]}  

Assume we have de-dupped seq as following
- frame 100 >> scene1
- frame 120 >> scene2
- frame 150 >> scene1

A pointer will be initialized at frame 1 and move 1 step at a time to look for matching patterns. 
The start_seq will be found when the pointer reaches frame 100, since it matches the ['scene1','scene2'] pattern together with next scene at frame 120. To look for end_seq with offset being 1, the pointer will move 1 step to frame 120, and it immediately finds end_seq by matching the ['scene2','scene1'] patter with next scene at frame 150. Frame 150 will be marked as end_seq

*** offset = 2 example  
start_seq = {'offset': 2, 'patter':[['scene1','scene2']]}  
end_seq =   {'offset': 2, 'patter':[['scene2','scene1']]}  

Assume we have de-dupped seq as following
- frame 100 >> scene1
- frame 120 >> scene2
- frame 130 >> scene3
- frame 140 >> scene2
- frame 150 >> scene1

A pointer will be initialized at frame 1 and move 1 step at a time to look for matching patterns. 
The start_seq will be found when the pointer reaches frame 100, since it matches the ['scene1','scene2'] pattern together with next scene at frame 120. To look for end_seq with offset being 2, the pointer will move 2 steps to frame 130. The pattern ['scene3','scene2'] doesn't match any patterns so the pointer will keep moving to the next one at from 140. Now the pattern ['scene2','scene1'] matches the end_seq so that frame 150 will be marked as end_seq. 

- pattern >> the sequence patter list
-- Multiple string sequences can be provided as needed like this:
[['scene1','scene2'],['scene3','scene2']]
-- A sequence can be any length:
[['scene1','scene2','scene3']]

With offset set to 1, the program will look for end of seg.  
**Output attributes**:
- None

**IAM permissions (least privilege)**:
- None
