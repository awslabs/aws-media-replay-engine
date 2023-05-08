[![Header](../assets/images/mre-header-1.png)](../../MRE-Developer-Guide.md)

# Developers Guide - Events

## Creating events with automation

Events can be automatically synchronized with your EPG data source using a provided MRE API. A queue is advised to bridge live EPG update sources to MRE where a Lambda function can filter as desired.

![create-events](../assets/images/devguide-create-events.png)

As it relates to managing events in the **MRE Console** you can:
- Add an event
- Delete an event
- View events

Using the **MRE API** you can:
- Add an event
- Update an event
- Delete an event
- View events
- Search for events and more

Before creating an event, consider two attributes that are helpful to organize them in MRE. The attribute **Program** groups events. An example is a large multi-day tournament that can be set as the **Program** name (2022 Winter Olympics).

The payload to the **event** API takes a payload that is described here:

[POST /event](https://htmlpreview.github.io/?https://github.com/awslabs/aws-media-replay-engine/blob/main/docs/source/output/api/controlplane-event.html#create-event)

Below are Python code snippets that are useful to perform the  

```
def update_event(event_name, program, event_payload):
    path = f"/event/{event_name}/program/{program}"
    method = "PUT"
    event_headers = {
        "Content-Type": "application/json"
    }
    return invoke_api(path, method,headers=event_headers, body=json.dumps(event_payload))

def get_event(event_name, program):
    path = f"/event/{event_name}/program/{program}"
    method = "GET"
    event_headers = {
        "Content-Type": "application/json"
    }
    return invoke_api(path, method,headers=event_headers)

def create_event(event_payload):
    path = "/event"
    method = "POST"
    event_headers = {
        "Content-Type": "application/json"
    }
    return invoke_api(path, method,headers=event_headers, body=json.dumps(event_payload))
```

## Subscribing to Event life cycle events in MRE


MRE emits Event Life Cycle events to Amazon EventBridge to enable external process to Start delivering source video chunks to a S3 bucket and to end the external process when an event is complete. When scheduling an Event in MRE, ensure that the  BootstrapTimeInMinutes, DurationMinutes and Start time attributes are set appropriately when invoking the Event API.

- MRE emits VOD_EVENT_START / LIVE_EVENT_START events to EventBridge for an event to start. 

    - For VOD events, MRE sends the VOD_EVENT_START  event to EventBridge as soon as an Event is Created within MRE.
    - For LIVE events, MRE sends the LIVE_EVENT_START event to EventBridge at a future time ( EventStartTime (Start attribute) - BootstrapTimeInMinutes ).

- MRE emits VOD_EVENT_END / LIVE_EVENT_END events to EventBridge when an Event ends. 

    - For VOD events, MRE sends the VOD_EVENT_END event to EventBridge at a future time ( EventStartTime (Start attribute) + BootstrapTimeInMinutes + DurationMinutes).
    - For LIVE events, MRE sends the LIVE_EVENT_END event to EventBridge at a future time ( EventStartTime (Start attribute) + DurationMinutes).
  
## Context Variables

Events can also include **Context Variables**, key/value pairs which provide additional data to be read by the plugins used in the workflow. Use cases for this include:

- Custom attributes to coorindate with external processing
- Common attribute values used across all plugin executions (i.e. time offset, broadcast id, etc.)
- Sharing data between plugin executions across all chunks (i.e. a value from chunk 1 gets passed to chunk 2, chunk 2 adds more data for chunk 3, etc.)

When you create the Event, and select a profile, you will have the option to modify the Profile Context Variable values & add additional Context Variables as well. The Profile Context Variables serve as the template for which future events will be created when selecting the profile.

```
{
	"TimeOffset": 12,
	"BroadcastId": 12345,
	"EventData": "New Data"
}
```
