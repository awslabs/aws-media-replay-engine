# Change Log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2021-04-05

⚠️ We have made a number of changes to improve the overall MRE Developer experience and fixed a number of defects. Some of these changes are breaking in nature. Upgrading from v1.0.1 to v2.0.0 involves a new deployment of MRE. This release does not provide any data migration options from v1.0.1 to v2.0.0. 

- New feature: Multiple micro services that are a part of the ControlPlane
- New feature: Gateway API for ControlPlane micro services
- New feature: Service discovery using Cloud Map
- Bug fix: Support for large feature sets found in Clips when creating replay requests
- Bug fix: Cloudfront Distribution domain name stored as a SSM param for MRE Fan Experience Frontend
- Bug Fix: Forcing MRE API to handle persistence of MediaLive payload as decimals.
- Bug fix: Several frontend bug fixes
