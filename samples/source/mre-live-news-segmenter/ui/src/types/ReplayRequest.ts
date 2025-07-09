/* eslint-disable @typescript-eslint/no-explicit-any */

export interface ReplayRequest {
  Program: string;
  Event: string;
  Requester: string;
  AudioTrack: number;
  Catchup: boolean;
  Description: string;
  UxLabel: string;
  TransitionName: string;
  TransitionOverride: TransitionOverride;
  ClipfeaturebasedSummarization: boolean;
  CreateHls: boolean;
  CreateMp4: boolean;
  IgnoreDislikedSegments: boolean;
  IncludeLikedSegments: boolean;
  Priorities: Priorities;
  Resolutions: string[] | undefined;
  SpecifiedTimestamps: string;
  DurationbasedSummarization: DurationbasedSummarization | undefined;
}

interface Priorities {
  Clips: (TimeBasedClip | FeatureBasedClip | DurationBasedClip)[];
}

export interface TimeBasedClip {
  StartTime: number | undefined;
  EndTime: number | undefined;
  Name: string;
}

export interface DurationBasedClip {
  Name: string;
  PluginName: string;
  Weight: number;
  AttribName: string;
  AttribValue: boolean;
}
export interface FeatureBasedClip {
  Name: string;
  PluginName: string;
  Include: boolean;
  AttribName: string;
  AttribValue: boolean;
}

interface TransitionOverride {
  FadeOutMs: number;
  FadeInMs: number;
}

interface DurationbasedSummarization {
  Duration: number;
  EqualDistribution: boolean;
  FillToExact: boolean;
  ToleranceMaxLimitInSecs: number;
}

// {
// 	"AudioTrack": 1,
// 	"Catchup": false,
// 	"ClipfeaturebasedSummarization": false,
// 	"CreateHls": false,
// 	"CreateMp4": true,
// 	"Description": "The context provides details about the introduction and opening remarks for the first 2020 presidential debate between Donald Trump and Joe Biden, held at the Health Education Campus of Case Western Reserve University and the Cleveland Clinic. The event organizers, including the Commission on Presidential Debates, the Cleveland Clinic, and Case Western Reserve University, expressed gratitude to various individuals and organizations who contributed to making the event possible. The format and rules of the debate were also outlined.",
// 	"Event": "ARDebateTest3",
// 	"IgnoreDislikedSegments": false,
// 	"IncludeLikedSegments": false,
// 	"Priorities": {
// 		"Clips": [
// 			{
// 				"EndTime": 507.15,
// 				"Name": "424.829 -  507.15",
// 				"StartTime": 424.829
// 			},
// 			{
// 				"EndTime": 700.009,
// 				"Name": "520.14 -  700.009",
// 				"StartTime": 520.14
// 			},
// 			{
// 				"EndTime": 760.43,
// 				"Name": "637.009 -  760.43",
// 				"StartTime": 637.009
// 			},
// 			{
// 				"EndTime": 1080.33,
// 				"Name": "991.77 -  1080.33",
// 				"StartTime": 991.77
// 			},
// 			{
// 				"EndTime": 1220.2,
// 				"Name": "1120.009 -  1220.2",
// 				"StartTime": 1120.009
// 			},
// 			{
// 				"EndTime": 1740.159,
// 				"Name": "1643 -  1740.159",
// 				"StartTime": 1643
// 			},
// 			{
// 				"EndTime": 1771.72,
// 				"Name": "1668.369 -  1771.72",
// 				"StartTime": 1668.369
// 			}
// 		]
// 	},
// 	"Program": "Debates",
// 	"Requester": "user",
// 	"Resolutions": [
// 		"1:1 (1080 x 1080)"
// 	],
// 	"SpecifiedTimestamps": "424.829, 507.15\n520.14, 700.009\n637.009, 760.43\n991.77, 1080.33\n1120.009, 1220.2\n1643, 1740.159\n1668.369, 1771.72",
// 	"TransitionName": "None",
// 	"UxLabel": "heart"
// }

// {
// 	"AudioTrack": 1,
// 	"Catchup": false,
// 	"ClipfeaturebasedSummarization": false,
// 	"CreateHls": true,
// 	"CreateMp4": false,
// 	"Description": "Based on the context provided, the clips appear to feature Donald Trump, Joe Biden, and Chris Wallace, who moderated the first 2020 presidential debate between Trump and Biden.",
// 	"DurationbasedSummarization": {
// 		"Duration": 60,
// 		"EqualDistribution": true,
// 		"FillToExact": true,
// 		"ToleranceMaxLimitInSecs": 30
// 	},
// 	"Event": "ARDebateTest3",
// 	"IgnoreDislikedSegments": false,
// 	"IncludeLikedSegments": false,
// 	"Priorities": {
// 		"Clips": [
// 			{
// 				"AttribName": "Summary",
// 				"AttribValue": true,
// 				"Name": "SegmentNews | Summary | true",
// 				"PluginName": "SegmentNews",
// 				"Weight": 2
// 			},
// 			{
// 				"AttribName": "Celebrities",
// 				"AttribValue": true,
// 				"Name": "SegmentNews | Celebrities | true",
// 				"PluginName": "SegmentNews",
// 				"Weight": 1
// 			},
// 			{
// 				"AttribName": "Scene_Description",
// 				"AttribValue": true,
// 				"Name": "SegmentNews | Scene_Description | true",
// 				"PluginName": "SegmentNews",
// 				"Weight": 35
// 			},
// 			{
// 				"AttribName": "Primary_Sentiment",
// 				"AttribValue": true,
// 				"Name": "DetectSentiment | Primary_Sentiment | true",
// 				"PluginName": "DetectSentiment",
// 				"Weight": 3
// 			},
// 			{
// 				"AttribName": "positive_flag",
// 				"AttribValue": true,
// 				"Name": "DetectSentiment | positive_flag | true",
// 				"PluginName": "DetectSentiment",
// 				"Weight": 4
// 			},
// 			{
// 				"AttribName": "Transcription",
// 				"AttribValue": true,
// 				"Name": "DetectSentiment | Transcription | true",
// 				"PluginName": "DetectSentiment",
// 				"Weight": 4
// 			},
// 			{
// 				"AttribName": "negative_flag",
// 				"AttribValue": false,
// 				"Name": "DetectSentiment | negative_flag | false",
// 				"PluginName": "DetectSentiment",
// 				"Weight": 4
// 			},
// 			{
// 				"AttribName": "negative_score",
// 				"AttribValue": true,
// 				"Name": "DetectSentiment | negative_score | true",
// 				"PluginName": "DetectSentiment",
// 				"Weight": 23
// 			},
// 			{
// 				"AttribName": "neutral_flag",
// 				"AttribValue": true,
// 				"Name": "DetectSentiment | neutral_flag | true",
// 				"PluginName": "DetectSentiment",
// 				"Weight": 4
// 			},
// 			{
// 				"AttribName": "flag_celebrity4",
// 				"AttribValue": true,
// 				"Name": "DetectCelebrities | flag_celebrity4 | true",
// 				"PluginName": "DetectCelebrities",
// 				"Weight": 23
// 			},
// 			{
// 				"AttribName": "Speaker",
// 				"AttribValue": true,
// 				"Name": "DetectSpeech | Speaker | true",
// 				"PluginName": "DetectSpeech",
// 				"Weight": 23
// 			}
// 		]
// 	},
// 	"Program": "Debates",
// 	"Requester": "user",
// 	"Resolutions": [
// 		"1:1 (1080 x 1080)"
// 	],
// 	"TransitionName": "None",
// 	"UxLabel": "rocky"
// }

// {
// 	"AudioTrack": 1,
// 	"Catchup": false,
// 	"ClipfeaturebasedSummarization": true,
// 	"CreateHls": false,
// 	"CreateMp4": true,
// 	"Description": "this is the description lorem ipsum you know the deal.",
// 	"Event": "ARDebateTest3",
// 	"IgnoreDislikedSegments": false,
// 	"IncludeLikedSegments": false,
// 	"Priorities": {
// 		"Clips": [
// 			{
// 				"AttribName": "Label",
// 				"AttribValue": true,
// 				"Include": false,
// 				"Name": "SegmentNews | Label | true",
// 				"PluginName": "SegmentNews"
// 			},
// 			{
// 				"AttribName": "Summary",
// 				"AttribValue": true,
// 				"Include": false,
// 				"Name": "SegmentNews | Summary | true",
// 				"PluginName": "SegmentNews"
// 			},
// 			{
// 				"AttribName": "Transcript",
// 				"AttribValue": true,
// 				"Include": true,
// 				"Name": "SegmentNews | Transcript | true",
// 				"PluginName": "SegmentNews"
// 			},
// 			{
// 				"AttribName": "Celebrities",
// 				"AttribValue": true,
// 				"Include": true,
// 				"Name": "SegmentNews | Celebrities | true",
// 				"PluginName": "SegmentNews"
// 			},
// 			{
// 				"AttribName": "Sentiment",
// 				"AttribValue": true,
// 				"Include": false,
// 				"Name": "SegmentNews | Sentiment | true",
// 				"PluginName": "SegmentNews"
// 			},
// 			{
// 				"AttribName": "Scene_Description",
// 				"AttribValue": true,
// 				"Include": true,
// 				"Name": "SegmentNews | Scene_Description | true",
// 				"PluginName": "SegmentNews"
// 			},
// 			{
// 				"AttribName": "Primary_Sentiment",
// 				"AttribValue": true,
// 				"Include": true,
// 				"Name": "DetectSentiment | Primary_Sentiment | true",
// 				"PluginName": "DetectSentiment"
// 			},
// 			{
// 				"AttribName": "positive_flag",
// 				"AttribValue": false,
// 				"Include": false,
// 				"Name": "DetectSentiment | positive_flag | false",
// 				"PluginName": "DetectSentiment"
// 			},
// 			{
// 				"AttribName": "positive_flag",
// 				"AttribValue": true,
// 				"Include": false,
// 				"Name": "DetectSentiment | positive_flag | true",
// 				"PluginName": "DetectSentiment"
// 			},
// 			{
// 				"AttribName": "Transcription",
// 				"AttribValue": true,
// 				"Include": false,
// 				"Name": "DetectSentiment | Transcription | true",
// 				"PluginName": "DetectSentiment"
// 			},
// 			{
// 				"AttribName": "neutral_score",
// 				"AttribValue": true,
// 				"Include": true,
// 				"Name": "DetectSentiment | neutral_score | true",
// 				"PluginName": "DetectSentiment"
// 			},
// 			{
// 				"AttribName": "positive_score",
// 				"AttribValue": true,
// 				"Include": true,
// 				"Name": "DetectSentiment | positive_score | true",
// 				"PluginName": "DetectSentiment"
// 			},
// 			{
// 				"AttribName": "mixed_score",
// 				"AttribValue": true,
// 				"Include": false,
// 				"Name": "DetectSentiment | mixed_score | true",
// 				"PluginName": "DetectSentiment"
// 			},
// 			{
// 				"AttribName": "Label",
// 				"AttribValue": true,
// 				"Include": false,
// 				"Name": "DetectSentiment | Label | true",
// 				"PluginName": "DetectSentiment"
// 			},
// 			{
// 				"AttribName": "mixed_flag",
// 				"AttribValue": false,
// 				"Include": true,
// 				"Name": "DetectSentiment | mixed_flag | false",
// 				"PluginName": "DetectSentiment"
// 			},
// 			{
// 				"AttribName": "mixed_flag",
// 				"AttribValue": true,
// 				"Include": false,
// 				"Name": "DetectSentiment | mixed_flag | true",
// 				"PluginName": "DetectSentiment"
// 			},
// 			{
// 				"AttribName": "negative_flag",
// 				"AttribValue": false,
// 				"Include": true,
// 				"Name": "DetectSentiment | negative_flag | false",
// 				"PluginName": "DetectSentiment"
// 			},
// 			{
// 				"AttribName": "negative_flag",
// 				"AttribValue": true,
// 				"Include": true,
// 				"Name": "DetectSentiment | negative_flag | true",
// 				"PluginName": "DetectSentiment"
// 			},
// 			{
// 				"AttribName": "negative_score",
// 				"AttribValue": true,
// 				"Include": false,
// 				"Name": "DetectSentiment | negative_score | true",
// 				"PluginName": "DetectSentiment"
// 			},
// 			{
// 				"AttribName": "neutral_flag",
// 				"AttribValue": false,
// 				"Include": true,
// 				"Name": "DetectSentiment | neutral_flag | false",
// 				"PluginName": "DetectSentiment"
// 			},
// 			{
// 				"AttribName": "neutral_flag",
// 				"AttribValue": true,
// 				"Include": false,
// 				"Name": "DetectSentiment | neutral_flag | true",
// 				"PluginName": "DetectSentiment"
// 			},
// 			{
// 				"AttribName": "flag_celebrity1",
// 				"AttribValue": true,
// 				"Include": true,
// 				"Name": "DetectCelebrities | flag_celebrity1 | true",
// 				"PluginName": "DetectCelebrities"
// 			},
// 			{
// 				"AttribName": "flag_celebrity2",
// 				"AttribValue": true,
// 				"Include": true,
// 				"Name": "DetectCelebrities | flag_celebrity2 | true",
// 				"PluginName": "DetectCelebrities"
// 			},
// 			{
// 				"AttribName": "flag_celebrity3",
// 				"AttribValue": true,
// 				"Include": false,
// 				"Name": "DetectCelebrities | flag_celebrity3 | true",
// 				"PluginName": "DetectCelebrities"
// 			},
// 			{
// 				"AttribName": "flag_celebrity4",
// 				"AttribValue": true,
// 				"Include": true,
// 				"Name": "DetectCelebrities | flag_celebrity4 | true",
// 				"PluginName": "DetectCelebrities"
// 			},
// 			{
// 				"AttribName": "flag_celebrity5",
// 				"AttribValue": true,
// 				"Include": false,
// 				"Name": "DetectCelebrities | flag_celebrity5 | true",
// 				"PluginName": "DetectCelebrities"
// 			},
// 			{
// 				"AttribName": "Image_Summary",
// 				"AttribValue": true,
// 				"Include": true,
// 				"Name": "DetectSceneLabels | Image_Summary | true",
// 				"PluginName": "DetectSceneLabels"
// 			},
// 			{
// 				"AttribName": "Label",
// 				"AttribValue": true,
// 				"Include": true,
// 				"Name": "DetectSpeech | Label | true",
// 				"PluginName": "DetectSpeech"
// 			},
// 			{
// 				"AttribName": "Transcription",
// 				"AttribValue": true,
// 				"Include": false,
// 				"Name": "DetectSpeech | Transcription | true",
// 				"PluginName": "DetectSpeech"
// 			},
// 			{
// 				"AttribName": "Speaker",
// 				"AttribValue": true,
// 				"Include": true,
// 				"Name": "DetectSpeech | Speaker | true",
// 				"PluginName": "DetectSpeech"
// 			}
// 		]
// 	},
// 	"Program": "Debates",
// 	"Requester": "user",
// 	"Resolutions": [
// 		"1:1 (1080 x 1080)"
// 	],
// 	"TransitionName": "None",
// 	"UxLabel": "test"
// }
