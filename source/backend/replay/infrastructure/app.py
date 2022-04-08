#!/usr/bin/env python3
from aws_cdk import core as cdk
from stacks.ReplayStack import ReplayStack

app = cdk.App()
ReplayStack(app, 'aws-mre-replay-handler', description="MRE Replay Lambda Functions stack")
app.synth()
