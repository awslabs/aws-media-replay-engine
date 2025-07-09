#!/usr/bin/env python3

#  Copyright 2024 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
from aws_cdk import App, Aspects
from stacks.mre_genai_search_stack import GenAISearchStack
from cdk_nag import AwsSolutionsChecks

app = App()
GenAISearchStack(
    app,
    "aws-mre-genai-search",
    env={
        "account": os.environ["CDK_DEFAULT_ACCOUNT"],
        "region": os.environ["CDK_DEFAULT_REGION"],
    },
)
Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

app.synth()
