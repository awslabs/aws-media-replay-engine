# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json

# Load a json file from current path
def load_config(file_name):
    with open(file_name, 'r') as f:
        return json.load(f)