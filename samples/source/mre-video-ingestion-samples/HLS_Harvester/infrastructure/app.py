# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

#!/usr/bin/env python3
from aws_cdk import App, Aspects
from stacks.chaliceapp import ChaliceApp
from cdk_nag import AwsSolutionsChecks

app = App()
ChaliceApp(app, 'aws-mre-samples-hls-harvester')
Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

app.synth()
