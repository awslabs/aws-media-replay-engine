'''
 Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 SPDX-License-Identifier: Apache-2.0
'''

from aws_cdk import App, Aspects
from stacks.mre_frontend_stack import MreFrontendStack
from cdk_nag import AwsSolutionsChecks

app = App()

MreFrontendStack(app, "mre-frontend-stack")
Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

app.synth()