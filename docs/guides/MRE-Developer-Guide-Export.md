[![Header](../assets/images/mre-header-1.png)](../../MRE-Developer-Guide.md)


# Developers Guide - Export

Media Replay Engine (MRE) provides the capability to export Event and Replay data into JSON format for enabling B2B and B2C contexts. These exports capture key metadata about the segments created, optimization applied, profiles used and the locations of clips/thumbnails.

## Event data export schema

The API to request an event specific export is here:

[GET /export/data/event/{event}/program/{program}](https://htmlpreview.github.io/?https://github.com/awslabs/aws-media-replay-engine/blob/main/docs/source/output/api/controlplane-event.html#get-event-export-data)

Here's an example of the JSON formatted export data.

```json
{
  "Event": {
    "Name": "",
    "Id": "adc70e33-bf21-4b30-be61-588f3c9a6e20",
    "Program": "",
    "Start": "",
    "AudioTracksFound": [1, 2],
    "AllOutputAttributes": {
      "Labeler": [
        "MatchPoint",
        "Ace",
        "DoubleFaults",
        "GamePoint",
        "SetPoint",
        "BreakPoint"
      ]
    },
    "ProgramId": "",
    "Profile": {
      "Name": "",
      "ChunkSize": 20,
      "MaxSegmentLengthSeconds": 120,
      "ProcessingFrameRate": 5,
      "Classifier": {
        "Name": "TennisSegmentation",
        "Configuration": {
          "start_seq": "[['near','far'],['topview','far']]",
          "padding_seconds": "1",
          "end_seq": "[['far','near'],['far','topview']]"
        },
        "DependentPlugins": [
          {
            "Name": "TennisSceneClassification",
            "Configuration": { "minimum_confidence": "30" },
            "DependentFor": ["TennisSegmentation"],
            "Level": 1,
            "SupportedMediaType": "Video"
          }
        ]
      },
      "Labeler": {
        "Name": "TennisScoreExtraction",
        "Configuration": {},
        "DependentPlugins": [
          {
            "Name": "TennisScoreBoxDetection",
            "Configuration": { "Minimum-Confidence": "0.6" },
            "DependentFor": ["TennisScoreExtraction"],
            "Level": 1,
            "SupportedMediaType": "Video"
          }
        ]
      }
    },
    "SourceVideoMetadata": {}
  },
  "Segments": [
    {
      "Start": 222.2,
      "End": 224.4,
      "OptoStart": {},
      "OptoEnd": {},
      "OptimizedClipLocation": {},
      "OriginalClipLocation": {
        "1": "S3 Location of mp4 clip",
        "2": "S3 Location of mp4 clip"
      },
      "OriginalThumbnailLocation": "S3 location of Thumbnail",
      "FeaturesFound": [],
      "Feedback": []
    },
    {
        "Start": 227,
        "End": 235.4,
        "OptoStart": {},
        "OptoEnd": {},
        "OptimizedClipLocation": {},
        "OriginalClipLocation": {
          "1": "S3 Location of mp4 clip",
          "2": "S3 Location of mp4 clip"
        },
        "OriginalThumbnailLocation": "S3 location of Thumbnail",
        "FeaturesFound": [],
        "Feedback": []
    },
    {
      "Start": 236.4,
      "End": 238.6,
      "OptoStart": {},
      "OptoEnd": {},
      "OptimizedClipLocation": {},
      "OriginalClipLocation": {
        "1": "S3 Location of mp4 clip",
        "2": "S3 Location of mp4 clip"
      },
      "OriginalThumbnailLocation": "S3 location of Thumbnail",
      "FeaturesFound": [],
      "Feedback": []
    }
  ]
}

```

## Replay data export schema

The API to request a replay specific export is here:

[GET /export/data/replay/{id}/event/{event}/program/{program}](https://htmlpreview.github.io/?https://github.com/awslabs/aws-media-replay-engine/blob/main/docs/source/output/api/controlplane-replay.html#get-replay-export-data)

Here's an example of the JSON formatted export data.

```json
{
  "Event": {
    "Name": "",
    "Id": "adc70e33-bf21-4b30-be61-588f3c9a6e20",
    "Program": "",
    "Start": "2021-09-12T20:01:14Z",
    "AudioTracksFound": [1, 2],
    "AllOutputAttributes": {
      "Labeler": [
        "MatchPoint",
        "Ace",
        "DoubleFaults",
        "GamePoint",
        "SetPoint",
        "BreakPoint"
      ]
    },
    "ProgramId": "CUS-e100019790c0ch20010",
    "Profile": {
      "Name": "",
      "ChunkSize": 20,
      "MaxSegmentLengthSeconds": 120,
      "ProcessingFrameRate": 5,
      "Classifier": {
        "Name": "TennisSegmentation",
        "Configuration": {
          "start_seq": "[['near','far'],['topview','far']]",
          "padding_seconds": "1",
          "end_seq": "[['far','near'],['far','topview']]"
        },
        "DependentPlugins": [
          {
            "Name": "TennisSceneClassification",
            "Configuration": { "minimum_confidence": "30" },
            "DependentFor": ["TennisSegmentation"],
            "Level": 1,
            "SupportedMediaType": "Video"
          }
        ]
      },
      "Labeler": {
        "Name": "TennisScoreExtraction",
        "Configuration": {},
        "DependentPlugins": [
          {
            "Name": "TennisScoreBoxDetection",
            "Configuration": { "Minimum-Confidence": "0.6" },
            "DependentFor": ["TennisScoreExtraction"],
            "Level": 1,
            "SupportedMediaType": "Video"
          }
        ]
      }
    },
    "SourceVideoMetadata": {}
  },
  "Replay": {
    "Duration": 5.0,
    "EqualDistribution": "N",
    "Id": "2eae3581-5057-4274-a5c2-1d6cc4e10dab",
    "AudioTrack": 1.0,
    "FeaturesSelected": [
      { "FeatureName": "MatchPoint", "FeatureValue": "True", "Weight": 100.0 },
      { "FeatureName": "Ace", "FeatureValue": "True", "Weight": 55.0 },
      { "FeatureName": "DoubleFaults", "FeatureValue": "True", "Weight": 45.0 },
      { "FeatureName": "GamePoint", "FeatureValue": "True", "Weight": 75.0 },
      { "FeatureName": "SetPoint", "FeatureValue": "True", "Weight": 85.0 },
      { "FeatureName": "BreakPoint", "FeatureValue": "True", "Weight": 55.0 }
    ],
    "ReplayFormat": "Mp4",
    "Resolutions": [
      "16:9 (1920 x 1080)",
      "9:16 (608 x 1080)"
    ],
    "Catchup": "Y",
    "Mp4Location": {
      "16:9": {
        "ReplayClips": [
            "S3 Location of mp4 replay clip"
        ]
      },
      "9:16": {
        "ReplayClips": [
            "S3 Location of mp4 replay clip"
        ]
      }
    },
    "Mp4ThumbnailLocation": {
      "16:9": {
        "ReplayThumbnails": [
            "S3 Location of mp4 Thumbnail"
        ]
      },
      "9:16": {
        "ReplayThumbnails": [
            "S3 Location of mp4 Thumbnail"
        ]
      }
    }
  },
  "Segments": [
    {
      "Start": 1121.6,
      "End": 1158.4,
      "OptoStart": {},
      "OptoEnd": {},
      "OptimizedClipLocation": {},
      "OriginalClipLocation": {
        "1": "S3 Location of mp4 clip",
        "2": "S3 Location of mp4 clip"
      },
      "OriginalThumbnailLocation": "S3 location of Thumbnail",
      "Feedback": [],
      "FeaturesFound": [
        {
          "AttribName": "DoubleFaults",
          "PluginName": "TennisScoreExtraction",
          "AttribValue": "True",
          "MultiplierChosen": 5.0,
          "Weight": 45.0,
          "Name": "TennisScoreExtraction - DoubleFaults - True"
        },
        {
          "AttribName": "GamePoint",
          "PluginName": "TennisScoreExtraction",
          "AttribValue": "True",
          "MultiplierChosen": 8.0,
          "Weight": 75.0,
          "Name": "TennisScoreExtraction - GamePoint - True"
        }
      ]
    },
    {
      "Start": 1467.2,
      "End": 1498.8,
      "OptoStart": {},
      "OptoEnd": {},
      "OptimizedClipLocation": {},
      "OriginalClipLocation": {
        "1": "S3 Location of mp4 clip",
        "2": "S3 Location of mp4 clip"
      },
      "OriginalThumbnailLocation": "S3 location of Thumbnail",
      "Feedback": [],
      "FeaturesFound": [
        {
          "AttribName": "DoubleFaults",
          "PluginName": "TennisScoreExtraction",
          "AttribValue": "True",
          "MultiplierChosen": 5.0,
          "Weight": 45.0,
          "Name": "TennisScoreExtraction - DoubleFaults - True"
        },
        {
          "AttribName": "GamePoint",
          "PluginName": "TennisScoreExtraction",
          "AttribValue": "True",
          "MultiplierChosen": 8.0,
          "Weight": 75.0,
          "Name": "TennisScoreExtraction - GamePoint - True"
        }
      ]
    }
  ]
}
```
