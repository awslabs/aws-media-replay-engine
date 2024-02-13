#!/usr/bin/env python3
from aws_cdk import App, Aspects
from stacks.ReplayStack import ReplayStack
from cdk_nag import AwsSolutionsChecks

app = App()
ReplayStack(app, 'aws-mre-replay-handler', description="MRE Replay Lambda Functions stack")
Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

app.synth()
