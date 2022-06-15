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
		"DependentPlugins": [{
			"Configuration": {
				"Minimum-Confidence": "0.6"
			},
			"DependentFor": ["TennisSegmentation"],
			"Name": "DependentPlugin1"
		},{
			"DependentFor": ["DependentPlugin1"],
			"Name": "DependentPlugin2"
		},{
			"DependentFor": ["DependentPlugin2"],
			"Name": "DependentPlugin3"
		},{
			"DependentFor": ["DependentPlugin2"],
			"Name": "DependentPlugin4"
		},{
			"DependentFor": ["DependentPlugin3", "DependentPlugin4"],
			"Name": "DependentPlugin5"
		},{
			"DependentFor": ["DependentPlugin5"],
			"Name": "DependentPlugin6"
		},{
			"DependentFor": ["DependentPlugin5"],
			"Name": "DependentPlugin7"
		}],
		"Name": "TennisSegmentation"
	}
}
```

Profiles should be created to support different types of content (sports, news or other types of material). Experimentation is made easier with profiles where you different versions can be created and results compared to determine more optimal settings to improve accuracy or latency for example.

The payload to the **profile** API takes a payload that is described here:

[POST /profile](https://htmlpreview.github.io/?https://github.com/awslabs/aws-media-replay-engine/blob/main/docs/source/output/api/controlplane-profile.html#create-profile)
