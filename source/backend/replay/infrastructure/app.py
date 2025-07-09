#!/usr/bin/env python3
from aws_cdk import App, Aspects
from cdk_nag import AwsSolutionsChecks
from stacks.ReplayStack import ReplayStack

app = App()
ReplayStack(app, 'aws-mre-replay-handler', description="MRE Replay Lambda Functions stack")
Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

app.synth()
