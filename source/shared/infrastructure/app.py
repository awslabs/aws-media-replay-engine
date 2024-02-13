#!/usr/bin/env python3
from aws_cdk import App, Aspects
from stacks.sharedResources import MreSharedResources
from cdk_nag import AwsSolutionsChecks

app = App()

MreSharedResources(app, 'aws-mre-shared-resources', description="MRE Shared resources stack")
Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

app.synth()
