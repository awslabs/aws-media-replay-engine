#!/usr/bin/env python3

#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from aws_cdk import App
from stacks.chaliceapp import ChaliceApp

app = App()
ChaliceApp(app, 'aws-mre-controlplane-workflow')

app.synth()
