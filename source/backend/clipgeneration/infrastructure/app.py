#!/usr/bin/env python3
from aws_cdk import App
from stacks.ClipGenStack import ClipGenStack

app = App()
ClipGenStack(app, 'aws-mre-clip-generation', description="MRE Clip Generation Lambda Functions stack")

app.synth()
