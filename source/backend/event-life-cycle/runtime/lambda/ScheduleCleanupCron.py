#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

##############################################################################
#
# PURPOSE:
# Deletes all Past EB schedules whose Start time is at least 1 Day old. This is required to ensure that we cleanup 
# Old schedules which get accounted in the Schedule Quota limits (which at the time of writing this is 1 Million / Region / Account)
# 
##############################################################################

import boto3
import traceback
import json
from datetime import datetime, timedelta
from botocore.config import Config


boto_config = Config(
                retries = {
                    'max_attempts': 5,
                    'mode': 'adaptive'
                }
            )

scheduler_client = boto3.client('scheduler', config=boto_config)

def lambda_handler(event, context):
    response = scheduler_client.list_schedules(
                    MaxResults=100,
                    NamePrefix='mre-',
                    State='ENABLED'
                )
    
    start_deletion_process(response)
    while "NextToken" in response:
        response = scheduler_client.list_schedules(
                    MaxResults=100,
                    NamePrefix='mre-',
                    State='ENABLED',
                    NextToken=response['NextToken']
                )
        start_deletion_process(response)

def start_deletion_process(response):
    if 'Schedules' in response:
        # We will only Delete Schedules in the Past which are at least 24 Hrs old
        for schedule in response['Schedules']:
            # Check if the Schedule's are at least 24 hrs old and the Current DateTime is Greater than the Schedule StartTime
            schedule_obj = scheduler_client.get_schedule(Name=schedule['Name'])
            if 'ScheduleExpression' in schedule_obj:
                sch_exp = schedule_obj['ScheduleExpression']    # Will be in this Format 'at(2023-01-24T04:09:00)'
                actual_schedule_start_time = f"{sch_exp[3: len(sch_exp)-1]}Z"   #2023-01-24T04:09:00Z
                actual_schedule_start_time = datetime.strptime(actual_schedule_start_time, "%Y-%m-%dT%H:%M:%SZ")
                new_schedule_start_time = actual_schedule_start_time +  timedelta(hours=24)

                cur_utc_time = datetime.utcnow()
                if cur_utc_time > new_schedule_start_time:
                    scheduler_client.delete_schedule(Name=schedule_obj['Name'])
                    print(f"Deleted Schedule {schedule_obj['Name']} with startTime = {actual_schedule_start_time}")

def delete_schedule(schedule_name):
    try:
        scheduler_client.delete_schedule(Name=schedule_name)
        print(f"Deleted schedule_name = {schedule_name}")
    except Exception as e:
        print(f"Encountered an exception while deleting a Schedule {schedule_name} {str(e)}.")
        print(traceback.format_exc())