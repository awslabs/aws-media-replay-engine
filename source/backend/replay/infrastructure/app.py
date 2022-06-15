#!/usr/bin/env python3
from aws_cdk import App
from stacks.ReplayStack import ReplayStack

app = App()
ReplayStack(app, 'aws-mre-replay-handler', description="MRE Replay Lambda Functions stack")
app.synth()
