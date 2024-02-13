# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from aws_cdk import App, Aspects
from stacks.mre_fan_experience_frontend_stack import MreFanExperienceFrontendStack
from cdk_nag import AwsSolutionsChecks

app = App()

MreFanExperienceFrontendStack(app, "mre-fan-experience-frontend-stack")
Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

app.synth()

