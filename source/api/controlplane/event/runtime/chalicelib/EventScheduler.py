#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import json
import boto3
from datetime import datetime, timedelta
import uuid
import os
from chalicelib.Schedule import Schedule

scheduler_client = boto3.client('scheduler')

EB_SCHEDULE_ROLE_ARN = os.environ['EB_SCHEDULE_ROLE_ARN']
class EventScheduler():
    def __init__(self,) -> None:
        pass
    
    def delete_schedule(self, schedule_name):
        try:
            
            scheduler_client.delete_schedule(
                                Name=schedule_name
                            )
            print(f"Deleted schedule_name = {schedule_name}")
        except Exception as e:
            print(f"Encountered an exception while deleting a Schedule {schedule_name} {str(e)}")


    def update_schedule_event_bridge_target(self, schedule: Schedule, chunk_source_details=None) -> None:
        
        scheduled_time, schedule_name, schedule_payload = self.get_schedule_details(schedule, chunk_source_details)

        try:
            

            scheduler_client.update_schedule(Name=schedule_name,
                                        ScheduleExpression=f'at({scheduled_time})',
                                        FlexibleTimeWindow={
                                            'Mode': 'OFF'
                                        },
                                        Target={
                                        "EventBridgeParameters":{
                                            'DetailType': "MRE Event Start or End Message",
                                            'Source': 'awsmre'
                                        },
                                        'Arn': schedule.resource_arn,
                                        'RoleArn': EB_SCHEDULE_ROLE_ARN,
                                        "Input":json.dumps(schedule_payload)
                                        })

        except Exception as e:
            print(f"Error while getting the Schedule {schedule_name} : {str(e)}")
            raise


    def get_schedule_details(self, schedule: Schedule, chunk_source_details=None) -> None:
        schedule_name = schedule.schedule_name
        
        if schedule.is_vod_event:
            event_state = "VOD_EVENT_END"

            cur_utc_time = datetime.utcnow()

            # End  a VOD Event at START + BOOTSTRAP + EVENT DURATION
            event_end_utc_time = cur_utc_time + timedelta(minutes=schedule.bootstrap_time_in_mins) + timedelta(minutes=schedule.event_duration_in_mins)
            scheduled_time = event_end_utc_time.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            event_state = "LIVE_EVENT_END" if schedule.schedule_name_prefix == "event-end" else "LIVE_EVENT_START"

            # Start  a LIVE Event at START - BOOTSTRAP DURATION
            if event_state == "LIVE_EVENT_START":
                final_event_utc_time = schedule.event_start_time - timedelta(minutes=schedule.bootstrap_time_in_mins)
            else:
                # Handling LIVE_EVENT_END
                # End  a LIVE Event at START + EVENT DURATION
                final_event_utc_time = schedule.event_start_time + timedelta(minutes=schedule.event_duration_in_mins)

            scheduled_time = final_event_utc_time.strftime("%Y-%m-%dT%H:%M:%S")

        
        schedule_payload = {
                "State": event_state,
                "Event": schedule.event_name,
                "Program": schedule.program_name,
                "IsVODEvent": schedule.is_vod_event,
                "ScheduleName": schedule_name,
                "StopChannel": schedule.stop_channel
            }
        if chunk_source_details:
            schedule_payload["ChunkSourceDetail"] = chunk_source_details

        return scheduled_time, schedule_name, schedule_payload

    def create_schedule_event_bridge_target(self, schedule: Schedule, chunk_source_details=None) -> None:
        scheduled_time, schedule_name, schedule_payload = self.get_schedule_details(schedule, chunk_source_details)

        scheduler_client.create_schedule(Name=schedule_name,
                                        ScheduleExpression=f'at({scheduled_time})',
                                        FlexibleTimeWindow={
                                            'Mode': 'OFF'
                                        },
                                        Target={
                                        "EventBridgeParameters":{
                                            'DetailType': "MRE Event Start or End Message",
                                            'Source': 'awsmre'
                                        },
                                        'Arn': schedule.resource_arn,
                                        'RoleArn': EB_SCHEDULE_ROLE_ARN,
                                        "Input":json.dumps(schedule_payload)
                                        }
                                        
                                    )
        return schedule_name