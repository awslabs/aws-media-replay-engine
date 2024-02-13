#!/usr/bin/env python3
from aws_cdk import App, Aspects
from stacks.chaliceapp import ChaliceApp
from cdk_nag import AwsSolutionsChecks

app = App()
ChaliceApp(app, 'aws-mre-gateway', description="MRE Gateway API reverse proxy stack. Implements IAM based Auth and JWT token based Auth based routes.")
Aspects.of(app).add(AwsSolutionsChecks(verbose=True))
app.synth()
