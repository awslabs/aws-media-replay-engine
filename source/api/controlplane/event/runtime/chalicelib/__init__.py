#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import json
import random
import string
from decimal import Decimal


def load_api_schema():
    api_schema = {}
    schema_dir = os.path.dirname(__file__) + "/apischema/"

    for file in os.listdir(schema_dir):
        with open(schema_dir + file) as schema_file:
            schema = json.load(schema_file)
            schema_title = schema["title"]
            api_schema[schema_title] = schema
            print(f"Loaded schema: {schema_title}")

    return api_schema

def replace_floats(obj):
    if isinstance(obj, list):
        return [replace_floats(o) for o in obj]
    elif isinstance(obj, dict):
        return {k: replace_floats(v) for k, v in obj.items()}
    elif isinstance(obj, float):
        return Decimal(obj)
    else:
        return obj

def replace_decimals(obj):
    if isinstance(obj, list):
        return [replace_decimals(o) for o in obj]
    elif isinstance(obj, dict):
        return {k: replace_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    else:
        return obj

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        if isinstance(obj, set):
            return list(obj)
        
        return super(DecimalEncoder, self).default(obj)
