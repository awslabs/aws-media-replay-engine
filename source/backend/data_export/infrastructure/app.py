#!/usr/bin/env python3
from aws_cdk import App
from stacks.DataExporter import MreDataExporter

app = App()
MreDataExporter(app, 'aws-mre-data-exporter', description="MRE Data Export Lambda Functions stack")
app.synth()
