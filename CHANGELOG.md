# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.7.0] - 2023-05-08
- MRE framework and Samples GitHub repositories are now merged to provide a unified codebase for deploying the MRE framework and optionally, sample plugins, profiles and ML model notebooks.
- Feature: Context variable support for MRE Events - MRE now supports adding context variables (key-value pairs) during Profile creation which can then be included (and optionally updated) during Event creation. When included, these event-level variables can be accessed and modified through MRE plugin helper functions in one or more Plugin lambdas thereby providing the ability to share event specific data across multiple plugins and step function invocations. More information on this can be found [here](docs/guides/MRE-Developer-Guide-Profiles.md#context-variables).
- Feature: Reworked the timestamp-based event filter component in the MRE List Events UI to list all the events starting prior to a given timestamp in a paginated fashion.

- Fixed:
    - Deleting an event does not automatically delete the related replay metadata.
    - Source S3 bucket drop-down does not list any buckets when creating a new event through the UI.
    - Occasional chunk processing failures caused by Gateway timeout error in the MRE helper layers.
    - List Replays control plane API (/replay/all) does not paginate to retrieve all the available data.
    - Replay engine not considering an empty Optimizer list (in Profile config) as a valid value when generating replays.


## [2.6.0] - 2023-01-31
- Feature: Event life cycle management - 
    - MRE automates event life cycle using EventBridge schedules. MRE now emits events to EventBridge whenever an event Starts, Ends and the status is marked "Complete".
    - MRE uses the BootstrapTimeInMinutes and DurationMinutes values to determine an Event's End and marks the Event (VOD/LIVE) as Complete.
    - When MediaLive is used as the Event's video source, the new Event API exposes an input attribute that can be configured to let MRE stop the MediaLive channel when an event ends.
- Feature: Ability to view mp4 highlight clips - MRE now supports the ability to view the final highlight clip when reviewing replay segments in the Clip preview page.
- Feature: Manual inclusion of segments in Highlights - Ability to always include segments when creating replays using the Thumbs up action in Clip preview page.
- Feature: Manual inclusion or exclusion of segments for highlights now triggers a new replay execution as long as the replay is configured to be in catchup mode.

- Fixed:
    - Event Start time now supports a granularity of specifying time in seconds
    - When all Completed Replays for an Event are deleted, the Events hasReplays attribute is set to False
    - Event filter in the Replay list UI now lists all the Events
    - Replay clip transition pixel offset issues
    - Dynamically configure Media Convert bitrate based on replay output resolution
    - "Events from" and "to" filters in the ListEvents MRE UI changed to use a UTC based backend filter
    - Clip feature based replays not generating highlights.
   

## [2.5.1] - 2022-11-14
- Feature: Support for Replay duration tolerance - With the tolerance value set, you can set a maximum Replay duration when the segments duration exceed the replay duration.

- Fixed:
    - Increased the total timeout of the CDK CustomResource Provider from the default 30 minutes to 2 hours to avoid stack timeouts during DynamoDB GSI creation.
    - Improved BYOB (Bring Your Own Bucket) S3 event notification - The new implementation configures one event notification trigger per bucket to avoid hard limit of 100 event notifications per S3 bucket (https://docs.aws.amazon.com/general/latest/gr/s3.html#limits_s3).


## [2.5.0] - 2022-11-04

- Feature: Support for pagination in the dataplane workflow APIs:
    - /workflow/segment/state
    - /workflow/labeling/segment/state
    - /workflow/optimization/segment/state
    - /plugin/dependentplugins/output

    > Pagination on the client-side is currently handled by the MediaReplayEnginePluginHelper Lambda layer such that this change is abstracted from the plugin developer.

    > ⚠️ This is a breaking feature release for MRE plugins where the plugin Lambda needs to use the latest MediaReplayEnginePluginHelper layer created as a part of building and deploying MRE v2.5.0.
- Feature: Support for clip transition effects during replay creation. By default, the Fade in/out transition option is provided with the ability to onboard new custom transition effects as MP4 videos.
- Feature: Ability to skip low quality segments when creating replays with the help of clip review feedback.
- Feature: Support for choosing one or more Feature detector plugins as priority for Replay when creating a Profile. This ensures that the Feature detector plugin completes its execution before the Segmentation plugin does in order to avoid missing clips in replay.

- Fixed:
    - Support for updating and deleting BYOB (Bring Your Own Bucket) based MRE Events.
    - Creating an Event via API does not automatically add the passed program value to *Program* DynamoDB table.
    - Creating a Model/Plugin/Profile via API does not automatically add the passed ContentGroup value to *ContentGroup* Dynamodb table.
    - Inaccurate frame timecode calculation by ProbeVideo when a live event starts exactly at 00:00 UTC.

- Rewrote BYOB (Bring Your Own Bucket) logic to create a unique S3 notfication per MRE Event.
- Optimized Amazon DynamoDB queries in the dataplane to mitigate throttling and reduce latency by:
    - Adding multiple Global Secondary Index (GSI) to the PluginResult table.
    - Using a new configuration parameter in the dataplane API Handler Lambda function called *MAX_DETECTOR_QUERY_WINDOW_SECS*. More information on this parameter can be found in the [Optimizer Developer Guide](docs/guides/MRE-Developer-Guide-Optimizer.md).
- Support for allowing Users to change their password in the MRE Frontend.
- Support for Replay duration to be configured in seconds in lieu of minutes during Replay creation.
    

## [2.4.0] - 2022-10-03

- Feature: A new caching layer has been introduced. A Segment Caching Lambda Caches Segment and Feature data into S3. This Cache gets used when Creating Replays and there by decrease the overall latency in Replay creation.

- Fixed:
    - Removed dependency on AWS Cloud Map to reduce latency and avoid throttling issues when discovering Micro services.
    - Pagination when viewing replay clips within Clip Preview
    - Timeout errors occurring during Event Data export
    - Several network calls to DDB, MediaConvert have been eliminated to improve end to end Latency
    - Implemented exponential back-off retry mechanism to fix intermittent API Connection errors.

## [2.3.0] - 2022-08-23

- Feature: Support for Optional clip generation for original and optimized segments. When creating MRE Events, it is now possible to mark clip generation as optional for either original or optimized (or both) segments in an effort to save cost and processing latency.
- Feature: Support for embedded timecode in the source video to handle multi-day events and reliable metadata synchronization. The timecode can either be ZERO_BASED or UTC_BASED.
- Fixed:
    - Default plugin configuration is not used if no configuration object is included in the Profile creation request.
    - Handle optional HLS clip format in replay data export.
    - Ignore 'In Progress' replays when getting eligible non-catchup replays in the replay engine.
    - Some of the features not associated correctly with the segments during replay and export creation.

## [2.2.0] - 2022-07-25

- Feature: Bring Your Own Bucket (BYOB) as the source for MRE Events. With this feature, you can stream video chunks to an existing S3 bucket in your AWS account and have them automatically processed by the MRE workflow provided an associated Event exists in MRE.
- Fixed:
    - Increased the Dataplane API Handler Lambda memory limit to 512 MB to avoid occasional processing timeouts and retries.
    - Profile SummaryView page breaks if a profile is created in MRE versions prior to v2.1.0.
    - Handle segments that don't have the optional Label attribute.
    - Timeout issues during Event and Replay metadata export.
- Improvements to the Replay engine query performance in order to avoid DDB throttling.

## [2.1.0] - 2022-06-15

- Feature: Plugins can now have multiple levels of dependency (i.e., DependentPlugins) compared to just one level in the prior MRE versions. These multiple level plugin dependencies are handled during profile creation.
    > ⚠️ This is a breaking feature release for MRE plugins where the plugin Lambda needs to use the latest MediaReplayEnginePluginHelper layer created as a part of building and deploying MRE v2.1.0.
- Migrated all the stacks in the framework to CDK v2.
- Fixed: 
    - get_segment_state API not differentiating between multiple dependent plugin results.
        > ⚠️ Due to this change, the third item in the get_segment_state API response is now of type dictionary instead of list. Refer to the sample code in the [Segmenter Plugin Dev Guide](docs/guides/MRE-Developer-Guide-Segmenter.md).
    - Profile DynamoDB table no longer stores the state_machine definition to keep the item size within the DynamoDB limit.
    - Not all the plugin OutputAttributes are displayed under priorities selection list during replay creation.
    - Clip generation engine selecting incorrect chunks to generate clips for optimized segments.
    - Gateway API not relaying ConflictError to clients.
    - Clip preview page not displaying all the clips in the thumbnail list.
- Minor change to the layout of the OutputAttributes in the view plugin page.

## [2.0.1] - 2022-05-31

- Fixed: Fixed a defect in API Authentication using JWT token. All GET requests were failing due to the wrong route configured in AuthResponse 
- Security: Upgraded PyJwt to 2.4.0 to mitigate the security risk - Key confusion through non-blocklisted public key formats (https://github.com/advisories/GHSA-ffqj-6fqr-9h24)
- Fixed: Plugin output attributes for Optimizer Plugins will not be displayed during replay creation.


## [2.0.0] - 2022-04-08

⚠️ We have made a number of changes to improve the overall MRE Developer experience and fixed a number of defects. Some of these changes are breaking in nature. Upgrading from v1.0.1 to v2.0.0 involves a new deployment of MRE. This release does not provide any data migration options from v1.0.1 to v2.0.0. For instructions on migrating data and changes to API consumers refer to the [MRE migration document](MRE-Migration.md).

- Added: Multiple micro services that are a part of the ControlPlane
- Added: Gateway API for ControlPlane micro services
- Added: Service discovery using Cloud Map
- Fixed: Support for large feature sets found in Clips when creating replay requests
- Fixed: Cloudfront Distribution domain name stored as a SSM param for MRE Fan Experience Frontend
- Fixed: Forcing MRE API to handle persistence of MediaLive payload as decimals.
- Fixed: Several frontend bug fixes


## [1.0.1] - 2022-01-14

- Fixed: issue in the Profile API where it would not create a Map state for audio-based DependentPlugins of Featurer.
- Fixed: issue in the get_dependent_plugins_output API where it would return empty results if the DependentPlugin is audio-based.
- Removed minItems requirement from the schema of both the get_segment_state and get_segment_state_for_labeling APIs to support Classifier and Labeler plugins with no DependentPlugins.
- Updated aws-amplify and react-scripts to a newer version.
- Fixed: issue in the Frontend UI that displayed number 0 when viewing an Event based on MediaLive channel.
- Fixed: Index exceeded condition from the ColorPalette library when too many Plugins exist.
- Fixed: issue where the Labels would not get displayed correctly even though they exist in the segment.


## [1.0.0] - 2021-11-24

- Initial release.
