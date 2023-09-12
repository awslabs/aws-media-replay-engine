#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import boto3
import os
import json
import uuid
import datetime
from botocore.config import Config
import subprocess
from queue import Queue
import threading
from subprocess import Popen
from aws_lambda_powertools import Logger
logger = Logger()


# Represents the number of Latest S3 Key Prefix names whose Objects will be Synced to the /tmp folder in this Lambda
# We limit it to 2 for CatchUp since the objects with older S3 Key Prefixes would be synched and processed already
NUMBER_OF_LOOKUP_PARTITIONS_FOR_CATCHUP = 2

# Represents the number of Latest S3 Key Prefix names whose Objects will be Synced to the /tmp folder in this Lambda
NUMBER_OF_LOOKUP_PARTITIONS_FOR_NON_CATCHUP = 10

MRE_CACHE_BUCKET = os.environ['CACHE_BUCKET_NAME']
ENABLE_CUSTOM_METRICS = os.environ['ENABLE_CUSTOM_METRICS']

client = boto3.client('cloudwatch')


class CacheSyncManager:
    '''
        Class provides methods to run the S3 Sync command concurrently to increase throughput on MRE-Segment-Feature mapping cache objects
    '''

    def __init__(self, isCatchUp: bool, cache_s3_key_prefixes: list, event, program, replay_id):

        self.__cache_s3_key_prefixes = cache_s3_key_prefixes    # For ex. 1/seg_xx_xx_1.json, 5/seg_xx_xx_2.json, 5/seg_xx_xx_1.json
        self.__isCatchup_replay = isCatchUp
        self.event_name = event
        self.program_name = program
        self.replay_id = replay_id

        # Create a sub folder in tmp
        self.__create_folder_in_temp()
    

    def __create_folder_in_temp(self) -> None:
        os.chdir("/tmp")
        if not os.path.exists(os.path.join(self.replay_id)):
            os.makedirs(self.replay_id)
        os.chdir("/")
    
    def sync_cache(self):

        
        # Sort ascending based on S3 Key Prefix. This is used during Catchup to Sync last 2 partitions from S3
        self.__cache_s3_key_prefixes.sort()

        final_s3_key_prefixes_to_sync = []

        # For Catchup replays, we will sync the Cache from Last S3 Key Partitions 
        if self.__isCatchup_replay:

            # For CatchUp replays we spin up a Max of 10 SubProcess to execute the Sync command from S3. This is due to the default 
            # Parallel execution threshold S3 enforces
            # Group the number of Key Prefixes into lists of 10
            groups_of_key_prefixes = [self.__cache_s3_key_prefixes[x:x+NUMBER_OF_LOOKUP_PARTITIONS_FOR_NON_CATCHUP] for x in range(0, len(self.__cache_s3_key_prefixes), NUMBER_OF_LOOKUP_PARTITIONS_FOR_NON_CATCHUP)]
            
            logger.info('Synching Cache files for CatchUp replay ...')
            logger.info(f"CacheSyncManagerCatchup Replay {self.replay_id}. Number of ALL Cache S3 Key Prefixes = {len(self.__cache_s3_key_prefixes)}")
            logger.info(f"CacheSyncManager-Catchup - Length of 10 group items in groups_of_key_prefixes = {len(groups_of_key_prefixes)}")
            logger.info(f'CacheSyncManager-Catchup Replay. groups_of_key_prefixes = {groups_of_key_prefixes}')
            
            start_time = datetime.datetime.now()
            for key_prefix_group in groups_of_key_prefixes:
                final_s3_key_prefixes_to_sync = []
                # Sync from 10 Key Prefixes at a time
                for key_prefix in key_prefix_group:
                    final_s3_key_prefixes_to_sync.append(key_prefix)

                logger.info(f'CacheSyncManager-Catchup Replay. Selected S3 Key Prefixes = {final_s3_key_prefixes_to_sync}')
                self.__start_subprocess(final_s3_key_prefixes_to_sync)
            
            end_time = datetime.datetime.now()
            cache_sync_time_in_secs = (end_time - start_time).total_seconds()
            logger.info(f'CacheSyncManager-Catchup Replay-S3 Cache All partitions Sync Duration: {cache_sync_time_in_secs} seconds')
            self.__put_metric("CatchUpCacheSyncTime", cache_sync_time_in_secs, [{'Name': 'Function', 'Value': 'MREReplayCacheSyncManager'}, {'Name': 'EventProgramReplayId', 'Value': f"{self.event_name}#{self.program_name}#{self.replay_id}"}])

            
            """ logger.info('Synching Cache files for CatchUp replay ...')
            # If there are more than 2 s3 key prefixes, we pick the last 2 partitions
            if len(self.__cache_s3_key_prefixes) >= NUMBER_OF_LOOKUP_PARTITIONS_FOR_CATCHUP:
                final_s3_key_prefixes_to_sync.append(self.__cache_s3_key_prefixes[-1])
                final_s3_key_prefixes_to_sync.append(self.__cache_s3_key_prefixes[-2])

                logger.info(f'CacheSyncManager-Catchup Replay. More than 2 Key Prefixes found. Selecting last 2 S3 Key Prefixes = {final_s3_key_prefixes_to_sync}')
            elif len(self.__cache_s3_key_prefixes) < NUMBER_OF_LOOKUP_PARTITIONS_FOR_CATCHUP:
                final_s3_key_prefixes_to_sync.extend(self.__cache_s3_key_prefixes)
                logger.info(f'CacheSyncManager-Catchup Replay. One Prefix found. Selecting ONE S3 Key Prefix = {final_s3_key_prefixes_to_sync}')

            start_time = datetime.datetime.now()
            self.__start_subprocess(final_s3_key_prefixes_to_sync)
            end_time = datetime.datetime.now()
            cache_sync_time_in_secs = (end_time - start_time).total_seconds()
            logger.info(f'CacheSyncManager-Catchup Replay-S3 Cache Sync Duration: {cache_sync_time_in_secs} seconds')
            self.__put_metric("CatchUpCacheSyncTime", cache_sync_time_in_secs, [{'Name': 'Function', 'Value': 'MREReplayCacheSyncManager'}, {'Name': 'EventProgramReplayId', 'Value': f"{self.event_name}#{self.program_name}#{self.replay_id}"}]) """

        else:
            # For non CatchUp replays we spin up a Max of 10 SubProcess to execute the Sync command from S3. This is due to the default 
            # Parallel execution threshold S3 enforces
            # Group the number of Key Prefixes into lists of 10
            groups_of_key_prefixes = [self.__cache_s3_key_prefixes[x:x+NUMBER_OF_LOOKUP_PARTITIONS_FOR_NON_CATCHUP] for x in range(0, len(self.__cache_s3_key_prefixes), NUMBER_OF_LOOKUP_PARTITIONS_FOR_NON_CATCHUP)]
            
            logger.info('Synching Cache files for NON CatchUp replay ...')
            logger.info(f"CacheSyncManager-Non Catchup Replay {self.replay_id}. Number of ALL Cache S3 Key Prefixes = {len(self.__cache_s3_key_prefixes)}")
            logger.info(f"Length of 10 group items in groups_of_key_prefixes = {len(groups_of_key_prefixes)}")
            logger.info(f'CacheSyncManager-Non Catchup Replay. groups_of_key_prefixes = {groups_of_key_prefixes}')
            
            start_time = datetime.datetime.now()
            for key_prefix_group in groups_of_key_prefixes:
                final_s3_key_prefixes_to_sync = []
                # Sync from 10 Key Prefixes at a time
                for key_prefix in key_prefix_group:
                    final_s3_key_prefixes_to_sync.append(key_prefix)

                logger.info(f'CacheSyncManager-NONCatchup Replay. Selected S3 Key Prefixes = {final_s3_key_prefixes_to_sync}')
                self.__start_subprocess(final_s3_key_prefixes_to_sync)
            
            end_time = datetime.datetime.now()
            cache_sync_time_in_secs = (end_time - start_time).total_seconds()
            logger.info(f'CacheSyncManager-NonCatchup Replay-S3 Cache All partitions Sync Duration: {cache_sync_time_in_secs} seconds')
            self.__put_metric("NoCatchUpCacheSyncTime", cache_sync_time_in_secs, [{'Name': 'Function', 'Value': 'MREReplayCacheSyncManager'}, {'Name': 'EventProgramReplayId', 'Value': f"{self.event_name}#{self.program_name}#{self.replay_id}"}])

        cached_files = os.listdir(f"/tmp/{self.replay_id}")
        logger.info(f"=====Number of cached files Synced into tmp/{self.replay_id} = {len(cached_files)}==========")
        logger.info(f"=====All cached files from tmp/{self.replay_id} = {cached_files}==========")


    def __start_subprocess(self, final_s3_key_prefixes_to_sync: list):
        sync_commands = []
        for prefix in final_s3_key_prefixes_to_sync:
            sync_commands.append(f"/opt/awscli/aws s3 sync 's3://{MRE_CACHE_BUCKET}/{prefix}' /tmp/{self.replay_id}/")

        processes = [Popen(cmd, shell=True) for cmd in sync_commands]
        for p in processes: 
            p.wait()

        

    def __put_metric(self, metric_name, metric_value, dimensions: list):

        if ENABLE_CUSTOM_METRICS.lower() in ['yes', 'y']:
            client.put_metric_data(
            Namespace='MRE',
            MetricData=[
                {
                    'MetricName': metric_name,
                    'Dimensions': dimensions,
                    'Value': metric_value * 1000,
                    'Unit': 'Milliseconds'
                },
            ]
    )