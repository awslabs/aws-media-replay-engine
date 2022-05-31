# Change Log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2021-04-05

⚠️ We have made a number of changes to improve the overall MRE Developer experience and fixed a number of defects. Some of these changes are breaking in nature. Upgrading from v1.0.1 to v2.0.0 involves a new deployment of MRE. This release does not provide any data migration options from v1.0.1 to v2.0.0. For instructions on migrating data and changes to API consumers refer to the [MRE migration document](MRE-Migration.md).

- Added: Multiple micro services that are a part of the ControlPlane
- Added: Gateway API for ControlPlane micro services
- Added: Service discovery using Cloud Map
- Fixed: Support for large feature sets found in Clips when creating replay requests
- Fixed: Cloudfront Distribution domain name stored as a SSM param for MRE Fan Experience Frontend
- Fixed: Forcing MRE API to handle persistence of MediaLive payload as decimals.
- Fixed: Several frontend bug fixes


## [2.0.1] - 2021-05-31

- Fixed: Fixed a defect in API Authentication using JWT token. All GET requests were failing due to the wrong route configured in AuthResponse 
- Security: Upgraded PyJwt to 2.4.0 to mitigate the security risk - Key confusion through non-blocklisted public key formats (https://github.com/advisories/GHSA-ffqj-6fqr-9h24)
- Fixed: Plugin output attributes for Optimizer Plugins will not be displayed during replay creation.
