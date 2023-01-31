#!/usr/bin/env python3
from aws_cdk import App
from stacks.chaliceapp import ChaliceApp

app = App()
ChaliceApp(app, 'aws-mre-event-life-cycle')

app.synth()
