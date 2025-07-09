#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from aws_cdk import App, Aspects
from stacks.chaliceapp import ChaliceApp
from cdk_nag import AwsSolutionsChecks

app = App()
stack = ChaliceApp(app, "mre-live-news-segmenter-api-stack")
Aspects.of(stack).add(AwsSolutionsChecks(verbose=True))

app.synth()
