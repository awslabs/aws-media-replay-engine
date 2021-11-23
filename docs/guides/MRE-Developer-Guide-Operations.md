![mre-header](mre-header-1.png)

# Developers Guide - Operating a MRE solution

AWS CloudWatch metrics are essential.

## Cost optimization

- Ensure ML endpoints are stopped when not in use
- If using Amazon Rekognition Custom Labels, calculate the number of inference units needed when configuring the service and then monitor actual use
- Experiment with the **Processing Frames per Second (FPS)** parameter in the MRE Profile as this allows easy control of how many frames actually are analyzed. This can effect Lambda function runtime and ML endpoint utilization both of which also contribute to system latency. You may find that you only need to process one frame every second to achieve the desired accuracy results. This is far more efficient than processing 25 or 30 FPS.
- Ensure Featurer plugins honor the **Processing FPS** profile parameter.
- Review audio track processing needs in your profile. By default, MRE will run audio-based Featurer plugins for each audio track configured in the event. This can add significant cost that can be avoided if the goal of the profile is not audio dependent.
- Use the minimal source video resolution needed to achieve the desired accuracy. Lower resolution video will also improve latency. The exported clip data can be applied to a higher resolution source separately to generate the content for distribution.

 
