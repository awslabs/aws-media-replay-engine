#!/usr/bin/env python3
from aws_cdk import core as cdk
from stacks.DataExporter import MreDataExporter

app = cdk.App()
MreDataExporter(app, 'aws-mre-data-exporter', description="MRE Data Export Lambda Functions stack")
app.synth()
