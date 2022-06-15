#!/usr/bin/env python3
from aws_cdk import App
from stacks.sharedResources import MreSharedResources

app = App()

MreSharedResources(app, 'aws-mre-shared-resources', description="MRE Shared resources stack")

app.synth()
