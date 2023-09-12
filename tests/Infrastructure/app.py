# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

#!/usr/bin/env python3
import aws_cdk as cdk
from stack import MreTestSuiteStack

app = cdk.App()
apiStack = MreTestSuiteStack(app, "aws-mre-test-suite", env=cdk.Environment())
app.synth()
