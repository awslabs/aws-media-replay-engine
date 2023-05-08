[![Header](../assets/images/mre-header-1.png)](../../MRE-Developer-Guide.md)

# Developers Guide - Profiles

Profiles in MRE exist to assemble the plugins and model configurations that are needed to accomplish a specific outcome. Sections for plugins classes exist where the desired plugins are linked together to form the skeleton of the pipeline that analyzes a specific type of video content.

In the example below, a basic tennis profile is shown that has four featurer class plugins, one segmenter plugin, one labeler and and one optimizer class plugin.  

![profile-example](../assets/images/devguide-profile-example.png)

In the example above, the **Detect Tennis Scores** plugin is dependent on the **Detect Scorebox** plugin. As a result, when the pipeline processes a video chunk, it will sequence the two plugin respectfully. The reason why this is setup this way is because the scorebox detection plugin results can be designed to be multi-sport for example. Then the appropriate score detection plugin can be applied to that result (tennis scores). This simplifies development when many different types of content (different sports) are needed to be processed.

Currently, MRE supports multiple level of dependencies (i.e., DependentPlugins) for all the plugin classes. These are handled recursively during profile creation using the "DependentFor" key in the "DependentPlugins" object list as shown below. Note that the actual dependency for each plugin is configured during its plugin registration process.

```
{
    "Name": "TennisProfile",
    "ContentGroups": ["Tennis"],
	"ProcessingFrameRate": 5,
	"ChunkSize": 10,
	"MaxSegmentLengthSeconds": 120,
	"Classifier": {
		"Configuration": {
			"start_seq": "[['near','far'],['topview','far']]",
			"padding_seconds": "1",
			"end_seq": "[['far','near'],['far','topview']]"
		},
		"DependentPlugins": [
			{
				"Configuration": {
					"Minimum-Confidence": "0.6"
				},
				"DependentFor": ["TennisSegmentation"],
				"Name": "DependentPlugin1"
			},
			{
				"DependentFor": ["DependentPlugin1"],
				"Name": "DependentPlugin2"
			},
			{
				"DependentFor": ["DependentPlugin2"],
				"Name": "DependentPlugin3"
			},
			{
				"DependentFor": ["DependentPlugin2"],
				"Name": "DependentPlugin4"
			},
			{
				"DependentFor": ["DependentPlugin3", "DependentPlugin4"],
				"Name": "DependentPlugin5"
			},
			{
				"DependentFor": ["DependentPlugin5"],
				"Name": "DependentPlugin6"
			},
			{
				"DependentFor": ["DependentPlugin5"],
				"Name": "DependentPlugin7"
			}
		],
		"Name": "TennisSegmentation"
	}
}
```

Profiles should be created to support different types of content (sports, news or other types of material). Experimentation is made easier with profiles where different versions can be created and results compared to determine more optimal settings to improve accuracy or latency for example.

By default, all the independent Featurer plugins included in the profile are executed before the Segmenter plugin to ensure accurate catchup highlights generation. In scenarios where this is not necessary, an independent Featurer plugin can be configured to be executed in parallel with the Segmenter plugin (for low latency) by including the "IsPriorityForReplay" attribute with a value of false while adding the independent Featurer plugin to a profile.

```
{
    "Name": "TennisProfile",
    "ContentGroups": ["Tennis"],
	"ProcessingFrameRate": 5,
	"ChunkSize": 10,
	"MaxSegmentLengthSeconds": 120,
	"Classifier": {
		"Configuration": {
			"start_seq": "[['near','far'],['topview','far']]",
			"padding_seconds": "1",
			"end_seq": "[['far','near'],['far','topview']]"
		},
		"DependentPlugins": [
			{
				"Configuration": {
					"Minimum-Confidence": "0.6"
				},
				"DependentFor": ["TennisSegmentation"],
				"Name": "DependentPlugin1"
			},
			{
				"DependentFor": ["DependentPlugin1"],
				"Name": "DependentPlugin2"
			},
			{
				"DependentFor": ["DependentPlugin2"],
				"Name": "DependentPlugin3"
			},
			{
				"DependentFor": ["DependentPlugin2"],
				"Name": "DependentPlugin4"
			},
			{
				"DependentFor": ["DependentPlugin3", "DependentPlugin4"],
				"Name": "DependentPlugin5"
			},
			{
				"DependentFor": ["DependentPlugin5"],
				"Name": "DependentPlugin6"
			},
			{
				"DependentFor": ["DependentPlugin5"],
				"Name": "DependentPlugin7"
			}
		],
		"Name": "TennisSegmentation"
	},
	"Featurers": [
		{
			"Name": "IndependentFeaturer1",
			"DependentPlugins": [
				{
					"Name": "DependentPlugin8",
					"Configuration": {
						"minimum_confidence": "0.9"
					},
					"DependentFor": [
						"IndependentFeaturer1"
					]
				}
			]
		},
		{
			"Name": "IndependentFeaturer2",
			"IsPriorityForReplay": false
		},
		{
			"Name": "IndependentFeaturer3",
			"IsPriorityForReplay": false
		}
	]
}
```
The payload to the **profile** API takes a payload that is described here:

[POST /profile](https://htmlpreview.github.io/?https://github.com/awslabs/aws-media-replay-engine/blob/main/docs/source/output/api/controlplane-profile.html#create-profile)

## Context Variables

Profiles can also include **Context Variables**, key/value pairs which provide additional data to be used by the created Event and read by the plugins used in the workflow. Use cases for this include:

- Custom attributes to coorindate with external processing
- Common attribute values used across all plugin executions (i.e. time offset, broadcast id, etc.)
- Sharing data between plugin executions across all chunks (i.e. a value from chunk 1 gets passed to chunk 2, chunk 2 adds more data for chunk 3, etc.)

Context Variables created in the profile act as a template for the events which are later created. For example, creating a profile called *TestProfile* with the Context Variables:

```
{
	"TimeOffset": 12,
	"BroadcastId": <EVENT_PLACEHOLDER>,
}
```

When you create the Event, and select *TestProfile* as the profile, you will have the option to modify the Profile Context Variable values & add additional Context Variables as well. The Profile Context Variables serve as the template for which future events will be created when selecting the profile.

```
{
	"TimeOffset": 12,
	"BroadcastId": 12345,
	"EventData": "New Data"
}
```