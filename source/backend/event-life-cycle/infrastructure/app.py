#!/usr/bin/env python3
from aws_cdk import App, Aspects
from stacks.chaliceapp import ChaliceApp
from cdk_nag import AwsSolutionsChecks

app = App()
ChaliceApp(app, 'aws-mre-event-life-cycle')
Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

app.synth()
