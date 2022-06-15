# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


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
