# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from aws_cdk import App, Aspects
from stacks.live_news_segmenter_frontend_stack import LiveNewSegmenterFrontendStack
from cdk_nag import AwsSolutionsChecks

app = App()

LiveNewSegmenterFrontendStack(app, "mre-live-news-segmenter-frontend-stack")
Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

app.synth()
