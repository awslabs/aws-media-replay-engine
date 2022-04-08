#!/usr/bin/env python3
from aws_cdk import core as cdk
from stacks.eventSchedulerStack import EventSchedulerStack

app = cdk.App()
EventSchedulerStack(app, 'aws-mre-event-scheduler', description="MRE Event Scheduler stack")
app.synth()
