#!/usr/bin/env python3
from aws_cdk import App, Aspects
from stacks.ClipGenStack import ClipGenStack
from cdk_nag import AwsSolutionsChecks

app = App()
ClipGenStack(app, 'aws-mre-clip-generation', description="MRE Clip Generation Lambda Functions stack")
Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

app.synth()
