#!/usr/bin/env python3

#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from aws_cdk import App
from stacks.mreServiceDiscoveryStack import MreServiceDiscoveryStack

app = App()
MreServiceDiscoveryStack(app, 'aws-mre-service-discovery')
app.synth()
