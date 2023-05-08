# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import shlex
import subprocess
import sys


if sys.argv[1] == 'serve':
    from sagemaker_mxnet_serving_container import serving
    serving.main()
else:
    subprocess.check_call(shlex.split(' '.join(sys.argv[1:])))

# prevent docker exit
subprocess.call(['tail', '-f', '/dev/null'])
