#!/usr/bin/env python3
from aws_cdk import App, Aspects
from stacks.DataExporter import MreDataExporter
from cdk_nag import AwsSolutionsChecks

app = App()
MreDataExporter(app, 'aws-mre-data-exporter', description="MRE Data Export Lambda Functions stack")
Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

app.synth()
