#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import boto3
from decimal import Decimal
from datetime import datetime

s3_client = boto3.client('s3')

class CacheDiscovery:
    def __init__(self, cache_bucket_name, program_name, event_name, profile_name) -> None:
        self.cache_bucket_name = cache_bucket_name
        self.program_name = program_name
        self.event_name = event_name
        self.profile_name = profile_name


    def discover_cache_key_prefixes(self) -> list:
        '''
            Returns the Key Prefixes created for an MRE Event
        '''

        result = s3_client.list_objects_v2(Bucket=self.cache_bucket_name, Prefix=f"{self.program_name}/{self.event_name}/", Delimiter='/')
            
        if 'CommonPrefixes' in result:

            # Get all Key Prefixes by Ignoring a key prefix in the name of the Profile.
            key_prefixes = [x['Prefix'] for x in result["CommonPrefixes"] if self.profile_name not in x['Prefix']]
            return key_prefixes
            
        return []
