#!/usr/bin/env python3

#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from aws_cdk import App, Tags, Aspects
from stacks.chaliceapp import ChaliceApp
from cdk_nag import AwsSolutionsChecks

app = App()
stack = ChaliceApp(app, 'aws-mre-dataplane')
Aspects.of(stack).add(AwsSolutionsChecks(verbose=True))

# Add a tag to all constructs in the stack
Tags.of(stack).add("Project", "AWS-MRE")
Tags.of(stack).add("System", "DataPlaneAPI")

app.synth()
