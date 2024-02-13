![mre-header](docs/assets/images/mre-header-1.png)

# Developers Guide

## What is the Media Replay Engine?
It is an open source AWS solution you deploy into your own AWS account to automatically process live and VOD broadcast content to identify segments (clips) using machine learning. You can schedule replays based on your criteria to generate the desired content for linear and DTC channels. This enables personalized content to be delivered to viewers and allows for revenue generation through ad insertion as desired.

MRE is comprised of a core framework and a console UI. The UI can be optionally installed, but is enabled for install by default. As a customer, you then author plugins and ML models to process the video content using the MRE helper library to integrate with the solution. You also then integrate the source video, EPG data with your systems using scripts or other Lambda functions. The MRE API provided by the core framework make integration easy to accomplish.

![mre-solutions](/docs/assets/images/devguide-mre-solutions.png)

## How Media Replay Engine works?
MRE begins processing video at the designated start time (UTC) for configured events in the solution. The video stream is delivered to Amazon S3 as chunks of video that can be as small as 6 seconds if streaming from an HLS source or larger as configured in AWS Elemental Media Live. Typically a chunk size of 20 or 30 seconds works well as a starting point.

As each video chunk is put into S3, a serverless pipeline will process the respective S3 Object (chunk). The pipeline is automatically created in AWS Step Functions based on a MRE profile that is preconfigured. The profile defines the plugins to be used which essentially point to specific AWS Lambda functions. The video chunk attributes are passed in the event payload along with event specific metadata that each plugin (AWS Lambda Function) can use to process the video and audio as needed.

Plugins then submit key data back to the pipeline using a provided set of helper functions in a AWS Lambda Layer. These helper functions simplify the development experience and handle important tasks such read and write operations with the database tables, persist state of a segment across multiple chunks to find the proper ending and maintain scope of plugin results to the appropriate class of the plugin (there are four described later).

Add replay and export details  

![system-diagram](/docs/assets/images/devguide-system-diagram.png)


## Terminology
MRE refers to several elements of the solution using terms that may be familiar. Here are a few key terms that are used and their definitions as it relates to MRE.
- **Segments**: These are the the clips that are determined by the solution that have a **in** and **out** timecode for each event processed. The timecode used internal to MRE is an absolute time 0 that starts at the beginning of the event processing. Elsewhere in the solution, these times can be converted to a UTC timestamp or other whatever is needed to align with other systems in your architecture.
- **Models**: Machine learning models can be built and trained independent of MRE and then registered with the solution for use with Plugins. MRE does not require a specific AWS service be used to host a model endpoint.
- **Plugins**: MRE requires the use of Python 3 (3.11 was tested) to author plugins as AWS Lambda functions. The plugin is where business logic is added to process video chunks broken down into frames. Frames can be processed using computer vision, have inference called with a model endpoint or other AWS service.
- **Profiles**: A profile in MRE is defined for a specific type of media content that will be processed. The profile is a set of **plugins** and **models** that are applied to the **event** video as it is received and processed by the solution. Different profiles can be created to achieve different results based on business needs.  
- **Events**: Events in the MRE context are the scheduled programs that will be processed at a specific time with video chunk content arriving on a specified AWS Elemental Media Live Channel or in a S3 bucket. The events are the same as EPG programs and can have a broadcast ID to uniquely identify them.  
- **Replays**: A replay in MRE is a request to summarize all the **segments** from an **event** be selecting only those that match your criteria. Another term that is synonymous with replays is **highlights**. Options exist to filter the segments based on total duration and weightings applied to key data. Multiple replays can be applied to an event.



**Development with MRE involves the following topics:**
- [Plugin Development](docs/guides/MRE-Developer-Guide-Plugins.md)
- [ML Model Development](docs/guides/MRE-Developer-Guide-Models.md)
- [Profile Configuration](docs/guides/MRE-Developer-Guide-Profiles.md)
- [Event Creation](docs/guides/MRE-Developer-Guide-Events.md)
- [Source Video Integration](docs/guides/MRE-Developer-Guide-Video.md)
- [Replay Creation](docs/guides/MRE-Developer-Guide-Replays.md)
- [Exporting](docs/guides/MRE-Developer-Guide-Export.md)
- [Security](docs/guides/MRE-Developer-Guide-APIAuth.md)
- [Extending MRE](docs/guides/MRE-Developer-Guide-Extension.md)

## Architecture

![MRE_Architecture](/docs/assets/images/MRE_Architecture.png)
