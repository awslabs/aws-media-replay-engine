#!/usr/bin/env python3
from aws_cdk import core as cdk
from stacks.ClipGenStack import ClipGenStack

app = cdk.App()
ClipGenStack(app, 'aws-mre-clip-generation', description="MRE Clip Generation Lambda Functions stack")

app.synth()
