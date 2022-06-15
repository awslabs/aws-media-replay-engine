#!/usr/bin/env python3
from aws_cdk import App
from stacks.eventSchedulerStack import EventSchedulerStack

app = App()
EventSchedulerStack(app, 'aws-mre-event-scheduler', description="MRE Event Scheduler stack")
app.synth()
