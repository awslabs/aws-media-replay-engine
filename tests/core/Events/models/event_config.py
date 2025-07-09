# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from dataclasses import dataclass, field

@dataclass
class EventConfig:
    GenerateOrigClips: bool = False
    GenerateOptoClips: bool = False
    GenerateOrigThumbNails: bool = False
    GenerateOptoThumbNails: bool = False
    FutureEvent: bool = False
    EventName: str = None
    


@dataclass
class MediaLiveEventConfig(EventConfig):
    Channel: str = None
    
@dataclass
class BYOBEventConfig(EventConfig):
    SourceVideoBucket: str = None
    