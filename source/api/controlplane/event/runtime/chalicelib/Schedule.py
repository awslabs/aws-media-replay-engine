#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass, field

@dataclass
class Schedule:
    schedule_name: str
    event_name: str
    program_name: str
    event_start_time: str
    is_vod_event: bool
    bootstrap_time_in_mins: float
    event_duration_in_mins: float
    resource_arn: str
    execution_role: str
    input_payload: str
    stop_channel: bool = field(default=False)
    schedule_name_prefix: str = field(default="")
    
