# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

#!/usr/bin/env python3

import os
from aws_cdk import App, Environment
from stacks.mre_plugins_stack import MrePluginsStack

cdk_env = Environment(account=os.environ['CDK_DEFAULT_ACCOUNT'],
                      region=os.environ['CDK_DEFAULT_REGION'])

# new MyDevStack(app, 'dev', {
#   env: {
#     account: process.env.CDK_DEFAULT_ACCOUNT,
#     region: process.env.CDK_DEFAULT_REGION
# }});

app = App()
MrePluginsStack(app, "aws-mre-plugin-samples", env=cdk_env)

app.synth()
