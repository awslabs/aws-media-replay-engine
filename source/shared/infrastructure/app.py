#!/usr/bin/env python3
from aws_cdk import core as cdk
from stacks.sharedResources import MreSharedResources

app = cdk.App()

MreSharedResources(app, 'aws-mre-shared-resources', description="MRE Shared resources stack")

app.synth()
