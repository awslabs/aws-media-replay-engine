#!/usr/bin/env python3
from aws_cdk import App
from stacks.chaliceapp import ChaliceApp

app = App()
ChaliceApp(app, 'aws-mre-gateway', description="MRE Gateway API reverse proxy stack. Implements IAM based Auth and JWT token based Auth based routes.")

app.synth()
