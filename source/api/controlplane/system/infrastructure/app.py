#!/usr/bin/env python3

#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from aws_cdk import App, Aspects
from stacks.chaliceapp import ChaliceApp
from cdk_nag import AwsSolutionsChecks

app = App()
ChaliceApp(app, 'aws-mre-controlplane-system')
Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

app.synth()
