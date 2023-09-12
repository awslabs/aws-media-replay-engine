
# Media Replay Engine Test Suite

## Overview

The Media Replay Engine test suite provides a collection of integration test cases to enable regression testing.
Test cases are grouped based on MRE constructs such as Models, Plugins, Profiles, Events
and can be found under the folder **tests/core**.

In the current release, the following are the scope of test cases 

|Entity   |Test case scope                                                 |
|---------|----------------------------------------------------------------|
|Models   |Creation, Deletion, Versioning, Validation              |
|Plugins  |Creation, Deletion, Versioning, Validation              |
|Profiles |Creation, Deletion, Validation, Featurer as/not a dependency for Replay  |
|Events   |Register and Process VOD/FUTURE events using MediaLive/BYOB as source    |


## Prerequisites

* python >= 3.8
* aws-cli
* aws-cdk >= 2.24.1
* docker
* node >= 16.15.0


## Deploy

To deploy the MRE test suite, run the following command within the **tests** folder.

```bash
chmod +x ./deploy.sh
./deploy.sh
```

### :heavy_exclamation_mark: **Attention!**
 
 `The MRE test suite deployment process creates 8 AWS MediaLive channels to enable parallel test runs. Before triggering the deployment process, ensure that the quota for maximum number of channels (defaulted to 5) that you can create in the current region has been increased by 8. Failing to increase the quota will result in deployment failure. `

## Plugin dependencies
The following MRE sample plugins should be deployed and registered within MRE to successfully run the tests.

- DetectPassThrough100
- LabelPassThrough
- OptimizePassThrough
- SegmentPassThrough100

Refer to the **Readme** under the **samples** folder for details on deploying and registering these plugins.

## Running test suite locally

1. Configure AWS Command Line Interface (AWS CLI) to interact with AWS. This will create a aws profile.
2. Define values for AWS_REGION and AWS_PROFILE and run the following command to execute all test cases.

```bash
./test-suite-entry.sh --region AWS_REGION --profile AWS_PROFILE
```


## Test Grouping

By default, running the **./test-suite-entry.sh** script runs all the tests. Tests can also be run at a group level. For example, if you are interested in running all tests for a VOD based MRE Event using MediaLive channel as the 
Video source, you can do so by running the following command. This command runs 4 tests in parallel as indicated by the option -n 4.

```bash
pytest -s -v -m past_event_media_live_as_source ./core/Events/event_media_live_test.py -n 4 --self-contained-html --html=past_event_media_live_as_source.html
```

Similarly, to run tests for a MRE Event scheduled in the FUTURE using BYOB as the Video source, run the following command.  This command runs 4 tests in parallel as indicated by the option -n 4.


```bash
pytest -s -v -m future_event_byob_as_source ./core/Events/event_byob_test.py -n 4 --self-contained-html --html=future_event_byob_as_source.html
```

Refer to **pytest.ini** at the root of the **tests** folder to view the groupings supported. The script defined in **./test-suite-entry.sh** orchestrates all these tests cases based on the test grouping.

