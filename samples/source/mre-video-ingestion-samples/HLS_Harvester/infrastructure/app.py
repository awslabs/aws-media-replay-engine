# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

#!/usr/bin/env python3
from aws_cdk import App
from stacks.chaliceapp import ChaliceApp

app = App()
ChaliceApp(app, 'aws-mre-samples-hls-harvester')

app.synth()
