[![Header](../assets/images/mre-header-1.png)](../../MRE-Developer-Guide.md)

# Developers Guide - Replays

A **replay** in MRE is how you generate a filtered set of segments (clips) for an **event**. Multiple replay configurations can be added to an event, but they are not required. Replay configurations support generating a filtered and sequential output that support use cases such as:

- Highlight clips that fit within a designated total duration (i.e. 5 minutes of the best moments in a game)
- Clips that have a common feature (i.e. all the ace shots in a tennis match)
- Clips that feature a specific player

At this time, MRE supports the following options to configure a replay request:
- Duration (seconds) - This enforces a soft limit for the Replay duration. If MRE finds a segment which results in the duration being exceeded, it will include it. This may result in the total Replay duration to be much higher than the value specified. For example, if the duration specified is 60 secs and if including a new segment results in a total duration of 110 secs, the segment will get included.
- Tolerance (Default 30 secs) - This enforces a hard upper limit on the Replay duration. If the duration specified is 60 secs with a tolerance of 10 secs, the total Replay duration will be less or equal to 70 secs.
- Weightings (0 to 100) for each featurer plugin output attribute value

Featurer plugins should designed and selected in a profile to generate the types of data that need to be leveraged in a replay request.

By default, replay requests are calculated at the completion of the event. However, a feature called **catch up** mode indicates that the replay should be calculated continually throughout an event as each new segment (clip) is detected. This feature supports the use case where an audience joins an event late and wants to see highlights to bring them up to speed before joining the event live.

The payload to the **replay** API takes a payload that is described here:

[POST /replay](https://htmlpreview.github.io/?https://github.com/awslabs/aws-media-replay-engine/blob/main/docs/source/output/api/controlplane-replay.html#add-replay)


### Transitions

MRE supports Transitions to be added when creating Replay clips. Currently, a Fade In Fade out
transition option is made available during the Replay creation. Additional transitions can be onboarded using custom Transition clips in MP4 format. We recommend to use Transition clips which are 1 second in duration.

To onboard new transition clips into MRE,

- Upload the Transition clips to the S3 bucket. To find the bucket name, refer to the Cloudformation stack named **aws-mre-shared-resources**. In the output section, refer to the bucket name for the output key **mretransitionclipsbucket**.
- Modify the values defined within **%%** in the file 
**aws-media-replay-engine/source/backend/replay/PutTransitions.py**. Then run the command

```python
python3 PutTransitions.py
```

Login to the MRE frontend. You will see the new Transition option in the Transitions drop down when creating a new Replay.