import os
import json
import boto3
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import AttributeNotExists, Key, Attr
from decimal import Decimal

EVENT_SCHEDULER_BUFFER_TIME_IN_MINS = os.environ['EVENT_SCHEDULER_BUFFER_TIME_IN_MINS']
EVENT_SCHEDULER_BOOTSTRAP_TIME_IN_MINS = os.environ['EVENT_SCHEDULER_BOOTSTRAP_TIME_IN_MINS']
EVENT_SCHEDULER_TIME_TO_LIVE_STREAM_IN_MINS = os.environ['EVENT_SCHEDULER_TIME_TO_LIVE_STREAM_IN_MINS']
EVENT_SCHEDULER_PAST_EVENTS_IN_SCOPE = os.environ['EVENT_SCHEDULER_PAST_EVENTS_IN_SCOPE']
EVENT_SCHEDULER_PAST_EVENT_START_DATE = os.environ['EVENT_SCHEDULER_PAST_EVENT_START_DATE_UTC']
EVENT_SCHEDULER_PAST_EVENT_END_DATE = os.environ['EVENT_SCHEDULER_PAST_EVENT_END_DATE_UTC']
EVENT_SCHEDULER_CONCURRENT_EVENTS = os.environ['EVENT_SCHEDULER_CONCURRENT_EVENTS']
EVENT_SCHEDULER_FUTURE_EVENTS_IN_SCOPE = os.environ['EVENT_SCHEDULER_FUTURE_EVENTS_IN_SCOPE']

EVENT_TABLE_NAME = os.environ['EVENT_TABLE_NAME']
CURRENT_EVENTS_TABLE_NAME = os.environ['CURRENT_EVENTS_TABLE_NAME']
EB_EVENT_BUS_NAME = os.environ['EB_EVENT_BUS_NAME']

ddb_resource = boto3.resource("dynamodb")
eb_client = boto3.client("events")

class MREEventScheduler:
    def process_events(self):
        
        # Process any Future events in the next 1 Hr
        if EVENT_SCHEDULER_FUTURE_EVENTS_IN_SCOPE == "TRUE":
            future_events = self.get_future_events()
            print(f"Found {len(future_events)} future events")
            self.__process_future_events(future_events)
            self.__start_future_events_harvesting(future_events)

        # Process Past Events if the Config says so
        if EVENT_SCHEDULER_PAST_EVENTS_IN_SCOPE == "TRUE":
            past_events = self.get_past_events()
            print(f"Found {len(past_events)} past events")
            self.__process_past_events(past_events)
            self.__start_past_events_harvesting(past_events)

    def __start_future_events_harvesting(self, future_events):
        events_scheduled = self.get_events_scheduled()
        
        for future_event in future_events:
            event_start_time = future_event['Start']

            cur_utc_time = datetime.utcnow()

            # If Event starts soon and has an EC2 Provisioned, send an event to EventBridge 
            # to initiate Stream harvesting
            # Make sure we are honoring concurrency limits and that the event processing is Idempotent
            if  (datetime.strptime(event_start_time, '%Y-%m-%dT%H:%M:%SZ') - cur_utc_time).seconds <= 60 and \
                self.is_event_scheduled(future_event['Id']) and \
                len(events_scheduled) <= int(EVENT_SCHEDULER_CONCURRENT_EVENTS):
                
                
                # Send Msg to EventBridge to Start Harvesting the Future event HLS Stream
                self.send_event_to_eventbridge(future_event, "FUTURE_EVENT_HARVEST_NOW")

    def __start_past_events_harvesting(self, past_events):
        events_scheduled = self.get_events_scheduled()

        for past_event in past_events:
            
            # Make sure we are honoring concurrency limits and that the event processing is Idempotent
            if  self.is_event_scheduled(past_event['Id']) and \
                len(events_scheduled) <= int(EVENT_SCHEDULER_CONCURRENT_EVENTS):

                # Send Msg to EventBridge to Start Harvesting the Future event HLS Stream
                self.send_event_to_eventbridge(past_event, "PAST_EVENT_HARVEST_NOW")

    def __process_future_events(self, future_events):
        for future_event in future_events:
            
            event_start_time = future_event['Start']

            # Fall back on the Default BOOTSTRAP time defined in Env Variable if the 
            # Event does not have BOOTSTRAP time defined
            event_bootstrap_time_in_mins = int(EVENT_SCHEDULER_BOOTSTRAP_TIME_IN_MINS) if 'BootstrapTimeInMinutes' not in future_event['BootstrapTimeInMinutes'] else int(future_event['BootstrapTimeInMinutes'])
            cur_utc_time = datetime.utcnow()
            future_time = cur_utc_time + timedelta(minutes=event_bootstrap_time_in_mins + int(EVENT_SCHEDULER_BUFFER_TIME_IN_MINS))

            # Check if the current event is few minutes away from streaming
            # ---------12PM (Current Time) ------------- 3PM (Event Start time) ---------------------------------
            # BootStrap is 90 Mins, Buffer Time = 5 Mins
            # At1:30PM ------- Current Time (1:30PM) + Future Time ( 3:00 PM = CurrentTime + Boostrap in Mins + Buffer Time) - Event Start Time <= 0
            if datetime.strptime(event_start_time, '%Y-%m-%dT%H:%M:%SZ') >= cur_utc_time and datetime.strptime(event_start_time, '%Y-%m-%dT%H:%M:%SZ') <= future_time:
                # Send a Message to EventBridge for Provisioning Stream Processing Resource Architecture
                # Check the Concurrent Events value , before provisioning Stream Processing Resources
                events_scheduled = self.get_events_scheduled()

                # Make sure we are honoring concurrency limits and that the event processing is Idempotent
                if len(events_scheduled) <= int(EVENT_SCHEDULER_CONCURRENT_EVENTS) and not self.is_event_scheduled(future_event['Id']):
                    
                    # Send Msg to EventBridge for Provisioning AWS Resources to Process Input Video Source
                    result = self.send_event_to_eventbridge(future_event, "FUTURE_EVENT_TO_BE_HARVESTED")
                    
                    # Push Event into CURRENT_EVENTS table so it gets accounted for concurrent tables pending processing
                    if result:
                        self.schedule_event(future_event)
                        print('Future Event has been scheduled ...')
                else:
                    print('Max Concurrent events have scheduled ...')


    def send_event_to_eventbridge(self, event, event_state):
        # Send Msg to EventBridge for Provisioning AWS Resources to Process Input Video Source

        if 'ProgramId' not in event or 'SourceVideoUrl' not in event:
            return False

        detail = {
            "State": event_state,
            "Event": {
                "Name": event['Name'],
                "Program": event['Program'],
                "ProgramId": event['ProgramId'],
                "SourceVideoAuth": event['SourceVideoAuth'],
                "SourceVideoUrl": event['SourceVideoUrl']
            }
        }

        response = eb_client.put_events(
            Entries=[
                {
                    "Source": "awsmre",
                    "DetailType": "Event ready to be scheduled",
                    "Detail": json.dumps(detail),
                    "EventBusName": EB_EVENT_BUS_NAME
                }
            ]
        )

        if response["FailedEntryCount"] > 0:
            print(f"Failed to send the event status to EventBridge for event '{event['Name']}' in program '{event['Program']}'. More details below:")
            print(response["Entries"])
            return False

        return True
    
    def __process_past_events(self, past_events):
        for past_event in past_events:
        
            events_scheduled = self.get_events_scheduled()

            # Make sure we are honoring concurrency limits and that the event processing is Idempotent
            if len(events_scheduled) <= int(EVENT_SCHEDULER_CONCURRENT_EVENTS) and not self.is_event_scheduled(past_event['Id']):
                
                # Send Msg to EventBridge for Provisioning AWS Resources to Process Input Video Source
                result = self.send_event_to_eventbridge(past_event, "PAST_EVENT_TO_BE_HARVESTED")

                if result:

                    # Push Event into CURRENT_EVENTS table so it gets accounted for concurrent tables pending processing
                    self.schedule_event(past_event)

                    print('Past Event has been scheduled ...')
            else:
                print('Max Concurrent events have scheduled ...')

    def is_event_scheduled(self, eventId):
        current_events_table = ddb_resource.Table(CURRENT_EVENTS_TABLE_NAME)
        response = current_events_table.get_item(
            Key={
                "EventId": eventId
            },
            ConsistentRead=True
        )
        return False if "Item" not in response else True

    def _get_events(self, filter_expression):
        event_table = ddb_resource.Table(EVENT_TABLE_NAME)
        response = event_table.scan(
            FilterExpression=filter_expression,
            ConsistentRead=True,
            ProjectionExpression="Profile, #status, #program, #created, FrameRate, #eventId, #start, #eventname, #programid, #srcvideoAuth, #srcvideoUrl, #bootstrapTimeInMinutes",
            ExpressionAttributeNames = {'#status': 'Status', '#created': 'Created', '#program' : 'Program', '#eventId' : 'Id', '#start': 'Start', '#eventname' : 'Name',
                "#programid": "ProgramId", "#srcvideoAuth": "SourceVideoAuth", "#srcvideoUrl": "SourceVideoUrl", "#bootstrapTimeInMinutes" : "BootstrapTimeInMinutes"
            }
        )
        return response["Items"]

    def get_past_events(self):
        '''
            Gets all past events based on a Date Range
        '''
        all_past_events = []
        try:
            
            cur_utc_time = datetime.utcnow()

            
            filter_expression = Attr("Start").between(EVENT_SCHEDULER_PAST_EVENT_START_DATE, EVENT_SCHEDULER_PAST_EVENT_END_DATE) & Attr("Start").lte(cur_utc_time.strftime("%Y-%m-%dT%H:%M:%SZ")) & Attr("Status").eq('Queued')

            past_events = self._get_events(filter_expression)
            for past_event in past_events:
                # Ignore any event which uses MediaLive Channel
                if "Channel" not in past_event:
                    all_past_events.append(past_event)

        except Exception as e:
            print(f"Unable to list range based events: {str(e)}")
            
        
        else:
            if len(all_past_events) > 0:
                # Sort future events Desc based on Event Start Datetime 
                sorted_past_events = sorted(all_past_events, key=lambda x: x['Start'], reverse=True)
                return replace_decimals(sorted_past_events)
            else:
                return []


    def get_events_scheduled(self):
        '''
            Gets all events scheduled for processing
        '''
        try:

            current_events_table = ddb_resource.Table(CURRENT_EVENTS_TABLE_NAME)
            response = current_events_table.scan(
                    ConsistentRead=True
                )
            current_events = response["Items"]

            while "LastEvaluatedKey" in response:
                response = current_events_table.scan(
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                    ConsistentRead=True
                )
                current_events.extend(response["Items"])

        except Exception as e:
            print(f"Unable to get count of current events: {str(e)}")
            raise Exception(f"Unable to get count of current events: {str(e)}")
        
        else:
            return replace_decimals(current_events)
    
    def schedule_event(self, event):
        '''
            Puts an Event into the CurrentEvents table which is used as a way to track Concurrent Events scheduled to be processed
        '''
        try:

            current_events_table = ddb_resource.Table(CURRENT_EVENTS_TABLE_NAME)
            current_events_table.put_item(
            Item={
                "EventId": event["Id"],
                "Program": event["Program"],
                "Status": "Event_ToBe_Scheduled",
                "CreatedDateTime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            }
        )

        except Exception as e:
            print(f"Unable to get count of current events: {str(e)}")
            raise Exception(f"Unable to get count of current events: {str(e)}")


    def get_future_events(self):
        '''
            Gets all future events whose Start time lies in the next 1 Hr
        '''
        all_future_events = []
        try:

            
            cur_utc_time = datetime.utcnow()

            # Look for Events scheduled in the next 1 Hr
            future_time_one_hr_away = cur_utc_time + timedelta(hours=1)

            filter_expression = Attr("Start").between(cur_utc_time.strftime("%Y-%m-%dT%H:%M:%SZ"), future_time_one_hr_away.strftime("%Y-%m-%dT%H:%M:%SZ")) & Attr("Status").eq('Queued')
            
            future_events = self._get_events(filter_expression)

            for future_event in future_events:
                # Ignore any event which uses MediaLive Channel
                if "Channel" not in future_event:
                    all_future_events.append(future_event)

        except Exception as e:
            print(f"Unable to list future events: {str(e)}")
            
        else:
            if len(all_future_events) > 0:
                # Sort future events Ascending based on Event Start Datetime
                sorted_future_events = sorted(all_future_events, key=lambda x: x['Start'], reverse=False)
                return replace_decimals(sorted_future_events)   
            else:
                return []


def schedule_events_for_processing(event, context):
    # Get all Events from MRE which are Queued and whose ActualStart time is in the Future
    # If FutureActualStartTime - CurrentTime <= BootStrap Time
    # Send a Msg to EventBridge - To Provision AWS Resources for Streaming HLS Streams and create Chunks
    scheduler = MREEventScheduler()
    scheduler.process_events()



def replace_decimals(obj):
    if isinstance(obj, list):
        return [replace_decimals(o) for o in obj]
    elif isinstance(obj, dict):
        return {k: replace_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    else:
        return obj
