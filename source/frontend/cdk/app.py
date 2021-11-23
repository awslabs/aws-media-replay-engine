'''
 Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 SPDX-License-Identifier: Apache-2.0
'''

from aws_cdk import core
from stacks.mre_frontend_stack import MreFrontendStack

app = core.App()

MreFrontendStack(app, "mre-frontend-stack")

app.synth()